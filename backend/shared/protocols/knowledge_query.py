"""
Knowledge Query Service Protocol — 知识查询模块对外契约

统一知识状态查询、上下文生成、对话证据分析、认知同步等能力。
其他模块只能通过此接口调用知识查询功能。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, AsyncGenerator

from shared.constants import DEFAULT_USER_ID


@runtime_checkable
class KnowledgeQueryService(Protocol):
    """知识查询模块对外契约"""

    # ── 上下文生成（注入 LLM system prompt） ──

    def get_knowledge_context(self, user_id: str = DEFAULT_USER_ID) -> str:
        """生成注入 LLM system prompt 的知识上下文"""
        ...

    def get_skill_context(self, skill_ids: list[str], user_id: str = DEFAULT_USER_ID) -> str:
        """获取特定技能的知识上下文"""
        ...

    def get_cognitive_profile(self, user_id: str = DEFAULT_USER_ID) -> str:
        """返回 CognitiveNode 的格式化画像摘要"""
        ...

    # ── 技能查询 ──

    def get_all_skills_summary(self, user_id: str = DEFAULT_USER_ID) -> dict:
        """获取所有技能的摘要"""
        ...

    def get_skill_detail(self, skill_id: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
        """获取单个技能详情"""
        ...

    def get_weak_skills(self, limit: int = 5, user_id: str = DEFAULT_USER_ID) -> list[str]:
        """获取薄弱技能列表"""
        ...

    def get_mastered_skills(self, user_id: str = DEFAULT_USER_ID) -> list[str]:
        """获取已掌握技能列表"""
        ...

    # ── 对话证据分析 ──

    def detect_dialogue_evidence(self, text: str) -> tuple[str | None, float]:
        """快速关键词检测对话证据（零 token）"""
        ...

    async def analyze_dialogue_evidence(
        self,
        user_text: str,
        assistant_reply: str,
        skill_ids: list[str],
    ) -> list[dict]:
        """分析一轮对话中的知识证据"""
        ...

    # ── 认知同步 ──

    def post_message_hooks(self, user_id: str, dir_id: str, node) -> None:
        """消息存储后的钩子：异步写元历史 + 触发分支命名/图谱更新"""
        ...

    async def analyze_conversation_evidence(
        self,
        user_id: str,
        dir_id: str,
        user_text: str,
        assistant_reply: str,
        conv_id: str = "",
    ) -> None:
        """分析一轮对话，提取知识证据（通过 CognitiveNode 事件系统）"""
        ...

    async def cognify_dialogue_context(
        self,
        user_id: str,
        conversation,
        skill_ids: list[str],
        context_type: str = "lower",
    ) -> None:
        """异步向 CognitiveNode 写入对话上下文"""
        ...
