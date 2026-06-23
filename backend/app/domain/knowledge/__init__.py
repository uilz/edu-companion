from app.services.knowledge.knowledge_query_service import KnowledgeQueryServiceImpl

from app.domain.knowledge.knowledge_atom import (
    KnowledgeAtom,
    KnowledgeAtomRegistry,
    get_atom_registry,
    reset_atom_registry,
)

# ── 全局访问器 ──

_knowledge_query_instance: KnowledgeQueryServiceImpl | None = None


def get_knowledge_query() -> KnowledgeQueryServiceImpl:
    """获取全局 KnowledgeQueryService 实例"""
    global _knowledge_query_instance
    if _knowledge_query_instance is None:
        _knowledge_query_instance = KnowledgeQueryServiceImpl()
    return _knowledge_query_instance


def set_knowledge_query(service: KnowledgeQueryServiceImpl) -> None:
    """设置全局 KnowledgeQueryService 实例（由 DI 容器调用）"""
    global _knowledge_query_instance
    _knowledge_query_instance = service
