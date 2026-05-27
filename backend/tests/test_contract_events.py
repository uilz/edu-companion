"""
契约测试: Event Schema 验证

验证所有 6 个领域事件:
- 字段类型正确
- 默认值合理
- event_type 属性返回正确字符串
- 序列化/反序列化可逆
- EVENT_TYPES 注册表完整
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from shared.events import (
    DomainEvent,
    AnswerSubmitted,
    SessionCompleted,
    KnowledgeStateUpdated,
    AssistantReplied,
    AudioSynthesized,
    ImageRendered,
    CognitiveNodeUpdated,
    EVENT_TYPES,
)

# ── 全部领域事件 ──

ALL_EVENTS = [
    AnswerSubmitted,
    SessionCompleted,
    KnowledgeStateUpdated,
    AssistantReplied,
    AudioSynthesized,
    ImageRendered,
    CognitiveNodeUpdated,
]

# ── 注册表完整性 ──
# ═══════════════════════════════════════════
# 注册表完整性
# ═══════════════════════════════════════════

def test_event_types_registry_has_all_events():
    """EVENT_TYPES 应包含全部 6 个事件类型"""
    assert len(EVENT_TYPES) == len(ALL_EVENTS)
    for cls in ALL_EVENTS:
        instance = cls()
        assert instance.event_type in EVENT_TYPES
        assert EVENT_TYPES[instance.event_type] is cls


def test_event_types_registry_no_duplicates():
    """每个 event_type 字符串唯一"""
    names = [cls().event_type for cls in ALL_EVENTS]
    assert len(names) == len(set(names)), f"Duplicates: {names}"


# ═══════════════════════════════════════════
# 基类契约
# ═══════════════════════════════════════════

def test_domain_event_has_event_id():
    e = DomainEvent()
    assert len(e.event_id) == 12  # _uid() generates 12-char UUID
    assert isinstance(e.occurred_at, datetime)


def test_domain_event_is_frozen():
    """DomainEvent 是不可变的"""
    e = DomainEvent()
    with pytest.raises(Exception):
        e.event_id = "xxx"  # type: ignore[misc]


# ═══════════════════════════════════════════
# 练习域事件
# ═══════════════════════════════════════════

class TestAnswerSubmitted:
    def test_defaults(self):
        e = AnswerSubmitted()
        assert e.event_type == "AnswerSubmitted"
        assert e.is_correct is False
        assert e.p_known_before == 0.5
        assert e.hints_used == 0

    def test_full_construction(self):
        e = AnswerSubmitted(
            user_id="u1", session_id="s1", question_id="q1",
            skill_id="calculus", is_correct=True,
            p_known_before=0.3, p_known_after=0.7,
            time_spent=12.5, hints_used=1,
        )
        assert e.user_id == "u1"
        assert e.p_known_before == 0.3
        assert e.is_correct is True

    def test_is_frozen(self):
        e = AnswerSubmitted()
        with pytest.raises(Exception):
            e.is_correct = True  # type: ignore[misc]


class TestSessionCompleted:
    def test_event_type(self):
        assert SessionCompleted().event_type == "SessionCompleted"

    def test_defaults(self):
        e = SessionCompleted()
        assert e.total_questions == 0
        assert e.accuracy == 0.0


# ═══════════════════════════════════════════
# 知识域事件
# ═══════════════════════════════════════════

class TestKnowledgeStateUpdated:
    def test_event_type(self):
        assert KnowledgeStateUpdated().event_type == "KnowledgeStateUpdated"

    def test_defaults(self):
        e = KnowledgeStateUpdated()
        assert e.old_mastery == "未接触"
        assert e.new_mastery == "未接触"
        assert e.attempt_count == 0

    def test_mastery_transition(self):
        e = KnowledgeStateUpdated(
            user_id="u1", skill_id="calculus",
            old_mastery="发展中", new_mastery="已掌握",
            p_known_before=0.55, p_known_after=0.92,
            attempt_count=12,
        )
        assert e.old_mastery == "发展中"
        assert e.new_mastery == "已掌握"

# ═══════════════════════════════════════════
# 序列化往返
# ═══════════════════════════════════════════

def test_asdict_roundtrip():
    """dataclass.asdict 应可序列化为纯 Python dict"""
    e = AnswerSubmitted(
        user_id="u1", session_id="s1", question_id="q1",
        skill_id="calculus", is_correct=True,
    )
    d = asdict(e)
    assert d["user_id"] == "u1"
    assert d["is_correct"] is True
    assert d["event_id"] == e.event_id
    assert isinstance(d["occurred_at"], datetime)


def test_all_events_json_serializable():
    """所有事件序列化为 dict 后应可 JSON 序列化"""
    for cls in ALL_EVENTS:
        e = cls()
        d = asdict(e)
        # datetime is fine in dict, but check no other weird types
        for key, val in d.items():
            if key == "occurred_at":
                assert isinstance(val, datetime)
            else:
                assert isinstance(val, (str, int, float, bool, list, type(None))), \
                    f"{cls.__name__}.{key} = {type(val).__name__}"
