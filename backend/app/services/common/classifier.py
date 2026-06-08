"""
分类服务 v2：关键词 + LLM 智能分类
降级策略：embedding (可选) > LLM 关键词提取 > 静态关键词匹配
"""

from __future__ import annotations

import logging

from app.services.common.embedding_utils import compute_embedding, cosine_similarity
from app.services.common import get_data_repo

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
    best = max(w for w, _ in matches)
    bonus = min(0.3, 0.1 * (len(matches) - 1))
    return min(1.0, best * 0.7 + bonus)


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
            "多元函数微分": {"多元函数": 0.85, "偏导数": 0.9, "全微分": 0.85, "方向导数": 0.8, "梯度": 0.8, "极值": 0.75},
            "重积分": {"重积分": 0.9, "二重积分": 0.9, "三重积分": 0.9, "极坐标": 0.75, "柱坐标": 0.75, "球坐标": 0.75},
            "曲线积分": {"曲线积分": 0.95, "第一类曲线积分": 0.9, "第二类曲线积分": 0.9, "格林公式": 0.85, "路径无关": 0.8, "曲线": 0.6},
            "曲面积分": {"曲面积分": 0.95, "第一类曲面积分": 0.9, "第二类曲面积分": 0.9, "高斯公式": 0.85, "斯托克斯": 0.8, "散度": 0.75, "旋度": 0.75},
            "无穷级数": {"无穷级数": 0.9, "收敛": 0.8, "发散": 0.8, "幂级数": 0.85, "傅里叶": 0.8, "交错级数": 0.8},
        },
        "代数": {"矩阵": 0.6, "行列式": 0.6, "方程": 0.55, "向量": 0.55},
        "几何": {"曲线": 0.7, "曲面": 0.7, "空间": 0.65},
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
    "大学物理": {
        "力学": {
            "牛顿力学": {"牛顿": 0.9, "力": 0.7, "加速度": 0.8, "运动": 0.7},
            "动量与能量": {"动量": 0.9, "能量": 0.85, "守恒": 0.8, "功": 0.75, "角动量": 0.8},
        },
        "电磁学": {
            "静电场": {"电场": 0.9, "电势": 0.85, "高斯": 0.8, "电容": 0.75},
            "磁场": {"磁场": 0.9, "安培": 0.8, "法拉第": 0.8, "电磁感应": 0.85},
            "电路": {"电路": 0.85, "电阻": 0.7, "电容": 0.7, "电感": 0.7, "交流": 0.65},
        },
        "热学": {
            "热力学": {"热力学": 0.9, "温度": 0.7, "熵": 0.8, "内能": 0.75, "卡诺": 0.8},
            "气体动理论": {"气体": 0.8, "分子": 0.7, "压强": 0.7, "自由度": 0.7},
        },
        "光学": {
            "波动光学": {"干涉": 0.9, "衍射": 0.9, "偏振": 0.85, "光栅": 0.8},
            "几何光学": {"透镜": 0.85, "折射": 0.8, "反射": 0.75},
        },
    },
    "程序设计": {
        "语言基础": {
            "Python基础": {"Python": 0.9, "列表": 0.75, "字典": 0.75, "函数": 0.7, "类": 0.7},
            "C语言基础": {"C语言": 0.9, "指针": 0.85, "数组": 0.75, "结构体": 0.8},
        },
        "数据结构": {
            "线性结构": {"数组": 0.8, "链表": 0.85, "栈": 0.85, "队列": 0.85},
            "树与图": {"树": 0.8, "二叉树": 0.85, "图": 0.8, "哈希": 0.8},
        },
        "算法": {
            "排序算法": {"排序": 0.9, "快排": 0.85, "归并": 0.8, "冒泡": 0.75},
            "搜索与遍历": {"搜索": 0.85, "DFS": 0.8, "BFS": 0.8, "二分": 0.8},
            "动态规划": {"动态规划": 0.95, "DP": 0.9, "背包": 0.8, "最优子结构": 0.8},
        },
    },
}


# ── 会话级关键词表（最细粒度，按 分区>领域>专题 组织）──
CONVERSATION_KEYWORDS: dict[str, dict[str, dict[str, dict[str, float]]]] = {
    "高等数学": {
        "分析": {
            "不定积分": {
                "换元积分法": {"换元": 0.9, "凑微分": 0.85, "三角换元": 0.85, "根式换元": 0.8},
                "分部积分法": {"分部积分": 0.95, "分部": 0.8, "tabular": 0.7},
                "有理函数积分": {"有理函数": 0.9, "部分分式": 0.85, "真分式": 0.8},
            },
            "定积分": {
                "定积分计算": {"定积分": 0.8, "牛顿莱布尼茨": 0.85, "换元": 0.7, "分部": 0.7},
                "广义积分": {"广义积分": 0.9, "反常积分": 0.9, "无穷限": 0.8, "瑕积分": 0.85},
                "定积分应用": {"面积": 0.8, "体积": 0.8, "弧长": 0.75, "旋转体": 0.8},
            },
            "曲线积分": {
                "第一类曲线积分": {"第一类": 0.9, "对弧长": 0.85, "标量": 0.7},
                "第二类曲线积分": {"第二类": 0.9, "对坐标": 0.85, "向量": 0.7},
                "格林公式": {"格林": 0.95, "格林公式": 0.95, "路径无关": 0.85, "保守场": 0.8},
            },
            "曲面积分": {
                "第一类曲面积分": {"第一类曲面": 0.9, "对面积": 0.85},
                "第二类曲面积分": {"第二类曲面": 0.9, "对坐标曲面": 0.85, "通量": 0.8},
                "高斯公式与斯托克斯": {"高斯": 0.9, "散度": 0.85, "斯托克斯": 0.9, "旋度": 0.85},
            },
            "无穷级数": {
                "数项级数": {"数项级数": 0.9, "收敛判别": 0.85, "比值": 0.75, "根值": 0.75, "莱布尼茨": 0.8},
                "幂级数": {"幂级数": 0.95, "收敛半径": 0.9, "收敛域": 0.85, "展开": 0.75},
                "傅里叶级数": {"傅里叶": 0.95, "三角级数": 0.8, "正交": 0.7},
            },
        },
    },
    "线性代数": {
        "特征理论": {
            "特征值与对角化": {
                "相似矩阵": {"相似": 0.9, "合同": 0.75, "等价": 0.7},
                "实对角化": {"实对称": 0.85, "正交": 0.8, "施密特": 0.8},
            },
        },
    },
    "概率论": {
        "随机变量": {
            "数字特征": {
                "条件期望": {"条件期望": 0.9, "条件方差": 0.85},
            },
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
        data = get_data_repo().load(user_id)

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
            logger.debug("文本 Embedding 计算失败", exc_info=True)
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
        data = get_data_repo().load(user_id)

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

        # Step 3.5: 会话级分类（更细粒度）
        conv_name: str | None = None
        conv_score = 0.0
        if topic_name and domain_name:
            conv_kws = CONVERSATION_KEYWORDS.get(partition_subject, {}).get(domain_name, {}).get(topic_name, {})
            for cname, kws in conv_kws.items():
                best = 0.0
                count = 0
                for kw, w in kws.items():
                    if kw in text:
                        best = max(best, w)
                        count += 1
                s = best * 0.7 + min(0.3, 0.1 * max(0, count - 1)) if count > 0 else 0.0
                if s > conv_score:
                    conv_score = s
                    conv_name = cname

            if conv_score < 0.3:
                conv_name = None

        # Step 4: 判断是否需要推荐切换
        is_switch = False
        if current_partition_id and partition_id != current_partition_id:
            is_switch = True

        return {
            "partition_id": partition_id,
            "domain_name": domain_name,
            "topic_name": topic_name,
            "conv_name": conv_name,
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
        from app.services.knowledge.tree_ops import tree_ops

        # 1. 分类
        full = self.classify_full(user_id, text, current_partition_id)

        partition_id = full["partition_id"]
        domain_name = full["domain_name"]
        topic_name = full["topic_name"]
        conv_name = full.get("conv_name")

        # 2. 如果无法归类 → 留在当前分区（不创建新分区）
        if not partition_id:
            if current_partition_id:
                partition_id = current_partition_id
                confidence = 0.3
            else:
                # 无当前分区且无法归类 → 自动创建
                partition = tree_ops.create_partition(user_id, text[:20], emoji="💬")
                partition_id = partition.id
                full = self.classify_full(user_id, text, partition_id)
                domain_name = full.get("domain_name")
                topic_name = full.get("topic_name")
                conv_name = full.get("conv_name")

        # 3. 判断是否推荐切换（在创建任何东西之前）
        should_recommend_switch = False
        switch_detail: dict = {}
        current_topic_id = ""
        data = get_data_repo().load(user_id)

        if current_conversation_id:
            for conv in data.conversations.values():
                if conv.id == current_conversation_id:
                    current_topic_id = conv.topic_id
                    break

        target_partition_exists = partition_id in data.partitions

        if current_partition_id and partition_id != current_partition_id:
            should_recommend_switch = True
            partition = data.partitions.get(partition_id)
            switch_detail = {
                "from_partition": current_partition_id,
                "to_partition": partition_id,
                "reason": "消息内容更适合另一个分区",
                "to_partition_name": partition.name if partition else "",
            }

        # 4. 如果是切换推荐且目标分区不存在 → 不创建，只返回推荐
        if should_recommend_switch and not target_partition_exists:
            partition_name = ""
            partition_emoji = ""
            if partition_id:
                p = data.partitions.get(partition_id)
                if p:
                    partition_name = p.name
                    partition_emoji = p.emoji

            path_parts = []
            if partition_name:
                path_parts.append(f"{partition_emoji} {partition_name}" if partition_emoji else partition_name)
            if domain_name:
                path_parts.append(domain_name)
            if topic_name:
                path_parts.append(topic_name)
            if conv_name:
                path_parts.append(conv_name)
            full_path = " > ".join(path_parts)

            return {
                "partition_id": current_partition_id,  # 保持当前分区
                "conversation_id": current_conversation_id,
                "domain_name": None,
                "topic_name": None,
                "conv_name": None,
                "partition_name": partition_name,
                "full_path": full_path,
                "should_recommend_switch": True,
                "switch_detail": switch_detail,
                "confidence": full.get("confidence", 0.0),
            }

        # 5. 目标分区存在 或 同分区 → 创建缺失层级，消息存到目标会话
        # 确保领域存在
        existing_domain = None
        for d in data.domains.values():
            if d.partition_id == partition_id and d.name == domain_name:
                existing_domain = d
                break

        if not existing_domain and domain_name:
            existing_domain = tree_ops.create_domain(user_id, partition_id, domain_name)

        domain_id = existing_domain.id if existing_domain else None

        # 确保专题存在
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

        # 确认活跃对话（含兜底）
        data = get_data_repo().load(user_id)
        conversation_id = ""
        if topic_id:
            topic = data.topics.get(topic_id)
            if topic and topic.active_conversation_id:
                conversation_id = topic.active_conversation_id
            # 兜底：active_conversation_id 为空时，查找 topic 下任意已有对话
            if not conversation_id and topic_id:
                for conv in data.conversations.values():
                    if conv.topic_id == topic_id and conv.is_active:
                        conversation_id = conv.id
                        break
            # 兜底：topic 下无任何对话，自动创建一个（使用 conv_name）
            if not conversation_id and topic_id:
                new_conv = tree_ops.create_conversation(user_id, topic_id, name=conv_name or "")
                conversation_id = new_conv.id

        # 检查同分区内专题切换
        if (current_conversation_id and conversation_id != current_conversation_id
              and domain_name and current_topic_id and current_topic_id != topic_id):
            should_recommend_switch = True
            switch_detail = {
                "from_conversation": current_conversation_id,
                "to_conversation": conversation_id,
                "reason": "消息内容属于不同专题",
            }

        # 获取 partition_name
        partition_name = ""
        partition_emoji = ""
        if partition_id:
            partition = data.partitions.get(partition_id)
            if partition:
                partition_name = partition.name
                partition_emoji = partition.emoji

        # 获取 domain/topic emoji
        domain_emoji = existing_domain.emoji if existing_domain else ""
        topic_emoji = existing_topic.emoji if existing_topic else ""

        # 构建带 emoji 的完整路径
        path_parts = []
        if partition_name:
            path_parts.append(f"{partition_emoji} {partition_name}" if partition_emoji else partition_name)
        if domain_name:
            path_parts.append(f"{domain_emoji} {domain_name}" if domain_emoji else domain_name)
        if topic_name:
            path_parts.append(f"{topic_emoji} {topic_name}" if topic_emoji else topic_name)
        if conv_name:
            path_parts.append(conv_name)
        full_path = " > ".join(path_parts)
        return {
            "partition_id": partition_id,
            "conversation_id": conversation_id,
            "domain_name": domain_name,
            "topic_name": topic_name,
            "conv_name": conv_name,
            "partition_name": partition_name,
            "full_path": full_path,
            "should_recommend_switch": should_recommend_switch,
            "switch_detail": switch_detail,
            "confidence": full.get("confidence", 0.0),
        }

# 全局单例
classifier = Classifier()
