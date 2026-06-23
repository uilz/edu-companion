"""
KnowledgeAtom — 统一知识标识桥接层

单一知识源：为 CognitiveNode / KnowledgeNode / KGNode 提供统一 id 映射。
写操作统一走此模块，读操作仍可用各模型的原生查询。
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeAtom:
    """统一知识标识 — 单一真相源"""
    atom_id: str  # 统一 id，格式: ka_{uuid}
    label: str
    level: str  # partition/domain/topic/concept/atom
    cognitive_node_id: Optional[str] = None  # 对应 CognitiveNode.id
    knowledge_node_id: Optional[str] = None  # 对应 KnowledgeNode.id
    kg_node_id: Optional[str] = None         # 对应 KGNode.id
    path_id: str = ""
    created_by: str = "system"
    metadata: dict = field(default_factory=dict)


class KnowledgeAtomRegistry:
    """知识原子注册中心 — 维护统一 id 与各模型 id 的映射"""

    def __init__(self):
        self._by_atom_id: dict[str, KnowledgeAtom] = {}
        self._by_cognitive_id: dict[str, str] = {}  # cognitive_id -> atom_id
        self._by_knowledge_id: dict[str, str] = {}  # knowledge_id -> atom_id
        self._by_kg_id: dict[str, str] = {}         # kg_id -> atom_id
        self._by_label: dict[str, list[str]] = {}   # label -> [atom_id]

    def register(self, atom: KnowledgeAtom) -> KnowledgeAtom:
        self._by_atom_id[atom.atom_id] = atom
        if atom.cognitive_node_id:
            self._by_cognitive_id[atom.cognitive_node_id] = atom.atom_id
        if atom.knowledge_node_id:
            self._by_knowledge_id[atom.knowledge_node_id] = atom.atom_id
        if atom.kg_node_id:
            self._by_kg_id[atom.kg_node_id] = atom.atom_id
        if atom.label not in self._by_label:
            self._by_label[atom.label] = []
        if atom.atom_id not in self._by_label[atom.label]:
            self._by_label[atom.label].append(atom.atom_id)
        return atom

    def resolve(self, id_or_label: str, id_type: str = "auto") -> Optional[KnowledgeAtom]:
        """通过任意 id 解析到统一 KnowledgeAtom"""
        if id_type == "cognitive" or (id_type == "auto" and id_or_label in self._by_cognitive_id):
            atom_id = self._by_cognitive_id.get(id_or_label)
            return self._by_atom_id.get(atom_id) if atom_id else None
        if id_type == "knowledge" or (id_type == "auto" and id_or_label in self._by_knowledge_id):
            atom_id = self._by_knowledge_id.get(id_or_label)
            return self._by_atom_id.get(atom_id) if atom_id else None
        if id_type == "kg" or (id_type == "auto" and id_or_label in self._by_kg_id):
            atom_id = self._by_kg_id.get(id_or_label)
            return self._by_atom_id.get(atom_id) if atom_id else None
        if id_type == "atom" or (id_type == "auto" and id_or_label in self._by_atom_id):
            return self._by_atom_id.get(id_or_label)
        return None

    def get_cognitive_id(self, atom_id: str) -> Optional[str]:
        atom = self._by_atom_id.get(atom_id)
        return atom.cognitive_node_id if atom else None

    def get_knowledge_id(self, atom_id: str) -> Optional[str]:
        atom = self._by_atom_id.get(atom_id)
        return atom.knowledge_node_id if atom else None

    def get_kg_id(self, atom_id: str) -> Optional[str]:
        atom = self._by_atom_id.get(atom_id)
        return atom.kg_node_id if atom else None


# 全局单例
_registry: Optional[KnowledgeAtomRegistry] = None


def get_atom_registry() -> KnowledgeAtomRegistry:
    global _registry
    if _registry is None:
        _registry = KnowledgeAtomRegistry()
    return _registry


def reset_atom_registry():
    global _registry
    _registry = None