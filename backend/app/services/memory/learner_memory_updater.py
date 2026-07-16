"""LI-03 Learner Memory — 长期记忆更新服务。

职责:
  把一次观察（learner_delta + reflection），变成长期理解。

具体:
  1. 将 learner_delta.knowledge_updates 应用到 BKT CognitiveNodes
  2. 创建 GrowthRecord（含 reflection + understanding summary）
  3. 更新 LearnerProfile 推理模式（reasoning_insights）

不做:
  - 不分析 Mission（LI-01）
  - 不观察理解（LI-02）
  - 不预测未来
  - 不生成推荐
  - 不做内容筛选

原则:
  P3 — 学习者驱动（Reflection 跳过了也要创建，标注 incomplete）
  P4 — 隔离能力（只写 knowledge/growth/profile，不碰其他命名空间）
  P5 — 记忆服务于连续性（不存储时长、正确率、连续天数）
  P7 — 不确定是一等公民（证据不足时不强制更新）
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.domain.session.runtime_context import LearnerDelta

logger = logging.getLogger(__name__)


# ── 辅助函数 ────────────────────────────────────────────


def _confidence_shift_to_belief_params(
    confidence_shift: float,
) -> tuple[bool, float]:
    """将 confidence_shift 转换为 belief_update 参数。

    Args:
        confidence_shift: -1 到 +1 之间的值

    Returns:
        (success, weight) — success 表示正向/负向更新，weight 表示更新强度
    """
    weight = min(abs(confidence_shift) * 2, 1.0)  # 0~1
    if confidence_shift > 0:
        return (True, weight)
    elif confidence_shift < 0:
        return (False, weight)
    else:
        return (True, 0.0)  # 无变化


def _build_skill_gain(
    skill_id: str,
    before: float,
    after: float,
    evidence: str,
) -> dict:
    """构造 GrowthRecord.skill_gains 中的单个条目。"""
    return {
        "skill": skill_id,
        "before": before,
        "after": after,
        "evidence": evidence,
        "category": "knowledge",
    }


# ── Main Service ─────────────────────────────────────────


class LearnerMemoryUpdater:
    """长期记忆更新器。

    LI-03 核心服务。将 Session 中的 learner_delta 和 reflection
    持久化到 BKT、GrowthRecord、LearnerProfile。
    """

    def __init__(
        self,
        cognitive_repo=None,
        cognitive_registry=None,
        growth_repo=None,
        learner_engine=None,
    ):
        """依赖注入，方便测试。"""
        self._cognitive_repo = cognitive_repo
        self._cognitive_registry = cognitive_registry
        self._growth_repo = growth_repo
        self._learner_engine = learner_engine

    def _ensure_deps(self):
        """懒加载依赖（生产环境单例）。"""
        if self._cognitive_repo is None:
            from app.domain.cognitive import get_repo
            self._cognitive_repo = get_repo()
        if self._cognitive_registry is None:
            from app.domain.cognitive.operation_registry import get_registry
            self._cognitive_registry = get_registry()
        if self._growth_repo is None:
            from app.domain.growth import get_growth_repo
            self._growth_repo = get_growth_repo()
        if self._learner_engine is None:
            from shared.learner_model import get_learner_model
            self._learner_engine = get_learner_model()

    async def apply_learner_delta(
        self,
        user_id: str,
        session_id: str,
        session_title: str,
        session_started_at: float,
        learner_delta: Optional[LearnerDelta],
        reflection: Optional[dict],
    ) -> dict:
        """应用 learner_delta 到持久层。

        Args:
            user_id: 用户 ID
            session_id: Session ID
            session_title: Session 标题（传给 GrowthRecord）
            session_started_at: Session 开始时间
            learner_delta: LI-02 产出的观察结果（可能为 None）
            reflection: 用户写的反思（可能为 None）

        Returns:
            dict: {
                "bkt_updated": int,      // 更新了几个 CognitiveNode
                "growth_record_id": str, // 创建的 GrowthRecord ID
                "patterns_updated": bool,
            }
        """
        self._ensure_deps()

        bkt_updated = 0
        skill_gains = []

        # ── 1. 应用 knowledge_updates 到 BKT ────────────

        if learner_delta and learner_delta.knowledge_updates:
            for update in learner_delta.knowledge_updates:
                try:
                    result = self._apply_knowledge_update(
                        user_id=user_id,
                        skill_id=update.skill_id,
                        confidence_shift=update.confidence_shift,
                        evidence=update.evidence,
                    )
                    if result:
                        bkt_updated += 1
                        skill_gains.append(result)
                except Exception:
                    logger.warning(
                        "LI-03: failed to update BKT for skill '%s':", update.skill_id,
                        exc_info=True,
                    )

        # ── 2. 创建 GrowthRecord ───────────────────────

        summary = ""
        key_takeaways = []
        reflection_snippet = None
        was_incomplete = False

        if reflection:
            summary = reflection.get("summary", reflection.get("content", ""))[:200]
            key_takeaways = reflection.get("key_takeaways", [])
            reflection_snippet = reflection.get("content", "")[:300]

        if not summary:
            # Reflection 跳过时，用 learner_delta 生成最小记录
            if learner_delta and learner_delta.growth_insights:
                summary = "; ".join(learner_delta.growth_insights)[:200]
            else:
                summary = f"完成了 {session_title}"
            was_incomplete = True

        growth_record = self._create_growth_record(
            user_id=user_id,
            session_id=session_id,
            session_title=session_title,
            session_started_at=session_started_at,
            summary=summary,
            key_takeaways=key_takeaways,
            reflection_snippet=reflection_snippet,
            skill_gains=skill_gains,
        )
        growth_id = growth_record.get("id", "")

        # ── 3. 更新推理模式 ────────────────────────────

        patterns_updated = False
        if learner_delta and learner_delta.reasoning_insights:
            try:
                self._update_reasoning_patterns(user_id, learner_delta.reasoning_insights)
                patterns_updated = True
            except Exception:
                logger.warning("LI-03: failed to update reasoning patterns", exc_info=True)

        return {
            "bkt_updated": bkt_updated,
            "growth_record_id": growth_id,
            "patterns_updated": patterns_updated,
            "incomplete": was_incomplete,
        }

    def _apply_knowledge_update(
        self,
        user_id: str,
        skill_id: str,
        confidence_shift: float,
        evidence: str,
    ) -> Optional[dict]:
        """将单个 knowledge_update 应用到 BKT。

        Args:
            user_id: 用户 ID
            skill_id: CognitiveNode ID
            confidence_shift: -1 到 +1
            evidence: 更新依据

        Returns:
            skill_gain dict（如果更新成功），None 如果节点不存在
        """
        node = self._cognitive_repo.get_node(skill_id, user_id)
        if not node:
            logger.warning("LI-03: CognitiveNode '%s' not found for user '%s'", skill_id, user_id)
            return None

        # 记录更新前的掌握度
        before = node.belief.proficiency_mean if node.belief else 0.5

        # 转换参数
        success, weight = _confidence_shift_to_belief_params(confidence_shift)

        # 调用 belief_update
        belief_state = {
            "belief_alpha": node.belief.alpha,
            "belief_beta": node.belief.beta,
            "belief_evidence_count": 0,
            "belief_last_updated": node.belief.last_updated,
        }

        result = self._cognitive_registry.execute(
            "belief_update",
            belief_state=belief_state,
            success=success,
            weight=weight,
        )
        after = result.get("belief_after", {})

        # 写回 CognitiveNode
        node.belief.alpha = after.get("belief_alpha", node.belief.alpha)
        node.belief.beta = after.get("belief_beta", node.belief.beta)
        alpha_beta_sum = node.belief.alpha + node.belief.beta
        node.belief.proficiency_mean = node.belief.alpha / alpha_beta_sum if alpha_beta_sum > 0 else 0.5
        node.belief.proficiency_precision = alpha_beta_sum
        node.belief.last_updated = after.get("belief_last_updated", time.time())

        self._cognitive_repo.upsert_node(node, user_id)

        return _build_skill_gain(
            skill_id=skill_id,
            before=before,
            after=node.belief.proficiency_mean,
            evidence=evidence or f"belief_update: ig={result.get('information_gain', 0):.4f}",
        )

    def _create_growth_record(
        self,
        user_id: str,
        session_id: str,
        session_title: str,
        session_started_at: float,
        summary: str,
        key_takeaways: list[str],
        reflection_snippet: Optional[str],
        skill_gains: list[dict],
    ) -> dict:
        """创建 GrowthRecord。

        Returns:
            dict: GrowthRecord 的 model_dump()
        """
        from app.domain.growth import create_growth_record

        record = create_growth_record(
            learner_id=user_id,
            session_id=session_id,
            session_title=session_title,
            session_started_at=session_started_at,
            session_finished_at=time.time(),
            skill_gains=skill_gains if skill_gains else None,
            summary=summary,
            reflection_snippet=reflection_snippet or "",
            key_takeaways=key_takeaways,
        )
        self._growth_repo.save(record)
        # GrowthRecord 是 dataclass，不是 Pydantic model
        return {
            "id": record.id,
            "summary": record.summary,
        }

    def _update_reasoning_patterns(
        self,
        user_id: str,
        reasoning_insights: list[str],
    ):
        """更新 LearnerProfile 推理模式。

        将本次 Session 的推理洞察累积到 LearnerProfile 的 JSONB 字段中。
        当前实现为简化存储（后续可以改进为结构化 profile）。
        """
        profile = self._learner_engine.get_or_create_profile(user_id)
        # LearnerProfile 目前没有 reasoning_insights 字段，
        # 使用 update_profile 存储到额外字段
        try:
            self._learner_engine.update_profile(
                user_id,
                {"last_reasoning_insights": reasoning_insights},
            )
        except Exception:
            logger.warning("LI-03: profile.update_profile not available", exc_info=True)


# ── Module-level convenience ─────────────────────────────

_updater: Optional[LearnerMemoryUpdater] = None


def get_memory_updater() -> LearnerMemoryUpdater:
    """获取全局 LearnerMemoryUpdater 单例。"""
    global _updater
    if _updater is None:
        _updater = LearnerMemoryUpdater()
    return _updater
