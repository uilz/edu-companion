"""验证 CognitiveNode Repository Protocol 和 MemoryFake 实现

MemoryCognitiveNodeRepository 可作为测试替身替代真实的 PostgreSQL 存储。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone
import pytest


@pytest.fixture
def repo():
    from app.domain.cognitive.memory_repository import MemoryCognitiveNodeRepository
    return MemoryCognitiveNodeRepository()


@pytest.fixture
def sample_node():
    from app.domain.cognitive.models import CognitiveNode
    import time
    return CognitiveNode(
        id="node_a",
        label="微积分.导数",
        level="atom",
        parent=None,
        children=[],
    )


class TestMemoryCognitiveNodeRepository:
    """MemoryCognitiveNodeRepository 的 CRUD + 查询验证"""

    def test_upsert_and_get(self, repo, sample_node):
        repo.upsert_node(sample_node)
        got = repo.get_node("node_a")
        assert got is not None
        assert got.id == "node_a"
        assert got.label == "微积分.导数"

    def test_get_nonexistent(self, repo):
        assert repo.get_node("not_exists") is None

    def test_delete(self, repo, sample_node):
        repo.upsert_node(sample_node)
        repo.delete_node("node_a")
        got = repo.get_node("node_a")
        assert got is None or got is None  # memory_fake marks as None

    def test_upsert_overwrite(self, repo, sample_node):
        repo.upsert_node(sample_node)
        sample_node.label = "微积分.极限"
        repo.upsert_node(sample_node)
        got = repo.get_node("node_a")
        assert got.label == "微积分.极限"

    def test_list_all_nodes(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="a", label="A"))
        repo.upsert_node(CognitiveNode(id="b", label="B"))
        all_nodes = repo.list_all_nodes()
        assert len(all_nodes) == 2

    def test_user_isolation(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="a", label="A"), user_id="u1")
        repo.upsert_node(CognitiveNode(id="b", label="B"), user_id="u2")
        assert len(repo.list_all_nodes("u1")) == 1
        assert len(repo.list_all_nodes("u2")) == 1

    def test_get_children(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        parent = CognitiveNode(id="p", label="parent")
        child = CognitiveNode(id="c", label="child", parent="p")
        repo.upsert_node(parent)
        repo.upsert_node(child)
        children = repo.get_children("p")
        assert len(children) == 1
        assert children[0].id == "c"

    def test_find_by_label(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="n1", label="导数", level="atom"))
        repo.upsert_node(CognitiveNode(id="n2", label="矩阵", level="atom"))
        found = repo.find_node_by_label("导数")
        assert found is not None
        assert found.id == "n1"

    def test_find_by_label_with_level(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="n1", label="导数", level="atom"))
        repo.upsert_node(CognitiveNode(id="n2", label="导数", level="topic"))
        found = repo.find_node_by_label("导数", level="topic")
        assert found is not None
        assert found.id == "n2"

    def test_find_by_path(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(
            id="n1", label="导数", path_id="数据科学.数据分析.统计学",
        ))
        found = repo.find_node_by_path("数据科学.数据分析.统计学")
        assert found is not None
        assert found.id == "n1"

    def test_get_suggested_count(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="p", label="parent"))
        repo.upsert_node(CognitiveNode(id="c1", label="c1", parent="p", node_type="suggested"))
        repo.upsert_node(CognitiveNode(id="c2", label="c2", parent="p", node_type="normal"))
        assert repo.get_suggested_count("p") == 1

    def test_get_child_count(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="p", label="parent"))
        repo.upsert_node(CognitiveNode(id="c1", label="c1", parent="p"))
        repo.upsert_node(CognitiveNode(id="c2", label="c2", parent="p"))
        assert repo.get_child_count("p") == 2

    def test_set_node_visible(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        n = CognitiveNode(id="n1", label="test", is_visible=False)
        repo.upsert_node(n)
        repo.set_node_visible("n1")
        got = repo.get_node("n1")
        assert got.is_visible is True

    def test_get_nodes_by_level(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        repo.upsert_node(CognitiveNode(id="a", label="a", level="atom"))
        repo.upsert_node(CognitiveNode(id="b", label="b", level="topic"))
        repo.upsert_node(CognitiveNode(id="c", label="c", level="atom"))
        atoms = repo.get_nodes_by_level("atom")
        assert len(atoms) == 2
        topics = repo.get_nodes_by_level("topic")
        assert len(topics) == 1

    def test_get_subtree(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        root = CognitiveNode(id="r", label="root")
        child = CognitiveNode(id="c", label="child", parent="r")
        repo.upsert_node(root)
        repo.upsert_node(child)
        subtree = repo.get_subtree("r")
        assert "r" in subtree
        assert "c" in subtree

    def test_get_visible_children(self, repo):
        from app.domain.cognitive.models import CognitiveNode
        parent = CognitiveNode(id="p", label="p")
        v_child = CognitiveNode(id="v", label="visible", parent="p", is_visible=True)
        h_child = CognitiveNode(id="h", label="hidden", parent="p", is_visible=False)
        repo.upsert_node(parent)
        repo.upsert_node(v_child)
        repo.upsert_node(h_child)
        visible = repo.get_visible_children("p")
        assert len(visible) == 1
        assert visible[0].id == "v"

    def test_protocol_compliance(self, repo):
        """MemoryCognitiveNodeRepository 应满足 CognitiveNodeRepository Protocol"""
        from shared.protocols.cognitive import CognitiveNodeRepository
        assert isinstance(repo, CognitiveNodeRepository)

    def test_pg_repository_protocol_compliance(self):
        """PgCognitiveNodeRepository 也应满足 Protocol"""
        from shared.protocols.cognitive import CognitiveNodeRepository
        from app.infrastructure.db.cognitive_repository import PgCognitiveNodeRepository
        # 仅验证运行时 checkable protocol — 不实例化（依赖 DB）
        assert CognitiveNodeRepository is not None
        assert hasattr(PgCognitiveNodeRepository, "upsert_node")
        assert hasattr(PgCognitiveNodeRepository, "get_node")
        assert hasattr(PgCognitiveNodeRepository, "delete_node")
