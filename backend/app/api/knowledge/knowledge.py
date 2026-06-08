"""
知识图谱 + 前置知识卡控 REST API

端点:
  GET  /api/knowledge/graph          — 获取知识图谱 (nodes + edges + mastery)
"""
from __future__ import annotations

import logging
from typing import Optional

import networkx as nx
from fastapi import APIRouter

from app.domain.auth.dependencies import current_user_id, get_mastery_label
from shared.knowledge_trace import get_cognitive_state
from app.domain.knowledge.checker import PrerequisiteChecker
from app.domain.knowledge.prerequisites import (
    SKILL_TO_SUBJECT,
    SUBJECT_SKILLS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识图谱"])


# ── Adapter: 将现有 BKT 引擎适配到 PrerequisiteChecker 接口 ──
# Canonical version in app.services.knowledge_state
from app.services.knowledge.knowledge_state import get_knowledge_state as _canonical_get_ks

class _BKTKnowledgeAdapter:
    """BKT 引擎 → PracticeService.get_knowledge_state 适配器"""
    async def get_knowledge_state(self, user_id: str, skill_id: str):
        return await _canonical_get_ks(user_id, skill_id)


def _get_checker() -> PrerequisiteChecker:
    return PrerequisiteChecker(_BKTKnowledgeAdapter())


# ── Force-Directed Layout ──

def compute_force_layout(nodes: list[dict], edges: list[dict]) -> dict[str, tuple[float, float]]:
    """
    使用改进力导向算法计算节点坐标。

    策略：在 Fruchterman-Reingold 基础上加中心引力，
    使根节点（无前置依赖）靠近中心，子节点自然向外延展。
    返回 {node_id: (x, y)}，坐标范围约 (50,50) ~ (750,550)。
    """
    import math

    if len(nodes) <= 1:
        return {nodes[0]["id"]: (400, 300)} if nodes else {}

    n_count = len(nodes)
    node_ids = [n["id"] for n in nodes]
    id_to_node = {n["id"]: n for n in nodes}

    # ── 计算每个节点的深度（从前置依赖树）──
    children: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for e in edges:
        children.setdefault(e["from"], []).append(e["to"])
        in_degree[e["to"]] = in_degree.get(e["to"], 0) + 1

    depth: dict[str, int] = {}
    queue = [nid for nid in node_ids if in_degree.get(nid, 0) == 0]
    for nid in queue:
        depth[nid] = 0
    while queue:
        cur = queue.pop(0)
        for child in children.get(cur, []):
            new_d = depth[cur] + 1
            if child not in depth or depth[child] < new_d:
                depth[child] = new_d
                if child not in queue:
                    queue.append(child)
    max_depth = max(depth.values()) if depth else 1

    # ── 按学科分组做初始位置 ──
    subjects: dict[str, list[str]] = {}
    for n in nodes:
        subj = n.get("subject", "其他")
        subjects.setdefault(subj, []).append(n["id"])

    # 初始环形排列 — 深度决定半径
    W, H = 700, 500
    cx, cy = W / 2 + 50, H / 2 + 50
    pos: dict[str, list[float]] = {}
    for nid in node_ids:
        d = depth.get(nid, max_depth // 2)
        radius = 50 + (d / max(max_depth, 1)) * 280
        # 按学科分配角度
        subj = id_to_node[nid].get("subject", "其他")
        subj_list = list(subjects.keys())
        angle_base = (subj_list.index(subj) / max(len(subj_list), 1)) * 2 * math.pi
        # 同科内分散
        idx_in_subj = subjects[subj].index(nid) if nid in subjects.get(subj, []) else 0
        total_in_subj = max(len(subjects.get(subj, [])), 1)
        angle = angle_base + (idx_in_subj / total_in_subj) * (2 * math.pi / max(len(subj_list), 1))
        pos[nid] = [
            cx + radius * math.cos(angle),
            cy + radius * math.sin(angle),
        ]

    # ── 构建 networkx 图并运行 spring_layout（少量迭代微调）──
    G = nx.Graph()
    G.add_nodes_from(node_ids)
    for e in edges:
        G.add_edge(e["from"], e["to"], weight=2.0)

    area = W * H
    k = math.sqrt(area / n_count) * 0.6  # 紧凑一些

    pos = nx.spring_layout(
        G, pos=pos, k=k, iterations=60, seed=42, scale=300,
        threshold=1e-3, weight="weight", center=(0, 0), fixed=None,
    )

    # 平移使所有坐标为正（留 50px 边距）
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    offset_x = 50 - min(xs)
    offset_y = 50 - min(ys)

    result: dict[str, tuple[float, float]] = {}
    for nid, (x, y) in pos.items():
        result[nid] = (round(x + offset_x, 1), round(y + offset_y, 1))
    return result


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/graph
# ═══════════════════════════════════════════════════════════

@router.get("/graph")
async def get_knowledge_graph(
    user_id: str = Depends(current_user_id),
    subject: Optional[str] = None,
    partition_id: Optional[str] = None,
):
    """
    获取用户的知识图谱

    数据源: 知识树优先，回退硬编码

    返回:
      nodes: 知识点节点 (含掌握度)
      edges: 前置依赖关系
    """
    checker = _get_checker()

    # ── 动态加载: 知识树优先 ──
    if partition_id:
        checker.load_from_knowledge_tree(user_id, partition_id)
    prerequisites = checker._prerequisites

    # 确定要显示的技能
    if subject and subject in SUBJECT_SKILLS:
        skills = SUBJECT_SKILLS[subject]
    else:
        skills = list(prerequisites.keys())

    # 节点
    nodes = []
    for skill_id in skills:
        state = get_cognitive_state(user_id, skill_id)
        result = await checker.can_practice(user_id, skill_id)

        nodes.append({
            "id": skill_id,
            "label": checker._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "mastery_level": get_mastery_label(state.p_known, state.attempt_count),
            "can_practice": result.can_practice,
            "blocked_by": result.blocked,
            "attempt_count": state.attempt_count,
        })

    # 边
    edges = []
    for skill_id, prereqs in prerequisites.items():
        if skill_id not in skills:
            continue
        for prereq_id in prereqs:
            edges.append({
                "from": prereq_id,
                "to": skill_id,
                "label": "前置",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "subjects": list(SUBJECT_SKILLS.keys()),
        "layout": compute_force_layout(nodes, edges),
    }


# ═══════════════════════════════════════════════════════════
# POST /api/knowledge/explain
# ═══════════════════════════════════════════════════════════

@router.post("/explain")
async def explain_knowledge(body: dict):
    """
    用 AI 解释知识点或用户选中的文字。

    请求体:
    {
        "text": "选中/提问的文本",
        "node_id": "可选的知识图谱节点ID",
        "style": "simple | conversation"
    }

    返回:
    { "explanation": "..." }
    """
    text = body.get("text", "")
    node_id = body.get("node_id")
    style = body.get("style", "simple")

    if not text.strip():
        return {"explanation": "请提供需要解释的文本"}

    from app.services.llm.llm_service import llm_service

    if style == "conversation":
        system_prompt = (
            "你是智能伴学助手，以苏格拉底式对话引导学生思考。"
            "根据上下文，用简洁易懂的语言回答学生的问题。"
            "如果适合，可以反问引导学生深入思考。不要超过200字。"
        )
        user_prompt = f"学生提问：{text}"
    else:
        context_hint = f"（知识点ID: {node_id}）" if node_id else ""
        system_prompt = (
            "你是智能伴学助手。用简洁易懂的语言解释知识点，"
            "适合中学生理解。可以适当举例子。控制在300字以内。"
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


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/retention
# ═══════════════════════════════════════════════════════════

@router.get("/retention")
async def get_retention_curve(user_id: str = Depends(current_user_id)):
    """
    获取遗忘曲线（艾宾浩斯估算）。

    对用户已练习过的所有技能，估算随时间推移的知识保留率。
    基于: retention = e^(-days / S)，其中 S 由 p_known 和 attempt_count 决定。
    """
    import math

    prerequisites = _get_checker()._prerequisites
    skills = []

    for skill_id in prerequisites:
        state = get_cognitive_state(user_id, skill_id)
        if state.attempt_count == 0:
            continue  # 未练习过的技能跳过

        # 估算记忆强度 S: 掌握度越高、练习次数越多 → S 越大
        S = max(1.0, state.p_known * 30 + math.log(state.attempt_count + 1) * 5)

        # 假设上次练习是 now（简化处理）
        points = []
        for days in [0, 1, 3, 7, 14, 30, 60, 90]:
            retention = round(math.exp(-days / S) * 100, 1)
            points.append({"day": days, "retention": min(retention, 100)})

        skills.append({
            "skill_id": skill_id,
            "label": _get_checker()._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "attempt_count": state.attempt_count,
            "curve": points,
        })

    # 按掌握度排序（低的在前——更需要复习）
    skills.sort(key=lambda s: s["mastery"])

    return {
        "user_id": user_id,
        "skills": skills,
        "total": len(skills),
        "avg_retention_7d": round(
            sum(s["curve"][3]["retention"] for s in skills) / max(len(skills), 1), 1
        ) if skills else 0,
        "at_risk": [s for s in skills if s["curve"][3]["retention"] < 50],  # 7天后保持率<50%
    }
