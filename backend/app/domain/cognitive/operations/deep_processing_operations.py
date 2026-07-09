"""DeepProcessing 子系统操作 — 深度加工触发与任务生成"""

from __future__ import annotations

import logging
import time

from app.domain.cognitive.operation_registry import get_registry

logger = logging.getLogger(__name__)
_registry = get_registry()

_TASK_TYPES = ["reflection", "analogy", "contrast", "elaboration"]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@_registry.register(
    "check_deep_processing_trigger",
    "检查是否需要触发深度加工任务",
    params_schema={
        "proficiency": {"type": "number", "required": True},
        "error_flag": {"type": "boolean", "required": False, "default": False},
        "stagnation_days": {"type": "number", "required": False, "default": 0.0},
        "next_action_type": {"type": "string", "required": False, "default": ""},
        "has_dialogue_context": {"type": "boolean", "required": False, "default": False},
    },
)
def check_deep_processing_trigger(
    proficiency: float,
    error_flag: bool = False,
    stagnation_days: float = 0.0,
    next_action_type: str = "",
    has_dialogue_context: bool = False,
) -> dict:
    """触发条件（任一）：error_flag / 0.7<=prof<=0.95 且有对话 / stagnation>7 / next_action_type=deep_processing。"""
    proficiency = _clamp(proficiency)

    triggered = False
    reasons = []

    if error_flag:
        triggered = True
        reasons.append("error_flag")
    if 0.7 <= proficiency <= 0.95 and has_dialogue_context:
        triggered = True
        reasons.append("dialogue_context_in_sweet_zone")
    if stagnation_days > 7:
        triggered = True
        reasons.append("stagnation")
    if next_action_type == "deep_processing":
        triggered = True
        reasons.append("scheduler_request")

    return {
        "subsystem": "deep_processing",
        "method": "check_deep_processing_trigger",
        "params": {"proficiency": proficiency},
        "result_summary": f"triggered={triggered} reasons={reasons}",
        "triggered": triggered,
        "reasons": reasons,
    }


@_registry.register(
    "generate_deep_processing_task",
    "生成深度加工任务描述",
    params_schema={
        "node_label": {"type": "string", "required": True},
        "task_type": {"type": "string", "required": True},
        "reason": {"type": "string", "required": False, "default": ""},
    },
)
def generate_deep_processing_task(
    node_label: str,
    task_type: str,
    reason: str = "",
) -> dict:
    """生成深度加工任务 prompt。"""
    task_type = task_type if task_type in _TASK_TYPES else "reflection"
    now = time.time()

    prompts = {
        "reflection": f"请用一句话总结你对「{node_label}」的理解，并指出最容易混淆的点。",
        "analogy": f"请为「{node_label}」举一个现实生活中的类比，并解释对应关系。",
        "contrast": f"请比较「{node_label}」与另一个相似概念，列出至少两点差异。",
        "elaboration": f"请用自己的话扩展解释「{node_label}」，并举一个具体例子。",
    }

    prompt = prompts[task_type]
    if reason:
        prompt = f"【{reason}】{prompt}"

    return {
        "subsystem": "deep_processing",
        "method": "generate_deep_processing_task",
        "params": {"task_type": task_type},
        "result_summary": f"task_type={task_type}",
        "task": {
            "task_type": task_type,
            "prompt": prompt,
            "status": "pending",
            "created_at": now,
        },
    }
