"""
学习事件记录模型 (v3.0 Event Layer)

记录所有可观测的学习行为，供画像层聚合计算趋势和指标。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(StrEnum):
    PRACTICE_SUBMIT = "practice_submit"            # 提交练习题答案
    PRACTICE_SESSION_START = "practice_session_start"
    PRACTICE_SESSION_COMPLETE = "practice_session_complete"
    CONVERSATION_MESSAGE = "conversation_message"   # 发送对话消息
    SKILL_DISCUSSED = "skill_discussed"             # AI 标注讨论了某知识点
    SKILL_MASTERY_CHANGED = "skill_mastery_changed" # BKT 掌握度变化
    BRANCH_CREATED = "branch_created"
    PARTITION_SWITCHED = "partition_switched"       # 切换学习分区
    EMOTION_DETECTED = "emotion_detected"           # 情绪检测
    FRUSTRATION_PEAK = "frustration_peak"           # 挫败峰值
    GRAPH_GENERATED = "graph_generated"             # AI 生成图谱
    REVIEW_RECOMMENDED = "review_recommended"       # 系统推荐复习


class LearningEvent(BaseModel):
    """单个学习行为事件"""
    id: str = Field(default_factory=lambda: f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{id(LearningEvent) % 10000:04d}")
    user_id: str = "default_user"
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 上下文
    partition_id: Optional[str] = None
    branch_id: Optional[str] = None
    skill_ids: list[str] = Field(default_factory=list)

    # 数据载荷
    data: dict[str, Any] = Field(default_factory=dict)

    # 便于查询的冗余索引
    event_date: str = ""  # "2026-05-19"
    event_hour: int = 0   # 0-23


class EventLog(BaseModel):
    """事件日志聚合"""
    user_id: str
    events: list[LearningEvent] = Field(default_factory=list)
    last_pruned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── 聚合查询结果 ──

class EventStats(BaseModel):
    """某分区 x 时间段的事件统计"""
    partition_id: str
    days: int = 7
    total_events: int = 0
    practice_count: int = 0
    conversation_count: int = 0
    skills_discussed: list[str] = Field(default_factory=list)
    mastery_changes: int = 0
    peak_hours: list[int] = Field(default_factory=list)  # 高频学习时段
    frustration_count: int = 0


class DailyMetrics(BaseModel):
    """按天聚合的指标"""
    date: str  # "2026-05-17"
    practice_minutes: float = 0.0
    practice_count: int = 0
    correct_count: int = 0
    conversations: int = 0
    skills_covered: list[str] = Field(default_factory=list)
