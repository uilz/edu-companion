"""测试 CognitiveNodeWriter — 统一认知节点写入器

使用 MemoryCognitiveNodeRepository 作为测试替身。
"""

import sys
from pathlib import Path

# 确保 backend/ 在 sys.path（参考 conftest.py 的模式）
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from app.domain.cognitive import set_repo
from app.domain.cognitive.writer import CognitiveNodeWriter
from app.domain.cognitive.memory_repository import MemoryCognitiveNodeRepository


# ── Fixtures ──


@pytest.fixture
def repo():
    """每个测试使用独立的 MemoryCognitiveNodeRepository 实例"""
    r = MemoryCognitiveNodeRepository()
    set_repo(r)
    return r


@pytest.fixture
def writer():
    """默认 CognitiveNodeWriter 实例（user_id="test_user"）"""
    return CognitiveNodeWriter(user_id="test_user")


@pytest.fixture
def root_partition(repo, writer):
    """创建一个根分区作为后续测试的父节点"""
    return writer.create_node(label="根分区", level="partition")


# ── 测试 create_node ──


class TestCreateNode:
    """创建新节点"""

    def test_create_partition_node(self, repo, writer):
        """创建 partition 级别节点，验证 label/level/parent"""
        node = writer.create_node(label="机器学习", level="partition")
        assert node is not None
        assert node.label == "机器学习"
        assert node.level == "partition"
        assert node.parent is None

        # 验证已持久化到 repo
        saved = repo.get_node(node.id, "test_user")
        assert saved is not None
        assert saved.label == "机器学习"
        assert saved.level == "partition"

    def test_create_node_with_parent(self, repo, writer):
        """创建带父节点的子节点"""
        parent = writer.create_node(label="知识领域", level="partition")
        child = writer.create_node(label="机器学习", level="domain", parent_id=parent.id)
        assert child.parent == parent.id
        assert child.level == "domain"

        saved = repo.get_node(child.id, "test_user")
        assert saved is not None
        assert saved.parent == parent.id

    def test_create_node_with_node_type(self, repo, writer):
        """测试 node_type 参数"""
        node = writer.create_node(
            label="自动生成节点",
            level="topic",
            parent_id="root",
            node_type="auto_generated",
        )
        assert node.node_type == "auto_generated"

        saved = repo.get_node(node.id, "test_user")
        assert saved.node_type == "auto_generated"

    def test_create_node_with_created_by(self, repo, writer):
        """测试 created_by 参数（调用不报错即可）"""
        node = writer.create_node(
            label="系统节点",
            level="topic",
            parent_id="root",
            created_by="system",
        )
        assert node is not None
        # created_by 通过 _write_extra_fields → update_extra_fields 写入，
        # MemoryCognitiveNodeRepository.update_extra_fields 是 no-op，
        # 此处验证节点创建成功且 API 调用正常
        assert node.label == "系统节点"

    def test_create_node_not_visible(self, repo, writer):
        """测试 is_visible=False"""
        node = writer.create_node(
            label="隐藏节点",
            level="topic",
            parent_id="root",
            is_visible=False,
        )
        assert node.is_visible is False

        saved = repo.get_node(node.id, "test_user")
        assert saved.is_visible is False

    def test_create_node_visible_by_default(self, repo, writer):
        """测试 is_visible 默认值为 True"""
        node = writer.create_node(label="默认可见节点", level="topic", parent_id="root")
        assert node.is_visible is True


class TestCreateNodeIdempotent:
    """create_node 幂等性"""

    def test_same_parent_level_label_returns_same_node(self, repo, writer):
        """同一 parent+level+label 不重复创建，返回同一节点"""
        node1 = writer.create_node(label="微积分", level="domain", parent_id="root")
        node2 = writer.create_node(label="微积分", level="domain", parent_id="root")
        assert node1.id == node2.id

    def test_different_parent_creates_different_node(self, repo, writer):
        """相同 level+label 但不同 parent，创建不同节点"""
        parent_a = writer.create_node(label="分区A", level="partition")
        parent_b = writer.create_node(label="分区B", level="partition")
        node_a = writer.create_node(label="数学", level="domain", parent_id=parent_a.id)
        node_b = writer.create_node(label="数学", level="domain", parent_id=parent_b.id)
        assert node_a.id != node_b.id

    def test_different_label_creates_different_node(self, repo, writer):
        """相同 parent+level 但不同 label，创建不同节点"""
        node1 = writer.create_node(label="微积分", level="domain", parent_id="root")
        node2 = writer.create_node(label="线性代数", level="domain", parent_id="root")
        assert node1.id != node2.id


# ── 测试 ensure_partition ──


class TestEnsurePartition:
    """ ensure_partition 操作"""

    def test_ensure_partition_creates_node(self, repo, writer):
        """创建分区节点"""
        node = writer.ensure_partition(label="数据科学", emoji="📐", description="数据科学分区")
        assert node.level == "partition"
        assert node.parent is None
        assert "📐" in node.label
        assert "数据科学" in node.label

    def test_ensure_partition_without_emoji(self, repo, writer):
        """创建分区节点（无 emoji）"""
        node = writer.ensure_partition(label="文科")
        assert node.level == "partition"
        assert node.label == "文科"

    def test_ensure_partition_idempotent(self, repo, writer):
        """ensure_partition 幂等"""
        p1 = writer.ensure_partition(label="语言学")
        p2 = writer.ensure_partition(label="语言学")
        assert p1.id == p2.id


# ── 测试 ensure_domain ──


class TestEnsureDomain:
    """ ensure_domain 操作"""

    def test_ensure_domain_creates_node(self, repo, writer, root_partition):
        """创建领域节点"""
        domain = writer.ensure_domain(
            label="电磁学",
            parent_id=root_partition.id,
            emoji="⚡",
            description="电磁学领域",
        )
        assert domain.level == "domain"
        assert domain.parent == root_partition.id
        assert "⚡" in domain.label

    def test_ensure_domain_idempotent(self, repo, writer, root_partition):
        """ensure_domain 幂等"""
        d1 = writer.ensure_domain(label="力学", parent_id=root_partition.id)
        d2 = writer.ensure_domain(label="力学", parent_id=root_partition.id)
        assert d1.id == d2.id


# ── 测试 ensure_topic ──


class TestEnsureTopic:
    """ ensure_topic 操作"""

    def test_ensure_topic_creates_node(self, repo, writer, root_partition):
        """创建专题节点"""
        domain = writer.ensure_domain(label="物理", parent_id=root_partition.id)
        topic = writer.ensure_topic(
            label="静电场",
            parent_id=domain.id,
            emoji="🔋",
            description="静电场专题",
        )
        assert topic.level == "topic"
        assert topic.parent == domain.id
        assert "🔋" in topic.label

    def test_ensure_topic_idempotent(self, repo, writer, root_partition):
        """ensure_topic 幂等"""
        domain = writer.ensure_domain(label="CS", parent_id=root_partition.id)
        t1 = writer.ensure_topic(label="数据结构", parent_id=domain.id)
        t2 = writer.ensure_topic(label="数据结构", parent_id=domain.id)
        assert t1.id == t2.id


# ── 测试 ensure 链式调用 ──


class TestEnsureChain:
    """partition → domain → topic 链式调用"""

    def test_partition_domain_topic_chain(self, repo, writer):
        """从分区到专题的完整链路"""
        partition = writer.ensure_partition(label="工科", emoji="🔧")
        domain = writer.ensure_domain(label="计算机科学", parent_id=partition.id, emoji="💻")
        topic = writer.ensure_topic(label="算法", parent_id=domain.id, emoji="📊")

        assert partition.level == "partition"
        assert domain.level == "domain"
        assert domain.parent == partition.id
        assert topic.level == "topic"
        assert topic.parent == domain.id

        # 验证层级关系持久化
        domain_children = repo.get_children(partition.id, "test_user")
        assert any(c.id == domain.id for c in domain_children)

        topic_children = repo.get_children(domain.id, "test_user")
        assert any(c.id == topic.id for c in topic_children)
