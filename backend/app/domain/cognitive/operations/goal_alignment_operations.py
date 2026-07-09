"""GoalAlignment 子系统操作 — 目标对齐"""

from __future__ import annotations

import logging
from collections import deque

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_CRITICAL_PATH_DISTANCE = 2


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "update_goal_alignment",
    "更新目标对齐：基于到最近目标节点的距离与边强度",
    params_schema={
        "goal_alignment_state": {"type": "object", "required": True},
        "goal_distances": {"type": "object", "required": True},
        "goal_weights": {"type": "object", "required": False},
        "on_critical_path": {"type": "boolean", "required": False, "default": False},
    },
)
def update_goal_alignment(
    goal_alignment_state: dict,
    goal_distances: dict[str, int],
    goal_weights: dict[str, float] | None = None,
    on_critical_path: bool = False,
) -> dict:
    """toward_goal = 加权平均；distance = 到最近目标的最短路径。"""
    if not goal_distances:
        return {
            "subsystem": "goal_alignment",
            "method": "update_goal_alignment",
            "result_summary": "no goals, default alignment",
            "goal_alignment_after": {
                "goal_toward": 0.0,
                "goal_distance": -1,
                "goal_on_critical_path": False,
            },
        }

    weights = goal_weights or {}
    # 默认权重为 1 / (1 + distance)
    for goal_id, distance in goal_distances.items():
        if goal_id not in weights:
            weights[goal_id] = 1.0 / (1.0 + distance)

    total_weight = sum(weights.get(g, 0.0) for g in goal_distances)
    if total_weight > 0:
        toward = sum(
            weights.get(g, 0.0) * _clamp(1.0 / (1.0 + d))
            for g, d in goal_distances.items()
        ) / total_weight
    else:
        toward = 0.0

    min_distance = min(goal_distances.values())
    on_critical = on_critical_path or min_distance <= _CRITICAL_PATH_DISTANCE

    goal_after = {
        "goal_toward": round(_clamp(toward), 4),
        "goal_distance": int(min_distance),
        "goal_on_critical_path": on_critical,
    }

    return {
        "subsystem": "goal_alignment",
        "method": "update_goal_alignment",
        "params": {"goals": list(goal_distances.keys())},
        "result_summary": (
            f"toward={goal_after['goal_toward']:.3f} "
            f"distance={min_distance} critical={on_critical}"
        ),
        "goal_alignment_after": goal_after,
    }


@_registry.register(
    "shortest_path_to_goals",
    "BFS 计算节点到多个目标节点的最短路径距离",
    params_schema={
        "start_node": {"type": "string", "required": True},
        "goal_nodes": {"type": "array", "required": True},
        "edges": {"type": "array", "required": True},
    },
)
def shortest_path_to_goals(
    start_node: str,
    goal_nodes: list[str],
    edges: list[tuple[str, str]],
) -> dict:
    """edges: (source, target) 无向图 BFS。"""
    goals = set(goal_nodes)
    if start_node in goals:
        return {
            "subsystem": "goal_alignment",
            "method": "shortest_path_to_goals",
            "result_summary": "start is goal",
            "distances": {start_node: 0},
            "min_distance": 0,
        }

    graph: dict[str, list[str]] = {}
    for s, t in edges:
        graph.setdefault(s, []).append(t)
        graph.setdefault(t, []).append(s)

    visited = {start_node}
    queue: deque[tuple[str, int]] = deque([(start_node, 0)])
    distances: dict[str, int] = {}

    while queue:
        node, dist = queue.popleft()
        for neighbor in graph.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            new_dist = dist + 1
            if neighbor in goals:
                distances[neighbor] = new_dist
            queue.append((neighbor, new_dist))

    min_distance = min(distances.values()) if distances else -1
    return {
        "subsystem": "goal_alignment",
        "method": "shortest_path_to_goals",
        "result_summary": f"min_distance={min_distance}",
        "distances": distances,
        "min_distance": min_distance,
    }
