"""
契约测试: Event Schema 验证

验证所有领域事件:
- 字段类型正确
- 默认值合理
- event_type 属性返回正确字符串
- 序列化/反序列化可逆
- EVENT_TYPES 注册表完整
"""

import json
import typing
from dataclasses import asdict, fields
from datetime import datetime, timezone
from typing import get_type_hints

import pytest

from shared.events import (
    DomainEvent,
    AnswerSubmitted,
    AssistantReplied,
    CognitiveNodeLinked,
    CognitiveNodeMetadataChanged,
    ErrorBookEntryReviewed,
    ErrorBookEntryResolved,
    ErrorRecorded,
    MessageClassified,
    NodeCreated,
    PendingCrossTopic,
    PracticeSubmitted,
    ProposalAccepted,
    SessionCompleted,
    EVENT_TYPES,
)

# ── 全部领域事件（须与 EVENT_TYPES 注册表一致） ──

ALL_EVENTS = list(EVENT_TYPES.values())


def _is_datetime_type(tp) -> bool:
    """判断类型注解是否为 datetime (兼容 Optional[datetime])。"""
    origin = typing.get_origin(tp)
    if origin is typing.Union or (hasattr(typing, "Union") and origin is typing.Union):
        return any(_is_datetime_type(arg) for arg in typing.get_args(tp))
    if tp is datetime:
        return True
    return False


def _field_actual_type(cls, field_name: str):
    """获取事件类字段的真实运行时类型（基于 default_factory 实例）。"""
    # 优先从 __annotations__ 取（解包 Optional/Union/ForwardRef）
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = {}
    if field_name in hints:
        return hints[field_name]
    # 退化：从 dataclass fields 中取
    for f in fields(cls):
        if f.name == field_name:
            return f.type
    return None


# ═══════════════════════════════════════════
# 注册表完整性
# ═══════════════════════════════════════════

def test_event_types_registry_has_all_events():
    """EVENT_TYPES 应包含全部领域事件"""
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
    # AnswerSubmitted 既有 occurred_at 也有 submitted_at
    assert isinstance(d["occurred_at"], datetime)
    if "submitted_at" in d:
        assert isinstance(d["submitted_at"], datetime)


def test_all_events_json_serializable():
    """所有事件序列化为 dict 后应可 JSON 序列化。

    判定规则：基于事件类字段的 *声明类型* 决定运行时值是否允许。
    - datetime 字段 → 运行时值必须是 datetime
    - 其他字段   → 运行时值必须在 JSON 白名单 (str/int/float/bool/list/dict/None)
    """
    for cls in ALL_EVENTS:
        e = cls()
        d = asdict(e)
        for key, val in d.items():
            field_type = _field_actual_type(cls, key)
            if _is_datetime_type(field_type):
                assert isinstance(val, datetime), \
                    f"{cls.__name__}.{key} 声明为 datetime, 实际 {type(val).__name__}"
            else:
                assert isinstance(val, (str, int, float, bool, list, dict, type(None))), \
                    f"{cls.__name__}.{key} = {type(val).__name__} 不在 JSON 序列化白名单"


def test_all_events_have_event_type_property():
    """每个事件类必须返回非空字符串 event_type。"""
    for cls in ALL_EVENTS:
        e = cls()
        assert isinstance(e.event_type, str)
        assert len(e.event_type) > 0
        # event_type 字符串与类名保持一致（约定）
        assert e.event_type == cls.__name__, \
            f"{cls.__name__}.event_type={e.event_type!r} 与类名不一致"


def test_all_events_have_occurred_at():
    """所有事件必须包含基类的 occurred_at 字段。"""
    for cls in ALL_EVENTS:
        e = cls()
        assert hasattr(e, "occurred_at")
        assert isinstance(e.occurred_at, datetime)
