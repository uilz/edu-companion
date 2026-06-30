"""
infrastructure/files/ — 文件系统基础设施层

文件边界 (R3 第二轮回购):
- parser.py:   文件 → Markdown 解析 (原 material_parser)
- chunker.py:  分块策略 (原 material_toc_extractor)
- indexer.py:  索引编排 + 后处理 (原 material_indexer)
- embedding.py: 向量化 (原 embedding_utils)
- search.py:   搜索引擎 (原 material_search)
- storage.py:  DB 工具函数 (原 material_common)
"""

from .parser import material_parser
from .chunker import TOCNode, extract_toc, assign_chunk_ranges, chunk_by_toc
from .indexer import MaterialIndexer, material_indexer
from .embedding import compute_embedding, cosine_similarity
from .search import MaterialSearch, material_search, HIT_THRESHOLD
from .storage import get_pool

__all__ = [
    "material_parser",
    "TOCNode", "extract_toc", "assign_chunk_ranges", "chunk_by_toc",
    "MaterialIndexer", "material_indexer",
    "compute_embedding", "cosine_similarity",
    "MaterialSearch", "material_search", "HIT_THRESHOLD",
    "get_pool",
]