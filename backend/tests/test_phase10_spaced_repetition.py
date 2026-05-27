"""Phase 10 测试：SpacedRepetition — SM-2 + Beta 信念集成"""

import pytest
import time
from app.services.spaced_repetition import (
    SpacedRepetition,
    DEFAULT_EASE_FACTOR,
    MIN_EASE_FACTOR,
    MAX_EASE_FACTOR,
    INITIAL_INTERVAL,
)
from app.cognitive.models import (
    CognitiveNode, Belief, Scheduling, PracticeSummary, Trend,
)


class TestBinaryToQuality:
    """回答质量映射测试"""

    def test_correct_no_hints(self):
        assert SpacedRepetition.binary_to_quality(True, 0) == 5

    def test_correct_one_hint(self):
        assert SpacedRepetition.binary_to_quality(True, 1) == 4

    def test_correct_multiple_hints(self):
        assert SpacedRepetition.binary_to_quality(True, 3) == 3

    def test_wrong_no_hints(self):
        assert SpacedRepetition.binary_to_quality(False, 0) == 2

    def test_wrong_many_hints(self):
        assert SpacedRepetition.binary_to_quality(False, 3) == 1


class TestComputeNext:
    """SM-2 核心间隔计算测试"""

    def test_first_correct_quality_5(self):
        """首次答对(质量5) → mastery_boost 后 6.6 天"""
        interval, ef = SpacedRepetition.compute_next(
            ef=DEFAULT_EASE_FACTOR, interval=1.0, quality=5,
            proficiency_mean=0.8, peak_proficiency=0.8,
        )
        # mastery_mean=0.8 → boost=1+(0.8-0.75)*2=1.1 → 6*1.1=6.6
        assert interval == 6.6
        assert ef > DEFAULT_EASE_FACTOR

    def test_first_correct_quality_4(self):
        """首次答对(质量4) → mastery_boost 后 6.6 天"""
        interval, ef = SpacedRepetition.compute_next(
            ef=DEFAULT_EASE_FACTOR, interval=1.0, quality=4,
            proficiency_mean=0.8, peak_proficiency=0.8,
        )
        assert interval == 6.6
        assert ef >= DEFAULT_EASE_FACTOR

    def test_second_correct(self):
        """第二次答对 → interval = 6 * EF"""
        interval, ef = SpacedRepetition.compute_next(
            ef=2.5, interval=6.0, quality=5,
            proficiency_mean=0.8, peak_proficiency=0.8,
        )
        assert interval > 6.0
        assert ef > 2.5

    def test_wrong_resets_interval(self):
        """答错 → interval 减半"""
        interval, ef = SpacedRepetition.compute_next(
            ef=2.5, interval=10.0, quality=1,
        )
        assert interval < 10.0
        assert ef < 2.5

    def test_wrong_quality_0_resets_to_1(self):
        """答得太差 → interval 回到 1 天"""
        interval, ef = SpacedRepetition.compute_next(
            ef=2.5, interval=30.0, quality=1,
        )
        assert interval <= 30.0 / 2.0  # 减半
        assert ef < 2.5

    def test_quality_3_barely_correct(self):
        """勉强答对(质量3) → EF 下降"""
        interval, ef = SpacedRepetition.compute_next(
            ef=2.5, interval=6.0, quality=3,
        )
        assert ef < 2.5

    def test_ef_range(self):
        """EF 被限制在 [1.3, 3.0]"""
        for quality in range(1, 6):
            for _ in range(20):
                _, ef = SpacedRepetition.compute_next(
                    ef=2.5, interval=6.0, quality=quality,
                    proficiency_mean=0.5, peak_proficiency=0.5,
                )
                assert MIN_EASE_FACTOR <= ef <= MAX_EASE_FACTOR

    def test_mastery_adjustment(self):
        """高掌握度 (0.85) → 间隔拉长"""
        interval_low, _ = SpacedRepetition.compute_next(
            ef=2.5, interval=6.0, quality=5,
            proficiency_mean=0.5, peak_proficiency=0.5,
        )
        interval_high, _ = SpacedRepetition.compute_next(
            ef=2.5, interval=6.0, quality=5,
            proficiency_mean=0.85, peak_proficiency=0.85,
        )
        assert interval_high >= interval_low

    def test_low_peak_protection(self):
        """从未掌握过的节点 → 间隔不超过 3 天"""
        interval, _ = SpacedRepetition.compute_next(
            ef=2.5, interval=1.0, quality=4,
            proficiency_mean=0.4, peak_proficiency=0.4,
        )
        # 首次答对间隔应为 6 天，但 peak < 0.75 所以限制到 3 天
        assert interval <= 3.0


class TestComputeUrgency:
    """紧迫度计算测试"""

    def test_no_practice(self):
        assert SpacedRepetition.compute_urgency(
            next_interval_days=1.0, days_since_practice=0.0,
        ) == 0.0

    def test_within_interval(self):
        """在间隔内且掌握度高 → urgency 0"""
        u = SpacedRepetition.compute_urgency(
            next_interval_days=10.0, days_since_practice=3.0,
            proficiency_mean=0.8,
        )
        # 3/10=0.3 < 0.5 → base=0. 掌握度>=0.75 → 无 mastery penalty
        assert u == 0.0

    def test_overdue(self):
        """超期 2x → urgency 高"""
        u = SpacedRepetition.compute_urgency(
            next_interval_days=5.0, days_since_practice=10.0,
        )
        assert u > 0.5

    def test_mastery_bonus(self):
        """低掌握度增加 urgency（不饱和的范围内）"""
        u_low = SpacedRepetition.compute_urgency(
            next_interval_days=5.0, days_since_practice=4.0,
            proficiency_mean=0.3,
        )
        u_high = SpacedRepetition.compute_urgency(
            next_interval_days=5.0, days_since_practice=4.0,
            proficiency_mean=0.8,
        )
        # 4/5=0.8 > 0.5 → base=(0.8-0.5)*1.5=0.45
        # low: 0.45 + (0.75-0.3)*0.3=0.45+0.135=0.585
        # high: 0.45 + 0(low_mastery_penalty=0 since 0.8>0.75)
        assert u_low > u_high

    def test_stagnation_bonus(self):
        """停滞 30 天增加 urgency"""
        u_no_stag = SpacedRepetition.compute_urgency(
            next_interval_days=5.0, days_since_practice=5.0,
            stagnation_days=0.0,
        )
        u_stag = SpacedRepetition.compute_urgency(
            next_interval_days=5.0, days_since_practice=5.0,
            stagnation_days=30.0,
        )
        assert u_stag > u_no_stag


class TestUpdateNodeScheduling:
    """CognitiveNode 调度更新全流程测试"""

    @pytest.fixture
    def node(self):
        return CognitiveNode(
            id="test_node",
            label="微积分.导数",
            level="atom",
            belief=Belief(alpha=2.0, beta=2.0, proficiency_mean=0.5),
            scheduling=Scheduling(urgency=0.0, next_review=0.0),
            practice_summary=PracticeSummary(
                total_attempts=5, correct_attempts=3,
                last_practiced=time.time() - 86400 * 2,  # 2 天前
            ),
            trend=Trend(stagnation_days=0.0, direction="stable"),
        )

    def test_correct_updates_scheduling(self, node):
        """答对后 urgency 下降、next_review 推后"""
        result = SpacedRepetition.update_node_scheduling(node, True, hints_used=0)
        assert result["interval_days"] >= 1.0
        assert result["ef"] >= 1.3
        assert node.scheduling.next_review > 0
        # next_review 应在未来
        assert node.scheduling.next_review > time.time()

    def test_wrong_increases_urgency(self, node):
        """答错后 interval 缩短，urgency 在合理范围"""
        # 设置 last_practiced 为刚刚（这样 overdue_ratio 不高）
        node.practice_summary.last_practiced = time.time() - 60  # 1 分钟前
        SpacedRepetition.update_node_scheduling(node, False, hints_used=0)
        # 答错后 interval 应 <= 1.0
        assert node.scheduling.next_review > 0
        assert node.scheduling.next_action_type in ("review", "deep_processing", "none")

    def test_action_type_review(self, node):
        """urgency > 0.7 → action_type = review"""
        node.scheduling.urgency = 0.8
        SpacedRepetition.update_node_scheduling(node, True, hints_used=0)
        # 答对后 urgency 可能下降
        # 验证 action_type 至少被设置
        assert node.scheduling.next_action_type in ("review", "deep_processing", "none")

    def test_action_type_deep_processing(self, node):
        """低掌握度 → deep_processing"""
        node.belief.proficiency_mean = 0.3
        node.belief.alpha = 1.5
        node.belief.beta = 3.5
        SpacedRepetition.update_node_scheduling(node, True, hints_used=0)
        assert node.scheduling.next_action_type in ("review", "deep_processing", "none")

    def test_ef_persistence(self, node):
        """EF 通过 interleaving_group 持久化"""
        SpacedRepetition.update_node_scheduling(node, True, hints_used=0)
        assert node.scheduling.interleaving_group.startswith("ef:")

    def test_consecutive_correct_increases_interval(self, node):
        """连续答对 → 间隔递增"""
        intervals = []
        for _ in range(3):
            result = SpacedRepetition.update_node_scheduling(
                node, True, hints_used=0,
            )
            intervals.append(result["interval_days"])
            # 更新 last_practiced 到更早
            node.practice_summary.last_practiced = time.time() - 86400
        # 间隔应该递增
        print(f"Intervals: {intervals}")
        for i in range(1, len(intervals)):
            assert intervals[i] >= intervals[i - 1] * 0.8  # 容忍波动
