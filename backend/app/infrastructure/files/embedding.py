"""
Embedding — 文本向量化 (原 infrastructure/embedding_utils.py)

使用本地 OpenVINO 量化模型 (granite-embedding-97m)，纯 CPU 推理。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_embedding_model = None
_tokenizer = None


def _model_cached(model_name: str) -> bool:
    from pathlib import Path
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir_name = f"models--{model_name.replace('/', '--')}"
    return (cache_dir / model_dir_name).exists()


def _get_embedding_model():
    global _embedding_model, _tokenizer
    if _embedding_model is not None:
        return _embedding_model, _tokenizer

    from pathlib import Path
    model_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "granite-embedding-97m"

    if not model_path.is_dir():
        logger.warning("Embedding model not found at %s", model_path)
        return None, None

    try:
        from openvino import Core
        from tokenizers import Tokenizer

        core = Core()
        ov_model = core.read_model(str(model_path / "openvino_model.xml"))
        _embedding_model = core.compile_model(ov_model, "CPU")
        _tokenizer = Tokenizer.from_file(str(model_path / "tokenizer.json"))

        logger.info("✅ OpenVINO embedding model loaded: %s (384-dim)", model_path.name)
        return _embedding_model, _tokenizer
    except Exception as e:
        logger.error("Failed to load embedding model: %s", e)
        return None, None


def compute_embedding(text: str) -> list[float] | None:
    """计算 384 维 embedding (OpenVINO 推理)"""
    if not text or not text.strip():
        return None
    try:
        import numpy as np
        model, tokenizer = _get_embedding_model()
        if model is None or tokenizer is None:
            return None

        enc = tokenizer.encode(text.strip())
        max_len = 512
        if len(enc.ids) > max_len:
            enc.truncate(max_len)

        input_ids = np.array([enc.ids], dtype=np.int64)
        attention_mask = np.array([[1] * len(enc.ids)], dtype=np.int64)

        result = model([input_ids, attention_mask])
        output_key = list(result.keys())[0]
        vec = result[output_key][0, -1]
        return vec.tolist()
    except Exception:
        logger.debug("Embedding failed", exc_info=True)
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度"""
    try:
        import numpy as np
        a_np, b_np = np.array(a), np.array(b)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_np, b_np) / (norm_a * norm_b))
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)