"""
Knowledge Tree API v5 — 四实体解耦架构

统一前缀: /api/knowledge-tree
"""
from __future__ import annotations
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id
from app.services.knowledge_tree.knowledge_node_service import kn_svc
from app.services.knowledge_tree.conversation_service import conv_svc
from app.services.knowledge_tree.navigation_service import nav_svc
from app.services.knowledge_tree.message_service import msg_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-tree", tags=["知识树 v5"])


# ═══════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════

class CreateKnowledgeNodeRequest(BaseModel):
    label: str
    level: str = "topic"
    parent_id: str | None = None
    brief: str = ""
    tags: list[str] = Field(default_factory=list)
    emoji: str = ""
    color: str = ""

class UpdateKnowledgeNodeRequest(BaseModel):
    label: str | None = None
    level: str | None = None
    brief: str | None = None
    tags: list[str] | None = None
    emoji: str | None = None
    color: str | None = None
    is_visible: bool | None = None

class CreateConversationRequest(BaseModel):
    knowledge_node_ids: list[str] = Field(default_factory=list)
    summary_short: str = ""

class UpdateConversationRequest(BaseModel):
    summary_short: str | None = None
    knowledge_node_ids: list[str] | None = None

class CreateNavigationNodeRequest(BaseModel):
    parent_id: str
    name: str
    node_type: str = "dir"  # dir | conv
    kind: str = "general"
    conversation_id: str | None = None
    knowledge_area_id: str | None = None

class UpdateNavigationNodeRequest(BaseModel):
    name: str | None = None
    user_name: str | None = None
    kind: str | None = None
    knowledge_area_id: str | None = None

class CreateMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    content_blocks: list[dict] = Field(default_factory=list)
    text_summary: str = ""
    parent_id: str | None = None
    knowledge_node_ids: list[str] = Field(default_factory=list)

class AddPrerequisiteRequest(BaseModel):
    prereq_id: str
    prereq_type: str = "strict"

class AddAssociateRequest(BaseModel):
    target_id: str
    strength: float = 0.5
    rel_type: str = "analogy"

class ReorderChildrenRequest(BaseModel):
    children_order: list[str]


# ═══════════════════════════════════════════
# KnowledgeNode (知识点) 端点
# ═══════════════════════════════════════════

@router.get("/nodes")
async def list_knowledge_nodes(
    user_id: str = Depends(current_user_id),
    parent_id: str | None = Query(None),
    level: str | None = Query(None),
    search: str | None = Query(None),
):
    """列出知识点"""
    if search:
        nodes = kn_svc.search(user_id, search)
    elif parent_id is not None:
        nodes = kn_svc.list_nodes(user_id, parent_id=parent_id)
    elif level is not None:
        nodes = kn_svc.list_nodes(user_id, level=level)
    else:
        nodes = kn_svc.list_nodes(user_id)
    return {"nodes": [n.model_dump(mode="json") for n in nodes], "total": len(nodes)}


@router.get("/nodes/{node_id}")
async def get_knowledge_node(node_id: str, user_id: str = Depends(current_user_id)):
    """获取单个知识点"""
    node = kn_svc.get_node(user_id, node_id)
    if not node:
        raise HTTPException(404, "知识点不存在")
    return {"node": node.model_dump(mode="json")}


@router.get("/nodes/{node_id}/subtree")
async def get_knowledge_subtree(node_id: str, user_id: str = Depends(current_user_id)):
    """获取知识点子树"""
    nodes = kn_svc.get_subtree(user_id, node_id)
    return {"nodes": {k: v.model_dump(mode="json") for k, v in nodes.items()}}


@router.get("/nodes/{node_id}/conversations")
async def get_node_conversations(node_id: str, user_id: str = Depends(current_user_id)):
    """获取与知识点关联的所有会话"""
    convs = conv_svc.list_conversations(user_id, knowledge_node_id=node_id)
    return {"conversations": [c.model_dump(mode="json") for c in convs], "total": len(convs)}


@router.post("/nodes")
async def create_knowledge_node(body: CreateKnowledgeNodeRequest, user_id: str = Depends(current_user_id)):
    """创建知识点"""
    try:
        node = kn_svc.create_node(
            user_id=user_id, label=body.label, level=body.level,
            parent_id=body.parent_id, brief=body.brief, tags=body.tags,
            emoji=body.emoji, color=body.color,
        )
        return {"node": node.model_dump(mode="json")}
    except Exception:
        logger.exception("创建知识点失败")
        raise HTTPException(500, "Internal server error")


@router.put("/nodes/{node_id}")
async def update_knowledge_node(node_id: str, body: UpdateKnowledgeNodeRequest, user_id: str = Depends(current_user_id)):
    """更新知识点"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    node = kn_svc.update_node(user_id, node_id, **fields)
    if not node:
        raise HTTPException(404, "知识点不存在")
    return {"node": node.model_dump(mode="json")}


@router.delete("/nodes/{node_id}")
async def delete_knowledge_node(node_id: str, user_id: str = Depends(current_user_id)):
    """删除知识点 (级联删除子节点)"""
    ok = kn_svc.delete_node(user_id, node_id)
    if not ok:
        raise HTTPException(404, "知识点不存在")
    return {"ok": True}


@router.post("/nodes/{node_id}/prerequisites")
async def add_prerequisite(node_id: str, body: AddPrerequisiteRequest, user_id: str = Depends(current_user_id)):
    """添加前置知识点"""
    ok = kn_svc.add_prerequisite(user_id, node_id, body.prereq_id, body.prereq_type)
    if not ok:
        raise HTTPException(404, "知识点不存在")
    return {"ok": True}


@router.delete("/nodes/{node_id}/prerequisites/{prereq_id}")
async def remove_prerequisite(node_id: str, prereq_id: str, user_id: str = Depends(current_user_id)):
    """移除前置知识点"""
    ok = kn_svc.remove_prerequisite(user_id, node_id, prereq_id)
    if not ok:
        raise HTTPException(404, "知识点不存在")
    return {"ok": True}


@router.post("/nodes/{node_id}/associates")
async def add_associate(node_id: str, body: AddAssociateRequest, user_id: str = Depends(current_user_id)):
    """添加关联知识点"""
    ok = kn_svc.add_associate(user_id, node_id, body.target_id, body.strength, body.rel_type)
    if not ok:
        raise HTTPException(404, "知识点不存在")
    return {"ok": True}


@router.put("/nodes/{node_id}/reorder")
async def reorder_children(node_id: str, body: ReorderChildrenRequest, user_id: str = Depends(current_user_id)):
    """重新排序子节点"""
    ok = kn_svc.reorder_children(user_id, node_id, body.children_order)
    if not ok:
        raise HTTPException(404, "知识点不存在")
    return {"ok": True}


# ═══════════════════════════════════════════
# Conversation (会话) 端点
# ═══════════════════════════════════════════

@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(current_user_id),
    knowledge_node_id: str | None = Query(None),
):
    """列出会话"""
    convs = conv_svc.list_conversations(user_id, knowledge_node_id=knowledge_node_id)
    return {"conversations": [c.model_dump(mode="json") for c in convs], "total": len(convs)}


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, user_id: str = Depends(current_user_id)):
    """获取单个会话"""
    conv = conv_svc.get_conversation(user_id, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    return {"conversation": conv.model_dump(mode="json")}


@router.post("/conversations")
async def create_conversation(body: CreateConversationRequest, user_id: str = Depends(current_user_id)):
    """创建会话"""
    try:
        conv = conv_svc.create_conversation(
            user_id=user_id,
            knowledge_node_ids=body.knowledge_node_ids,
            summary_short=body.summary_short,
        )
        return {"conversation": conv.model_dump(mode="json")}
    except Exception:
        logger.exception("创建会话失败")
        raise HTTPException(500, "Internal server error")


@router.put("/conversations/{conv_id}")
async def update_conversation(conv_id: str, body: UpdateConversationRequest, user_id: str = Depends(current_user_id)):
    """更新会话"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    conv = conv_svc.update_conversation(user_id, conv_id, **fields)
    if not conv:
        raise HTTPException(404, "会话不存在")
    return {"conversation": conv.model_dump(mode="json")}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user_id: str = Depends(current_user_id)):
    """删除会话"""
    ok = conv_svc.delete_conversation(user_id, conv_id)
    return {"ok": True}


@router.post("/conversations/{conv_id}/knowledge-nodes/{node_id}")
async def add_conversation_knowledge_node(conv_id: str, node_id: str, user_id: str = Depends(current_user_id)):
    """向会话添加知识点关联"""
    ok = conv_svc.add_knowledge_node(user_id, conv_id, node_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


@router.delete("/conversations/{conv_id}/knowledge-nodes/{node_id}")
async def remove_conversation_knowledge_node(conv_id: str, node_id: str, user_id: str = Depends(current_user_id)):
    """从会话移除知识点关联"""
    ok = conv_svc.remove_knowledge_node(user_id, conv_id, node_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


# ═══════════════════════════════════════════
# Navigation (导航树) 端点
# ═══════════════════════════════════════════

@router.get("/navigation")
async def get_navigation_tree(
    user_id: str = Depends(current_user_id),
    root_id: str | None = Query(None),
):
    """获取导航树"""
    tree = nav_svc.build_tree(user_id, root_id)
    return {"tree": tree}


@router.get("/navigation/{node_id}")
async def get_navigation_node(node_id: str, user_id: str = Depends(current_user_id)):
    """获取单个导航节点"""
    node = nav_svc.get_node(user_id, node_id)
    if not node:
        raise HTTPException(404, "导航节点不存在")
    return {"node": node.model_dump(mode="json")}


@router.get("/navigation/{node_id}/children")
async def get_navigation_children(node_id: str, user_id: str = Depends(current_user_id)):
    """获取导航节点的子节点列表"""
    children = nav_svc.list_children(user_id, node_id)
    return {"children": [c.model_dump(mode="json") for c in children], "total": len(children)}


@router.post("/navigation")
async def create_navigation_node(body: CreateNavigationNodeRequest, user_id: str = Depends(current_user_id)):
    """创建导航节点 (目录或会话引用)"""
    try:
        if body.node_type == "conv":
            if not body.conversation_id:
                raise HTTPException(400, "会话引用需要 conversation_id")
            node = nav_svc.create_conv_ref(
                user_id=user_id, parent_id=body.parent_id,
                conversation_id=body.conversation_id,
                name=body.name, kind=body.kind,
            )
        else:
            node = nav_svc.create_dir(
                user_id=user_id, parent_id=body.parent_id,
                name=body.name, kind=body.kind,
                knowledge_area_id=body.knowledge_area_id,
            )
        return {"node": node.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception:
        logger.exception("创建导航节点失败")
        raise HTTPException(500, "Internal server error")


@router.put("/navigation/{node_id}")
async def update_navigation_node(node_id: str, body: UpdateNavigationNodeRequest, user_id: str = Depends(current_user_id)):
    """更新导航节点"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    node = nav_svc.update_node(user_id, node_id, **fields)
    if not node:
        raise HTTPException(404, "导航节点不存在")
    return {"node": node.model_dump(mode="json")}


@router.delete("/navigation/{node_id}")
async def delete_navigation_node(node_id: str, user_id: str = Depends(current_user_id)):
    """删除导航节点 (递归删除子节点)"""
    ok = nav_svc.delete_node(user_id, node_id)
    return {"ok": True}


@router.post("/navigation/{node_id}/migrate")
async def migrate_navigation_node(node_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """迁移导航节点到目标目录"""
    target_dir_id = body.get("target_dir_id")
    if not target_dir_id:
        raise HTTPException(400, "target_dir_id is required")
    try:
        node = nav_svc.migrate_conv(user_id, node_id, target_dir_id)
        return {"node": node.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════════════════════
# Message (消息) 端点
# ═══════════════════════════════════════════

@router.get("/conversations/{conv_id}/messages")
async def list_messages(
    conv_id: str, user_id: str = Depends(current_user_id),
    limit: int = Query(50), offset: int = Query(0), tree: bool = Query(False),
):
    """列出会话消息"""
    if tree:
        messages = msg_svc.get_message_tree(user_id, conv_id)
    else:
        messages = msg_svc.list_messages(user_id, conv_id, limit, offset)
    return {"messages": [m.model_dump(mode="json") for m in messages], "total": len(messages)}


@router.get("/messages/{msg_id}")
async def get_message(msg_id: str, user_id: str = Depends(current_user_id)):
    """获取单个消息"""
    msg = msg_svc.get_message(user_id, msg_id)
    if not msg:
        raise HTTPException(404, "消息不存在")
    return {"message": msg.model_dump(mode="json")}


@router.post("/messages")
async def create_message(body: CreateMessageRequest, user_id: str = Depends(current_user_id)):
    """创建消息"""
    try:
        msg = msg_svc.create_message(
            user_id=user_id, conversation_id=body.conversation_id,
            role=body.role, content=body.content,
            content_blocks=body.content_blocks,
            text_summary=body.text_summary,
            parent_id=body.parent_id,
            knowledge_node_ids=body.knowledge_node_ids,
        )
        # 同步更新会话的 message_ids
        conv_svc.add_message(user_id, body.conversation_id, msg.id)
        return {"message": msg.model_dump(mode="json")}
    except Exception:
        logger.exception("创建消息失败")
        raise HTTPException(500, "Internal server error")


@router.put("/messages/{msg_id}")
async def update_message(msg_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """更新消息"""
    fields = {k: v for k, v in body.items() if v is not None}
    msg = msg_svc.update_message(user_id, msg_id, **fields)
    if not msg:
        raise HTTPException(404, "消息不存在")
    return {"message": msg.model_dump(mode="json")}


@router.delete("/messages/{msg_id}")
async def delete_message(msg_id: str, user_id: str = Depends(current_user_id)):
    """删除消息 (级联删除子消息)"""
    ok = msg_svc.delete_message(user_id, msg_id)
    return {"ok": True}


@router.post("/messages/{msg_id}/knowledge-nodes/{node_id}")
async def add_message_knowledge_node(msg_id: str, node_id: str, user_id: str = Depends(current_user_id)):
    """向消息添加知识点关联"""
    ok = msg_svc.add_knowledge_node(user_id, msg_id, node_id)
    if not ok:
        raise HTTPException(404, "消息不存在")
    return {"ok": True}


# ═══════════════════════════════════════════
# 从旧 knowledge.py 迁移的端点
# ═══════════════════════════════════════════


@router.post("/explain")
async def explain_knowledge(body: dict):
    """
    用 AI 解释知识点或用户选中的文字。

    请求体:
    {"text": "选中/提问的文本", "node_id": "可选ID", "style": "simple | conversation"}
    """
    import logging
    logger = logging.getLogger(__name__)
    text = body.get("text", "")
    node_id = body.get("node_id")
    style = body.get("style", "simple")

    if not text.strip():
        return {"explanation": "请提供需要解释的文本"}

    from app.infrastructure.llm.llm_service import llm_service

    if style == "conversation":
        system_prompt = (
            "你是苹果果，以苏格拉底式对话引导用户自主思考。"
            "根据上下文，用简洁易懂的语言回答学生的问题。"
            "如果适合，可以反问引导学生深入思考。不要超过200字。"
        )
        user_prompt = f"学生提问：{text}"
    else:
        context_hint = f"（知识点ID: {node_id}）" if node_id else ""
        system_prompt = (
            "你是苹果果。用简洁易懂的语言解释知识点，"
            "适合自主学习场景。可以适当举例子。控制在300字以内。"
        )
        user_prompt = f"请解释以下内容{context_hint}：\n{text}"

    try:
        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=1024,
        )
        return {"explanation": raw.strip(), "content": raw.strip()}
    except Exception as e:
        logger.warning("AI 解释生成失败: %s", e)
        return {"explanation": "AI 解释暂不可用，请稍后再试。", "content": "AI 解释暂不可用，请稍后再试。"}


@router.get("/retention")
async def get_retention_curve(user_id: str = Depends(current_user_id)):
    """
    获取遗忘曲线（艾宾浩斯估算）。
    """
    import math
    import logging
    logger = logging.getLogger(__name__)
    from shared.knowledge_trace import get_cognitive_state
    from shared.constants import get_mastery_label
    from app.domain.knowledge.checker import PrerequisiteChecker
    from app.services.knowledge.knowledge_state import get_knowledge_state as _canonical_get_ks

    class _BKTKnowledgeAdapter:
        async def get_knowledge_state(self, uid: str, skill_id: str):
            return await _canonical_get_ks(uid, skill_id)

    checker = PrerequisiteChecker(_BKTKnowledgeAdapter())
    prerequisites = checker._prerequisites
    from app.domain.knowledge.prerequisites import SKILL_TO_SUBJECT

    skills = []
    for skill_id in prerequisites:
        state = get_cognitive_state(user_id, skill_id)
        if state.attempt_count == 0:
            continue
        S = max(1.0, state.p_known * 30 + math.log(state.attempt_count + 1) * 5)
        points = []
        for days in [0, 1, 3, 7, 14, 30, 60, 90]:
            retention = round(math.exp(-days / S) * 100, 1)
            points.append({"day": days, "retention": min(retention, 100)})
        skills.append({
            "skill_id": skill_id,
            "label": checker._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "attempt_count": state.attempt_count,
            "curve": points,
        })

    skills.sort(key=lambda s: s["mastery"])
    return {
        "user_id": user_id,
        "skills": skills,
        "total": len(skills),
        "avg_retention_7d": round(
            sum(s["curve"][3]["retention"] for s in skills) / max(len(skills), 1), 1
        ) if skills else 0,
        "at_risk": [s for s in skills if s["curve"][3]["retention"] < 50],
    }