"""
LanguageRoom 笔记服务层 (Task 架构 P0-2)

将以下 3 个共享 tool handler 的 SQL 收敛到独立服务函数:
  - create_error_entry        ← tool_error_mark
  - create_explain_card       ← tool_message_post
  - create_vocabulary_capture ← tool_vocabulary_capture

设计原则
========
1. **职责单一** — 本模块只管"写入数据 + 同步更新 session 计数", 不负责事件发布
2. **可独立测试** — 单元测试可直接调用本模块函数, 不需要构造 tool params
3. **tool handler 退化** — handler 仅做参数解析 + 调用本服务, 不再含 SQL
4. **错误降级** — 单表写入失败不影响其他表 (FlashCard / ErrorBookEntry 写入可能因表不存在而失败)

调用方
======
- ``app.infrastructure.llm.liveroom_tools._handle_error_mark``
- ``app.infrastructure.llm.liveroom_tools._handle_message_post``
- ``app.infrastructure.llm.liveroom_tools._handle_vocabulary_capture``
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def _new_id(prefix: str) -> str:
    """生成 12 位短 UUID"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _resolve_participant(db, room_id: str, user_id: str) -> dict | None:
    """获取房间内该用户的 active participant_id"""
    return db.fetchone(
        "SELECT id FROM room_participants WHERE room_id = %s AND user_id = %s",
        (room_id, user_id),
    )


# ═══════════════════════════════════════════════════════
#  错误条目 (复用 ErrorBookEntry = error_book 表)
#  Task #69: 修复 B1 — 写不存在的 practice_error_book → 写真实 error_book
#  字段映射 (practice 通用 schema → language_room 复用):
#    entry_id              ← EBE_xxx
#    user_id               ← user_id
#    question_id           ← transcript_id (synthetic, 兼容 NOT NULL 历史)
#    source_type           ← 'language_room'
#    source_ref_id         ← transcript_id (多源定位)
#    error_type            ← error_type (4 类: grammar/vocabulary/pronunciation/coherence)
#    user_answer           ← transcript text
#    misconception         ← user_note (用户批注)
#    referenced_materials_json ← linked_node_ids (JSONB)
#    is_resolved           ← FALSE
#    attribution           ← {room_id, context, source: 'language_room', linked_node_ids}
# ═══════════════════════════════════════════════════════


def create_error_entry(
    user_id: str,
    room_id: str,
    transcript_id: str,
    error_type: str = "grammar",
    user_note: str = "",
    linked_node_ids: list[str] | None = None,
) -> dict:
    """创建 ErrorBookEntry (transcript 错误标记)

    Returns:
        {"error_entry_id": str, "transcript_id": str, "error_type": str}
    """
    from app.infrastructure.db.database import get_db

    db = get_db()
    error_entry_id = _new_id("EBE")

    # 1. 取 transcript 文本 (用于错误条目的 user_answer 字段)
    # 注: room_transcripts 表只有 text 列, 无 user_text
    t = db.fetchone(
        """SELECT text FROM room_transcripts
           WHERE id = %s AND user_id = %s""",
        (transcript_id, user_id),
    )
    user_answer = (t.get("text") or "") if t else ""

    # 2. 写 error_book (真实表名) — Task #69 修复 B1
    attribution_payload = {
        "room_id": room_id,
        "source": "language_room",
        "source_ref_id": transcript_id,
        "linked_node_ids": linked_node_ids or [],
        "context": user_note,
    }
    db.execute(
        """INSERT INTO error_book
            (entry_id, user_id, question_id, source_type, source_ref_id,
             error_type, user_answer, misconception,
             referenced_materials_json, attribution,
             is_resolved, review_count, created_at)
           VALUES (%s, %s, %s, 'language_room', %s, %s, %s, %s,
             %s::jsonb, %s::jsonb,
             FALSE, 0, NOW())""",
        (
            error_entry_id, user_id, transcript_id, transcript_id,
            error_type,
            user_answer,
            user_note,
            json.dumps(linked_node_ids or []),
            json.dumps(attribution_payload, ensure_ascii=False),
        ),
    )

    # 3. 标记 transcript
    db.execute(
        """UPDATE room_transcripts
           SET is_error = TRUE, error_entry_id = %s, is_user_marked = TRUE,
               user_note = %s
           WHERE id = %s""",
        (error_entry_id, user_note, transcript_id),
    )

    # 4. 更新 session 计数
    p = _resolve_participant(db, room_id, user_id)
    if p:
        db.execute(
            """UPDATE room_sessions
               SET errors_marked = errors_marked + 1,
                   linked_node_ids = %s::jsonb,
                   updated_at = NOW()
               WHERE participant_id = %s AND ended_at IS NULL""",
            (
                json.dumps(linked_node_ids or []),
                p["id"],
            ),
        )

    return {
        "error_entry_id": error_entry_id,
        "transcript_id": transcript_id,
        "error_type": error_type,
    }


# ═══════════════════════════════════════════════════════
#  解释卡片 (复用 ExplainCard = messages.metadata.explain_cards)
#  Task #69: 修复 B2 — D14 已删 explain_cards 表, 改存 messages.metadata
#  存储策略:
#    - 写入 messages 表 (单条 message 即一张解释卡)
#    - conv_id = room_id (房间作为会话上下文)
#    - role = 'assistant' (AI 提供的辅助说明)
#    - content = 卡片文本
#    - metadata JSONB:
#        {
#          "source_module": "language_room",
#          "source_ref_id": <room_id>,
#          "message_type": <type>,
#          "reference_url": <url>,
#          "explain_cards": [<cards-list>],  # 历史兼容字段
#          "is_explain_card": true,
#        }
#  查询: list_messages 走 metadata->>'source_module'='language_room' + source_ref_id
# ═══════════════════════════════════════════════════════


def create_explain_card(
    user_id: str,
    room_id: str,
    text: str,
    message_type: str = "text",
    reference_url: str = "",
) -> dict:
    """创建 ExplainCard (房间文字辅助浮卡)

    Returns:
        {"id": str, "text": str, "message_type": str}
    """
    from app.infrastructure.db.database import get_db

    db = get_db()
    message_id = _new_id("MSG")

    # Task #69: messages 表需先确保存在 (与 conversation.MessageRepository 共用)
    # 这里直接执行幂等 CREATE TABLE IF NOT EXISTS, 不依赖 conversation 模块
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id                  TEXT PRIMARY KEY,
                user_id             TEXT NOT NULL,
                conv_id             TEXT NOT NULL,
                role                TEXT NOT NULL,
                content             TEXT DEFAULT '',
                content_blocks      JSONB DEFAULT '[]',
                text_summary        TEXT DEFAULT '',
                knowledge_node_ids  JSONB DEFAULT '[]',
                parent_id           TEXT,
                children_ids        JSONB DEFAULT '[]',
                has_sub_branches    BOOLEAN DEFAULT FALSE,
                sub_branch_ids      JSONB DEFAULT '[]',
                sub_branch_summaries JSONB DEFAULT '[]',
                timestamp           TIMESTAMPTZ DEFAULT NOW(),
                token_count         INTEGER DEFAULT 0,
                version             INTEGER DEFAULT 1,
                is_deleted          BOOLEAN DEFAULT FALSE,
                agent_label         TEXT DEFAULT '',
                metadata            JSONB DEFAULT '{}'
            )
        """)
    except Exception as e:
        logger.debug("messages 表 ensure 失败 (可能已存在): %s", e)

    metadata_payload = {
        "source_module": "language_room",
        "source_ref_id": room_id,
        "message_type": message_type,
        "reference_url": reference_url,
        "is_explain_card": True,
        "explain_cards": [
            {
                "id": message_id,
                "content": text,
                "message_type": message_type,
                "reference_url": reference_url,
            }
        ],
    }

    db.execute(
        """INSERT INTO messages
            (id, user_id, conv_id, role, content, metadata, timestamp)
           VALUES (%s, %s, %s, 'assistant', %s, %s::jsonb, NOW())""",
        (
            message_id, user_id, room_id,
            text,
            json.dumps(metadata_payload, ensure_ascii=False),
        ),
    )

    # 更新 session 计数
    p = _resolve_participant(db, room_id, user_id)
    if p:
        db.execute(
            """UPDATE room_sessions
               SET messages_posted = messages_posted + 1,
                   updated_at = NOW()
               WHERE participant_id = %s AND ended_at IS NULL""",
            (p["id"],),
        )

    return {
        "id": message_id,
        "text": text,
        "message_type": message_type,
    }


# ═══════════════════════════════════════════════════════
#  词汇捕获 (复用 FlashCard 数据卡)
# ═══════════════════════════════════════════════════════


def create_vocabulary_capture(
    user_id: str,
    room_id: str,
    word: str,
    translation: str = "",
    context_sentence: str = "",
    language: str = "",
    transcript_id: str = "",
    linked_node_ids: list[str] | None = None,
) -> dict:
    """创建词汇便签 (FlashCard 数据卡 + vocabulary_captures)

    Returns:
        {"id": str, "card_id": str, "word": str, "translation": str}
    """
    from app.infrastructure.db.database import get_db

    db = get_db()
    capture_id = _new_id("VC")
    card_id = _new_id("FC")

    # 1. 写 FlashCard (降级: 表可能不存在)
    try:
        db.execute(
            """INSERT INTO flashcards
                (id, user_id, type, source, front_text, back_text, back_context,
                 language, source_ref, status, linked_node_ids,
                 tags, created_at, updated_at)
               VALUES (%s, %s, 1, 'language_room', %s, %s, %s, %s, %s::jsonb,
                 'pending', %s::jsonb, '[]'::jsonb, NOW(), NOW())""",
            (
                card_id, user_id, word,
                translation,
                context_sentence,
                language,
                json.dumps({
                    "module": "language_room",
                    "id": capture_id,
                    "room_id": room_id,
                    "transcript_id": transcript_id,
                }),
                json.dumps(linked_node_ids or []),
            ),
        )
    except Exception as e:
        logger.warning("FlashCard 数据卡创建失败（表可能不存在）: %s", e)
        card_id = ""

    # 2. 写 vocabulary_captures
    db.execute(
        """INSERT INTO vocabulary_captures
            (id, user_id, room_id, transcript_id, card_id, word, translation,
             context_sentence, language, captured_at, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())""",
        (
            capture_id, user_id, room_id,
            transcript_id or None,
            card_id, word, translation,
            context_sentence, language,
        ),
    )

    # 3. 更新 session 计数
    p = _resolve_participant(db, room_id, user_id)
    if p:
        db.execute(
            """UPDATE room_sessions
               SET vocabulary_captured = vocabulary_captured + 1,
                   cards_generated = cards_generated + 1,
                   updated_at = NOW()
               WHERE participant_id = %s AND ended_at IS NULL""",
            (p["id"],),
        )

    return {
        "id": capture_id,
        "card_id": card_id,
        "word": word,
        "translation": translation,
    }
