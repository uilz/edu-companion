"""AI 知识树展开服务

提取自原 knowledge_graph_ai.py 的 ai_expand_node 端点，
供 /api/knowledge-graph/ai/expand 与 LLM Function Calling 工具共用，
避免 API 路由被业务工具直接依赖。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.knowledge_tree.knowledge_node_service import kn_svc

logger = logging.getLogger(__name__)


async def expand_node(
    user_id: str,
    node_id: str,
    depth: int,
    direction: str,
) -> dict[str, Any]:
    """为指定节点 AI 生成子节点/父节点/双向扩展，返回新增节点与边。"""
    target = kn_svc.get_node(user_id, node_id)
    if not target:
        return {"ok": False, "error": "节点不存在"}

    all_nodes = kn_svc.list_nodes(user_id)
    existing_labels = {n.label for n in all_nodes}

    direction_text = {
        "children": "子节点（更深入的知识点）",
        "parents": "父节点（前置知识）",
        "both": "子节点和父节点",
    }.get(direction, "子节点")

    try:
        from app.infrastructure.llm.llm_service import llm_service

        prompt = f"""你是知识图谱扩充专家。当前知识树中节点「{target.label}」需要扩充{direction_text}。

目标节点: {target.label} (层级: {target.level})
目标节点描述: {target.brief or '无'}
生成深度: {depth} 层
现有节点（不要重复）: {json.dumps(list(existing_labels), ensure_ascii=False)}

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
                {"role": "user", "content": f"为节点「{target.label}」扩充{direction_text}，{depth}层深度"},
            ],
            temperature=0.3,
            max_tokens=8192,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)

        label_to_id: dict[str, str] = {target.label: node_id}
        added_nodes = []

        child_parent_id = node_id if direction in ("children", "both") else None

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

    except json.JSONDecodeError as e:
        logger.error("AI 展开 JSON 解析失败: %s, raw=%s", e, raw[:200] if "raw" in dir() else "N/A")
        return {"ok": False, "error": f"AI 返回格式错误: {str(e)}"}
    except Exception as e:
        logger.exception("AI 扩充节点失败")
        return {"ok": False, "error": str(e)}
