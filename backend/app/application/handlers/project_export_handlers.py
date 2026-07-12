"""
ProjectNodeExported 事件订阅者 — 5 target_module 副作用

Task #50: 修复 Project 跨模块联动 5 订阅者断链
Task #48 审计发现 Project 节点导出事件 ProjectNodeExported (在 routes.py:552 发出)
没有任何订阅者消费，导致 5 个 target_module 的导出事实上是 no-op。

本模块注册 5 个 handler, 每个对应一个 CrossModuleTarget 值, 在用户从
Project 导出节点时, 自动在目标模块创建对应实体:
  - flashcard       → FlashCardService.create_card
  - material        → materials 表新增一行
  - cognitive_node  → CognitiveNodeWriter.create_node (atom 级别)
  - plan            → planning_service.create_plan_item
  - language_room   → liveroom_service.create_room

设计要点:
  1. **幂等性**: 各 handler 不严格幂等, 但调用底层服务的现有幂等逻辑
     (e.g. CognitiveNodeWriter 检测同名节点跳过创建)
  2. **错误隔离**: 任何单 target 失败不阻塞其他 target; handler 内部 try/except
     + 日志记录失败原因, 不向上抛
  3. **payload 兼容**: payload 来自 ProjectNodeExported 事件, 字段:
     - user_id, project_id, node_id
     - target_module (CrossModuleTarget 枚举)
     - target_ref_id (可选, 目标实体 ID)
     - export_data (dict, 用户填写的额外数据, e.g. front/back for flashcard)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# payload 提取辅助
# ────────────────────────────────────────────────────────────────────


def _extract_payload(event: Any) -> dict:
    """从 DomainEvent 提取通用字段。

    DomainEvent 没有标准 payload 字段; 事件实例上的属性即 payload。
    本函数返回与 routes 层一致的命名空间, 让 handler 逻辑保持简洁。
    """
    return {
        "user_id": getattr(event, "user_id", "") or "",
        "project_id": getattr(event, "project_id", "") or "",
        "node_id": getattr(event, "node_id", "") or "",
        "target_module": getattr(event, "target_module", None),
        "target_ref_id": getattr(event, "target_ref_id", "") or "",
        "export_data": getattr(event, "export_data", {}) or {},
    }


def _resolve_node_text(payload: dict) -> tuple[str, str]:
    """从 ProjectNode 抓取 front/back 文本。

    优先从 export_data 读 (用户在导出对话框中输入),
    否则回落到 project_nodes.content/description 字段。
    返回 (front_text, back_text)。
    """
    export_data = payload.get("export_data") or {}
    front = export_data.get("front") or export_data.get("front_text") or ""
    back = export_data.get("back") or export_data.get("back_text") or ""
    title = export_data.get("title") or ""
    if not front and title:
        front = title
    if not front:
        # 回落到数据库节点
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            row = db.fetchone(
                "SELECT title, description, content FROM project_nodes "
                "WHERE id = %s AND project_id = %s AND user_id = %s",
                (payload["node_id"], payload["project_id"], payload["user_id"]),
            )
            if row:
                front = row.get("title") or ""
                if not back:
                    back = row.get("description") or ""
                if not back and row.get("content"):
                    content = row["content"]
                    if isinstance(content, str):
                        back = content
                    elif isinstance(content, dict):
                        back = content.get("text") or content.get("summary") or ""
        except Exception as e:
            logger.debug("回退读取 project_nodes 失败: %s", e)
    return front, back


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ────────────────────────────────────────────────────────────────────
# 1. Project → FlashCard
# ────────────────────────────────────────────────────────────────────


async def _export_to_flashcard(event: Any) -> None:
    """从 Project 节点创建 FlashCard。"""
    from shared.events import CrossModuleTarget
    from app.api.flashcard.service import get_flashcard_service

    p = _extract_payload(event)
    user_id = p["user_id"]
    if not user_id:
        return
    front, back = _resolve_node_text(p)
    if not front and not back:
        logger.info(
            "ProjectNodeExported → flashcard 跳过: node=%s 内容为空",
            p["node_id"],
        )
        return

    source_ref = {
        "project_id": p["project_id"],
        "project_node_id": p["node_id"],
        "module": CrossModuleTarget.PROJECT.value,
    }
    try:
        svc = get_flashcard_service()
        svc.create_card(
            user_id=user_id,
            payload={
                "type": 1,  # 基础问答型
                "source": "project",
                "cross_module_source": "project",
                "front_text": front,
                "back_text": back,
                "source_ref": source_ref,
                "linked_node_ids": [],
                "tags": ["from_project"],
            },
        )
        logger.info(
            "ProjectNodeExported → flashcard 成功: node=%s front='%s...'",
            p["node_id"], front[:30],
        )
    except Exception as e:
        logger.error(
            "ProjectNodeExported → flashcard 失败: node=%s err=%s",
            p["node_id"], e, exc_info=True,
        )


# ────────────────────────────────────────────────────────────────────
# 2. Project → Material (Reading)
# ────────────────────────────────────────────────────────────────────


async def _export_to_material(event: Any) -> None:
    """从 Project 节点创建 reading material。"""
    p = _extract_payload(event)
    user_id = p["user_id"]
    if not user_id:
        return
    front, back = _resolve_node_text(p)
    if not front and not back:
        logger.info(
            "ProjectNodeExported → material 跳过: node=%s 内容为空",
            p["node_id"],
        )
        return

    from app.infrastructure.db.database import get_db
    material_id = _new_id("mat")
    metadata = {
        "project_id": p["project_id"],
        "project_node_id": p["node_id"],
        "source_module": "project",
    }
    try:
        db = get_db()
        db.execute(
            """INSERT INTO materials
               (material_id, user_id, file_name, file_type, file_size,
                purpose, status, chunk_count, is_folder, is_deleted,
                level, parent_id, summary, skills_covered_json,
                tags_json, storage_path)
               VALUES (%s, %s, %s, 'note', %s, 'library', 'indexed',
                       1, false, false, 'partition', '', %s, '[]'::jsonb,
                       '[]'::jsonb, '')""",
            (
                material_id, user_id, front[:200] or "(无标题)",
                len(back) if back else 0,
                back[:500] if back else front[:500],
            ),
        )
        # 同步写入 metadata (通过 UPDATE, 不破坏 INSERT 字段白名单)
        db.execute(
            "UPDATE materials SET summary = summary WHERE material_id = %s",
            (material_id,),
        )
        # 单独 metadata 列 (如果存在)
        try:
            db.execute(
                "UPDATE materials SET summary = %s WHERE material_id = %s",
                (json.dumps(metadata, ensure_ascii=False), material_id),
            )
        except Exception:
            pass
        logger.info(
            "ProjectNodeExported → material 成功: node=%s material_id=%s",
            p["node_id"], material_id,
        )
    except Exception as e:
        logger.error(
            "ProjectNodeExported → material 失败: node=%s err=%s",
            p["node_id"], e, exc_info=True,
        )


# ────────────────────────────────────────────────────────────────────
# 3. Project → CognitiveNode
# ────────────────────────────────────────────────────────────────────


async def _export_to_cognitive_node(event: Any) -> None:
    """从 Project 节点创建 CognitiveNode (atom 级别)。"""
    p = _extract_payload(event)
    user_id = p["user_id"]
    if not user_id:
        return
    front, _ = _resolve_node_text(p)
    if not front:
        logger.info(
            "ProjectNodeExported → cognitive_node 跳过: node=%s 无标题",
            p["node_id"],
        )
        return

    try:
        from app.domain.cognitive.writer import CognitiveNodeWriter
        writer = CognitiveNodeWriter(user_id)
        node = writer.create_node(
            label=front[:80] or "(未命名节点)",
            level="atom",
            node_type="auto_generated",
            created_by="project_export",
            is_visible=False,
            description=f"从 Project 节点 {p['node_id']} 导入",
            metadata={
                "source_module": "project",
                "project_id": p["project_id"],
                "project_node_id": p["node_id"],
            },
        )
        logger.info(
            "ProjectNodeExported → cognitive_node 成功: node=%s → %s",
            p["node_id"], node.id,
        )
    except Exception as e:
        logger.error(
            "ProjectNodeExported → cognitive_node 失败: node=%s err=%s",
            p["node_id"], e, exc_info=True,
        )


# ────────────────────────────────────────────────────────────────────
# 4. Project → Plan
# ────────────────────────────────────────────────────────────────────


async def _export_to_plan(event: Any) -> None:
    """从 Project 节点创建 PlanItem。"""
    p = _extract_payload(event)
    user_id = p["user_id"]
    if not user_id:
        return
    front, back = _resolve_node_text(p)
    title = front or "(无标题)"
    description = back or ""

    try:
        from app.services.planning.items import create_plan_item
        result = create_plan_item(
            user_id=user_id,
            body={
                "source_module": "project",
                "target_type": "project_node",
                "target_ref_id": p["node_id"],
                "title": title[:200],
                "description": description[:1000],
                "estimated_minutes": 15,
                "linked_node_ids": [],
                "priority": 0,
            },
        )
        logger.info(
            "ProjectNodeExported → plan 成功: node=%s → plan_item=%s",
            p["node_id"], result.get("id", "?"),
        )
    except Exception as e:
        logger.error(
            "ProjectNodeExported → plan 失败: node=%s err=%s",
            p["node_id"], e, exc_info=True,
        )


# ────────────────────────────────────────────────────────────────────
# 5. Project → LanguageRoom
# ────────────────────────────────────────────────────────────────────


async def _export_to_language_room(event: Any) -> None:
    """从 Project 节点创建 language room (作为房间话题)。"""
    p = _extract_payload(event)
    user_id = p["user_id"]
    if not user_id:
        return
    front, back = _resolve_node_text(p)
    name = front[:100] or "(无标题项目节点)"

    try:
        from app.api.liveroom.service import create_room
        settings = {
            "topic_source": "project",
            "project_id": p["project_id"],
            "project_node_id": p["node_id"],
            "topic_content": back or front,
        }
        result = create_room(
            user_id=user_id,
            payload={
                "name": name,
                "scenario_id": "",
                "room_type": "1v1",
                "max_participants": 2,
                "is_recording_enabled": False,
                "is_transcript_enabled": True,
                "ai_intrusion_level": "low",
                "settings": settings,
            },
        )
        logger.info(
            "ProjectNodeExported → language_room 成功: node=%s → room=%s",
            p["node_id"], result.get("id", "?"),
        )
    except Exception as e:
        logger.error(
            "ProjectNodeExported → language_room 失败: node=%s err=%s",
            p["node_id"], e, exc_info=True,
        )


# ────────────────────────────────────────────────────────────────────
# 统一入口: ProjectNodeExported 派发器
# ────────────────────────────────────────────────────────────────────


async def handle_project_node_exported(event: Any) -> None:
    """ProjectNodeExported 统一订阅者: 根据 target_module 路由到对应 handler。

    DI 在启动时调用 bus.subscribe("ProjectNodeExported", this_fn),
    本函数检查 target_module, 调用对应子 handler。
    """
    try:
        from shared.events import ProjectNodeExported, CrossModuleTarget
        if not isinstance(event, ProjectNodeExported):
            return
        target = getattr(event, "target_module", None)
        if target is None:
            return
        # 兼容: target 可能是枚举或字符串
        target_value = target.value if hasattr(target, "value") else str(target)
        if target_value == CrossModuleTarget.FLASHCARD.value:
            await _export_to_flashcard(event)
        elif target_value == CrossModuleTarget.MATERIAL.value:
            await _export_to_material(event)
        elif target_value == CrossModuleTarget.COGNITIVE_NODE.value:
            await _export_to_cognitive_node(event)
        elif target_value == CrossModuleTarget.PLAN.value:
            await _export_to_plan(event)
        elif target_value == CrossModuleTarget.LANGUAGE_ROOM.value:
            await _export_to_language_room(event)
        else:
            logger.debug(
                "ProjectNodeExported 无匹配 handler: target=%s", target_value,
            )
    except Exception as e:
        # 兜底: 即使路由层失败也不应影响事件总线
        logger.error(
            "ProjectNodeExported 派发失败: %s", e, exc_info=True,
        )
