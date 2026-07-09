"""认知操作模块 — 导入所有子系统操作以触发 @register 注册。"""

from __future__ import annotations

from app.domain.cognitive.operations import (
    activation_operations,
    bkt_operations,
    composition_operations,
    deep_processing_operations,
    engagement_operations,
    error_cluster_operations,
    goal_alignment_operations,
    metacognition_operations,
    prediction_operations,
    scheduling_operations,
    trend_operations,
)

__all__ = [
    "activation_operations",
    "bkt_operations",
    "composition_operations",
    "deep_processing_operations",
    "engagement_operations",
    "error_cluster_operations",
    "goal_alignment_operations",
    "metacognition_operations",
    "prediction_operations",
    "scheduling_operations",
    "trend_operations",
]
