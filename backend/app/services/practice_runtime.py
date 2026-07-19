"""
PracticeRuntime — Self-testing lifecycle service.

Per Contract /vision/contracts/practice.html:
- Creates practices with questions (I2: from Knowledge gaps)
- Records immutable attempts (I3: append-only)
- AI reviews without revealing correct answer (I4)
- Publishes BreakthroughDetected on depth transitions
"""

from __future__ import annotations
import logging
from uuid import UUID
from app.domain.practice.aggregates import Practice, PracticeState, Question, Attempt
from app.infrastructure.db.repositories.practice_repo import PracticeRepo

logger = logging.getLogger(__name__)


class PracticeRuntime:
    def __init__(self, event_bus=None):
        self.repo = PracticeRepo()
        self._event_bus = event_bus

    async def _publish(self, event) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(event)
            except Exception:
                logger.exception("Failed to publish %s", type(event).__name__)

    async def create_practice(self, ws_id: UUID, user_id: UUID,
                               title: str = "",
                               questions: list[dict] | None = None) -> Practice:
        """Create a new practice. Contract I2: questions from knowledge gaps."""
        practice = Practice(workspace_id=ws_id, title=title)
        self.repo.save(practice)

        if questions:
            for i, q_data in enumerate(questions, 1):
                q = Question(
                    practice_id=practice.id,
                    seq=i,
                    text=q_data.get("text", ""),
                    concept_ids=q_data.get("concept_ids", ""),
                    context_source=q_data.get("context_source", ""),
                    correct_answer=q_data.get("correct_answer", ""),
                )
                self.repo.save_question(q)
            practice.total_questions = len(questions)
            self.repo.save(practice)

        from shared.events_practice import PracticeStarted
        await self._publish(PracticeStarted(
            practice_id=str(practice.id), workspace_id=str(ws_id),
            user_id=str(user_id), title=title,
        ))
        logger.info("Practice created: %s in workspace %s", practice.id, ws_id)
        return practice

    async def start_practice(self, practice_id: UUID, user_id: UUID) -> Practice:
        practice = self.repo.find_by_id(practice_id)
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")
        practice.start()
        self.repo.save(practice)
        return practice

    async def submit_attempt(self, question_id: UUID, user_id: UUID,
                              answer: str, is_correct: bool,
                              confidence: int = 0, response_time_s: float = 0.0,
                              ) -> Attempt:
        """Submit an answer. Contract I3: immutable, append-only."""
        attempt = Attempt(
            question_id=question_id, user_id=user_id,
            answer=answer, is_correct=is_correct,
            confidence=confidence, response_time_s=response_time_s,
        )
        self.repo.save_attempt(attempt)

        # Find parent practice
        db = __import__('app.infrastructure.db.database', fromlist=['get_db']).get_db()
        q_row = db.fetchone("SELECT practice_id FROM practice_questions WHERE id = %s", (str(question_id),))
        practice_id = q_row["practice_id"] if q_row else None

        # Detect breakthrough: correct answer on a previously wrong concept
        is_breakthrough = is_correct and await self._check_breakthrough(question_id, user_id)

        from shared.events_practice import AttemptSubmitted, BreakthroughDetected
        await self._publish(AttemptSubmitted(
            attempt_id=str(attempt.id), question_id=str(question_id),
            practice_id=str(practice_id) if practice_id else "",
            user_id=str(user_id), is_correct=is_correct,
            response_time_s=response_time_s,
        ))

        if is_breakthrough and practice_id:
            practice = self.repo.find_by_id(practice_id)
            await self._publish(BreakthroughDetected(
                attempt_id=str(attempt.id), question_id=str(question_id),
                practice_id=str(practice_id),
                workspace_id=str(practice.workspace_id) if practice else "",
                user_id=str(user_id),
            ))

        return attempt

    async def _check_breakthrough(self, question_id: UUID, user_id: UUID) -> bool:
        """Detect breakthrough: first correct after 2+ consecutive wrong answers."""
        db = __import__('app.infrastructure.db.database', fromlist=['get_db']).get_db()
        recent = db.fetchall(
            """SELECT is_correct FROM practice_attempts
               WHERE question_id = %s AND user_id = %s
               ORDER BY created_at DESC LIMIT 3""",
            (str(question_id), str(user_id)),
        )
        if len(recent) >= 3:
            # Most recent (current) is correct, previous 2+ are wrong → breakthrough
            return recent[0]["is_correct"] and all(not r["is_correct"] for r in recent[1:])
        return False

    async def review_attempt(self, attempt_id: UUID, comment: str) -> None:
        """AI reviews an attempt. Contract I4: provides feedback, not answer."""
        self.repo.review_attempt(attempt_id, comment)

    async def complete_practice(self, practice_id: UUID, user_id: UUID) -> Practice:
        practice = self.repo.find_by_id(practice_id)
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")

        # Calculate final stats
        questions = self.repo.find_questions(practice_id)
        correct = 0
        for q in questions:
            attempts = self.repo.find_attempts(q.id)
            if attempts:
                correct += 1 if attempts[-1].is_correct else 0

        practice.total_questions = len(questions)
        practice.correct_count = correct
        practice.complete()
        self.repo.save(practice)

        from shared.events_practice import PracticeCompleted
        await self._publish(PracticeCompleted(
            practice_id=str(practice_id),
            workspace_id=str(practice.workspace_id),
            user_id=str(user_id),
            total_questions=len(questions), correct_count=correct,
        ))
        return practice
