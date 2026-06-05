"""
SpacedRepetition — SM-2 改进版间隔重复调度引擎

核心改进：
1. 使用 Beta 信念分布参数 (α, β) 计算 retention 概率
2. 回答质量从 Binary 映射到 SM-2 5 级量表
3. Urgency 计算：距目标复习时间的 "超期比"
4. 与 CognitiveNode 的 Scheduling 字段双向同步

References:
  - P-F. Wozniak, "Optimization of learning" (SM-2), SuperMemo 1987
  - Settles & Meeder, "A Trainable Spaced Repetition Model", 2016
  - Tabibian et al., "A Convex Optimization Approach to Spaced Repetition", 2019
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 默认参数 ───
DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR = 1.3
MAX_EASE_FACTOR = 3.0

# 初次复习间隔（天）
INITIAL_INTERVAL = 1.0
# 最大间隔上限（天），防止无限增长
MAX_INTERVAL = 365.0
# 延期标记：练习完多久（天）开始认为该复习了
REVIEW_THRESHOLD_DAYS = 1.0
# 掌握度阈值：高于此认为已掌握，考虑拉长间隔
MASTERY_THRESHOLD = 0.75


@dataclass
class ReviewResult:
    """一次复习的结果（供队列生成和 API 返回使用）"""
    node_id: str
    label: str
    level: str
    proficiency_mean: float
    urgency: float
    next_review: float       # epoch
    interval_days: float
    ease_factor: float
    stagnation_days: float
    direction: str
    action_type: str         # review | practice | challenge
    reason: str              # 为什么选中这个节点（可读说明）


class SpacedRepetition:
    """
    间隔重复调度器

    用法：
        sr = SpacedRepetition()
        # 从 CognitiveNode 读取当前状态，计算下次复习
        next_interval, ef = sr.compute_next(ef=2.5, interval=1.0, quality=4)
        # 更新 urgency
        urgency = sr.compute_urgency(next_interval_days=3.0, days_since_practice=2.0)
    """

    @staticmethod
    def binary_to_quality(is_correct: bool, hints_used: int = 0) -> int:
        """
        将二元答题结果映射到 SM-2 5 级质量分

        Quality mapping:
          5 = perfect (correct, no hints)
          4 = correct with hesitation (correct, hints <= 1)
          3 = correct with help (correct, hints > 1)
          2 = wrong, close (wrong, but showed understanding)
          1 = wrong, complete error
          0 = total blackout
        """
        if is_correct:
            if hints_used == 0:
                return 5
            elif hints_used <= 1:
                return 4
            else:
                return 3
        else:
            if hints_used <= 1:
                return 2
            else:
                return 1

    @staticmethod
    def compute_next(
        ef: float = DEFAULT_EASE_FACTOR,
        interval: float = INITIAL_INTERVAL,
        quality: int = 4,
        proficiency_mean: float = 0.5,
        peak_proficiency: float = 0.5,
    ) -> tuple[float, float]:
        """
        SM-2 核心：根据回答质量计算新间隔和 easiness factor

        参数：
            ef: 当前 easiness factor (1.3 - 3.0)
            interval: 当前间隔（天）
            quality: 回答质量 (0-5)
            proficiency_mean: 当前 Beta 信念均值 (0-1)
            peak_proficiency: 历史最高掌握度

        返回：
            (new_interval_days, new_ef)
        """
        # 回答质量 < 3 → 失败，重置间隔
        if quality < 3:
            new_interval = max(1.0, interval / 2.0)
            # 连续失败需要更短间隔
            if quality <= 1:
                new_interval = 1.0
            ef = max(MIN_EASE_FACTOR, ef - 0.2)
            return new_interval, ef

        # 回答质量 >= 3 → 成功
        if ef < 1.3:
            ef = 1.3

        # SM-2 EF 更新公式
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(MIN_EASE_FACTOR, min(MAX_EASE_FACTOR, ef))

        # 间隔计算：首次 1 天，第二次 6 天，之后 interval * EF
        if interval == 1.0:
            new_interval = 6.0
        else:
            new_interval = interval * ef

        # Beta 信念调整：掌握度高可拉长间隔
        if proficiency_mean >= MASTERY_THRESHOLD:
            # 掌握度越高，间隔越长（但不超过 2x）
            mastery_boost = 1.0 + (proficiency_mean - MASTERY_THRESHOLD) * 2.0
            new_interval *= min(mastery_boost, 2.0)
        elif proficiency_mean < 0.4:
            # 低于 0.4 需要更短间隔
            new_interval *= max(proficiency_mean * 2.0, 0.5)

        # peak_proficiency 保护：如果从未达到过掌握，保守间隔
        if peak_proficiency < MASTERY_THRESHOLD and new_interval > 3.0:
            new_interval = min(new_interval, 3.0)

        new_interval = min(new_interval, MAX_INTERVAL)
        return round(new_interval, 1), round(ef, 2)

    @staticmethod
    def compute_urgency(
        next_interval_days: float,
        days_since_practice: float,
        stagnation_days: float = 0.0,
        proficiency_mean: float = 0.5,
    ) -> float:
        """
        计算复习紧迫度 (0-1)

        公式：
          如果从未练习过 (days_since_practice==0) → 0.0
          超期比例 = days_since_practice / next_interval_days
          urgency = clamp(super_ratio - 0.5, 0, 1) * 1.5
          + stagnation_bonus: 停滞每 7 天 +0.1

        返回 0-1，>0.7 表示需要立即复习
        """
        if days_since_practice <= 0 or next_interval_days <= 0:
            return 0.0

        # 超期比例
        overdue_ratio = days_since_practice / next_interval_days

        # 核心 urgency：超过 50% 间隔才开始有 urgency
        if overdue_ratio <= 0.5:
            base = 0.0
        else:
            base = min((overdue_ratio - 0.5) * 1.5, 1.0)

        # 停滞惩罚：连续停滞天数追加 urgency
        stagnation_bonus = min(stagnation_days / 30.0, 0.2)

        # 低掌握度加成
        low_mastery_penalty = max(0.0, (MASTERY_THRESHOLD - proficiency_mean) * 0.3)

        urgency = min(base + stagnation_bonus + low_mastery_penalty, 1.0)
        return round(urgency, 3)

    @classmethod
    def update_node_scheduling(
        cls,
        node: "CognitiveNode",  # type: ignore  # noqa: F821
        is_correct: bool,
        hints_used: int = 0,
    ) -> dict:
        """
        根据答题结果更新 CognitiveNode 的 Scheduling 字段。

        这个方法是 submit_answer → sync 链路的终点。

        参数：
            node: CognitiveNode 实例
            is_correct: 是否答对
            hints_used: 提示次数

        返回：
            { "interval_days": float, "urgency": float, "ef": float }
        """
        now = time.time()
        days_since = (
            (now - node.practice_summary.last_practiced) / 86400.0
            if node.practice_summary.last_practiced
            else 0.0
        )

        quality = cls.binary_to_quality(is_correct, hints_used)
        current_interval = node.scheduling.next_review - (node.practice_summary.last_practiced or 0)
        current_interval_days = max(current_interval / 86400.0, 1.0) if current_interval > 0 else 1.0

        # 从 Scheduling 中读取 EF（持久化在 interleaving_group 字段后，用自定义属性）
        # 临时方案：从已知参数推断初始 EF
        ef = _get_ef(node) or DEFAULT_EASE_FACTOR

        new_interval_days, new_ef = cls.compute_next(
            ef=ef,
            interval=current_interval_days,
            quality=quality,
            proficiency_mean=node.belief.proficiency_mean,
            peak_proficiency=node.belief.peak_proficiency,
        )

        # 写入 Scheduling
        next_review_epoch = now + new_interval_days * 86400.0
        node.scheduling.next_review = next_review_epoch
        node.scheduling.urgency = cls.compute_urgency(
            next_interval_days=new_interval_days,
            days_since_practice=days_since,
            stagnation_days=node.trend.stagnation_days if node.trend else 0.0,
            proficiency_mean=node.belief.proficiency_mean,
        )

        # 决定 next_action_type
        if node.scheduling.urgency > 0.7:
            node.scheduling.next_action_type = "review"
        elif node.belief.proficiency_mean < 0.5:
            node.scheduling.next_action_type = "deep_processing"
        else:
            node.scheduling.next_action_type = "none"

        # 持久化 EF（通过 interleaving_group 字段存储，或扩展 Scheduling 模型）
        _set_ef(node, new_ef)

        logger.debug(
            "Scheduling update: %s | interval=%.1fd ef=%.2f urgency=%.3f action=%s",
            node.label, new_interval_days, new_ef,
            node.scheduling.urgency, node.scheduling.next_action_type,
        )

        return {
            "interval_days": new_interval_days,
            "urgency": node.scheduling.urgency,
            "ef": new_ef,
            "next_action_type": node.scheduling.next_action_type,
        }


# ─── EF 持久化辅助（双字段兼容） ───

_EF_PREFIX = "ef:"
_EF_MARKER = "__spaced_ef__"


def _get_ef(node) -> Optional[float]:
    """从 CognitiveNode 读取持久的 EF 值"""
    # 方案 1：从 meta_info 或自定义字段读取（优先）
    # 当前 CognitiveNode 没有 meta_info 字段完全可写
    # 方案 2：从 interleaving_group 编码读取（兼容）
    ig = node.scheduling.interleaving_group
    if ig.startswith(_EF_PREFIX):
        try:
            return float(ig[len(_EF_PREFIX):])
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse EF value from interleaving_group '%s': %s", ig, e)
    # 方案 3：从 label 后缀读取（极简兼容）
    # 无持久化 → 用掌握度推断初始 EF
    return None


def _set_ef(node, ef: float) -> None:
    """将 EF 持久化到 CognitiveNode"""
    node.scheduling.interleaving_group = f"{_EF_PREFIX}{ef}"


# 全局实例（单例）
spaced_repetition = SpacedRepetition()
