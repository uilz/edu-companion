"""GrowthEngine — 事件驱动的成长记录引擎。

监听 SessionCompleted / ReflectionGenerated 事件，
生成 GrowthRecord 并发布 GrowthRecordCreated 事件。

消费端：Today、Profile、Growth 页面均可查询同一套 GrowthRecord。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.event_bus import EventBus
    from app.domain.growth.repository import GrowthRepository
    from shared.events import DomainEvent

logger = logging.getLogger("domain.growth")


class GrowthEngine:
    """Growth 领域服务引擎。

    职责：
    1. 监听 LearningSessionCompleted → 生成 GrowthRecord
    2. 监听 ReflectionGenerated → 补充反思数据到已有 GrowthRecord
    3. 发布 GrowthRecordCreated 事件
    """

    def __init__(self, repo: GrowthRepository, event_bus: EventBus):
        self._repo = repo
        self._bus = event_bus

    async def on_session_completed(self, event) -> None:
        """LearningSessionCompleted 事件处理器。

        从 Session 完成事件中提取关键数据，生成 GrowthRecord。
        """
        from app.domain.growth.models import create_growth_record
        from shared.events import GrowthRecordCreated

        session_id = event.session_id
        learner_id = event.learner_id

        # 检查是否已有此次 Session 的 GrowthRecord（幂等）
        existing = self._repo.list_by_session(session_id)
        if existing:
            logger.info(
                "GrowthRecord already exists for session=%s, skipping",
                session_id,
            )
            return

        # 生成 GrowthRecord
        record = create_growth_record(
            learner_id=learner_id,
            session_id=session_id,
            session_title=event.title or "",
            session_started_at=event.started_at,
            session_finished_at=event.finished_at,
            summary=event.title or "",
        )

        self._repo.save(record)
        logger.info(
            "GrowthRecordCreated id=%s session=%s learner=%s",
            record.id, session_id, learner_id,
        )

        # 发布 GrowthRecordCreated 事件
        growth_event = GrowthRecordCreated(
            record_id=record.id,
            learner_id=learner_id,
            session_id=session_id,
            session_title=record.session_title,
            total_gain=record.total_gain,
            skill_count=record.skill_count,
            duration_minutes=record.duration_minutes,
        )
        await self._bus.publish(growth_event)

    async def on_reflection_generated(self, event) -> None:
        """ReflectionGenerated 事件处理器。

        将反思内容补充到对应的 GrowthRecord。
        """
        session_id = event.session_id

        existing = self._repo.list_by_session(session_id)
        if not existing:
            # GrowthRecord 尚未创建，可能是异常顺序
            logger.warning(
                "ReflectionGenerated but no GrowthRecord for session=%s",
                session_id,
            )
            return

        record = existing[0]
        record.reflection_snippet = event.content or ""
        record.key_takeaways = event.key_takeaways or []
        record.next_steps = event.next_steps or []

        # 从反思中提取隐含的技能增益
        if event.key_takeaways:
            self._extract_skill_gains_from_reflection(record, event)

        self._repo.save(record)
        logger.info(
            "GrowthRecord enriched with reflection session=%s takeaways=%d",
            session_id, len(event.key_takeaways or []),
        )

    def _extract_skill_gains_from_reflection(self, record, event):
        """从反思的 key_takeaways 中简单提取技能增益。

        格式期望：每条 takeaway 包含 "理解了" / "掌握了" / "学会了" 等关键词。
        """
        from app.domain.growth.models import SkillGain

        for takeaway in event.key_takeaways or []:
            for keyword in ("理解", "掌握", "学会", "完成", "突破"):
                if keyword in takeaway:
                    # 简单的启发式提取
                    skill_name = takeaway.split(keyword)[0].strip().rstrip("了，。")
                    if not skill_name or len(skill_name) < 2:
                        skill_name = takeaway[:20]
                    record.skill_gains.append(SkillGain(
                        skill=skill_name,
                        before=0.3,
                        after=0.7,
                        evidence=takeaway,
                        category="knowledge",
                    ))
                    break
