"""学习规划领域服务 — 骨架"""

class PlanningServiceImpl:
    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus

    async def generate_plan(self, user_id):
        return {}

    async def on_answer_submitted(self, event):
        """事件: 答题 → 更新计划进度"""
        pass

    async def on_session_completed(self, event):
        """事件: 会话完成 → 标记计划项完成"""
        pass

    async def on_knowledge_updated(self, event):
        """事件: 知识升级 → 重生成学习计划"""
        if event.new_mastery == "已掌握":
            # 移除已掌握知识点，加入下一级
            await self.generate_plan(event.user_id)
