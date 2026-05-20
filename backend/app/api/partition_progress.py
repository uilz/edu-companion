"""
分区学习进度画像 API

端点:
  GET /{partition_id}           — 完整分区进度画像
  GET /student-profile          — 跨分区全局画像
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas.learning_profile import (
    Anomaly,
    Coverage,
    Dependency,
    LearningPath,
    PartitionProgress,
    PathDeviation,
    SkillCluster,
    SkillNodeState,
    TemporalMetrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partition-progress", tags=["学习画像"])


def _get_user_data():
    from app.services.storage import storage
    return storage.load("default_user")


def _compute_partition_progress(partition_id: str) -> PartitionProgress:
    """从旧数据（knowledge_graphs + knowledge_states + practice_sessions）构建 PartitionProgress"""
    data = _get_user_data()

    partition = data.partitions.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="分区不存在")

    graph = data.knowledge_graphs.get(partition_id)
    knowledge_states = getattr(data, "knowledge_states", {}) or {}

    pp = PartitionProgress(
        partition_id=partition_id,
        partition_name=partition.name,
        partition_emoji=getattr(partition, "emoji", "📁"),
    )

    if not graph or not graph.nodes:
        return pp  # 空图谱 → 空画像

    # ── 1. 构建 SkillNodeState ──
    skills: dict[str, SkillNodeState] = {}
    for node_id, node in graph.nodes.items():
        # 从 BKT 获取掌握度
        ks = knowledge_states.get(node_id)
        mastery = 0.0
        mastery_level = "未接触"
        if ks:
            p_know = ks.get("p_know", 0.1)
            mastery = round(p_know * 100, 1)
            mastery_level = _classify_mastery(p_know)

        # 拓扑深度（入度为0的根节点=0层）
        depth = 0
        prereq_ids = [e.from_id for e in graph.edges if e.to_id == node_id]
        if prereq_ids:
            depth = _compute_depth(node_id, graph, set())

        # 前置是否满足
        prereqs_met = all(
            knowledge_states.get(pid, {}).get("p_know", 0.0) >= 0.8
            for pid in prereq_ids
        )

        skills[node_id] = SkillNodeState(
            skill_id=node_id,
            label=node.label,
            description=node.description or "",
            mastery=mastery,
            mastery_level=mastery_level,
            depth=depth,
            prerequisites=prereq_ids,
            prerequisites_met=prereqs_met or len(prereq_ids) == 0,
            blocked=not prereqs_met and len(prereq_ids) > 0,
        )

    # ── 2. 构建依赖 ──
    dependencies = []
    for edge in graph.edges:
        from_skill_node = skills.get(edge.from_id)
        satisfied = from_skill_node and from_skill_node.mastery >= 80
        dependencies.append(Dependency(
            from_skill=edge.from_id,
            to_skill=edge.to_id,
            relation=edge.relation or "prerequisite",
            satisfied=satisfied,
        ))

    # ── 3. 覆盖率 ──
    total = len(skills)
    touched = sum(1 for s in skills.values() if (ks := knowledge_states.get(s.skill_id)))
    mastered = sum(1 for s in skills.values() if s.mastery_level == "已掌握")
    learning = sum(1 for s in skills.values() if s.mastery_level in ("发展中", "接近掌握"))
    weak = sum(1 for s in skills.values() if s.mastery_level == "初学")
    pp.coverage = Coverage(
        total=total,
        touched=touched,
        assessed=touched,  # 兼容
        mastered=mastered,
        learning=learning,
        weak=weak,
        untouched=total - touched,
    )

    # ── 4. 学习路径 ──
    ideal_order = _topological_order(skills, graph)
    actual_order = []   # v1: 暂从 practice_sessions 推断

    frontier = [
        sid for sid in ideal_order
        if skills[sid].blocked is False and skills[sid].mastery < 80
    ]
    review_queue = [
        sid for sid, s in skills.items()
        if s.mastery >= 80  # 已掌握但可能遗忘
    ][:5]

    pr_edges = [e for e in graph.edges if e.relation == "prerequisite"]
    pp.learning_path = LearningPath(
        ideal_order=ideal_order,
        actual_order=actual_order,
        frontier=frontier,
        review_queue=review_queue,
    )

    # ── 5. 异常检测 ──
    anomalies = []
    for sid, s in skills.items():
        # 跳过前置但学到了后置
        if s.blocked and s.mastery > 60:
            anomalies.append(Anomaly(
                type="mastered_without_prereq",
                skills=[sid],
                detail=f"前置未满足但掌握度已达{s.mastery}%，依赖关系可能不准确",
                severity="warning",
            ))
        # 长期停滞
        if s.mastery_level in ("发展中", "初学"):
            if ks := knowledge_states.get(sid):
                n_obs = ks.get("n_observations", 0)
                if n_obs >= 5 and s.mastery < 50:
                    anomalies.append(Anomaly(
                        type="long_stagnation",
                        skills=[sid],
                        detail=f"已练习{n_obs}次但掌握度仅{s.mastery}%",
                        severity="warning",
                    ))

    pp.anomalies = anomalies

    # ── 6. 时序指标 ──
    pp.temporal = TemporalMetrics(
        learning_velocity=0.0,   # v2: 从事件日志计算
        estimated_completion_days=_estimate_completion(total, mastered, 0),
        review_backlog=len(review_queue),
    )

    pp.skills = skills
    pp.dependencies = dependencies
    pp.generated_at = datetime.now(timezone.utc)

    return pp


def _classify_mastery(p_know: float) -> str:
    if p_know >= 0.9:  return "已掌握"
    if p_know >= 0.7:  return "接近掌握"
    if p_know >= 0.4:  return "发展中"
    if p_know > 0.0:   return "初学"
    return "未接触"


def _compute_depth(node_id: str, graph, visited: set) -> int:
    if node_id in visited:
        return 0
    visited.add(node_id)
    prereqs = [e.from_id for e in graph.edges if e.to_id == node_id]
    if not prereqs:
        return 0
    return 1 + max(_compute_depth(p, graph, visited) for p in prereqs)


def _topological_order(skills: dict, graph) -> list[str]:
    """拓扑排序 — 前置依赖优先"""
    in_degree: dict[str, int] = {}
    adj: dict[str, list[str]] = {}
    for sid in skills:
        in_degree[sid] = 0
        adj[sid] = []
    for e in graph.edges:
        if e.from_id in skills and e.to_id in skills:
            in_degree[e.to_id] = in_degree.get(e.to_id, 0) + 1
            adj[e.from_id].append(e.to_id)

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result = []
    while queue:
        node_id = queue.pop(0)
        result.append(node_id)
        for child in adj.get(node_id, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return result


def _estimate_completion(total: int, mastered: int, velocity: float) -> int:
    remaining = total - mastered
    if remaining <= 0:
        return 0
    v = velocity if velocity > 0 else 1.0   # 保守估计每天1个
    return max(1, int(remaining / v))


# ═══════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════

@router.get("/{partition_id}", response_model=PartitionProgress)
async def get_partition_progress(partition_id: str):
    """获取分区的完整学习进度画像"""
    return _compute_partition_progress(partition_id)
