"""内置模块: 临时会话清理 (TempConversationCleanup)

功能: 定期清理 48h 过期的临时会话
行为: 静默任务，不产生用户可见提案
"""
from __future__ import annotations
from shared.constants import DEFAULT_USER_ID
import logging
import time
from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class TempConversationCleanupModule(SecretaryModule):
    """临时会话清理模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="temp_conv_cleanup",
            display_name="临时会话清理",
            emoji="🧹",
            description="定期清理 48h 过期的临时会话",
            default_enabled=True,
            run_interval_seconds=3600,  # 每小时
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """清理所有用户 48h 过期的临时会话（PG + JSON 双后端）"""
        from app.services.common.storage import storage
        from app.cognitive.link_storage import get_links_for_conversation, remove_link

        cutoff = time.time() - 48 * 3600  # 48 小时前
        cleaned = 0

        # PG 后端：直接查询 conversations 表
        try:
            from app.db.database import get_db
            db = get_db()
            rows = db.fetchall(
                "SELECT id FROM conversations "
                "WHERE is_temporary = true AND created_at < to_timestamp(%s)",
                (cutoff,),
            )
            for row in rows:
                cid = row["id"]
                try:
                    links = get_links_for_conversation(cid)
                    for link in links:
                        remove_link(link["id"])
                except Exception:
                    pass
                db.execute("DELETE FROM messages WHERE conversation_id = %s", (cid,))
                db.execute("DELETE FROM conversations WHERE id = %s", (cid,))
                cleaned += 1
        except Exception as e:
            logger.debug("PG 清理失败: %s", e)

        # JSON 存储后端：遍历用户数据文件
        # PG 存储后端同样通过 storage.load 统一接口
        for uid in self._list_users():
            try:
                data = storage.load(uid)
                to_delete = []
                for cid, conv in data.conversations.items():
                    if conv.is_temporary and conv.updated_at < cutoff:
                        to_delete.append(cid)

                for cid in to_delete:
                    # 清理 conversation_node_links
                    try:
                        links = get_links_for_conversation(cid)
                        for link in links:
                            remove_link(link["id"])
                    except Exception as e:
                        logger.warning("Failed to clean conversation links for %s: %s", cid, e)
                    # 标记删除
                    data.conversations.pop(cid, None)
                    cleaned += 1

                if to_delete:
                    storage.save(uid, data)
            except Exception as e:
                logger.debug("清理用户 %s 临时会话失败: %s", uid, e)

        if cleaned:
            logger.info("🧹 清理 %d 个过期临时会话", cleaned)
        return []

    def _list_users(self) -> list[str]:
        """检测存在临时会话的用户列表"""
        # 遍历 storage 数据目录
        import os
        from pathlib import Path
        from app.config import COMPANION_HOME
        base = COMPANION_HOME / "data"
        if base.exists():
            return [d.name for d in base.iterdir() if d.is_dir()]
        return [DEFAULT_USER_ID]
