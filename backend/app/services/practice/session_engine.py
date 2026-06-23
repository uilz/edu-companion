"""
SessionEngine — 纯评分逻辑和会话状态机

职责:
1. 判题逻辑 (_check_answer 等纯函数)
2. 会话状态转换验证 (status machine)
3. 统计计算 (不含 DB 读写)
4. 错因分析

不依赖 infrastructure/DB，可独立单元测试。
"""

from __future__ import annotations

import logging
from typing import Optional

from shared.utils import safe_json, safe_iso, safe_int

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# 会话状态机
# ═══════════════════════════════════════════

SESSION_STATE_TRANSITIONS = {
    "created": ["started", "cancelled"],
    "started": ["paused", "completed", "cancelled"],
    "paused": ["started", "cancelled"],
    "completed": [],
    "cancelled": [],
}


def validate_transition(current_status: str, target_status: str) -> bool:
    """验证会话状态转换是否合法"""
    allowed = SESSION_STATE_TRANSITIONS.get(current_status, [])
    return target_status in allowed


# ═══════════════════════════════════════════
# 判题引擎
# ═══════════════════════════════════════════

def check_answer(
    user_answer: Optional[list],
    correct_answer: list,
    question_type: str,
) -> bool:
    """纯判题逻辑（无 DB/I/O 依赖）"""
    if not user_answer:
        return False

    # 选择题 / 判断题：精确集合匹配（选项字母）
    if question_type in ("single", "multiple", "judge", "choice"):
        user_set = set(str(a).strip().upper() for a in user_answer if a)
        correct_set = set(str(a).strip().upper() for a in correct_answer if a)
        if not user_set and not correct_set:
            return True
        if not user_set or not correct_set:
            return False
        return user_set == correct_set

    # 填空题：去除首尾空格后精确匹配（不区分大小写）
    if question_type == "fill":
        user_text = str(user_answer[0]).strip() if user_answer else ""
        correct_text = str(correct_answer[0]).strip() if correct_answer else ""
        return user_text.upper() == correct_text.upper()

    # 简答题 / free_form / essay：关键词包含匹配
    # 如果参考答案为空，则标记为正确（待人工批阅）
    if question_type in ("free_form", "essay"):
        if not correct_answer or not any(a and str(a).strip() for a in correct_answer):
            return True  # 无标准答案，默认通过（待人工批阅）
        user_text = str(user_answer[0]).strip().lower() if user_answer else ""
        # 检查用户答案是否包含参考答案中的关键词
        for ref in correct_answer:
            ref_text = str(ref).strip().lower()
            if ref_text and ref_text in user_text:
                return True
        return False

    # 兜底：精确匹配
    user_set = set(str(a).strip().upper() for a in user_answer if a)
    correct_set = set(str(a).strip().upper() for a in correct_answer if a)
    return user_set == correct_set


# ═══════════════════════════════════════════
# 统计计算（纯函数）
# ═══════════════════════════════════════════

def compute_stats(total: int, correct: int) -> dict:
    """根据答题记录计算统计数据（纯计算）"""
    wrong = total - correct
    score = round((correct / max(total, 1)) * 100, 1)
    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "score": score,
    }


# ═══════════════════════════════════════════
# 错因分类
# ═══════════════════════════════════════════

ERROR_CATEGORIES = [
    "概念混淆",      # 对知识点理解错误
    "计算失误",      # 计算过程出错（如加减乘除、代入错误）
    "审题不清",      # 未正确理解题目要求
    "公式记错",      # 公式/定理记忆错误
    "逻辑推理错误",  # 推理过程出问题
    "粗心大意",      # 非知识性错误（如笔误、看错数）
    "缺少思路",      # 完全不知道如何下手
    "时间不足",      # 时间压力导致错误
    "其他",          # 无法归类的错误
]


def classify_error(question_data: dict, user_answer: Optional[list]) -> Optional[str]:
    """基于题目类型和用户回答的简单错因分类（纯函数）"""
    if not user_answer:
        return "缺少思路"
    q_type = question_data.get("question_type", "")
    if q_type in ("fill", "calculation"):
        return "计算失误"
    if question_data.get("difficulty", 3) >= 4:
        return "概念混淆"
    return None


# ═══════════════════════════════════════════
# 数据安全转换（纯函数）
# ═══════════════════════════════════════════





