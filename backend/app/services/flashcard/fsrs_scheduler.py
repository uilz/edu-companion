"""
FSRScheduler — Free Spaced Repetition Scheduler

依据 docs/modules/flashcard/overview.md §3.1 + ADR 0002 §2:

- 跟踪每张卡片的 **stability**(稳定性) / **difficulty**(难度) / **forgetting_rate**(遗忘速率)
- 自评三档: difficult / good / easy
- 计算下次复习时间, 算法透明 (用户可手动覆盖)
- 字段级粒度的版本控制 (field_versions: {"front_text": 3, ...})

FSRS 是基于 DSR (Difficulty-Stability-Retrievability) 模型:
  R(t, S) = (1 + t/(9*S))^(-1)

简化实现 (本模块自包含):
- 不引入 fsrs 第三方依赖, 内部实现核心公式
- 暴露 compute_next() 给外部调用, 副作用为零
- 每次复习后展示: stability / difficulty / forgetting_rate / next_review
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ── 默认参数 ──────────────────────────────────────────────

# FSRS v4 默认权重 (公开常量, 真实 FSRS 通过机器学习从用户复习历史拟合)
DEFAULT_W_DIFFICULT = [
    0.4072,   # initial difficulty for "good"
    1.1829,   # initial difficulty for "easy" bonus
    0.0,      # unused
    0.0,      # unused
    0.0,      # unused
    0.0,      # unused
]

# Review rating -> adjustment factors
RATING_AGAIN = 1   # difficult
RATING_HARD = 2
RATING_GOOD = 3
RATING_EASY = 4    # easy

# 内部自评映射: difficult / good / easy -> FSRS rating
SELF_TO_RATING: dict[str, int] = {
    "difficult": RATING_AGAIN,
    "good": RATING_GOOD,
    "easy": RATING_EASY,
}

# 默认初始参数
INITIAL_STABILITY = 2.5          # 初始稳定性 (天)
INITIAL_DIFFICULTY = 5.0         # 初始难度 [1, 10]
DEFAULT_TARGET_RETENTION = 0.85  # 默认目标保留率
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
MIN_STABILITY = 0.1
MAX_STABILITY = 36500.0          # 100 年 (上限, 防止无限增长)
MIN_INTERVAL_DAYS = 1
MAX_INTERVAL_DAYS = 365          # 1 年上限 (与材料层调度一致)


# ── 数据结构 ──────────────────────────────────────────────


@dataclass
class FSRSState:
    """FSRS 调度状态 (存储于 flashcards 表的 stability/difficulty/forgetting_rate 字段)"""
    stability: float
    difficulty: float
    forgetting_rate: float
    last_review_at: datetime | None
    next_review_at: datetime | None
    review_count: int
    lapse_count: int
    target_retention: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "stability": round(self.stability, 4),
            "difficulty": round(self.difficulty, 4),
            "forgetting_rate": round(self.forgetting_rate, 4),
            "last_review_at": self.last_review_at.isoformat() if self.last_review_at else None,
            "next_review_at": self.next_review_at.isoformat() if self.next_review_at else None,
            "review_count": self.review_count,
            "lapse_count": self.lapse_count,
            "target_retention": self.target_retention,
        }


@dataclass
class ReviewComputation:
    """一次复习的完整计算结果 (供 API/UI 展示)"""
    # 调度结果
    state: FSRSState                # 复习后的状态
    interval_days: int               # 下次复习间隔 (天)
    elapsed_days: int                # 距上次复习天数
    retrievability_before: float     # 复习时的预测保留率 (用于可观测性)
    # 显式字段 — 满足"FSRS 可观测"约束
    stability_before: float
    stability_after: float
    difficulty_before: float
    difficulty_after: float
    forgetting_rate_after: float
    # UI 提示
    explanation: str                 # 人类可读解释 (e.g. "Stability 2.5→5.0 days")


# ── FSRS 计算核心 ──────────────────────────────────────────────


class FSRScheduler:
    """
    间隔重复调度器 (FSRS-inspired)

    核心方程 (简化):
        R(t, S) = (1 + t / (9 * S))^(-1)         # 保留率
        I = S * 9 * (1/R - 1)                    # 期望间隔 (反解)
        S'_again = S * w11 * exp(-w12 * (D-1))   # 失败后稳定性
        S'_good  = S * (1 + exp(w8) * (11 - D) * S^(-w9) * (exp((1-R)*w10) - 1) * (R < 1 ? w15 : 1))
        S'_easy  = S * (1 + w13)                  # 简单
    """

    # 内部固定权重 (FSRS v4 简化版)
    W = {
        "w11": 0.4,   # lapse penalty
        "w12": 0.9,   # difficulty penalty on lapse
        "w13": 1.2,   # easy bonus
        "w8": 0.75,   # difficulty effect on growth
        "w9": 0.45,   # stability effect on growth
        "w10": 1.7,   # recall probability on growth
        "w15": 0.85,  # R<1 extra factor
    }

    @staticmethod
    def retrievability(t_days: float, stability: float) -> float:
        """R(t, S) = (1 + t / (9*S))^(-1)"""
        if stability <= 0:
            return 0.0
        return (1.0 + t_days / (9.0 * stability)) ** -1

    @staticmethod
    def initial_state(target_retention: float = DEFAULT_TARGET_RETENTION) -> FSRSState:
        """新卡片的初始 FSRS 状态"""
        return FSRSState(
            stability=INITIAL_STABILITY,
            difficulty=INITIAL_DIFFICULTY,
            forgetting_rate=0.0,         # 待第一次复习后才有意义
            last_review_at=None,
            next_review_at=datetime.now(timezone.utc),
            review_count=0,
            lapse_count=0,
            target_retention=target_retention,
        )

    @staticmethod
    def compute_interval_for_target_retention(
        stability: float,
        target_retention: float = DEFAULT_TARGET_RETENTION,
    ) -> int:
        """由 stability + target_retention 反解出间隔天数

        令 R = target_retention, 反解 R(t, S) = (1 + t/(9*S))^(-1) → t = 9*S * (1/R - 1)
        """
        if stability <= 0:
            return MIN_INTERVAL_DAYS
        # 边界处理
        r = min(max(target_retention, 0.5), 0.99)
        days = 9.0 * stability * (1.0 / r - 1.0)
        return max(MIN_INTERVAL_DAYS, min(int(round(days)), MAX_INTERVAL_DAYS))

    @classmethod
    def _difficulty_update(
        cls,
        prev_difficulty: float,
        rating: int,
    ) -> float:
        """D' = D - w6 * (rating - 3)"""
        # FSRS v4: D' = D - 0.8 * (rating - 3), 截断到 [1, 10]
        delta = 0.8 * (3 - rating)  # rating=1 (difficult) 时 delta=+1.6
        new_d = prev_difficulty + delta * 0.5  # 半速更新, 避免抖动
        return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_d))

    @classmethod
    def _stability_update(
        cls,
        prev_stability: float,
        prev_difficulty: float,
        retrievability: float,
        rating: int,
    ) -> float:
        """稳定性更新

        difficult (rating=1): S' = S * w11 * exp(-w12 * (D-1))   # 大幅下降
        good     (rating=3): S' = S * (1 + exp(w8) * (11-D) * S^(-w9) * (exp((1-R)*w10) - 1) * (R<1 ? w15 : 1))
        easy     (rating=4): S' = S * (1 + w13)
        """
        w = cls.W
        D = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, prev_difficulty))
        S = max(MIN_STABILITY, prev_stability)

        if rating == RATING_AGAIN:
            new_S = S * w["w11"] * math.exp(-w["w12"] * (D - 1.0))
        elif rating == RATING_GOOD:
            factor = (
                1.0
                + math.exp(w["w8"])
                * (11.0 - D)
                * (S ** -w["w9"])
                * (math.exp((1.0 - retrievability) * w["w10"]) - 1.0)
                * (w["w15"] if retrievability < 1.0 else 1.0)
            )
            new_S = S * max(1.0, factor)
        elif rating == RATING_EASY:
            new_S = S * (1.0 + w["w13"])
        elif rating == RATING_HARD:
            new_S = S * 1.05
        else:
            new_S = S

        return max(MIN_STABILITY, min(MAX_STABILITY, new_S))

    @classmethod
    def compute_forgetting_rate(cls, difficulty: float) -> float:
        """遗忘速率: 与难度正相关 (难度越高, 遗忘越快)

        简化: forgetting_rate = (D - 1) / 9, 范围 [0, 1]
        """
        D = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, difficulty))
        return round((D - 1.0) / 9.0, 4)

    @classmethod
    def review(
        cls,
        state: FSRSState,
        self_assessment: Literal["difficult", "good", "easy"],
        now: datetime | None = None,
    ) -> ReviewComputation:
        """
        核心入口: 接收当前 FSRS 状态 + 自评结果, 返回新状态 + 完整计算细节

        设计要点 (可观测性):
        - 返回 ReviewComputation 携带 stability_before/after, difficulty_before/after, forgetting_rate_after
        - 任何 UI 可直接展示, 用户可"手动覆盖任意参数"
        """
        now = now or datetime.now(timezone.utc)
        rating = SELF_TO_RATING.get(self_assessment)
        if rating is None:
            raise ValueError(f"未知自评: {self_assessment}, 必须是 difficult/good/easy")

        # ── 计算 elapsed_days ──
        if state.last_review_at:
            elapsed_seconds = (now - state.last_review_at).total_seconds()
            elapsed_days = max(0, int(elapsed_seconds // 86400))
        else:
            elapsed_days = 0

        # ── 计算复习时的预测保留率 (基于旧 stability) ──
        r_before = cls.retrievability(elapsed_days, state.stability) if state.last_review_at else 1.0

        # ── 更新 difficulty / stability ──
        difficulty_before = state.difficulty
        stability_before = state.stability

        difficulty_after = cls._difficulty_update(difficulty_before, rating)
        stability_after = cls._stability_update(
            stability_before, difficulty_after, r_before, rating
        )
        forgetting_rate_after = cls.compute_forgetting_rate(difficulty_after)

        # ── 计算下次复习间隔 ──
        interval_days = cls.compute_interval_for_target_retention(
            stability_after, state.target_retention
        )
        next_review_at = now + timedelta(days=interval_days)

        # ── 更新元数据 ──
        new_state = FSRSState(
            stability=stability_after,
            difficulty=difficulty_after,
            forgetting_rate=forgetting_rate_after,
            last_review_at=now,
            next_review_at=next_review_at,
            review_count=state.review_count + 1,
            lapse_count=state.lapse_count + (1 if rating == RATING_AGAIN else 0),
            target_retention=state.target_retention,
        )

        # ── 生成可读解释 (UI 直接展示) ──
        explanation = (
            f"自评 {self_assessment}: 稳定性 {stability_before:.2f}→{stability_after:.2f} 天, "
            f"难度 {difficulty_before:.2f}→{difficulty_after:.2f}, "
            f"遗忘速率 {forgetting_rate_after:.2%}, "
            f"下次复习 {interval_days} 天后 ({next_review_at.strftime('%Y-%m-%d')})"
        )

        return ReviewComputation(
            state=new_state,
            interval_days=interval_days,
            elapsed_days=elapsed_days,
            retrievability_before=round(r_before, 4),
            stability_before=round(stability_before, 4),
            stability_after=round(stability_after, 4),
            difficulty_before=round(difficulty_before, 4),
            difficulty_after=round(difficulty_after, 4),
            forgetting_rate_after=forgetting_rate_after,
            explanation=explanation,
        )

    @classmethod
    def preview(
        cls,
        state: FSRSState,
        self_assessment: Literal["difficult", "good", "easy"],
    ) -> dict[str, Any]:
        """不修改状态, 仅预览结果 (用户界面上"如果选 difficult, 间隔会变成 3 天")"""
        result = cls.review(state, self_assessment)
        return {
            "stability_after": result.stability_after,
            "difficulty_after": result.difficulty_after,
            "interval_days": result.interval_days,
            "next_review_at": result.state.next_review_at.isoformat(),
        }

    @classmethod
    def reset_scheduling(
        cls,
        target_retention: float = DEFAULT_TARGET_RETENTION,
    ) -> FSRSState:
        """重置调度 — 字段级粒度控制 (field_versions['stability'] 同步递增由 service 层处理)"""
        return cls.initial_state(target_retention)

    @classmethod
    def override(
        cls,
        state: FSRSState,
        stability: float | None = None,
        difficulty: float | None = None,
        target_retention: float | None = None,
        next_review_at: datetime | None = None,
    ) -> FSRSState:
        """手动覆盖任意参数 (满足"用户可手动覆盖任意参数"约束)"""
        return FSRSState(
            stability=stability if stability is not None else state.stability,
            difficulty=difficulty if difficulty is not None else state.difficulty,
            forgetting_rate=cls.compute_forgetting_rate(difficulty) if difficulty is not None else state.forgetting_rate,
            last_review_at=state.last_review_at,
            next_review_at=next_review_at if next_review_at is not None else state.next_review_at,
            review_count=state.review_count,
            lapse_count=state.lapse_count,
            target_retention=target_retention if target_retention is not None else state.target_retention,
        )
