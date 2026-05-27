"""
知识图谱 + 前置知识卡控 REST API

端点:
  GET  /api/knowledge/graph          — 获取知识图谱 (nodes + edges + mastery)
  GET  /api/knowledge/prerequisites  — 获取指定技能的前置依赖
  POST /api/knowledge/check          — 检查用户是否可以练习某技能
  GET  /api/knowledge/blocked        — 获取用户被卡控的技能清单
  GET  /api/knowledge/ready          — 获取用户可练习的技能清单
  GET  /api/knowledge/path           — 获取最优学习路径
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import networkx as nx
from fastapi import APIRouter, HTTPException, Query

from app.shared.constants import DEFAULT_USER_ID
from app.core.knowledge_trace import bkt_engine
from domain.knowledge.checker import PrerequisiteChecker
from domain.knowledge.prerequisites import (
    ALL_PREREQUISITES,
    SKILL_TO_SUBJECT,
    SUBJECT_SKILLS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识图谱"])


# ── Adapter: 将现有 BKT 引擎适配到 PrerequisiteChecker 接口 ──

class _BKTKnowledgeAdapter:
    """BKT 引擎 → PracticeService.get_knowledge_state 适配器

    Phase 6: 优先读 CognitiveNode，备降 BKT
    """
    async def get_knowledge_state(self, user_id: str, skill_id: str):
        # CognitiveNode 主源
        try:
            from app.cognitive.storage import get_node
            node = get_node(skill_id, user_id)
            if node and node.belief:
                return {
                    "skill_id": skill_id,
                    "p_known": node.belief.proficiency_mean,
                    "attempt_count": node.practice_summary.total_attempts if node.practice_summary else 0,
                    "correct_count": node.practice_summary.correct_attempts if node.practice_summary else 0,
                    "mastery_level": _cognitive_mastery_level(node.belief.proficiency_mean),
                    "source": "cognitive_node",
                }
        except Exception:
            pass

        # 备降: 旧 BKT
        state = bkt_engine.load_or_create(user_id, skill_id)
        return state.model_dump()


def _cognitive_mastery_level(p: float) -> str:
    if p >= 0.9:  return "已掌握"
    if p >= 0.7:  return "接近掌握"
    if p >= 0.4:  return "发展中"
    if p > 0.0:   return "初学"
    return "未接触"


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
    user_id: str = DEFAULT_USER_ID,
    subject: Optional[str] = None,
):
    """
    获取用户的知识图谱

    返回:
      nodes: 知识点节点 (含掌握度)
      edges: 前置依赖关系
    """
    checker = _get_checker()
    prerequisites = ALL_PREREQUISITES

    # 确定要显示的技能
    if subject and subject in SUBJECT_SKILLS:
        skills = SUBJECT_SKILLS[subject]
    else:
        skills = list(prerequisites.keys())

    # 节点
    nodes = []
    for skill_id in skills:
        state = bkt_engine.load_or_create(user_id, skill_id)
        result = await checker.can_practice(user_id, skill_id)

        nodes.append({
            "id": skill_id,
            "label": checker._skill_display_name(skill_id),
            "subject": SKILL_TO_SUBJECT.get(skill_id, "未知"),
            "mastery": round(state.p_known * 100, 1),
            "mastery_level": bkt_engine.get_mastery_level(state),
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
# GET /api/knowledge/prerequisites
# ═══════════════════════════════════════════════════════════

@router.get("/prerequisites")
async def get_prerequisites(skill_id: str = Query(..., description="知识点ID")):
    """获取指定技能的前置依赖"""
    checker = _get_checker()
    try:
        result = await checker.get_prerequisites(skill_id)
        return result
    except Exception:
        raise HTTPException(status_code=404, detail=f"未知技能: {skill_id}")


# ═══════════════════════════════════════════════════════════
# POST /api/knowledge/check
# ═══════════════════════════════════════════════════════════

from pydantic import BaseModel

class CheckRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    skill_ids: list[str]

@router.post("/check")
async def check_prerequisites(req: CheckRequest):
    """
    批量检查前置条件

    请求体: {"user_id": "u1", "skill_ids": ["calculus_derivative", "calculus_integral"]}
    返回: 每个技能的前置检查结果
    """
    checker = _get_checker()
    results = await checker.check_batch(req.user_id, req.skill_ids)
    return {
        "results": {sid: r.to_dict() for sid, r in results.items()},
        "all_pass": all(r.can_practice for r in results.values()),
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/blocked
# ═══════════════════════════════════════════════════════════

@router.get("/blocked")
async def get_blocked_skills(user_id: str = DEFAULT_USER_ID):
    """获取用户被前置知识卡控的所有技能"""
    checker = _get_checker()
    blocked = await checker.get_blocked_skills(user_id)
    return {
        "blocked": blocked,
        "total": len(blocked),
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/ready
# ═══════════════════════════════════════════════════════════

@router.get("/ready")
async def get_ready_skills(
    user_id: str = DEFAULT_USER_ID,
    subject: Optional[str] = None,
):
    """获取用户当前可以练习的技能清单"""
    checker = _get_checker()
    skills = await checker.find_ready_skills(user_id, subject)
    return {
        "ready": skills,
        "total": len(skills),
        "subject": subject,
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/path
# ═══════════════════════════════════════════════════════════

@router.get("/path")
async def get_learning_path(
    user_id: str = DEFAULT_USER_ID,
    target_skill: str = Query(..., description="目标知识点ID"),
):
    """
    获取最优学习路径（拓扑排序 + 当前掌握度过滤）

    返回从用户当前已掌握知识到目标技能的最短路径
    """
    checker = _get_checker()
    prerequisites = ALL_PREREQUISITES

    if target_skill not in prerequisites:
        raise HTTPException(status_code=404, detail=f"未知技能: {target_skill}")

    # BFS 收集目标技能的所有传递前置
    all_prereqs: set[str] = set()

    def collect(skill_id: str):
        for p in prerequisites.get(skill_id, []):
            if p not in all_prereqs:
                all_prereqs.add(p)
                collect(p)

    collect(target_skill)

    # 过滤已掌握的
    path = []
    missing: list[str] = []
    for skill_id in sorted(all_prereqs, key=lambda s: checker._compute_depth(s)):
        state = bkt_engine.load_or_create(user_id, skill_id)
        if state.p_known >= 0.7:
            path.append({"skill_id": skill_id, "status": "已掌握",
                         "mastery": round(state.p_known * 100)})
        else:
            missing.append(skill_id)
            path.append({"skill_id": skill_id, "status": "待学习",
                         "mastery": round(state.p_known * 100)})

    # 目标技能本身
    target_state = bkt_engine.load_or_create(user_id, target_skill)
    path.append({"skill_id": target_skill, "status": "🎯 目标",
                 "mastery": round(target_state.p_known * 100)})

    return {
        "target": target_skill,
        "path": path,
        "total_steps": len(path),
        "mastered_count": sum(1 for p in path if p["status"] == "已掌握"),
        "remaining_count": len(missing),
        "remaining_skills": missing,
    }


# ═══════════════════════════════════════════════════════════
# GET /api/knowledge/retention
# ═══════════════════════════════════════════════════════════

@router.get("/retention")
async def get_retention_curve(user_id: str = DEFAULT_USER_ID):
    """
    获取遗忘曲线（艾宾浩斯估算）。

    对用户已练习过的所有技能，估算随时间推移的知识保留率。
    基于: retention = e^(-days / S)，其中 S 由 p_known 和 attempt_count 决定。
    """
    import math

    prerequisites = ALL_PREREQUISITES
    skills = []
    now = datetime.now()

    for skill_id in prerequisites:
        state = bkt_engine.load_or_create(user_id, skill_id)
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
