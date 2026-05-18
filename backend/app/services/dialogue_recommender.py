"""
练习错误 → 深度对话推荐
PracticeToDialogueRecommendation

当检测到概念性错误、连续错误、或迷思概念时，
主动推荐学生切换到对话模式进行深度讨论。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.schemas.practice import (
    AttemptRecord,
    ErrorType,
    ErrorAnalysis,
    PracticeSession,
)

logger = logging.getLogger(__name__)


class PracticeToDialogueRecommendation:
    """
    练习后推荐深度对话
    
    四种触发条件（按优先级）：
    1. 同一知识点连续错 ≥2 次 → 练习效果差，需要对话引导
    2. 概念性错误（最严重）→ 做题治不了概念问题
    3. 迷思概念检测到 → 具体误解需要讨论
    4. 挫败感上升（连续错4题+）→ 情绪需要安抚+换个方式
    """

    # 每种触发条件的推荐文案模板
    TEMPLATES = {
        "consecutive_same_skill": (
            "这个知识点连续错了 {count} 次，做题效果可能不太好。"
            "要不要在对话中详细讨论一下？💬"
        ),
        "conceptual_error": (
            "检测到概念理解偏差：{detail}。"
            "概念问题靠做题很难纠正，聊聊会更有效。要切换到对话吗？💬"
        ),
        "misconception": (
            "你对'{detail}'的理解可能有偏差。"
            "这个问题值得深入讨论一下。聊聊？💬"
        ),
        "frustration": (
            "做了 {count} 道都错了，是不是思路卡住了？"
            "停下来聊聊也许能豁然开朗 💬"
        ),
        "media_search": (
            "在 {skill} 上遇到困难？🔍 我帮你搜了几个平台的讲解，"
            "点链接在新窗口打开看看～"
        ),
    }

    def should_recommend(
        self,
        session: PracticeSession,
        latest_error: Optional[ErrorAnalysis] = None,
    ) -> Optional[str]:
        """
        判断是否应该推荐切换对话
        
        参数:
            session: 当前练习session
            latest_error: 最新的错因分析
        
        返回:
            推荐文案（str），或 None（不推荐）
        """
        attempts = session.attempts or []

        # 需要至少2条记录才能判断
        if len(attempts) < 2:
            return None

        # 条件1: 同一知识点连续错 ≥2 次
        same_skill_errors = self._count_same_skill_consecutive_errors(attempts)
        if same_skill_errors >= 2:
            skill_id = self._get_last_error_skill(attempts)
            return self.TEMPLATES["consecutive_same_skill"].format(
                count=same_skill_errors
            )

        # 条件2: 概念性错误 —— 最严重，必须推荐
        if latest_error and latest_error.error_type == ErrorType.CONCEPTUAL:
            detail = latest_error.misconception or latest_error.error_subtype or "概念理解"
            return self.TEMPLATES["conceptual_error"].format(detail=detail[:50])

        # 条件3: 有具体迷思概念描述
        if latest_error and latest_error.misconception:
            return self.TEMPLATES["misconception"].format(
                detail=latest_error.misconception[:50]
            )

        # 条件4: 连续错4题+（挫败感）
        consecutive_wrong = self._count_consecutive_wrong(attempts)
        if consecutive_wrong >= 4:
            return self.TEMPLATES["frustration"].format(count=consecutive_wrong)

        return None

    def should_recommend_media(
        self,
        session: PracticeSession,
    ) -> Optional[tuple[str, str]]:
        """
        判断是否应该推荐媒体搜索
        
        返回:
            (推荐文案, 知识点ID) 或 None
        """
        attempts = session.attempts or []
        if len(attempts) < 1:
            return None

        # 任何错误都推荐媒体搜索，但不重复推荐（一个session一次）
        last = attempts[-1]
        if not last.is_correct:
            skill_id = "知识点"
            if last.error_analysis and last.error_analysis.related_skills:
                skill_id = last.error_analysis.related_skills[0]

            return (
                self.TEMPLATES["media_search"].format(skill=skill_id),
                skill_id,
            )

        return None

    def get_error_skill(self, session: PracticeSession) -> Optional[str]:
        """提取最近错误的知识点ID"""
        for a in reversed(session.attempts or []):
            if not a.is_correct and a.error_analysis and a.error_analysis.related_skills:
                return a.error_analysis.related_skills[0]
        return None

    def _count_same_skill_consecutive_errors(
        self, attempts: list[AttemptRecord]
    ) -> int:
        """统计最后N条中同一知识点的连续错误数"""
        if not attempts:
            return 0

        # 从最后一条向前数
        count = 0
        target_skill = None

        for a in reversed(attempts):
            if not a.error_analysis and a.is_correct:
                break  # 遇到正确的停止

            if target_skill is None:
                target_skill = a.error_analysis.related_skills[0] if (
                    a.error_analysis and a.error_analysis.related_skills
                ) else None

            if target_skill and a.error_analysis:
                if a.error_analysis.related_skills and a.error_analysis.related_skills[0] == target_skill:
                    count += 1
                else:
                    break
            elif not a.is_correct:
                count += 1
            else:
                break

        return count

    def _get_last_error_skill(self, attempts: list[AttemptRecord]) -> str:
        """获取最后一条错误的技能ID"""
        for a in reversed(attempts):
            if not a.is_correct and a.error_analysis:
                if a.error_analysis.related_skills:
                    return a.error_analysis.related_skills[0]
        return "知识点"

    def _count_consecutive_wrong(self, attempts: list[AttemptRecord]) -> int:
        """统计连续错误数"""
        count = 0
        for a in reversed(attempts):
            if not a.is_correct:
                count += 1
            else:
                break
        return count


# 全局实例
practice_to_dialogue = PracticeToDialogueRecommendation()
