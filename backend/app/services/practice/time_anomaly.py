"""
时间异常检测 — 审题用时分析 (ADR 0011 A5)

对比用户答题用时与平均用时，推断答题行为模式。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def detect_time_anomaly(
    attempt: dict,
    user_stats: dict,
) -> Optional[str]:
    """
    对比该题用户用时 vs 用户平均用时，推断答题模式。

    参数:
        attempt: 答题记录 {duration_seconds, is_correct, ...}
        user_stats: 用户统计 {avg_duration_seconds, total_attempts, ...}

    返回:
        - "卡住了 / 缺少思路"  — 用时过长但答错
        - "粗心 / 审题不清"      — 用时过短但答错
        - "概念问题"              — 用时正常但答错
        - None                  — 用时正常且答对，或数据不足无法判断
    """
    duration = attempt.get("duration_seconds") or attempt.get("duration", 0)
    is_correct = attempt.get("is_correct", attempt.get("correct", False))

    avg_duration = user_stats.get("avg_duration_seconds", 0)
    if not avg_duration or avg_duration <= 0:
        return None

    # 计算比率
    ratio = duration / avg_duration if avg_duration > 0 else 0

    if not is_correct:
        if ratio > 2.0:
            return "卡住了 / 缺少思路"
        elif ratio < 0.5:
            return "粗心 / 审题不清"
        else:
            return "概念问题"

    # 答对的情况下，用时异常也值得关注
    if ratio > 3.0:
        return "用时过长但答对 — 可能知识点不熟练"

    return None


def get_time_anomaly_stats(
    user_id: str,
    recent_attempts: list[dict],
) -> dict:
    """
    统计用户最近答题的时间异常模式。

    返回:
        {
            "total_attempts": 10,
            "avg_duration": 45.2,
            "anomalies": {
                "stuck": 2,        # 卡住
                "careless": 3,     # 粗心
                "concept": 5,      # 概念问题
            },
            "primary_pattern": "concept",  # 主要模式
        }
    """
    if not recent_attempts:
        return {"total_attempts": 0, "avg_duration": 0, "anomalies": {}, "primary_pattern": None}

    # 计算平均用时
    durations = [a.get("duration_seconds", a.get("duration", 0)) for a in recent_attempts]
    avg_duration = sum(durations) / len(durations) if durations else 0

    user_stats = {"avg_duration_seconds": avg_duration}

    anomalies = {"stuck": 0, "careless": 0, "concept": 0}

    for attempt in recent_attempts:
        pattern = detect_time_anomaly(attempt, user_stats)
        if pattern and "卡住" in pattern:
            anomalies["stuck"] += 1
        elif pattern and "粗心" in pattern:
            anomalies["careless"] += 1
        elif pattern and "概念" in pattern:
            anomalies["concept"] += 1

    # 找出主要模式
    primary = max(anomalies, key=anomalies.get) if any(anomalies.values()) else None

    return {
        "total_attempts": len(recent_attempts),
        "avg_duration": round(avg_duration, 1),
        "anomalies": anomalies,
        "primary_pattern": primary,
    }