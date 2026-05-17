"""
树形对话操作服务
提供分区、分支、消息节点的创建、修改、删除、切换等操作
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.schemas.conversation import (
    Branch,
    ContentBlock,
    Partition,
    TreeNode,
    UserData,
)
from app.services.storage import storage


class TreeOpsService:
    """所有树形结构操作"""

    def create_partition(
        self,
        user_id: str,
        name: str,
        subject: str = "",
        direction: str = "subject",
        emoji: str = "💬",
    ) -> Partition:
        """创建新分区，附带虚拟根节点"""
        data = storage.load(user_id)

        # 创建虚拟根节点
        root_id = str(uuid4())
        root_node = TreeNode(
            id=root_id,
            parent_id=root_id,  # 自引用，表示虚拟根
            partition_id="",  # 会在创建 partition 后设置
            branch_id="",
            role="assistant",  # 虚拟节点，角色不重要
            content_blocks=[],
            text_summary="[virtual_root]",
        )

        # 创建分区
        partition = Partition(
            name=name,
            subject=subject,
            direction=direction,
            emoji=emoji,
            root_id=root_id,
        )
        root_node.partition_id = partition.id

        # 创建第一个分支
        branch = Branch(partition_id=partition.id, name=name)
        partition.active_branch_id = branch.id

        # 存储
        data.nodes[root_id] = root_node
        data.partitions[partition.id] = partition
        data.branches[branch.id] = branch
        data.active_partition_id = partition.id

        storage.save(user_id, data)
        return partition

    def add_message(
        self,
        user_id: str,
        partition_id: str,
        role: str,
        content_blocks: list[ContentBlock],
        text_summary: str = "",
    ) -> TreeNode:
        """向当前活跃分支添加消息"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        branch = data.branches.get(partition.active_branch_id)
        if not branch:
            raise ValueError(f"Active branch {partition.active_branch_id} not found")

        # 创建节点
        node = TreeNode(
            parent_id=branch.path[-1] if branch.path else partition.root_id,
            partition_id=partition_id,
            branch_id=branch.id,
            role=role,
            content_blocks=content_blocks,
            text_summary=text_summary,
        )

        # 更新父节点的 children
        parent = data.nodes.get(node.parent_id)
        if parent:
            parent.children_ids.append(node.id)

        # 更新分支路径
        branch.path.append(node.id)
        branch.last_message_at = time.time()

        # 更新分区统计
        partition.message_count += 1
        partition.updated_at = time.time()
        partition.last_active_at = time.time()

        # 存储
        data.nodes[node.id] = node
        storage.save(user_id, data)
        return node

    def create_branch(
        self,
        user_id: str,
        partition_id: str,
        fork_point_id: str | None = None,
        name: str = "",
    ) -> Branch:
        """创建新分支，可选从指定消息分叉"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        # 停用当前活跃分支
        for b in data.branches.values():
            if b.partition_id == partition_id and b.is_active:
                b.is_active = False

        # 构建新分支的路径
        path: list[str] = []
        if fork_point_id:
            # 从分叉点构建路径: [parent_path..., fork_point_id]
            fork_node = data.nodes.get(fork_point_id)
            if fork_node:
                # 从根到分叉点重建路径
                current = fork_point_id
                while current and current != partition.root_id:
                    path.append(current)
                    node = data.nodes.get(current)
                    if node:
                        current = node.parent_id
                    else:
                        break
                path.reverse()

        branch = Branch(
            partition_id=partition_id,
            name=name or f"分支-{str(uuid4())[:6]}",
            fork_point_id=fork_point_id,
            path=path,
            is_active=True,
        )

        partition.active_branch_id = branch.id
        data.branches[branch.id] = branch
        storage.save(user_id, data)
        return branch

    def modify_message(
        self,
        user_id: str,
        message_id: str,
        new_content_blocks: list[ContentBlock],
        new_text_summary: str = "",
    ) -> TreeNode:
        """修改消息（创建新节点并分叉新分支）"""
        data = storage.load(user_id)
        node = data.nodes.get(message_id)
        if not node:
            raise ValueError(f"Message {message_id} not found")

        # 标记原消息有修改版本
        node.has_modified_version = True

        # 创建新节点（同父节点）
        new_node = TreeNode(
            parent_id=node.parent_id,
            partition_id=node.partition_id,
            branch_id="",  # 会被 create_branch 设置
            role=node.role,
            content_blocks=new_content_blocks,
            text_summary=new_text_summary,
        )

        # 为修改版本创建新分支
        branch = self.create_branch(user_id, node.partition_id, fork_point_id=node.parent_id)
        new_node.branch_id = branch.id

        # 添加到父节点的 children
        parent = data.nodes.get(node.parent_id)
        if parent:
            parent.children_ids.append(new_node.id)

        # 存储
        data.nodes[new_node.id] = new_node
        storage.save(user_id, data)
        return new_node

    def delete_message(self, user_id: str, message_id: str) -> None:
        """软删除消息及其子树"""
        data = storage.load(user_id)

        def delete_subtree(nid: str) -> None:
            node = data.nodes.get(nid)
            if not node:
                return
            node.is_deleted = True
            # 将子节点重新挂到被删除节点的父节点
            parent = data.nodes.get(node.parent_id)
            if parent and nid in parent.children_ids:
                parent.children_ids.remove(nid)
                for child_id in node.children_ids:
                    if child_id not in parent.children_ids:
                        parent.children_ids.append(child_id)
                    child = data.nodes.get(child_id)
                    if child:
                        child.parent_id = parent.id
            # 递归删除
            for child_id in node.children_ids[:]:
                delete_subtree(child_id)

        delete_subtree(message_id)

        # 标记分支摘要需更新
        node = data.nodes.get(message_id)
        if node:
            branch = data.branches.get(node.branch_id)
            if branch:
                branch.summary_dirty = True
                # 重建路径，排除已删除节点
                branch.path = [
                    nid
                    for nid in branch.path
                    if not data.nodes.get(
                        nid,
                        TreeNode(
                            parent_id="",
                            branch_id="",
                            partition_id="",
                            role="user",
                        ),
                    ).is_deleted
                ]

        storage.save(user_id, data)

    def switch_branch(
        self, user_id: str, partition_id: str, branch_id: str
    ) -> Branch:
        """切换分区的活跃分支"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        # 停用该分区所有分支
        for b in data.branches.values():
            if b.partition_id == partition_id:
                b.is_active = False

        # 激活目标分支
        branch = data.branches.get(branch_id)
        if not branch or branch.partition_id != partition_id:
            raise ValueError(
                f"Branch {branch_id} not found in partition {partition_id}"
            )

        branch.is_active = True
        partition.active_branch_id = branch_id

        storage.save(user_id, data)
        return branch

    def get_partition_context(self, user_id: str, partition_id: str) -> dict:
        """获取分区完整上下文（用于 LLM 调用）"""
        data = storage.load(user_id)
        partition = data.partitions.get(partition_id)
        if not partition:
            raise ValueError(f"Partition {partition_id} not found")

        # 获取活跃分支的消息
        branch = data.branches.get(partition.active_branch_id)
        messages: list[TreeNode] = []
        if branch:
            for nid in branch.path:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    messages.append(node)

        return {
            "partition": partition,
            "branch": branch,
            "messages": messages,
            "context_summary": partition.context_summary,
        }


# 全局单例
tree_ops = TreeOpsService()
