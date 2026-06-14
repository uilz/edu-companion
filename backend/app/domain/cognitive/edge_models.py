"""KnowledgeEdge — 知识图谱边模型

Phase 8 动态关系建模。
层级关系由 parent_id + path_id 推导，不在本表中存储。
"""
from __future__ import annotations

import time
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeEdge(BaseModel):
    """知识图谱边，描述两个 CognitiveNode 之间的关系"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str = "related_to"  # prerequisite | analogy | related_to | user_defined
    strength: float = 0.5
    confidence: float | None = None
    trust_score: float = 0.5
    edge_status: str = "suggested"
        # auto_active | pending_confirm | suggested | user_rejected
    created_by: str = "system"
    created_at: float = Field(default_factory=time.time)
    last_evaluated_at: float = Field(default_factory=time.time)

    def get_current_trust(self) -> float:
        """惰性衰减计算：读时计算信任度衰减"""
        import math
        now = time.time()
        days = (now - self.last_evaluated_at) / 86400.0
        if days > 0:
            decay = math.exp(-0.015 * days)
            new_score = self.trust_score * decay
            # 如果变化超过阈值才写库（由调用方负责）
            return max(0.0, min(1.0, new_score))
        return self.trust_score
