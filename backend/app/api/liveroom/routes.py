"""LanguageRoom REST API

依据 docs/modules/language-room/overview.md + ADR 0004
路由前缀: /api/liveroom

设计原则：
- 数据归属 = 参与者各自存 (决策 1)
- 房间可见性 = 邀请制 (决策 2)
- 词汇/错误/文字辅助复用 FlashCard/ErrorBookEntry/ExplainCard (不重建)
- AI 纠错倾向 = 用户主动选择 (决策 6)
- 错误标记 = 用户主动行为 = Belief 合法来源 (决策 7)
- AI 角色**不**调用 LLM 做评判
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.liveroom import service as svc
from app.api.liveroom.schemas import (
    RoomCreate, RoomUpdate, RoomResponse,
    ParticipantJoinRequest, ParticipantResponse,
    TranscriptCreateRequest, TranscriptResponse,
    VocabularyCaptureRequest, VocabularyCaptureResponse,
    ErrorMarkRequest, ErrorMarkResponse,
    MessagePostRequest, MessageResponse,
    RecordingStartRequest, RecordingResponse,
    TokenRequest, TokenResponse,
    ScenarioCreate, ScenarioResponse,
    PersonaCreate, PersonaResponse,
    InvasivenessUpdateRequest, InvasivenessResponse,
    AIHelperInvokeRequest, AIHelperInvokeResponse,
    ScenarioChangeRequest,
    SessionReviewResponse,
    InvitationCreate, InvitationResponse,
)
from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/liveroom", tags=["LanguageRoom 实时语音房间"])


# ════════════════════════════════════════════════
# 房间 CRUD
# ════════════════════════════════════════════════


@router.post("/rooms", summary="创建房间")
async def create_room(
    body: RoomCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if not body.name.strip():
        raise HTTPException(400, "房间名不能为空")
    return svc.create_room(user_id, body.model_dump())


@router.get("/rooms", summary="列出我的房间")
async def list_rooms(
    user_id: str = Depends(current_user_id),
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_rooms(user_id, status=status, limit=limit, offset=offset)


@router.get("/rooms/{room_id}", summary="房间详情")
async def get_room(
    room_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    room = svc.get_room(user_id, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    return room


@router.patch("/rooms/{room_id}", summary="更新房间（房主）")
async def update_room(
    room_id: str,
    body: RoomUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        room = svc.update_room(user_id, room_id, body.model_dump(exclude_none=True))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    if not room:
        raise HTTPException(404, "房间不存在")
    return room


@router.post("/rooms/{room_id}/end", summary="结束房间（房主）")
async def end_room(
    room_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        room = svc.end_room(user_id, room_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    if not room:
        raise HTTPException(404, "房间不存在")
    return room


# ════════════════════════════════════════════════
# 加入 / 退出
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/join", summary="加入房间")
async def join_room(
    room_id: str,
    body: ParticipantJoinRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    result = svc.join_room(user_id, room_id, body.model_dump())
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/rooms/{room_id}/leave", summary="退出房间")
async def leave_room(
    room_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.leave_room(user_id, room_id)


@router.get("/rooms/{room_id}/participants", summary="参与者列表")
async def list_participants(
    room_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_participants(user_id, room_id)


@router.post("/rooms/{room_id}/participants/{target_user_id}/mute", summary="静音（房主）")
async def mute_participant(
    room_id: str,
    target_user_id: str,
    muted: bool = Query(True),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        return svc.mute_participant(user_id, room_id, target_user_id, muted)
    except PermissionError as e:
        raise HTTPException(403, str(e))


# ════════════════════════════════════════════════
# 场景切换
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/scenario", summary="切换场景（房主）")
async def change_scenario(
    room_id: str,
    body: ScenarioChangeRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        return svc.change_scenario(user_id, room_id, body.scenario_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))


# ════════════════════════════════════════════════
# AI 角色 (同伴)
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/ai-persona", summary="邀请 AI 角色加入")
async def add_ai_persona(
    room_id: str,
    persona_id: str = Query(...),
    role_label: str = Query(""),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.add_ai_persona_to_room(user_id, room_id, persona_id, role_label)


@router.delete("/rooms/{room_id}/ai-persona/{participant_id}", summary="移除 AI 角色")
async def remove_ai_persona(
    room_id: str,
    participant_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.remove_ai_persona_from_room(user_id, room_id, participant_id)


# ════════════════════════════════════════════════
# AI 辅助者 (用户召唤)
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/ai-helper/invoke", summary="用户召唤 AI 辅助者")
async def invoke_helper(
    room_id: str,
    body: AIHelperInvokeRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.invoke_ai_helper(user_id, room_id, body.model_dump())


@router.get("/rooms/{room_id}/ai-helper/config", summary="获取辅助者配置")
async def get_helper_config(
    room_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.get_invasiveness(user_id, room_id)


@router.put("/rooms/{room_id}/ai-helper/config", summary="更新辅助者配置（用户主动）")
async def update_helper_config(
    room_id: str,
    body: InvasivenessUpdateRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.update_invasiveness(user_id, room_id, body.model_dump())


# ════════════════════════════════════════════════
# 转写
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/transcripts", summary="新增转写片段（LiveKit webhook）")
async def add_transcript(
    room_id: str,
    body: TranscriptCreateRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.add_transcript(user_id, room_id, body.model_dump())


@router.get("/rooms/{room_id}/transcripts", summary="查询转写")
async def list_transcripts(
    room_id: str,
    only_user: bool = Query(True, description="仅返回当前用户的转写 (决策 11)"),
    only_errors: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_transcripts(
        user_id, room_id,
        only_user=only_user, only_errors=only_errors, limit=limit,
    )


# ════════════════════════════════════════════════
# 词汇便签 (复用 FlashCard)
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/vocabulary", summary="词汇便签")
async def capture_vocabulary(
    room_id: str,
    body: VocabularyCaptureRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if not body.word.strip():
        raise HTTPException(400, "word 不能为空")
    return svc.capture_vocabulary(user_id, room_id, body.model_dump())


# ════════════════════════════════════════════════
# 错误标记 (复用 ErrorBookEntry)
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/error", summary="标记错误")
async def mark_error(
    room_id: str,
    body: ErrorMarkRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if not body.transcript_id:
        raise HTTPException(400, "transcript_id 必填")
    return svc.mark_error(user_id, room_id, body.model_dump())


# ════════════════════════════════════════════════
# 文字辅助区 (复用 ExplainCard)
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/messages", summary="发送文字辅助")
async def post_message(
    room_id: str,
    body: MessagePostRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.post_message(user_id, room_id, body.model_dump())


@router.get("/rooms/{room_id}/messages", summary="查询我的文字辅助")
async def list_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_messages(user_id, room_id, limit=limit)


# ════════════════════════════════════════════════
# 录音控制
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/recording/start", summary="开始录音")
async def start_recording(
    room_id: str,
    body: RecordingStartRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.start_recording(user_id, room_id, body.model_dump())


@router.post("/rooms/{room_id}/recording/stop", summary="停止录音")
async def stop_recording(
    room_id: str,
    body: dict,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    recording_id = body.get("recording_id", "")
    if not recording_id:
        raise HTTPException(400, "recording_id 必填")
    return svc.stop_recording(user_id, room_id, recording_id)


# ════════════════════════════════════════════════
# LiveKit Token
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/token", summary="LiveKit 访问令牌")
async def issue_token(
    room_id: str,
    body: TokenRequest = TokenRequest(),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.issue_livekit_token(user_id, room_id, body.display_name)


# ════════════════════════════════════════════════
# 场景管理
# ════════════════════════════════════════════════


@router.post("/scenarios", summary="创建场景")
async def create_scenario(
    body: ScenarioCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.create_scenario(user_id, body.model_dump())


@router.get("/scenarios", summary="查询场景")
async def list_scenarios(
    user_id: str = Depends(current_user_id),
    category: Optional[str] = None,
    only_system: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_scenarios(
        user_id, category=category or "", only_system=only_system, limit=limit,
    )


@router.get("/scenarios/{scenario_id}", summary="场景详情")
async def get_scenario(
    scenario_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    scenario = svc.get_scenario(user_id, scenario_id)
    if not scenario:
        raise HTTPException(404, "场景不存在")
    return scenario


# ════════════════════════════════════════════════
# AI 角色库
# ════════════════════════════════════════════════


@router.post("/ai-personas", summary="创建 AI 角色")
async def create_persona(
    body: PersonaCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.create_persona(user_id, body.model_dump())


@router.get("/ai-personas", summary="查询 AI 角色")
async def list_personas(
    user_id: str = Depends(current_user_id),
    language: Optional[str] = None,
    only_system: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.list_personas(
        user_id, language=language or "", only_system=only_system, limit=limit,
    )


@router.get("/ai-personas/{persona_id}", summary="AI 角色详情")
async def get_persona(
    persona_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    persona = svc.get_persona(persona_id)
    if not persona:
        raise HTTPException(404, "AI 角色不存在")
    return persona


# ════════════════════════════════════════════════
# 会话回顾
# ════════════════════════════════════════════════


@router.get("/rooms/{room_id}/review", summary="会话回顾（按参与者维度）")
async def get_session_review(
    room_id: str,
    user_id: str = Depends(current_user_id),
    session_id: Optional[str] = None,
):
    """获取会话回顾 (按参与者各自维度)"""
    if not user_id:
        raise HTTPException(401, "请先登录")
    from app.infrastructure.db.database import get_db
    db = get_db()
    if not session_id:
        sess = db.fetchone(
            """SELECT id FROM room_sessions
               WHERE room_id = %s AND user_id = %s
               ORDER BY started_at DESC LIMIT 1""",
            (room_id, user_id),
        )
        if not sess:
            return {}
        session_id = sess["id"]
    return svc.get_session_review(user_id, session_id)


@router.get("/sessions/{session_id}/review", summary="按 session_id 查询回顾")
async def get_session_review_by_id(
    session_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return svc.get_session_review(user_id, session_id)


# ════════════════════════════════════════════════
# 邀请
# ════════════════════════════════════════════════


@router.post("/rooms/{room_id}/invitations", summary="创建房间邀请")
async def create_invitation(
    room_id: str,
    body: InvitationCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        return svc.create_invitation(user_id, room_id, body.model_dump())
    except PermissionError as e:
        raise HTTPException(403, str(e))
