"""
LanguageRoom 工具集 (ADR 0004 决策 5)

共享 tool registry 的一部分 — 由 LanguageRoom 模块贡献的 LLM 工具。

设计：
  - AI 角色 / 用户 / 服务 都通过 `app.infrastructure.llm.tool_repository` 调用
  - 工具元信息定义在 `tool_registry.py ALL_TOOL_INFO` (单一事实来源)
  - 本文件只实现 handler + 同步入口

工具清单:
  - tool_vocabulary_capture  (用户/API 写 flashcards + vocabulary_captures)
  - tool_error_mark          (用户/API 写 ErrorBookEntry + 更新 room_transcripts.is_error)
  - tool_message_post        (用户/API 写 explain_cards 浮卡)
  - tool_knowledge_search    (AI helper 在生成回答前搜索知识)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  LLM Function Calling schema (供 main.py 注册到 tool_repository)
# ══════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "tool_vocabulary_capture",
            "description": "在 LanguageRoom 房间内捕获生词, 自动生成 FlashCard 数据卡 (source=language_room)",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户 ID"},
                    "room_id": {"type": "string", "description": "房间 ID"},
                    "transcript_id": {"type": "string", "description": "转写片段 ID (可空)"},
                    "word": {"type": "string", "description": "生词"},
                    "translation": {"type": "string", "description": "释义/翻译"},
                    "context_sentence": {"type": "string", "description": "上下文例句"},
                    "language": {"type": "string", "description": "目标语言"},
                    "linked_node_ids": {
                        "type": "array", "items": {"type": "string"},
                        "description": "关联知识点 ID 列表",
                    },
                },
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_error_mark",
            "description": "在 LanguageRoom 房间内标记用户转写片段为错误, 复用 ErrorBookEntry",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户 ID"},
                    "room_id": {"type": "string", "description": "房间 ID"},
                    "transcript_id": {"type": "string", "description": "转写片段 ID"},
                    "error_type": {
                        "type": "string",
                        "enum": ["grammar", "vocabulary", "pronunciation", "coherence"],
                        "default": "grammar",
                    },
                    "user_note": {"type": "string", "description": "用户备注"},
                    "linked_node_ids": {
                        "type": "array", "items": {"type": "string"},
                        "description": "关联知识点 ID 列表",
                    },
                },
                "required": ["transcript_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_message_post",
            "description": "在 LanguageRoom 房间内发送文字辅助消息, 复用 ExplainCard 浮卡",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户 ID"},
                    "room_id": {"type": "string", "description": "房间 ID"},
                    "text": {"type": "string", "description": "消息内容"},
                    "message_type": {
                        "type": "string",
                        "enum": ["text", "link", "spelling", "note"],
                        "default": "text",
                    },
                    "reference_url": {"type": "string", "description": "参考链接 (可选)"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_knowledge_search",
            "description": "在知识树中搜索节点, AI 辅助者 (ai_helper) 在生成回答前调用以获取相关上下文",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户 ID"},
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "default": 5, "description": "最大返回数量"},
                    "scope_node_id": {"type": "string", "description": "限定子树 (可选)"},
                },
                "required": ["query"],
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════
#  同步 handler — 单一事实来源
#  - service.py (sync) 直接调用
#  - ai_persona.py (sync LLM) 直接调用
#  - tool_executor.py (async) 通过异步包装调用
#
#  注意 (Task 架构 P0-2):
#  - 业务写入已委托给 services.liveroom.notes (create_error_entry /
#    create_explain_card / create_vocabulary_capture)
#  - 本文件只做参数解析 + 事件发布, 不再含 SQL
# ══════════════════════════════════════════════════════════════


def _handle_vocabulary_capture(params: dict) -> dict:
    """词汇捕获 — 委托给 services.liveroom.notes.create_vocabulary_capture (Task 架构 P0-2)

    服务层负责:
      - 写 flashcards (type=1, source='language_room')
      - 写 vocabulary_captures
      - 更新 room_sessions 计数
    本 handler 仅做参数解析 + 事件发布
    """
    from app.infrastructure.event_bus_utils import publish_event_safe
    from app.services.liveroom.notes import create_vocabulary_capture
    from shared.events import LanguageRoomVocabularyCaptured

    user_id = params.get("user_id", "")
    room_id = params.get("room_id", "")
    word = (params.get("word") or "").strip()
    if not word:
        return {"ok": False, "error": "word 不能为空"}

    try:
        result = create_vocabulary_capture(
            user_id=user_id,
            room_id=room_id,
            word=word,
            translation=params.get("translation", ""),
            context_sentence=params.get("context_sentence", ""),
            language=params.get("language", ""),
            transcript_id=params.get("transcript_id", ""),
            linked_node_ids=params.get("linked_node_ids", []),
        )
    except Exception as e:
        logger.exception("create_vocabulary_capture 失败")
        return {"ok": False, "error": str(e)}

    publish_event_safe(LanguageRoomVocabularyCaptured(
        user_id=user_id,
        room_id=room_id,
        transcript_id=params.get("transcript_id", ""),
        card_id=result.get("card_id", ""),
        word=word,
        translation=params.get("translation", ""),
    ))

    return {"ok": True, **result}


def _handle_error_mark(params: dict) -> dict:
    """错误标记 — 委托给 services.liveroom.notes.create_error_entry (Task 架构 P0-2)

    服务层负责:
      - 校验 transcript
      - 写 practice_error_book (ErrorBookEntry)
      - 标记 room_transcripts.is_error
      - 更新 room_sessions 计数
    本 handler 仅做参数解析 + 事件发布
    """
    from app.infrastructure.db.database import get_db
    from app.infrastructure.event_bus_utils import publish_event_safe
    from app.services.liveroom.notes import create_error_entry
    from shared.events import LanguageRoomErrorMarked

    user_id = params.get("user_id", "")
    room_id = params.get("room_id", "")
    transcript_id = params.get("transcript_id", "")
    if not transcript_id:
        return {"ok": False, "error": "transcript_id 必填"}

    # 校验 transcript 存在且属于此 user (服务层需要 transcript.text, 故前置校验)
    t = get_db().fetchone(
        """SELECT id FROM room_transcripts
           WHERE id = %s AND user_id = %s""",
        (transcript_id, user_id),
    )
    if not t:
        return {"ok": False, "error": "转写片段不存在或不属于此用户"}

    try:
        result = create_error_entry(
            user_id=user_id,
            room_id=room_id,
            transcript_id=transcript_id,
            error_type=params.get("error_type", "grammar"),
            user_note=params.get("user_note", ""),
            linked_node_ids=params.get("linked_node_ids", []),
        )
    except Exception as e:
        logger.exception("create_error_entry 失败")
        return {"ok": False, "error": str(e)}

    publish_event_safe(LanguageRoomErrorMarked(
        user_id=user_id,
        room_id=room_id,
        transcript_id=transcript_id,
        error_entry_id=result.get("error_entry_id", ""),
        error_type=params.get("error_type", "grammar"),
        linked_node_ids=params.get("linked_node_ids", []),
    ))

    return {"ok": True, **result}


def _handle_message_post(params: dict) -> dict:
    """文字辅助消息 — 委托给 services.liveroom.notes.create_explain_card (Task 架构 P0-2)

    服务层负责:
      - 写 explain_cards 浮卡
      - 更新 room_sessions 计数
    本 handler 仅做参数解析 + 事件发布
    """
    from app.infrastructure.event_bus_utils import publish_event_safe
    from app.services.liveroom.notes import create_explain_card
    from shared.events import LanguageRoomMessagePosted

    user_id = params.get("user_id", "")
    room_id = params.get("room_id", "")
    text = (params.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "text 不能为空"}

    try:
        result = create_explain_card(
            user_id=user_id,
            room_id=room_id,
            text=text,
            message_type=params.get("message_type", "text"),
            reference_url=params.get("reference_url", ""),
        )
    except Exception as e:
        logger.exception("create_explain_card 失败")
        return {"ok": False, "error": str(e)}

    publish_event_safe(LanguageRoomMessagePosted(
        user_id=user_id,
        room_id=room_id,
        message_id=result.get("id", ""),
        text=text,
        message_type=params.get("message_type", "text"),
    ))

    return {"ok": True, **result}


def _handle_knowledge_search(params: dict) -> dict:
    """知识搜索 — AI helper 用于在生成回答前获取上下文

    委托给 kn_svc.search (复用现有 knowledge_tree 知识图谱)
    """
    user_id = params.get("user_id", "")
    query = (params.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空", "results": []}

    try:
        from app.services.knowledge_tree.knowledge_node_service import kn_svc
        max_results = int(params.get("max_results", 5))
        nodes = kn_svc.search(user_id=user_id, query=query, limit=max_results)
        results = [
            {
                "id": n.id,
                "label": n.label,
                "brief": getattr(n, "brief", ""),
                "level": n.level,
            }
            for n in nodes
        ]
        return {
            "ok": True,
            "query": query,
            "total": len(results),
            "results": results,
        }
    except Exception as e:
        logger.exception("tool_knowledge_search 失败")
        return {"ok": False, "error": str(e), "results": []}


# 同步 handler 表
SYNC_HANDLERS: dict[str, Any] = {
    "tool_vocabulary_capture": _handle_vocabulary_capture,
    "tool_error_mark": _handle_error_mark,
    "tool_message_post": _handle_message_post,
    "tool_knowledge_search": _handle_knowledge_search,
}


# ══════════════════════════════════════════════════════════════
#  异步包装 (供 tool_executor / LLM 管线)
# ══════════════════════════════════════════════════════════════


async def _async_handle_vocabulary_capture(params: dict) -> dict:
    return _handle_vocabulary_capture(params)


async def _async_handle_error_mark(params: dict) -> dict:
    return _handle_error_mark(params)


async def _async_handle_message_post(params: dict) -> dict:
    return _handle_message_post(params)


async def _async_handle_knowledge_search(params: dict) -> dict:
    return _handle_knowledge_search(params)


TOOL_HANDLERS: dict[str, Any] = {
    "tool_vocabulary_capture": _async_handle_vocabulary_capture,
    "tool_error_mark": _async_handle_error_mark,
    "tool_message_post": _async_handle_message_post,
    "tool_knowledge_search": _async_handle_knowledge_search,
}


# ══════════════════════════════════════════════════════════════
#  公共入口
# ══════════════════════════════════════════════════════════════


def execute_sync(tool_name: str, params: dict) -> dict:
    """同步执行 liveroom tool (供 service 层 + ai_persona 调用)

    Args:
        tool_name: 工具名 (tool_vocabulary_capture / tool_error_mark / ...)
        params: 工具参数

    Returns:
        dict: 执行结果 (含 ok / error / 业务数据)
    """
    handler = SYNC_HANDLERS.get(tool_name)
    if not handler:
        return {"ok": False, "error": f"tool {tool_name} not found"}
    try:
        return handler(params)
    except Exception as e:
        logger.exception("执行 liveroom tool 失败: %s", tool_name)
        return {"ok": False, "error": str(e)}
