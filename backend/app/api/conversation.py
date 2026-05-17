"""
对话系统 API 路由
提供分区、分支、消息的 CRUD 操作
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.conversation import TextBlock
from app.services.storage import storage
from app.services.tree_ops import tree_ops

router = APIRouter()


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


@router.post("/message")
async def send_message(req: SendMessageRequest):
    """发送消息：分类 → 添加到树 → 返回"""
    # 如果没指定分区，自动分类
    partition_id = req.partition_id
    if not partition_id:
        from app.services.classifier import classifier
        result = classifier.classify_partition(USER_ID, req.text)
        partition_id = result.get("partition_id")

        if not partition_id:
            # 没有现有分区，创建新分区
            partition = tree_ops.create_partition(
                USER_ID, req.text[:20], emoji="💬"
            )
            partition_id = partition.id

    # 添加消息到树
    blocks = [TextBlock(text=req.text)]
    node = tree_ops.add_message(USER_ID, partition_id, "user", blocks, req.text)

    # TODO: 用 LLM 生成助手回复
    return {
        "user_message": node,
        "partition_id": partition_id,
    }


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
