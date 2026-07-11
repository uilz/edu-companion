"""Practice 聚合根。

PracticeAggregateRoot 是练习领域的聚合根，维护一个练习会话的生命周期状态。
它只负责业务规则和状态机，不直接处理持久化或事件发布。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PracticeDomainError(Exception):
    """练习域业务规则错误。"""

    pass


@dataclass
class PracticeAggregateRoot:
    """练习会话聚合根。

    状态完全由命令驱动，每次状态变更产生领域事件（以 dict 形式返回，便于序列化）。
    """

    session_id: str
    user_id: str
    bank_id: str = ""
    session_type: str = "practice"  # 'practice' | 'exam' | 'review'
    mode: str = "adaptive"
    status: str = "created"  # 'created' | 'started' | 'completed' | 'abandoned'
    question_ids: list[str] = field(default_factory=list)
    answered_question_ids: list[str] = field(default_factory=list)
    skipped_question_ids: list[str] = field(default_factory=list)
    correct_count: int = 0
    wrong_count: int = 0
    score: float = 0.0
    version: int = 0

    def start(self, question_ids: list[str]) -> dict[str, Any]:
        """开始会话，传入题目顺序。"""
        if self.status != "created":
            raise PracticeDomainError(f"Cannot start session in status {self.status}")
        self.question_ids = list(question_ids)
        self.status = "started"
        self.version += 1
        return {
            "event_type": "SessionStarted",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "question_ids": self.question_ids,
            "version": self.version,
        }

    def submit_answer(
        self,
        question_id: str,
        is_correct: bool,
        response_time_ms: int = 0,
    ) -> dict[str, Any]:
        """提交一题答案，更新聚合根状态。"""
        if self.status != "started":
            raise PracticeDomainError(f"Cannot submit answer in status {self.status}")
        if question_id not in self.question_ids:
            raise PracticeDomainError(f"Question {question_id} not in session")
        if question_id in self.answered_question_ids:
            raise PracticeDomainError(f"Question {question_id} already answered")

        self.answered_question_ids.append(question_id)
        if is_correct:
            self.correct_count += 1
        else:
            self.wrong_count += 1

        total = self.correct_count + self.wrong_count
        self.score = self.correct_count / total if total > 0 else 0.0
        self.version += 1

        return {
            "event_type": "AnswerSubmitted",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "question_id": question_id,
            "is_correct": is_correct,
            "response_time_ms": response_time_ms,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "score": self.score,
            "version": self.version,
        }

    def skip_question(self, question_id: str) -> dict[str, Any]:
        """跳过一题。"""
        if self.status != "started":
            raise PracticeDomainError(f"Cannot skip question in status {self.status}")
        if question_id not in self.question_ids:
            raise PracticeDomainError(f"Question {question_id} not in session")
        if question_id in self.answered_question_ids or question_id in self.skipped_question_ids:
            raise PracticeDomainError(f"Question {question_id} already processed")

        self.skipped_question_ids.append(question_id)
        self.version += 1

        return {
            "event_type": "QuestionSkipped",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "question_id": question_id,
            "version": self.version,
        }

    def complete(self, duration_seconds: int = 0) -> dict[str, Any]:
        """完成会话。"""
        if self.status not in ("started", "created"):
            raise PracticeDomainError(f"Cannot complete session in status {self.status}")
        self.status = "completed"
        self.version += 1
        return {
            "event_type": "SessionCompleted",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "score": self.score,
            "duration_seconds": duration_seconds,
            "version": self.version,
        }

    def to_snapshot(self) -> dict[str, Any]:
        """生成快照，用于快速重建聚合根。"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "bank_id": self.bank_id,
            "session_type": self.session_type,
            "mode": self.mode,
            "status": self.status,
            "question_ids": self.question_ids,
            "answered_question_ids": self.answered_question_ids,
            "skipped_question_ids": self.skipped_question_ids,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "score": self.score,
            "version": self.version,
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "PracticeAggregateRoot":
        """从快照重建聚合根。"""
        return cls(
            session_id=snapshot["session_id"],
            user_id=snapshot["user_id"],
            bank_id=snapshot.get("bank_id", ""),
            session_type=snapshot.get("session_type", "practice"),
            mode=snapshot.get("mode", "adaptive"),
            status=snapshot.get("status", "created"),
            question_ids=list(snapshot.get("question_ids", [])),
            answered_question_ids=list(snapshot.get("answered_question_ids", [])),
            skipped_question_ids=list(snapshot.get("skipped_question_ids", [])),
            correct_count=int(snapshot.get("correct_count", 0)),
            wrong_count=int(snapshot.get("wrong_count", 0)),
            score=float(snapshot.get("score", 0.0)),
            version=int(snapshot.get("version", 0)),
        )

    def apply_command_record(self, record_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """从命令记录恢复状态，返回产生的领域事件。"""
        if record_type == "StartSessionCommand":
            return self.start(payload.get("question_ids", []))
        if record_type == "SubmitAnswerCommand":
            return self.submit_answer(
                payload["question_id"],
                payload["is_correct"],
                payload.get("response_time_ms", 0),
            )
        if record_type == "SkipQuestionCommand":
            return self.skip_question(payload["question_id"])
        if record_type == "CompleteSessionCommand":
            return self.complete(payload.get("duration_seconds", 0))
        return None
