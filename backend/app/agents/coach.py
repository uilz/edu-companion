"""
Coach Agent（教练智能体）
负责练习指导、错题分析、学习策略建议

特点：
- 分析错误原因，给出针对性建议
- 提供练习策略和方法指导
- 帮助制定和调整学习计划
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from app.agents.base import BaseAgent
from app.schemas.learner import IntentType, EmotionType

logger = logging.getLogger(__name__)


class CoachAgent(BaseAgent):
    """教练智能体 - 练习指导与学习策略"""

    agent_name: str = "coach"
    agent_description: str = "练习指导、错题分析、学习策略建议"

    def __init__(self, llm_service: Any) -> None:
        super().__init__(llm_service)
        self._system_prompt = self._build_system_prompt()
        # Phase 5: 配置工具
        from app.services.tool_executor import TOOL_DEFINITIONS, tool_executor
        self.set_tools(TOOL_DEFINITIONS, tool_executor)

    def _build_system_prompt(self) -> str:
        return """你是一位学习教练，名叫"小练"。你擅长帮助学生制定练习策略和分析学习问题。

## 核心能力
1. **错题分析**：分析错误原因，找出知识薄弱点
2. **练习指导**：推荐合适的练习内容和方法
3. **学习策略**：提供时间管理、记忆技巧等学习方法
4. **进度评估**：帮助学生了解自己的学习状态

## 回复风格
- 务实、有条理，像一位贴心的教练
- 使用列表和步骤化的方式组织信息
- 给出具体可执行的建议
- 适当鼓励，但不盲目夸赞

## 错题分析策略
1. 首先确认学生的理解（"你是怎么想的？"）
2. 找出具体的错误点
3. 解释为什么这个答案是错的
4. 给出正确的思路和方法
5. 类似题目练习建议

## 学习策略建议
- **间隔重复**：建议复习频率
- **主动回忆**：鼓励先尝试回忆再看答案
- **番茄工作法**：建议学习时间安排
- **错题本**：帮助整理常见错误类型

## 注意事项
- 根据学生的知识水平调整建议难度
- 如果学生情绪低落，先给予鼓励再提建议
- 建议要具体，避免空洞的"加油"
"""

    def should_handle(
        self,
        intent: IntentType,
        emotion: EmotionType,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Coach Agent 优先处理以下情况：
        - 练习相关 (practice)
        - 挫败感 (frustration)
        - 寻求鼓励 (encouragement)
        """
        handle_intents = {
            IntentType.PRACTICE,
            IntentType.FRUSTRATION,
            IntentType.ENCOURAGEMENT,
        }
        return intent in handle_intents

    async def handle(
        self,
        user_message: str,
        context: Optional[list[dict[str, str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """非流式处理"""
        # 如果有元数据（如知识状态），加入上下文
        enhanced_context = list(context) if context else []
        if metadata:
            if "knowledge_state" in metadata:
                enhanced_context.append({
                    "role": "system",
                    "content": f"当前学生知识状态信息: {metadata['knowledge_state']}",
                })
            if "emotion" in metadata:
                enhanced_context.append({
                    "role": "system",
                    "content": f"检测到学生当前情绪: {metadata['emotion']}",
                })

        messages = self.get_messages(user_message, enhanced_context)
        reply = await self.llm.generate(
            messages=messages,
            task_type="chat",
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
        enhanced_context = list(context) if context else []
        if metadata:
            if "knowledge_state" in metadata:
                enhanced_context.append({
                    "role": "system",
                    "content": f"当前学生知识状态信息: {metadata['knowledge_state']}",
                })
            if "emotion" in metadata:
                enhanced_context.append({
                    "role": "system",
                    "content": f"检测到学生当前情绪: {metadata['emotion']}",
                })

        messages = self.get_messages(user_message, enhanced_context)
        full_reply = ""
        async for chunk in self._stream_with_tools(
            messages=messages,
            task_type="chat",
            temperature=0.7,
            max_tokens=2048,
        ):
            full_reply += chunk
            yield chunk
        self.record_exchange(user_message, full_reply)

    def generate_error_analysis(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        explanation: str,
    ) -> str:
        """
        生成错题分析报告（结构化提示词）

        返回格式化的分析请求，交由LLM处理
        """
        return f"""请分析以下错题：

【题目】{question}
【学生的答案】{student_answer}
【正确答案】{correct_answer}
【参考解析】{explanation}

请从以下角度分析：
1. 错误类型（概念错误/计算错误/粗心/理解偏差等）
2. 涉及的知识点
3. 学生可能的思维过程
4. 针对性的改进建议
5. 类似题目的练习建议"""
