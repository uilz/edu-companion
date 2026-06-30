"""
Material common utilities — 素材通用工具 (services 层 re-export)

从 embedding_utils 导入核心函数。
"""

from app.infrastructure.embedding_utils import (
    compute_embedding,
    cosine_similarity,
)

__all__ = ["compute_embedding", "cosine_similarity"]