"""
Knowledge v5 — 四实体解耦架构服务层

KnowledgeNodeService: 知识点 CRUD (封装 CognitiveNode 仓储)
ConversationService: 会话 CRUD (独立 PG 表)
NavigationService: 导航树 CRUD (独立 PG 表)
MessageService: 消息 CRUD (独立 PG 表)
KnowledgeEventBus: 事件总线 + SSE 推送
"""
from app.services.knowledge_tree.knowledge_node_service import KnowledgeNodeService, kn_svc
from app.services.knowledge_tree.conversation_service import ConversationService, conv_svc
from app.services.knowledge_tree.navigation_service import NavigationService, nav_svc
from app.services.knowledge_tree.message_service import MessageService, msg_svc
from app.services.knowledge_tree.event_bus_service import KnowledgeEventBus, KnowledgeEvent, kb_event_bus

__all__ = [
    "KnowledgeNodeService", "kn_svc",
    "ConversationService", "conv_svc",
    "NavigationService", "nav_svc",
    "MessageService", "msg_svc",
    "KnowledgeEventBus", "KnowledgeEvent", "kb_event_bus",
]