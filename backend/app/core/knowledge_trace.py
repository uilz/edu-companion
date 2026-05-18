"""
增强版BKT知识追踪引擎 v2.0
支持：多维知识状态、提示打折、解释评分、疲劳感知
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from app.config import settings
from app.schemas.practice import (
    ErrorType,
    ExplanationState,
    KnowledgeDimension,
    KnowledgeState,
)

logger = logging.getLogger(__name__)


class BKTEngine:
    """
    增强版BKT引擎
    
    核心更新：
    1. 多维知识状态（concept/procedure/application/transfer）
    2. 提示打折（hint_level影响p_known更新幅度）
    3. 解释评分反馈（explanation_score调整更新方向）
    4. 伪掌握检测（答对但解释不出来）
    """

    # 提示等级 → 更新折扣因子
    HINT_DISCOUNT = {0: 1.0, 1: 0.7, 2: 0.4, 3: 0.2, 4: 0.05}

    def __init__(self) -> None:
        self.default_p_learn = settings.bkt_default_p_learn
        self.default_p_guess = settings.bkt_default_p_guess
        self.default_p_slip = settings.bkt_default_p_slip
        self.default_p_know = settings.bkt_default_p_know
        self.mastery_threshold = settings.bkt_mastery_threshold

    def create_knowledge_state(
        self,
        skill_id: str,
        p_known: Optional[float] = None,
        p_learn: Optional[float] = None,
        p_guess: Optional[float] = None,
        p_slip: Optional[float] = None,
        p_transit: Optional[float] = None,
    ) -> KnowledgeState:
        """创建新的知识点状态"""
        return KnowledgeState(
            skill_id=skill_id,
            p_known=p_known if p_known is not None else self.default_p_know,
            p_learned=p_learn if p_learn is not None else self.default_p_learn,
            p_guess=p_guess if p_guess is not None else self.default_p_guess,
            p_slip=p_slip if p_slip is not None else self.default_p_slip,
            p_transit=p_transit if p_transit is not None else self.default_p_learn,
        )

    def update_correct(self, state: KnowledgeState) -> KnowledgeState:
        """正确回答后更新"""
        p_k, p_l, p_g, p_s = state.p_known, state.p_learned, state.p_guess, state.p_slip

        p_correct = p_k * (1 - p_s) + (1 - p_k) * (p_l * (1 - p_s) + (1 - p_l) * p_g)
        if p_correct == 0:
            p_correct = 1e-10

        state.p_known = p_k * (1 - p_s) / p_correct
        state.p_learned = p_l * (1 - p_s) / p_correct
        state.attempt_count += 1
        state.correct_count += 1

        return state

    def update_incorrect(self, state: KnowledgeState) -> KnowledgeState:
        """错误回答后更新"""
        p_k, p_l, p_g, p_s = state.p_known, state.p_learned, state.p_guess, state.p_slip

        p_incorrect = p_k * p_s + (1 - p_k) * (p_l * p_s + (1 - p_l) * (1 - p_g))
        if p_incorrect == 0:
            p_incorrect = 1e-10

        p_k_new = p_k * p_s / p_incorrect
        p_l_new = p_l * p_s / p_incorrect

        state.p_learned = p_l_new + (1 - p_l_new) * state.p_transit
        state.p_known = p_k_new + (1 - p_k_new) * state.p_transit * state.p_learned
        state.attempt_count += 1

        return state

    def update(
        self,
        state: KnowledgeState,
        is_correct: bool,
        hint_level: int = 0,
        explanation_score: Optional[float] = None,
    ) -> KnowledgeState:
        """
        统一更新入口
        
        参数:
            state: 当前知识点状态
            is_correct: 是否正确
            hint_level: 提示等级 (0-4)
            explanation_score: 解释质量评分 (0-1)，None表示未提供
        """
        # 保存原始值（update_correct/update_inplace会原地修改）
        original_p_known = state.p_known

        # 1. 基础BKT更新
        if is_correct:
            state = self.update_correct(state)
        else:
            state = self.update_incorrect(state)

        # 2. 提示打折
        discount = self.HINT_DISCOUNT.get(hint_level, 0.05)
        delta = state.p_known - original_p_known
        state.p_known = original_p_known + delta * discount

        # 更新维度
        if is_correct:
            state.correct_count += 1
        state.attempt_count += 1

        # 3. 解释评分调整
        if explanation_score is not None:
            state = self._apply_explanation_adjustment(state, is_correct, explanation_score)

        state.last_updated = __import__("datetime").datetime.now()
        return state

    def _apply_explanation_adjustment(
        self,
        state: KnowledgeState,
        is_correct: bool,
        explanation_score: float,
    ) -> KnowledgeState:
        """
        解释评分调整
        
        答对 + 解释好(>0.8) → 大幅提升（真正掌握）
        答对 + 解释差(<0.5) → 不提升（伪掌握）
        答错 + 解释好(>0.7) → p_known不降，增加p_slip
        答错 + 解释差(<0.5) → 大幅下降（真正不理解）
        """
        if is_correct:
            if explanation_score > 0.8:
                state.p_known = min(0.99, state.p_known + 0.1)
            elif explanation_score < 0.5:
                state.pseudo_mastery_flags.append(state.skill_id)
        else:
            if explanation_score > 0.7:
                # 理解正确但计算失误 → 增加slip概率
                state.p_slip = min(0.5, state.p_slip + 0.05)
            elif explanation_score < 0.5:
                state.p_known = max(0.0, state.p_known - 0.1)
                state.misconception_flags.append(f"{state.skill_id}:explanation_wrong")

        # 更新解释状态
        if state.explanation_state is None:
            state.explanation_state = ExplanationState()
        state.explanation_state.explanation_count += 1
        state.explanation_state.last_explained = __import__("datetime").datetime.now()
        old_avg = state.explanation_state.avg_explanation_score
        n = state.explanation_state.explanation_count
        state.explanation_state.avg_explanation_score = (old_avg * (n - 1) + explanation_score) / n

        return state

    def predict_correct_prob(self, state: KnowledgeState) -> float:
        """预测下一次答对的概率"""
        p_k, p_l, p_g, p_s = state.p_known, state.p_learned, state.p_guess, state.p_slip
        return p_k * (1 - p_s) + (1 - p_k) * (p_l * (1 - p_s) + (1 - p_l) * p_g)

    def get_mastery_level(self, state: KnowledgeState) -> str:
        """获取掌握等级"""
        p = state.p_known
        if state.attempt_count == 0:
            return "未接触"
        elif p < 0.3:
            return "初学"
        elif p < 0.6:
            return "发展中"
        elif p < self.mastery_threshold:
            return "接近掌握"
        else:
            return "已掌握"

    def recommend_practice(
        self,
        states: dict[str, KnowledgeState],
        top_n: int = 5,
    ) -> list[dict]:
        """推荐需要练习的知识点"""
        recommendations = []

        for skill_id, state in states.items():
            level = self.get_mastery_level(state)
            priority_map = {
                "接近掌握": 1.0,
                "发展中": 0.7,
                "初学": 0.5,
                "未接触": 0.3,
                "已掌握": 0.0,
            }
            priority = priority_map.get(level, 0.0)

            recommendations.append({
                "skill_id": skill_id,
                "level": level,
                "priority": priority,
                "p_known": state.p_known,
            })

        recommendations.sort(key=lambda x: x["priority"], reverse=True)
        return [r for r in recommendations if r["priority"] > 0][:top_n]

    def compute_forgetting_prob(self, state: KnowledgeState, days_since: float) -> float:
        """
        计算遗忘概率（Ebbinghaus遗忘曲线）
        R = e^(-t/S)，S为知识稳定性
        """
        stability = state.explanation_state.stability if state.explanation_state else 1.0
        return math.exp(-days_since / max(stability, 0.1))

    # ── 持久化 ──

    def load_or_create(
        self,
        user_id: str,
        skill_id: str,
        p_known: float | None = None,
    ) -> KnowledgeState:
        """
        从 UserData 加载已有知识状态，不存在则创建。
        状态持久化在 UserData.knowledge_states[skill_id] 中。
        """
        try:
            from app.services.storage import storage
            data = storage.load(user_id)
            if skill_id in data.knowledge_states:
                state_dict = data.knowledge_states[skill_id]
                return KnowledgeState(**state_dict)
        except Exception:
            pass  # 降级：创建新状态
        return self.create_knowledge_state(skill_id, p_known=p_known)

    def save_state(self, user_id: str, state: KnowledgeState) -> None:
        """将知识状态写入 UserData 并持久化到磁盘"""
        try:
            from app.services.storage import storage
            data = storage.load(user_id)
            data.knowledge_states[state.skill_id] = state.model_dump()
            storage.save(user_id, data)
        except Exception:
            pass  # 写入失败静默降级，不影响答题流

    def load_all_states(self, user_id: str) -> dict[str, KnowledgeState]:
        """加载用户的所有知识状态"""
        try:
            from app.services.storage import storage
            data = storage.load(user_id)
            return {
                skill_id: KnowledgeState(**state_dict)
                for skill_id, state_dict in data.knowledge_states.items()
            }
        except Exception:
            return {}


# 全局实例
bkt_engine = BKTEngine()
