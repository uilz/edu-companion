"""资料系统领域服务 — 骨架"""

class MaterialServiceImpl:
    def __init__(self, event_bus):
        self._bus = event_bus

    async def upload(self, user_id, file_path):
        return {}

    async def search(self, user_id, query, top_k=10):
        return []

    async def generate_questions(self, user_id, material_id, count=5):
        return []

    async def on_indexed(self, event):
        """事件: 索引完成 → 自动出题建议"""
        pass
