"""
秘书系统分析引擎 — CognitiveNode 数据源

所有分析函数基于 cognitive_nodes 表计算，返回结构化结果。
支持传入预加载的 nodes 列表避免重复查询。
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _get_nodes(user_id: str, nodes: list | None = None) -> list:
    """获取节点列表（缓存优先）"""
    if nodes is not None:
        return nodes
    from app.cognitive import get_repo
    return get_repo().list_all_nodes(user_id)


def find_weakness_clusters(user_id: str, limit: int = 5, *, nodes: list | None = None) -> list[dict]:
    """找出掌握度最低的知识点集群"""
    nodes = _get_nodes(user_id, nodes)
    weak = []
    for n in nodes:
        mu = n.belief.proficiency_mean if n.belief else 0.0
        if 0 < mu < 0.4:
            weak.append({
                "node_id": n.id,
                "label": n.label,
                "mastery": round(mu * 100, 1),
                "level": n.level,
            })
    weak.sort(key=lambda x: x["mastery"])
    return weak[:limit]


def detect_stagnant_topics(user_id: str, threshold_days: float = 7.0, *, nodes: list | None = None) -> list[dict]:
    """检测停滞的知识点（长时间无练习进展）"""
    nodes = _get_nodes(user_id, nodes)
    now = time.time()
    stagnant = []
    for n in nodes:
        if not n.practice_summary or not n.practice_summary.last_practiced:
            continue
        days = (now - n.practice_summary.last_practiced) / 86400
        if days >= threshold_days:
            stagnant.append({
                "node_id": n.id,
                "label": n.label,
                "days_since": round(days, 1),
                "attempts": n.practice_summary.total_attempts,
            })
    stagnant.sort(key=lambda x: x["days_since"], reverse=True)
    return stagnant


def trace_proficiency_regression(user_id: str, *, nodes: list | None = None) -> list[dict]:
    """检测掌握度下降的知识点"""
    nodes = _get_nodes(user_id, nodes)
    regressing = []
    for n in nodes:
        if n.trend and n.trend.direction == "declining":
            regressing.append({
                "node_id": n.id,
                "label": n.label,
                "velocity": n.trend.velocity if n.trend.velocity else 0.0,
            })
    return regressing


def assess_current_burden(user_id: str, *, nodes: list | None = None) -> dict:
    """评估当前学习负担"""
    nodes = _get_nodes(user_id, nodes)
    total = len(nodes)
    urgent = sum(1 for n in nodes if n.scheduling and n.scheduling.urgency > 0.5)
    learning = sum(1 for n in nodes if n.belief and 0.1 < n.belief.proficiency_mean < 0.8)
    return {
        "total_nodes": total,
        "urgent_reviews": urgent,
        "active_learning": learning,
        "burden_level": "high" if urgent > 5 else "medium" if urgent > 2 else "low",
    }


def detect_calibration_mismatch(user_id: str, *, nodes: list | None = None) -> list[dict]:
    """检测信度与掌握度不匹配的知识点"""
    nodes = _get_nodes(user_id, nodes)
    mismatches = []
    for n in nodes:
        if not n.belief:
            continue
        conf = 1.0 / (1.0 + n.belief.beta)
        mu = n.belief.proficiency_mean
        if mu > 0.7 and conf < 0.3:
            mismatches.append({
                "node_id": n.id,
                "label": n.label,
                "mastery": round(mu * 100, 1),
                "confidence": round(conf, 3),
                "issue": "high_mastery_low_confidence",
            })
    return mismatches


def detect_prediction_divergence(user_id: str, *, nodes: list | None = None) -> list[dict]:
    """检测预测偏差（实际表现与模型预测不符）"""
    nodes = _get_nodes(user_id, nodes)
    divergent = []
    for n in nodes:
        if not n.practice_summary or not n.belief:
            continue
        attempts = n.practice_summary.total_attempts
        correct = n.practice_summary.correct_attempts
        if attempts < 3:
            continue
        actual_rate = correct / attempts if attempts > 0 else 0
        predicted = n.belief.proficiency_mean
        diff = abs(actual_rate - predicted)
        if diff > 0.3:
            divergent.append({
                "node_id": n.id,
                "label": n.label,
                "predicted": round(predicted, 2),
                "actual": round(actual_rate, 2),
                "divergence": round(diff, 2),
            })
    return divergent


def compute_progress_delta(user_id: str, days: float = 7.0, *, nodes: list | None = None) -> dict:
    """计算最近 N 天的学习进展变化"""
    nodes = _get_nodes(user_id, nodes)
    now = time.time()
    cutoff = now - days * 86400
    recent_practices = 0
    for n in nodes:
        if n.practice_summary and n.practice_summary.last_practiced and n.practice_summary.last_practiced >= cutoff:
            recent_practices += 1
    return {
        "period_days": days,
        "nodes_practiced": recent_practices,
        "total_nodes": len(nodes),
        "coverage_delta": round(recent_practices / max(len(nodes), 1) * 100, 1),
    }


def rank_recommendations(user_id: str, limit: int = 5, *, nodes: list | None = None) -> list[dict]:
    """推荐下一步学习的知识点"""
    nodes = _get_nodes(user_id, nodes)
    candidates = []
    for n in nodes:
        mu = n.belief.proficiency_mean if n.belief else 0.0
        urgency = n.scheduling.urgency if n.scheduling else 0.0
        score = (1.0 - abs(mu - 0.5)) * 0.4 + urgency * 0.6
        if mu < 0.9:
            candidates.append({
                "node_id": n.id,
                "label": n.label,
                "mastery": round(mu * 100, 1),
                "urgency": round(urgency, 2),
                "score": round(score, 3),
            })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:limit]


def find_overdue_reviews(user_id: str, *, nodes: list | None = None) -> list[dict]:
    """找出需要复习但已过期的知识点"""
    nodes = _get_nodes(user_id, nodes)
    overdue = []
    for n in nodes:
        if n.scheduling and n.scheduling.urgency > 0.6 and n.belief and n.belief.proficiency_mean >= 0.6:
            overdue.append({
                "node_id": n.id,
                "label": n.label,
                "urgency": round(n.scheduling.urgency, 2),
                "mastery": round(n.belief.proficiency_mean * 100, 1),
            })
    overdue.sort(key=lambda x: x["urgency"], reverse=True)
    return overdue


def predict_fatigue_risk(user_id: str, *, nodes: list | None = None) -> dict:
    """预测疲劳风险"""
    nodes = _get_nodes(user_id, nodes)
    now = time.time()
    recent_count = 0
    for n in nodes:
        if n.practice_summary and n.practice_summary.last_practiced:
            hours = (now - n.practice_summary.last_practiced) / 3600
            if hours < 2:
                recent_count += 1
    risk = "high" if recent_count > 10 else "medium" if recent_count > 5 else "low"
    return {
        "recent_practices_2h": recent_count,
        "risk_level": risk,
        "recommendation": "建议休息" if risk == "high" else "可以继续" if risk == "low" else "适当休息",
    }
