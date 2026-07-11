"""Phase 9 测试 — conftest 与公共 fixture"""

import sys
from pathlib import Path

# 确保 backend/ 在 sys.path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from app.infrastructure.event_bus import EventBus


@pytest.fixture
def event_bus():
    """干净的 EventBus 实例（每测试独立）"""
    return EventBus(handler_timeout=1.0)


@pytest.fixture
def mock_cognitive_node():
    """创建一个默认的 CognitiveNode 用于测试"""
    from app.domain.cognitive.models import (
        CognitiveNode, Belief, PracticeSummary, PracticeEvent,
    )
    import time
    return CognitiveNode(
        id="test_node_001",
        label="微积分.导数",
        level="atom",
        node_type="auto_generated",
        is_visible=False,
        belief=Belief(alpha=2.0, beta=2.0, proficiency_mean=0.5),
        practice_summary=PracticeSummary(total_attempts=0, correct_attempts=0),
    )


@pytest.fixture
def sample_answer_event():
    """一个典型的 AnswerSubmitted 事件"""
    from shared.events import AnswerSubmitted
    return AnswerSubmitted(
        user_id="test_user",
        source_module="practice",
        attempt_id="att_001",
        session_id="test_session_001",
        question_id="q_001",
        skill_id="微积分.导数",
        is_correct=True,
        answer=["A"],
        correct_answer=["A"],
        response_time_seconds=30.0,
        hints_used=0,
        cognitive_node_ids=["微积分.导数"],
    )


@pytest.fixture
def sample_error_answer_event():
    """一个答错的 AnswerSubmitted 事件"""
    from shared.events import AnswerSubmitted
    return AnswerSubmitted(
        user_id="test_user",
        source_module="practice",
        attempt_id="att_002",
        session_id="test_session_002",
        question_id="q_002",
        skill_id="微积分.极限",
        is_correct=False,
        answer=["B"],
        correct_answer=["A"],
        response_time_seconds=120.0,
        hints_used=2,
        cognitive_node_ids=["微积分.极限"],
    )
