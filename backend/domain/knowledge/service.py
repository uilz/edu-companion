"""知识图谱领域服务 — 骨架"""

class KnowledgeGraphServiceImpl:
    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus

    async def on_answer_submitted(self, event):
        """事件: 答题 → 更新图谱掌握度"""
        pass

    async def on_error_recorded(self, event):
        """事件: 错题 → 标记薄弱知识点"""
        pass

    async def get_graph(self, user_id):
        return {}

    async def can_practice(self, user_id, skill_id):
        return True, None

    async def find_learning_path(self, user_id, target_skill):
        return []
