"""知识图谱 — 会话域：会话关联 / AI 对话编辑"""
from __future__ import annotations

import json as _json
import logging
import re
import time

from fastapi import APIRouter, HTTPException

from . import (
    _load, _save, _get_graph, _get_descendant_ids,
    _sync_graph_to_cognitive, LinkConversationRequest, AiChatRequest,
)
from app.services.knowledge.tree_ops import tree_ops
from shared.constants import DEFAULT_USER_ID

_USER_ID = DEFAULT_USER_ID

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/link-conversation — 关联会话到节点
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/link-conversation")
async def link_conversation(partition_id: str, body: LinkConversationRequest):
    graph = _get_graph(partition_id)
    if not graph or body.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    data = _load()
    if body.conversation_id not in data.conversations:
        raise HTTPException(status_code=404, detail="会话不存在")

    node = graph.nodes[body.node_id]
    conv_ids = list(getattr(node, "conversation_ids", None) or [])
    if body.conversation_id not in conv_ids:
        conv_ids.append(body.conversation_id)
    node.conversation_ids = conv_ids

    graph.updated_at = time.time()
    graph.version += 1
    data.knowledge_graphs[partition_id] = graph
    _save(data)
    return {"ok": True, "conversation_ids": conv_ids}


# ═══════════════════════════════════════════════════════════
# DELETE /{partition_id}/link-conversation/{node_id}/{conversation_id} — 取消关联
# ═══════════════════════════════════════════════════════════

@router.delete("/{partition_id}/link-conversation/{node_id}/{conversation_id}")
async def unlink_conversation(partition_id: str, node_id: str, conversation_id: str):
    graph = _get_graph(partition_id)
    if not graph or node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    node = graph.nodes[node_id]
    conv_ids = list(getattr(node, "conversation_ids", None) or [])
    if conversation_id in conv_ids:
        conv_ids.remove(conversation_id)
    node.conversation_ids = conv_ids

    graph.updated_at = time.time()
    graph.version += 1
    data = _load()
    data.knowledge_graphs[partition_id] = graph
    _save(data)
    return {"ok": True, "conversation_ids": conv_ids}


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/explore — 知识树节点探索对话
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/explore")
async def explore_node(partition_id: str, body: dict):
    """在知识树上点击节点，创建/恢复探索对话。"""
    graph = _get_graph(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="分区不存在")

    node_id = body.get("node_id", "")
    node_label = body.get("node_label", "")
    node_level = body.get("node_level", "concept")

    if node_id and node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    try:
        conv = tree_ops.ensure_tree_exploration(
            _USER_ID, partition_id, node_id, node_label, node_level,
        )

        # 绑定到 KGNode 的 conversation_ids
        if node_id and node_id in graph.nodes:
            bound_node = graph.nodes[node_id]
            conv_ids = list(getattr(bound_node, "conversation_ids", None) or [])
            if conv.id not in conv_ids:
                conv_ids.append(conv.id)
                bound_node.conversation_ids = conv_ids
                data = _load()
                data.knowledge_graphs[partition_id] = graph
                _save(data)

        # 返回已有消息
        data = _load()
        messages = []
        for nid in conv.path:
            node = data.nodes.get(nid)
            if node and not node.is_deleted and node.text_summary != "[virtual_root]":
                messages.append(node.model_dump(mode="json"))

        return {"ok": True, "conversation_id": conv.id, "messages": messages}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to explore node")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════════════════════════
# POST /{partition_id}/ai-chat — AI 对话帮助编辑知识树
# ═══════════════════════════════════════════════════════════

@router.post("/{partition_id}/ai-chat")
async def ai_chat(partition_id: str, body: AiChatRequest):
    """与 AI 对话，帮助编辑/操作知识树。

    每个节点绑定一个独立的「知识树探索」会话，会话仅允许修改该节点及其子孙节点。
    若用户意图操作其他节点，系统提示切换到对应节点的探索会话。
    """
    from app.services.knowledge.tree_ops import tree_ops
    from shared.constants import DEFAULT_USER_ID

    graph = _get_graph(partition_id)
    if not graph:
        raise HTTPException(status_code=404, detail="分区不存在")

    if body.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail="节点不存在")

    data = _load()
    partition = data.partitions.get(partition_id)
    bound_node = graph.nodes[body.node_id]
    scope_ids = _get_descendant_ids(graph, body.node_id)
    scope_labels = {nid: graph.nodes[nid].label for nid in scope_ids}

    # ── 查找或创建「知识树探索」会话 ──
    conversation_id = body.conversation_id
    if not conversation_id:
        conv_ids = getattr(bound_node, "conversation_ids", None) or []
        for cid in conv_ids:
            conv = data.conversations.get(cid)
            if conv and conv.metadata.get("type") == "tree_exploration":
                conversation_id = cid
                break

        if not conversation_id:
            # 使用新方法：自动补全层级创建探索会话
            try:
                conversation = tree_ops.ensure_tree_exploration(
                    DEFAULT_USER_ID, partition_id, body.node_id,
                    bound_node.label, "concept",
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            conversation_id = conversation.id

            bound_node.conversation_ids = list(set(bound_node.conversation_ids or []) | {conversation_id})
            data.knowledge_graphs[partition_id] = graph
            _save(data)
        else:
            conv = data.conversations.get(conversation_id)
            existing_bound = conv.metadata.get("bound_node_id", "") if conv else ""
            if existing_bound and existing_bound != body.node_id:
                existing_label = graph.nodes[existing_bound].label if existing_bound in graph.nodes else "未知"
                return {
                    "ok": False,
                    "error": "scope_mismatch",
                    "message": f"当前操作节点「{bound_node.label}」与探索会话绑定的节点「{existing_label}」不一致，请切换到对应节点的探索会话。",
                    "bound_node_id": existing_bound,
                    "bound_node_label": existing_label,
                }

    # ── 构建作用域上下文 ──
    scope_context = {
        "bound_node_id": body.node_id,
        "bound_node_label": bound_node.label,
        "bound_node_desc": bound_node.description or "",
        "scope_node_ids": list(scope_ids),
        "scope_labels": scope_labels,
        "all_nodes": {
            nid: {"label": n.label, "description": n.description}
            for nid, n in graph.nodes.items()
        },
    }

    try:
        from app.services.llm.llm_service import llm_service

        system_prompt = f"""你是知识树编辑助手，严格遵循作用域规则。

## 当前作用域
- 分区: {partition.name or '未知'}
- 绑定节点: {bound_node.label}（ID: {body.node_id}）
- 描述: {bound_node.description or '无'}
- 作用域内节点（可操作）:
  {', '.join(f'  [{nid}] {label}' for nid, label in scope_labels.items())}

## 严格规则
1. 【作用域限制】你只能编辑、扩充、删除上列「作用域内节点」。
2. 【禁止越界】如果用户提及作用域外的节点，不要执行任何操作，回复：
   "⚠️ 节点「X」不在当前探索会话的作用域内。请先点击该节点，在详情面板中启动它的探索会话。"
3. 【禁止越界】如果用户要求创建与当前知识树无关的节点（新学科/领域），回复：
   "⚠️ 该内容不在当前知识树的范围内。请到对话系统创建新的分区，知识树会自动生成。"
4. 【父节点不可操作】如果用户要求编辑当前节点的父节点，回复：
   "⚠️ 父节点「X」不在当前探索会话的作用域内。请先选中父节点，在它的详情面板中启动探索会话。"
5. 你仅提供建议，不直接修改数据。

## 双向推荐（重要！）
当以下情况发生时，在回复末尾添加推荐标记：

### A. 探索完成
用户表达「探索完成/差不多了/够了/结束了」意图时，回复末尾加上：
[RECOMMEND:tree_complete:node_id]
示例回复：已经完成了对「xxx」的知识探索！[RECOMMEND:tree_complete]

### B. 深入兴趣
用户对作用域内某个具体子节点表现出浓厚兴趣（反复追问细节、想深入学习）时，回复末尾加上：
[RECOMMEND:deep_dive:节点ID:节点标签]
示例回复：你对「微积分」好像很感兴趣！[RECOMMEND:deep_dive:xxxx-xxxx-xxxx:微积分]

### C. 父节点关联
用户提及当前节点的父节点内容时，回复末尾加上：
[RECOMMEND:parent:父节点ID:父节点标签]
示例回复：这个知识点属于「高等数学」。[RECOMMEND:parent:yyyy-yyyy:高等数学]

## 可用操作格式
[ACTION:add_node] 节点名: 描述
[ACTION:edit_node:node_id] 修改: 新描述
[ACTION:add_edge] from_node_id -> to_node_id

## 当前全量节点（仅参考，不可越界操作）
{_json.dumps(scope_context["all_nodes"], ensure_ascii=False)}
"""

        response = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.message},
            ],
            temperature=0.7, max_tokens=4096,
        )

        # ── 解析双向推荐标记 ──
        conversation_recommendation = None
        rec_match = re.search(
            r'\[RECOMMEND:(tree_complete|deep_dive|parent)(?::([^:]*))?(?::([^\]]*))?\]',
            response,
        )
        if rec_match:
            rec_type = rec_match.group(1)
            rec_node_id = rec_match.group(2) or ""
            rec_node_label = rec_match.group(3) or ""

            if rec_type == "tree_complete":
                conversation_recommendation = {
                    "type": "exploration_complete",
                    "message": "知识树探索已完成！建议到对话系统中深入学习具体知识点。",
                    "partition_id": partition_id,
                    "partition_name": partition.name if partition else "",
                }
            elif rec_type == "deep_dive" and rec_node_id:
                target_node = graph.nodes.get(rec_node_id)
                target_label = rec_node_label or (target_node.label if target_node else "")
                suggested_conv_id = None
                if target_node:
                    conv_ids = getattr(target_node, "conversation_ids", None) or []
                    for cid in conv_ids:
                        conv = data.conversations.get(cid)
                        if conv and conv.metadata.get("type") != "tree_exploration":
                            suggested_conv_id = cid
                            break
                conversation_recommendation = {
                    "type": "deep_dive",
                    "message": f"对「{target_label}」很感兴趣？可以去对话系统深入探讨。",
                    "node_id": rec_node_id,
                    "node_label": target_label,
                    "partition_id": partition_id,
                    "suggested_conversation_id": suggested_conv_id or "",
                }
            elif rec_type == "parent":
                target_node = graph.nodes.get(rec_node_id)
                target_label = rec_node_label or (target_node.label if target_node else "")
                conversation_recommendation = {
                    "type": "parent_reference",
                    "message": f"这个知识属于「{target_label}」，建议切换到该节点的探索会话。",
                    "node_id": rec_node_id,
                    "node_label": target_label,
                    "partition_id": partition_id,
                }

        # 清理回复中的推荐标记
        cleaned_response = re.sub(r'\s*\[RECOMMEND:[^\]]*\]', '', response).strip()

        tree_ops.add_message(
            DEFAULT_USER_ID, partition_id, "user",
            [{"type": "text", "content": body.message}],
            text_summary=body.message[:100],
            conversation_id=conversation_id,
        )
        tree_ops.add_message(
            DEFAULT_USER_ID, partition_id, "assistant",
            [{"type": "text", "content": cleaned_response}],
            text_summary=cleaned_response[:100],
            conversation_id=conversation_id,
        )

        result = {
            "ok": True,
            "response": cleaned_response,
            "conversation_id": conversation_id,
            "node_id": body.node_id,
            "scope_node_ids": list(scope_ids),
            "scope_labels": scope_labels,
        }
        if conversation_recommendation:
            result["conversation_recommendation"] = conversation_recommendation

        return result

    except Exception as e:
        logger.error(f"AI 对话失败: {e}")
        return {"ok": False, "error": str(e)}
