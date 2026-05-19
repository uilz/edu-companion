"""
Tutor Agent（导师智能体）
负责知识讲解、概念解释、苏格拉底式引导教学

特点：
- 善于用通俗易懂的语言解释复杂概念
- 使用苏格拉底式提问引导学生思考
- 举例说明，使用类比帮助理解
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from app.agents.base import BaseAgent
from app.schemas.learner import IntentType, EmotionType

logger = logging.getLogger(__name__)


class TutorAgent(BaseAgent):
    """导师智能体 - 知识讲解与引导"""

    agent_name: str = "tutor"
    agent_description: str = "知识讲解、概念解释、苏格拉底式引导教学"

    def __init__(self, llm_service: Any) -> None:
        super().__init__(llm_service)
        self._system_prompt = self._build_system_prompt()
        # Phase 5: 配置工具
        from app.services.tool_executor import TOOL_DEFINITIONS, tool_executor
        self.set_tools(TOOL_DEFINITIONS, tool_executor)

    def _build_system_prompt(self) -> str:
        return """你是一位经验丰富的学习导师，名叫"小智"。你的教学风格如下：

## 核心教学原则
1. **循序渐进**：从简单到复杂，确保每一步学生都能理解
2. **苏格拉底式提问**：不直接给答案，而是通过提问引导学生自己思考
3. **举例说明**：用生活中的例子解释抽象概念
4. **鼓励探索**：激发学生的好奇心和学习兴趣

## 回复风格
- 语言亲切自然，像朋友一样交流
- 使用中文回复，适当使用emoji增加趣味性
- 回答简洁但完整，避免过于冗长
- 在适当的地方使用类比和比喻
- 代码和公式要格式化清晰

## 教学策略
- 如果学生提问：先确认理解问题，然后引导思考
- 如果学生请求解释概念：先问学生了解多少，再针对性讲解
- 如果学生表达困惑：先安抚情绪，再重新组织讲解
- 如果学生情绪低落：给予鼓励，适当降低难度

## 注意事项
- 不要一次讲太多，保持每次回复在合理长度
- 如果涉及数学公式，使用清晰的格式
- 鼓励学生提出更多问题
"""

    def should_handle(
        self,
        intent: IntentType,
        emotion: EmotionType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Tutor Agent 优先处理以下情况：
        - 提问 (question)
        - 请求解释 (explain)
        - 复习 (review)
        - 闲聊（当情绪积极时）
        """
        handle_intents = {
            IntentType.QUESTION,
            IntentType.EXPLAIN,
            IntentType.REVIEW,
            IntentType.CHITCHAT,
        }
        return intent in handle_intents

    async def handle(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """非流式处理"""
        messages = self.get_messages(user_message, context)
        reply = await self.llm.generate(
            messages=messages,
            task_type="explain",
            temperature=0.7,
            max_tokens=2048,
        )
        self.record_exchange(user_message, reply)
        return reply

    async def handle_stream(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式处理 — Phase 5: 支持 tool calling"""
        messages = self.get_messages(user_message, context)
        full_reply = ""
        async for chunk in self._stream_with_tools(
            messages=messages,
            task_type="explain",
            temperature=0.7,
            max_tokens=2048,
        ):
            full_reply += chunk
            yield chunk
        self.record_exchange(user_message, full_reply)

    def create_socratic_prompt(self, question: str, subject: str) -> str:
        """
        生成苏格拉底式引导问题

        当学生直接要答案时，用引导的方式帮助学生思考
        """
        return f"""学生提出了关于{subject}的问题："{question}"

请不要直接给出答案，而是：
1. 先肯定学生的思考
2. 提出2-3个引导性问题，帮助学生自己发现答案
3. 如果学生之前已经尝试过但失败了，给予适当的提示
4. 保持耐心和鼓励的语气"""
