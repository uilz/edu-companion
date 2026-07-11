"""
Knowledge Tree 服务层单元测试

覆盖：
- KnowledgeTreeService CRUD
- TreeNodeService CRUD + move + reorder + delete
- TreeEdgeService CRUD
- CognitiveLinkService CRUD
- 事件发布
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.application.di import get_event_bus
from app.infrastructure.db.database import get_db
from app.services.knowledge_tree import kt_svc, tn_svc, te_svc, cl_svc


@pytest.fixture
def user_id():
    return f"kt_test_user_{int(time.time() * 1000)}"


@pytest.fixture
def tree(user_id):
    t = kt_svc.create_tree(user_id, title="测试树", tree_type="project")
    yield t
    # cleanup handled by cascading delete below


def cleanup_user(user_id: str) -> None:
    db = get_db()
    db.execute("DELETE FROM tree_node_cognitive_links WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM tree_edges WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM tree_nodes WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM knowledge_trees WHERE user_id = %s", (user_id,))


class TestKnowledgeTreeService:
    def test_create_and_get_tree(self, user_id):
        tree = kt_svc.create_tree(user_id, title="单元测试树", description="desc")
        assert tree.title == "单元测试树"
        assert tree.tree_type == "project"
        assert tree.default_view_mode == "tree"

        fetched = kt_svc.get_tree(user_id, tree.id)
        assert fetched is not None
        assert fetched.id == tree.id
        assert fetched.description == "desc"
        cleanup_user(user_id)

    def test_list_trees(self, user_id):
        t1 = kt_svc.create_tree(user_id, title="树1")
        t2 = kt_svc.create_tree(user_id, title="树2")
        trees = kt_svc.list_trees(user_id)
        ids = {t.id for t in trees}
        assert t1.id in ids
        assert t2.id in ids
        cleanup_user(user_id)

    def test_update_tree(self, user_id):
        tree = kt_svc.create_tree(user_id, title="旧标题")
        updated = kt_svc.update_tree(user_id, tree.id, title="新标题", default_layout="force")
        assert updated.title == "新标题"
        assert updated.default_layout == "force"
        cleanup_user(user_id)

    def test_delete_tree(self, user_id):
        tree = kt_svc.create_tree(user_id, title="待删除")
        assert kt_svc.delete_tree(user_id, tree.id) is True
        assert kt_svc.get_tree(user_id, tree.id) is None
        cleanup_user(user_id)


class TestTreeNodeService:
    def test_create_node(self, user_id, tree):
        node = tn_svc.create_node(user_id, tree.id, "根节点", node_type="topic")
        assert node.tree_id == tree.id
        assert node.label == "根节点"
        assert node.node_type == "topic"
        assert node.parent_id is None
        cleanup_user(user_id)

    def test_create_child_node_updates_parent_children_order(self, user_id, tree):
        root = tn_svc.create_node(user_id, tree.id, "根")
        child = tn_svc.create_node(user_id, tree.id, "子", parent_id=root.id)
        root_after = tn_svc.get_node(user_id, root.id)
        assert child.id in root_after.children_order
        cleanup_user(user_id)

    def test_update_node(self, user_id, tree):
        node = tn_svc.create_node(user_id, tree.id, "旧标签")
        updated = tn_svc.update_node(user_id, node.id, label="新标签", color="#ff0000")
        assert updated.label == "新标签"
        assert updated.color == "#ff0000"
        cleanup_user(user_id)

    def test_move_node(self, user_id, tree):
        root = tn_svc.create_node(user_id, tree.id, "根")
        child1 = tn_svc.create_node(user_id, tree.id, "子1", parent_id=root.id)
        child2 = tn_svc.create_node(user_id, tree.id, "子2")

        moved = tn_svc.move_node(user_id, child2.id, new_parent_id=root.id)
        assert moved.parent_id == root.id
        root_after = tn_svc.get_node(user_id, root.id)
        assert child1.id in root_after.children_order
        assert child2.id in root_after.children_order
        cleanup_user(user_id)

    def test_reorder_children(self, user_id, tree):
        root = tn_svc.create_node(user_id, tree.id, "根")
        c1 = tn_svc.create_node(user_id, tree.id, "c1", parent_id=root.id)
        c2 = tn_svc.create_node(user_id, tree.id, "c2", parent_id=root.id)

        ok = tn_svc.reorder_children(user_id, root.id, [c2.id, c1.id])
        assert ok is True
        root_after = tn_svc.get_node(user_id, root.id)
        assert root_after.children_order == [c2.id, c1.id]
        cleanup_user(user_id)

    def test_delete_node(self, user_id, tree):
        root = tn_svc.create_node(user_id, tree.id, "根")
        child = tn_svc.create_node(user_id, tree.id, "子", parent_id=root.id)

        assert tn_svc.delete_node(user_id, child.id) is True
        assert tn_svc.get_node(user_id, child.id) is None
        root_after = tn_svc.get_node(user_id, root.id)
        assert child.id not in root_after.children_order
        cleanup_user(user_id)


class TestTreeEdgeService:
    def test_create_and_get_edge(self, user_id, tree):
        n1 = tn_svc.create_node(user_id, tree.id, "n1")
        n2 = tn_svc.create_node(user_id, tree.id, "n2")
        edge = te_svc.create_edge(user_id, tree.id, n1.id, n2.id, edge_type="related", strength=0.7)
        assert edge is not None
        assert edge.edge_type == "related"
        assert edge.strength == pytest.approx(0.7)

        fetched = te_svc.get_edge(user_id, edge.id)
        assert fetched.id == edge.id
        cleanup_user(user_id)

    def test_list_edges(self, user_id, tree):
        n1 = tn_svc.create_node(user_id, tree.id, "n1")
        n2 = tn_svc.create_node(user_id, tree.id, "n2")
        te_svc.create_edge(user_id, tree.id, n1.id, n2.id)

        edges = te_svc.list_edges(user_id, tree.id)
        assert len(edges) == 1
        assert edges[0].source_node_id == n1.id
        cleanup_user(user_id)

    def test_delete_edge(self, user_id, tree):
        n1 = tn_svc.create_node(user_id, tree.id, "n1")
        n2 = tn_svc.create_node(user_id, tree.id, "n2")
        edge = te_svc.create_edge(user_id, tree.id, n1.id, n2.id)

        assert te_svc.delete_edge(user_id, edge.id) is True
        assert te_svc.get_edge(user_id, edge.id) is None
        cleanup_user(user_id)


class TestCognitiveLinkService:
    def test_create_and_list_links(self, user_id, tree):
        node = tn_svc.create_node(user_id, tree.id, "节点")
        link = cl_svc.create_link(user_id, tree.id, node.id, "kn_demo_1", link_role="primary")
        assert link is not None
        assert link.cognitive_node_id == "kn_demo_1"

        links = cl_svc.list_links_by_tree_node(user_id, node.id)
        assert len(links) == 1
        cleanup_user(user_id)

    def test_delete_link(self, user_id, tree):
        node = tn_svc.create_node(user_id, tree.id, "节点")
        link = cl_svc.create_link(user_id, tree.id, node.id, "kn_demo_2")

        assert cl_svc.delete_link(user_id, link.id) is True
        assert cl_svc.list_links_by_tree_node(user_id, node.id) == []
        cleanup_user(user_id)


class TestKnowledgeTreeEvents:
    def test_create_node_emits_tree_node_created(self, user_id, tree):
        bus = get_event_bus()
        captured = []

        async def handler(event):
            captured.append(event)

        bus.subscribe("TreeNodeCreated", handler)
        try:
            node = tn_svc.create_node(user_id, tree.id, "事件节点")
            time.sleep(0.2)
            assert len(captured) >= 1
            assert captured[-1].event_type == "TreeNodeCreated"
            assert captured[-1].node_id == node.id
            assert captured[-1].tree_id == tree.id
        finally:
            bus.unsubscribe("TreeNodeCreated", handler)
            cleanup_user(user_id)

    def test_create_edge_emits_tree_edge_created(self, user_id, tree):
        bus = get_event_bus()
        captured = []

        async def handler(event):
            captured.append(event)

        bus.subscribe("TreeEdgeCreated", handler)
        try:
            n1 = tn_svc.create_node(user_id, tree.id, "n1")
            n2 = tn_svc.create_node(user_id, tree.id, "n2")
            edge = te_svc.create_edge(user_id, tree.id, n1.id, n2.id)
            time.sleep(0.2)
            assert any(e.event_type == "TreeEdgeCreated" and e.edge_id == edge.id for e in captured)
        finally:
            bus.unsubscribe("TreeEdgeCreated", handler)
            cleanup_user(user_id)

    def test_create_link_emits_tree_node_linked(self, user_id, tree):
        bus = get_event_bus()
        captured = []

        async def handler(event):
            captured.append(event)

        bus.subscribe("TreeNodeLinkedToCognitiveNode", handler)
        try:
            node = tn_svc.create_node(user_id, tree.id, "link_node")
            link = cl_svc.create_link(user_id, tree.id, node.id, "kn_event_1")
            time.sleep(0.2)
            assert any(
                e.event_type == "TreeNodeLinkedToCognitiveNode"
                and e.tree_node_id == node.id
                and e.cognitive_node_id == "kn_event_1"
                for e in captured
            )
        finally:
            bus.unsubscribe("TreeNodeLinkedToCognitiveNode", handler)
            cleanup_user(user_id)
