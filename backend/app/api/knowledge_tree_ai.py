"""
Knowledge Tree AI v5 — AI 生成 / 扩充 / 编辑 / 对话

统一前缀: /api/knowledge-tree/ai
"""
from __future__ import annotations

import json as _json
import logging
import re
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id
from app.services.knowledge_tree.knowledge_node_service import kn_svc
from app.services.knowledge_tree.conversation_service import conv_svc
from app.services.knowledge_tree.message_service import msg_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-tree/ai", tags=["知识树 AI v5"])


# ═══════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════

class GenerateRequest(BaseModel):
    subject: str = ""
    description: str = ""
    parent_id: str | None = None
    depth: int = 3


class AiExpandRequest(BaseModel):
    depth: int = 2
    direction: str = "children"  # children | parents | both


class AiEditRequest(BaseModel):
    instruction: str


class AiChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _get_descendant_ids(user_id: str, node_id: str) -> set[str]:
    """获取节点的所有子孙节点 ID（含自身）"""
    subtree = kn_svc.get_subtree(user_id, node_id)
    return set(subtree.keys()) | {node_id}


def _build_node_context(nodes: list, bound_node_id: str | None = None) -> dict:
    """构建节点的上下文信息"""
    all_nodes = {}
    scope_labels = {}
    for n in nodes:
        info = {"label": n.label, "level": n.level, "brief": n.brief}
        all_nodes[n.id] = info
        if bound_node_id:
            scope_labels[n.id] = n.label
    return {"all_nodes": all_nodes, "scope_labels": scope_labels}


# ═══════════════════════════════════════════
# POST /ai/generate — AI 生成知识树
# ═══════════════════════════════════════════

@router.post("/generate")
async def generate_knowledge_tree(
    body: GenerateRequest,
    user_id: str = Depends(current_user_id),
):
    """AI 生成知识树。可指定 parent_id 在某节点下生成，或生成根节点。"""
    try:
        from app.infrastructure.llm.llm_service import llm_service

        # 收集已有节点信息
        existing_nodes = kn_svc.list_nodes(user_id)
        existing_labels = {n.label for n in existing_nodes}

        context_parts = []
        if body.subject:
            context_parts.append(f"学科/领域: {body.subject}")
        if body.description:
            context_parts.append(f"描述: {body.description}")
        if body.parent_id:
            parent = kn_svc.get_node(user_id, body.parent_id)
            if parent:
                context_parts.append(f"父节点: {parent.label} ({parent.level})")

        domain_context = "\n".join(context_parts) if context_parts else "通用知识"

        system_prompt = f"""你是知识图谱生成专家。根据用户的学习领域生成结构化的知识树。

{domain_context}

现有知识节点（不要重复）: {_json.dumps(list(existing_labels), ensure_ascii=False)}"""

        if not existing_labels:
            system_prompt += """

要求:
1. 生成 {depth} 层深度的知识点，从基础到高级
2. 每个节点包含: label(中文名), level(domain|topic|concept|atom), brief(一句话描述)
3. 根节点为 domain，子节点按层级递减
4. 输出严格JSON格式，不要任何额外文字

输出格式:
{{
  "nodes": [
    {{"label": "中文名", "level": "domain", "brief": "一句话描述"}}
  ],
  "edges": [
    {{"from_label": "父节点名", "to_label": "子节点名", "relation": "prerequisite"}}
  ]
}}""".replace("{depth}", str(body.depth))
        else:
            system_prompt += """

要求:
1. 在现有知识点基础上增量添加 {depth} 层新节点
2. 每个节点包含: label(中文名), level(topic|concept|atom), brief(一句话描述)
3. 不要重复已有节点
4. 输出严格JSON格式

输出格式:
{{
  "nodes": [
    {{"label": "中文名", "level": "topic", "brief": "一句话描述"}}
  ],
  "edges": [
    {{"from_label": "父节点名", "to_label": "子节点名", "relation": "prerequisite"}}
  ]
}}""".replace("{depth}", str(body.depth))

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"为'{body.subject or '知识树'}'生成{body.depth}层知识树"},
            ],
            temperature=0.3, max_tokens=16384,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        # 创建节点
        label_to_id: dict[str, str] = {}
        added_nodes = []

        for n in result.get("nodes", []):
            label = n.get("label", "")
            if not label or label in existing_labels:
                continue
            level = n.get("level", "topic")
            brief = n.get("brief", "")
            node = kn_svc.create_node(
                user_id=user_id,
                label=label,
                level=level,
                parent_id=body.parent_id,
                brief=brief,
                created_by="ai",
            )
            label_to_id[label] = node.id
            existing_labels.add(label)
            added_nodes.append({"id": node.id, "label": label, "level": level})

        # 创建边（prerequisite 关系）
        added_edges = []
        for e in result.get("edges", []):
            from_label = e.get("from_label", "")
            to_label = e.get("to_label", "")
            from_id = label_to_id.get(from_label)
            to_id = label_to_id.get(to_label)
            if from_id and to_id:
                kn_svc.add_prerequisite(user_id, to_id, from_id, "strict")
                # 将 to 节点的 parent 设为 from 节点
                kn_svc.update_node(user_id, to_id, parent_id=from_id)
                added_edges.append({"from_id": from_id, "to_id": to_id})

        return {
            "ok": True,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "total_nodes": len(added_nodes),
        }

    except _json.JSONDecodeError as e:
        logger.error(f"AI 生成 JSON 解析失败: {e}, raw={raw[:200] if 'raw' in dir() else 'N/A'}")
        return {"ok": False, "error": f"AI 返回格式错误: {str(e)}"}
    except Exception as e:
        logger.exception("AI 生成知识树失败")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════
# POST /ai/expand/{node_id} — AI 扩充节点
# ═══════════════════════════════════════════

@router.post("/expand/{node_id}")
async def ai_expand_node(
    node_id: str,
    body: AiExpandRequest,
    user_id: str = Depends(current_user_id),
):
    """AI 在指定节点下扩充子节点（或父节点/双向）"""
    target = kn_svc.get_node(user_id, node_id)
    if not target:
        raise HTTPException(404, "知识点不存在")

    # 获取已有节点
    all_nodes = kn_svc.list_nodes(user_id)
    existing_labels = {n.label for n in all_nodes}

    direction_text = {
        "children": "子节点（更深入的知识点）",
        "parents": "父节点（前置知识）",
        "both": "子节点和父节点",
    }.get(body.direction, "子节点")

    try:
        from app.infrastructure.llm.llm_service import llm_service

        prompt = f"""你是知识图谱扩充专家。当前知识树中节点「{target.label}」需要扩充{direction_text}。

目标节点: {target.label} (层级: {target.level})
目标节点描述: {target.brief or '无'}
生成深度: {body.depth} 层
现有节点（不要重复）: {_json.dumps(list(existing_labels), ensure_ascii=False)}

请为新节点生成:
1. 每个节点包含: label(中文名), level(topic|concept|atom), brief(一句话描述)
2. 边表示依赖关系: from_label是前置知识, to_label是后置知识
3. 不要重复已有节点
4. 输出严格JSON格式

输出格式:
{{
  "nodes": [
    {{"label": "中文名", "level": "concept", "brief": "一句话描述"}}
  ],
  "edges": [
    {{"from_label": "前置节点", "to_label": "后置节点"}}
  ]
}}"""

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"为节点「{target.label}」扩充{direction_text}，{body.depth}层深度"},
            ],
            temperature=0.3, max_tokens=8192,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        label_to_id: dict[str, str] = {target.label: node_id}
        added_nodes = []

        # 确定子节点的 parent_id
        child_parent_id = node_id if body.direction in ("children", "both") else None

        for n in result.get("nodes", []):
            label = n.get("label", "")
            if not label or label in existing_labels:
                continue
            level = n.get("level", "concept")
            brief = n.get("brief", "")
            node = kn_svc.create_node(
                user_id=user_id,
                label=label,
                level=level,
                parent_id=child_parent_id,
                brief=brief,
                created_by="ai",
            )
            label_to_id[label] = node.id
            existing_labels.add(label)
            added_nodes.append({"id": node.id, "label": label, "level": level})

        # 创建边
        added_edges = []
        for e in result.get("edges", []):
            from_label = e.get("from_label", "")
            to_label = e.get("to_label", "")
            from_id = label_to_id.get(from_label)
            to_id = label_to_id.get(to_label)
            if from_id and to_id:
                kn_svc.add_prerequisite(user_id, to_id, from_id, "strict")
                added_edges.append({"from_id": from_id, "to_id": to_id})

        return {
            "ok": True,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "total_nodes": len(added_nodes),
        }

    except _json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 返回格式错误: {str(e)}"}
    except Exception as e:
        logger.exception("AI 扩充节点失败")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════
# POST /ai/edit/{node_id} — AI 编辑节点
# ═══════════════════════════════════════════

@router.post("/edit/{node_id}")
async def ai_edit_node(
    node_id: str,
    body: AiEditRequest,
    user_id: str = Depends(current_user_id),
):
    """AI 根据用户指令编辑节点信息"""
    node = kn_svc.get_node(user_id, node_id)
    if not node:
        raise HTTPException(404, "知识点不存在")

    try:
        from app.infrastructure.llm.llm_service import llm_service

        prompt = f"""你是知识图谱编辑专家。根据用户指令修改节点信息。

当前节点:
- 名称: {node.label}
- 层级: {node.level}
- 描述: {node.brief or '无'}
- 标签: {', '.join(node.tags) if node.tags else '无'}

用户指令: {body.instruction}

请输出修改后的节点信息，严格JSON格式:
{{
  "label": "新名称（如不需要改则保持原样）",
  "level": "topic",
  "brief": "新描述",
  "tags": ["标签1", "标签2"]
}}"""

        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是知识图谱编辑专家，根据用户指令精确修改节点信息。只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3, max_tokens=2048,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = _json.loads(raw)

        updates = {}
        if result.get("label") and result["label"] != node.label:
            updates["label"] = result["label"]
        if result.get("brief"):
            updates["brief"] = result["brief"]
        if result.get("level"):
            updates["level"] = result["level"]
        if result.get("tags") is not None:
            updates["tags"] = result["tags"]

        if updates:
            updated = kn_svc.update_node(user_id, node_id, **updates)
            return {"ok": True, "node": updated.model_dump(mode="json")}
        return {"ok": True, "node": node.model_dump(mode="json"), "changed": False}

    except _json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 返回格式错误: {str(e)}"}
    except Exception as e:
        logger.exception("AI 编辑节点失败")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════
# POST /ai/chat/{node_id} — AI 对话编辑知识树
# ═══════════════════════════════════════════

@router.post("/chat/{node_id}")
async def ai_chat_edit_tree(
    node_id: str,
    body: AiChatRequest,
    user_id: str = Depends(current_user_id),
):
    """创建/获取知识树探索会话，返回 conversation_id。

    此为对话系统的统一入口封装：
      1. 创建/查找 tree_exploration 类型对话
      2. 返回 conversation_id，前端通过 SSE + POST message 进行流式对话
      3. 实际消息处理走 ReplyPipeline（含 knowledge_* 工具）
    """
    from app.services.common import get_data_repo as _gdr
    from app.schemas.directory_node import DirectoryNode

    # 验证节点存在
    bound_node = kn_svc.get_node(user_id, node_id)
    if not bound_node:
        raise HTTPException(404, "知识点不存在")

    data = _gdr().load(user_id)

    # 查找已存在的探索会话
    conversation_id = body.conversation_id
    if not conversation_id:
        for dn in data.directory_nodes.values():
            if dn.node_type == "conv" and dn.metadata.get("type") == "tree_exploration" and dn.metadata.get("knowledge_node_id") == node_id:
                conversation_id = dn.id
                break

    if not conversation_id:
        # 确保「知识树探索」分区存在
        explore_partition_id = None
        for dn in data.directory_nodes.values():
            if dn.node_type == "dir" and dn.name == "知识树探索":
                explore_partition_id = dn.id
                break
        if not explore_partition_id:
            explore_dir = DirectoryNode(
                user_id=user_id, parent_id=None,
                node_type="dir", kind="partition",
                name="知识树探索", path=[],
            )
            data.directory_nodes[explore_dir.id] = explore_dir
            explore_partition_id = explore_dir.id

        # 创建探索对话
        conv = DirectoryNode(
            user_id=user_id, parent_id=explore_partition_id,
            node_type="conv", kind="general",
            name=f"探索: {bound_node.label}",
            path=data.directory_nodes[explore_partition_id].path + [explore_partition_id],
            metadata={"type": "tree_exploration", "knowledge_node_id": node_id},
        )
        data.directory_nodes[conv.id] = conv
        parent = data.directory_nodes[explore_partition_id]
        parent.add_child(conv.id)
        _gdr().save(user_id, data)
        conversation_id = conv.id

    return {
        "ok": True,
        "conversation_id": conversation_id,
        "node_id": node_id,
        "node_label": bound_node.label,
    }


# ═══════════════════════════════════════════
# GET /ai/recommendation — 知识树推荐
# ═══════════════════════════════════════════

@router.get("/recommendation")
async def get_recommendations(
    source: str = Query("conversation"),
    user_id: str = Depends(current_user_id),
):
    """获取知识树推荐信息（替代旧 /api/knowledge/graph/recommendation）

    source=conversation: 在对话页面时，推荐未关联对话的叶子节点
    source=tree: 在知识树页面时，推荐未探索的节点
    """
    try:
        all_nodes = kn_svc.list_nodes(user_id)
        if not all_nodes:
            return {"ok": True, "recommendations": [{
                "type": "empty",
                "message": "还没有知识树，请先生成知识树",
                "action": "generate",
            }]}

        recommendations = []

        if source == "tree":
            # 找叶子节点（没有子节点的节点）
            parent_ids = {n.parent_id for n in all_nodes if n.parent_id}
            leaf_nodes = [n for n in all_nodes if n.id not in parent_ids]
            unexplored = [
                {"id": n.id, "label": n.label}
                for n in leaf_nodes if n.mastery < 0.3
            ]
            if unexplored:
                recommendations.append({
                    "type": "unexplored_nodes",
                    "message": f"还有 {len(unexplored)} 个节点未探索",
                    "action": "explore",
                    "nodes": unexplored[:5],
                })
            elif leaf_nodes and all(n.mastery >= 0.3 for n in leaf_nodes):
                recommendations.append({
                    "type": "tree_complete",
                    "message": "知识树已探索完毕！建议去对话系统深入学习",
                    "action": "go_conversation",
                })

        elif source == "conversation":
            # 找有关联 conversation 的节点
            nodes_with_conv = set()
            convs = conv_svc.list_conversations(user_id)
            for conv in convs:
                for nid in conv.knowledge_node_ids:
                    nodes_with_conv.add(nid)

            nodes_without_conv = [
                {"id": n.id, "label": n.label}
                for n in all_nodes if n.id not in nodes_with_conv
            ]
            if nodes_without_conv:
                recommendations.append({
                    "type": "pending_nodes",
                    "message": f"有 {len(nodes_without_conv)} 个节点待整理",
                    "action": "go_tree",
                    "nodes": nodes_without_conv[:5],
                })

        return {"ok": True, "recommendations": recommendations[:3]}

    except Exception as e:
        logger.exception("获取推荐失败")
        return {"ok": False, "error": str(e)}