"""
CognitiveNodeWriter — 统一认知节点写入封装

将 partition/domain/topic/concept/atom 等所有层级的创建统一经过此写入器。
职责：
  1. 重复检测（同一 parent 下同名节点不重复创建）
  2. path_id 自动生成（基于父节点 path + label）
  3. 可见性设置（用户显式创建的设为 true，系统生成的设 false）
  4. 写入 cognitive_nodes 表（唯一持久化点）
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from app.cognitive import get_repo
from app.cognitive.models import CognitiveNode, MetaInfo

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"


class CognitiveNodeWriter:
    """统一认知节点写入器"""

    def __init__(self, user_id: str = DEFAULT_USER_ID):
        self.user_id = user_id

    # ── 公共接口 ──

    def create_node(
        self,
        label: str,
        level: str,
        parent_id: Optional[str] = None,
        *,
        node_type: str = "explicit",
        created_by: str = "user",
        is_visible: bool = True,
        emoji: str = "",
        description: str = "",
        metadata: Optional[dict] = None,
    ) -> CognitiveNode:
        """创建知识节点（幂等：同一 parent + level + label 只创建一次）

        Args:
            label: 节点标签
            level: partition/domain/topic/concept/atom
            parent_id: 父节点 ID（partition 级别可为空）
            node_type: explicit/auto_generated/suggested/migrated
            created_by: user/system/secretary/classifier
            is_visible: 是否在侧边栏可见
            emoji: 图标前缀（如 "📐"）
            description: 描述
            metadata: 扩展元数据

        Returns:
            创建或已存在的 CognitiveNode
        """
        # 1. 重复检测
        existing = self._find_existing(label, level, parent_id)
        if existing:
            logger.debug("节点已存在，跳过创建: %s (%s)", label, level)
            return existing

        # 2. 生成 path_id
        path_id = self._generate_path_id(label, parent_id)

        # 3. 构建完整标签
        full_label = (emoji + " " + label) if emoji else label

        now = time.time()

        # 4. 构建节点
        node = CognitiveNode(
            id=path_id,
            label=full_label,
            level=level,
            parent=parent_id or None,
            children=[],
            is_visible=is_visible,
            node_type=node_type,
            meta=MetaInfo(created_at=now, updated_at=now),
        )

        # 5. 持久化（upsert_node 会将 pydantic model 转为 DB 行）
        get_repo().upsert_node(node, self.user_id)

        # 6. 额外字段通过 raw SQL 写入（pydantic model 未声明但 DB 有列）
        self._write_extra_fields(node.id, created_by, description, metadata)

        # 7. 维护父节点 children 列表
        if parent_id:
            self._add_to_parent_children(node.id, parent_id)

        logger.info(
            "✅ CognitiveNodeWriter 创建: %s (%s, parent=%s)",
            label, level, parent_id or "root",
        )

        return node

    def ensure_partition(
        self, label: str, emoji: str = "", description: str = ""
    ) -> CognitiveNode:
        """确保分区存在"""
        return self.create_node(label=label, level="partition", emoji=emoji, description=description)

    def ensure_domain(
        self, label: str, parent_id: str, emoji: str = "", description: str = ""
    ) -> CognitiveNode:
        """确保领域存在"""
        return self.create_node(label=label, level="domain", parent_id=parent_id, emoji=emoji, description=description)

    def ensure_topic(
        self, label: str, parent_id: str, emoji: str = "", description: str = ""
    ) -> CognitiveNode:
        """确保专题存在"""
        return self.create_node(label=label, level="topic", parent_id=parent_id, emoji=emoji, description=description)

    # ── 内部方法 ──

    def _find_existing(
        self, label: str, level: str, parent_id: Optional[str]
    ) -> Optional[CognitiveNode]:
        """同一 parent 下按 label 精确查找已存在且未删除的节点"""
        children = get_repo().get_children(parent_id or "", self.user_id)
        clean_label = label.strip()
        for c in children:
            # get_children 已过滤 deleted_at IS NULL，无需再检查
            c_label = c.label.split(" ", 1)[-1] if " " in c.label else c.label
            if c_label == clean_label and c.level == level:
                return c
        return None

    @staticmethod
    def _generate_path_id(label: str, parent_id: Optional[str]) -> str:
        """生成语义路径 ID"""
        slug = label.lower().replace(" ", "_")
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        if not slug:
            slug = "node"
        if parent_id:
            return f"{parent_id}/{slug}"
        return slug

    def _write_extra_fields(
        self, node_id: str, created_by: str, description: str, metadata: Optional[dict]
    ) -> None:
        """写入 pydantic model 未声明的额外 DB 字段"""
        import json as _json
        meta_str = _json.dumps(metadata) if metadata else ""
        get_repo().update_extra_fields(node_id, self.user_id, created_by, description, meta_str)

    def _add_to_parent_children(self, node_id: str, parent_id: str) -> None:
        """将 node_id 追加到父节点 children 列表（去重）"""
        get_repo().add_to_parent_children(node_id, parent_id, self.user_id)
