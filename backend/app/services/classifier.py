"""
分类服务 v2：关键词 + LLM 智能分类
降级策略：embedding (可选) > LLM 关键词提取 > 静态关键词匹配

sentence-transformers 未装时正常降级，不报错。
"""

from __future__ import annotations

import logging

from app.services.storage import storage

logger = logging.getLogger(__name__)

# ── 扩展关键词权重表 ──
KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {
    "高等数学": {
        "极限": 0.9, "导数": 0.9, "积分": 0.85, "微分": 0.85,
        "泰勒": 0.8, "级数": 0.8, "连续": 0.75, "中值定理": 0.8,
        "不定积分": 0.85, "定积分": 0.85, "多元函数": 0.7, "偏导数": 0.8,
        "重积分": 0.75, "曲线积分": 0.75, "曲面积分": 0.75, "无穷级数": 0.8,
    },
    "线性代数": {
        "矩阵": 0.9, "行列式": 0.9, "特征值": 0.85, "特征向量": 0.85,
        "向量": 0.7, "线性变换": 0.8, "线性方程组": 0.85, "秩": 0.75,
        "正交": 0.7, "对角化": 0.8, "二次型": 0.75,
    },
    "大学物理": {
        "电磁": 0.85, "力学": 0.8, "热力学": 0.8, "量子": 0.75,
        "波动": 0.7, "光学": 0.7, "电场": 0.8, "磁场": 0.8, "电路": 0.7,
        "牛顿": 0.8, "动量": 0.75, "能量": 0.7, "角动量": 0.75,
    },
    "概率论": {
        "概率": 0.85, "随机变量": 0.9, "分布": 0.8, "期望": 0.8,
        "方差": 0.8, "贝叶斯": 0.75, "正态分布": 0.85, "二项": 0.75,
        "泊松": 0.75, "协方差": 0.8, "大数定律": 0.7, "中心极限": 0.7,
    },
    "英语": {
        "单词": 0.7, "语法": 0.7, "阅读": 0.6, "听力": 0.6,
        "写作": 0.6, "翻译": 0.65, "词汇": 0.7, "时态": 0.65,
        "从句": 0.65, "作文": 0.6,
    },
    "程序设计": {
        "代码": 0.8, "编程": 0.8, "算法": 0.8, "数据结构": 0.8,
        "Python": 0.85, "Java": 0.8, "C": 0.75, "函数": 0.6,
        "数组": 0.7, "链表": 0.75, "递归": 0.75, "排序": 0.7,
        "debug": 0.7, "bug": 0.65, "编译": 0.6,
    },
    "数字电路": {
        "电路": 0.75, "逻辑门": 0.85, "触发器": 0.8, "寄存器": 0.8,
        "时序": 0.75, "组合逻辑": 0.8, "卡诺图": 0.85, "状态机": 0.75,
        "Verilog": 0.8, "FPGA": 0.7,
    },
    "通用学习": {
        "学习": 0.5, "方法": 0.5, "笔记": 0.5, "复习": 0.5,
        "考试": 0.5, "计划": 0.4, "安排": 0.4,
    },
}


def keyword_score(text: str, subject: str) -> float:
    """计算关键词匹配得分 (0-1)。最高匹配 + 多匹配奖励"""
    keywords = KEYWORD_WEIGHTS.get(subject, {})
    if not keywords:
        return 0.0
    matches = [(w, kw) for kw, w in keywords.items() if kw in text]
    if not matches:
        return 0.0
    # 最高匹配权重 (0.7) + 多匹配奖励 (0.3)
    best = max(w for w, _ in matches)
    bonus = min(0.3, 0.1 * (len(matches) - 1))
    return min(1.0, best * 0.7 + bonus)


def compute_embedding(text: str) -> list[float] | None:
    """计算 embedding，模型未装时返回 None"""
    try:
        from sentence_transformers import SentenceTransformer
        import os
        _model = SentenceTransformer(
            "ibm-granite/granite-embedding-278m-multilingual"
        )
        return _model.encode(text).tolist()
    except Exception:
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


class Classifier:
    """消息分类器 v2: 关键词为主，embedding 为辅"""

    def __init__(self) -> None:
        self._embeddings_cache: dict[str, list[float]] = {}

    def classify_partition(self, user_id: str, text: str) -> dict:
        """
        将文本分类到最合适的分区。
        优先关键词匹配，embedding 不可用时正常降级。
        """
        data = storage.load(user_id)

        if not data.partitions:
            return {
                "partition_id": None,
                "is_cross": False,
                "linked_partitions": [],
                "confidence": 0.0,
            }

        # 尝试获取 embedding（可能为 None）
        try:
            text_emb = compute_embedding(text)
        except Exception:
            text_emb = None

        scores: dict[str, float] = {}
        for pid, partition in data.partitions.items():
            # 关键词为主得分
            kw = keyword_score(text, partition.subject or "")
            kw_boost = keyword_score(text, partition.name)

            if text_emb is not None:
                # Embedding 可用：vec 60% + kw 40%
                target_text = f"{partition.name} {partition.subject or ''}"
                if pid not in self._embeddings_cache:
                    cached = compute_embedding(target_text)
                    if cached:
                        self._embeddings_cache[pid] = cached
                sim = cosine_similarity(text_emb, self._embeddings_cache.get(pid, text_emb))
                scores[pid] = sim * 0.5 + max(kw, kw_boost) * 0.5
            else:
                # 关键词为主：kw 70% + name match 30%
                scores[pid] = max(kw, 0.0) * 0.7 + kw_boost * 0.3

        # 按得分排序
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_pid, best_score = sorted_scores[0]

        # 确保最低匹配度
        if best_score < 0.15:
            return {
                "partition_id": None,  # 都不匹配 → 创建新分区
                "is_cross": False,
                "linked_partitions": [],
                "confidence": best_score,
            }

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
        """决定继续/新建分支"""
        # 引用词 → 继续当前分支
        reference_words = ["刚才", "上面", "之前", "那个", "这个题", "那道题", "接着", "继续"]
        if any(w in text for w in reference_words):
            return "continue"

        # 问题型 + 新关键词 → 新分支
        question_patterns = ["什么是", "怎么", "为什么", "解释", "求", "如何", "区别", "对比"]
        if len(text) > 20 and any(kw in text for kw in question_patterns):
            return "new_branch"

        return "continue"


# 全局单例
classifier = Classifier()
