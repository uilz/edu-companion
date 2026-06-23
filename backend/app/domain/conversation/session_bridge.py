"""SessionCompleted 事件 → 对话记忆写入"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.events import SessionCompleted

logger = logging.getLogger("conversation")


class SessionBridge:
    """SessionCompleted 事件监听器：将练习结果写入对话 branch 的 practice_summary"""

    async def on_session_completed(self, event: SessionCompleted) -> None:
        """练习完成 → 写入对话记忆，更新 branch 的 practice_summary"""
        user_id = getattr(event, "user_id", "?")
        session_id = getattr(event, "session_id", "?")
        accuracy = getattr(event, "accuracy", 0.0)

        logger.info(
            "Conversation: session completed user=%s session=%s accuracy=%.2f",
            user_id, session_id, accuracy,
        )

        # 更新对话 branch 的 practice_summary
        try:
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            # Find branches that reference this session and update practice_summary
            updated = False
            for branch in (dn for dn in data.directory_nodes.values() if dn.node_type == "conv"):
                if session_id in getattr(branch, "practice_sessions", []):
                    summary_parts = [
                        f"已练{getattr(event, 'total_questions', 0)}题",
                        f"正确率{accuracy:.0%}",
                        f"用时{getattr(event, 'duration_minutes', 0):.0f}分钟",
                    ]
                    branch.practice_summary = ",".join(summary_parts)
                    updated = True

            if updated:
                get_data_repo().save(user_id, data)
                logger.info("Conversation: practice_summary updated for session %s", session_id)
            else:
                # No branch references this session yet — find most recent branch and append
                for branch in (dn for dn in data.directory_nodes.values() if dn.node_type == "conv"):
                    sessions = getattr(branch, "practice_sessions", [])
                    sessions.append(session_id)
                    summary_parts = [
                        f"已练{getattr(event, 'total_questions', 0)}题",
                        f"正确率{accuracy:.0%}",
                    ]
                    branch.practice_summary = ",".join(summary_parts)
                    get_data_repo().save(user_id, data)
                    logger.info("Conversation: practice_summary appended to branch for session %s", session_id)
                    break
        except Exception as exc:
            logger.warning("Conversation: failed to update branch practice_summary: %s", exc)
