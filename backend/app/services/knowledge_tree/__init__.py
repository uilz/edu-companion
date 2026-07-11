"""
Knowledge — 四实体解耦架构服务层

KnowledgeTreeService: 知识树容器 CRUD
TreeNodeService: 知识树节点 CRUD
TreeEdgeService: 知识树边 CRUD
CognitiveLinkService: 树节点-认知节点关联
ConversationService: 会话 CRUD (独立 PG 表)
NavigationService: 导航树 CRUD (独立 PG 表)
MessageService: 消息 CRUD (独立 PG 表)
KnowledgeEventBus: 事件总线 + SSE 推送
"""
from app.services.knowledge_tree.tree_service import KnowledgeTreeService, kt_svc
from app.services.knowledge_tree.tree_node_service import TreeNodeService, tn_svc
from app.services.knowledge_tree.tree_edge_service import TreeEdgeService, te_svc
from app.services.knowledge_tree.cognitive_link_service import CognitiveLinkService, cl_svc
from app.services.knowledge_tree.knowledge_node_service import KnowledgeNodeService, kn_svc
from app.services.knowledge_tree.conversation_service import ConversationService, conv_svc
from app.services.knowledge_tree.navigation_service import NavigationService, nav_svc
from app.services.knowledge_tree.message_service import MessageService, msg_svc
from app.services.knowledge_tree.event_bus_service import KnowledgeEventBus, KnowledgeEvent, kb_event_bus

__all__ = [
    "KnowledgeTreeService", "kt_svc",
    "TreeNodeService", "tn_svc",
    "TreeEdgeService", "te_svc",
    "CognitiveLinkService", "cl_svc",
    "KnowledgeNodeService", "kn_svc",
    "ConversationService", "conv_svc",
    "NavigationService", "nav_svc",
    "MessageService", "msg_svc",
    "KnowledgeEventBus", "KnowledgeEvent", "kb_event_bus",
]