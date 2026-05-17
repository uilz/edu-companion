"""
BKT（贝叶斯知识追踪）引擎
完全实现 BKT 模型的前后向更新算法

BKT 模型参数：
- P(K): 掌握概率 — 学习者已经学会该知识点的概率
- P(L): 初始学习概率 — 在练习前已学会的概率
- P(G): 猜对概率 — 没学会但猜对的概率
- P(S): 失手概率 — 学会了但做错的概率
- P(T): 学习转移概率 — 练习后从"未学会"变为"学会"的概率
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.schemas.learner import KnowledgeState

logger = logging.getLogger(__name__)


class BKT:
    """
    贝叶斯知识追踪引擎

    核心公式：
    1. P(L|obs) = P(L) * P(obs|L) / P(obs)
    2. P(K|obs) = P(K) + P(L|¬K) * P(T)
    3. P(obs) = P(obs|L)*P(L) + P(obs|¬L)*P(L)
    """

    def __init__(self) -> None:
        # 从配置读取默认BKT参数
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
        """
        创建一个新的知识点状态

        参数:
            skill_id: 知识点ID
            p_known: 初始掌握概率
            p_learn: 初始学习概率
            p_guess: 猜对概率
            p_slip: 失手概率
            p_transit: 学习转移概率
        """
        return KnowledgeState(
            skill_id=skill_id,
            p_known=p_known if p_known is not None else self.default_p_know,
            p_learned=p_learn if p_learn is not None else self.default_p_learn,
            p_guess=p_guess if p_guess is not None else self.default_p_guess,
            p_slip=p_slip if p_slip is not None else self.default_p_slip,
            p_transit=p_transit if p_transit is not None else self.default_p_learn,
        )

    def update_correct(self, state: KnowledgeState) -> KnowledgeState:
        """
        根据正确作答更新知识点状态

        BKT 更新公式（回答正确时）：
        P(K|correct) = P(K) * (1 - P(S)) / P(correct)
        P(L|correct) = P(L) * (1 - P(S)) / P(correct)

        其中 P(correct) = P(K)(1-P(S)) + (1-P(K))(P(L)(1-P(S)) + (1-P(L))*P(G))
        """
        p_k = state.p_known
        p_l = state.p_learned
        p_g = state.p_guess
        p_s = state.p_slip

        # 回答正确的概率
        p_correct = p_k * (1 - p_s) + (1 - p_k) * (p_l * (1 - p_s) + (1 - p_l) * p_g)

        if p_correct == 0:
            p_correct = 1e-10  # 防止除零

        # 后验更新：回答正确后
        p_k_given_correct = p_k * (1 - p_s) / p_correct
        p_l_given_correct = p_l * (1 - p_s) / p_correct

        # 更新状态
        state.p_known = p_k_given_correct
        state.p_learned = p_l_given_correct
        state.attempt_count += 1
        state.correct_count += 1

        logger.debug(
            "BKT [正确] skill=%s: P(K) %.4f->%.4f",
            state.skill_id, p_k, state.p_known,
        )
        return state

    def update_incorrect(self, state: KnowledgeState) -> KnowledgeState:
        """
        根据错误作答更新知识点状态

        BKT 更新公式（回答错误时）：
        P(K|incorrect) = P(K) * P(S) / P(incorrect)
        P(L|incorrect) = P(L) * P(S) / P(incorrect)

        其中 P(incorrect) = P(K)*P(S) + (1-P(K))*(P(L)*P(S) + (1-P(L))*(1-P(G)))
        """
        p_k = state.p_known
        p_l = state.p_learned
        p_g = state.p_guess
        p_s = state.p_slip

        # 回答错误的概率
        p_incorrect = p_k * p_s + (1 - p_k) * (p_l * p_s + (1 - p_l) * (1 - p_g))

        if p_incorrect == 0:
            p_incorrect = 1e-10  # 防止除零

        # 后验更新：回答错误后
        p_k_given_incorrect = p_k * p_s / p_incorrect
        p_l_given_incorrect = p_l * p_s / p_incorrect

        # 更新状态（含学习转移）
        # 错误后仍然可能发生学习转移
        state.p_learned = p_l_given_incorrect + (1 - p_l_given_incorrect) * state.p_transit
        state.p_known = p_k_given_incorrect + (1 - p_k_given_incorrect) * state.p_transit * state.p_learned

        state.attempt_count += 1

        logger.debug(
            "BKT [错误] skill=%s: P(K) %.4f->%.4f",
            state.skill_id, p_k, state.p_known,
        )
        return state

    def update(self, state: KnowledgeState, is_correct: bool) -> KnowledgeState:
        """
        根据作答结果更新知识点状态（统一入口）

        参数:
            state: 当前知识点状态
            is_correct: 是否回答正确

        返回:
            更新后的知识点状态
        """
        if is_correct:
            return self.update_correct(state)
        else:
            return self.update_incorrect(state)

    def batch_update(
        self,
        states: dict[str, KnowledgeState],
        results: list[tuple[str, bool]],
    ) -> dict[str, KnowledgeState]:
        """
        批量更新多个知识点的状态

        参数:
            states: 知识点ID -> 状态 的映射
            results: [(skill_id, is_correct), ...] 的列表

        返回:
            更新后的状态映射
        """
        for skill_id, is_correct in results:
            if skill_id not in states:
                states[skill_id] = self.create_knowledge_state(skill_id)
            self.update(states[skill_id], is_correct)
        return states

    def predict_correct_prob(self, state: KnowledgeState) -> float:
        """
        预测下一次回答正确的概率

        P(correct) = P(K)(1-P(S)) + (1-P(K))(P(L)(1-P(S)) + (1-P(L))*P(G))
        """
        p_k = state.p_known
        p_l = state.p_learned
        p_g = state.p_guess
        p_s = state.p_slip

        p_correct = p_k * (1 - p_s) + (1 - p_k) * (p_l * (1 - p_s) + (1 - p_l) * p_g)
        return p_correct

    def get_mastery_level(self, state: KnowledgeState) -> str:
        """
        获取知识点掌握等级

        返回:
            "未接触" | "初学" | "发展中" | "接近掌握" | "已掌握"
        """
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
    ) -> list[dict[str, str | float]]:
        """
        根据知识状态推荐需要练习的知识点

        策略：
        1. 优先推荐"接近掌握"的（最容易突破）
        2. 然后是"发展中"的
        3. 最后是"初学"的

        参数:
            states: 所有知识点状态
            top_n: 推荐数量

        返回:
            推荐列表 [{"skill_id": ..., "level": ..., "priority": ...}, ...]
        """
        recommendations: list[dict[str, str | float]] = []

        for skill_id, state in states.items():
            level = self.get_mastery_level(state)
            # 计算优先级分数
            if level == "接近掌握":
                priority = 1.0
            elif level == "发展中":
                priority = 0.7
            elif level == "初学":
                priority = 0.5
            elif level == "未接触":
                priority = 0.3
            else:  # 已掌握
                priority = 0.0

            recommendations.append({
                "skill_id": skill_id,
                "level": level,
                "priority": priority,
                "p_known": state.p_known,
            })

        # 按优先级降序排序
        recommendations.sort(key=lambda x: float(x["priority"]), reverse=True)

        # 排除已掌握的
        recommendations = [r for r in recommendations if r["priority"] > 0]

        return recommendations[:top_n]


# ── 全局BKT引擎实例 ──
bkt_engine = BKT()
