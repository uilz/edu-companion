"""对话系统领域服务 — 骨架"""
# 实际实现从原 app/services/conversation_llm.py, tree_ops.py 等迁移

class ConversationServiceImpl:
    def __init__(self, llm, event_bus, circuit):
        self._llm = llm
        self._bus = event_bus
        self._circuit = circuit

    async def send_message(self, user_id, content, partition_id=None, branch_id=None):
        return {}

    async def on_session_completed(self, event):
        """事件: 练习完成 → 写入对话记忆"""
        pass

    async def on_knowledge_updated(self, event):
        """事件: 知识升级 → LLM 上下文感知"""
        pass

    async def on_plan_generated(self, event):
        """事件: 计划生成 → 向用户推送新计划"""
        pass

    async def on_goal_achieved(self, event):
        """事件: 目标达成 → 推送祝贺"""
        pass

    async def inject_practice_context(self, user_id, branch_id, context):
        pass
