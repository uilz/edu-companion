"""习惯养成领域服务 — 骨架"""

class HabitServiceImpl:
    def __init__(self, event_bus):
        self._bus = event_bus

    async def on_answer_submitted(self, event):
        """事件: 答题 → 检查每日目标"""
        pass

    async def check_daily_goal(self, user_id):
        return {}

    async def get_pomodoro_suggestion(self, user_id):
        return {}

    async def get_tiny_habits(self, user_id):
        return []
