"""
Agent 编排器（Orchestrator）
根据用户意图和情绪，选择最合适的Agent来处理请求
这是整个系统的"大脑"，协调各组件协同工作
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from app.agents.base import BaseAgent
from app.agents.tutor import TutorAgent
from app.agents.coach import CoachAgent
from app.schemas.learner import IntentType, EmotionType

logger = logging.getLogger(__name__)


def _get_default_llm():
    from app.services.llm_service import llm_service
    return llm_service


def _get_default_learner():
    from app.core.learner_model import learner_engine
    return learner_engine

logger = logging.getLogger(__name__)


def _build_cognitive_context(user_id: str, profile=None) -> str | None:
    """从 CognitiveNode 构建知识状态摘要（Phase 6 迁移后优先）"""
    try:
        from app.db.database import get_db
        db = get_db()
        rows = db.fetchall(
            "SELECT id, belief FROM cognitive_nodes "
            "WHERE user_id = %s AND level IN ('atom', 'concept') "
            "AND belief != '{}'::jsonb "
            "ORDER BY updated_at DESC LIMIT 5",
            (user_id,)
        )
        if not rows:
            return None
        parts = []
        for r in rows:
            belief = r.get("belief", {})
            if isinstance(belief, str):
                import json
                try:
                    belief = json.loads(belief)
                except Exception:
                    belief = {}
            mu = belief.get("proficiency_mean", 0.0) if isinstance(belief, dict) else 0.0
            parts.append(f"{r['id']}: 掌握度 {mu:.2f}")
        return ", ".join(parts)
    except Exception:
        return None


class Orchestrator:
    """
    Agent 编排器

    工作流程：
    1. 接收用户消息
    2. 分析意图和情绪
    3. 选择合适的Agent
    4. 收集上下文（知识状态等）
    5. 调用Agent处理
    6. 返回结果
    """

    def __init__(
        self,
        llm: Optional[LLMService] = None,
        learner_engine=None,
        event_bus=None,  # Phase 5: 领域事件总线
    ) -> None:
        self.llm = llm or _get_default_llm()
        self._learner = learner_engine or _get_default_learner()
        self._bus = event_bus  # Phase 5

        # 初始化所有Agent
        self.agents: dict[str, BaseAgent] = {
            "tutor": TutorAgent(self.llm),
            "coach": CoachAgent(self.llm),
        }

        # 默认Agent
        self.default_agent_name = "tutor"

        logger.info(
            "编排器初始化完成，已注册Agent: %s",
            list(self.agents.keys()),
        )

    def _select_agent(
        self,
        intent: IntentType,
        emotion: EmotionType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BaseAgent:
        """
        根据意图和情绪选择最合适的Agent

        选择策略：
        1. 遍历所有Agent，看谁最匹配
        2. 如果多个Agent匹配，根据优先级选择
        3. 如果没有Agent匹配，使用默认Agent

        参数:
            intent: 检测到的意图
            emotion: 检测到的情绪
            metadata: 额外上下文

        返回:
            选中的Agent实例
        """
        # 优先级映射（数字越小越优先）
        priority_map = {
            "coach": 1,  # 练习/挫败感场景优先
            "tutor": 2,  # 知识讲解次之
        }

        # Phase 7.5: 协商意图直接路由到 CoachAgent
        if intent == IntentType.NEGOTIATE:
            coach = self.agents.get("coach")
            if coach:
                logger.info("检测到协商意图，选择 CoachAgent")
                return coach

        candidates: list[tuple[int, BaseAgent]] = []

        for name, agent in self.agents.items():
            if agent.should_handle(intent, emotion, metadata):
                priority = priority_map.get(name, 99)
                candidates.append((priority, agent))

        if candidates:
            # 选择优先级最高的
            candidates.sort(key=lambda x: x[0])
            selected = candidates[0][1]
            logger.info(
                "选择Agent [%s] 处理意图=%s 情绪=%s",
                selected.agent_name, intent.value, emotion.value,
            )
            return selected

        # 使用默认Agent
        default = self.agents[self.default_agent_name]
        logger.info("使用默认Agent [%s]", default.agent_name)
        return default

    async def analyze_message(
        self,
        user_message: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        分析用户消息的意图和情绪

        参数:
            user_message: 用户消息
            session_id: 会话ID

        返回:
            分析结果 {"intent": ..., "emotion": ..., "confidence": ..., "subject": ...}
        """
        context = None
        if session_id:
            session = self._learner.get_session(session_id)
            if session and session.get("messages"):
                # 取最近几条消息作为上下文
                recent = session["messages"][-3:]
                context = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in recent
                ]

        result = await self.llm.classify_intent(user_message, context)
        return result

    async def process_message(
        self,
        user_id: str,
        user_message: str,
        session_id: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        处理用户消息的完整流程

        参数:
            user_id: 用户ID
            user_message: 用户消息
            session_id: 会话ID
            subject: 学科

        返回:
            完整的处理结果
        """
        # 1. 分析意图和情绪
        analysis = await self.analyze_message(user_message, session_id)
        intent_str = analysis.get("intent", "unknown")
        emotion_str = analysis.get("emotion", "neutral")
        confidence = analysis.get("confidence", 0.0)

        # 转换为枚举
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN
        try:
            emotion = EmotionType(emotion_str)
        except ValueError:
            emotion = EmotionType.NEUTRAL

        detected_subject = analysis.get("subject") or subject

        # 2. 获取学习者上下文
        profile = self._learner.get_or_create_profile(user_id)
        metadata: dict[str, Any] = {
            "emotion": emotion_str,
            "subject": detected_subject,
            "user_id": user_id,
        }

        # 3. 选择Agent
        agent = self._select_agent(intent, emotion, metadata)

        # 4. 构建上下文消息
        context_messages: list[dict[str, str]] = []

        # 添加学科信息到上下文
        if detected_subject:
            context_messages.append({
                "role": "system",
                "content": f"当前讨论的学科是: {detected_subject}",
            })

        # 添加知识状态摘要到上下文（优先 CognitiveNode）
        cog_summary = _build_cognitive_context(user_id, profile)
        if cog_summary:
            context_messages.append({
                "role": "system",
                "content": f"学生的知识状态概览: {cog_summary}",
            })

        # 5. 检查黑板是否有秘书提案
        if session_id:
            proposals_context = await self._read_secretary_proposals(session_id)
            if proposals_context:
                context_messages.append({
                    "role": "system",
                    "content": proposals_context,
                })

        # 6. 调用Agent处理
        reply = await agent.handle(user_message, context_messages, metadata)

        # 6. 更新会话
        if session_id:
            self._learner.add_message_to_session(session_id, "user", user_message)
            self._learner.add_message_to_session(session_id, "assistant", reply)

        return {
            "reply": reply,
            "agent_used": agent.agent_name,
            "intent_detected": intent_str,
            "emotion_detected": emotion_str,
            "confidence": confidence,
            "subject": detected_subject,
        }

    async def process_message_stream(
        self,
        user_id: str,
        user_message: str,
        session_id: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式处理用户消息

        参数:
            user_id: 用户ID
            user_message: 用户消息
            session_id: 会话ID
            subject: 学科

        产出:
            逐片段的回复文本
        """
        # 1. 分析意图和情绪
        analysis = await self.analyze_message(user_message, session_id)
        intent_str = analysis.get("intent", "unknown")
        emotion_str = analysis.get("emotion", "neutral")

        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN
        try:
            emotion = EmotionType(emotion_str)
        except ValueError:
            emotion = EmotionType.NEUTRAL

        detected_subject = analysis.get("subject") or subject

        # 2. 获取上下文
        profile = self._learner.get_or_create_profile(user_id)
        metadata: dict[str, Any] = {
            "emotion": emotion_str,
            "subject": detected_subject,
            "user_id": user_id,
        }

        # 3. 选择Agent
        agent = self._select_agent(intent, emotion, metadata)

        # 4. 构建上下文
        context_messages: list[dict[str, str]] = []
        if detected_subject:
            context_messages.append({
                "role": "system",
                "content": f"当前讨论的学科是: {detected_subject}",
            })
        cog_summary = _build_cognitive_context(user_id, profile)
        if cog_summary:
            context_messages.append({
                "role": "system",
                "content": f"学生的知识状态概览: {cog_summary}",
            })

        # 5. 检查黑板是否有秘书提案
        if session_id:
            proposals_context = await self._read_secretary_proposals(session_id)
            if proposals_context:
                context_messages.append({
                    "role": "system",
                    "content": proposals_context,
                })

        # 6. 流式处理
        full_reply = ""
        async for chunk in agent.handle_stream(user_message, context_messages, metadata):
            full_reply += chunk
            yield chunk

        # 6. 更新会话
        if session_id:
            self._learner.add_message_to_session(session_id, "user", user_message)
            self._learner.add_message_to_session(session_id, "assistant", full_reply)

        # 7. Phase 5: 发布 AssistantReplied 事件 → 触发多媒体生成
        if self._bus and full_reply:
            import uuid
            from shared.events import AssistantReplied
            has_math = "$" in full_reply
            # 尝试提取知识点
            skill_ids = []
            # 简单检测学科关键词
            subjects = ["数学", "物理", "化学", "英语", "语文", "编程", "算法"]
            for s in subjects:
                if s in user_message or s in full_reply:
                    skill_ids.append(f"skill:{s}")
                    break
            try:
                await self._bus.publish(AssistantReplied(
                    user_id=user_id,
                    message_id=str(uuid.uuid4()),
                    content=full_reply,
                    contains_math=has_math,
                    skill_ids=skill_ids,
                ))
            except Exception:
                pass

    def get_available_agents(self) -> list[dict[str, str]]:
        """获取所有可用Agent的信息"""
        return [
            {
                "name": agent.agent_name,
                "description": agent.agent_description,
            }
            for agent in self.agents.values()
        ]

    async def _read_secretary_proposals(self, session_id: str) -> str | None:
        """从黑板读取秘书提案，格式化为上下文文本"""
        try:
            from app.core.blackboard import blackboard
            data = await blackboard.get(f"bb:secretary:{session_id}")
            if not data or data.get("status") != "ready":
                return None
            proposals = data.get("proposals", [])
            if not proposals:
                return None

            lines = ["📋 秘书建议（用户可自主选择，以协商口吻呈现）:"]
            for p in proposals[:3]:
                lines.append(f"- {p.get('emoji', '')} {p.get('title', '')}: {p.get('description', '')}")
            lines.append("请以上述建议为参考，与用户协商下一步行动，让用户自主选择。")

            report = data.get("report_summary")
            if report:
                lines.append(f"💡 诊断摘要: {report.get('summary', '')}")

            return "\n".join(lines)
        except Exception:
            return None


# ── 全局编排器实例 ──
orchestrator = Orchestrator()
