"""内置模块: 学习简报 (DailyBrief)

功能: 每天生成一次学习简报，汇总当日学习情况
触发条件:
  - 每天首次检查
  - 用户有至少一项学习活动
简报内容:
  - 今日学习时长/题量
  - 掌握度变化
  - 薄弱点提醒
  - 明日简单规划
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class DailyBriefModule(SecretaryModule):
    """学习简报模块 — 每日一次"""

    def __init__(self) -> None:
        super().__init__()
        self._last_brief_date: str = ""  # YYYY-MM-DD

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="daily_brief",
            display_name="学习简报",
            emoji="📊",
            description="每日学习小结，汇总今日学习情况和明日建议",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """每日首次检查生成简报"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 同一天不重复生成
        if self._last_brief_date == today:
            return []

        self._last_brief_date = today

        proposals: list[Proposal] = []

        # 从学习事件中收集今日数据
        events_today = self._collect_today_events(user_id)
        if events_today["total_events"] < 3:
            return []  # 学习数据太少，不生成简报

        # 构建简报
        summary_parts = []
        if events_today["practice_count"] > 0:
            accuracy = events_today["avg_accuracy"] * 100
            summary_parts.append(f"完成 {events_today['practice_count']} 题，正确率 {accuracy:.0f}%")
        if events_today["conversation_count"] > 0:
            summary_parts.append(f"进行了 {events_today['conversation_count']} 次对话学习")
        summary = "，".join(summary_parts) if summary_parts else "今日暂无详细数据"

        proposals.append(Proposal(
            emoji="📊",
            title=f"今日学习简报 ({today[5:]})",
            description=summary,
            action_type="brief",
            priority=2,
            payload={
                "date": today,
                **events_today,
            },
            insight_source="daily_brief",
            generated_by="daily_brief",
        ))

        # 如果有薄弱点，加一条明日规划
        try:
            from ..analysis import find_weakness_clusters, _get_nodes

            nodes = _get_nodes(user_id)
            weakness = find_weakness_clusters(user_id, limit=1, nodes=nodes)
            if weakness:
                top = weakness[0]
                proposals.append(Proposal(
                    emoji="🎯",
                    title="明日建议",
                    description=f"薄弱点「{top['label']}」(掌握度 {top['mastery']:.0f}%)，建议优先安排专项练习",
                    action_type="brief",
                    priority=3,
                    payload={
                        "kp_id": top["node_id"],
                        "mastery": top["mastery"],
                    },
                    insight_source="daily_brief_weakness",
                ))
        except Exception as e:
            logger.debug("简报薄弱点检查: %s", e)

        return proposals

    def _collect_today_events(self, user_id: str) -> dict[str, Any]:
        """收集今日学习事件"""
        try:
            from ..analysis import _get_nodes

            nodes = _get_nodes(user_id)
            today_start = time.time() - 86400  # 过去 24 小时

            result = {
                "total_events": 0,
                "practice_count": 0,
                "conversation_count": 0,
                "avg_accuracy": 0.0,
            }

            for node in nodes:
                if not node:
                    continue
                events = []
                if node.practice_summary:
                    events.append(node.practice_summary)
                if node.engagement:
                    events.append(node.engagement)

                for ev in events:
                    ev_time = getattr(ev, 'last_updated', 0) or getattr(ev, 'updated_at', 0)
                    if isinstance(ev_time, (int, float)) and ev_time > today_start:
                        result["total_events"] += 1

                if node.practice_summary:
                    ps = node.practice_summary
                    result["practice_count"] += ps.total_attempts or 0
                    acc = getattr(ps, 'accuracy', None)
                    if acc is None:
                        if ps.total_attempts > 0:
                            acc = ps.correct_attempts / ps.total_attempts
                        else:
                            acc = ps.recent_success_rate_7d
                    if acc and acc > 0:
                        result["avg_accuracy"] = (result["avg_accuracy"] + acc) / 2

                if node.conversation_log:
                    result["conversation_count"] += 1

            return result
        except Exception as e:
            logger.debug("收集今日事件失败: %s", e)
            return {"total_events": 0, "practice_count": 0, "conversation_count": 0, "avg_accuracy": 0.0}
