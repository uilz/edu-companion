"""
结构化日志工具 — 关键操作输出 JSON 格式日志

使用方式:
    from app.core.log_utils import log_classify_decision, log_event_processed
    log_classify_decision(mode=1, candidates=3, immersion_depth=5)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _json_log(event: str, **fields: Any) -> None:
    """输出 JSON 行日志"""
    record = {
        "event": event,
        "ts": time.time(),
        **fields,
    }
    logger.info(json.dumps(record, ensure_ascii=False, default=str))


def log_classify_decision(
    mode: int,
    candidates: int,
    immersion_depth: int,
    immersion_suppressed: bool = False,
    latency_ms: float = 0.0,
) -> None:
    """分类器决策日志"""
    _json_log(
        "classify_decision",
        mode=mode,
        candidates=candidates,
        immersion_depth=immersion_depth,
        immersion_suppressed=immersion_suppressed,
        latency_ms=round(latency_ms, 1),
    )


def log_event_processed(
    event_type: str,
    event_id: str,
    handler: str,
    duration_ms: float,
    success: bool = True,
) -> None:
    """事件处理日志"""
    _json_log(
        "event_processed",
        event_type=event_type,
        event_id=event_id,
        handler=handler,
        duration_ms=round(duration_ms, 1),
        success=success,
    )


def log_ripple_edge(
    source_label: str,
    target_label: str,
    similarity: float,
    edge_count: int,
) -> None:
    """波纹边检测日志"""
    _json_log(
        "ripple_edge",
        source=source_label,
        target=target_label,
        similarity=round(similarity, 3),
        pending_edges=edge_count,
    )


def log_diagnosis(
    user_id: str,
    weak_count: int,
    cognitive_load: float,
    proposal_count: int,
) -> None:
    """诊断周期日志"""
    _json_log(
        "secretary_diagnosis",
        user_id=user_id,
        weak_count=weak_count,
        cognitive_load=round(cognitive_load, 2),
        proposals=proposal_count,
    )
