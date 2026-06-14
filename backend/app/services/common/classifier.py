"""
分类服务 (精简) — 仅保留 embedding 工具函数的 re-export。

旧 KEYWORD_WEIGHTS 四级分类配置已删除，
新分类器请使用 app.services.common.classifier_service.ClassifierService。
"""

from __future__ import annotations

from app.infrastructure.embedding_utils import compute_embedding, cosine_similarity

__all__ = [
    "compute_embedding",
    "cosine_similarity",
]
