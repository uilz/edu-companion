"""
对话系统 REST API 路由
层级：分区 → 领域 → 专题 → 对话 → 消息
所有 CRUD 统一在 /tree/{level} 下，消息操作挂在 /tree/conversation/{conv_id}/message 和 /tree/message/{id}

从 conversation.py 拆分：仅 REST 端点 + 请求模型 + 辅助函数
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File, Form, Query, Depends  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

from app.schemas.conversation import TextBlock
from app.services.common import get_data_repo
from app.services.knowledge.tree_service import tree_ops
from app.domain.auth.dependencies import current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ══════════════════ 请求模型 ══════════════════
class ToolResultRequest(BaseModel):
    """ask_question 工具的结果提交"""
    tool_call_id: str
    answers: str  # 用户回答文本
    dir_id: str | None = None


class SendMessageRequest(BaseModel):
    text: str
    content_blocks: list[dict] = Field(default_factory=list)
    dir_id: str | None = None
    pending_quote: dict | None = None  # 引用数据
    knowledge_node_id: str | None = None  # 知识树探索会话绑定的节点 ID


class StreamMessageRequest(BaseModel):
    action: str = "send"  # "send" | "replay" | "stop"
    text: str = ""
    dir_id: str | None = None
    parent_id: str | None = None  # 分支回复：指定父消息 ID（用户消息的父节点）
    pending_quote: dict | None = None
    knowledge_node_id: str | None = None
    content_blocks: list[dict] = Field(default_factory=list)
    pending_msg_id: str | None = None  # 仅 replay 使用: 指定要恢复的消息 ID



class CreateConversationRequest(BaseModel):
    topic_id: str = ""
    parent_id: str = ""
    parent_type: str = ""
    type: str = "normal"
    name: str = ""
    mode: str = "tutor"  # tutor | feynman | peer


class MigrateConversationRequest(BaseModel):
    target_dir_id: str
    target_type: str = "normal"


class SwitchConfirmRequest(BaseModel):
    """用户确认 SwitchBanner 后，迁移节点的请求"""
    source_conv_id: str
    source_node_id: str          # 触发分类的用户消息节点 ID
    target_dir_id: str     # 目标分区 ID
    target_domain_name: str = "" # 目标领域名（跨分区/同分区专题切换）
    target_topic_name: str = ""  # 目标专题名


class ExploreRequest(BaseModel):
    node_id: str
    node_label: str
    node_level: str = "concept"


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


# ══════════════════ ETag 辅助 ══════════════════
def _check_etag(request: Request, user_id: str) -> str | None:
    etag = get_data_repo().get_etag(user_id)
    if_none_match = request.headers.get("if-none-match", "")
    if if_none_match == etag:
        raise HTTPException(304)
    return etag


# ══════════════════ 通用树节点 CRUD ══════════════════
@router.get("/tree/{level}")
async def list_nodes(level: str, request: Request, user_id: str = Depends(current_user_id), parent_id: str = Query(None), type: str = Query(None)):
    if level != "directory":
        raise HTTPException(400, f"Unsupported level: {level}")
    data = get_data_repo().load(user_id)
    nodes = []
    for n in data.directory_nodes.values():
        if parent_id and n.parent_id != parent_id:
            continue
        nodes.append(n.model_dump(mode="json"))
    return Response(
        content=json.dumps({"directory_nodes": nodes}),
        media_type="application/json",
        headers={"Cache-Control": "no-cache"},
    )


# ══════════════════ DirectoryNode CRUD ══════════════════
@router.post("/tree/directory")
async def create_directory_node(body: dict, user_id: str = Depends(current_user_id)):
    """创建目录节点。body: { node_type, kind, parent_id, name }"""
    try:
        node_type = body.get("node_type", "dir")
        kind = body.get("kind", "general")
        parent_id = body.get("parent_id")
        name = body.get("name", "新目录")

        if node_type == "conv":
            entity = tree_ops.create_conv(user_id, parent_id, name, kind=kind)
        else:
            entity = tree_ops.create_dir(user_id, parent_id, name, kind=kind)
        return {"directory_node": entity.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception("Failed to create directory node")
        raise HTTPException(500, "Internal server error")


@router.patch("/tree/directory/{node_id}")
async def rename_directory_node(node_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """重命名目录节点。"""
    try:
        name = body.get("name")
        if not name:
            raise HTTPException(400, "Name is required")
        entity = tree_ops.rename_node(user_id, node_id, name)
        return {"directory_node": entity.model_dump(mode="json")}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception(f"Failed to rename directory node {node_id}")
        raise HTTPException(500, "Internal server error")


@router.delete("/tree/directory/{node_id}")
async def delete_directory_node(node_id: str, user_id: str = Depends(current_user_id)):
    """删除目录节点及其所有子节点。"""
    try:
        tree_ops.delete_node(user_id, node_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception(f"Failed to delete directory node {node_id}")
        raise HTTPException(500, "Internal server error")


@router.post("/tree/conversation/{conv_id}/migrate")
async def migrate_conversation(conv_id: str, body: MigrateConversationRequest, user_id: str = Depends(current_user_id)):
    """将对话迁移到目标目录下。

    修复历史: 原代码调用 tree_ops.migrate_temporary_conversation（不存在）→ 500。
    实际语义与 tree_ops.migrate_conv 等价（kind="temp" 判定在 tree_conv 自身处理），
    故改用现有方法。该方法已支持任意 conv → dir 迁移。
    """
    try:
        conv = tree_ops.migrate_conv(
            user_id, conv_id, body.target_dir_id,
        )
        return {"ok": True, "conversation": conv.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("Failed to migrate conversation")
        raise HTTPException(500, "Internal server error")


@router.post("/tree/switch")
async def switch_conversation(body: SwitchConfirmRequest, user_id: str = Depends(current_user_id)):
    """用户确认切换推荐后：将触发节点及其子节点迁移到目标层级下的新会话。

    状态: 未实现。`move_subtree_to_conversation` 在 tree_ops 上不存在 (ADR Phase B 设计，
    实施阶段未落地)。明确返回 501，避免上游 SwitchBanner 误以为操作成功。
    """
    raise HTTPException(
        status_code=501,
        detail="switch_subtree 未实现 — tree_ops.move_subtree_to_conversation 缺失 (ADR 2026-phases/conversation-hierarchy-redesign Phase B 待办)",
    )


@router.get("/tree/directory/{node_id}")
async def get_directory_node(node_id: str, user_id: str = Depends(current_user_id)):
    """获取单个目录节点的详细信息（含祖先链）。"""
    data = get_data_repo().load(user_id)
    node = data.directory_nodes.get(node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    result = node.model_dump(mode="json")
    # 构建祖先链
    ancestors = []
    pid = result.get("parent_id", "")
    while pid and pid in data.directory_nodes:
        p = data.directory_nodes[pid]
        ancestors.append({"id": p.id, "name": p.display_name, "node_type": p.node_type})
        pid = p.parent_id
    result["ancestors"] = list(reversed(ancestors))
    return {"directory_node": result}


@router.get("/tree/conversation/{conv_id}")
async def get_conversation(conv_id: str, user_id: str = Depends(current_user_id)):
    """获取单个会话的完整信息（含目录路径）。
    
    DirectoryNode 版本：返回 parent_id、祖先目录路径等。
    """
    data = get_data_repo().load(user_id)
    conv = data.directory_nodes.get(conv_id)
    if not conv or conv.node_type != "conv":
        raise HTTPException(404, "Conversation not found")
    result = conv.model_dump(mode="json")
    # 构建祖先链
    ancestors = []
    pid = result.get("parent_id", "")
    while pid and pid in data.directory_nodes:
        p = data.directory_nodes[pid]
        ancestors.append({"id": p.id, "name": p.display_name, "node_type": p.node_type})
        pid = p.parent_id
    result["ancestors"] = list(reversed(ancestors))
    return {"conversation": result}


@router.get("/tree/conversations/recent")
async def list_recent_conversations(user_id: str = Depends(current_user_id), limit: int = Query(50)):
    """扁平模式下获取最近活跃对话列表。返回所有 conv 节点按 last_active 降序排列。"""
    data = get_data_repo().load(user_id)
    convs = []
    for dn in data.directory_nodes.values():
        if dn.node_type == "conv" and not dn.metadata.get("is_deleted", False):
            last_active = dn.metadata.get("last_active", dn.updated_at)
            convs.append({
                "id": dn.id,
                "name": dn.display_name,
                "kind": dn.kind,
                "parent_id": dn.parent_id,
                "last_active": last_active,
                "message_count": len(dn.conv_message_ids),
            })
    convs.sort(key=lambda x: x["last_active"], reverse=True)
    convs = convs[:limit]
    # Attach ancestor path for display (skip virtual root)
    for c in convs:
        pid = c["parent_id"]
        ancestors = []
        while pid and pid in data.directory_nodes:
            p = data.directory_nodes[pid]
            if p.parent_id is not None:  # skip the virtual root node
                ancestors.append({"id": p.id, "name": p.display_name})
            pid = p.parent_id
        c["ancestors"] = list(reversed(ancestors))
    return {"conversations": convs}


@router.delete("/tree/{level}/{node_id}")
async def delete_node(level: str, node_id: str, user_id: str = Depends(current_user_id)):
    if level == "message":
        tree_ops.delete_message(user_id, node_id)
        return {"ok": True}
    raise HTTPException(400, f"Unsupported level: {level}")


def _merge_cognitive_ids(messages: list[dict], msg_ids: list[str]) -> None:
    """从 messages 表合并 cognitive_node_ids 到树节点 json 中"""
    from app.infrastructure.db.database import get_db

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
    conv_id: str, request: Request, user_id: str = Depends(current_user_id),
    limit: int = 50, offset: int = 0,
    head: int | None = None, tail: int | None = None,
):
    """获取会话消息骨架列表（仅 id/parent_id/role/version 等结构字段，无正文）。

    支持三种模式（向后兼容）：
      - limit/offset：传统分页
      - head=N&tail=M：分段加载，开头 N 条 + 末尾 M 条（用于大型对话）
      - 仅 limit/offset：默认全量上限 50
    """
    etag = _check_etag(request, user_id)
    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        raise HTTPException(404, "Conversation not found")
    total_ids = len(conv_node.conv_message_ids)

    # 分段模式：head + tail（去重）
    if head is not None or tail is not None:
        head_n = head if head is not None else 0
        tail_n = tail if tail is not None else 0
        head_ids = conv_node.conv_message_ids[:head_n]
        tail_ids = conv_node.conv_message_ids[-tail_n:] if tail_n > 0 else []
        # 去重保持顺序
        seen = set()
        msg_ids = []
        for mid in head_ids + tail_ids:
            if mid not in seen:
                seen.add(mid)
                msg_ids.append(mid)
    else:
        msg_ids = conv_node.conv_message_ids[offset: offset + limit]

    from app.services.conversation.message_repository import get_message_repo
    msg_repo = get_message_repo()

    def _get_msg(mid: str):
        n = data.nodes.get(mid)
        if n and not getattr(n, "is_deleted", False):
            return n
        return msg_repo.get(mid)

    messages = []
    for mid in msg_ids:
        node = _get_msg(mid)
        if node and not getattr(node, "is_deleted", False):
            # 保留根占位消息（前端需要它的 ID 作为 currentPath 起点）
            d = {
                "id": node.id,
                "directory_id": getattr(node, "directory_id", ""),
                "parent_id": node.parent_id,
                "children_ids": node.children_ids,
                "role": node.role,
                "version": node.version,
                "timestamp": getattr(node, "timestamp", 0),
                "token_count": getattr(node, "token_count", 0),
                "has_sub_branches": getattr(node, "has_sub_branches", False),
                "sub_branch_ids": getattr(node, "sub_branch_ids", []),
                "content": "",
                "content_blocks": [],
                "text_summary": "",
                "is_deleted": getattr(node, "is_deleted", False),
                "status": getattr(node, "status", "done"),
            }
            messages.append(d)
    return Response(
        content=json.dumps({"messages": messages, "total": total_ids}),
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


@router.get("/tree/conversation/{conv_id}/blocks")
async def get_conversation_blocks(conv_id: str, user_id: str = Depends(current_user_id), limit: int = 100):
    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        return {"blocks": []}
    path = conv_node.conv_message_ids
    blocks = []
    if path:
        asst_ids = {
            nid
            for nid in path
            if (n := data.nodes.get(nid)) and n.role == "assistant" and not getattr(n, "is_deleted", False)
        }
        blocks = [
            b.model_dump(mode="json")
            for b in data.response_blocks.values()
            if b.message_id in asst_ids
        ][:limit]
    return {"blocks": blocks}

@router.post("/tree/conversation/{conv_id}/message")
async def handle_message(
    conv_id: str,
    req: StreamMessageRequest,
    user_id: str = Depends(current_user_id),
):
    """统一消息端点 — action=send/replay 返回 SSE 流，action=stop 返回 JSON

    send:   启动 Pipeline → StreamingResponse（从事件 0 开始）
    replay: 重连已有 Pipeline → StreamingResponse（从事件 0 回放 + 继续）
    stop:   取消 Pipeline → { ok: true }
    """
    from app.domain.conversation.conversation_processor import start_background_pipeline
    from app.services.conversation.stream_buffer import stream_buffer

    if req.action == "stop":
        ok = await stream_buffer.cancel(conv_id)
        return {"ok": ok}

    if req.action == "replay":
        # 支持 pending_msg_id 粒度的 replay
        if req.pending_msg_id:
            if not await stream_buffer.has_msg_events(conv_id, req.pending_msg_id):
                return {"ok": True, "stream_ended": True}
        else:
            if not await stream_buffer.has_active(conv_id):
                return {"ok": True, "stream_ended": True}
        return StreamingResponse(
            _sse_generator(conv_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if req.action == "send":
        pid = req.dir_id
        if not pid:
            data = get_data_repo().load(user_id)
            conv_node = data.directory_nodes.get(conv_id)
            if not conv_node or conv_node.node_type != "conv":
                raise HTTPException(404, "Conversation not found")
            pid = conv_node.parent_id or conv_id

        await start_background_pipeline(
            user_id, req.text, pid,
            conv_id=conv_id,
            parent_id=req.parent_id or "",
            pending_quote=req.pending_quote,
            knowledge_node_id=req.knowledge_node_id,
        )

        return StreamingResponse(
            _sse_generator(conv_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    raise HTTPException(400, f"Unknown action: {req.action}")


@router.post("/tree/conversation/{conv_id}/tool-result")
async def handle_tool_result(
    conv_id: str,
    req: ToolResultRequest,
    user_id: str = Depends(current_user_id),
):
    """提交 ask_question 工具的结果（用户回答），恢复挂起的管线继续执行

    与方案B不同：不启动新管线，而是恢复同一管线中挂起的 ToolLoopStage while 循环。
    工具结果直接注入 llm_messages，LLM 在原有上下文中继续推理。
    原 SSE 连接保持打开，恢复后继续接收事件。
    """
    from app.domain.conversation.conversation_processor import resume_background_pipeline
    from app.domain.conversation.pipeline_stages import ToolResult

    tool_result = ToolResult(
        tool_call_id=req.tool_call_id,
        answers=req.answers,
    )

    # 恢复挂起的管线（而非启动新管线）
    ok = await resume_background_pipeline(conv_id, tool_result)
    if not ok:
        raise HTTPException(404, "No suspended pipeline found for this conversation")

    # 返回简单 JSON（原 SSE 连接保持打开，继续接收恢复后的事件）
    return {"ok": True, "message": "答案已提交，AI 正在继续回复"}


async def _sse_generator(conv_id: str):
    """SSE 事件生成器 — 从 StreamBuffer 读取，格式化为 SSE"""
    import asyncio as _asyncio
    from app.services.conversation.stream_buffer import stream_buffer as _buf

    event_counter = 0
    try:
        async for event in _buf.stream(conv_id):
            event_counter += 1
            data = json.dumps(event, ensure_ascii=False, default=str)
            yield f"id: {event_counter}\ndata: {data}\n\n"

        # 流正常结束
        yield "data: {\"type\":\"stream_end\"}\n\n"
    except _asyncio.CancelledError:
        # 客户端断开 → 不影响 pipeline 继续运行
        pass
    except Exception as e:
        logger.error("SSE 生成器异常 [%s]: %s", conv_id[:8], e)
        error_data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


@router.get("/tree/message/{message_id}")
async def get_message(message_id: str, user_id: str = Depends(current_user_id)):
    data = get_data_repo().load(user_id)
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
async def switch_version(message_id: str, req: dict | None = None, user_id: str = Depends(current_user_id)):
    if req is None:
        req = {}
    """切换到指定版本：从目标版本 DFS 重建 conv.path。
    请求体: { "direction": "prev" | "next" } 或 { "target_index": int }
    """
    direction = req.get("direction")
    target_index = req.get("target_index")

    data = get_data_repo().load(user_id)
    node = data.nodes.get(message_id)
    if not node:
        raise HTTPException(404, "Message not found")

    conv_id_val = getattr(node, "directory_id", getattr(node, "conv_id", ""))
    conv = data.directory_nodes.get(conv_id_val)
    if not conv or conv.node_type != "conv":
        raise HTTPException(400, "No conversation found")

    # 1) 在 conv.conv_message_ids 中找到当前活跃的版本节点（同父同角色）
    parent = data.nodes.get(node.parent_id) if node.parent_id else None
    if not parent:
        raise HTTPException(400, "No parent found")

    # 当前活跃版本 = conv_message_ids 中与 node 同父同角色的那个
    cur_version_id = None
    version_point_idx = None
    for i, nid in enumerate(conv.conv_message_ids):
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

    # 4) 重建 conv.conv_message_ids = prefix + DFS(目标版本)
    prefix = conv.conv_message_ids[:version_point_idx]
    conv_for_dfs = conv.id  # 限制只收集同一会话的节点，防止子支混入

    def dfs(nid: str, acc: list):
        nd = data.nodes.get(nid)
        if not nd or nd.is_deleted:
            return
        # 只收集属于当前会话的节点，跳过子支（属于其他会话）
        nd_conv = getattr(nd, "directory_id", getattr(nd, "conv_id", None))
        if nd_conv != conv_for_dfs:
            return
        acc.append(nid)
        for cid in nd.children_ids:
            dfs(cid, acc)

    new_path = list(prefix)
    dfs(target_id, new_path)

    # 5) 保存并返回
    conv.conv_message_ids = new_path
    conv.summary_dirty = True
    get_data_repo().save(user_id, data)

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
async def modify_message(message_id: str, req: ModifyMessageRequest, user_id: str = Depends(current_user_id)):
    try:
        blocks = [
            TextBlock(text=block.get("text", ""))
            for block in req.content_blocks
            if block.get("type") == "text"
        ]
        node = tree_ops.modify_message(user_id, message_id, blocks, req.text_summary)
        data = get_data_repo().load(user_id)
        parent = data.nodes.get(node.parent_id) if node.parent_id else None
        all_siblings = parent.children_ids if parent else []
        version_count = sum(
            1
            for vid in all_siblings
            if data.nodes.get(vid) and data.nodes[vid].role == node.role
        )
        return {"node": node, "version_count": version_count}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception("modify_message 失败")
        raise HTTPException(500, "Internal server error")


@router.post("/tree/message/{message_id}/reply")
async def reply_to_edited_message(message_id: str, user_id: str = Depends(current_user_id)):
    """编辑消息后重新生成 AI 回复"""
    from app.infrastructure.llm.tool_dispatch import generate_reply_with_tools
    from app.schemas.conversation import TextBlock

    try:
        data = get_data_repo().load(user_id)
        node = data.nodes.get(message_id)
        if not node or node.role != "user":
            raise HTTPException(400, "Can only reply to user messages")

        conv_id = getattr(node, "directory_id", getattr(node, "conv_id", ""))
        conv = data.directory_nodes.get(conv_id)
        if not conv or conv.node_type != "conv":
            raise HTTPException(404, "Conversation not found")

        pid = getattr(node, "directory_id", None) or conv.parent_id or conv_id

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
        response_blocks = await generate_reply_with_tools(user_id, pid, text)

        # 提取文本
        text_parts = []
        for block in response_blocks:
            if block.type == "text":
                text_parts.append(block.content.get("text", ""))
        reply_text = "\n\n".join(text_parts) if text_parts else "（已收到你的修改）"

        # 存助手消息（会自动追加到 conv.path）
        assistant_node = tree_ops.add_message(
            user_id, pid, "assistant",
            [TextBlock(text=reply_text)], reply_text,
            conv_id=conv_id,
        )

        # 回填 message_id
        data = get_data_repo().load(user_id)
        for block in response_blocks:
            if block.id in data.response_blocks:
                data.response_blocks[block.id].message_id = assistant_node.id
        get_data_repo().save(user_id, data)

        return {
            "assistant_message": assistant_node.model_dump(mode="json"),
            "conv_id": conv_id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception("reply_to_edited_message 失败")
        raise HTTPException(500, "Internal server error")


# ═══════════════════════════════════════════
# 分支对话链式遍历 API
# ═══════════════════════════════════════════

@router.get("/tree/conversation/{conv_id}/chain")
async def get_conversation_chain(conv_id: str, user_id: str = Depends(current_user_id)):
    """返回当前活跃消息链（基于 conv.conv_message_ids）。
    
    返回从根到尾部的完整消息列表，跳过空的 shell 占位符。
    """
    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        raise HTTPException(404, "Conversation not found")
    
    messages = []
    # 消息存储在 PostgreSQL messages 表（D18），通过 message_repository 补充查询
    from app.services.conversation.message_repository import get_message_repo
    msg_repo = get_message_repo()
    for mid in conv_node.conv_message_ids:
        node = data.nodes.get(mid)
        if not node or getattr(node, "is_deleted", False):
            # 从 PostgreSQL 单条加载（兼容按目录存储的旧消息）
            node = msg_repo.get(mid)
        if node and not getattr(node, "is_deleted", False):
            # 保留根占位消息（前端需要它的 ID 作为 currentPath 起点）
            messages.append(node.model_dump(mode="json"))

    return {"messages": messages, "total": len(messages)}


@router.post("/tree/conversation/{conv_id}/chain/path")
async def compute_chain_path(conv_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """计算从根到指定消息的完整路径。

    请求体: { "from_id": "msg_id" }
    返回: 从根（parent_id=None）到 from_id 的祖先链（含 from_id 自身）
    """
    from_id = body.get("from_id", "")
    if not from_id:
        raise HTTPException(400, "from_id is required")

    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        raise HTTPException(404, "Conversation not found")

    # 沿 parent_id 回溯到根
    # 消息存储在 PostgreSQL messages 表（D18），通过 message_repository 单条加载
    from app.services.conversation.message_repository import get_message_repo
    msg_repo = get_message_repo()

    def _get_msg(mid: str):
        # 先查 nodeMap 缓存
        n = data.nodes.get(mid)
        if n and not getattr(n, "is_deleted", False):
            return n
        # 否则从 PostgreSQL 单条加载（兼容按目录存储的旧消息）
        return msg_repo.get(mid)

    path = []
    current_id = from_id
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = _get_msg(current_id)
        if not node or getattr(node, "is_deleted", False):
            break
        path.append(node.model_dump(mode="json"))
        current_id = node.parent_id

    path.reverse()  # 根 → from_id
    return {"messages": path, "total": len(path), "from_id": from_id}


@router.post("/tree/conversation/{conv_id}/chain/skeleton")
async def get_chain_skeleton(conv_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """单次链式加载：从 node_id 同时向上回溯到 root + 向下沿长子链到 leaf。

    请求体: { "node_id": "msg_id" }
    返回: { "ancestors": [...], "descendants": [...] }
    """
    node_id = body.get("node_id", "")
    if not node_id:
        raise HTTPException(400, "node_id is required")

    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        raise HTTPException(404, "Conversation not found")

    from app.services.conversation.message_repository import get_message_repo
    msg_repo = get_message_repo()

    def _get_msg(mid: str):
        n = data.nodes.get(mid)
        if n and not getattr(n, "is_deleted", False):
            return n
        return msg_repo.get(mid)

    # ── 回填 children_by_parent（旧数据 children_ids 为空） ──
    children_by_parent: dict[str, list[str]] = {}
    for mid in conv_node.conv_message_ids:
        n = _get_msg(mid)
        if n and n.parent_id:
            children_by_parent.setdefault(n.parent_id, []).append(n.id)

    def _get_children(nid: str) -> list[str]:
        n = _get_msg(nid)
        cids = []
        if n:
            cids = list(getattr(n, "children_ids", []) or [])
        if not cids and nid in children_by_parent:
            cids = children_by_parent[nid]
        return cids

    def _get_default_child(nid: str) -> str | None:
        cids = _get_children(nid)
        if not cids:
            return None
        # 按 version 取最新
        candidates = []
        for cid in cids:
            n = _get_msg(cid)
            if n and not getattr(n, "is_deleted", False):
                candidates.append(n)
        if not candidates:
            return None
        candidates.sort(key=lambda n: (n.version, getattr(n, "timestamp", 0)), reverse=True)
        return candidates[0].id

    def _skeleton(n) -> dict:
        return {
            "id": n.id,
            "parent_id": n.parent_id,
            "children_ids": getattr(n, "children_ids", []),
            "role": n.role,
            "version": n.version,
            "directory_id": getattr(n, "directory_id", ""),
            "timestamp": getattr(n, "timestamp", 0),
            "is_deleted": getattr(n, "is_deleted", False),
            "status": getattr(n, "status", "done"),
        }

    # ── ancestors：从 node_id 向上回溯到根 ──
    ancestors = []
    cur = node_id
    visited = set()
    while cur and cur not in visited:
        visited.add(cur)
        n = _get_msg(cur)
        if not n or getattr(n, "is_deleted", False):
            break
        ancestors.append(_skeleton(n))
        cur = n.parent_id
    ancestors.reverse()  # 根 → node_id

    # ── descendants：从 node_id 沿长子链到 leaf ──
    descendants = []
    cur = node_id
    depth = 0
    while depth < 1000:  # 防御性上限
        child = _get_default_child(cur)
        if not child or child in visited:
            break
        visited.add(child)
        n = _get_msg(child)
        if not n or getattr(n, "is_deleted", False):
            break
        descendants.append(_skeleton(n))
        cur = child
        depth += 1

    return {
        "ancestors": ancestors,
        "descendants": descendants,
        "from_id": node_id,
    }


@router.post("/tree/conversation/{conv_id}/chain/tail")
async def compute_chain_tail(conv_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """计算从指定消息开始的尾部路径（沿 children_ids 向下）。
    
    请求体: { "from_id": "msg_id" }
    返回: from_id 及其后代消息列表（DFS 顺序，不含 from_id 的祖先）
    """
    from_id = body.get("from_id", "")
    if not from_id:
        raise HTTPException(400, "from_id is required")
    
    data = get_data_repo().load(user_id)
    conv_node = data.directory_nodes.get(conv_id)
    if not conv_node or conv_node.node_type != "conv":
        raise HTTPException(404, "Conversation not found")
    
    # DFS 遍历从 from_id 开始
    from app.services.conversation.message_repository import get_message_repo
    msg_repo = get_message_repo()

    def _get_msg(mid: str):
        n = data.nodes.get(mid)
        if n and not getattr(n, "is_deleted", False):
            return n
        return msg_repo.get(mid)

    # 回填 children_ids：旧数据 children_ids 为空，按 parent_id 反向构建
    children_by_parent: dict[str, list[str]] = {}
    # 收集本 conv 的所有消息（用 conv_message_ids 循环）
    for mid in conv_node.conv_message_ids:
        n = _get_msg(mid)
        if n and n.parent_id:
            children_by_parent.setdefault(n.parent_id, []).append(n.id)

    def _get_children(nid: str) -> list[str]:
        # 优先用节点自己的 children_ids，否则用反向构建
        n = _get_msg(nid)
        cids = []
        if n:
            cids = list(getattr(n, "children_ids", []) or [])
        if not cids and nid in children_by_parent:
            cids = children_by_parent[nid]
        return cids

    tail = []
    def dfs(nid: str):
        node = _get_msg(nid)
        if not node or getattr(node, "is_deleted", False):
            return
        tail.append(node.model_dump(mode="json"))
        for cid in _get_children(nid):
            dfs(cid)
    
    dfs(from_id)
    return {"messages": tail, "total": len(tail), "from_id": from_id}


@router.get("/tree/stream/active/{conv_id}")
async def check_stream_active(conv_id: str):
    """检测指定对话是否正在后台流式生成"""
    from app.services.conversation.stream_buffer import stream_buffer
    active = await stream_buffer.has_active(conv_id)
    return {"active": active, "conv_id": conv_id}


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
# 文件上传（R2-5: 统一到 /api/files/upload，不再使用独立 workspace）
# ═══════════════════════════════════════════

@router.post("/workspace/upload")
async def upload_workspace_file(
    file: UploadFile = File(...),
    conv_id: str = Form(...),
    user_id: str = Depends(current_user_id),
):
    """上传文件到对话（已迁移到 /api/files/upload + 记录 conv_id）"""
    if not file.filename:
        raise HTTPException(400, "No file selected")

    # 验证对话存在
    data = get_data_repo().load(user_id)
    conv = data.directory_nodes.get(conv_id)
    if not conv or conv.node_type != "conv":
        raise HTTPException(404, "Conversation not found")

    # 委托给 /api/files/upload 的核心逻辑
    from app.api.system.files_routes.upload import _do_upload
    result = await _do_upload(
        file=file,
        purpose="session",
        upload_source="conversation",
        level="partition",
        parent_id=conv_id,
        uid=user_id,
    )
    # 返回与旧 workspace 兼容的格式
    return {
        "file_id": result["material_id"],
        "original_name": result["file_name"],
        "file_type": result.get("file_type", "document"),
    }


# ══════════════════ 子支操作 ══════════════════

class SubBranchCreateRequest(BaseModel):
    source_conv_id: str
    source_message_id: str
    char_start: int = 0
    char_end: int = 0
    quoted_text: str = ""
    initial_message: str = ""
    mode: str = "tutor"  # tutor | feynman | peer


@router.post("/sub-branch")
async def create_sub_branch(req: SubBranchCreateRequest, user_id: str = Depends(current_user_id)):
    """创建子支会话"""
    try:
        conv, ref = tree_ops.create_sub_branch(
            user_id,
            req.source_conv_id,
            req.source_message_id,
            req.char_start,
            req.char_end,
            req.quoted_text,
            mode=req.mode,
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
async def get_message_sub_branches(message_id: str, user_id: str = Depends(current_user_id)):
    """获取消息的子支列表"""
    branches = tree_ops.get_sub_branches(user_id, message_id)
    return {"sub_branches": branches}


@router.get("/sub-branch/{conv_id}/parent")
async def get_sub_branch_parent(conv_id: str, user_id: str = Depends(current_user_id)):
    """获取子支的父会话信息"""
    result = tree_ops.get_sub_branch_parent(user_id, conv_id)
    if not result:
        raise HTTPException(404, "Not a sub-branch or parent not found")
    return result


# ═══════════════════════════════════════════
# 情绪分析
# ═══════════════════════════════════════════


@router.get("/emotion/trend")
async def get_emotion_trend(user_id: str = Depends(current_user_id), window_hours: int = 72):
    """获取用户情绪趋势分析"""
    from app.services.analytics.emotion_analyzer import emotion_analyzer

    trend = await emotion_analyzer.analyze_trend(user_id, window_hours=window_hours)
    return trend.to_dict()


@router.get("/emotion/recent")
async def get_recent_emotions(user_id: str = Depends(current_user_id), limit: int = 10):
    """获取最近N条情绪记录"""
    from app.services.analytics.emotion_analyzer import emotion_analyzer

    records = emotion_analyzer._cache.get(user_id, [])
    return {
        "records": [r.to_dict() for r in records[-min(limit, 50):]],
        "total": len(records),
    }


@router.get("/emotion/stats")
async def get_emotion_stats(user_id: str = Depends(current_user_id)):
    """情绪统计概览（用于首页卡片展示）"""
    from app.services.analytics.emotion_analyzer import emotion_analyzer

    records = emotion_analyzer._cache.get(user_id, [])
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
