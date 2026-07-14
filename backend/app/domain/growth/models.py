"""Growth Domain 领域模型。

Growth 是 Learner 成长的记录层，由 GrowthEngine 监听 Session 事件自动生成。
Today、Profile、Growth 页面消费同一套 GrowthRecord。

Domain Model v1.2:
  - GrowthRecord 是值对象：一次 Session 产生的成长记录
  - SkillGain 是内嵌值：单个技能的掌握度变化
  - GrowthEngine 是领域服务：事件驱动生成 GrowthRecord
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4


@dataclass(frozen=True)
class SkillGain:
    """单个技能的掌握度变化（值对象）。"""
    skill: str
    before: float          # 0.0 ~ 1.0
    after: float           # 0.0 ~ 1.0
    evidence: str = ""     # AI 对这次增长的判断依据
    category: Literal["knowledge", "behavior", "preference", "reflection"] = "knowledge"

    @property
    def delta(self) -> float:
        return round(self.after - self.before, 3)


@dataclass
class GrowthRecord:
    """一次 Session 产生的成长记录（实体）。"""
    id: str
    learner_id: str
    session_id: str
    session_title: str

    # 时间
    session_started_at: float = 0.0
    session_finished_at: float | None = None
    created_at: float = 0.0

    # 成长数据
    skill_gains: list[SkillGain] = field(default_factory=list)
    summary: str = ""                         # AI 总结
    reflection_snippet: str = ""              # 从 Reflection 提取的片段
    key_takeaways: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    # 标记
    is_verified: bool = False                 # Learner 确认过（暂未使用）

    @property
    def duration_minutes(self) -> float:
        if self.session_finished_at and self.session_started_at:
            return round((self.session_finished_at - self.session_started_at) / 60, 1)
        return 0.0

    @property
    def total_gain(self) -> float:
        """所有技能增益总和。"""
        return round(sum(g.delta for g in self.skill_gains), 3)

    @property
    def skill_count(self) -> int:
        return len(self.skill_gains)


# ── 工厂 ──

def create_growth_record(
    learner_id: str,
    session_id: str,
    session_title: str,
    session_started_at: float = 0.0,
    session_finished_at: float | None = None,
    skill_gains: list[dict] | None = None,
    summary: str = "",
    reflection_snippet: str = "",
    key_takeaways: list[str] | None = None,
    next_steps: list[str] | None = None,
) -> GrowthRecord:
    """创建 GrowthRecord 工厂函数。"""
    import time
    record = GrowthRecord(
        id=f"growth_{uuid4().hex[:12]}",
        learner_id=learner_id,
        session_id=session_id,
        session_title=session_title,
        session_started_at=session_started_at,
        session_finished_at=session_finished_at,
        created_at=time.time(),
        summary=summary,
        reflection_snippet=reflection_snippet,
        key_takeaways=key_takeaways or [],
        next_steps=next_steps or [],
    )
    if skill_gains:
        for g in skill_gains:
            record.skill_gains.append(SkillGain(
                skill=g["skill"],
                before=g.get("before", 0.0),
                after=g.get("after", 0.0),
                evidence=g.get("evidence", ""),
                category=g.get("category", "knowledge"),
            ))
    return record
