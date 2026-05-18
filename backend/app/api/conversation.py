"""
对话系统 API 路由
提供分区、分支、消息的 CRUD 操作
集成多模态响应块和后台任务
"""

from __future__ import annotations

import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.schemas.conversation import TextBlock
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.classifier import classifier

router = APIRouter()

logger = logging.getLogger(__name__)


# ── 请求模型 ──

class SendMessageRequest(BaseModel):
    text: str
    content_blocks: list[dict] = Field(default_factory=list)  # ContentBlock dicts
    partition_id: str | None = None  # 手动指定分区

class CreatePartitionRequest(BaseModel):
    name: str
    subject: str = ""
    direction: str = "subject"
    emoji: str = "💬"

class CreateBranchRequest(BaseModel):
    partition_id: str
    fork_point_id: str | None = None
    name: str = ""

class ModifyMessageRequest(BaseModel):
    content_blocks: list[dict]
    text_summary: str = ""


# MVP 单用户
USER_ID = "default_user"


# ── 分区 ──

@router.get("/partitions")
async def list_partitions():
    """列出所有分区"""
    data = storage.load(USER_ID)
    return {"partitions": list(data.partitions.values())}


@router.post("/partitions")
async def create_partition(req: CreatePartitionRequest):
    """创建新分区"""
    partition = tree_ops.create_partition(
        USER_ID, req.name, req.subject, req.direction, req.emoji
    )
    return {"partition": partition}


# ── 分支 ──

@router.get("/partitions/{partition_id}/branches")
async def list_branches(partition_id: str):
    """列出分区的所有分支"""
    data = storage.load(USER_ID)
    branches = [b for b in data.branches.values() if b.partition_id == partition_id]
    return {"branches": branches}


@router.post("/branches")
async def create_branch(req: CreateBranchRequest):
    """创建新分支"""
    branch = tree_ops.create_branch(
        USER_ID, req.partition_id, req.fork_point_id, req.name
    )
    return {"branch": branch}


@router.post("/branches/{branch_id}/switch")
async def switch_branch(branch_id: str, partition_id: str):
    """切换活跃分支"""
    branch = tree_ops.switch_branch(USER_ID, partition_id, branch_id)
    return {"branch": branch}


# ── 消息 ──

@router.get("/branches/{branch_id}/messages")
async def list_messages(branch_id: str, limit: int = 50, offset: int = 0):
    """列出分支中的消息"""
    data = storage.load(USER_ID)
    branch = data.branches.get(branch_id)
    if not branch:
        raise HTTPException(404, "Branch not found")

    messages = []
    for nid in branch.path[offset : offset + limit]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node)

    return {"messages": messages, "total": len(branch.path)}


@router.get("/partitions/{partition_id}/messages")
async def list_partition_messages(partition_id: str, limit: int = 50, offset: int = 0):
    """列出分区所有分支的消息，包含 response_blocks"""
    data = storage.load(USER_ID)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise HTTPException(404, "Partition not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        return {"messages": [], "total": 0, "response_blocks": []}

    messages = []
    for nid in branch.path[offset : offset + limit]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node)

    # 获取关联的 response_blocks
    response_blocks = []
    for block in data.response_blocks.values():
        if block.partition_id == partition_id:
            response_blocks.append(block)

    return {
        "messages": messages,
        "total": len(branch.path),
        "response_blocks": response_blocks,
    }


@router.post("/message")
async def send_message(req: SendMessageRequest):
    """发送消息：分类 → 存储 → LLM回复 → 存储回复（含工具调用）"""
    from app.services.conversation_llm import send_and_reply

    # 如果没指定分区，自动分类
    partition_id = req.partition_id
    if not partition_id:
        result = classifier.classify_partition(USER_ID, req.text)
        partition_id = result.get("partition_id")

        if not partition_id:
            # 没有现有分区，创建新分区
            partition = tree_ops.create_partition(
                USER_ID, req.text[:20], emoji="💬"
            )
            partition_id = partition.id

    # 发送消息并获取 LLM 回复（含工具调用）
    outcome = await send_and_reply(USER_ID, partition_id, req.text)

    return {
        "user_message": outcome["user_message"],
        "assistant_message": outcome["assistant_message"],
        "partition_id": partition_id,
        "response_blocks": outcome.get("response_blocks", []),
    }


class EmotionTrendRequest(BaseModel):
    window_hours: int = Field(default=72, description="时间窗口（小时）")


@router.get("/emotion/trend")
async def get_emotion_trend(window_hours: int = 72):
    """获取学生情绪趋势分析"""
    from app.services.emotion_analyzer import emotion_analyzer
    trend = await emotion_analyzer.analyze_trend(USER_ID, window_hours=window_hours)
    return trend.to_dict()


@router.websocket("/ws")
async def websocket_conversation(websocket: WebSocket) -> None:
    """
    WebSocket 对话端点（流式）。
    前端发送: {"text": "...", "partition_id": "...", "conversation_id": "..."}
    后端返回: {"type": "token|done|error|status", ...}
    """
    await websocket.accept()
    user_id = USER_ID
    conversation_id = str(uuid.uuid4())[:8]

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
            request_id = data.get("request_id", str(uuid.uuid4())[:8])

            if not text:
                await websocket.send_text(json.dumps({"type": "error", "message": "消息不能为空"}))
                continue

            # 发送状态
            await websocket.send_text(json.dumps({
                "type": "status", "message": "正在思考...", "request_id": request_id
            }))

            try:
                # 分类（如果没指定分区）
                if not partition_id:
                    cls_result = classifier.classify_partition(user_id, text)
                    partition_id = cls_result.get("partition_id")
                    if not partition_id:
                        partition = tree_ops.create_partition(user_id, text[:20], emoji="💬")
                        partition_id = partition.id

                # 流式生成回复
                from app.services.conversation_llm import send_and_reply_stream
                async for event in send_and_reply_stream(user_id, partition_id, text):
                    event["request_id"] = request_id
                    event["partition_id"] = partition_id
                    await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))

            except Exception as e:
                logger.error("消息处理失败: %s", str(e), exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error", "message": str(e), "request_id": request_id
                }))

    except WebSocketDisconnect:
        logger.info("对话WebSocket断开")


# ── 后台任务端点 ──

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """获取后台任务状态"""
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
    """获取任务关联的 ResponseBlock（用于轮询）"""
    from app.services.background_jobs import job_manager

    job = job_manager.get_job(USER_ID, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    data = storage.load(USER_ID)
    block = data.response_blocks.get(job.block_id)
    if not block:
        raise HTTPException(404, "ResponseBlock not found")

    return {
        "job": job,
        "block": block,
    }


# ── Response Blocks ──

@router.get("/response-blocks/{block_id}")
async def get_response_block(block_id: str):
    """获取单个 ResponseBlock"""
    data = storage.load(USER_ID)
    block = data.response_blocks.get(block_id)
    if not block:
        raise HTTPException(404, "ResponseBlock not found")
    return {"block": block}


@router.put("/messages/{message_id}")
async def modify_message(message_id: str, req: ModifyMessageRequest):
    """修改消息（创建新分支）"""
    blocks = [
        TextBlock(text=block.get("text", ""))
        for block in req.content_blocks
        if block.get("type") == "text"
    ]
    node = tree_ops.modify_message(USER_ID, message_id, blocks, req.text_summary)
    return {"node": node}


@router.delete("/messages/{message_id}")
async def delete_message(message_id: str):
    """软删除消息"""
    tree_ops.delete_message(USER_ID, message_id)
    return {"ok": True}
