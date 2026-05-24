"""内置模块: 元认知反思提示 (MetaCognitivePrompt)

功能: 在学习会话结束后，建议元认知反思提示，帮助用户固化学习收获
触发条件:
  - SessionContext 显示有近期的学习活动
  - 会话持续 >= 5 分钟 或 已完成一定数量的习题

反思提示库:
  - 旨在引导用户思考＂我学到了什么？哪些策略有效？下一步该做什么？＂
  - 随机从预定义提示池中挑选，保持新鲜感
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)

# ── 元认知反思提示池 ──

_REFLECTION_PROMPTS = [
    {
        "question": "今天学到的最重要的一个概念是什么？",
        "focus": "concept_extraction",
        "hint": "试着用自己的话总结出来，就像在教给别人一样。",
    },
    {
        "question": "刚才的练习中，哪种类型的题目让你感觉最吃力？",
        "focus": "difficulty_awareness",
        "hint": "识别薄弱点比盲目刷题效率更高。",
    },
    {
        "question": "如果有机会重新开始这次学习，你会改变什么策略？",
        "focus": "strategy_reflection",
        "hint": "反思学习方法本身，是提升效率的关键。",
    },
    {
        "question": "这次学习的内容和你以前学过的知识有什么联系？",
        "focus": "knowledge_linking",
        "hint": "建立知识网络比孤立记忆更持久。",
    },
    {
        "question": "你觉得刚才的专注度和效率怎么样？有什么因素影响了你的状态？",
        "focus": "metacognitive_awareness",
        "hint": "了解自己的注意力规律，才能更好地安排学习计划。",
    },
    {
        "question": "接下来你打算继续深入这个主题，还是切换到其他内容？为什么？",
        "focus": "next_step_planning",
        "hint": "有意识地规划下一步，避免随波逐流。",
    },
    {
        "question": "今天的学习中，有没有哪个瞬间让你觉得「明白了」？",
        "focus": "aha_moment_capture",
        "hint": "记录顿悟时刻，它们是你理解跃迁的标记点。",
    },
    {
        "question": "如果要对今天的掌握度打分（1-10），你会打几分？差距在哪里？",
        "focus": "self_assessment",
        "hint": "坦诚评估是精准复习的前提。",
    },
]

# 会话时长阈值（分钟），超过则认为是有意义的学习会话
_SESSION_DURATION_THRESHOLD_MIN = 5

# 题目数量阈值
_QUESTIONS_THRESHOLD = 3


class MetaCognitivePromptModule(SecretaryModule):
    """元认知反思提示模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="meta_cognitive_prompt",
            display_name="元认知反思",
            emoji="🧠",
            description="学习后建议元认知反思提示，帮助固化收获",
            default_enabled=True,
            run_interval_seconds=600,  # 每 10 分钟检查一次
        )

    def _is_recent_learning_activity(self, ctx: SessionContext | None) -> bool:
        """判断是否有近期的学习活动"""
        if ctx is None:
            return False
        return (
            ctx.session_duration_min >= _SESSION_DURATION_THRESHOLD_MIN
            or ctx.questions_done_recently >= _QUESTIONS_THRESHOLD
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """检查是否适合建议元认知反思"""
        proposals: list[Proposal] = []

        if not self._is_recent_learning_activity(ctx):
            return proposals

        # 从提示池中随机选一条
        prompt = random.choice(_REFLECTION_PROMPTS)

        proposals.append(Proposal(
            emoji="🧠",
            title="反思一下刚才的学习",
            description=f"**{prompt['question']}**\n\n💡 {prompt['hint']}",
            action_type="reflect",
            payload={
                "question": prompt["question"],
                "focus": prompt["focus"],
                "hint": prompt["hint"],
            },
            priority=3,
            generated_by="meta_cognitive_prompt",
            overrideable=True,
        ))

        return proposals
