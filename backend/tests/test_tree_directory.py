"""测试 TreeDirectoryMixin — DirectoryNode CRUD 操作。

使用内存版 FakeDataRepository 注入，mock CognitiveNodeWriter 避免真实 DB。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch
import pytest
from typing import Any

from app.services.common import set_data_repo
from app.schemas.conversation import UserData
from app.schemas.directory_node import DirectoryNode


# ═══════════════════════════════════════════════
# FakeDataRepository — 内存版实现
# ═══════════════════════════════════════════════

class FakeDataRepository:
    """内存版 DataRepository，不依赖任何外部存储。"""

    def __init__(self) -> None:
        self._store: dict[str, UserData] = {}

    def load(self, user_id: str) -> UserData:
        data = self._store.get(user_id)
        if data is None:
            data = UserData(user_id=user_id)
            self._store[user_id] = data
        return data

    def save(self, user_id: str, data: UserData) -> None:
        self._store[user_id] = data

    def get_etag(self, user_id: str) -> str:
        return f'W/"test-{user_id}"'


# ═══════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════

@pytest.fixture
def fake_repo():
    """返回一个干净的 FakeDataRepository 实例。"""
    return FakeDataRepository()


@pytest.fixture
def tree_mixin(fake_repo):
    """创建 TreeDirectoryMixin 实例，注入 fake_repo 并 mock CognitiveNodeWriter。

    Yields:
        (mixin, fake_repo) 元组，每测试独立
    """
    set_data_repo(fake_repo)
    with patch("app.domain.cognitive.writer.CognitiveNodeWriter.create_node") as mock_create:
        mock_create.return_value = None
        from app.services.knowledge.tree_directory import TreeDirectoryMixin
        mixin = TreeDirectoryMixin()
        yield mixin, fake_repo


# ═══════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════

class TestTreeDirectoryMixin:
    """DirectoryNode CRUD 操作测试"""

    # ── _ensure_root ──

    def test_ensure_root_creates_when_missing(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        assert len(data.directory_nodes) == 0

        root = mixin._ensure_root(user_id, data)
        assert root is not None
        assert root.node_type == "dir"
        assert root.parent_id is None
        assert root.name == mixin.ROOT_NAME
        assert root.id in data.directory_nodes

    def test_ensure_root_returns_existing(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root1 = mixin._ensure_root(user_id, data)
        root2 = mixin._ensure_root(user_id, data)
        assert root1.id == root2.id
        assert len(data.directory_nodes) == 1

    # ── _ensure_temp_dir ──

    def test_ensure_temp_dir_creates_under_root(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)

        temp = mixin._ensure_temp_dir(user_id, data)
        assert temp.node_type == "dir"
        assert temp.kind == "temp"
        assert temp.name == "💬 临时"
        # 应自动创建 root
        root = mixin._find_root(data)
        assert root is not None
        assert temp.parent_id == root.id
        assert temp.id in root.children_order

    def test_ensure_temp_dir_idempotent(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        t1 = mixin._ensure_temp_dir(user_id, data)
        t2 = mixin._ensure_temp_dir(user_id, data)
        assert t1.id == t2.id

    # ── create_dir ──

    def test_create_dir(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        child = mixin.create_dir(user_id, root.id, "数学")
        assert child.node_type == "dir"
        assert child.kind == "general"
        assert child.name == "数学"
        assert child.parent_id == root.id
        assert child.id in data.directory_nodes
        assert child.id in root.children_order

    def test_create_dir_raises_for_missing_parent(self, tree_mixin):
        mixin, _ = tree_mixin
        with pytest.raises(ValueError, match="父目录"):
            mixin.create_dir("u1", "nonexistent", "孤儿")

    # ── create_conv ──

    def test_create_conv_with_default_name(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        conv = mixin.create_conv(user_id, root.id)
        assert conv.node_type == "conv"
        assert conv.kind == "general"
        assert conv.name == "新对话"
        assert conv.parent_id == root.id
        assert conv.id in data.directory_nodes
        assert conv.id in root.children_order
        # 应有根消息
        assert len(conv.conv_message_ids) == 1
        msg_id = conv.conv_message_ids[0]
        assert msg_id in data.nodes

    def test_create_conv_with_custom_name(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        conv = mixin.create_conv(user_id, root.id, "我的对话", "general")
        assert conv.name == "我的对话"

    def test_create_conv_raises_for_missing_parent(self, tree_mixin):
        mixin, _ = tree_mixin
        with pytest.raises(ValueError, match="父目录"):
            mixin.create_conv("u1", "nonexistent", "孤儿")

    # ── delete_node ──

    def test_delete_leaf_node(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        child = mixin.create_dir(user_id, root.id, "子目录")

        mixin.delete_node(user_id, child.id)
        assert child.id not in data.directory_nodes
        assert child.id not in root.children_order

    def test_delete_recursive(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        # 创建层级: root -> dir1 -> conv1
        dir1 = mixin.create_dir(user_id, root.id, "D1")
        conv1 = mixin.create_conv(user_id, dir1.id, "C1")

        mixin.delete_node(user_id, dir1.id)
        assert dir1.id not in data.directory_nodes
        assert conv1.id not in data.directory_nodes
        # conv 下的消息也应删除
        for mid in conv1.conv_message_ids:
            assert mid not in data.nodes

    def test_delete_nonexistent_node(self, tree_mixin):
        mixin, _ = tree_mixin
        # 不存在的节点应静默返回
        mixin.delete_node("u1", "ghost")

    # ── rename_node ──

    def test_rename_node(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        child = mixin.create_dir(user_id, root.id, "旧名")

        renamed = mixin.rename_node(user_id, child.id, "新名")
        assert renamed.user_name == "新名"
        assert renamed.display_name == "新名"
        # 验证从 repo 读取也一致
        data2 = repo.load(user_id)
        assert data2.directory_nodes[child.id].user_name == "新名"

    def test_rename_nonexistent_node_raises(self, tree_mixin):
        mixin, _ = tree_mixin
        with pytest.raises(ValueError, match="不存在"):
            mixin.rename_node("u1", "ghost", "新名")

    def test_rename_temp_node_raises(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        temp = mixin._ensure_temp_dir(user_id, data)
        with pytest.raises(ValueError, match="临时节点不可重命名"):
            mixin.rename_node(user_id, temp.id, "新名")

    # ── list_children ──

    def test_list_children_ordered(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        c1 = mixin.create_dir(user_id, root.id, "B")
        c2 = mixin.create_dir(user_id, root.id, "A")
        children = mixin.list_children(user_id, root.id)
        # 按 children_order 排序: c1 先创建, c2 后创建
        assert len(children) == 2
        assert [n.id for n in children] == [c1.id, c2.id]

    def test_list_children_empty(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        children = mixin.list_children(user_id, root.id)
        assert children == []

    def test_list_children_missing_parent(self, tree_mixin):
        mixin, _ = tree_mixin
        children = mixin.list_children("u1", "nonexistent")
        assert children == []

    # ── find_conv ──

    def test_find_conv_found(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        conv = mixin.create_conv(user_id, root.id, "对话1")

        found = mixin.find_conv(data, conv.id)
        assert found is not None
        assert found.id == conv.id

    def test_find_conv_dir_not_found(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        # dir 节点不应被 find_conv 返回
        found = mixin.find_conv(data, root.id)
        assert found is None

    def test_find_conv_nonexistent(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        found = mixin.find_conv(data, "nonexistent")
        assert found is None

    # ── migrate_conv ──

    def test_migrate_conv(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)

        # 创建两个目录, 一个对话在第一个目录下
        dir1 = mixin.create_dir(user_id, root.id, "源目录")
        dir2 = mixin.create_dir(user_id, root.id, "目标目录")
        conv = mixin.create_conv(user_id, dir1.id, "可迁移对话")

        # 迁移
        migrated = mixin.migrate_conv(user_id, conv.id, dir2.id)
        assert migrated.parent_id == dir2.id
        assert conv.id in dir2.children_order
        assert conv.id not in dir1.children_order
        assert migrated.kind == "general"

    def test_migrate_conv_nonexistent_raises(self, tree_mixin):
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        with pytest.raises(ValueError, match="不存在"):
            mixin.migrate_conv(user_id, "ghost", root.id)

    def test_migrate_conv_to_dir_node(self, tree_mixin):
        """迁移 conv 到一个 dir 节点。"""
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        dir1 = mixin.create_dir(user_id, root.id, "D1")
        conv = mixin.create_conv(user_id, dir1.id, "C1")

        # create_dir 创建另一个 dir
        dir2 = mixin.create_dir(user_id, root.id, "D2")
        migrated = mixin.migrate_conv(user_id, conv.id, dir2.id)
        assert migrated.parent_id == dir2.id

    def test_migrate_conv_to_conv_raises(self, tree_mixin):
        """迁移对话到一个 conv 节点（非 dir）应报错。"""
        mixin, repo = tree_mixin
        user_id = "u1"
        data = repo.load(user_id)
        root = mixin._ensure_root(user_id, data)
        dir1 = mixin.create_dir(user_id, root.id, "D1")
        conv1 = mixin.create_conv(user_id, dir1.id, "C1")
        conv2 = mixin.create_conv(user_id, dir1.id, "C2")
        with pytest.raises(ValueError, match="目标目录"):
            mixin.migrate_conv(user_id, conv1.id, conv2.id)
