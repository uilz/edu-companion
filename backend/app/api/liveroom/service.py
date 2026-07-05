"""LanguageRoom Service — 业务逻辑层

依据 docs/modules/language-room/overview.md + data-model.md + ADR 0004

核心实现：
- 11 张表的 CRUD
- 事件发布（按参与者维度）
- 错误标记 → 复用 ErrorBookEntry
- 词汇便签 → 复用 FlashCard 数据卡
- 文字辅助 → 复用 ExplainCard
- AI 角色服务调用
- LiveKit Token 颁发
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── 工具 ──


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _ensure_tables() -> None:
    """确保表存在（幂等）"""
    try:
        from app.services.liveroom import _ensure_tables as _et
        _et()
    except Exception as e:
        logger.warning("liveroom _ensure_tables 失败: %s", e)


def _publish_event(event: Any) -> None:
    """统一事件发布 — 委托给 publish_event_safe 自动处理 sync/async 上下文"""
    from app.infrastructure.event_bus_utils import publish_event_safe
    publish_event_safe(event)


def _row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    for col in ("settings", "roles", "target_goals", "linked_node_ids",
                "helper_types", "session_metadata", "chapters_visited"):
        if col in out and isinstance(out[col], str):
            try:
                out[col] = json.loads(out[col])
            except (json.JSONDecodeError, TypeError):
                out[col] = [] if col != "settings" else {}
    return out


# ════════════════════════════════════════════════
# 房间 CRUD
# ════════════════════════════════════════════════


def create_room(user_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomCreated

    db = get_db()
    room_id = _uid("LR")
    db.execute(
        """INSERT INTO language_rooms
            (id, owner_id, name, scenario_id, room_type, max_participants,
             is_recording_enabled, is_transcript_enabled, ai_intrusion_level,
             status, started_at, settings, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', NOW(), %s::jsonb, NOW(), NOW())""",
        (
            room_id, user_id, payload.get("name", ""),
            payload.get("scenario_id", ""), payload.get("room_type", "1v1"),
            payload.get("max_participants", 2),
            payload.get("is_recording_enabled", False),
            payload.get("is_transcript_enabled", True),
            payload.get("ai_intrusion_level", "low"),
            json.dumps(payload.get("settings", {})),
        ),
    )
    # 写 LiveKit 房间注册
    try:
        from app.services.liveroom.realtime import create_room
        create_room(
            room_id, payload.get("name", ""),
            payload.get("max_participants", 2),
            payload.get("settings"),
        )
    except Exception as e:
        logger.warning("LiveKit 房间注册失败（可忽略）: %s", e)

    # 发布事件
    _publish_event(LanguageRoomCreated(
        user_id=user_id,
        room_id=room_id,
        scenario_id=payload.get("scenario_id", ""),
        max_participants=payload.get("max_participants", 2),
        is_recording_enabled=payload.get("is_recording_enabled", False),
    ))

    return get_room(user_id, room_id)


def get_room(user_id: str, room_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = _row_to_dict(db.fetchone("SELECT * FROM language_rooms WHERE id = %s", (room_id,)))
    if not row:
        return {}
    # 统计活跃参与者
    pcount = db.fetchone(
        "SELECT COUNT(*) AS c FROM room_participants WHERE room_id = %s AND left_at IS NULL",
        (room_id,),
    )
    row["participant_count"] = int(pcount["c"]) if pcount else 0
    return row


def list_rooms(user_id: str, status: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    params: list[Any] = [user_id]
    sql = """SELECT lr.* FROM language_rooms lr
             WHERE lr.id IN (
               SELECT room_id FROM room_participants
               WHERE user_id = %s
             )"""
    if status:
        sql += " AND lr.status = %s"
        params.append(status)
    sql += " ORDER BY lr.started_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_dict(r) for r in rows]


def update_room(user_id: str, room_id: str, payload: dict) -> Optional[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    existing = db.fetchone(
        "SELECT owner_id, status FROM language_rooms WHERE id = %s", (room_id,),
    )
    if not existing:
        return None
    if existing["owner_id"] != user_id:
        raise PermissionError("仅房主可以更新房间设置")

    # 字段级更新
    fields: list[str] = []
    params: list[Any] = []
    for key in ("name", "scenario_id", "max_participants",
                "is_recording_enabled", "is_transcript_enabled", "ai_intrusion_level"):
        if key in payload and payload[key] is not None:
            fields.append(f"{key} = %s")
            params.append(payload[key])
    if "settings" in payload:
        fields.append("settings = %s::jsonb")
        params.append(json.dumps(payload["settings"]))
    if not fields:
        return get_room(user_id, room_id)
    fields.append("updated_at = NOW()")
    params.append(room_id)
    db.execute(f"UPDATE language_rooms SET {', '.join(fields)} WHERE id = %s", tuple(params))
    return get_room(user_id, room_id)


def end_room(user_id: str, room_id: str) -> Optional[dict]:
    """结束房间 + 按参与者维度分发聚合事件"""
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomEnded, LanguageRoomCompleted, LanguageRoomParticipantLeft

    db = get_db()
    existing = db.fetchone(
        "SELECT * FROM language_rooms WHERE id = %s", (room_id,),
    )
    if not existing:
        return None
    if existing["owner_id"] != user_id:
        raise PermissionError("仅房主可以结束房间")

    now = _now()
    db.execute(
        "UPDATE language_rooms SET status = 'ended', ended_at = NOW(), updated_at = NOW() WHERE id = %s",
        (room_id,),
    )
    # 关闭所有 active 参与者
    db.execute(
        "UPDATE room_participants SET left_at = NOW() WHERE room_id = %s AND left_at IS NULL",
        (room_id,),
    )
    # 关闭所有 active session
    db.execute(
        """UPDATE room_sessions SET ended_at = NOW(),
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
            WHERE room_id = %s AND ended_at IS NULL""",
        (room_id,),
    )

    # 计算 duration: 兼容 offset-naive (DB) 和 offset-aware (Python) 时间戳
    started_at = existing.get("started_at")
    if started_at is not None and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    duration = (now - started_at).total_seconds() if started_at else 0

    # 发布 LanguageRoomEnded
    _publish_event(LanguageRoomEnded(
        user_id=user_id, room_id=room_id, duration_seconds=duration,
    ))

    # 按参与者维度分发 LanguageRoomCompleted
    participants = db.fetchall(
        """SELECT id, user_id, participant_type FROM room_participants
           WHERE room_id = %s""",
        (room_id,),
    )
    for p in participants:
        # 该用户的转写段
        transcripts = db.fetchall(
            """SELECT id, text, language, started_at, ended_at, confidence, is_error
               FROM room_transcripts WHERE participant_id = %s ORDER BY started_at""",
            (p["id"],),
        )
        # 该用户的错误数
        errors_count = db.fetchone(
            "SELECT COUNT(*) AS c FROM room_transcripts WHERE participant_id = %s AND is_error = TRUE",
            (p["id"],),
        )
        # 该用户的会话统计
        sess = db.fetchone(
            """SELECT errors_marked, cards_generated, ai_help_requests, linked_node_ids
               FROM room_sessions WHERE participant_id = %s ORDER BY started_at DESC LIMIT 1""",
            (p["id"],),
        )
        sess = sess or {}
        linked = sess.get("linked_node_ids") or "[]"
        if isinstance(linked, str):
            try:
                linked = json.loads(linked)
            except Exception:
                linked = []
        # 仅 human 接收聚合事件（AI 角色不算）
        if p["participant_type"] == "human":
            _publish_event(LanguageRoomCompleted(
                user_id=p["user_id"],
                room_id=room_id,
                session_id=p["id"],
                scenario_id=existing.get("scenario_id", ""),
                duration_seconds=duration,
                transcript_segments=[dict(t) for t in transcripts],
                errors_marked=int(errors_count["c"]) if errors_count else int(sess.get("errors_marked", 0) or 0),
                cards_generated=int(sess.get("cards_generated", 0) or 0),
                linked_node_ids=linked,
                ai_help_requests=int(sess.get("ai_help_requests", 0) or 0),
            ))

    return get_room(user_id, room_id)


# ════════════════════════════════════════════════
# 参与者
# ════════════════════════════════════════════════


def join_room(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomParticipantJoined, LanguageRoomStarted

    db = get_db()
    room = db.fetchone("SELECT * FROM language_rooms WHERE id = %s", (room_id,))
    if not room:
        return {"error": "房间不存在"}
    if room["status"] != "active":
        return {"error": "房间已结束"}

    # 检查邀请 token（邀请制）
    token = payload.get("invitation_token", "")
    if token:
        inv = db.fetchone(
            """SELECT * FROM room_invitations
               WHERE room_id = %s AND invitation_token = %s
                 AND (is_used = FALSE OR invitee_id = %s)""",
            (room_id, token, user_id),
        )
        if not inv:
            return {"error": "邀请 token 无效"}

    # 检查人数上限
    active_count = db.fetchone(
        "SELECT COUNT(*) AS c FROM room_participants WHERE room_id = %s AND left_at IS NULL",
        (room_id,),
    )
    if active_count and int(active_count["c"]) >= room["max_participants"]:
        return {"error": "房间已满"}

    # 检查是否已加入
    existing = db.fetchone(
        """SELECT * FROM room_participants
           WHERE room_id = %s AND user_id = %s AND left_at IS NULL""",
        (room_id, user_id),
    )
    if existing:
        return _row_to_dict(existing)

    participant_id = _uid("PART")
    db.execute(
        """INSERT INTO room_participants
            (id, room_id, user_id, participant_type, role_label, language,
             joined_at, is_owner, created_at)
           VALUES (%s, %s, %s, 'human', %s, %s, NOW(), FALSE, NOW())""",
        (
            participant_id, room_id, user_id,
            payload.get("role_label", ""), payload.get("language", ""),
        ),
    )

    # 第一个参与者 = 房主之外, 启动房间
    started = bool(active_count and int(active_count["c"]) == 0)
    if started:
        db.execute(
            "UPDATE language_rooms SET started_at = NOW() WHERE id = %s AND started_at IS NULL",
            (room_id,),
        )
        _publish_event(LanguageRoomStarted(
            user_id=user_id, room_id=room_id,
        ))

    # 创建 session
    session_id = _uid("RS")
    db.execute(
        """INSERT INTO room_sessions
            (id, room_id, user_id, participant_id, started_at, created_at, updated_at)
           VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())""",
        (session_id, room_id, user_id, participant_id),
    )

    # 发布事件
    _publish_event(LanguageRoomParticipantJoined(
        user_id=user_id,
        room_id=room_id,
        participant_id=participant_id,
        participant_type="human",
    ))

    return {
        "id": participant_id,
        "room_id": room_id,
        "user_id": user_id,
        "participant_type": "human",
        "is_owner": False,
    }


def leave_room(user_id: str, room_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomParticipantLeft

    db = get_db()
    p = db.fetchone(
        """SELECT * FROM room_participants
           WHERE room_id = %s AND user_id = %s AND left_at IS NULL""",
        (room_id, user_id),
    )
    if not p:
        return {"ok": True, "left": True}
    db.execute(
        "UPDATE room_participants SET left_at = NOW() WHERE id = %s",
        (p["id"],),
    )
    db.execute(
        """UPDATE room_sessions SET ended_at = NOW(),
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
            WHERE participant_id = %s AND ended_at IS NULL""",
        (p["id"],),
    )
    _publish_event(LanguageRoomParticipantLeft(
        user_id=user_id,
        room_id=room_id,
        participant_id=p["id"],
        speaking_time_seconds=p.get("speaking_time_seconds", 0) or 0,
    ))
    return {"ok": True, "participant_id": p["id"]}


def list_participants(user_id: str, room_id: str) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT * FROM room_participants
           WHERE room_id = %s ORDER BY joined_at""",
        (room_id,),
    )
    return [_row_to_dict(r) for r in rows]


def mute_participant(user_id: str, room_id: str, target_user_id: str, muted: bool) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    room = db.fetchone("SELECT owner_id FROM language_rooms WHERE id = %s", (room_id,))
    if not room:
        return {"error": "房间不存在"}
    if room["owner_id"] != user_id:
        raise PermissionError("仅房主可以静音他人")

    db.execute(
        "UPDATE room_participants SET is_muted = %s WHERE room_id = %s AND user_id = %s",
        (muted, room_id, target_user_id),
    )

    # LiveKit 操作
    try:
        from app.services.liveroom.realtime import mute_participant
        p = db.fetchone(
            "SELECT id FROM room_participants WHERE room_id = %s AND user_id = %s",
            (room_id, target_user_id),
        )
        if p:
            mute_participant(room_id, p["id"], muted)
    except Exception as e:
        logger.warning("LiveKit 静音操作失败: %s", e)

    return {"ok": True, "muted": muted}


# ════════════════════════════════════════════════
# 场景切换
# ════════════════════════════════════════════════


def change_scenario(user_id: str, room_id: str, scenario_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomScenarioChanged

    db = get_db()
    room = db.fetchone("SELECT owner_id, scenario_id FROM language_rooms WHERE id = %s", (room_id,))
    if not room:
        return {"error": "房间不存在"}
    if room["owner_id"] != user_id:
        raise PermissionError("仅房主可以切换场景")
    old_scenario = room.get("scenario_id", "")
    db.execute(
        "UPDATE language_rooms SET scenario_id = %s, updated_at = NOW() WHERE id = %s",
        (scenario_id, room_id),
    )
    _publish_event(LanguageRoomScenarioChanged(
        user_id=user_id,
        room_id=room_id,
        old_scenario_id=old_scenario or "",
        new_scenario_id=scenario_id,
    ))
    return {"ok": True, "scenario_id": scenario_id}


# ════════════════════════════════════════════════
# AI 角色
# ════════════════════════════════════════════════


def add_ai_persona_to_room(user_id: str, room_id: str, persona_id: str, role_label: str = "") -> dict:
    _ensure_tables()
    from app.services.liveroom.ai_persona import join_ai_companion
    return join_ai_companion(room_id, user_id, persona_id, role_label)


def remove_ai_persona_from_room(user_id: str, room_id: str, participant_id: str) -> dict:
    _ensure_tables()
    from app.services.liveroom.ai_persona import leave_ai_companion
    return leave_ai_companion(room_id, participant_id, user_id)


# ════════════════════════════════════════════════
# 转写
# ════════════════════════════════════════════════


def add_transcript(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomTranscriptSegmentAdded

    db = get_db()
    # 找该用户在此房间的 participant
    p = db.fetchone(
        """SELECT id FROM room_participants
           WHERE room_id = %s AND user_id = %s AND left_at IS NULL""",
        (room_id, user_id),
    )
    if not p:
        return {"error": "用户未加入该房间"}

    # 递增 segment_index
    last = db.fetchone(
        """SELECT MAX(segment_index) AS m FROM room_transcripts
           WHERE participant_id = %s""",
        (p["id"],),
    )
    next_idx = (last["m"] + 1) if (last and last.get("m") is not None) else 1

    transcript_id = _uid("TR")
    started_at = payload.get("started_at") or _now()
    ended_at = payload.get("ended_at") or _now()
    db.execute(
        """INSERT INTO room_transcripts
            (id, room_id, participant_id, user_id, segment_index, text, language,
             started_at, ended_at, confidence, speaker_id, speaker_name, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
        (
            transcript_id, room_id, p["id"], user_id, next_idx,
            payload.get("text", ""), payload.get("language", ""),
            started_at, ended_at,
            payload.get("confidence", 0.0),
            payload.get("speaker_id", user_id),
            payload.get("speaker_name", ""),
        ),
    )
    # 更新 session 计数
    db.execute(
        """UPDATE room_sessions SET transcript_count = transcript_count + 1,
            updated_at = NOW() WHERE participant_id = %s AND ended_at IS NULL""",
        (p["id"],),
    )
    _publish_event(LanguageRoomTranscriptSegmentAdded(
        user_id=user_id,
        room_id=room_id,
        transcript_id=transcript_id,
        participant_id=p["id"],
        speaker_id=payload.get("speaker_id", user_id),
        text=payload.get("text", ""),
        language=payload.get("language", ""),
        confidence=payload.get("confidence", 0.0),
    ))
    return {"transcript_id": transcript_id}


def list_transcripts(
    user_id: str, room_id: str,
    only_user: bool = True,
    only_errors: bool = False,
    limit: int = 200,
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    params: list[Any] = [room_id]
    sql = "SELECT * FROM room_transcripts WHERE room_id = %s"
    if only_user:
        sql += " AND user_id = %s"
        params.append(user_id)
    if only_errors:
        sql += " AND is_error = TRUE"
    sql += " ORDER BY started_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_dict(r) for r in rows]


# ════════════════════════════════════════════════
# 词汇便签 (复用 FlashCard 数据卡)
# ════════════════════════════════════════════════


def capture_vocabulary(user_id: str, room_id: str, payload: dict) -> dict:
    """词汇便签 — 走共享 tool registry (ADR 0004 决策 5)

    实际写入由 `tool_vocabulary_capture` 工具处理 (liveroom_tools.py)
    这里只是把 REST 入口参数转成 tool params, 保证:
    - AI 角色和用户/API 共用一份数据写入逻辑
    - 单元测试和重构只需改一处
    """
    from app.infrastructure.llm.liveroom_tools import execute_sync

    result = execute_sync("tool_vocabulary_capture", {
        "user_id": user_id,
        "room_id": room_id,
        "transcript_id": payload.get("transcript_id", ""),
        "word": payload.get("word", ""),
        "translation": payload.get("translation", ""),
        "context_sentence": payload.get("context_sentence", ""),
        "language": payload.get("language", ""),
        "linked_node_ids": payload.get("linked_node_ids", []),
    })
    if not result.get("ok"):
        return {"error": result.get("error", "工具执行失败")}
    return {
        "id": result.get("id", ""),
        "card_id": result.get("card_id", ""),
        "word": result.get("word", ""),
        "translation": result.get("translation", ""),
    }


# ════════════════════════════════════════════════
# 错误标记 (复用 ErrorBookEntry)
# ════════════════════════════════════════════════


def mark_error(user_id: str, room_id: str, payload: dict) -> dict:
    """错误标记 — 走共享 tool registry (ADR 0004 决策 5)

    实际写入由 `tool_error_mark` 工具处理 (liveroom_tools.py)
    """
    from app.infrastructure.llm.liveroom_tools import execute_sync

    result = execute_sync("tool_error_mark", {
        "user_id": user_id,
        "room_id": room_id,
        "transcript_id": payload.get("transcript_id", ""),
        "error_type": payload.get("error_type", "grammar"),
        "user_note": payload.get("user_note", ""),
        "linked_node_ids": payload.get("linked_node_ids", []),
    })
    if not result.get("ok"):
        return {"error": result.get("error", "工具执行失败")}
    return {
        "error_entry_id": result.get("error_entry_id", ""),
        "transcript_id": result.get("transcript_id", ""),
        "error_type": result.get("error_type", "grammar"),
    }


# ════════════════════════════════════════════════
# 文字辅助区 (复用 ExplainCard)
# ════════════════════════════════════════════════


def post_message(user_id: str, room_id: str, payload: dict) -> dict:
    """文字辅助消息 — 走共享 tool registry (ADR 0004 决策 5)

    实际写入由 `tool_message_post` 工具处理 (liveroom_tools.py)
    """
    from app.infrastructure.llm.liveroom_tools import execute_sync

    result = execute_sync("tool_message_post", {
        "user_id": user_id,
        "room_id": room_id,
        "text": payload.get("text", ""),
        "message_type": payload.get("message_type", "text"),
        "reference_url": payload.get("reference_url", ""),
    })
    if not result.get("ok"):
        return {"error": result.get("error", "工具执行失败")}
    return {
        "id": result.get("id", ""),
        "text": result.get("text", ""),
        "message_type": result.get("message_type", "text"),
    }


def list_messages(user_id: str, room_id: str, limit: int = 50) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    # D14: explain_cards 表已砍, 卡片数据存 messages.metadata JSONB
    # (Task #69: 现在 create_explain_card 真的写 messages, 此查询应能取到数据)
    # 注: messages 表列名以实际 schema 为准: conv_id (not conversation_id), timestamp (not created_at)
    try:
        rows = db.fetchall(
            """SELECT * FROM messages
               WHERE metadata->>'source_module' = 'language_room'
                 AND metadata->>'source_ref_id' = %s
                 AND user_id = %s
                 AND is_deleted = FALSE
               ORDER BY timestamp DESC LIMIT %s""",
            (room_id, user_id, limit),
        )
    except Exception:
        # messages 表 / metadata 列可能不存在 — 降级返回空
        logger.debug("list_messages 表/列不可用, 返回空列表", exc_info=True)
        return []
    return [_row_to_dict(r) for r in rows]


# ════════════════════════════════════════════════
# 录音
# ════════════════════════════════════════════════


def start_recording(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomRecordingStarted
    from app.services.liveroom.realtime import start_recording as lk_start_recording

    db = get_db()
    recording_id = lk_start_recording(room_id, user_id)
    now = _now()
    db.execute(
        """INSERT INTO room_recordings
            (id, room_id, user_id, storage_path, started_at, ended_at, format, created_at)
           VALUES (%s, %s, %s, '', %s, %s, %s, NOW())""",
        (recording_id, room_id, user_id, now, now, payload.get("format", "opus")),
    )
    _publish_event(LanguageRoomRecordingStarted(
        user_id=user_id, room_id=room_id, recording_id=recording_id,
    ))
    return {"recording_id": recording_id, "started_at": now}


def stop_recording(user_id: str, room_id: str, recording_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomRecordingStopped
    from app.services.liveroom.realtime import stop_recording as lk_stop_recording

    db = get_db()
    rec = db.fetchone(
        "SELECT * FROM room_recordings WHERE id = %s AND room_id = %s AND user_id = %s",
        (recording_id, room_id, user_id),
    )
    if not rec:
        return {"error": "录音不存在或无权操作"}
    info = lk_stop_recording(recording_id)
    duration = info.get("duration_seconds", 0)
    size = info.get("file_size_bytes", 0)
    storage = info.get("storage_path", "")
    db.execute(
        """UPDATE room_recordings
           SET ended_at = NOW(), duration_seconds = %s,
               file_size_bytes = %s, storage_path = %s
           WHERE id = %s""",
        (int(duration), int(size), storage, recording_id),
    )
    _publish_event(LanguageRoomRecordingStopped(
        user_id=user_id, room_id=room_id, recording_id=recording_id,
        duration_seconds=duration, file_size_bytes=size,
    ))
    return {
        "recording_id": recording_id,
        "duration_seconds": int(duration),
        "file_size_bytes": int(size),
    }


# ════════════════════════════════════════════════
# LiveKit Token
# ════════════════════════════════════════════════


def issue_livekit_token(user_id: str, room_id: str, display_name: str = "") -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    from app.services.liveroom.realtime import issue_token

    db = get_db()
    room = db.fetchone("SELECT owner_id FROM language_rooms WHERE id = %s", (room_id,))
    if not room:
        return {"error": "房间不存在"}
    is_owner = (room["owner_id"] == user_id)
    token_info = issue_token(room_id, user_id, display_name, is_owner=is_owner)
    return {
        "token": token_info.token,
        "url": token_info.url,
        "identity": token_info.identity,
        "room_name": token_info.room_name,
        "expires_at": token_info.expires_at,
    }


# ════════════════════════════════════════════════
# 场景
# ════════════════════════════════════════════════


def create_scenario(user_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    scenario_id = _uid("SC")
    db.execute(
        """INSERT INTO room_scenarios
            (id, user_id, name, description, category, roles, target_goals,
             prompt_text, linked_node_ids, cross_disciplinary, is_system, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, FALSE, NOW(), NOW())""",
        (
            scenario_id, user_id, payload.get("name", ""), payload.get("description", ""),
            payload.get("category", "daily"),
            json.dumps(payload.get("roles", [])),
            json.dumps(payload.get("target_goals", [])),
            payload.get("prompt_text", ""),
            json.dumps(payload.get("linked_node_ids", [])),
            payload.get("cross_disciplinary", False),
        ),
    )
    return get_scenario(user_id, scenario_id)


def get_scenario(user_id: str, scenario_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = _row_to_dict(db.fetchone(
        "SELECT * FROM room_scenarios WHERE id = %s", (scenario_id,),
    ))
    return row or {}


def list_scenarios(
    user_id: str, category: str = "", only_system: bool = False, limit: int = 50
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sql = """SELECT * FROM room_scenarios
             WHERE (user_id = %s OR is_system = TRUE)"""
    params: list[Any] = [user_id]
    if category:
        sql += " AND category = %s"
        params.append(category)
    if only_system:
        sql += " AND is_system = TRUE"
    sql += " ORDER BY is_system DESC, created_at DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_dict(r) for r in rows]


# ════════════════════════════════════════════════
# AI 角色库
# ════════════════════════════════════════════════


def create_persona(user_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    persona_id = _uid("AP")
    db.execute(
        """INSERT INTO ai_personas
            (id, user_id, name, gender_voice, personality, target_language,
             proficiency, speech_rate, accent, behavior, correction_tendency,
             is_topic_lead, is_system, background, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, NOW(), NOW())""",
        (
            persona_id, user_id, payload.get("name", ""),
            payload.get("gender_voice", ""), payload.get("personality", ""),
            payload.get("target_language", "en"),
            payload.get("proficiency", "intermediate"),
            payload.get("speech_rate", "normal"),
            payload.get("accent", ""),
            payload.get("behavior", "balanced"),
            payload.get("correction_tendency", "none"),
            payload.get("is_topic_lead", False),
            payload.get("background", ""),
        ),
    )
    return get_persona(persona_id)


def get_persona(persona_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = _row_to_dict(db.fetchone(
        "SELECT * FROM ai_personas WHERE id = %s", (persona_id,),
    ))
    return row or {}


def list_personas(
    user_id: str, language: str = "", only_system: bool = False, limit: int = 50
) -> list[dict]:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    sql = "SELECT * FROM ai_personas WHERE (user_id = %s OR user_id IS NULL)"
    params: list[Any] = [user_id]
    if language:
        sql += " AND target_language = %s"
        params.append(language)
    if only_system:
        sql += " AND is_system = TRUE"
    sql += " ORDER BY is_system DESC, name LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_dict(r) for r in rows]


# ════════════════════════════════════════════════
# 侵入度配置
# ════════════════════════════════════════════════


def update_invasiveness(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    inv_id = f"INV_{user_id}_{room_id}"[:40]
    existing = db.fetchone(
        "SELECT id FROM ai_helper_invasiveness WHERE user_id = %s AND room_id = %s",
        (user_id, room_id),
    )
    if existing:
        db.execute(
            """UPDATE ai_helper_invasiveness
               SET invasiveness_level = %s, helper_types = %s::jsonb,
                   correction_tendency = %s, response_style = %s,
                   updated_at = NOW()
               WHERE user_id = %s AND room_id = %s""",
            (
                payload.get("invasiveness_level", "low"),
                json.dumps(payload.get("helper_types", [])),
                payload.get("correction_tendency", "none"),
                payload.get("response_style", "concise"),
                user_id, room_id,
            ),
        )
    else:
        db.execute(
            """INSERT INTO ai_helper_invasiveness
                (id, user_id, room_id, invasiveness_level, helper_types,
                 correction_tendency, response_style, show_to_room, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, FALSE, NOW(), NOW())""",
            (
                inv_id, user_id, room_id,
                payload.get("invasiveness_level", "low"),
                json.dumps(payload.get("helper_types", [])),
                payload.get("correction_tendency", "none"),
                payload.get("response_style", "concise"),
            ),
        )
    return get_invasiveness(user_id, room_id)


def get_invasiveness(user_id: str, room_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = _row_to_dict(db.fetchone(
        """SELECT * FROM ai_helper_invasiveness
           WHERE user_id = %s AND room_id = %s""",
        (user_id, room_id),
    ))
    if not row:
        return {
            "user_id": user_id,
            "room_id": room_id,
            "invasiveness_level": "low",
            "helper_types": ["grammar", "vocabulary", "sentence_pattern"],
            "correction_tendency": "none",
            "response_style": "concise",
        }
    return row


def invoke_ai_helper(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.services.liveroom.ai_persona import (
        InvasivenessConfig, invoke_helper as svc_invoke_helper,
    )
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        """SELECT * FROM ai_helper_invasiveness
           WHERE user_id = %s AND room_id = %s""",
        (user_id, room_id),
    )
    if row:
        config = InvasivenessConfig.from_row(row)
    else:
        config = InvasivenessConfig(user_id=user_id, room_id=room_id)

    context = {"recent_text": payload.get("context_text", "")}
    result = svc_invoke_helper(
        user_id, room_id, payload.get("helper_type", "grammar"),
        payload.get("query", ""), config, context,
    )
    # 更新 session 计数
    p = db.fetchone(
        "SELECT id FROM room_participants WHERE room_id = %s AND user_id = %s",
        (room_id, user_id),
    )
    if p and result.get("ok"):
        db.execute(
            """UPDATE room_sessions
               SET ai_help_requests = ai_help_requests + 1,
                   updated_at = NOW()
               WHERE participant_id = %s AND ended_at IS NULL""",
            (p["id"],),
        )
    return result


# ════════════════════════════════════════════════
# 会话回顾
# ════════════════════════════════════════════════


def get_session_review(user_id: str, session_id: str) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    sess = db.fetchone(
        """SELECT rs.*, lr.scenario_id, lr.name AS room_name
           FROM room_sessions rs
           JOIN language_rooms lr ON lr.id = rs.room_id
           WHERE rs.id = %s AND rs.user_id = %s""",
        (session_id, user_id),
    )
    if not sess:
        return {}

    sess = _row_to_dict(sess) or {}

    # 转写
    transcripts = db.fetchall(
        """SELECT * FROM room_transcripts
           WHERE room_id = %s AND user_id = %s
           ORDER BY started_at""",
        (sess["room_id"], user_id),
    )
    # 错误（从关联的 ErrorBookEntry 取 error_type；room_transcripts 仅存 is_error + error_entry_id）
    # 注：ErrorBookEntry 实际表名为 error_book，主键为 entry_id
    errors = db.fetchall(
        """SELECT rt.id, rt.room_id, rt.user_id, rt.error_entry_id,
                  rt.is_error, rt.user_note, rt.started_at,
                  eb.error_type, eb.referenced_materials_json AS linked_node_ids
           FROM room_transcripts rt
           LEFT JOIN error_book eb ON eb.entry_id = rt.error_entry_id
           WHERE rt.room_id = %s AND rt.user_id = %s AND rt.is_error = TRUE""",
        (sess["room_id"], user_id),
    )
    # 词汇
    vocabs = db.fetchall(
        """SELECT * FROM vocabulary_captures
           WHERE room_id = %s AND user_id = %s
           ORDER BY captured_at""",
        (sess["room_id"], user_id),
    )
    # 消息（ExplainCard 浮卡; Task #69: 改读 messages.metadata 走 source_module=language_room）
    try:
        msgs = db.fetchall(
            """SELECT * FROM messages
               WHERE metadata->>'source_module' = 'language_room'
                 AND metadata->>'source_ref_id' = %s
                 AND user_id = %s
                 AND is_deleted = FALSE
               ORDER BY timestamp""",
            (sess["room_id"], user_id),
        )
    except Exception:
        msgs = []

    scenario = get_scenario(user_id, sess.get("scenario_id", "") or "") if sess.get("scenario_id") else None

    return {
        "session_id": session_id,
        "room_id": sess.get("room_id", ""),
        "user_id": user_id,
        "scenario": scenario,
        "duration_seconds": sess.get("duration_seconds", 0) or 0,
        "started_at": sess.get("started_at"),
        "ended_at": sess.get("ended_at"),
        "transcript_count": sess.get("transcript_count", 0) or 0,
        "errors_marked": sess.get("errors_marked", 0) or 0,
        "cards_generated": sess.get("cards_generated", 0) or 0,
        "ai_help_requests": sess.get("ai_help_requests", 0) or 0,
        "vocabulary_captured": sess.get("vocabulary_captured", 0) or 0,
        "messages_posted": sess.get("messages_posted", 0) or 0,
        "transcripts": [_row_to_dict(t) for t in transcripts],
        "errors": [_row_to_dict(e) for e in errors],
        "vocabularies": [_row_to_dict(v) for v in vocabs],
        "messages": [_row_to_dict(m) for m in msgs],
    }


# ════════════════════════════════════════════════
# 邀请
# ════════════════════════════════════════════════


def create_invitation(user_id: str, room_id: str, payload: dict) -> dict:
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    import secrets
    db = get_db()
    room = db.fetchone("SELECT owner_id FROM language_rooms WHERE id = %s", (room_id,))
    if not room:
        return {"error": "房间不存在"}
    if room["owner_id"] != user_id:
        raise PermissionError("仅房主可以创建邀请")
    inv_id = _uid("INV")
    token = secrets.token_urlsafe(24)
    expires_hours = int(payload.get("expires_hours", 24))
    db.execute(
        """INSERT INTO room_invitations
            (id, room_id, inviter_id, invitee_id, invitation_token, expires_at, created_at)
           VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL '%s hours', NOW())""",
        (inv_id, room_id, user_id, payload.get("invitee_id", ""), token, expires_hours),
    )
    return {"id": inv_id, "invitation_token": token, "expires_hours": expires_hours}
