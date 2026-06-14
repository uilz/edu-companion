"""
Organization Service — 对话/目录自动组织工具 (ADR 0005)

三方法:
  - organize_message     标记 conv summary_dirty
  - organize_conversation  生成 summary_short + ai_name
  - organize_directory    合并子对话摘要

由 OrganizationDetector 轮询 events 表按阈值触发。
"""

from __future__ import annotations

import logging
import time

from app.services.common import get_data_repo
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)


class OrganizationService:
    """对话/目录自动组织 — 三方法"""

    # ─── 消息级 ───────────────────────────────────

    async def organize_message(self, user_id: str, node_id: str) -> None:
        """组织单条消息 — 标记所属 conv 为 dirty。"""
        data = get_data_repo().load(user_id)
        msg = data.nodes.get(node_id)
        if not msg:
            return
        conv = data.directory_nodes.get(msg.directory_id)
        if not conv or conv.node_type != "conv":
            return
        conv.summary_dirty = True
        conv.updated_at = time.time()
        get_data_repo().save(user_id, data)

    # ─── 对话级 ───────────────────────────────────

    async def organize_conversation(
        self,
        user_id: str,
        conv_id: str,
        llm_summarize: bool = True,
    ) -> None:
        """组织对话 — 生成 summary_short + ai_name。"""
        data = get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv or conv.node_type != "conv":
            return

        # 收集有效消息
        messages = [
            data.nodes.get(nid) for nid in conv.conv_message_ids
            if data.nodes.get(nid) and not data.nodes[nid].is_deleted
        ]
        if not messages:
            return
        texts = [m.text_summary or m.content[:200] for m in messages]

        # ── summary_short ──
        if llm_summarize and len(texts) >= 3:
            summary = await self._llm_summarize(texts)
            conv.summary_short = summary or texts[0][:100]
        else:
            conv.summary_short = texts[0][:100]

        # ── ai_name (仅当用户未手动命名时) ──
        if not conv.user_name:
            if len(texts) <= 5:
                conv.ai_name = texts[0][:20]
            elif llm_summarize:
                name = await self._llm_rename(texts)
                conv.ai_name = name or texts[0][:20]
            else:
                conv.ai_name = texts[0][:20]

        conv.summary_dirty = False
        conv.updated_at = time.time()
        get_data_repo().save(user_id, data)

    # ─── 目录级 ───────────────────────────────────

    async def organize_directory(self, user_id: str, dir_id: str) -> None:
        """组织目录 — 合并子对话摘要。"""
        data = get_data_repo().load(user_id)
        dn = data.directory_nodes.get(dir_id)
        if not dn or dn.node_type != "dir":
            return

        # 收集直接子 conv 的摘要
        child_summaries: list[str] = []
        for cid in dn.children_order:
            child = data.directory_nodes.get(cid)
            if child and child.node_type == "conv" and child.summary_short:
                child_summaries.append(child.summary_short)

        if child_summaries:
            dn.summary_short = " | ".join(child_summaries[:5])
            if len(child_summaries) > 5:
                dn.summary_short += " ..."
        else:
            dn.summary_short = dn.display_name

        dn.summary_dirty = False
        dn.updated_at = time.time()
        get_data_repo().save(user_id, data)

    # ─── LLM 辅助 ─────────────────────────────────

    async def _llm_summarize(self, texts: list[str]) -> str:
        """用 LLM 生成对话摘要 (20 字以内)。"""
        try:
            sample = "\n".join(texts[-6:])
            result = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一个简洁的摘要助手。"},
                    {"role": "user", "content": f"请用一句话概括以下对话的核心内容（20字以内）：\n{sample}"},
                ],
                task_type="fast",
                max_tokens=100,
            )
            return result.strip()
        except Exception:
            logger.debug("LLM 摘要失败", exc_info=True)
            return ""

    async def _llm_rename(self, texts: list[str]) -> str:
        """用 LLM 生成对话名称 (10 字以内)。"""
        try:
            sample = "\n".join(texts[:3])
            result = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "根据对话内容生成一个简短名称（10字以内）。"},
                    {"role": "user", "content": f"对话内容：\n{sample}\n\n请生成名称："},
                ],
                task_type="fast",
                max_tokens=50,
            )
            return result.strip()
        except Exception:
            logger.debug("LLM 重命名失败", exc_info=True)
            return ""


# 全局单例
organization_service = OrganizationService()
