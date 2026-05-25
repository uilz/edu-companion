"""
对话系统 API 路由 v5.0 归一化
层级：分区 → 领域 → 专题 → 对话 → 消息
所有 CRUD 统一在 /tree/{level} 下，消息操作挂在 /tree/conversation/{conv_id}/message 和 /tree/message/{id}
"""

from __future__ import annotations

import json, logging, os, uuid, mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Response, UploadFile, File, Form, Query  # type: ignore
from fastapi.responses import FileResponse  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

from app.schemas.conversation import TextBlock
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.classifier import classifier
from app.services.active_stream import active_streams

router = APIRouter()
logger = logging.getLogger(__name__)


# ══════════════════ 请求模型 ══════════════════
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


class PersistMessageRequest(BaseModel):
    role: str
    content: str
    source: str = "user"
    metadata: dict = {}


USER_ID = "default_user"


# ══════════════════ ETag 辅助 ══════════════════
def _check_etag(request: Request) -> str | None:
    etag = storage.get_etag(USER_ID)
    if_none_match = request.headers.get("if-none-match", "")
    if if_none_match == etag:
        raise HTTPException(304)
    return etag


# ══════════════════ 辅助：递归找到最底层对话 ══════════════════
def _find_default_conversation(user_id: str, level: str, entity_id: str) -> str | None:
    data = storage.load(user_id)
    if level == "conversation":
        return entity_id
    config = tree_ops.LEVEL_CONFIG[level]
    child_coll_name = config["child_collection"]
    if not child_coll_name:
        return None
    child_coll = getattr(data, child_coll_name)
    child_key = config["child_key"]
    for child in child_coll.values():
        if getattr(child, child_key, None) == entity_id:
            next_level = tree_ops.LEVELS[tree_ops.LEVELS.index(level) + 1]
            return _find_default_conversation(user_id, next_level, child.id)
    return None


# ══════════════════ 通用树节点 CRUD ══════════════════
@router.get("/tree/{level}")
async def list_nodes(level: str, request: Request, parent_id: str = Query(None)):
    if level not in tree_ops.LEVELS:
        raise HTTPException(400, f"Invalid level: {level}")
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    coll_name = tree_ops.LEVEL_CONFIG[level]["collection"]
    collection = getattr(data, coll_name)
    nodes = [n.model_dump(mode="json") for n in collection.values()]
    if parent_id:
        parent_key = tree_ops.LEVEL_CONFIG[level]["parent_key"]
        if parent_key:
            nodes = [n for n in nodes if n.get(parent_key) == parent_id]
    return Response(
        content=json.dumps({coll_name: nodes}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


@router.post("/tree/{level}")
async def create_node(level: str, body: dict):
    if level not in tree_ops.LEVELS:
        raise HTTPException(400, f"Invalid level: {level}")
    try:
        parent_id = body.get("parent_id")
        name = body.get("name")
        emoji = body.get("emoji", "")
        if name is None:
            raise HTTPException(400, "Name is required")
        if level == "partition":
            entity = tree_ops.create_partition(USER_ID, name, subject=name, emoji=emoji)
        elif level == "domain":
            entity = tree_ops.create_domain(USER_ID, parent_id, name, emoji)
        elif level == "topic":
            entity = tree_ops.create_topic(USER_ID, parent_id, name, emoji)
        elif level == "conversation":
            entity = tree_ops.create_conversation(USER_ID, parent_id, name)
        else:
            raise HTTPException(400, "Unsupported level")
        conv_id = _find_default_conversation(USER_ID, level, entity.id)
        return {level: entity, "conversation_id": conv_id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception(f"Failed to create {level}")
        raise HTTPException(500, "Internal server error")


@router.patch("/tree/{level}/{node_id}")
async def rename_node(level: str, node_id: str, req: RenameRequest):
    if level not in tree_ops.LEVELS:
        raise HTTPException(400, f"Invalid level: {level}")
    try:
        if level == "partition":
            entity = tree_ops.rename_partition(USER_ID, node_id, req.name)
        elif level == "domain":
            entity = tree_ops.rename_domain(USER_ID, node_id, req.name)
        elif level == "topic":
            entity = tree_ops.rename_topic(USER_ID, node_id, req.name)
        elif level == "conversation":
            entity = tree_ops.rename_conversation(USER_ID, node_id, req.name)
        else:
            raise HTTPException(400)
        return {level: entity.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception(f"Failed to rename {level}")
        raise HTTPException(500, "Internal server error")


@router.delete("/tree/{level}/{node_id}")
async def delete_node(level: str, node_id: str):
    if level not in tree_ops.LEVELS:
        raise HTTPException(400, f"Invalid level: {level}")
    try:
        if level == "partition":
            tree_ops.delete_partition(USER_ID, node_id)
        elif level == "domain":
            tree_ops.delete_domain(USER_ID, node_id)
        elif level == "topic":
            tree_ops.delete_topic(USER_ID, node_id)
        elif level == "conversation":
            tree_ops.delete_conversation(USER_ID, node_id)
        else:
            raise HTTPException(400)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception(f"Failed to delete {level}")
        raise HTTPException(500, "Internal server error")


# ══════════════════ 消息操作（归一化到 /tree/conversation/{conv_id}/message 和 /tree/message/{id}）══
@router.get("/tree/conversation/{conv_id}/messages")
async def list_messages(
    conv_id: str, request: Request, limit: int = 50, offset: int = 0
):
    etag = _check_etag(request)
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = []
    for nid in conv.path[offset : offset + limit]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node.model_dump(mode="json"))
    return Response(
        content=json.dumps({"messages": messages, "total": len(conv.path)}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


@router.get("/tree/conversation/{conv_id}/blocks")
async def get_conversation_blocks(conv_id: str, limit: int = 100):
    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    blocks = []
    if conv:
        asst_ids = {
            nid
            for nid in conv.path
            if (n := data.nodes.get(nid)) and n.role == "assistant" and not n.is_deleted
        }
        blocks = [
            b.model_dump(mode="json")
            for b in data.response_blocks.values()
            if b.message_id in asst_ids
        ][:limit]
    return {"blocks": blocks}

@router.post("/tree/conversation/{conv_id}/message")
async def send_message_in_conversation(conv_id: str, req: SendMessageRequest):
    """在指定对话中发送消息（用于 WebSocket 降级或直接 HTTP）"""
    from app.services.conversation_llm import send_and_reply

    pid = req.partition_id
    if not pid:
        data = storage.load(USER_ID)
        conv = data.conversations.get(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        for topic in data.topics.values():
            if topic.id == conv.topic_id:
                domain = data.domains.get(topic.domain_id)
                if domain:
                    pid = domain.partition_id
                    break
    if not pid:
        raise HTTPException(400, "Cannot determine partition")
    outcome = await send_and_reply(USER_ID, pid, req.text, conversation_id=conv_id)
    return {
        "user_message": outcome["user_message"],
        "assistant_message": outcome["assistant_message"],
        "partition_id": pid,
        "conversation_id": conv_id,
        "response_blocks": outcome.get("response_blocks", []),
    }


@router.post("/tree/conversation/{conv_id}/switch")
async def switch_conversation(conv_id: str, topic_id: str = Query(...)):
    try:
        c = tree_ops.switch_conversation(USER_ID, topic_id, conv_id)
        return {"conversation": c.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Failed to switch conversation")
        raise HTTPException(500, "Internal server error")


@router.get("/tree/message/{message_id}")
async def get_message(message_id: str):
    data = storage.load(USER_ID)
    node = data.nodes.get(message_id)
    if not node:
        raise HTTPException(404, "Message not found")
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    versions = []
    if parent:
        all_siblings = parent.children_ids if parent else []
        versions = [
            vid
            for vid in all_siblings
            if data.nodes.get(vid) and data.nodes[vid].role == node.role
        ]
    return {
        "message": node.model_dump(mode="json"),
        "versions": versions,
        "version_count": len(versions),
    }


@router.put("/tree/message/{message_id}")
async def modify_message(message_id: str, req: ModifyMessageRequest):
    blocks = [
        TextBlock(text=block.get("text", ""))
        for block in req.content_blocks
        if block.get("type") == "text"
    ]
    node = tree_ops.modify_message(USER_ID, message_id, blocks, req.text_summary)
    data = storage.load(USER_ID)
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    all_siblings = parent.children_ids if parent else []
    version_count = sum(
        1
        for vid in all_siblings
        if data.nodes.get(vid) and data.nodes[vid].role == node.role
    )
    return {"node": node, "version_count": version_count}


@router.delete("/tree/message/{message_id}")
async def delete_message(message_id: str):
    tree_ops.delete_message(USER_ID, message_id)
    return {"ok": True}


@router.get("/tree/message/{message_id}/blocks")
async def get_message_blocks(message_id: str):
    data = storage.load(USER_ID)
    blocks = [
        b.model_dump(mode="json")
        for b in data.response_blocks.values()
        if b.message_id == message_id
    ]
    return {"blocks": blocks}


@router.get("/tree/response-block/{block_id}")
async def get_response_block(block_id: str):
    data = storage.load(USER_ID)
    block = data.response_blocks.get(block_id)
    if not block:
        raise HTTPException(404, "ResponseBlock not found")
    return {"block": block.model_dump(mode="json")}


# 持久化消息（无 LLM）
@router.get("/tree/stream/active/{conversation_id}")
async def check_stream_active(conversation_id: str):
    """检测指定对话是否正在后台流式生成"""
    active = await active_streams.is_active(conversation_id)
    return {"active": active, "conversation_id": conversation_id}


@router.post("/tree/conversation/{conv_id}/message/persist")
async def persist_message(conv_id: str, req: PersistMessageRequest):
    from app.schemas.conversation import TextBlock

    data = storage.load(USER_ID)
    conv = data.conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    partition_id = None
    for top in data.topics.values():
        if top.id == conv.topic_id:
            dom = data.domains.get(top.domain_id)
            if dom:
                partition_id = dom.partition_id
                break
    if not partition_id:
        raise HTTPException(400, "Cannot determine partition")
    node = tree_ops.add_message(
        USER_ID,
        partition_id,
        req.role,
        [TextBlock(text=req.content)],
        text_summary=req.source,
        conversation_id=conv_id,
    )
    if req.metadata:
        data = storage.load(USER_ID)
        updated_node = data.nodes.get(node.id)
        if updated_node:
            updated_node.metadata = updated_node.metadata or {}
            updated_node.metadata.update(req.metadata)
            storage.save(USER_ID, data)
    return {"id": node.id, "role": node.role, "content": req.content}


# ═══════════════════════════════════════════
# WebSocket 流式对话
# ═══════════════════════════════════════════


@router.websocket("/ws")
async def websocket_conversation(websocket: WebSocket) -> None:
    """WebSocket 流式对话端点，后台 generator 不依赖 WS 连接"""
    await websocket.accept()
    user_id = USER_ID

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "JSON解析失败"})
                )
                continue

            text = data.get("text", "").strip()
            partition_id = data.get("partition_id")
            conversation_id = data.get("conversation_id", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])

            if not text:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "消息不能为空"})
                )
                continue

            await websocket.send_text(
                json.dumps({"type": "status", "message": "正在思考...", "request_id": request_id})
            )

            from app.services.conversation_llm import send_and_reply_stream

            # 后台 generator + 队列解耦（WS 断后 generator 继续跑，持续写 DB）
            stream_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=200)

            async def _background_consume():
                """后台消费 generator，产出→队列，不依赖 WS"""
                await active_streams.mark_start(conversation_id)
                assistant_text = ""
                try:
                    async for event in send_and_reply_stream(
                        user_id, partition_id, text, conversation_id=conversation_id,
                    ):
                        await stream_queue.put(event)
                        if event.get("type") == "token":
                            assistant_text += event.get("content", "")
                    await stream_queue.put(None)  # 哨兵：流结束
                except Exception as e:
                    logger.error("后台流异常: %s", str(e))
                    await stream_queue.put({"type": "error", "message": str(e)})
                    await stream_queue.put(None)
                finally:
                    await active_streams.mark_done(conversation_id)
                    # 发布回复事件
                    if assistant_text.strip():
                        import re as _re
                        skill_ids = _re.findall(r"\[KNOWLEDGE:(\w+)\]", assistant_text)
                        contains_math = bool(_re.search(r"\$", assistant_text))
                        asyncio.ensure_future(_publish_reply_event(
                            user_id, partition_id, conversation_id,
                            assistant_text, skill_ids, contains_math,
                        ))

            bg_task = asyncio.create_task(_background_consume())

            # 从队列读取并转发到 WS
            try:
                while True:
                    event = await asyncio.wait_for(stream_queue.get(), timeout=120)
                    if event is None:
                        break  # 流正常结束
                    event["request_id"] = request_id

                    if event.get("type") == "context_switch":
                        rec_pid = event.get("partition_id", "")
                        rec_cid = event.get("conversation_id", "")
                        if rec_pid:
                            partition_id = rec_pid
                        if rec_cid:
                            conversation_id = rec_cid
                        event["partition_id"] = partition_id

                    if "partition_id" not in event or not event["partition_id"]:
                        event["partition_id"] = partition_id

                    await websocket.send_text(
                        json.dumps(event, ensure_ascii=False, default=str)
                    )
            except (WebSocketDisconnect, asyncio.TimeoutError, ConnectionError):
                # WS 断开 → generator 仍在后台跑，持续写 DB
                logger.info(f"WS 断开 [{conversation_id[:8]}], 后台流继续")
                # 不取消 bg_task，让它自然完成
            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                try:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e), "request_id": request_id})
                    )
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("对话WebSocket断开")


async def _publish_reply_event(
    user_id, partition_id, conversation_id, content, skill_ids, contains_math
):
    try:
        from app.application.di import container
        from app.shared.events import AssistantReplied

        await container.event_bus.publish(
            AssistantReplied(
                user_id=user_id,
                partition_id=partition_id,
                conversation_id=conversation_id,
                content=content,
                skill_ids=skill_ids,
                contains_math=contains_math,
            )
        )
    except Exception:
        logger.debug("事件发布失败（fire-and-forget）", exc_info=True)


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


@router.get("/tree/conversations/{conv_id}/materials")
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
            refs.append(m.model_dump())  # type: ignore[attr-defined])
    return {"materials": refs}


# ═══════════════════════════════════════════
# 专题内练习建议
# ═══════════════════════════════════════════


@router.get("/tree/conversations/{conv_id}/practice-suggestions")
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

    from app.services.practice_integrator import practice_integrator  # type: ignore

    suggestions = practice_integrator.get_suggestions(USER_ID, conv.topic_id, messages)
    return {"suggestions": suggestions}


# ═══════════════════════════════════════════
# 工作空间（v4: conversation 级）
# ═══════════════════════════════════════════

WORKSPACE_BASE = Path.home() / ".companion" / "uploads"


def _workspace_dir(user_id: str, conv_id: str) -> Path:
    return WORKSPACE_BASE / user_id / conv_id


def _file_type_dir(base: Path, file_type: str) -> Path:
    mapping = {
        "image": "images",
        "audio": "audio",
        "video": "video",
        "document": "documents",
    }
    d = base / mapping.get(file_type, "others")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _guess_file_type(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
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

    mime = (
        file.content_type
        or mimetypes.guess_type(file.filename)[0]
        or "application/octet-stream"
    )
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
        id=file_id,
        user_id=USER_ID,
        original_name=file.filename,
        storage_path=str(storage_path),
        mime_type=mime,
        file_size=len(content),
        file_type=file_type,
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
                files.append(
                    {
                        "name": f.name,
                        "relative_path": str(f.relative_to(ws_dir)),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )
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
    return FileResponse(
        path, media_type=record.mime_type, filename=record.original_name
    )
