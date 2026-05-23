"""
对话系统 API 路由 v4.0
层级：分区 → 领域 → 专题 → 对话 → 消息
集成多模态响应块和后台任务
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Response, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.schemas.conversation import TextBlock
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.classifier import classifier

import mimetypes

router = APIRouter()
logger = logging.getLogger(__name__)


# ── 请求模型 ──

class SendMessageRequest(BaseModel):
    text: str
    content_blocks: list[dict] = Field(default_factory=list)
    partition_id: str | None = None

class CreatePartitionRequest(BaseModel):
    name: str
    subject: str = ""
    direction: str = "subject"
    emoji: str = "💬"

class CreateDomainRequest(BaseModel):
    partition_id: str
    name: str
    emoji: str = "📚"

class CreateTopicRequest(BaseModel):
    domain_id: str
    name: str
    emoji: str = "📝"

class CreateConversationRequest(BaseModel):
    topic_id: str
    name: str = ""

class RenameRequest(BaseModel):
    name: str

class ModifyMessageRequest(BaseModel):
    content_blocks: list[dict]
    text_summary: str = ""

class EmotionTrendRequest(BaseModel):
    window_hours: int = Field(default=72, description="时间窗口（小时）")


# MVP 单用户
USER_ID = "default_user"


# ── ETag helper ──
def _check_etag(request: Request) -> str | None:
    etag = storage.get_etag(USER_ID)
    if_none_match = request.headers.get("if-none-match", "")
    if if_none_match == etag:
        raise HTTPException(304)
    return etag


# ═══════════════════════════════════════════
# 分区
# ═══════════════════════════════════════════

@router.get("/partitions")
async def list_partitions(request: Request):
    """列出所有分区"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    return Response(
        content=json.dumps({"partitions": [p.model_dump(mode="json") for p in data.partitions.values()]}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )

@router.post("/partitions")
async def create_partition(req: CreatePartitionRequest):
    """创建新分区"""
    partition = tree_ops.create_partition(USER_ID, req.name, req.subject, req.direction, req.emoji)
    return {"partition": partition}

@router.patch("/partitions/{partition_id}")
async def rename_partition(partition_id: str, req: RenameRequest):
    """重命名分区"""
    try:
        p = tree_ops.rename_partition(USER_ID, partition_id, req.name)
        return {"partition": p.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/partitions/{partition_id}")
async def delete_partition(partition_id: str):
    """删除分区及其下属所有领域/专题/对话"""
    try:
        tree_ops.delete_partition(USER_ID, partition_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ═══════════════════════════════════════════
# 领域
# ═══════════════════════════════════════════

@router.get("/partitions/{partition_id}/domains")
async def list_domains(partition_id: str, request: Request):
    """列出指定分区下的所有领域"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    domains = [
        d.model_dump(mode="json")
        for d in data.domains.values()
        if d.partition_id == partition_id
    ]
    return Response(
        content=json.dumps({"domains": domains}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )

@router.post("/domains")
async def create_domain(req: CreateDomainRequest):
    """在指定分区下创建新领域"""
    try:
        d = tree_ops.create_domain(USER_ID, req.partition_id, req.name, req.emoji)
        return {"domain": d.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.patch("/domains/{domain_id}")
async def rename_domain(domain_id: str, req: RenameRequest):
    """重命名领域"""
    try:
        d = tree_ops.rename_domain(USER_ID, domain_id, req.name)
        return {"domain": d.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str):
    """删除领域及其下属所有专题/对话"""
    try:
        tree_ops.delete_domain(USER_ID, domain_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ═══════════════════════════════════════════
# 专题
# ═══════════════════════════════════════════

@router.get("/domains/{domain_id}/topics")
async def list_topics(domain_id: str, request: Request):
    """列出指定领域下的所有专题"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    topics = [
        t.model_dump(mode="json")
        for t in data.topics.values()
        if t.domain_id == domain_id
    ]
    return Response(
        content=json.dumps({"topics": topics}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )

@router.post("/topics")
async def create_topic(req: CreateTopicRequest):
    """在指定领域下创建新专题"""
    try:
        t = tree_ops.create_topic(USER_ID, req.domain_id, req.name, req.emoji)
        return {"topic": t.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.patch("/topics/{topic_id}")
async def rename_topic(topic_id: str, req: RenameRequest):
    """重命名专题"""
    try:
        t = tree_ops.rename_topic(USER_ID, topic_id, req.name)
        return {"topic": t.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: str):
    """删除专题及其下属所有对话和消息"""
    try:
        tree_ops.delete_topic(USER_ID, topic_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ═══════════════════════════════════════════
# 对话
# ═══════════════════════════════════════════

@router.get("/topics/{topic_id}/conversations")
async def list_conversations(topic_id: str, request: Request):
    """列出指定专题下的所有未归档对话"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    if topic_id not in data.topics:
        raise HTTPException(404, "Topic not found")
    convs = [
        c.model_dump(mode="json")
        for c in data.conversations.values()
        if c.topic_id == topic_id and not c.is_archived
    ]
    return Response(
        content=json.dumps({"conversations": convs}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )

@router.post("/conversations")
async def create_conversation(req: CreateConversationRequest):
    """在专题下创建新对话"""
    try:
        c = tree_ops.create_conversation(USER_ID, req.topic_id, req.name)
        return {"conversation": c.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.patch("/conversations/{conv_id}")
async def rename_conversation(conv_id: str, req: RenameRequest):
    """重命名对话"""
    try:
        c = tree_ops.rename_conversation(USER_ID, conv_id, req.name)
        return {"conversation": c.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除对话（软删消息）"""
    try:
        tree_ops.delete_conversation(USER_ID, conv_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/conversations/{conv_id}/switch")
async def switch_conversation(conv_id: str, topic_id: str):
    """切换专题的活跃对话"""
    try:
        c = tree_ops.switch_conversation(USER_ID, topic_id, conv_id)
        return {"conversation": c.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ═══════════════════════════════════════════
# 消息（对话内）
# ═══════════════════════════════════════════

@router.get("/conversations/{conv_id}/messages")
async def list_messages(conv_id: str, request: Request, limit: int = 50, offset: int = 0):
    """列出对话中的消息列表（分页，不包含已删除消息）"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages = [
        data.nodes.get(nid).model_dump(mode="json")
        for nid in conv.path[offset: offset + limit]
        if data.nodes.get(nid) and not data.nodes.get(nid).is_deleted
    ]
    return Response(
        content=json.dumps({"messages": messages, "total": len(conv.path)}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=3"},
    )

@router.get("/partitions/{partition_id}/messages")
async def list_partition_messages(partition_id: str, request: Request, limit: int = 50, offset: int = 0):
    """列出分区活跃对话的消息，包含 response_blocks"""
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    if partition_id not in data.partitions:
        raise HTTPException(404, "Partition not found")

    # 找到活跃对话
    conv = None
    for topic in data.topics.values():
        domain = data.domains.get(topic.domain_id)
        if domain and domain.partition_id == partition_id:
            cid = topic.active_conversation_id
            if cid and cid in data.conversations:
                conv = data.conversations[cid]
                break

    if not conv:
        return Response(
            content=json.dumps({"messages": [], "total": 0, "response_blocks": []}),
            media_type="application/json",
            headers={"ETag": etag, "Cache-Control": "private, max-age=3"},
        )

    messages = [
        data.nodes.get(nid).model_dump(mode="json")
        for nid in conv.path[offset: offset + limit]
        if data.nodes.get(nid) and not data.nodes.get(nid).is_deleted
    ]
    response_blocks = [
        b.model_dump(mode="json")
        for b in data.response_blocks.values()
        if b.partition_id == partition_id
    ]
    return Response(
        content=json.dumps({"messages": messages, "total": len(conv.path), "response_blocks": response_blocks}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "private, max-age=3"},
    )


# ═══════════════════════════════════════════
# 发送消息
# ═══════════════════════════════════════════

@router.post("/message")
async def send_message(req: SendMessageRequest):
    """发送消息（自动分类路由 + LLM 回复）"""
    from app.services.conversation_llm import send_and_reply

    # v4: auto_resolve handles classification + routing
    route = classifier.auto_resolve(
        USER_ID, req.text,
        current_partition_id=req.partition_id or "",
    )
    partition_id = route["partition_id"]

    outcome = await send_and_reply(USER_ID, partition_id, req.text)
    return {
        "user_message": outcome["user_message"],
        "assistant_message": outcome["assistant_message"],
        "partition_id": partition_id,
        "conversation_id": route.get("conversation_id", ""),
        "response_blocks": outcome.get("response_blocks", []),
        "switch_recommendation": route.get("switch_detail") if route.get("should_recommend_switch") else None,
    }


# ═══════════════════════════════════════════
# WebSocket 流式对话
# ═══════════════════════════════════════════

@router.websocket("/ws")
async def websocket_conversation(websocket: WebSocket) -> None:
    """WebSocket 流式对话端点，支持逐 token 流式输出和上下文切换事件"""
    await websocket.accept()
    user_id = USER_ID

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "JSON解析失败"}))
                continue

            text = data.get("text", "").strip()
            partition_id = data.get("partition_id")
            conversation_id = data.get("conversation_id", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])

            if not text:
                await websocket.send_text(json.dumps({"type": "error", "message": "消息不能为空"}))
                continue

            await websocket.send_text(json.dumps({
                "type": "status", "message": "正在思考...", "request_id": request_id
            }))

            try:
                from app.services.conversation_llm import send_and_reply_stream
                assistant_content = ""
                async for event in send_and_reply_stream(
                    user_id, partition_id, text,
                    conversation_id=conversation_id,
                ):
                    event["request_id"] = request_id

                    # context_switch 事件：更新 partition_id 为推荐值
                    if event.get("type") == "context_switch":
                        rec_pid = event.get("partition_id", "")
                        rec_cid = event.get("conversation_id", "")
                        if rec_pid:
                            partition_id = rec_pid
                        if rec_cid:
                            conversation_id = rec_cid
                        event["partition_id"] = partition_id

                    # 确保事件带 partition_id
                    if "partition_id" not in event or not event["partition_id"]:
                        event["partition_id"] = partition_id

                    await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))
                    if event.get("type") == "token":
                        assistant_content += event.get("content", "")

                if assistant_content.strip():
                    import asyncio as _asyncio
                    import re as _re
                    skill_ids = _re.findall(r'\[KNOWLEDGE:(\w+)\]', assistant_content)
                    contains_math = bool(_re.search(r'\$', assistant_content))
                    _asyncio.ensure_future(
                        _publish_reply_event(user_id, partition_id, conversation_id,
                            assistant_content, skill_ids, contains_math)
                    )

            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error", "message": str(e), "request_id": request_id
                }))

    except WebSocketDisconnect:
        logger.info("对话WebSocket断开")


async def _publish_reply_event(user_id, partition_id, conversation_id, content, skill_ids, contains_math):
    try:
        from app.application.di import container
        from app.shared.events import AssistantReplied
        await container.event_bus.publish(AssistantReplied(
            user_id=user_id,
            partition_id=partition_id,
            conversation_id=conversation_id,
            content=content,
            skill_ids=skill_ids,
            contains_math=contains_math,
        ))
    except Exception:
        logger.debug("事件发布失败（fire-and-forget）", exc_info=True)


# ═══════════════════════════════════════════
# 消息持久化 & 编辑
# ═══════════════════════════════════════════

class PersistMessageRequest(BaseModel):
    conversation_id: str
    role: str
    content: str
    source: str = "user"
    metadata: dict = {}

@router.post("/messages/persist")
async def persist_message(req: PersistMessageRequest):
    """持久化一条消息（不触发 LLM 回复）"""
    return _add_message_to_tree(req.conversation_id, req.role, req.content, req.source, req.metadata)

def _add_message_to_tree(conversation_id: str, role: str, content: str, source: str, metadata: dict = None) -> dict:
    """在对话树中插入一条消息并返回"""
    from app.schemas.conversation import TextBlock
    data = storage.load(USER_ID)
    conv = data.conversations.get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # 从 topic → domain → partition 反向查找 partition_id
    partition_id = None
    for top in data.topics.values():
        if top.id == conv.topic_id:
            dom = data.domains.get(top.domain_id)
            if dom:
                partition_id = dom.partition_id
                break

    if not partition_id:
        raise HTTPException(400, "Cannot determine partition for this conversation")

    blocks = [TextBlock(text=content)]
    node = tree_ops.add_message(
        USER_ID, partition_id, role, blocks,
        text_summary=source, conversation_id=conversation_id,
    )

    if metadata:
        node.metadata = node.metadata or {}
        node.metadata.update(metadata)
        storage.save(USER_ID, data)

    return {"id": node.id, "role": node.role, "content": content}


@router.put("/messages/{message_id}")
async def modify_message(message_id: str, req: ModifyMessageRequest):
    """编辑消息 — v4: 在当前对话内创建新版本，不另开对话"""
    blocks = [
        TextBlock(text=block.get("text", ""))
        for block in req.content_blocks
        if block.get("type") == "text"
    ]
    node = tree_ops.modify_message(USER_ID, message_id, blocks, req.text_summary)
    # Count same-parent+role versions for frontend version counter
    data = storage.load(USER_ID)
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    all_siblings = parent.children_ids if parent else []
    version_count = sum(
        1 for vid in all_siblings
        if data.nodes.get(vid) and data.nodes[vid].role == node.role
    )
    return {"node": node, "version_count": version_count}

@router.delete("/messages/{message_id}")
async def delete_message(message_id: str):
    """软删除消息及其子树"""
    tree_ops.delete_message(USER_ID, message_id)
    return {"ok": True}


# ═══════════════════════════════════════════
# Response Blocks
# ═══════════════════════════════════════════

@router.get("/messages/{message_id}/blocks")
async def get_message_blocks(message_id: str):
    """获取消息关联的所有响应块"""
    data = storage.load(USER_ID)
    blocks = [b.model_dump(mode="json") for b in data.response_blocks.values() if b.message_id == message_id]
    return {"blocks": blocks}

@router.get("/conversations/{conv_id}/blocks")
async def get_conversation_blocks(conv_id: str, limit: int = 100):
    blocks = []
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if conv:
        asst_ids = {nid for nid in conv.path
                    if (n := data.nodes.get(nid)) and n.role == "assistant" and not n.is_deleted}
        blocks = [b.model_dump(mode="json")
                  for b in data.response_blocks.values()
                  if b.message_id in asst_ids][:limit]
    return {"blocks": blocks}

@router.get("/messages/{message_id}")
async def get_message(message_id: str):
    """获取单条消息（用于版本切换）"""
    data = storage.load(USER_ID)
    node = data.nodes.get(message_id)
    if not node:
        raise HTTPException(404, "Message not found")
    # 从父节点的 children_ids 中筛选同角色的版本（排除AI应答等异角色节点）
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    all_siblings = parent.children_ids if parent else []
    versions = [
        vid for vid in all_siblings
        if data.nodes.get(vid) and data.nodes[vid].role == node.role
    ]
    return {
        "message": node.model_dump(mode="json"),
        "versions": versions,
        "version_count": len(versions),
    }

@router.get("/response-blocks/{block_id}")
async def get_response_block(block_id: str):
    """获取单个响应块"""
    data = storage.load(USER_ID)
    block = data.response_blocks.get(block_id)
    if not block:
        raise HTTPException(404, "ResponseBlock not found")
    return {"block": block}


# ═══════════════════════════════════════════
# 情绪
# ═══════════════════════════════════════════

@router.get("/emotion/trend")
async def get_emotion_trend(window_hours: int = 72):
    """获取用户情绪趋势分析"""
    from app.services.emotion_analyzer import emotion_analyzer
    trend = await emotion_analyzer.analyze_trend(USER_ID, window_hours=window_hours)
    return trend.to_dict()


# ═══════════════════════════════════════════
# 后台任务
# ═══════════════════════════════════════════

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """查询后台任务状态"""
    from app.services.background_jobs import job_manager
    job = job_manager.get_job(USER_ID, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"job": job}

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """取消后台任务"""
    from app.services.background_jobs import job_manager
    success = await job_manager.cancel(USER_ID, job_id)
    if not success:
        raise HTTPException(404, "Job not found or already completed")
    return {"ok": True, "job_id": job_id}

@router.get("/jobs/{job_id}/block")
async def get_job_response_block(job_id: str):
    """获取任务关联的响应块"""
    from app.services.background_jobs import job_manager
    job = job_manager.get_job(USER_ID, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    data = storage.load(USER_ID)
    block = data.response_blocks.get(job.block_id)
    if not block:
        raise HTTPException(404, "ResponseBlock not found")
    return {"job": job, "block": block}


# ═══════════════════════════════════════════
# 专题内资料
# ═══════════════════════════════════════════

@router.get("/conversations/{conv_id}/materials")
async def list_conversation_material_refs(conv_id: str):
    """列出对话关联的学习资料"""
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    from app.services.materials_meta import materials_meta
    refs = []
    for mid in conv.material_refs:
        m = materials_meta.get(mid)
        if m:
            refs.append(m.model_dump())
    return {"materials": refs}


# ═══════════════════════════════════════════
# 专题内练习建议
# ═══════════════════════════════════════════

@router.get("/conversations/{conv_id}/practice-suggestions")
async def get_practice_suggestions(conv_id: str):
    """获取基于对话上下文的练习建议"""
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages = []
    for nid in conv.path[-10:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node)

    from app.services.practice_integrator import practice_integrator
    suggestions = practice_integrator.get_suggestions(USER_ID, conv.topic_id, messages)
    return {"suggestions": suggestions}


# ═══════════════════════════════════════════
# 工作空间（v4: conversation 级）
# ═══════════════════════════════════════════

WORKSPACE_BASE = Path.home() / ".companion" / "uploads"

def _workspace_dir(user_id: str, conv_id: str) -> Path:
    return WORKSPACE_BASE / user_id / conv_id

def _file_type_dir(base: Path, file_type: str) -> Path:
    mapping = {"image": "images", "audio": "audio", "video": "video", "document": "documents"}
    d = base / mapping.get(file_type, "others")
    d.mkdir(parents=True, exist_ok=True)
    return d

def _guess_file_type(mime: str) -> str:
    if mime.startswith("image/"): return "image"
    if mime.startswith("audio/"): return "audio"
    if mime.startswith("video/"): return "video"
    return "document"

@router.post("/workspace/upload")
async def upload_workspace_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
):
    """上传文件到对话工作空间"""
    if not file.filename:
        raise HTTPException(400, "No file selected")

    data = storage.load(USER_ID)
    conv = data.conversations.get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    file_type = _guess_file_type(mime)
    ws_dir = _workspace_dir(USER_ID, conversation_id)
    type_dir = _file_type_dir(ws_dir, file_type)

    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    storage_name = f"{file_id}{ext}"
    storage_path = type_dir / storage_name

    content = await file.read()
    storage_path.write_bytes(content)

    from app.schemas.conversation import FileRecord
    record = FileRecord(
        id=file_id, user_id=USER_ID, original_name=file.filename,
        storage_path=str(storage_path), mime_type=mime,
        file_size=len(content), file_type=file_type,
    )
    data.files[file_id] = record
    storage.save(USER_ID, data)

    return {"file_id": file_id, "original_name": file.filename, "file_type": file_type}

@router.get("/workspace/files")
async def list_workspace_files(conversation_id: str = Query(...)):
    """列出工作空间中的文件"""
    data = storage.load(USER_ID)
    conv = data.conversations.get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    ws_dir = _workspace_dir(USER_ID, conversation_id)
    files = []
    if ws_dir.exists():
        for f in ws_dir.rglob("*"):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "relative_path": str(f.relative_to(ws_dir)),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
    return {"files": files}

@router.delete("/workspace/files/{file_id}")
async def delete_workspace_file(file_id: str, conversation_id: str = Query(...)):
    """删除工作空间中的文件"""
    data = storage.load(USER_ID)
    record = data.files.get(file_id)
    if not record:
        raise HTTPException(404, "File not found")
    path = Path(record.storage_path)
    if path.exists():
        path.unlink()
    data.files.pop(file_id, None)
    storage.save(USER_ID, data)
    return {"ok": True}

@router.get("/workspace/download/{file_id}")
async def download_workspace_file(file_id: str):
    """下载工作空间中的文件"""
    data = storage.load(USER_ID)
    record = data.files.get(file_id)
    if not record:
        raise HTTPException(404, "File not found")
    path = Path(record.storage_path)
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    return FileResponse(path, media_type=record.mime_type, filename=record.original_name)
