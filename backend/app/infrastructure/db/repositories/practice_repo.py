"""Practice Repository — raw SQL via Database class."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from app.infrastructure.db.database import get_db
from app.domain.practice.aggregates import Practice, PracticeState, Question, Attempt


def _row_to_practice(row: dict) -> Practice:
    return Practice(
        id=row["id"], workspace_id=row["workspace_id"],
        state=PracticeState(row["state"]), title=row.get("title", ""),
        total_questions=row.get("total_questions", 0),
        correct_count=row.get("correct_count", 0),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
        updated_at=row.get("updated_at", datetime.now(timezone.utc)),
    )


def _row_to_question(row: dict) -> Question:
    return Question(
        id=row["id"], practice_id=row["practice_id"],
        seq=row.get("seq", 1), text=row.get("text", ""),
        concept_ids=row.get("concept_ids", ""),
        context_source=row.get("context_source", ""),
        correct_answer=row.get("correct_answer", ""),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


def _row_to_attempt(row: dict) -> Attempt:
    return Attempt(
        id=row["id"], question_id=row["question_id"],
        user_id=row["user_id"], answer=row.get("answer", ""),
        is_correct=row.get("is_correct", False),
        confidence=row.get("confidence", 0),
        response_time_s=row.get("response_time_s", 0.0),
        reviewed=row.get("reviewed", False),
        review_comment=row.get("review_comment", ""),
        created_at=row.get("created_at", datetime.now(timezone.utc)),
    )


class PracticeRepo:
    def find_by_id(self, pid: UUID) -> Practice | None:
        db = get_db()
        row = db.fetchone(
            "SELECT id, workspace_id, state, title, total_questions, correct_count, "
            "created_at, updated_at FROM practices WHERE id = %s",
            (str(pid),),
        )
        return _row_to_practice(row) if row else None

    def find_by_workspace(self, ws_id: UUID) -> list[Practice]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, workspace_id, state, title, total_questions, correct_count, "
            "created_at, updated_at FROM practices WHERE workspace_id = %s "
            "ORDER BY created_at DESC",
            (str(ws_id),),
        )
        return [_row_to_practice(r) for r in rows]

    def save(self, practice: Practice) -> None:
        db = get_db()
        db.upsert("practices", {
            "id": str(practice.id), "workspace_id": str(practice.workspace_id),
            "state": practice.state.value, "title": practice.title,
            "total_questions": practice.total_questions,
            "correct_count": practice.correct_count,
            "updated_at": practice.updated_at.isoformat(),
        }, "id")

    def save_question(self, q: Question) -> None:
        db = get_db()
        db.insert("practice_questions", {
            "id": str(q.id), "practice_id": str(q.practice_id),
            "seq": q.seq, "text": q.text,
            "concept_ids": q.concept_ids,
            "context_source": q.context_source,
            "correct_answer": q.correct_answer,
        })

    def find_questions(self, practice_id: UUID) -> list[Question]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, practice_id, seq, text, concept_ids, context_source, "
            "correct_answer, created_at FROM practice_questions WHERE practice_id = %s ORDER BY seq",
            (str(practice_id),),
        )
        return [_row_to_question(r) for r in rows]

    def save_attempt(self, a: Attempt) -> None:
        db = get_db()
        db.insert("practice_attempts", {
            "id": str(a.id), "question_id": str(a.question_id),
            "user_id": str(a.user_id), "answer": a.answer,
            "is_correct": a.is_correct, "confidence": a.confidence,
            "response_time_s": a.response_time_s,
            "reviewed": a.reviewed, "review_comment": a.review_comment,
        })

    def find_attempts(self, question_id: UUID) -> list[Attempt]:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, question_id, user_id, answer, is_correct, confidence, "
            "response_time_s, reviewed, review_comment, created_at "
            "FROM practice_attempts WHERE question_id = %s ORDER BY created_at",
            (str(question_id),),
        )
        return [_row_to_attempt(r) for r in rows]

    def review_attempt(self, attempt_id: UUID, comment: str) -> None:
        db = get_db()
        db.execute(
            "UPDATE practice_attempts SET reviewed = true, review_comment = %s WHERE id = %s",
            (comment, str(attempt_id)),
        )
