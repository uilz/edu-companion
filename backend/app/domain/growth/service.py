"""GrowthService — Growth Domain 应用服务。

提供给 Growth API、Today、Profile 等消费端的查询接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.growth.narrative import (
    build_growth_narrative,
    build_growth_timeline,
    build_growth_insights,
)

if TYPE_CHECKING:
    from app.domain.growth.repository import GrowthRepository


class GrowthService:
    """Growth 领域查询服务。"""

    def __init__(self, repo: GrowthRepository):
        self._repo = repo

    async def get_latest_growth(self, learner_id: str) -> dict | None:
        """获取最新一次 GrowthRecord（供 Today 页面使用）。"""
        record = self._repo.get_latest(learner_id)
        if not record:
            return None
        return self._record_to_dict(record)

    async def list_growth_records(
        self, learner_id: str, limit: int = 20
    ) -> list[dict]:
        """获取 GrowthRecord 列表。"""
        records = self._repo.list_by_learner(learner_id, limit)
        return [self._record_to_dict(r) for r in records]

    async def get_growth_summary(self, learner_id: str) -> dict:
        """获取 Growth 摘要（供 Growth 页面顶部卡片）。"""
        records = self._repo.list_by_learner(learner_id, limit=999)
        total_sessions = len(records)
        total_duration = sum(r.duration_minutes for r in records)
        total_skill_gains = sum(r.skill_count for r in records)
        total_gain_score = sum(r.total_gain for r in records)

        # 最近 7 天的 streak
        import time
        now = time.time()
        streak = 0
        day_map: dict[str, bool] = {}
        for r in records:
            day_start = int(r.session_started_at // 86400) * 86400
            day_map[str(day_start)] = True

        for i in range(30):
            day = int(now // 86400) * 86400 - i * 86400
            if str(day) in day_map:
                streak += 1
            else:
                break

        summary = {
            "total_sessions": total_sessions,
            "total_duration_minutes": round(total_duration, 1),
            "total_skill_gains": total_skill_gains,
            "total_gain_score": round(total_gain_score, 2),
            "streak_days": streak,
            "recent_records": [
                self._record_to_dict(r) for r in records[:5]
            ],
        }
        summary["growth_narrative"] = build_growth_narrative(summary)
        summary["timeline"] = build_growth_timeline(summary)
        summary["insights"] = build_growth_insights(summary)
        return summary

    @staticmethod
    def _record_to_dict(record) -> dict:
        return {
            "id": record.id,
            "learner_id": record.learner_id,
            "session_id": record.session_id,
            "session_title": record.session_title,
            "session_started_at": record.session_started_at,
            "session_finished_at": record.session_finished_at,
            "duration_minutes": record.duration_minutes,
            "skill_gains": [
                {
                    "skill": g.skill,
                    "before": g.before,
                    "after": g.after,
                    "delta": g.delta,
                    "evidence": g.evidence,
                    "category": g.category,
                }
                for g in record.skill_gains
            ],
            "summary": record.summary,
            "reflection_snippet": record.reflection_snippet,
            "key_takeaways": record.key_takeaways,
            "next_steps": record.next_steps,
            "total_gain": record.total_gain,
        }
