"""
对话上下文 → 智能练习选题
ContextAwarePracticeTrigger

从对话branch中提取：
1. 知识主题 → 匹配 skill_id
2. Bloom层次 → 决定考察深度
3. 困惑信号 → 调整难度/题型
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.schemas.conversation import Branch, TreeNode
from app.schemas.practice import BloomLevel, PracticeSession, CreateSessionRequest
from app.services.shared_ks import shared_ks
from app.services.question_generator import get_question_generator

logger = logging.getLogger(__name__)

# Bloom层次推断规则：用户语言模式 → 认知层次
BLOOM_PATTERNS: list[tuple[str, BloomLevel]] = [
    (r"证明|推导|论证", BloomLevel.EVALUATE),
    (r"区别|对比|比较|有什么不同|区别是", BloomLevel.ANALYZE),
    (r"怎么做|步骤|解法|算一下|求解|解题", BloomLevel.APPLY),
    (r"为什么|解释|原理|含义|是什么", BloomLevel.UNDERSTAND),
    (r"定义|概念|什么是|叫什么", BloomLevel.REMEMBER),
]

# 困惑信号：检测到 → 降低难度或改变策略
CONFUSION_PATTERNS = [
    r"不太?懂", r"不明白", r"有点绕", r"没听懂",
    r"再说一遍", r"什么是", r"还是不会", r"完全不知道",
    r"好难", r"懵", r"晕", r"记不住",
]

# 对话→练习模式映射
CONVERSATION_MODE_MAP = {
    "question_asked": "contextual",      # 学生主动提问后练习
    "explanation_given": "targeted",     # 学生解释后针对性练习
    "concept_discussed": "adaptive",     # 深度讨论后自适应
}


class ContextAwarePracticeTrigger:
    """
    从对话上下文智能触发练习
    
    核心流程：
    1. 提取最近对话主题 → 匹配知识点
    2. 推断Bloom层次（用户在问什么层级的问题）
    3. 检测困惑信号（是否需要降低难度）
    4. 查MDKS获取当前掌握度
    5. 生成contextual练习session
    """

    # 对话中不同交互类型对应的练习模式
    MODE_MAP = CONVERSATION_MODE_MAP

    def infer_skills_from_context(
        self, recent_texts: list[str], subject_hint: str = ""
    ) -> list[str]:
        """
        从最近对话文本推断应该练习的知识点
        
        方案：基于关键词+主题映射，不依赖外部API。
        MVP阶段用简单的关键词检测，后续接入Embedding搜索。
        """
        # 合并最近消息文本
        combined = " ".join(recent_texts).lower()

        # 学科→知识点关键词映射（MVP硬编码，后续数据驱动）
        SUBJECT_SKILLS: dict[str, dict[str, str]] = {
            "数学": {
                "极限": "calculus_limit",
                "连续": "calculus_continuity",
                "导数": "calculus_derivative",
                "微分": "calculus_differential",
                "积分": "calculus_integral",
                "级数": "calculus_series",
                "函数": "calculus_function",
                "切线": "calculus_derivative",
                "斜率": "calculus_derivative",
                "极值": "calculus_derivative",
                "最值": "calculus_derivative",
                "渐近线": "calculus_limit",
            },
            "物理": {
                "力学": "physics_mechanics",
                "牛顿": "physics_newton",
                "电磁": "physics_electromagnetism",
                "热力学": "physics_thermodynamics",
                "量子": "physics_quantum",
                "波动": "physics_waves",
            },
            "线代": {
                "矩阵": "linear_matrix",
                "行列式": "linear_determinant",
                "向量": "linear_vector",
                "特征值": "linear_eigenvalue",
                "线性": "linear_transform",
            },
            "英语": {
                "单词": "english_vocabulary",
                "语法": "english_grammar",
                "阅读": "english_reading",
                "写作": "english_writing",
            },
        }

        # 匹配主题
        detected_skills: list[str] = []
        for subject, skills in SUBJECT_SKILLS.items():
            for keyword, skill_id in skills.items():
                if keyword in combined and skill_id not in detected_skills:
                    detected_skills.append(skill_id)

        # 如果没有匹配到任何知识点，返回通用标识
        if not detected_skills:
            detected_skills = [subject_hint or "general_practice"]

        logger.info(
            "从对话上下文推断知识点: %s (来源文本前50字: '%s')",
            detected_skills, combined[:50]
        )
        return detected_skills[:3]  # 最多3个

    def infer_bloom_level(
        self, recent_texts: list[str]
    ) -> tuple[BloomLevel, str]:
        """
        从对话文本推断当前应该练习的Bloom层次
        
        返回: (BloomLevel, 推断原因)
        """
        combined = " ".join(recent_texts).lower()

        for pattern, level in BLOOM_PATTERNS:
            if re.search(pattern, combined):
                return level, f"匹配到关键词模式: '{pattern}'"

        # 默认：如果用户没说具体操作，就是理解层次
        return BloomLevel.UNDERSTAND, "默认（无特定操作模式）"

    def detect_confusion(self, recent_texts: list[str]) -> bool:
        """检测对话中是否有困惑信号"""
        combined = " ".join(recent_texts).lower()
        for pattern in CONFUSION_PATTERNS:
            if re.search(pattern, combined):
                logger.info("检测到困惑信号: '%s'", pattern)
                return True
        return False

    def compute_target_difficulty(
        self, skill_ids: list[str], user_id: str
    ) -> float:
        """
        根据MDKS当前掌握度计算ZPD目标难度
        
        ZPD甜蜜点：p_known在0.3-0.7之间效果最好
        目标难度 = 1.0 - p_known 但不过极值
        """
        if not skill_ids:
            return 0.5

        # 取所有知识点的平均掌握度
        p_values = []
        for sid in skill_ids:
            try:
                state = shared_ks.get_state(user_id, sid)
                p_values.append(state.p_known)
            except Exception:
                p_values.append(0.3)  # 默认偏难（需要练习）

        avg_p = sum(p_values) / len(p_values)

        # ZPD难度映射：
        # p_known < 0.3 → difficulty 0.6 (偏简单但要挑战)
        # p_known 0.3-0.5 → difficulty 0.5 (中等)
        # p_known 0.5-0.7 → difficulty 0.4 (适中偏难)
        # p_known > 0.7 → difficulty 0.3 (挑战)
        if avg_p < 0.3:
            return 0.65
        elif avg_p < 0.5:
            return 0.55
        elif avg_p < 0.7:
            return 0.45
        else:
            return 0.35

    def trigger(
        self,
        user_id: str,
        branch: Branch,
        recent_messages: list[TreeNode],
        subject_hint: str = "",
        count: int = 3,
    ) -> dict:
        """
        主入口：基于对话上下文触发练习
        
        返回:
            dict with skill_ids, bloom_level, difficulty, confusion, mode
            可直接传给练习API创建session
        """
        # 1. 提取最近文本
        recent_texts = [
            msg.text_summary or " ".join(
                b.text if hasattr(b, "text") else ""
                for b in msg.content_blocks if hasattr(b, "text")
            )
            for msg in recent_messages[-5:]
            if msg.role in ("user", "assistant")
        ]

        if not recent_texts:
            # 无对话上下文，返回默认
            return {
                "skill_ids": ["general_practice"],
                "bloom_level": BloomLevel.UNDERSTAND,
                "difficulty": 0.5,
                "confused": False,
                "mode": "adaptive",
            }

        # 2. 推断知识点
        skill_ids = self.infer_skills_from_context(recent_texts, subject_hint)

        # 3. 推断Bloom层次
        bloom_level, bloom_reason = self.infer_bloom_level(recent_texts)

        # 4. 检测困惑
        confused = self.detect_confusion(recent_texts)
        if confused:
            # 困惑 → 降低Bloom层次到理解，降低难度
            bloom_level = BloomLevel.UNDERSTAND
            logger.info("困惑检测：降低Bloom层次到UNDERSTAND")

        # 5. 计算目标难度
        difficulty = self.compute_target_difficulty(skill_ids, user_id)

        result = {
            "skill_ids": skill_ids,
            "bloom_level": bloom_level,
            "difficulty": difficulty,
            "confused": confused,
            "mode": "contextual",
            "bloom_reason": bloom_reason,
        }

        logger.info(
            "ContextAwarePracticeTrigger: skills=%s bloom=%s diff=%.2f confused=%s",
            skill_ids, bloom_level, difficulty, confused,
        )
        return result


# 全局实例
context_trigger = ContextAwarePracticeTrigger()
