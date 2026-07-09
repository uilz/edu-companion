"""图上有界传播操作 — 将信念更新沿认知边传播 1-2 跳。

设计要点：
- 不同边类型有不同的方向性与默认权重范围；
- 传播距离受 edge_distance_decay 与 max_propagation_hops 限制；
- 目标节点的 independent_evidence_weight 可抑制过度平滑。
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_BIDIRECTIONAL_TYPES = {"co_occurrence", "chunk", "user_related", "cross_domain", "related_to"}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _direction_factor(edge_type: str, edge_source: str, edge_target: str, from_node: str, to_node: str) -> float:
    """返回沿某条边从一个节点到另一个节点的传播因子；0 表示不传播。"""
    if edge_type == "prerequisite":
        # 前置掌握提升后继估计：仅 source -> target
        return 1.0 if from_node == edge_source and to_node == edge_target else 0.0

    if edge_type == "hierarchy":
        # parent -> child 更强；反向仍存在但较弱
        if from_node == edge_source and to_node == edge_target:
            return 1.0
        if from_node == edge_target and to_node == edge_source:
            return 0.5
        return 0.0

    if edge_type in _BIDIRECTIONAL_TYPES:
        return 1.0

    # 未知类型默认双向弱传播
    return 0.3


@_registry.register(
    "graph_propagate",
    "将源节点的信念更新量沿认知边有界传播到邻居",
    params_schema={
        "source_node_id": {"type": "string", "required": True},
        "delta_alpha": {"type": "number", "required": True},
        "delta_beta": {"type": "number", "required": True},
        "edges": {"type": "array", "required": True},
        "neighbor_belief_states": {"type": "object", "required": False, "default": {}},
        "max_hops": {"type": "number", "required": False, "default": 2},
    },
)
def graph_propagate(
    source_node_id: str,
    delta_alpha: float,
    delta_beta: float,
    edges: list[dict[str, Any]],
    neighbor_belief_states: dict[str, dict[str, Any]] | None = None,
    max_hops: int = 2,
) -> dict[str, Any]:
    """从源节点出发，按边权重与衰减做有界 BFS 传播。

    返回每个邻居应追加的 delta_alpha/delta_beta（不是更新后的绝对值）。
    """
    neighbor_belief_states = neighbor_belief_states or {}
    max_hops = max(1, int(max_hops))

    # 构建邻接表（带方向性）
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for edge in edges:
        source = edge.get("source_id")
        target = edge.get("target_id")
        if not source or not target or source == target:
            continue
        adjacency.setdefault(source, []).append((target, edge))
        # 对于双向边，反向也要加入；方向因子在遍历阶段决定
        adjacency.setdefault(target, []).append((source, edge))

    # BFS：记录每个节点获得的最大累积因子（避免环路过度累积）
    best_factor: dict[str, tuple[int, float]] = {source_node_id: (0, 1.0)}
    queue: deque[tuple[str, int, float]] = deque([(source_node_id, 0, 1.0)])

    while queue:
        node, dist, factor = queue.popleft()
        if dist >= max_hops:
            continue

        for neighbor, edge in adjacency.get(node, []):
            edge_type = edge.get("edge_type", "related_to")
            direction = _direction_factor(
                edge_type,
                edge.get("source_id"),
                edge.get("target_id"),
                node,
                neighbor,
            )
            if direction == 0.0:
                continue

            edge_hops = int(edge.get("max_propagation_hops", max_hops))
            if dist + 1 > edge_hops:
                continue

            edge_weight = _clamp(float(edge.get("edge_weight", edge.get("strength", 0.5))))
            distance_decay = _clamp(float(edge.get("edge_distance_decay", 0.5)), 0.01, 0.99)

            new_factor = factor * edge_weight * (distance_decay ** (dist + 1)) * direction
            if new_factor <= 1e-6:
                continue

            prev = best_factor.get(neighbor)
            if prev is None or new_factor > prev[1]:
                best_factor[neighbor] = (dist + 1, new_factor)
                queue.append((neighbor, dist + 1, new_factor))

    updates: list[dict[str, Any]] = []
    for node_id, (dist, raw_factor) in best_factor.items():
        if node_id == source_node_id:
            continue

        neighbor_state = neighbor_belief_states.get(node_id, {})
        independent_weight = _clamp(
            float(neighbor_state.get("independent_evidence_weight", 1.0)), 0.0, 1.0
        )
        effective_factor = raw_factor * independent_weight
        if effective_factor <= 1e-6:
            continue

        updates.append(
            {
                "node_id": node_id,
                "distance": dist,
                "delta_alpha": round(delta_alpha * effective_factor, 6),
                "delta_beta": round(delta_beta * effective_factor, 6),
                "factor": round(effective_factor, 6),
            }
        )

    return {
        "subsystem": "graph_propagation",
        "method": "graph_propagate",
        "params": {"source_node_id": source_node_id, "max_hops": max_hops},
        "result_summary": f"propagated to {len(updates)} neighbors",
        "propagation_after": {
            "updates": updates,
            "updated_count": len(updates),
        },
    }
