"""PracticeAggregateRoot 单元测试"""

from __future__ import annotations

import pytest

from app.domain.practice.aggregate import PracticeAggregateRoot, PracticeDomainError


@pytest.fixture
def new_aggregate() -> PracticeAggregateRoot:
    return PracticeAggregateRoot(
        session_id="sess_001",
        user_id="user_001",
        bank_id="bank_001",
        session_type="practice",
        mode="adaptive",
    )


class TestLifecycle:
    def test_initial_state(self, new_aggregate: PracticeAggregateRoot) -> None:
        assert new_aggregate.status == "created"
        assert new_aggregate.version == 0
        assert new_aggregate.question_ids == []
        assert new_aggregate.score == 0.0

    def test_start_session(self, new_aggregate: PracticeAggregateRoot) -> None:
        event = new_aggregate.start(["q1", "q2", "q3"])

        assert new_aggregate.status == "started"
        assert new_aggregate.question_ids == ["q1", "q2", "q3"]
        assert new_aggregate.version == 1
        assert event["event_type"] == "SessionStarted"
        assert event["question_ids"] == ["q1", "q2", "q3"]

    def test_cannot_start_twice(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        with pytest.raises(PracticeDomainError):
            new_aggregate.start(["q2"])


class TestSubmitAnswer:
    def test_submit_correct_answer(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1", "q2"])
        event = new_aggregate.submit_answer("q1", is_correct=True, response_time_ms=1200)

        assert new_aggregate.status == "started"
        assert new_aggregate.answered_question_ids == ["q1"]
        assert new_aggregate.correct_count == 1
        assert new_aggregate.wrong_count == 0
        assert new_aggregate.score == 1.0
        assert new_aggregate.version == 2
        assert event["event_type"] == "AnswerSubmitted"
        assert event["is_correct"] is True
        assert event["response_time_ms"] == 1200

    def test_submit_wrong_answer(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1", "q2"])
        event = new_aggregate.submit_answer("q1", is_correct=False, response_time_ms=800)

        assert new_aggregate.answered_question_ids == ["q1"]
        assert new_aggregate.correct_count == 0
        assert new_aggregate.wrong_count == 1
        assert new_aggregate.score == 0.0
        assert event["is_correct"] is False

    def test_score_updates_after_multiple_answers(
        self, new_aggregate: PracticeAggregateRoot
    ) -> None:
        new_aggregate.start(["q1", "q2", "q3", "q4"])
        new_aggregate.submit_answer("q1", is_correct=True)
        new_aggregate.submit_answer("q2", is_correct=False)
        event = new_aggregate.submit_answer("q3", is_correct=True)

        assert new_aggregate.correct_count == 2
        assert new_aggregate.wrong_count == 1
        assert new_aggregate.score == pytest.approx(2 / 3)
        assert event["score"] == pytest.approx(2 / 3)

    def test_cannot_submit_before_start(self, new_aggregate: PracticeAggregateRoot) -> None:
        with pytest.raises(PracticeDomainError):
            new_aggregate.submit_answer("q1", is_correct=True)

    def test_cannot_submit_unknown_question(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        with pytest.raises(PracticeDomainError):
            new_aggregate.submit_answer("q2", is_correct=True)

    def test_cannot_submit_duplicate_answer(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        new_aggregate.submit_answer("q1", is_correct=True)
        with pytest.raises(PracticeDomainError):
            new_aggregate.submit_answer("q1", is_correct=False)

    def test_cannot_submit_after_complete(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        new_aggregate.complete()
        with pytest.raises(PracticeDomainError):
            new_aggregate.submit_answer("q1", is_correct=True)


class TestSkipQuestion:
    def test_skip_question(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1", "q2"])
        event = new_aggregate.skip_question("q2")

        assert new_aggregate.skipped_question_ids == ["q2"]
        assert new_aggregate.version == 2
        assert event["event_type"] == "QuestionSkipped"

    def test_cannot_skip_answered_question(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        new_aggregate.submit_answer("q1", is_correct=True)
        with pytest.raises(PracticeDomainError):
            new_aggregate.skip_question("q1")

    def test_cannot_skip_twice(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        new_aggregate.skip_question("q1")
        with pytest.raises(PracticeDomainError):
            new_aggregate.skip_question("q1")


class TestCompleteSession:
    def test_complete_started_session(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1", "q2"])
        new_aggregate.submit_answer("q1", is_correct=True)
        event = new_aggregate.complete(duration_seconds=120)

        assert new_aggregate.status == "completed"
        assert new_aggregate.version == 3
        assert event["event_type"] == "SessionCompleted"
        assert event["duration_seconds"] == 120
        assert event["score"] == 1.0

    def test_complete_empty_session(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        event = new_aggregate.complete()

        assert new_aggregate.status == "completed"
        assert event["correct_count"] == 0
        assert event["score"] == 0.0

    def test_cannot_complete_twice(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1"])
        new_aggregate.complete()
        with pytest.raises(PracticeDomainError):
            new_aggregate.complete()


class TestSnapshot:
    def test_snapshot_roundtrip(self, new_aggregate: PracticeAggregateRoot) -> None:
        new_aggregate.start(["q1", "q2"])
        new_aggregate.submit_answer("q1", is_correct=True)
        new_aggregate.skip_question("q2")
        snapshot = new_aggregate.to_snapshot()

        restored = PracticeAggregateRoot.from_snapshot(snapshot)
        assert restored.session_id == new_aggregate.session_id
        assert restored.user_id == new_aggregate.user_id
        assert restored.status == new_aggregate.status
        assert restored.answered_question_ids == ["q1"]
        assert restored.skipped_question_ids == ["q2"]
        assert restored.correct_count == 1
        assert restored.score == 1.0
        assert restored.version == new_aggregate.version

    def test_apply_command_record_rebuilds_state(
        self, new_aggregate: PracticeAggregateRoot
    ) -> None:
        new_aggregate.start(["q1", "q2"])
        snapshot = new_aggregate.to_snapshot()

        restored = PracticeAggregateRoot.from_snapshot(snapshot)
        restored.apply_command_record(
            "SubmitAnswerCommand",
            {"question_id": "q1", "is_correct": True, "response_time_ms": 500},
        )

        assert restored.answered_question_ids == ["q1"]
        assert restored.correct_count == 1
        assert restored.score == 1.0

    def test_apply_unknown_command_record_is_noop(
        self, new_aggregate: PracticeAggregateRoot
    ) -> None:
        new_aggregate.start(["q1"])
        result = new_aggregate.apply_command_record("UnknownCommand", {})
        assert result is None
