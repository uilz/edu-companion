"""
分区学习进度画像 API (v3 — CognitiveNode 主源)

数据源优先级:
  1. cognitive_nodes 表 (Phase 6, 首选)
  2. 旧 userData JSON (向后兼容备降)

端点:
  GET /{partition_id}           — 完整分区进度画像
  GET /student-profile          — 跨分区全局画像
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

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


# ═══════════════════════════════════════════════════
# 双源读取: CognitiveNode (主) + 旧 JSON (备降)
# ═══════════════════════════════════════════════════


def _has_cognitive_nodes(user_id: str = "default_user") -> bool:
    """检查用户是否有 CognitiveNode 数据"""
    try:
        from app.cognitive.storage import get_node
        # 尝试读取一个任意节点判断数据是否存在
        from app.db.database import get_db
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM cognitive_nodes WHERE user_id = %s",
            (user_id,)
        )
        return row and row["cnt"] > 0
    except Exception:
        return False


def _get_user_data():
    """旧 JSON 存储 — 向后兼容"""
    from app.services.storage import storage
    return storage.load("default_user")


# ═══════════════════════════════════════════════════
# 源1: CognitiveNode 画像计算
# ═══════════════════════════════════════════════════


def _compute_partition_progress_cognitive(partition_id: str) -> PartitionProgress | None:
    """
    从 cognitive_nodes 表计算分区进度画像。

    返回 None 表示无数据 (触发备降)。
    """
    try:
        from app.cognitive.storage import get_node, get_children
        from app.cognitive.models import CognitiveNode

        partition_node = get_node(partition_id)
        if not partition_node:
            logger.info(f"[cognitive] 分区节点不存在: {partition_id}")
            return None

        # 获取分区下所有子节点 (递归)
        all_nodes: dict[str, CognitiveNode] = {partition_id: partition_node}
        _collect_subtree(partition_id, all_nodes)

        # 筛选 atom/concept 级别节点作为技能节点
        skill_nodes = {
            nid: n for nid, n in all_nodes.items()
            if n.level in ("atom", "concept") and n.belief
        }

        # ── 构建 SkillNodeState ──
        skills: dict[str, SkillNodeState] = {}
        for nid, n in skill_nodes.items():
            mu = n.belief.proficiency_mean if n.belief else 0.0
            level = _classify_mastery(mu)
            prereq_ids = [p.target_id for p in (n.prerequisites or [])]

            # 前置满足检查
            prereqs_have_data = bool(prereq_ids)
            prereqs_met = all(
                all_nodes.get(pid) and
                (all_nodes[pid].belief.proficiency_mean if all_nodes[pid].belief else 0) >= 0.8
                for pid in prereq_ids
            ) if prereqs_have_data else True

            trend_dir = n.trend.direction if n.trend else "stable"
            urgency = n.scheduling.review_urgency if n.scheduling else 0.0

            skills[nid] = SkillNodeState(
                skill_id=nid,
                label=n.label,
                description="",
                mastery=round(mu * 100, 1),
                mastery_level=level,
                confidence=round(1.0 / (1.0 + (n.belief.beta if n.belief else 10)), 4),
                trend=trend_dir,
                depth=_compute_cognitive_depth(nid, all_nodes),
                prerequisites=prereq_ids,
                prerequisites_met=prereqs_met or not prereqs_have_data,
                blocked=not prereqs_met and prereqs_have_data,
                attempt_count=n.practice_summary.total_attempts if n.practice_summary else 0,
                correct_count=n.practice_summary.correct_attempts if n.practice_summary else 0,
                last_practiced=_ts_from_epoch(n.practice_summary.last_practiced) if n.practice_summary and n.practice_summary.last_practiced else None,
                forgetting_curve=1.0 - urgency if urgency else 1.0,
                review_urgency=urgency,
            )

        # ── 构建依赖 ──
        dependencies = []
        for nid, n in skill_nodes.items():
            for p in (n.prerequisites or []):
                dependencies.append(Dependency(
                    from_skill=p.target_id,
                    to_skill=nid,
                    relation="prerequisite",
                    satisfied=skills.get(p.target_id, SkillNodeState(skill_id="")).mastery >= 80,
                ))
            for u in (n.unlocks or []):
                dependencies.append(Dependency(
                    from_skill=nid,
                    to_skill=u.target_id,
                    relation=u.label or "builds_on",
                    satisfied=skills.get(nid, SkillNodeState(skill_id="")).mastery >= 80,
                ))

        # ── 覆盖率 ──
        total = len(skills)
        mastered = sum(1 for s in skills.values() if s.mastery_level == "已掌握")
        learning = sum(1 for s in skills.values() if s.mastery_level in ("发展中", "接近掌握"))
        weak = sum(1 for s in skills.values() if s.mastery_level == "初学")
        touched = sum(1 for s in skills.values() if s.attempt_count > 0)
        coverage = Coverage(
            total=total,
            touched=touched,
            assessed=touched,
            mastered=mastered,
            learning=learning,
            weak=weak,
            untouched=total - touched,
        )

        # ── 学习路径 ──
        ideal_order = _topological_sort_cognitive(skills, dependencies)
        frontier = [
            sid for sid in ideal_order
            if not skills[sid].blocked and skills[sid].mastery < 80
        ]
        review_queue = sorted(
            [sid for sid, s in skills.items() if s.review_urgency > 0.5 and s.mastery >= 80],
            key=lambda x: skills[x].review_urgency,
            reverse=True,
        )[:5]

        learning_path = LearningPath(
            ideal_order=ideal_order,
            actual_order=[],
            frontier=frontier,
            review_queue=review_queue,
        )

        # ── 异常检测 ──
        anomalies = []
        for sid, s in skills.items():
            if s.blocked and s.mastery > 60:
                anomalies.append(Anomaly(
                    type="mastered_without_prereq",
                    skills=[sid],
                    detail=f"前置未满足但掌握度已达{s.mastery}%",
                    severity="warning",
                ))
            if s.mastery_level in ("发展中", "初学") and s.attempt_count >= 5 and s.mastery < 50:
                anomalies.append(Anomaly(
                    type="long_stagnation",
                    skills=[sid],
                    detail=f"已练习{s.attempt_count}次但掌握度仅{s.mastery}%",
                    severity="warning",
                ))

        # ── 时序指标 ──
        temporal = _compute_temporal_cognitive(skill_nodes)
        temporal.estimated_completion_days = _estimate_completion(total, mastered, temporal.learning_velocity)
        temporal.review_backlog = len(review_queue)

        pp = PartitionProgress(
            partition_id=partition_id,
            partition_name=partition_node.label,
            partition_emoji="📁",
            skills=skills,
            dependencies=dependencies,
            coverage=coverage,
            learning_path=learning_path,
            anomalies=anomalies,
            temporal=temporal,
            generated_at=datetime.now(timezone.utc),
        )
        return pp

    except Exception as e:
        logger.error(f"[cognitive] 画像计算失败: {e}", exc_info=True)
        return None


def _collect_subtree(node_id: str, acc: dict) -> None:
    """递归收集子树节点"""
    from app.cognitive.storage import get_node
    children = get_node(node_id)
    if not children:
        return
    for child_id in (children.children or []):
        if child_id not in acc:
            child = get_node(child_id)
            if child:
                acc[child_id] = child
                _collect_subtree(child_id, acc)


def _compute_cognitive_depth(node_id: str, all_nodes: dict) -> int:
    """计算认知深度 (从根到节点的路径长度)"""
    depth = 0
    current = all_nodes.get(node_id)
    visited = {node_id}
    while current and current.parent and current.parent not in visited:
        visited.add(current.parent)
        current = all_nodes.get(current.parent)
        depth += 1
        if depth > 20:
            break
    return depth


def _topological_sort_cognitive(skills: dict, dependencies: list) -> list[str]:
    """拓扑排序"""
    in_degree: dict[str, int] = {sid: 0 for sid in skills}
    adj: dict[str, list[str]] = {sid: [] for sid in skills}
    for dep in dependencies:
        if dep.from_skill in skills and dep.to_skill in skills:
            in_degree[dep.to_skill] += 1
            adj[dep.from_skill].append(dep.to_skill)
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result = []
    while queue:
        sid = queue.pop(0)
        result.append(sid)
        for child in adj.get(sid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return result


def _compute_temporal_cognitive(skill_nodes: dict) -> TemporalMetrics:
    """从 CognitiveNode 趋势数据计算时序指标"""
    velocities = []
    for n in skill_nodes.values():
        if n.trend and n.trend.velocity:
            velocities.append(n.trend.velocity)
    avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

    backlog = sum(
        1 for n in skill_nodes.values()
        if n.scheduling and n.scheduling.review_urgency > 0.5
    )

    return TemporalMetrics(
        learning_velocity=round(avg_velocity, 2),
        daily_practice_minutes=0.0,
        review_backlog=backlog,
    )


def _ts_from_epoch(ts: float | int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ═══════════════════════════════════════════════════
# 源2: 旧 JSON 备降画像计算
# ═══════════════════════════════════════════════════


def _compute_partition_progress_legacy(partition_id: str) -> PartitionProgress | None:
    """从旧 JSON 数据计算 — 向后兼容备降"""
    data = _get_user_data()

    partition = data.partitions.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="分区不存在")

    graph = data.knowledge_graphs.get(partition_id)
    knowledge_states = getattr(data, "knowledge_states", {}) or {}

    if not graph or not graph.nodes:
        return None  # 空图谱 → 空画像

    pp = PartitionProgress(
        partition_id=partition_id,
        partition_name=partition.name,
        partition_emoji=getattr(partition, "emoji", "📁"),
    )

    # ── 1. 构建 SkillNodeState ──
    skills: dict[str, SkillNodeState] = {}
    for node_id, node in graph.nodes.items():
        ks = knowledge_states.get(node_id, {})
        p_know = ks.get("p_know", 0.1) if isinstance(ks, dict) else 0.1
        mastery = round(p_know * 100, 1)
        mastery_level = _classify_mastery(p_know)

        prereq_ids = [e.from_id for e in graph.edges if e.to_id == node_id]
        prereqs_met = all(
            knowledge_states.get(pid, {}).get("p_know", 0.0) >= 0.8
            for pid in prereq_ids
        ) if prereq_ids else True

        skills[node_id] = SkillNodeState(
            skill_id=node_id,
            label=node.label,
            description=node.description or "",
            mastery=mastery,
            mastery_level=mastery_level,
            depth=_legacy_depth(node_id, graph, set()),
            prerequisites=prereq_ids,
            prerequisites_met=prereqs_met,
            blocked=not prereqs_met and len(prereq_ids) > 0,
            attempt_count=ks.get("attempt_count", 0) if isinstance(ks, dict) else 0,
            correct_count=ks.get("correct_count", 0) if isinstance(ks, dict) else 0,
        )

    # ── 2. 依赖 ──
    dependencies = []
    for edge in graph.edges:
        from_node = skills.get(edge.from_id)
        satisfied = from_node and from_node.mastery >= 80
        dependencies.append(Dependency(
            from_skill=edge.from_id,
            to_skill=edge.to_id,
            relation=edge.relation or "prerequisite",
            satisfied=satisfied,
        ))

    # ── 3. 覆盖率 ──
    total = len(skills)
    touched = sum(1 for s in skills.values() if knowledge_states.get(s.skill_id))
    mastered = sum(1 for s in skills.values() if s.mastery_level == "已掌握")
    learning = sum(1 for s in skills.values() if s.mastery_level in ("发展中", "接近掌握"))
    weak = sum(1 for s in skills.values() if s.mastery_level == "初学")
    pp.coverage = Coverage(
        total=total, touched=touched, assessed=touched,
        mastered=mastered, learning=learning, weak=weak,
        untouched=total - touched,
    )

    # ── 4. 学习路径 ──
    ideal_order = _legacy_topological(skills, graph)
    frontier = [sid for sid in ideal_order if not skills[sid].blocked and skills[sid].mastery < 80]
    review_queue = [sid for sid, s in skills.items() if s.mastery >= 80][:5]
    pp.learning_path = LearningPath(
        ideal_order=ideal_order, actual_order=[],
        frontier=frontier, review_queue=review_queue,
    )

    # ── 5. 异常 ──
    anomalies = []
    for sid, s in skills.items():
        if s.blocked and s.mastery > 60:
            anomalies.append(Anomaly(type="mastered_without_prereq", skills=[sid],
                detail=f"前置未满足但掌握度已达{s.mastery}%", severity="warning"))
        if s.mastery_level in ("发展中", "初学"):
            if ks := knowledge_states.get(sid):
                n_obs = ks.get("n_observations", 0) if isinstance(ks, dict) else 0
                if n_obs >= 5 and s.mastery < 50:
                    anomalies.append(Anomaly(type="long_stagnation", skills=[sid],
                        detail=f"已练习{n_obs}次但掌握度仅{s.mastery}%", severity="warning"))
    pp.anomalies = anomalies

    # ── 6. 时序 ──
    temporal = _legacy_temporal(data, partition_id)
    temporal.estimated_completion_days = _estimate_completion(total, mastered, temporal.learning_velocity)
    temporal.review_backlog = len(review_queue)
    pp.temporal = temporal
    pp.skills = skills
    pp.dependencies = dependencies
    pp.generated_at = datetime.now(timezone.utc)

    return pp


def _legacy_depth(node_id: str, graph, visited: set) -> int:
    if node_id in visited:
        return 0
    visited.add(node_id)
    prereqs = [e.from_id for e in graph.edges if e.to_id == node_id]
    if not prereqs:
        return 0
    return 1 + max(_legacy_depth(p, graph, visited) for p in prereqs)


def _legacy_topological(skills: dict, graph) -> list[str]:
    in_degree: dict[str, int] = {sid: 0 for sid in skills}
    adj: dict[str, list[str]] = {sid: [] for sid in skills}
    for e in graph.edges:
        if e.from_id in skills and e.to_id in skills:
            in_degree[e.to_id] += 1
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


def _legacy_temporal(data, partition_id: str) -> TemporalMetrics:
    events: list[dict] = data.event_log
    cutoff_7d = datetime.now(timezone.utc).timestamp() - 7 * 86400
    recent = [e for e in events if e.get("partition_id") == partition_id and _ts_legacy(e) > cutoff_7d]

    day_minutes: dict[str, float] = {}
    for e in recent:
        if e.get("type") == "practice_submit":
            day = e.get("event_date", "")
            day_minutes[day] = day_minutes.get(day, 0) + e.get("data", {}).get("time_spent", 0) / 60

    avg_daily = sum(day_minutes.values()) / 7 if day_minutes else 0.0
    mastery_events = [e for e in recent if e.get("type") == "skill_mastery_changed"]
    velocity = len(mastery_events) / 7.0 if mastery_events else 0.0

    return TemporalMetrics(learning_velocity=round(velocity, 2), daily_practice_minutes=round(avg_daily, 1))


def _ts_legacy(event: dict) -> float:
    ts = event.get("timestamp")
    if isinstance(ts, str):
        return datetime.fromisoformat(ts).timestamp()
    if isinstance(ts, datetime):
        return ts.timestamp()
    return 0.0


# ═══════════════════════════════════════════════════
# 公共函数
# ═══════════════════════════════════════════════════


def _classify_mastery(p_know: float) -> str:
    if p_know >= 0.9:
        return "已掌握"
    if p_know >= 0.7:
        return "接近掌握"
    if p_know >= 0.4:
        return "发展中"
    if p_know > 0.0:
        return "初学"
    return "未接触"


def _estimate_completion(total: int, mastered: int, velocity: float) -> int:
    remaining = total - mastered
    if remaining <= 0:
        return 0
    v = velocity if velocity > 0 else 1.0
    return max(1, int(remaining / v))


# ═══════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════


@router.get("/{partition_id}", response_model=PartitionProgress)
async def get_partition_progress(partition_id: str):
    """获取分区的完整学习进度画像 — 优先使用 CognitiveNode"""

    # 首选: CognitiveNode
    if _has_cognitive_nodes():
        result = _compute_partition_progress_cognitive(partition_id)
        if result is not None:
            return result

    # 备降: 旧 JSON
    result = _compute_partition_progress_legacy(partition_id)
    if result is not None:
        return result

    # 空
    from app.services.storage import storage
    data = storage.load("default_user")
    partition = data.partitions.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="分区不存在")
    return PartitionProgress(
        partition_id=partition_id,
        partition_name=partition.name,
        partition_emoji=getattr(partition, "emoji", "📁"),
    )
