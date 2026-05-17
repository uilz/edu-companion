"""
分类服务：Embedding + LLM 两层分类
第一层：向量相似度 + 关键词匹配（快速）
第二层：LLM 确认（可选，MVP 暂不调用）
"""

from __future__ import annotations

import os

from app.services.storage import storage

# Embedding 模型（延迟加载）
_model = None

# 关键词权重表
KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {
    "高等数学": {
        "极限": 0.9, "导数": 0.9, "积分": 0.85, "微分": 0.85,
        "泰勒": 0.8, "级数": 0.8, "连续": 0.75,
    },
    "线性代数": {
        "矩阵": 0.9, "行列式": 0.9, "特征值": 0.85, "特征向量": 0.85,
        "向量": 0.7, "线性变换": 0.8,
    },
    "大学物理": {
        "电磁": 0.85, "力学": 0.8, "热力学": 0.8, "量子": 0.75,
        "波动": 0.7, "光学": 0.7,
    },
    "概率论": {
        "概率": 0.85, "随机变量": 0.9, "分布": 0.8, "期望": 0.8,
        "方差": 0.8, "贝叶斯": 0.75,
    },
    "英语": {
        "单词": 0.7, "语法": 0.7, "阅读": 0.6, "听力": 0.6,
        "写作": 0.6, "翻译": 0.65,
    },
}


def get_embedding_model():
    """延迟加载 embedding 模型"""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(
                "ibm-granite/granite-embedding-278m-multilingual"
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embedding. "
                "Install it with: pip install sentence-transformers"
            )
    return _model


def compute_embedding(text: str) -> list[float]:
    """计算文本的 embedding 向量"""
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()


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
        # 纯 Python fallback
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def keyword_score(text: str, subject: str) -> float:
    """计算关键词匹配得分"""
    keywords = KEYWORD_WEIGHTS.get(subject, {})
    if not keywords:
        return 0.0
    total_weight = sum(keywords.values())
    matched = sum(w for kw, w in keywords.items() if kw in text)
    return matched / total_weight if total_weight > 0 else 0.0


class Classifier:
    """消息分类器"""

    def __init__(self) -> None:
        self._embeddings_cache: dict[str, list[float]] = {}

    def classify_partition(self, user_id: str, text: str) -> dict:
        """
        将文本分类到最合适的分区
        返回: {"partition_id": str|None, "is_cross": bool, "linked_partitions": list, "confidence": float}
        """
        data = storage.load(user_id)

        if not data.partitions:
            return {
                "partition_id": None,
                "is_cross": False,
                "linked_partitions": [],
                "confidence": 0.0,
            }

        # 第一层：Embedding 相似度
        try:
            text_emb = compute_embedding(text)
        except ImportError:
            # 无 embedding 模型时只用关键词
            text_emb = None

        scores: dict[str, float] = {}
        for pid, partition in data.partitions.items():
            # 用分区名称 + 学科作为 embedding 目标
            target_text = f"{partition.name} {partition.subject}"

            if text_emb is not None:
                if pid not in self._embeddings_cache:
                    self._embeddings_cache[pid] = compute_embedding(target_text)
                sim = cosine_similarity(text_emb, self._embeddings_cache[pid])
            else:
                sim = 0.5  # 默认值

            # 结合关键词得分
            kw = keyword_score(text, partition.subject)
            combined = sim * 0.6 + kw * 0.4
            scores[pid] = combined

        # 按得分排序
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_pid, best_score = sorted_scores[0]

        # 高置信度 → 直接匹配
        if best_score > 0.85:
            return {
                "partition_id": best_pid,
                "is_cross": False,
                "linked_partitions": [],
                "confidence": best_score,
            }

        # MVP: 直接返回最佳匹配
        return {
            "partition_id": best_pid,
            "is_cross": False,
            "linked_partitions": [],
            "confidence": best_score,
        }

    def decide_branch(
        self,
        user_id: str,
        partition_id: str,
        text: str,
        recent_messages: list[str],
    ) -> str:
        """
        决定是继续当前分支还是新建分支
        返回: "continue" | "new_branch" | "fork:{message_id}"
        """
        # 检测引用词
        reference_words = ["刚才", "上面", "之前", "那个", "这个题", "那道题"]
        if any(w in text for w in reference_words):
            return "continue"

        # 长文本 + 新问题关键词 → 新分支
        if len(text) > 50 and any(
            kw in text for kw in ["什么是", "怎么", "为什么", "解释", "求"]
        ):
            return "new_branch"

        return "continue"


# 全局单例
classifier = Classifier()
