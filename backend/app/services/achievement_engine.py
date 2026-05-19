"""
成就激励引擎 v1.0

12 种成就，三级（青铜/白银/黄金）。
每次答题后触发检测，解锁时返回弹窗数据。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── 成就定义 ──

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    # ── 青铜（入门·一次性）──
    "first_practice": {
        "name": "初出茅庐",
        "icon": "🎯",
        "tier": "bronze",
        "description": "完成第 1 次练习",
        "trigger": "practice_count",
        "threshold": 1,
    },
    "first_correct": {
        "name": "首战告捷",
        "icon": "✨",
        "tier": "bronze",
        "description": "第 1 次答对",
        "trigger": "correct_count",
        "threshold": 1,
    },
    "first_session": {
        "name": "学习启程",
        "icon": "🚀",
        "tier": "bronze",
        "description": "创建第 1 个学习 session",
        "trigger": "session_count",
        "threshold": 1,
    },
    "first_conversation": {
        "name": "初次对话",
        "icon": "🗣️",
        "tier": "bronze",
        "description": "发送第 1 条对话消息",
        "trigger": "conversation_count",
        "threshold": 1,
    },

    # ── 白银（积累·可升级）──
    "question_master": {
        "name": "题海勇士",
        "icon": "⚔️",
        "tier": "silver",
        "description": "累计答题",
        "trigger": "practice_count",
        "levels": {1: 50, 2: 200, 3: 500},
    },
    "accuracy_champion": {
        "name": "百发百中",
        "icon": "💎",
        "tier": "silver",
        "description": "保持高正确率",
        "trigger": "accuracy",
        "levels": {1: 0.7, 2: 0.8, 3: 0.9},
        "needs_min_questions": True,
    },
    "streak_warrior": {
        "name": "持之以恒",
        "icon": "🔥",
        "tier": "silver",
        "description": "连续学习",
        "trigger": "streak",
        "levels": {1: 3, 2: 7, 3: 30},
    },
    "knowledge_explorer": {
        "name": "博学多才",
        "icon": "📖",
        "tier": "silver",
        "description": "掌握多个知识点",
        "trigger": "mastered_skills",
        "levels": {1: 5, 2: 15, 3: 30},
    },

    # ── 黄金（里程碑·一次性）──
    "all_rounder": {
        "name": "全能学者",
        "icon": "🏆",
        "tier": "gold",
        "description": "3 个学科各掌握 ≥1 个技能",
        "trigger": "multi_subject",
        "threshold": 3,
    },
    "speed_demon": {
        "name": "闪电思维",
        "icon": "⚡",
        "tier": "gold",
        "description": "单题 10s 内答对（累计 10 次）",
        "trigger": "fast_correct",
        "threshold": 10,
    },
    "perfectionist": {
        "name": "完美主义",
        "icon": "👑",
        "tier": "gold",
        "description": "单次 session 10 题全对",
        "trigger": "perfect_session",
        "threshold": 1,
    },
    "comeback_kid": {
        "name": "逆袭之王",
        "icon": "🦅",
        "tier": "gold",
        "description": "同一技能 mastery 从 <20% → ≥80%",
        "trigger": "comeback",
        "threshold": 1,
    },
}

# ── Engine ──

class AchievementEngine:
    """成就检测引擎"""

    def __init__(self):
        pass

    def check_all(
        self,
        user_id: str,
        stats: dict[str, Any],
        existing_achievements: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        检测所有成就，返回新解锁的列表。

        stats 包含：
        - practice_count: int
        - correct_count: int
        - accuracy: float (0-1)
        - session_count: int
        - conversation_count: int
        - streak: int
        - mastered_skills: int
        - multi_subject_count: int
        - fast_correct: int
        - perfect_session: int
        - comeback: int
        """
        if existing_achievements is None:
            existing_achievements = {}

        newly_unlocked: list[dict[str, Any]] = []

        for ach_id, ach_def in ACHIEVEMENTS.items():
            existing = existing_achievements.get(ach_id) or {}

            if ach_def.get("levels"):
                # 可升级成就
                current_level = existing.get("level", 0)
                levels = ach_def["levels"]
                for lv in sorted(levels.keys()):
                    if lv > current_level:
                        threshold = levels[lv]
                        value = stats.get(ach_def["trigger"], 0)
                        if ach_def.get("needs_min_questions") and stats.get("practice_count", 0) < 50:
                            continue
                        if value >= threshold:
                            newly_unlocked.append({
                                "id": ach_id,
                                "name": f"{ach_def['name']} Lv{lv}",
                                "icon": ach_def["icon"],
                                "tier": ach_def["tier"],
                                "level": lv,
                                "description": ach_def["description"],
                                "unlocked_at": datetime.now().isoformat(),
                            })
            else:
                # 一次性成就
                if existing:
                    continue  # 已解锁
                threshold = ach_def.get("threshold", 1)
                value = stats.get(ach_def["trigger"], 0)
                if value >= threshold:
                    newly_unlocked.append({
                        "id": ach_id,
                        "name": ach_def["name"],
                        "icon": ach_def["icon"],
                        "tier": ach_def["tier"],
                        "level": 1,
                        "description": ach_def["description"],
                        "unlocked_at": datetime.now().isoformat(),
                    })

        return newly_unlocked

    def get_all_with_progress(
        self,
        stats: dict[str, Any],
        existing_achievements: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """获取所有成就（含进度），用于成就墙展示"""
        if existing_achievements is None:
            existing_achievements = {}

        result = []
        for ach_id, ach_def in ACHIEVEMENTS.items():
            existing = existing_achievements.get(ach_id) or {}
            trigger = ach_def["trigger"]
            value = stats.get(trigger, 0)

            if ach_def.get("levels"):
                levels = ach_def["levels"]
                # Find current level
                current = existing.get("level", 0)
                next_lv = None
                next_threshold = None
                for lv in sorted(levels.keys()):
                    if lv > current:
                        next_lv = lv
                        next_threshold = levels[lv]
                        break
                result.append({
                    "id": ach_id,
                    "name": ach_def["name"],
                    "icon": ach_def["icon"],
                    "tier": ach_def["tier"],
                    "description": ach_def["description"],
                    "unlocked": existing != {},
                    "level": current,
                    "max_level": max(levels.keys()),
                    "progress": min(value / (next_threshold or 1), 1.0) if next_threshold else 1.0,
                    "progress_label": f"{value}/{next_threshold or '∞'}",
                    "unlocked_at": existing.get("unlocked_at"),
                })
            else:
                result.append({
                    "id": ach_id,
                    "name": ach_def["name"],
                    "icon": ach_def["icon"],
                    "tier": ach_def["tier"],
                    "description": ach_def["description"],
                    "unlocked": existing != {},
                    "level": 1 if existing else 0,
                    "max_level": 1,
                    "progress": min(value / ach_def.get("threshold", 1), 1.0),
                    "progress_label": f"{value}/{ach_def.get('threshold', 1)}",
                    "unlocked_at": existing.get("unlocked_at"),
                })

        return result


# 全局实例
achievement_engine = AchievementEngine()
