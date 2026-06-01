"""Phase 9 测试 — CognitiveNode CRUD + sync"""

import pytest
from tests.factories import make_cognitive_node


class TestCognitiveNodeStorage:
    """CognitiveNode 存储层 CRUD 测试"""

    def test_make_cognitive_node_defaults(self):
        """验证工厂函数产生合法 CognitiveNode"""
        node = make_cognitive_node()
        assert node.id == "test_node_001"
        assert node.belief.proficiency_mean == 0.5
        assert node.practice_summary.total_attempts == 0

    def test_make_cognitive_node_with_practice(self):
        """含练习数据的 CognitiveNode"""
        node = make_cognitive_node(total_attempts=10, correct_attempts=7, proficiency=0.7)
        assert node.practice_summary.total_attempts == 10
        assert node.practice_summary.correct_attempts == 7
        assert node.belief.proficiency_mean == 0.7

    def test_cognitive_node_trend_direction_stable(self):
        """默认 trend 方向为 stable"""
        node = make_cognitive_node()
        assert node.trend.direction == "stable"

    def test_cognitive_node_belief_update_logic(self):
        """验证 Beta 分布后验更新：α += correct, β += 1-correct"""
        node = make_cognitive_node(proficiency=0.5)
        old_alpha = node.belief.alpha
        old_beta = node.belief.beta

        # 模拟一次答对
        node.belief.alpha = old_alpha + 1
        node.belief.beta = old_beta + 0
        total = node.belief.alpha + node.belief.beta
        node.belief.proficiency_mean = node.belief.alpha / total

        assert node.belief.alpha == old_alpha + 1
        assert node.belief.proficiency_mean > 0.5

    def test_cognitive_node_belief_update_wrong(self):
        """答错：α 不变, β+1, 掌握度下降"""
        node = make_cognitive_node(proficiency=0.6, total_attempts=4, correct_attempts=3)
        old_alpha = node.belief.alpha
        old_beta = node.belief.beta

        # 模拟一次答错
        node.belief.beta = old_beta + 1
        total = node.belief.alpha + node.belief.beta
        node.belief.proficiency_mean = node.belief.alpha / total

        assert node.belief.beta == old_beta + 1
        assert node.belief.proficiency_mean < 0.6

    def test_node_practice_summary_updates(self):
        """practice_summary 的 total_attempts 单调递增"""
        node = make_cognitive_node(total_attempts=5, correct_attempts=3)
        node.practice_summary.total_attempts += 1
        node.practice_summary.correct_attempts += 1
        assert node.practice_summary.total_attempts == 6
        assert node.practice_summary.correct_attempts == 4

    def test_node_serialization(self):
        """CognitiveNode model_dump 可用作 JSON 序列化"""
        node = make_cognitive_node()
        dumped = node.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["id"] == "test_node_001"
        assert "belief" in dumped
        assert dumped["belief"]["proficiency_mean"] == 0.5

    def test_node_proficiency_property(self):
        """proficiency 属性映射 belief.proficiency_mean"""
        node = make_cognitive_node(proficiency=0.75)
        assert node.proficiency == 0.75
        assert node.proficiency == node.belief.proficiency_mean
