"""session.py _derive_topic_status 单测。"""

import pytest
from app.api.session.session import _derive_topic_status


class TestDeriveTopicStatus:
    """topic_status 分档逻辑测试。"""

    def test_high_mastery_very_stable(self):
        assert _derive_topic_status([{"skill": "矩阵", "after": 0.85}]) == "很稳"

    def test_boundary_80_is_stable(self):
        assert _derive_topic_status([{"skill": "递归", "after": 0.8}]) == "很稳"

    def test_mid_high_is_familiar(self):
        assert _derive_topic_status([{"skill": "矩阵", "after": 0.65}]) == "比较熟了"

    def test_boundary_60_is_familiar(self):
        assert _derive_topic_status([{"skill": "递归", "after": 0.6}]) == "比较熟了"

    def test_mid_is_consolidating(self):
        assert _derive_topic_status([{"skill": "矩阵", "after": 0.45}]) == "正在巩固"

    def test_boundary_40_is_consolidating(self):
        assert _derive_topic_status([{"skill": "递归", "after": 0.4}]) == "正在巩固"

    def test_low_mid_is_beginning(self):
        assert _derive_topic_status([{"skill": "矩阵", "after": 0.25}]) == "刚开始"

    def test_boundary_20_is_beginning(self):
        assert _derive_topic_status([{"skill": "递归", "after": 0.2}]) == "刚开始"

    def test_very_low_is_new(self):
        assert _derive_topic_status([{"skill": "矩阵", "after": 0.05}]) == "新朋友"

    def test_empty_skill_gains_returns_none(self):
        assert _derive_topic_status([]) is None

    def test_none_skill_gains_returns_none(self):
        assert _derive_topic_status([]) is None  # empty list same as no data

    def test_only_uses_first_skill(self):
        """多个 skill 时仅取第一个作为核心 topic。"""
        result = _derive_topic_status([
            {"skill": "矩阵乘法", "after": 0.9},
            {"skill": "线性变换", "after": 0.2},
        ])
        assert result == "很稳"
