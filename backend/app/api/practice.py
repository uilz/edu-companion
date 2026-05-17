"""
练习题 REST API 端点
管理练习题的获取、提交答案、错题分析
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.core.learner_model import learner_engine
from app.schemas.learner import (
    Difficulty,
    PracticeQuestion,
    PracticeResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/practice", tags=["练习"])


@router.get("/questions", response_model=list[PracticeQuestion])
async def get_questions(
    subject: Optional[str] = None,
    skill_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 5,
) -> list[PracticeQuestion]:
    """
    获取练习题列表

    支持按学科、知识点、难度筛选

    参数:
        subject: 学科（如"数学"、"语文"）
        skill_id: 知识点ID
        difficulty: 难度 (easy/medium/hard)
        limit: 返回数量限制

    返回:
        练习题列表
    """
    questions = learner_engine.get_questions(
        subject=subject,
        skill_id=skill_id,
        difficulty=difficulty,
        limit=limit,
    )
    return questions


@router.get("/questions/{question_id}", response_model=PracticeQuestion)
async def get_question(question_id: str) -> PracticeQuestion:
    """
    获取单个练习题详情

    参数:
        question_id: 题目ID

    返回:
        练习题详情
    """
    # 在题库中搜索
    for questions in learner_engine._question_bank.values():
        for q in questions:
            if q.question_id == question_id:
                return q

    raise HTTPException(status_code=404, detail=f"题目未找到: {question_id}")


@router.post("/submit", response_model=PracticeResult)
async def submit_answer(
    user_id: str,
    question_id: str,
    answer: str,
    time_spent: float = 0.0,
) -> PracticeResult:
    """
    提交练习答案

    系统会自动：
    1. 判断答案是否正确
    2. 使用BKT模型更新知识状态
    3. 返回详细的反馈信息

    参数:
        user_id: 用户ID
        question_id: 题目ID
        answer: 用户的答案
        time_spent: 花费时间（秒）

    返回:
        练习结果，包含正误判断和知识状态更新
    """
    result = learner_engine.submit_answer(
        user_id=user_id,
        question_id=question_id,
        answer=answer,
        time_spent=time_spent,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"题目未找到: {question_id}")

    return result


@router.get("/recommend/{user_id}", response_model=list[PracticeQuestion])
async def recommend_practice(
    user_id: str,
    limit: int = 5,
) -> list[PracticeQuestion]:
    """
    根据用户知识状态推荐练习题

    优先推荐用户薄弱的知识点相关的题目

    参数:
        user_id: 用户ID
        limit: 推荐数量

    返回:
        推荐的练习题列表
    """
    profile = learner_engine.get_or_create_profile(user_id)

    # 获取推荐知识点
    recommendations = learner_engine.bkt.recommend_practice(
        profile.knowledge_states, top_n=limit
    )

    if not recommendations:
        # 如果没有数据，返回一些通用练习题
        return learner_engine.get_questions(limit=limit)

    # 根据推荐的知识点获取练习题
    recommended_questions: list[PracticeQuestion] = []
    for rec in recommendations:
        skill_id = str(rec["skill_id"])
        questions = learner_engine.get_questions(skill_id=skill_id, limit=2)
        recommended_questions.extend(questions)

    # 去重
    seen_ids: set[str] = set()
    unique_questions: list[PracticeQuestion] = []
    for q in recommended_questions:
        if q.question_id not in seen_ids:
            seen_ids.add(q.question_id)
            unique_questions.append(q)

    return unique_questions[:limit]


@router.get("/skills/{user_id}")
async def get_skill_status(user_id: str) -> dict[str, Any]:
    """
    获取用户各知识点的状态

    参数:
        user_id: 用户ID

    返回:
        各知识点的掌握状态
    """
    profile = learner_engine.get_or_create_profile(user_id)

    skills: list[dict[str, Any]] = []
    for skill_id, state in profile.knowledge_states.items():
        level = learner_engine.bkt.get_mastery_level(state)
        predicted_correct = learner_engine.bkt.predict_correct_prob(state)
        skills.append({
            "skill_id": skill_id,
            "p_known": round(state.p_known, 4),
            "attempt_count": state.attempt_count,
            "correct_count": state.correct_count,
            "accuracy": round(state.accuracy, 4),
            "mastery_level": level,
            "predicted_correct_prob": round(predicted_correct, 4),
            "is_mastered": state.is_mastered,
        })

    # 按掌握程度排序（最弱的在前）
    skills.sort(key=lambda x: x["p_known"])

    return {
        "user_id": user_id,
        "total_skills": len(skills),
        "skills": skills,
    }
