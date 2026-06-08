"""行为触发提案生成器 — 根据学习行为自动生成提案

工作流程:
  1. 学习事件（练习、对话、会话完成）通过 EventBus 流入
  2. 分析行为模式（连续错误、学习时长、知识点覆盖）
  3. 生成有针对性的提案（复习、练习、扩展）

集成方式:
  - 作为 `SecretaryModule` 注册到 `module_registry`，定时检查行为数据
  - 也通过 `secretary_event_handler` 实时响应事件
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class BehaviorTriggerModule(SecretaryModule):
    """行为触发模块 — 分析学习行为生成提案"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="behavior_trigger",
            display_name="行为触发",
            emoji="🎯",
            description="根据练习表现、学习时长等行为自动生成复习/练习/扩展提案",
            default_enabled=True,
            run_interval_seconds=300,  # 5分钟
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """检查行为数据，生成提案"""
        proposals: list[Proposal] = []

        # 1. 检查是否有连续错误的知识点 → 生成复习提案
        try:
            from app.cognitive import get_repo
            nodes = await _async_get_nodes(user_id)
            if nodes:
                struggling = _find_struggling_topics(nodes)
                for item in struggling[:2]:  # 最多 2 条
                    proposals.append(Proposal(
                        emoji="📖",
                        title=f"薄弱点: {item.get('label', '')}",
                        description=f"连续 {item.get('consecutive_wrong', 0)} 次答错，"
                                    f"掌握度 {item.get('proficiency', 0):.0%}。"
                                    f"建议花 10 分钟回头复习基础概念",
                        action_type="review",
                        priority=4 if item.get('urgency', 0) > 0.7 else 3,
                        payload={
                            "kp_id": item.get("node_id", ""),
                            "reason": "consecutive_wrong",
                            "consecutive_wrong": item.get("consecutive_wrong", 0),
                            "proficiency": item.get("proficiency", 0),
                        },
                        insight_source="behavior_trigger:struggling",
                    ))
        except Exception as e:
            logger.debug("薄弱点检查失败: %s", e)

        # 2. 检查是否有长时间未练习的知识点
        try:
            if nodes:
                stale = _find_stale_topics(nodes)
                for item in stale[:2]:
                    proposals.append(Proposal(
                        emoji="🔁",
                        title=f"需要复习: {item.get('label', '')}",
                        description=f"已 {item.get('days_since_practice', 0)} 天未练习，"
                                    f"掌握度 {item.get('proficiency', 0):.0%}。复习以避免遗忘",
                        action_type="review",
                        priority=3,
                        payload={
                            "kp_id": item.get("node_id", ""),
                            "reason": "stale",
                            "days_since_practice": item.get("days_since_practice", 0),
                            "proficiency": item.get("proficiency", 0),
                        },
                        insight_source="behavior_trigger:stale",
                    ))
        except Exception as e:
            logger.debug("停滞知识点检查失败: %s", e)

        # 3. 检查学习活跃度 → 生成扩展提案
        try:
            if nodes:
                ready = _find_ready_for_expansion(nodes)
                for item in ready[:1]:  # 最多 1 条
                    proposals.append(Proposal(
                        emoji="🚀",
                        title=f"扩展学习: {item.get('label', '')}",
                        description=f"掌握度已达 {item.get('proficiency', 0):.0%}，可以挑战进阶内容",
                        action_type="explore",
                        priority=2,
                        payload={
                            "kp_id": item.get("node_id", ""),
                            "reason": "ready_for_expansion",
                            "proficiency": item.get("proficiency", 0),
                        },
                        insight_source="behavior_trigger:expansion",
                    ))
        except Exception as e:
            logger.debug("扩展检查失败: %s", e)

        return proposals

    async def on_activate(self) -> None:
        logger.info("行为触发模块激活")

    async def on_deactivate(self) -> None:
        logger.info("行为触发模块停用")


# ═══════════════════════════════════════════
#  分析辅助函数
# ═══════════════════════════════════════════


async def _async_get_nodes(user_id: str):
    """同步 list_all_nodes 包装为异步"""
    from app.cognitive import get_repo
    import asyncio
    return await asyncio.to_thread(get_repo().list_all_nodes, user_id)


def _find_struggling_topics(nodes: list) -> list[dict[str, Any]]:
    """找出掌握度低 + 连续错误的薄弱知识点"""
    results = []
    for node in nodes:
        if not node or not node.belief:
            continue
        import json as _json
        belief = node.belief
        if isinstance(belief, str):
            try:
                belief = _json.loads(belief)
            except Exception:
                continue

        proficiency = belief.get("proficiency_mean", 0.0)
        wrong_streak = belief.get("consecutive_wrong", 0)

        # 薄弱条件：掌握度 < 0.6 或 连续错误 >= 2
        if proficiency < 0.6 or wrong_streak >= 2:
            urgency = max(0, min(1, (0.6 - proficiency) + wrong_streak * 0.2))
            results.append({
                "node_id": node.id,
                "label": getattr(node, "label", node.id)[:30],
                "proficiency": proficiency,
                "consecutive_wrong": wrong_streak,
                "urgency": urgency,
            })

    results.sort(key=lambda x: x["urgency"], reverse=True)
    return results


def _find_stale_topics(nodes: list) -> list[dict[str, Any]]:
    """找出长时间未练习的知识点"""
    results = []
    now = time.time()
    for node in nodes:
        if not node or not node.practice_summary:
            continue

        last_practice = getattr(node.practice_summary, "last_practice_time", 0)
        if not last_practice:
            continue

        days_since = (now - last_practice) / 86400
        if days_since < 3:
            continue  # 不到 3 天不算停滞

        proficiency = 0.0
        if node.belief:
            import json as _json
            belief = node.belief
            if isinstance(belief, str):
                try:
                    belief = _json.loads(belief)
                except Exception:
                    continue
            proficiency = belief.get("proficiency_mean", 0.0)

        results.append({
            "node_id": node.id,
            "label": getattr(node, "label", node.id)[:30],
            "days_since_practice": round(days_since, 1),
            "proficiency": proficiency,
        })

    results.sort(key=lambda x: x["days_since_practice"], reverse=True)
    return results


def _find_ready_for_expansion(nodes: list) -> list[dict[str, Any]]:
    """找出高掌握度但未扩展的知识点"""
    results = []
    for node in nodes:
        if not node or not node.belief:
            continue
        import json as _json
        belief = node.belief
        if isinstance(belief, str):
            try:
                belief = _json.loads(belief)
            except Exception:
                continue

        proficiency = belief.get("proficiency_mean", 0.0)
        if proficiency >= 0.75 and hasattr(node, 'is_visible') and node.is_visible:
            results.append({
                "node_id": node.id,
                "label": getattr(node, "label", node.id)[:30],
                "proficiency": proficiency,
            })

    results.sort(key=lambda x: x["proficiency"], reverse=True)
    return results[:3]  # 前 3 个候选


# ═══════════════════════════════════════════
#  事件触发生成器（实时响应）
# ═══════════════════════════════════════════


async def on_practice_submitted(
    user_id: str,
    atom_node_ids: list[str] | None = None,
    correctness: float = 0.0,
) -> Proposal | None:
    """练习提交事件 → 低正确率时生成复习提案"""
    if correctness > 0.6:
        return None  # 正确率尚可，不生成

    if not atom_node_ids:
        return None

    # 取第一个知识点
    node_id = atom_node_ids[0]
    try:
        from app.cognitive import get_repo
        node = get_repo().get_node(node_id, user_id)
        label = getattr(node, "label", node_id) if node else node_id
    except Exception:
        label = node_id

    from ..models import Proposal
    return Proposal(
        emoji="📖",
        title=f"练习反馈: {label[:30]}",
        description=f"正确率 {correctness:.0%}，可以再练练巩固基础知识",
        action_type="review",
        priority=4 if correctness < 0.3 else 3,
        payload={
            "kp_id": node_id,
            "reason": "practice_feedback",
            "correctness": correctness,
        },
        insight_source="behavior_trigger:practice_feedback",
    )


async def on_session_completed(
    user_id: str,
    accuracy: float = 0.0,
    duration_minutes: int = 0,
    session_id: str = "",
) -> Proposal | None:
    """会话完成事件 → 生成回顾/反思提案"""
    if accuracy >= 0.8 and duration_minutes >= 20:
        from ..models import Proposal
        return Proposal(
            emoji="✅",
            title="学得不错！",
            description=f"本次 {duration_minutes} 分钟学习，正确率 {accuracy:.0%}。继续保持！",
            action_type="review",
            priority=2,
            payload={
                "accuracy": accuracy,
                "duration_minutes": duration_minutes,
                "session_id": session_id,
            },
            insight_source="behavior_trigger:session_completed",
        )

    if accuracy < 0.4 and duration_minutes > 15:
        from ..models import Proposal
        return Proposal(
            emoji="💪",
            title="需要调整学习节奏",
            description=f"本次正确率 {accuracy:.0%}，建议休息 5 分钟后再回来复习",
            action_type="rest",
            priority=3,
            payload={
                "accuracy": accuracy,
                "duration_minutes": duration_minutes,
                "session_id": session_id,
            },
            insight_source="behavior_trigger:session_completed",
        )

    return None