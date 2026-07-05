"""
InterestExplorer 跨模块导入

按 docs/modules/interest-explorer/overview.md §10 + events.md §3.2 实现:
- 5 个目标模块: reading / project / flashcard / cognitive_node / language_room
- 严格遵循 CrossModuleTarget 枚举
- 不绕过现有数据流（通过标准模块 API）
- 每个目标模块调用相应的 API/服务

事件:
- 触发 InterestContentImported（target_module, target_ref_id）
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from shared.events import CrossModuleTarget, InterestContentImported

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 字符串（用于跨模块追溯时间戳）。"""
    return datetime.now(timezone.utc).isoformat()


class CrossModuleImporter:
    """跨模块导入执行器

    关键设计:
      - 通过 asyncio.create_task 异步触发事件（不阻塞调用方）
      - 每个目标模块的导入逻辑独立实现
      - 失败不抛出（仅记录日志）
    """

    async def import_to_reading(
        self,
        user_id: str,
        push_id: str,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """导入到阅读模块

        创建 Material 记录（URL 类型），URL 编码进 file_name 前缀
        """
        try:
            from app.infrastructure.db.database import get_db
            import uuid
            db = get_db()
            material_id = str(uuid.uuid4())
            # 在 file_name 前缀标记 [URL]，URL 存入 summary 末尾
            file_name = f"[URL] {title[:150]}"
            full_summary = f"来源: InterestExplorer 推送\n原文链接: {url}\n\n{summary}"
            db.execute(
                """
                INSERT INTO materials
                (material_id, user_id, file_name, file_type, file_size,
                 storage_path, purpose, status, summary, tags_json,
                 is_folder, level, created_at, indexed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    material_id,
                    user_id,
                    file_name,
                    "url",
                    0,
                    url,  # 存储路径直接用 URL（不下载）
                    "reading",
                    "pending",
                    full_summary[: 2000],
                    '["interest_explorer"]',
                    False,
                    0,
                ),
            )
            await self._publish_imported(
                user_id, push_id, CrossModuleTarget.READING, material_id
            )
            return material_id
        except Exception as e:
            logger.warning("import_to_reading 失败: %s", e)
            return None

    async def import_to_project(
        self,
        user_id: str,
        push_id: str,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """导入到项目模块

        调用 project API 创建一个项目灵感
        """
        try:
            from app.api.project import service as project_api_service
            project = project_api_service.create_project(
                user_id=user_id,
                name=title[:200],
                description=summary or url,
                template_id=None,
                template_version=None,
                tags=["interest_explorer"],
            )
            project_id = project.get("id") if isinstance(project, dict) else None
            await self._publish_imported(
                user_id, push_id, CrossModuleTarget.PROJECT, project_id or ""
            )
            return project_id
        except Exception as e:
            logger.warning("import_to_project 失败: %s", e)
            return None

    async def import_to_flashcard(
        self,
        user_id: str,
        push_id: str,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """导入到 FlashCard 模块

        复用多源提取接口 / 或直接创建数据卡
        """
        try:
            from app.api.flashcard.service import get_flashcard_service
            # 使用全局 svc (注入 event bus), 否则 create_card 不会发布事件
            svc = get_flashcard_service()
            card = svc.create_card(user_id, {
                "type": 1,
                "source": "interest_explorer",
                "cross_module_source": "interest_explorer",
                "front_text": title[:500],
                "back_text": (summary or url)[: 1000],
                "source_ref": {
                    "module": "interest_explorer",
                    "id": push_id,
                    "url": url,
                    "title": title,
                },
                "linked_node_ids": [],
                "tags": ["interest_explorer"],
            })
            card_id = card.get("id") if isinstance(card, dict) else None
            await self._publish_imported(
                user_id, push_id, CrossModuleTarget.FLASHCARD, card_id or ""
            )
            return card_id
        except Exception as e:
            logger.warning("import_to_flashcard 失败: %s", e)
            return None

    async def import_to_cognitive_node(
        self,
        user_id: str,
        push_id: str,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """导入到知识图谱

        调用 CognitiveNodeWriter 创建一个新节点（atom 级别）
        """
        try:
            from app.domain.cognitive.writer import CognitiveNodeWriter
            writer = CognitiveNodeWriter(user_id)
            node = writer.create_node(
                label=title[:200],
                level="atom",
                parent_id=None,
                created_by="interest_explorer",
                is_visible=True,
                description=summary or url,
                metadata={"source": "interest_explorer", "url": url, "push_id": push_id},
            )
            node_id = node.id if hasattr(node, "id") else None
            await self._publish_imported(
                user_id, push_id, CrossModuleTarget.COGNITIVE_NODE, node_id or ""
            )
            return node_id
        except Exception as e:
            logger.warning("import_to_cognitive_node 失败: %s", e)
            return None

    async def import_to_language_room(
        self,
        user_id: str,
        push_id: str,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """导入到语言房间（创建讨论话题）

        真实实现 (Task #36 Part C):
          调用 liveroom.service.create_room 创建一个新语言房间，name/title
          来自 push 内容，settings 中保留 source/push_id/url/summary 供后续追溯。
          失败时返回 None + 写日志，**不**抛 500。
        """
        try:
            from app.api.liveroom import service as liveroom_service

            room_payload = {
                "name": (title or "兴趣话题")[:200],
                "scenario_id": "",
                "room_type": "1v1",   # 兴趣话题默认 1v1，留给用户扩展
                "max_participants": 2,
                "is_recording_enabled": False,
                "is_transcript_enabled": True,
                "ai_intrusion_level": "low",
                "settings": {
                    "source": "interest_explorer",
                    "source_ref_id": push_id,
                    "source_url": url or "",
                    "source_summary": (summary or "")[:1000],
                    "imported_at": _now_iso(),
                },
            }
            room = liveroom_service.create_room(user_id, room_payload)
            room_id = (room or {}).get("id") if isinstance(room, dict) else None
            if not room_id:
                logger.warning(
                    "import_to_language_room: create_room 返回空结果 user=%s push=%s",
                    user_id, push_id,
                )
                return None

            await self._publish_imported(
                user_id, push_id, CrossModuleTarget.LANGUAGE_ROOM, room_id
            )
            return room_id
        except Exception as e:
            logger.warning("import_to_language_room 失败: %s", e)
            return None

    async def import_to(
        self,
        user_id: str,
        push_id: str,
        target_module: CrossModuleTarget,
        title: str,
        url: str,
        summary: str = "",
    ) -> Optional[str]:
        """统一入口: 按 target_module 分发

        严格使用 CrossModuleTarget 枚举
        """
        if target_module == CrossModuleTarget.READING:
            return await self.import_to_reading(
                user_id, push_id, title, url, summary
            )
        if target_module == CrossModuleTarget.PROJECT:
            return await self.import_to_project(
                user_id, push_id, title, url, summary
            )
        if target_module == CrossModuleTarget.FLASHCARD:
            return await self.import_to_flashcard(
                user_id, push_id, title, url, summary
            )
        if target_module == CrossModuleTarget.COGNITIVE_NODE:
            return await self.import_to_cognitive_node(
                user_id, push_id, title, url, summary
            )
        if target_module == CrossModuleTarget.LANGUAGE_ROOM:
            return await self.import_to_language_room(
                user_id, push_id, title, url, summary
            )
        logger.warning("未知的 target_module: %s", target_module)
        return None

    async def _publish_imported(
        self,
        user_id: str,
        push_id: str,
        target_module: CrossModuleTarget,
        target_ref_id: str,
    ) -> None:
        """发布 InterestContentImported 事件"""
        try:
            from app.application.di import container
            await container.event_bus.publish(InterestContentImported(
                user_id=user_id,
                push_id=push_id,
                target_module=target_module,
                target_ref_id=target_ref_id,
            ))
        except Exception as e:
            logger.debug("InterestContentImported 事件发布失败: %s", e)


# ═══════════════════════════════════════════
# 模块单例
# ═══════════════════════════════════════════

_importer: CrossModuleImporter | None = None


def get_importer() -> CrossModuleImporter:
    global _importer
    if _importer is None:
        _importer = CrossModuleImporter()
    return _importer
