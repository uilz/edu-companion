"""ErrorCluster 子系统操作 — 错误聚类"""

from __future__ import annotations

import logging
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()


@_registry.register(
    "record_error_cluster",
    "记录错误聚类：答错时按 error_type 累加",
    params_schema={
        "error_type": {"type": "string", "required": True},
        "error_embedding": {"type": "array", "required": False},
        "now": {"type": "number", "required": False},
    },
)
def record_error_cluster(
    error_type: str,
    error_embedding: list[float] | None = None,
    now: float | None = None,
) -> dict:
    """生成一条错误聚类记录描述，供 repository 写入子表。"""
    now = now or time.time()

    return {
        "subsystem": "error_cluster",
        "method": "record_error_cluster",
        "params": {"error_type": error_type},
        "result_summary": f"error_type={error_type} recorded",
        "cluster": {
            "error_type": error_type,
            "frequency": 1,
            "last_occurred": now,
            "cluster_metadata": {
                "embedding": error_embedding or [],
            },
        },
    }
