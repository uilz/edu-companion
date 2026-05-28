"""提案采纳行动引擎 — 采纳提案后自动触发对应系统动作

工作机制:
  1. 用户点击"采纳" → API 调用 execute_action()
  2. 根据 action_type 分发到具体执行器
  3. 执行结果可注入对话上下文，实现无缝衔接

支持的动作类型:
  - review:   生成复习提纲/回顾内容
  - practice: 自动进入练习模式
  - rest:     推送休息建议
  - brief:    展开简报详情
  - explore:  推荐扩展学习资源
"""

from __future__ import annotations
from app.shared.constants import DEFAULT_USER_ID
import logging
from ..models import Proposal

logger = logging.getLogger(__name__)


class ProposalActionHandler:
    """提案采纳行动执行器"""

    def __init__(self) -> None:
        self._executors = {
            "review": self._execute_review,
            "practice": self._execute_practice,
            "rest": self._execute_rest,
            "brief": self._execute_brief,
            "explore": self._execute_explore,
        }

    async def execute(
        self, proposal: Proposal, user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        """执行提案动作，返回结果

        返回:
            {
                "action_type": str,
                "success": bool,
                "message": str,          # 给用户看的提示
                "context": str | None,   # 注入对话的上下文文本
                "payload": dict,         # 动作携带的数据
            }
        """
        executor = self._executors.get(proposal.action_type)
        if not executor:
            return {
                "action_type": proposal.action_type,
                "success": False,
                "message": f"未知动作类型: {proposal.action_type}",
                "context": None,
                "payload": proposal.payload or {},
            }

        result = await executor(proposal, user_id)

        # 记录执行日志
        logger.info(
            "执行提案动作: type=%s proposal=%s success=%s",
            proposal.action_type, proposal.id, result["success"],
        )

        return result

    # ── 各动作执行器 ──

    async def _execute_review(
        self, proposal: Proposal, user_id: str,
    ) -> dict[str, Any]:
        """复习动作 — 从 cognitive_nodes 提取知识点回顾"""
        kp_id = (proposal.payload or {}).get("kp_id", "")
        if not kp_id:
            return {
                "action_type": "review",
                "success": False,
                "message": "未指定复习知识点",
                "context": None,
                "payload": {},
            }

        # 从 cognitive_nodes 获取知识点详情
        context_text = None
        try:
            from app.cognitive.storage import get_node
            node = get_node(user_id, kp_id)
            if node and node.belief:
                import json as _json
                belief = node.belief
                if isinstance(belief, str):
                    belief = _json.loads(belief)
                proficiency = belief.get("proficiency_mean", 0.0)

                # 尝试获取最近练习记录
                recent_practice = ""
                if node.practice_summary:
                    acc = node.practice_summary.accuracy or 0
                    recent_practice = f"最近正确率 {acc:.0%}"

                context_text = (
                    f"📖 你选择了复习「{kp_id}」。"
                    f"当前掌握度 {proficiency:.0%}。{recent_practice}"
                )
        except Exception as e:
            logger.debug("获取知识点详情失败: %s", e)
            context_text = f"📖 开始复习「{kp_id}」"

        return {
            "action_type": "review",
            "success": True,
            "message": f"好的，我们来复习「{kp_id}」！",
            "context": context_text,
            "payload": {"kp_id": kp_id, **proposal.payload},
        }

    async def _execute_practice(
        self, proposal: Proposal, user_id: str,
    ) -> dict[str, Any]:
        """练习动作 — 生成或推荐练习题"""
        kp_id = (proposal.payload or {}).get("kp_id", "")

        context_text = "📝 开始专项练习"
        if kp_id:
            context_text = f"📝 针对「{kp_id}」进行专项练习"

        return {
            "action_type": "practice",
            "success": True,
            "message": f"好的，为你安排针对性练习！",
            "context": context_text,
            "payload": {"kp_id": kp_id, **proposal.payload},
        }

    async def _execute_rest(
        self, proposal: Proposal, user_id: str,
    ) -> dict[str, Any]:
        """休息动作 — 推荐休息"""
        payload = proposal.payload or {}
        reason = payload.get("reason", "")
        duration_min = payload.get("session_minutes", 0)

        context_text = "☕ 休息时间"
        if duration_min > 45:
            context_text = f"☕ 已学习 {duration_min//60}h{duration_min%60}m，建议休息 10 分钟"

        return {
            "action_type": "rest",
            "success": True,
            "message": "休息一下，学习效率更高哦！",
            "context": context_text,
            "payload": {"reason": reason, "duration_min": duration_min},
        }

    async def _execute_brief(
        self, proposal: Proposal, user_id: str,
    ) -> dict[str, Any]:
        """简报动作 — 展开学习简报详情"""
        payload = proposal.payload or {}
        date = payload.get("date", "今天")

        # 从 cognitive_nodes 收集更详细的数据
        details = []
        try:
            from app.cognitive.storage import list_all_nodes
            nodes = list_all_nodes(user_id)
            if nodes:
                subjects = {}
                for n in nodes:
                    if n.practice_summary and n.practice_summary.accuracy:
                        subjects[n.id] = {
                            "accuracy": n.practice_summary.accuracy,
                            "attempts": n.practice_summary.total_attempts or 0,
                        }
                details = [
                    f"  • {k}: 正确率 {v['accuracy']:.0%} ({v['attempts']} 题)"
                    for k, v in list(subjects.items())[:5]
                ]
        except Exception:
            pass

        context_parts = [f"📊 {date} 学习简报"]
        if details:
            context_parts.append("详细数据:")
            context_parts.extend(details)
        else:
            context_parts.append("暂无详细练习数据")

        return {
            "action_type": "brief",
            "success": True,
            "message": f"这是 {date} 的学习小结！",
            "context": "\n".join(context_parts[:8]),
            "payload": {"date": date, "detail_count": len(details), **payload},
        }

    async def _execute_explore(
        self, proposal: Proposal, user_id: str,
    ) -> dict[str, Any]:
        """探索动作 — 推荐扩展资源"""
        kp_id = (proposal.payload or {}).get("kp_id", "")

        context_text = "🔍 扩展学习"
        if kp_id:
            context_text = f"🔍 推荐「{kp_id}」的扩展资源"

        return {
            "action_type": "explore",
            "success": True,
            "message": "为你推荐一些扩展学习资源！",
            "context": context_text,
            "payload": {"kp_id": kp_id, **proposal.payload},
        }


# ── 全局实例 ──
action_handler = ProposalActionHandler()
