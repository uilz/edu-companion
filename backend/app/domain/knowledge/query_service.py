"""
知识查询服务实现 — 统一委托到 cognitive_queries + cognitive_sync

将分散的知识查询和认知同步能力收敛到单一入口。
"""

from __future__ import annotations

import logging
from typing import Optional

from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


class KnowledgeQueryServiceImpl:
    """知识查询服务实现 — 委托到 cognitive_queries + cognitive_sync"""

    # ── 上下文生成 ──

    def get_knowledge_context(self, user_id: str = DEFAULT_USER_ID) -> str:
        from app.services.knowledge.cognitive_queries import get_knowledge_context
        return get_knowledge_context(user_id)

    def get_skill_context(self, skill_ids: list[str], user_id: str = DEFAULT_USER_ID) -> str:
        from app.services.knowledge.cognitive_queries import get_skill_context
        return get_skill_context(skill_ids, user_id)

    def get_cognitive_profile(self, user_id: str = DEFAULT_USER_ID) -> str:
        from app.services.knowledge.cognitive_queries import get_cognitive_profile
        return get_cognitive_profile(user_id)

    # ── 技能查询 ──

    def get_all_skills_summary(self, user_id: str = DEFAULT_USER_ID) -> dict:
        from app.services.knowledge.cognitive_queries import get_all_skills_summary
        return get_all_skills_summary(user_id)

    def get_skill_detail(self, skill_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
        from app.services.knowledge.cognitive_queries import get_skill_detail
        return get_skill_detail(skill_id, user_id)

    def get_weak_skills(self, limit: int = 5, user_id: str = DEFAULT_USER_ID) -> list[str]:
        from app.services.knowledge.cognitive_queries import get_weak_skills
        return get_weak_skills(limit, user_id)

    def get_mastered_skills(self, user_id: str = DEFAULT_USER_ID) -> list[str]:
        from app.services.knowledge.cognitive_queries import get_mastered_skills
        return get_mastered_skills(user_id)

    # ── 对话证据分析 ──

    def detect_dialogue_evidence(self, text: str) -> tuple[Optional[str], float]:
        from app.services.knowledge.cognitive_queries import detect_dialogue_evidence
        return detect_dialogue_evidence(text)

    async def analyze_dialogue_evidence(
        self,
        user_text: str,
        assistant_reply: str,
        skill_ids: list[str],
    ) -> list[dict]:
        from app.services.knowledge.cognitive_queries import analyze_dialogue_evidence
        return await analyze_dialogue_evidence(user_text, assistant_reply, skill_ids)

    # ── 认知同步 ──

    def post_message_hooks(self, user_id: str, partition_id: str, node) -> None:
        from app.services.knowledge.cognitive_sync import _p0_post_message_hooks
        return _p0_post_message_hooks(user_id, partition_id, node)

    async def analyze_conversation_evidence(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        assistant_reply: str,
        conversation_id: str = "",
    ) -> None:
        from app.services.knowledge.cognitive_sync import _analyze_conversation_evidence
        return await _analyze_conversation_evidence(
            user_id, partition_id, user_text, assistant_reply, conversation_id,
        )

    async def cognify_dialogue_context(
        self,
        user_id: str,
        conversation,
        skill_ids: list[str],
        context_type: str = "lower",
    ) -> None:
        from app.services.knowledge.cognitive_sync import _cognify_dialogue_context
        return await _cognify_dialogue_context(
            user_id, conversation, skill_ids, context_type,
        )
