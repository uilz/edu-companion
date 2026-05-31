"""
Canonical get_knowledge_state helper.

Merges the 3 near-identical adapter methods found in:
  - app/api/knowledge.py  (_BKTKnowledgeAdapter)
  - app/api/study.py      (_Adapter)
  - app/services/adaptive_planner.py  (_CognitiveAdapter)

Returns a dict suitable for PrerequisiteChecker adapter protocol.
"""
from __future__ import annotations

import logging

from app.core.knowledge_trace import get_cognitive_state

logger = logging.getLogger(__name__)


def mastery_level(p: float) -> str:
    """中文 mastery label based on proficiency."""
    if p >= 0.9:
        return "已掌握"
    if p >= 0.7:
        return "接近掌握"
    if p >= 0.4:
        return "发展中"
    if p > 0.0:
        return "初学"
    return "未接触"


async def get_knowledge_state(user_id: str, skill_id: str) -> dict:
    """Return knowledge mastery state for *skill_id* / *user_id*.

    Priority: CognitiveNode (storage.get_node) → fallback get_cognitive_state.
    Returns dict with keys: skill_id, p_known, attempt_count, correct_count,
    mastery_level, source.
    """
    # Primary: CognitiveNode (try by ID first, then by label)
    try:
        from app.cognitive.storage import get_node, find_node_by_label
        node = get_node(skill_id, user_id)
        if node is None:
            node = find_node_by_label(skill_id, user_id)
        if node and node.belief:
            return {
                "skill_id": skill_id,
                "p_known": node.belief.proficiency_mean,
                "attempt_count": (
                    node.practice_summary.total_attempts
                    if node.practice_summary else 0
                ),
                "correct_count": (
                    node.practice_summary.correct_attempts
                    if node.practice_summary else 0
                ),
                "mastery_level": mastery_level(node.belief.proficiency_mean),
                "source": "cognitive_node",
            }
    except Exception as e:
        logger.warning("CognitiveNode unavailable for %s/%s, falling back: %s", user_id, skill_id, e)

    # Fallback: old BKT via CognitiveNode reader
    state = get_cognitive_state(user_id, skill_id)
    return state.model_dump()
