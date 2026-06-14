"""验证 embedding_utils 提取的正确性

确保 compute_embedding / cosine_similarity 可从 embedding_utils 导入，
旧 classifier.py 保留兼容的 re-export。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock
import pytest


class TestEmbeddingUtilsImports:
    """验证导入路径的正确性"""

    def test_direct_import(self):
        """embedding_utils 可直接导入"""
        from app.infrastructure.embedding_utils import (
            compute_embedding,
            cosine_similarity,
        )
        assert callable(compute_embedding)
        assert callable(cosine_similarity)

    def test_classifier_reimport(self):
        """旧 classifier.py 保留 compute_embedding / cosine_similarity 的 re-export"""
        from app.services.common.classifier import (
            compute_embedding,
            cosine_similarity,
        )
        assert callable(compute_embedding)
        assert callable(cosine_similarity)

    def test_material_common_uses_embedding_utils(self):
        """material_common 从 embedding_utils 导入"""
        import app.infrastructure.media.material_common
        # 验证模块没有直接引用 classifier 的 compute_embedding
        import inspect
        source = inspect.getsource(app.services.materials.material_common)
        assert "from app.infrastructure.embedding_utils import" in source


class TestCosineSimilarity:
    """余弦相似度计算"""

    def test_identical_vectors(self):
        from app.infrastructure.embedding_utils import cosine_similarity
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        from app.infrastructure.embedding_utils import cosine_similarity
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite(self):
        from app.infrastructure.embedding_utils import cosine_similarity
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector(self):
        from app.infrastructure.embedding_utils import cosine_similarity
        assert cosine_similarity([0, 0], [1, 0]) == pytest.approx(0.0)

    def test_mixed(self):
        from app.infrastructure.embedding_utils import cosine_similarity
        sim = cosine_similarity([1, 2, 3], [4, 5, 6])
        import math
        expected = (4 + 10 + 18) / (math.sqrt(14) * math.sqrt(77))
        assert sim == pytest.approx(expected)
