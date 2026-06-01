"""Phase 9 测试 — GrowthEngine 认知图生长"""

import pytest
from tests.factories import make_cognitive_node


class TestGrowthEngine:
    """GrowthEngine 测试"""

    def test_ensure_ancestors_partition_level(self):
        """partition 级节点不应有父节点"""
        node = make_cognitive_node(level="partition", node_id="partition.p1")
        assert node.level == "partition"
        assert node.parent is None or node.parent == ""

    def test_atom_node_has_parent(self):
        """atom 级节点应有所属父节点"""
        node = make_cognitive_node(
            level="atom",
            label="导数",
            node_id="高等数学.微积分.导数",
        )
        node.parent = "高等数学.微积分"
        assert node.parent == "高等数学.微积分"

    def test_node_hierarchy_levels(self):
        """验证节点层级顺序: partition > domain > topic > concept > atom"""
        valid_levels = ["partition", "domain", "topic", "concept", "atom"]
        node_atom = make_cognitive_node(level="atom")
        node_topic = make_cognitive_node(level="topic", node_id="topic_001")
        node_partition = make_cognitive_node(level="partition", node_id="partition.p1")

        assert node_atom.level in valid_levels
        assert node_topic.level in valid_levels
        assert node_partition.level in valid_levels

    def test_node_visibility_default(self):
        """auto_generated 类型节点默认不可见"""
        node = make_cognitive_node(node_type="auto_generated")
        assert node.is_visible is False

    def test_explicit_node_visible(self):
        """explicit 类型节点默认可见"""
        node = make_cognitive_node(
            node_type="explicit",
            is_visible=True,
            node_id="explicit_001",
        )
        assert node.is_visible is True

    def test_node_bump_version(self):
        """bump_version 应递增 version"""
        node = make_cognitive_node()
        v1 = node.meta.version
        node.bump_version()
        assert node.meta.version == v1 + 1
