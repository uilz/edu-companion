"""
Embedding 引擎：OpenVINO 加载本地 Granite 模型

模型位置：models/granite-embedding-97m/（相对项目根目录）
"""
import logging
import numpy as np
import os

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "models", "granite-embedding-97m"
))
_MODEL = None
_TOKENIZER = None


def _load():
    global _MODEL, _TOKENIZER
    try:
        from tokenizers import Tokenizer
        from openvino import Core

        # OpenVINO 模型：优先用 quantized 版本（有 .bin 文件）
        for cand in [
            os.path.join(_MODEL_PATH, "openvino", "openvino_model_qint8_quantized.xml"),
            os.path.join(_MODEL_PATH, "openvino_model.xml"),
        ]:
            if os.path.isfile(cand):
                xml_path = cand
                break
        else:
            logger.warning("OpenVINO model not found")
            return False

        core = Core()
        _MODEL = core.compile_model(xml_path, "CPU")

        tokenizer_path = os.path.join(_MODEL_PATH, "tokenizer.json")
        _TOKENIZER = Tokenizer.from_file(tokenizer_path)

        import json
        cfg_path = os.path.join(_MODEL_PATH, "config.json")
        max_len = 512
        if os.path.isfile(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f)
            max_len = cfg.get("max_position_embeddings", 512)

        _TOKENIZER.enable_truncation(max_length=128)  # 小 batch 减少内存
        _TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        logger.info("OpenVINO 模型加载成功: %s", xml_path)
        return True
    except Exception as e:
        logger.warning("模型加载失败: %s", e, exc_info=True)
        return False


def compute_embedding(text: str) -> list[float] | None:
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        if not _load():
            return None

    try:
        tokens = _TOKENIZER.encode(text)
        input_ids = np.expand_dims(np.array(tokens.ids, dtype=np.int64), 0)
        attention_mask = np.expand_dims(np.array(tokens.attention_mask, dtype=np.int64), 0)

        result = _MODEL([input_ids, attention_mask])
        output_key = list(result.keys())[0]
        token_embeddings = result[output_key]

        # mean pooling
        mask = np.expand_dims(attention_mask, -1).astype(np.float32)
        sum_emb = np.sum(token_embeddings * mask, axis=1)
        count = np.maximum(np.sum(mask, axis=1), 1e-9)
        embedding = sum_emb / count

        # L2 normalize
        norm = np.linalg.norm(embedding, axis=1, keepdims=True)
        if norm.any():
            embedding = embedding / np.maximum(norm, 1e-9)

        return embedding[0].tolist()
    except Exception as e:
        logger.warning("Embedding 计算失败: %s", e, exc_info=True)
        return None
