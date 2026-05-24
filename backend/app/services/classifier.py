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


def _model_cached(model_name: str) -> bool:
    """检查 HuggingFace 模型是否已在本地缓存（无网络时不卡60秒）"""
    from pathlib import Path
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir_name = f"models--{model_name.replace('/', '--')}"
    return (cache_dir / model_dir_name).exists()


def compute_embedding(text: str) -> list[float] | None:
    """计算 embedding，优先加载本地模型（无网络时也不卡60s）"""
    import os
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "models", "granite-embedding-97m"
    )
    if not os.path.isdir(model_path):
        logger.warning("Embedding model not found at %s, skipping", model_path)
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_path)
        return _model.encode(text).tolist()
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


# ── 领域关键词表（按学科分区） ──
DOMAIN_KEYWORDS: dict[str, dict[str, float]] = {
    "高等数学": {
        "分析": {"极限": 0.9, "导数": 0.85, "积分": 0.85, "连续": 0.7, "中值定理": 0.8,
                 "微分": 0.8, "级数": 0.75, "泰勒": 0.75},
        "代数": {"矩阵": 0.6, "行列式": 0.6, "方程": 0.55, "向量": 0.55},  # 弱匹配，主要是分析
        "几何": {"曲线": 0.7, "曲面": 0.7, "空间": 0.65},
    },
    "线性代数": {
        "矩阵论": {"矩阵": 0.9, "秩": 0.8, "逆": 0.75, "转置": 0.7, "分块": 0.7},
        "向量空间": {"向量": 0.8, "空间": 0.7, "基": 0.75, "维数": 0.7, "子空间": 0.8, "线性无关": 0.8},
        "特征理论": {"特征值": 0.9, "特征向量": 0.85, "对角化": 0.8, "相似": 0.7, "二次型": 0.75},
        "线性方程组": {"方程组": 0.9, "解": 0.6, "齐次": 0.8, "通解": 0.75, "特解": 0.7},
    },
    "大学物理": {
        "力学": {"牛顿": 0.85, "动量": 0.8, "能量": 0.8, "角动量": 0.8, "运动": 0.7, "刚体": 0.75},
        "电磁学": {"电磁": 0.85, "电场": 0.85, "磁场": 0.85, "电路": 0.75, "麦克斯韦": 0.8},
        "热学": {"热": 0.8, "温度": 0.7, "熵": 0.75, "气体": 0.7, "热力学": 0.85},
        "光学": {"光": 0.75, "透镜": 0.7, "干涉": 0.8, "衍射": 0.8, "偏振": 0.75},
        "量子": {"量子": 0.85, "波函数": 0.8, "薛定谔": 0.8, "能级": 0.7},
    },
    "概率论": {
        "随机变量": {"随机变量": 0.9, "分布": 0.8, "密度": 0.7, "期望": 0.8, "方差": 0.8},
        "常见分布": {"正态": 0.85, "二项": 0.8, "泊松": 0.8, "指数": 0.75, "均匀": 0.7},
        "极限定理": {"大数定律": 0.9, "中心极限": 0.9, "收敛": 0.7},
        "多维": {"联合": 0.75, "边缘": 0.75, "协方差": 0.85, "相关": 0.7},
    },
    "程序设计": {
        "语言基础": {"Python": 0.85, "Java": 0.8, "C": 0.75, "语法": 0.7, "函数": 0.65, "变量": 0.6},
        "数据结构": {"数组": 0.75, "链表": 0.8, "树": 0.75, "栈": 0.75, "队列": 0.75, "图": 0.7, "哈希": 0.8},
        "算法": {"算法": 0.9, "排序": 0.8, "搜索": 0.75, "递归": 0.8, "动态规划": 0.85, "贪心": 0.75, "回溯": 0.75},
        "工程实践": {"debug": 0.7, "测试": 0.65, "git": 0.65, "重构": 0.65, "项目": 0.6},
    },
    "数字电路": {
        "组合逻辑": {"逻辑门": 0.9, "卡诺图": 0.85, "编码器": 0.8, "译码器": 0.8, "多路": 0.75},
        "时序逻辑": {"触发器": 0.9, "寄存器": 0.85, "计数器": 0.8, "状态机": 0.85, "时序": 0.75},
        "硬件描述": {"Verilog": 0.85, "FPGA": 0.8, "VHDL": 0.75, "仿真": 0.65},
    },
}

# ── 专题关键词表（更细粒度）──
TOPIC_KEYWORDS: dict[str, dict[str, dict[str, float]]] = {
    "高等数学": {
        "分析": {
            "极限与连续": {"极限": 0.9, "连续": 0.8, "间断": 0.75, "ε-δ": 0.9},
            "导数与微分": {"导数": 0.9, "求导": 0.85, "微分": 0.85, "切线": 0.7, "变化率": 0.7},
            "中值定理": {"中值定理": 0.9, "罗尔": 0.85, "拉格朗日": 0.85, "柯西": 0.8, "泰勒": 0.8},
            "不定积分": {"不定积分": 0.9, "原函数": 0.8, "换元": 0.8, "分部积分": 0.85},
            "定积分": {"定积分": 0.9, "面积": 0.65, "广义积分": 0.75, "反常积分": 0.75},
        },
        "几何": {
            "空间解析几何": {"曲面": 0.8, "曲线": 0.75, "切平面": 0.8, "法线": 0.75},
        },
    },
    "线性代数": {
        "矩阵论": {
            "矩阵运算": {"矩阵": 0.85, "乘法": 0.6, "转置": 0.75, "逆矩阵": 0.8, "伴随": 0.75},
        },
        "向量空间": {
            "向量与空间": {"向量": 0.8, "基": 0.8, "维数": 0.75, "线性无关": 0.85, "子空间": 0.8},
            "线性变换": {"线性变换": 0.9, "映射": 0.7, "核": 0.7, "像": 0.65},
        },
        "特征理论": {
            "特征值与对角化": {"特征值": 0.9, "特征向量": 0.85, "对角化": 0.85, "相似": 0.75},
            "二次型": {"二次型": 0.9, "正定": 0.8, "标准形": 0.8, "惯性指数": 0.75},
        },
        "线性方程组": {
            "方程组求解": {"方程组": 0.9, "齐次": 0.8, "通解": 0.8, "特解": 0.75, "增广": 0.7},
        },
    },
    "概率论": {
        "随机变量": {
            "随机变量基础": {"随机变量": 0.9, "分布函数": 0.8, "离散": 0.7, "连续": 0.7},
            "数字特征": {"期望": 0.9, "方差": 0.85, "协方差": 0.8, "矩": 0.7},
        },
        "常见分布": {
            "正态分布": {"正态": 0.9, "高斯": 0.85, "标准正态": 0.85},
            "其他分布": {"二项": 0.8, "泊松": 0.8, "指数": 0.75, "均匀": 0.7, "几何": 0.65},
        },
        "极限定理": {
            "大数定律": {"大数定律": 0.9, "切比雪夫": 0.8, "辛钦": 0.75, "伯努利": 0.7},
            "中心极限定理": {"中心极限": 0.9, "正态逼近": 0.8, "棣莫弗": 0.75},
        },
    },
}


class Classifier:
    """消息分类器 v3: 分区→领域→专题 三级分类，关键词为主"""

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


    def classify_full(
        self, user_id: str, text: str, current_partition_id: str = "",
    ) -> dict:
        """
        三级分类：分区 → 领域 → 专题。
        返回完整路由信息，含是否需要切换推荐。
        """
        data = storage.load(user_id)

        # Step 1: 分区分类（复用现有逻辑）
        partition_result = self.classify_partition(user_id, text)
        partition_id = partition_result.get("partition_id")
        confidence = partition_result.get("confidence", 0.0)

        if not partition_id and current_partition_id:
            # 无法归类但存在当前分区 → 留在当前
            partition_id = current_partition_id
            confidence = 0.3

        if not partition_id:
            # 完全无法归类 → 需创建新分区
            return {
                "partition_id": None,
                "domain_name": None,
                "topic_name": None,
                "is_switch": False,
                "confidence": 0.0,
            }

        partition = data.partitions.get(partition_id)
        partition_subject = (partition.subject or partition.name) if partition else ""

        # Step 2: 领域分类（关键词匹配）
        domain_name: str | None = None
        domain_score = 0.0
        domain_kws = DOMAIN_KEYWORDS.get(partition_subject, {})

        for dname, kws in domain_kws.items():
            score = keyword_score(text, "")  # reset
            # Manual score for domain keywords
            best = 0.0
            count = 0
            for kw, w in kws.items():
                if kw in text:
                    best = max(best, w)
                    count += 1
            s = best * 0.7 + min(0.3, 0.1 * (count - 1)) if count > 0 else 0.0
            if s > domain_score:
                domain_score = s
                domain_name = dname

        if domain_score < 0.3:
            # 低分不强制 fallback，设为 None 让上层决定
            domain_name = None
            domain_score = 0.0

        # Step 3: 专题分类
        topic_name: str | None = None
        topic_score = 0.0

        topic_kws = TOPIC_KEYWORDS.get(partition_subject, {}).get(domain_name or "", {})
        if topic_kws:
            for tname, kws in topic_kws.items():
                best = 0.0
                count = 0
                for kw, w in kws.items():
                    if kw in text:
                        best = max(best, w)
                        count += 1
                s = best * 0.7 + min(0.3, 0.1 * max(0, count - 1)) if count > 0 else 0.0
                if s > topic_score:
                    topic_score = s
                    topic_name = tname

        if topic_score < 0.3:
            topic_name = None  # 模糊匹配时不强制定专题

        # Step 4: 判断是否需要推荐切换
        is_switch = False
        if current_partition_id and partition_id != current_partition_id:
            is_switch = True

        return {
            "partition_id": partition_id,
            "domain_name": domain_name,
            "topic_name": topic_name,
            "is_switch": is_switch,
            "confidence": confidence,
        }

    def auto_resolve(
        self, user_id: str, text: str,
        current_partition_id: str = "", current_conversation_id: str = "",
    ) -> dict:
        """
        完整自动路由：分类 + 创建缺失层级 + 返回最终路由。
        由 send_and_reply_stream 调用的统一入口。
        """
        from app.services.tree_ops import tree_ops

        # 1. 分类
        full = self.classify_full(user_id, text, current_partition_id)

        partition_id = full["partition_id"]
        domain_name = full["domain_name"]
        topic_name = full["topic_name"]

        # 2. 如果无法归类且无当前分区 → 自动创建
        if not partition_id:
            partition = tree_ops.create_partition(user_id, text[:20], emoji="💬")
            partition_id = partition.id
            # Re-classify to get domain/topic for the new partition
            full = self.classify_full(user_id, text, partition_id)
            domain_name = full.get("domain_name")
            topic_name = full.get("topic_name")

        # 3. 确保领域存在
        data = storage.load(user_id)
        existing_domain = None
        for d in data.domains.values():
            if d.partition_id == partition_id and d.name == domain_name:
                existing_domain = d
                break

        if not existing_domain and domain_name:
            existing_domain = tree_ops.create_domain(user_id, partition_id, domain_name)

        domain_id = existing_domain.id if existing_domain else None

        # 4. 确保专题存在
        existing_topic = None
        if domain_id:
            for t in data.topics.values():
                if t.domain_id == domain_id and (not topic_name or t.name == topic_name):
                    existing_topic = t
                    break
            if not existing_topic:
                topic_name_final = topic_name or domain_name or "新专题"
                existing_topic = tree_ops.create_topic(user_id, domain_id, topic_name_final)

        topic_id = existing_topic.id if existing_topic else None

        # 5. 确认活跃对话
        data = storage.load(user_id)
        conversation_id = ""
        if topic_id:
            topic = data.topics.get(topic_id)
            if topic and topic.active_conversation_id:
                conversation_id = topic.active_conversation_id

        # 6. 判断是否推荐切换
        should_recommend_switch = False
        switch_detail: dict = {}

        if current_partition_id and partition_id != current_partition_id:
            should_recommend_switch = True
            switch_detail = {
                "from_partition": current_partition_id,
                "to_partition": partition_id,
                "reason": "消息内容更适合另一个分区",
            }
        elif current_conversation_id and conversation_id != current_conversation_id and domain_name:
            # 同一分区，但对话不同（需有有效领域检测结果）
            should_recommend_switch = True
            switch_detail = {
                "from_conversation": current_conversation_id,
                "to_conversation": conversation_id,
                "reason": "消息内容属于不同专题",
            }

        return {
            "partition_id": partition_id,
            "conversation_id": conversation_id,
            "domain_name": domain_name,
            "topic_name": topic_name,
            "should_recommend_switch": should_recommend_switch,
            "switch_detail": switch_detail,
            "confidence": full.get("confidence", 0.0),
        }


# 全局单例
classifier = Classifier()
