"""
对话系统 REST API 路由 v5.0 归一化
层级：分区 → 领域 → 专题 → 对话 → 消息
所有 CRUD 统一在 /tree/{level} 下，消息操作挂在 /tree/conversation/{conv_id}/message 和 /tree/message/{id}

从 conversation.py 拆分：仅 REST 端点 + 请求模型 + 辅助函数
"""

from __future__ import annotations

import json
import logging
import uuid
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File, Form, Query  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

from shared.constants import DEFAULT_USER_ID
from app.schemas.conversation import TextBlock
from app.services.storage import storage
from app.services.tree_ops import tree_ops

router = APIRouter()
logger = logging.getLogger(__name__)


# ══════════════════ 请求模型 ══════════════════
class SendMessageRequest(BaseModel):
    text: str
    content_blocks: list[dict] = Field(default_factory=list)
    partition_id: str | None = None
    pending_quote: dict | None = None  # 引用数据


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


USER_ID = DEFAULT_USER_ID


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
    # 对话按 last_active_at 降序排列
    if level == "conversation":
        nodes.sort(key=lambda n: n.get("last_active_at", 0) or 0, reverse=True)
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
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
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
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception(f"Failed to rename {level}")
        raise HTTPException(500, "Internal server error")


@router.delete("/tree/{level}/{node_id}")
async def delete_node(level: str, node_id: str):
    if level == "message":
        tree_ops.delete_message(USER_ID, node_id)
        return {"ok": True}
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
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception(f"Failed to delete {level}")
        raise HTTPException(500, "Internal server error")


def _merge_cognitive_ids(messages: list[dict], msg_ids: list[str]) -> None:
    """从 messages 表合并 cognitive_node_ids 到树节点 json 中"""
    from app.cognitive.storage import get_db

    try:
        db = get_db()
        rows = db.fetchall(
            "SELECT id, cognitive_node_ids FROM messages WHERE id = ANY(%s)",
            (msg_ids,),
        )
        cog_map: dict[str, list[str]] = {}
        for r in rows:
            cog_map[r["id"]] = r.get("cognitive_node_ids") or []
        for msg in messages:
            mid = msg.get("id", "")
            if mid in cog_map and cog_map[mid]:
                msg["cognitive_node_ids"] = cog_map[mid]
    except Exception:
        logger.warning("merge_cognitive_ids failed", exc_info=True)


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
    msg_ids = []
    for nid in conv.path[offset : offset + limit]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted and node.conversation_id == conv_id:
            d = node.model_dump(mode="json")
            msg_ids.append(nid)
            messages.append(d)
    # 合并 cognitive_node_ids
    if msg_ids:
        _merge_cognitive_ids(messages, msg_ids)
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
    outcome = await send_and_reply(USER_ID, pid, req.text, conversation_id=conv_id, pending_quote=req.pending_quote)
    return {
        "user_message": outcome["user_message"],
        "assistant_message": outcome["assistant_message"],
        "partition_id": pid,
        "conversation_id": conv_id,
        "response_blocks": outcome.get("response_blocks", []),
    }


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


@router.post("/tree/message/{message_id}/switch-version")
async def switch_version(message_id: str, req: dict | None = None):
    if req is None:
        req = {}
    """切换到指定版本：从目标版本 DFS 重建 conv.path。
    请求体: { "direction": "prev" | "next" } 或 { "target_index": int }
    """
    direction = req.get("direction")
    target_index = req.get("target_index")

    data = storage.load(USER_ID)
    node = data.nodes.get(message_id)
    if not node:
        raise HTTPException(404, "Message not found")

    conv = data.conversations.get(node.conversation_id)
    if not conv:
        raise HTTPException(400, "No conversation found")

    # 1) 在 conv.path 中找到当前活跃的版本节点（同父同角色）
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    if not parent:
        raise HTTPException(400, "No parent found")

    # 当前活跃版本 = path 中与 node 同父同角色的那个
    cur_version_id = None
    version_point_idx = None
    for i, nid in enumerate(conv.path):
        n = data.nodes.get(nid)
        if n and n.parent_id == node.parent_id and n.role == node.role:
            cur_version_id = nid
            version_point_idx = i
            break

    if not cur_version_id:
        # fallback: 用 message_id 自身
        cur_version_id = message_id
        version_point_idx = 0

    # 2) 找到所有同父同角色版本（兄弟节点）
    versions = [
        vid for vid in parent.children_ids
        if (n := data.nodes.get(vid)) and n.role == node.role and not n.is_deleted
    ]
    if len(versions) <= 1:
        return {"messages": [], "switched_to": message_id, "index": 1, "total": 1}

    cur_idx = versions.index(cur_version_id) if cur_version_id in versions else -1
    if cur_idx == -1:
        raise HTTPException(400, "Cannot locate current version")

    # 3) 确定目标版本
    if target_index is not None:
        new_idx = max(0, min(target_index, len(versions) - 1))
    elif direction == "prev":
        new_idx = (cur_idx - 1 + len(versions)) % len(versions)
    elif direction == "next":
        new_idx = (cur_idx + 1) % len(versions)
    else:
        raise HTTPException(400, "Provide direction or target_index")

    target_id = versions[new_idx]

    # 4) 重建 conv.path = prefix + DFS(目标版本)
    prefix = conv.path[:version_point_idx]
    conv_id = conv.id  # 限制只收集同一会话的节点，防止子支混入

    def dfs(nid: str, acc: list):
        nd = data.nodes.get(nid)
        if not nd or nd.is_deleted:
            return
        # 只收集属于当前会话的节点，跳过子支（属于其他会话）
        if nd.conversation_id != conv_id:
            return
        acc.append(nid)
        for cid in nd.children_ids:
            dfs(cid, acc)

    new_path = list(prefix)
    dfs(target_id, new_path)

    # 5) 保存并返回
    conv.path = new_path
    conv.summary_dirty = True
    storage.save(USER_ID, data)

    messages = []
    for nid in new_path:
        n = data.nodes.get(nid)
        if n and not n.is_deleted:
            messages.append(n.model_dump(mode="json"))

    return {
        "messages": messages,
        "switched_to": target_id,
        "index": new_idx + 1,
        "total": len(versions),
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


@router.post("/tree/message/{message_id}/reply")
async def reply_to_edited_message(message_id: str):
    """编辑消息后重新生成 AI 回复"""
    from app.services.conversation_llm import generate_reply_with_tools, _p0_post_message_hooks
    from app.schemas.conversation import TextBlock

    data = storage.load(USER_ID)
    node = data.nodes.get(message_id)
    if not node or node.role != "user":
        raise HTTPException(400, "Can only reply to user messages")

    conv_id = node.conversation_id
    conv = data.conversations.get(conv_id) if conv_id else None
    if not conv:
        raise HTTPException(404, "Conversation not found")

    pid = node.partition_id
    if not pid:
        for topic in data.topics.values():
            if topic.id == conv.topic_id:
                domain = data.domains.get(topic.domain_id)
                if domain:
                    pid = domain.partition_id
                    break

    # 获取编辑后的消息文本
    text = ""
    for b in (node.content_blocks or []):
        if isinstance(b, dict) and b.get("type") == "text":
            text = b.get("text", "")
            break
        elif hasattr(b, "text"):
            text = b.text
            break
    if not text:
        raise HTTPException(400, "Message has no text content")

    # 用 generate_reply_with_tools 生成回复（含工具调用）
    response_blocks = await generate_reply_with_tools(USER_ID, pid, text)

    # 提取文本
    text_parts = []
    for block in response_blocks:
        if block.type == "text":
            text_parts.append(block.content.get("text", ""))
    reply_text = "\n\n".join(text_parts) if text_parts else "（已收到你的修改）"

    # 存助手消息（会自动追加到 conv.path）
    assistant_node = tree_ops.add_message(
        USER_ID, pid, "assistant",
        [TextBlock(text=reply_text)], reply_text,
        conversation_id=conv_id,
    )

    # 回填 message_id
    data = storage.load(USER_ID)
    for block in response_blocks:
        if block.id in data.response_blocks:
            data.response_blocks[block.id].message_id = assistant_node.id
    storage.save(USER_ID, data)

    return {
        "assistant_message": assistant_node.model_dump(mode="json"),
        "conversation_id": conv_id,
    }



@router.get("/tree/stream/active/{conversation_id}")
async def check_stream_active(conversation_id: str):
    """检测指定对话是否正在后台流式生成"""
    from app.services.active_stream import active_streams
    active = await active_streams.is_active(conversation_id)
    return {"active": active, "conversation_id": conversation_id}


# ═══════════════════════════════════════════
# 情绪
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
# 后台任务
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
# 专题内资料
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
# 专题内练习建议
# ═══════════════════════════════════════════


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


# ══════════════════ 子支操作 ══════════════════

class SubBranchCreateRequest(BaseModel):
    source_conversation_id: str
    source_message_id: str
    char_start: int = 0
    char_end: int = 0
    quoted_text: str = ""
    initial_message: str = ""


@router.post("/sub-branch")
async def create_sub_branch(req: SubBranchCreateRequest):
    """创建子支会话"""
    try:
        conv, ref = tree_ops.create_sub_branch(
            USER_ID,
            req.source_conversation_id,
            req.source_message_id,
            req.char_start,
            req.char_end,
            req.quoted_text,
        )
        return {
            "conversation": conv.model_dump(mode="json"),
            "sub_branch_ref": ref.model_dump(mode="json"),
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception("Failed to create sub-branch")
        raise HTTPException(500, "Internal server error")


@router.get("/messages/{message_id}/sub-branches")
async def get_message_sub_branches(message_id: str):
    """获取消息的子支列表"""
    branches = tree_ops.get_sub_branches(USER_ID, message_id)
    return {"sub_branches": branches}


@router.get("/sub-branch/{conv_id}/parent")
async def get_sub_branch_parent(conv_id: str):
    """获取子支的父会话信息"""
    result = tree_ops.get_sub_branch_parent(USER_ID, conv_id)
    if not result:
        raise HTTPException(404, "Not a sub-branch or parent not found")
    return result


# ═══════════════════════════════════════════
# 情绪分析
# ═══════════════════════════════════════════


@router.get("/emotion/trend")
async def get_emotion_trend(window_hours: int = 72):
    """获取用户情绪趋势分析"""
    from app.services.emotion_analyzer import emotion_analyzer

    trend = await emotion_analyzer.analyze_trend(USER_ID, window_hours=window_hours)
    return trend.to_dict()


@router.get("/emotion/recent")
async def get_recent_emotions(limit: int = 10):
    """获取最近N条情绪记录"""
    from app.services.emotion_analyzer import emotion_analyzer

    records = emotion_analyzer._cache.get(USER_ID, [])
    return {
        "records": [r.to_dict() for r in records[-min(limit, 50):]],
        "total": len(records),
    }


@router.get("/emotion/stats")
async def get_emotion_stats():
    """情绪统计概览（用于首页卡片展示）"""
    from app.services.emotion_analyzer import emotion_analyzer

    records = emotion_analyzer._cache.get(USER_ID, [])
    if not records:
        return {"status": "insufficient_data", "message": "还没有足够的情绪数据"}

    cat_counts = {}
    for r in records:
        cat_counts[r.category] = cat_counts.get(r.category, 0) + 1
    dominant = max(cat_counts, key=cat_counts.get)

    neg_count = sum(1 for r in records
                    if emotion_analyzer.EMOTION_CATEGORIES.get(r.category, {}).get("severity") == "negative")
    total = len(records)

    return {
        "status": "ready",
        "total_records": total,
        "dominant_emotion": dominant,
        "dominant_emoji": emotion_analyzer.EMOTION_CATEGORIES.get(dominant, {}).get("emoji", ""),
        "negative_ratio": round(neg_count / total, 2) if total > 0 else 0,
        "categories": cat_counts,
    }
