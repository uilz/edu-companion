"""Phase 10 测试：AdaptiveSelector — 队列生成 + 优先级打分"""

import pytest
import time

from app.domain.cognitive.models import (
    CognitiveNode, Belief, Scheduling, PracticeSummary, Trend,
)
from app.services.analytics.adaptive_selector import AdaptiveSelector, ReviewResult


class TestScoreNodes:
    """节点打分逻辑测试"""

    @pytest.fixture
    def selector(self):
        return AdaptiveSelector()

    def make_node(
        self, node_id: str, label: str,
        level: str = "atom",
        proficiency: float = 0.5,
        urgency: float = 0.0,
        attempts: int = 0,
        days_since: float = 0.0,
        stagnation: float = 0.0,
    ) -> CognitiveNode:
        now = time.time()
        return CognitiveNode(
            id=node_id,
            label=label,
            level=level,
            belief=Belief(
                alpha=2.0 + proficiency * 3,
                beta=2.0 + (1 - proficiency) * 3,
                proficiency_mean=proficiency,
            ),
            scheduling=Scheduling(urgency=urgency, next_review=now + 86400 if urgency < 0.5 else now - 86400),
            practice_summary=PracticeSummary(
                total_attempts=attempts,
                correct_attempts=max(0, int(attempts * proficiency)),
                last_practiced=now - days_since * 86400 if days_since > 0 else None,
            ),
            trend=Trend(stagnation_days=stagnation, direction="stable"),
        )

    def test_review_priority_high_urgency(self, selector):
        """urgency > 0.7 的节点应该排前面"""
        nodes = [
            self.make_node("n1", "导数", urgency=0.8),
            self.make_node("n2", "极限", urgency=0.1),
        ]
        results = selector._score_nodes(nodes, "adaptive")
        top = max(results, key=lambda x: x["total_score"])
        assert top["node"].id == "n1"

    def test_zpd_sweet_spot(self, selector):
        """掌握度 0.5 的节点 ZPD 分最高"""
        scores = []
        for mu in [0.2, 0.5, 0.8]:
            node = self.make_node(f"n{int(mu*10)}", f"skill_{mu}", proficiency=mu)
            scored = selector._score_nodes([node], "adaptive")
            scores.append(scored[0]["zpd_score"])
        # 0.5 应该最高
        assert scores[1] > scores[0]
        assert scores[1] > scores[2]

    def test_explore_new_nodes(self, selector):
        """未练习过的节点探索分高"""
        nodes = [
            self.make_node("n1", "新知识", attempts=0),
            self.make_node("n2", "已练习", attempts=10),
        ]
        results = selector._score_nodes(nodes, "adaptive")
        n1_score = next(r for r in results if r["node"].id == "n1")
        n2_score = next(r for r in results if r["node"].id == "n2")
        assert n1_score["explore_score"] > n2_score["explore_score"]

    def test_review_mode_only_urgency(self, selector):
        """review 模式只用 urgency"""
        nodes = [
            self.make_node("n1", "高紧迫", urgency=0.9, proficiency=0.5),
            self.make_node("n2", "低紧迫", urgency=0.1, proficiency=0.5),
        ]
        results = selector._score_nodes(nodes, "review")
        n1 = next(r for r in results if r["node"].id == "n1")
        n2 = next(r for r in results if r["node"].id == "n2")
        assert n1["review_score"] > n2["review_score"]
        assert n1["zpd_score"] == 0.0  # review 模式 ZPD 不参与

    def test_explore_mode_only_explore(self, selector):
        """explore 模式只用探索分"""
        node = self.make_node("n1", "新知识", attempts=0)
        results = selector._score_nodes([node], "explore")
        assert results[0]["review_score"] == 0.0
        assert results[0]["zpd_score"] == 0.0
        assert results[0]["explore_score"] > 0.5

    def test_concept_nodes_included(self, selector):
        """concept 级别节点也被包含"""
        node = self.make_node("n1", "概念", level="concept")
        results = selector._score_nodes([node], "adaptive")
        assert len(results) == 1


class TestToReviewResult:
    """ReviewResult 转换测试"""

    def test_high_urgency_reason(self):
        node = CognitiveNode(
            id="n1", label="微积分",
            belief=Belief(proficiency_mean=0.5),
            scheduling=Scheduling(urgency=0.85),
            practice_summary=PracticeSummary(total_attempts=5),
            trend=Trend(stagnation_days=0.0),
        )
        item = {"review_score": 0.85, "zpd_score": 0.3, "explore_score": 0.2, "days_since": 7.0}
        result = AdaptiveSelector._to_review_result(node, item)
        assert result.action_type == "review"
        assert "紧迫度" in result.reason

    def test_low_proficiency_practice(self):
        node = CognitiveNode(
            id="n1", label="困难概念",
            belief=Belief(proficiency_mean=0.3),
            scheduling=Scheduling(urgency=0.0),
            practice_summary=PracticeSummary(total_attempts=15),
            trend=Trend(stagnation_days=5.0),
        )
        item = {"review_score": 0.0, "zpd_score": 0.0, "explore_score": 0.0, "days_since": 1.0}
        result = AdaptiveSelector._to_review_result(node, item)
        assert result.action_type == "practice"


class TestZPDEdgeCases:
    """ZPD 边界情况测试"""

    @pytest.fixture
    def selector(self):
        return AdaptiveSelector()

    def test_zero_proficiency(self, selector):
        """掌握度 0 → ZPD 分 0"""
        node = CognitiveNode(
            id="n1", label="零掌握",
            belief=Belief(proficiency_mean=0.0),
            scheduling=Scheduling(),
            practice_summary=PracticeSummary(),
            trend=Trend(),
        )
        results = selector._score_nodes([node], "adaptive")
        assert results[0]["zpd_score"] == 0.0

    def test_full_proficiency(self, selector):
        """掌握度 1.0 → ZPD 分 0"""
        node = CognitiveNode(
            id="n1", label="已掌握",
            belief=Belief(proficiency_mean=1.0),
            scheduling=Scheduling(),
            practice_summary=PracticeSummary(),
            trend=Trend(),
        )
        results = selector._score_nodes([node], "adaptive")
        assert results[0]["zpd_score"] == 0.0

    def test_mid_proficiency(self, selector):
        """掌握度 0.5 → ZPD 分高"""
        node = CognitiveNode(
            id="n1", label="甜点区",
            belief=Belief(proficiency_mean=0.5),
            scheduling=Scheduling(),
            practice_summary=PracticeSummary(),
            trend=Trend(),
        )
        results = selector._score_nodes([node], "adaptive")
        assert results[0]["zpd_score"] > 0.5
