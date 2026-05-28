"""
⚠️  DEPRECATED — 本模块已由 CognitiveNode 替代。

SharedKnowledgeStateService 仅剩 knowledge_bridge.py 内部的
SharedKnowledgeState (domain/learning/shared_knowledge.py) 作为 fallback。
所有新代码应直接使用 app.cognitive.storage + CognitiveNode。

共享知识状态服务
统一管理对话和练习两个系统的知识状态

对话交互类型 → 知识状态更新规则：
- question_asked: 学生主动提问 → 说明在思考，微小提升
- explanation_given: 学生尝试解释 → application维度提升
- concept_discussed: 深度讨论 → concept维度提升
- misconception_corrected: 对话中纠正错误 → concept大幅提升
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.core.knowledge_trace import bkt_engine
from app.schemas.practice import KnowledgeState
from app.services.storage import storage

logger = logging.getLogger(__name__)

# 对话交互 → 知识状态更新映射
INTERACTION_GAINS = {
    "question_asked": {"concept": 0.02},           # 提问说明在思考
    "explanation_given": {"application": 0.05},    # 解释能提升应用能力
    "concept_discussed": {"concept": 0.05},         # 深度讨论提升概念
    "misconception_corrected": {"concept": 0.10},   # 纠正错误大幅提升
}


class SharedKnowledgeStateService:
    """
    统一知识状态服务
    
    对话系统和练习系统通过这个服务共享知识状态。
    对话中也能更新知识状态，练习中也能获取对话上下文。
    """

    def update_from_conversation(
        self,
        user_id: str,
        skill_id: str,
        interaction_type: str,
        depth: int = 1,
    ) -> KnowledgeState | None:
        """
        对话交互后更新知识状态
        
        参数:
            user_id: 用户ID
            skill_id: 知识点ID
            interaction_type: 交互类型
            depth: 对话轮次深度
        """
        if interaction_type not in INTERACTION_GAINS:
            return None

        # 获取或创建知识状态
        state = self._get_or_create_state(user_id, skill_id)
        gains = INTERACTION_GAINS[interaction_type]

        # 深度加成：对话轮次越多，提升越大
        depth_multiplier = min(2.0, 1.0 + depth * 0.1)

        for dim, gain in gains.items():
            if dim in state.dimensions:
                old = state.dimensions[dim].p_known
                new = min(0.99, old + gain * depth_multiplier)
                state.dimensions[dim].p_known = new
                logger.debug(
                    "对话更新知识: %s.%s %.3f→%.3f (%s)",
                    skill_id, dim, old, new, interaction_type,
                )

        state.last_updated = datetime.now()
        return state

    def update_from_practice(
        self,
        user_id: str,
        skill_id: str,
        is_correct: bool,
        hint_level: int = 0,
        explanation_score: Optional[float] = None,
    ) -> KnowledgeState:
        """练习答题后更新知识状态"""
        state = self._get_or_create_state(user_id, skill_id)
        return bkt_engine.update(
            state, is_correct,
            hint_level=hint_level,
            explanation_score=explanation_score,
        )

    def get_state(self, user_id: str, skill_id: str) -> KnowledgeState:
        """获取知识状态"""
        return self._get_or_create_state(user_id, skill_id)

    def get_weak_skills(self, user_id: str, top_n: int = 5) -> list[str]:
        """获取最薄弱的知识点"""
        # MVP: 从对话系统推断知识点（后续从专门存储读取）
        data = storage.load(user_id)
        skills = set()
        for partition in data.partitions.values():
            if partition.subject:
                skills.add(partition.subject)

        return list(skills)[:top_n]

    def _get_or_create_state(self, user_id: str, skill_id: str) -> KnowledgeState:
        """获取或创建知识状态"""
        # MVP: 内存存储（后续持久化到PostgreSQL）
        if not hasattr(self, '_states'):
            self._states = {}
        key = f"{user_id}:{skill_id}"
        if key not in self._states:
            self._states[key] = bkt_engine.create_knowledge_state(skill_id)
        return self._states[key]


# 全局实例
shared_ks = SharedKnowledgeStateService()
