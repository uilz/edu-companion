"""
Material common utilities — 素材通用工具

从 embedding_utils 导入核心函数，避免直接依赖 classifier。
"""

from app.infrastructure.embedding_utils import (
    compute_embedding,
    cosine_similarity,
)

__all__ = ["compute_embedding", "cosine_similarity"]