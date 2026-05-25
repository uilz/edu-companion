"""内置模块: 横向扩展提案 (LateralExpansion)

功能: 监测父节点下可见子节点活动 ≥ 3 次且未扩展过，生成扩展提案
行为: 提案接受后 LLM 生成 suggested 节点，直接 is_visible=true
"""
from __future__ import annotations

import logging
from typing import Any

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class LateralExpansionModule(SecretaryModule):
    """横向扩展提案模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="lateral_expansion",
            display_name="知识结构扩展",
            emoji="🌱",
            description="检测知识树可扩展方向，建议新增专题",
            default_enabled=True,
            run_interval_seconds=600,  # 每 10 分钟
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """扫描所有父节点，检测可扩展方向"""
        from app.cognitive.growth_engine import growth_engine
        from app.cognitive.storage import get_nodes_by_level

        proposals: list[Proposal] = []

        # 扫描所有 partition、domain 级节点
        for level in ("partition", "domain", "topic"):
            parents = get_nodes_by_level(level, user_id)
            for parent in parents:
                try:
                    suggestions = growth_engine.suggest_lateral_expansion(
                        user_id, parent.id,
                    )
                    for s in suggestions:
                        proposals.append(Proposal(
                            emoji="🌿",
                            title=f"扩展「{s['parent_label']}」的知识结构",
                            description=(
                                f"该分类下已有 {s['visible_count']} 个活跃子专题。"
                                "需要自动生成更多分支方向吗？"
                            ),
                            action_type="lateral_expansion",
                            priority=2,
                            payload={
                                "parent_id": s["parent_id"],
                                "parent_label": s["parent_label"],
                                "visible_count": s["visible_count"],
                            },
                            insight_source="lateral_expansion",
                        ))
                except Exception as e:
                    logger.debug("横向扩展扫描异常[%s/%s]: %s", level, parent.id, e)

        return proposals
