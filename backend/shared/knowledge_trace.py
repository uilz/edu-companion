"""
CognitiveNode → KnowledgeState 适配桥

从 CognitiveNode 读取知识状态，返回 KnowledgeState DTO。
供 PrerequisiteChecker、前端统计等模块使用。
"""

from __future__ import annotations

import logging

from app.schemas.practice import KnowledgeState

logger = logging.getLogger(__name__)


def get_cognitive_state(user_id: str, skill_id: str) -> KnowledgeState:
    """从 CognitiveNode 读取知识状态（权威数据源）。
    若节点不存在则返回默认初始状态。
    """
    try:
        from app.cognitive import get_repo
        node = get_repo().get_node(skill_id, user_id)
        if node and node.belief:
            ks = KnowledgeState(
                skill_id=skill_id,
                p_known=node.belief.proficiency_mean,
            )
            if node.practice_summary:
                ks.attempt_count = node.practice_summary.total_attempts
                ks.correct_count = node.practice_summary.correct_attempts
            return ks
    except Exception as e:
        logger.warning("CognitiveNode unavailable for %s/%s, returning default state: %s", user_id, skill_id, e)
    return KnowledgeState(skill_id=skill_id)


def get_all_cognitive_states(user_id: str) -> dict[str, KnowledgeState]:
    """从 CognitiveNode 读取所有知识点的掌握状态。"""
    try:
        from app.cognitive import get_repo
        nodes = get_repo().list_all_nodes(user_id)
        result: dict[str, KnowledgeState] = {}
        for node in nodes:
            if node.belief:
                ks = KnowledgeState(
                    skill_id=node.id,
                    p_known=node.belief.proficiency_mean,
                )
                if node.practice_summary:
                    ks.attempt_count = node.practice_summary.total_attempts
                    ks.correct_count = node.practice_summary.correct_attempts
                result[node.id] = ks
        return result
    except Exception:
        return {}
