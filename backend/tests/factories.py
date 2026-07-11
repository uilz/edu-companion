"""Phase 9 测试数据工厂 — 生成 CognitiveNode、事件、提议等测试对象"""
import time


def make_cognitive_node(
    node_id: str = "test_node_001",
    label: str = "微积分.导数",
    level: str = "atom",
    node_type: str = "auto_generated",
    proficiency: float = 0.5,
    total_attempts: int = 0,
    correct_attempts: int = 0,
    is_visible: bool = False,
    path_id: str = "数据科学.数据分析.统计学",
) -> object:
    """创建测试用 CognitiveNode"""
    from app.domain.cognitive.models import (
        CognitiveNode, Belief, PracticeSummary, Trend,
        CognitiveLoad, Scheduling, Engagement,
    )
    return CognitiveNode(
        id=node_id,
        label=label,
        level=level,
        node_type=node_type,
        is_visible=is_visible,
        path_id=path_id,
        belief=Belief(
            alpha=2.0 + correct_attempts,
            beta=2.0 + (total_attempts - correct_attempts),
            proficiency_mean=proficiency,
        ),
        practice_summary=PracticeSummary(
            total_attempts=total_attempts,
            correct_attempts=correct_attempts,
        ),
        trend=Trend(),
        cognitive_load=CognitiveLoad(),
        scheduling=Scheduling(),
        engagement=Engagement(),
    )


def make_answer_event(
    skill_id: str = "微积分.导数",
    is_correct: bool = True,
    user_id: str = "test_user",
    session_id: str = "test_session",
    question_id: str = "q_001",
    response_time_seconds: float = 30.0,
) -> object:
    """创建测试用 AnswerSubmitted 事件"""
    from shared.events import AnswerSubmitted
    return AnswerSubmitted(
        user_id=user_id,
        source_module="practice",
        attempt_id="att_001",
        session_id=session_id,
        question_id=question_id,
        skill_id=skill_id,
        is_correct=is_correct,
        answer=["A"],
        correct_answer=["A"],
        response_time_seconds=response_time_seconds,
        hints_used=0,
        cognitive_node_ids=[skill_id],
    )


def make_proposal(
    proposal_id: str = "prop_001",
    title: str = "薄弱点诊断",
    description: str = "导数章节掌握度偏低，建议复习",
    action_type: str = "review",
    priority: int = 3,
    source: str = "diagnosis",
    status: str = "pending",
) -> dict:
    """创建测试用提案数据 (dict 格式，适合 mock)"""
    return {
        "id": proposal_id,
        "title": title,
        "description": description,
        "action_type": action_type,
        "priority": priority,
        "source": source,
        "status": status,
        "emoji": "📚",
        "created_at": time.time(),
    }
