"""
习惯养成系统

基于 BJ Fogg TinyHabits 方法：
1. 从小开始（每天2题）
2. 锚定时间（每天固定时间提醒）
3. 庆祝成功（正反馈）

+ 番茄钟建议 + 每日目标追踪
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DailyGoal:
    level: str  # beginner / regular / intensive
    target_questions: int
    today_done: int
    today_remaining: int
    today_accuracy: float
    is_completed: bool
    streak_days: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "target_questions": self.target_questions,
            "today_done": self.today_done,
            "today_remaining": self.today_remaining,
            "today_accuracy": round(self.today_accuracy, 2),
            "is_completed": self.is_completed,
            "streak_days": self.streak_days,
            "message": self.message,
        }


@dataclass
class TinyHabit:
    """一个微习惯"""
    name: str
    anchor: str  # 锚定事件（"刷完牙后"）
    behavior: str  # 微行为（"做2道题"）
    celebration: str  # 庆祝方式
    days_done: int = 0
    total_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "anchor": self.anchor,
            "behavior": self.behavior,
            "celebration": self.celebration,
            "days_done": self.days_done,
            "total_days": self.total_days,
            "consistency": round(self.days_done / max(self.total_days, 1), 2),
        }


class HabitFormation:
    """
    习惯养成引擎

    每日目标分级：
    - beginner: 5题/10分钟
    - regular: 10题/20分钟
    - intensive: 20题/40分钟
    """

    DAILY_TARGETS = {
        "beginner": {"questions": 5, "minutes": 10, "label": "入门"},
        "regular": {"questions": 10, "minutes": 20, "label": "日常"},
        "intensive": {"questions": 20, "minutes": 40, "label": "强化"},
    }

    # 内置微习惯模板
    TINY_HABITS = [
        TinyHabit(
            name="晨间一练",
            anchor="吃完早饭后",
            behavior="打开学习助手工具做3道题",
            celebration="给自己一个 ✨",
        ),
        TinyHabit(
            name="睡前复习",
            anchor="刷完牙后",
            behavior="看一遍今天的错题",
            celebration="心里说'今天进步了' 💤",
        ),
        TinyHabit(
            name="等车刷题",
            anchor="等公交/地铁时",
            behavior="做2道选择题",
            celebration="默默说'零碎时间也没浪费' 🚇",
        ),
    ]

    def get_user_level(self, total_questions: int, study_days: int) -> str:
        """根据历史数据推断用户等级"""
        if study_days == 0:
            return "beginner"

        avg_daily = total_questions / max(study_days, 1)

        if avg_daily >= 15 and study_days >= 7:
            return "intensive"
        elif avg_daily >= 5 or study_days >= 3:
            return "regular"
        else:
            return "beginner"

    def check_daily_goal(
        self,
        today_questions: int,
        today_correct: int,
        today_accuracy: float,
        current_streak: int,
        total_questions: int,
        study_days: int,
    ) -> DailyGoal:
        """检查今日目标完成情况"""
        level = self.get_user_level(total_questions, study_days)
        target = self.DAILY_TARGETS[level]
        remaining = max(0, target["questions"] - today_questions)
        is_done = today_questions >= target["questions"]

        if is_done:
            msg = self._completion_message(level, today_questions, current_streak)
        elif today_questions == 0:
            msg = self._encourage_start(level, target["questions"])
        else:
            msg = self._progress_message(level, today_questions, remaining, target["questions"])

        return DailyGoal(
            level=level,
            target_questions=target["questions"],
            today_done=today_questions,
            today_remaining=remaining,
            today_accuracy=today_accuracy,
            is_completed=is_done,
            streak_days=current_streak,
            message=msg,
        )

    def get_tiny_habits(self, current_streak: int = 0) -> list[TinyHabit]:
        """获取推荐的微习惯列表（根据 streak 调整）"""
        habits = []
        for h in self.TINY_HABITS:
            habit = TinyHabit(
                name=h.name,
                anchor=h.anchor,
                behavior=h.behavior,
                celebration=h.celebration,
                days_done=min(current_streak, 30),
                total_days=max(current_streak, 1),
            )
            habits.append(habit)
        return habits

    def get_pomodoro_recommendation(self, fatigue_drop_minute: int | None) -> dict[str, Any]:
        """生成番茄钟建议"""
        if fatigue_drop_minute is None:
            return {
                "work_minutes": 25,
                "break_minutes": 5,
                "message": "建议使用标准番茄钟：学习25分钟 + 休息5分钟 🍅",
            }

        if fatigue_drop_minute < 20:
            return {
                "work_minutes": 15,
                "break_minutes": 5,
                "message": f"专注力在{fatigue_drop_minute}分钟左右下降，建议用短番茄钟：15分钟学习 + 5分钟休息 🍅",
            }
        elif fatigue_drop_minute < 45:
            return {
                "work_minutes": 25,
                "break_minutes": 5,
                "message": f"专注力可持续约{fatigue_drop_minute}分钟，标准番茄钟很适合你：25+5 🍅",
            }
        else:
            return {
                "work_minutes": 45,
                "break_minutes": 10,
                "message": f"专注力很强（{fatigue_drop_minute}分钟），可以用长番茄钟：45+10 🍅",
            }

    # ── 文案生成 ──

    def _completion_message(self, level: str, done: int, streak: int) -> str:
        labels = {
            "beginner": "今天已经完成入门目标",
            "regular": "日常目标达成",
            "intensive": "强化训练完成",
        }
        base = labels.get(level, "目标已完成")
        if streak >= 7:
            return f"🔥 {base}！已练{done}题，连续{streak}天，你是学习战士！"
        elif streak >= 3:
            return f"✅ {base}！已练{done}题，连续{streak}天，势头正盛！"
        else:
            return f"✅ {base}！已练{done}题，明天继续保持～"

    def _progress_message(self, level: str, done: int, remaining: int, target: int) -> str:
        pct = int(done / target * 100)
        if remaining <= 2:
            return f"快完成了！还差{remaining}题就达到今日目标 🏃"
        elif remaining <= 5:
            return f"已完成{pct}%，再练{remaining}题就完成今日目标 💪"
        else:
            return f"今日已完成{done}/{target}题，还有{remaining}题，加油 🌱"

    def _encourage_start(self, level: str, target: int) -> str:
        tips = {
            "beginner": f"今天还没开始哦～只需{target}题，5分钟就能完成！现在试试？🌱",
            "regular": f"今日目标{target}题，打开就是进步的第一步 💪",
            "intensive": f"今天还没练呢，{target}题的目标在等你 🎯",
        }
        return tips.get(level, f"今天还没开始学习，{target}题就能完成目标✨")


# 全局实例
habit_formation = HabitFormation()
