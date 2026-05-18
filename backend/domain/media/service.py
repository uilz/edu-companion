"""媒体搜索领域服务 — 骨架"""

class MediaServiceImpl:
    async def search(self, query, platforms=None):
        return {}

    async def recommend_for_error(self, skill_id, error_type):
        return []

    async def on_error_recorded(self, event):
        """事件: 错题 → 推荐相关视频"""
        pass
