"""验证 tree_crud.py 拆分为 4 个子模块的正确性

确保：
- tree_ops.py 仍然导出 TreeOpsService 和 tree_ops 全局实例
- 所有公开方法可通过 tree_ops 调用
- 调用方 import from tree_ops 不受影响
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock, PropertyMock
import pytest


class DummyNode:
    """模拟 TreeNode — 仅用于测试需要的字段"""
    def __init__(self, id="n1", parent_id="r", partition_id="p1",
                 conversation_id="c1", role="user", content_blocks=None,
                 text_summary="hello", children_ids=None, is_deleted=False,
                 has_sub_branches=False, sub_branch_ids=None,
                 sub_branch_summaries=None, has_modified_version=False):
        self.id = id
        self.parent_id = parent_id
        self.partition_id = partition_id
        self.conversation_id = conversation_id
        self.role = role
        self.content_blocks = content_blocks or []
        self.text_summary = text_summary
        self.children_ids = children_ids or []
        self.is_deleted = is_deleted
        self.has_sub_branches = has_sub_branches
        self.sub_branch_ids = sub_branch_ids or []
        self.sub_branch_summaries = sub_branch_summaries or []
        self.has_modified_version = has_modified_version


class DummyData:
    """模拟 UserData — 用普通 dict 属性"""
    def __init__(self):
        self.partitions = {}
        self.domains = {}
        self.topics = {}
        self.conversations = {}
        self.nodes = {}
        self.active_partition_id = ""


@pytest.fixture
def mocked_tree_ops():
    """创建 TreeOpsService 并将 _storage 和 cognitive sync 替换为 mock"""
    with patch("app.services.knowledge.tree_ops.storage") as mock_stg, \
         patch("app.services.knowledge.tree_sync.upsert_node") as mock_upsert, \
         patch("app.services.knowledge.tree_sync.cog_delete_node") as mock_del, \
         patch("app.cognitive.storage.get_node", return_value=None):
        from app.services.knowledge.tree_ops import TreeOpsService
        svc = TreeOpsService()
        data = DummyData()
        mock_stg.load.return_value = data
        mock_stg.save.return_value = None
        yield svc, data, mock_stg


class TestTreeHierarchy:
    """分区/领域/专题/对话 CRUD"""

    def test_create_partition(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "高等数学")
        assert p.id in data.partitions
        assert data.partitions[p.id].name == "高等数学"

    def test_create_partition_auto_creates_child(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        # auto_create_child: domain
        domain = next(iter(data.domains.values()), None)
        assert domain is not None, "auto_create_child 应自动创建 domain"
        assert domain.partition_id == p.id

    def test_create_and_get_domain(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = svc.create_domain("u1", p.id, "微积分")
        assert d.id in data.domains
        assert data.domains[d.id].name == "微积分"

    def test_create_topic(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = svc.create_domain("u1", p.id, "微积分")
        t = svc.create_topic("u1", d.id, "导数")
        assert t.id in data.topics

    def test_create_conversation(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id, "新对话")
        assert c.id in data.conversations

    def test_delete_partition(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        svc.delete_partition("u1", p.id)
        assert p.id not in data.partitions


class TestTreeMessages:
    """消息 CRUD"""

    def test_add_message(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        # 使用自动创建的 active conversation
        c = data.conversations.get(t.active_conversation_id)
        assert c is not None, "create_partition 应自动创建 conversation"
        node = svc.add_message("u1", p.id, "user",
                               [{"type": "text", "text": "hello"}],
                               text_summary="hello")
        assert node.id in data.nodes
        assert len(c.path) > 0

    def test_update_message(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        node = svc.add_message("u1", p.id, "user",
                               [{"type": "text", "text": "hello"}],
                               text_summary="hello")
        svc.update_message_content("u1", node.id, "updated")
        assert data.nodes[node.id].text_summary == "updated"

    def test_modify_message_creates_new_version(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        node = svc.add_message("u1", p.id, "user",
                               [{"type": "text", "text": "v1"}])
        new_node = svc.modify_message("u1", node.id,
                                      [{"type": "text", "text": "v2"}])
        assert new_node.id != node.id
        assert new_node.id in data.nodes

    def test_delete_message(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        node = svc.add_message("u1", p.id, "user",
                               [{"type": "text", "text": "hello"}])
        svc.delete_message("u1", node.id)
        assert data.nodes[node.id].is_deleted is True


class TestTreeContext:
    """上下文查询 / 切换"""

    def test_get_partition_context(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        ctx = svc.get_partition_context("u1", p.id)
        assert ctx["partition"] is not None
        assert "messages" in ctx

    def test_switch_conversation(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c1 = svc.create_conversation("u1", t.id, "C1")
        c2 = svc.create_conversation("u1", t.id, "C2")
        # 默认第一个是 active，切换到第二个
        switched = svc.switch_conversation("u1", c2.id, p.id)
        assert switched.id == c2.id
        assert c2.is_active is True
        assert c1.is_active is False


class TestTreeSubBranch:
    """子支操作"""

    def test_create_sub_branch(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        msg = svc.add_message("u1", p.id, "user",
                              [{"type": "text", "text": "test message"}],
                              text_summary="test message")
        branch, ref = svc.create_sub_branch("u1", c.id, msg.id, 0, 4, "test")
        assert branch.id in data.conversations
        assert branch.parent_conversation_id == c.id

    def test_get_sub_branches(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        msg = svc.add_message("u1", p.id, "user",
                              [{"type": "text", "text": "test"}],
                              text_summary="test")
        svc.create_sub_branch("u1", c.id, msg.id, 0, 4, "test")
        branches = svc.get_sub_branches("u1", msg.id)
        assert len(branches) == 1

    def test_delete_sub_branch(self, mocked_tree_ops):
        svc, data, _ = mocked_tree_ops
        p = svc.create_partition("u1", "数学")
        d = next(d for d in data.domains.values() if d.partition_id == p.id)
        t = next(t for t in data.topics.values() if t.domain_id == d.id)
        c = svc.create_conversation("u1", t.id)
        msg = svc.add_message("u1", p.id, "user",
                              [{"type": "text", "text": "test"}],
                              text_summary="test")
        branch, _ = svc.create_sub_branch("u1", c.id, msg.id, 0, 4, "test")
        result = svc.delete_sub_branch("u1", branch.id)
        assert result["ok"] is True

    def test_sub_branch_on_temporary_conversation_fails(self, mocked_tree_ops):
        """临时对话不能创建子支"""
        svc, data, _ = mocked_tree_ops
        # 使用 _ensure_temp_partition 创建临时分区
        temp_p, temp_d = svc._ensure_temp_partition("u1", data)
        t = svc.create_topic("u1", temp_d.id, "临时专题")
        c = svc.create_conversation("u1", t.id, "临时对话")
        c.is_temporary = True
        msg = svc.add_message("u1", temp_p.id, "user",
                              [{"type": "text", "text": "test"}],
                              text_summary="test")
        with pytest.raises(ValueError, match="临时会话不支持"):
            svc.create_sub_branch("u1", c.id, msg.id, 0, 4, "test")
