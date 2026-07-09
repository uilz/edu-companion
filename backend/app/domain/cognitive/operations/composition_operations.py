"""Composition 子系统操作 — 组块形成"""

from __future__ import annotations

import logging

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_MIN_CO_OCCURRENCE = 10
_MIN_PROFICIENCY = 0.8
_MIN_STABILITY = 0.7


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "check_chunk_formation",
    "检查组块是否满足形成条件",
    params_schema={
        "co_occurrence_count": {"type": "number", "required": True},
        "member_proficiencies": {"type": "array", "required": True},
        "member_stabilities": {"type": "array", "required": True},
    },
)
def check_chunk_formation(
    co_occurrence_count: int,
    member_proficiencies: list[float],
    member_stabilities: list[float],
) -> dict:
    """同 session 内一起练习的原子节点满足条件则形成组块。"""
    all_proficient = all(_clamp(p) >= _MIN_PROFICIENCY for p in member_proficiencies)
    all_stable = all(_clamp(s) >= _MIN_STABILITY for s in member_stabilities)
    formed = (
        co_occurrence_count >= _MIN_CO_OCCURRENCE
        and all_proficient
        and all_stable
    )

    return {
        "subsystem": "composition",
        "method": "check_chunk_formation",
        "params": {"co_occurrence_count": co_occurrence_count},
        "result_summary": (
            f"formed={formed} proficient={all_proficient} stable={all_stable}"
        ),
        "formed": formed,
        "chunking_status": "formed" if formed else "forming",
    }
