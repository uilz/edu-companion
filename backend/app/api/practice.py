"""
练习系统API v2.0
端点：题目生成、会话管理、答题提交、统计查询
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.knowledge_trace import bkt_engine
from app.schemas.practice import (
    AnswerType,
    AttemptRecord,
    BloomLevel,
    CoverageGap,
    DailyStat,
    ErrorAnalysis,
    ErrorBookEntry,
    ErrorType,
    Material,
    MaterialChunk,
    PracticeSession,
    PracticeStats,
    PracticeSessionPlan,
    Question,
    QuestionOption,
    ReviewTask,
    SessionStatus,
    SkillStat,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice"])

# ── 内存存储（MVP，后续迁移PostgreSQL）──

_question_bank: dict[str, list[Question]] = {}  # skill_id → questions
_sessions: dict[str, PracticeSession] = {}       # session_id → session
_error_book: dict[str, list[ErrorBookEntry]] = {} # user_id → entries
_materials: dict[str, list[Material]] = {}        # user_id → materials
_material_chunks: dict[str, list[MaterialChunk]] = {}  # material_id → chunks


# ──────────────────────────────────────────────
# 请求/响应模型
# ──────────────────────────────────────────────

class GenerateQuestionRequest(BaseModel):
    subject: str = "数学"
    skill_id: str = ""
    bloom_level: BloomLevel = BloomLevel.UNDERSTAND
    difficulty: float = 0.5
    count: int = 5
    content_type: str = "choice"
    material_ids: Optional[list[str]] = None  # 从用户资料生成


class CreateSessionRequest(BaseModel):
    subject: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    duration_minutes: int = 30
    mode: str = "adaptive"  # adaptive/targeted/review/challenge/contextual


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    time_spent_seconds: float = 0.0
    hints_used: int = 0
    explanation_text: Optional[str] = None


class HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


# ──────────────────────────────────────────────
# 题目管理
# ──────────────────────────────────────────────

from app.services.question_generator import get_question_generator, QuestionGenerator


def _generate_questions(
    generator: QuestionGenerator,
    skill_id: str,
    subject: str,
    bloom_level: BloomLevel,
    difficulty: float,
    count: int,
) -> list[Question]:
    """使用LLM生成题目"""
    return generator.generate(
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type="choice",
    )


@router.post("/questions/generate")
async def generate_questions(req: GenerateQuestionRequest):
    """生成练习题（使用LLM）"""
    from app.services.llm_service import LLMService
    llm_service = LLMService()
    generator = get_question_generator(llm_service)
    
    questions = _generate_questions(
        generator,
        skill_id=req.skill_id,
        subject=req.subject,
        bloom_level=req.bloom_level,
        difficulty=req.difficulty,
        count=req.count,
    )

    # 存入题库
    if req.skill_id not in _question_bank:
        _question_bank[req.skill_id] = []
    _question_bank[req.skill_id].extend(questions)

    return {
        "questions": [q.model_dump() for q in questions],
        "count": len(questions),
    }


@router.get("/questions")
async def get_questions(
    subject: Optional[str] = None,
    skill_id: Optional[str] = None,
    bloom_level: Optional[BloomLevel] = None,
    limit: int = 20,
):
    """获取题目列表"""
    all_questions = []
    for skill_questions in _question_bank.values():
        all_questions.extend(skill_questions)

    if subject:
        all_questions = [q for q in all_questions if q.subject == subject]
    if skill_id:
        all_questions = [q for q in all_questions if q.skill_id == skill_id]
    if bloom_level:
        all_questions = [q for q in all_questions if q.bloom_level == bloom_level]

    return {
        "questions": [q.model_dump() for q in all_questions[:limit]],
        "total": len(all_questions),
    }


# ──────────────────────────────────────────────
# 练习会话
# ──────────────────────────────────────────────

@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """创建练习会话"""
    user_id = "default_user"  # MVP单用户

    # 确定练习的知识点
    skill_ids = req.skill_ids or []
    if not skill_ids:
        # 自动选择：从题库中选有题的知识点
        skill_ids = [s for s, qs in _question_bank.items() if qs][:4]

    # 选题
    questions = []
    for skill_id in skill_ids:
        pool = _question_bank.get(skill_id, [])
        if pool:
            # 简单选题：按难度匹配
            target_diff = 0.5  # MVP默认
            sorted_q = sorted(pool, key=lambda q: abs(q.difficulty - target_diff))
            questions.extend(sorted_q[:3])

    session = PracticeSession(
        user_id=user_id,
        planned_skills=skill_ids,
        estimated_minutes=req.duration_minutes,
        mode=req.mode,
        question_ids=[q.question_id for q in questions],
    )

    _sessions[session.session_id] = session

    return {
        "session": session.model_dump(),
        "questions": [q.model_dump() for q in questions],
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session": session.model_dump()}


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str, partition_id: str | None = None, branch_id: str | None = None):
    """结束会话（可选：写入对话branch）"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = SessionStatus.COMPLETED
    session.completed_at = datetime.now()

    # P1: 练习结果写入对话记忆
    result = {"session": session.model_dump()}
    if partition_id and branch_id:
        try:
            from app.services.practice_integrator import integrate_practice_to_branch
            node = await integrate_practice_to_branch(
                "default_user", session, partition_id, branch_id,
            )
            if node:
                result["branch_node"] = node.model_dump()
        except Exception as e:
            logger.warning(f"练习结果写入branch失败: {e}")

    # P2: 练习错误→自动推荐媒体搜索
    media_recommend = None
    try:
        from app.services.dialogue_recommender import practice_to_dialogue
        rec = practice_to_dialogue.should_recommend_media(session)
        if rec:
            from app.services.media_search import media_search
            platforms_result = await media_search.recommend_for_error(
                error_skill=rec[1],
                error_type=(
                    session.attempts[-1].error_analysis.error_type.value
                    if session.attempts and session.attempts[-1].error_analysis
                    else ""
                ),
            )
            media_recommend = {
                "message": rec[0],
                "platforms": platforms_result,
            }
    except Exception as e:
        logger.warning(f"媒体推荐生成失败: {e}")

    result.update({
        "accuracy": session.accuracy,
        "total_questions": session.total_questions,
        "correct_count": session.correct_count,
        "struggling_skills": session.struggling_skills,
        "media_recommend": media_recommend,
    })
    return result


# ──────────────────────────────────────────────
# 答题与反馈
# ──────────────────────────────────────────────

@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest):
    """提交答案"""
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 查找题目
    question = None
    for pool in _question_bank.values():
        for q in pool:
            if q.question_id == req.question_id:
                question = q
                break
        if question:
            break

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 判对错
    is_correct = req.answer.strip().upper() == question.correct_answer.strip().upper()

    # 创建答题记录
    attempt = AttemptRecord(
        user_id=session.user_id,
        question_id=req.question_id,
        session_id=req.session_id,
        user_answer=req.answer,
        is_correct=is_correct,
        time_spent_seconds=req.time_spent_seconds,
        hints_used=req.hints_used,
        explanation_text=req.explanation_text,
    )

    # 更新知识状态
    state = bkt_engine.load_or_create(session.user_id, question.skill_id)
    updated_state = bkt_engine.update(
        state, is_correct,
        hint_level=req.hints_used,
        explanation_score=None,  # 需要LLM评分，MVP先跳过
    )
    bkt_engine.save_state(session.user_id, updated_state)  # 持久化

    attempt.knowledge_before = {question.skill_id: state.p_known}
    attempt.knowledge_after = {question.skill_id: updated_state.p_known}

    # 更新会话
    session.attempts.append(attempt)
    if is_correct:
        session.correct_count += 1

    # 生成反馈
    feedback = {
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "knowledge_update": {
            "skill_id": question.skill_id,
            "p_known_before": state.p_known,
            "p_known_after": updated_state.p_known,
            "mastery_level": bkt_engine.get_mastery_level(updated_state),
        },
    }

    # 错误时添加错因分析
    if not is_correct and question.options:
        chosen = next((o for o in question.options if o.letter.upper() == req.answer.upper()), None)
        if chosen and chosen.distractor_type:
            feedback["error_analysis"] = {
                "type": "misconception",
                "distractor_type": chosen.distractor_type,
                "suggestion": f"你选择了{chosen.letter}，可能的原因是{chosen.distractor_type}",
            }

    # 情感反馈
    recent = session.last_n_results(5)
    consecutive_wrong = sum(1 for a in reversed(recent) if not a.is_correct)
    if consecutive_wrong >= 3:
        feedback["emotional_feedback"] = "别着急，困难的知识点需要多花时间。要不要先看看相关视频讲解？🎬"
    elif consecutive_wrong >= 2:
        feedback["emotional_feedback"] = "这个知识点确实有点难，我们一步步来 🤝"

    return feedback


@router.post("/hint")
async def get_hint(req: HintRequest):
    """获取提示"""
    # 查找题目
    question = None
    for pool in _question_bank.values():
        for q in pool:
            if q.question_id == req.question_id:
                question = q
                break
        if question:
            break

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    level = req.current_level + 1
    hints = question.hints or []

    if level == 0:
        text = "试着自己想想看 💪"
        hint_type = "encouragement"
    elif level <= len(hints):
        text = hints[level - 1]
        hint_type = "direction"
    else:
        text = question.explanation
        hint_type = "full"

    return {
        "hint": {"level": level, "text": text, "type": hint_type},
        "next_level_available": level < 4,
    }


# ──────────────────────────────────────────────
# 错题本（增强）
# ──────────────────────────────────────────────

@router.get("/errors")
async def get_error_book(
    resolved: Optional[bool] = None,
    skill_id: Optional[str] = None,
    limit: int = 20,
):
    """获取错题本"""
    user_id = "default_user"
    entries = _error_book.get(user_id, [])

    if resolved is not None:
        entries = [e for e in entries if e.is_resolved == resolved]
    if skill_id:
        entries = [e for e in entries if e.skill_id == skill_id]

    entries.sort(key=lambda e: e.created_at, reverse=True)

    return {
        "entries": [e.model_dump() for e in entries[:limit]],
        "total": len(entries),
        "unresolved_count": sum(1 for e in _error_book.get(user_id, []) if not e.is_resolved),
    }


@router.post("/errors/{entry_id}/review")
async def review_error(entry_id: str, is_correct: bool = True):
    """复习错题（标记已解决/更新间隔）"""
    user_id = "default_user"
    entries = _error_book.get(user_id, [])
    
    entry = next((e for e in entries if e.entry_id == entry_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Error entry not found")
    
    entry.review_count += 1
    entry.is_resolved = is_correct
    
    if is_correct:
        entry.next_review = datetime.now().__class__.now()  # 不再需要复习
    else:
        # SM-2: 间隔翻倍
        interval = min(entry.review_count * 3 + 1, 60)
        entry.next_review = datetime.now().__class__.now()
    
    return {
        "entry": entry.model_dump(),
        "review_count": entry.review_count,
        "is_resolved": entry.is_resolved,
    }


@router.get("/errors/due")
async def get_due_errors():
    """获取待复习的错题"""
    user_id = "default_user"
    now = datetime.now()
    entries = _error_book.get(user_id, [])
    
    due = [e for e in entries if not e.is_resolved and e.next_review <= now]
    due.sort(key=lambda e: e.created_at)
    
    return {
        "due": [e.model_dump() for e in due[:10]],
        "total_due": len(due),
    }


# ──────────────────────────────────────────────
# 统计（增强）
# ──────────────────────────────────────────────

@router.get("/stats")
async def get_stats(time_range: str = "week"):
    """获取练习统计（增强：含错因分布、环比、知识掌握度）"""
    from datetime import datetime, timedelta

    user_id = "default_user"
    now = datetime.now()

    # 时间窗口
    if time_range == "week":
        days_back = 7
        prev_days_back = 14
    elif time_range == "month":
        days_back = 30
        prev_days_back = 60
    else:  # all
        days_back = 365
        prev_days_back = 730

    cutoff = now - timedelta(days=days_back)
    prev_cutoff_start = now - timedelta(days=prev_days_back)
    prev_cutoff_end = now - timedelta(days=days_back)

    # ── 当期数据 ──
    current_sessions = [
        s for s in _sessions.values()
        if s.user_id == user_id and s.started_at >= cutoff
    ]
    all_attempts = []
    for s in current_sessions:
        all_attempts.extend(s.attempts)

    total = len(all_attempts)
    correct = sum(1 for a in all_attempts if a.is_correct)
    accuracy = correct / total if total > 0 else 0.0
    study_minutes = sum(s.duration_minutes for s in current_sessions)
    study_days = len(set(s.started_at.strftime("%Y-%m-%d") for s in current_sessions))

    # ── 环比数据（上一周期） ──
    prev_sessions = [
        s for s in _sessions.values()
        if s.user_id == user_id
        and prev_cutoff_start <= s.started_at < prev_cutoff_end
    ]
    prev_attempts = []
    for s in prev_sessions:
        prev_attempts.extend(s.attempts)
    prev_total = len(prev_attempts)
    prev_correct = sum(1 for a in prev_attempts if a.is_correct)
    prev_accuracy = prev_correct / prev_total if prev_total > 0 else 0.0
    prev_minutes = sum(s.duration_minutes for s in prev_sessions)
    prev_days = len(set(s.started_at.strftime("%Y-%m-%d") for s in prev_sessions))

    # ── 错因分布 ──
    error_dist: dict[str, int] = {}
    for a in all_attempts:
        if not a.is_correct and a.error_analysis:
            etype = a.error_analysis.error_type.value
            error_dist[etype] = error_dist.get(etype, 0) + 1

    # ── 知识掌握度（从持久化状态读取） ──
    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = []
    for skill_id, state in skill_states.items():
        if state.attempt_count > 0:
            mastery_bars.append({
                "skill_id": skill_id,
                "p_known": round(state.p_known, 2),
                "mastery_level": bkt_engine.get_mastery_level(state),
                "attempt_count": state.attempt_count,
                "correct_count": state.correct_count,
            })
    mastery_bars.sort(key=lambda x: x["p_known"])  # 低→高

    # ── 每日趋势 ──
    daily_trend: list[dict] = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_attempts = [
            a for a in all_attempts
            if a.submitted_at.strftime("%Y-%m-%d") == day
        ]
        day_total = len(day_attempts)
        day_correct = sum(1 for a in day_attempts if a.is_correct)
        daily_trend.append({
            "date": day[-5:],  # MM-DD
            "questions": day_total,
            "correct": day_correct,
            "accuracy": round(day_correct / day_total, 2) if day_total > 0 else 0.0,
        })

    # ── 时段热力图 ──
    hourly_heatmap: list[dict] = []
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for day_idx in range(7):
        for hour in [8, 10, 14, 16, 20, 22]:
            count = sum(
                1 for a in all_attempts
                if a.submitted_at.weekday() == day_idx
                and a.submitted_at.hour == hour
            )
            hourly_heatmap.append({
                "day": day_idx + 1,
                "day_name": day_names[day_idx],
                "hour": hour,
                "questions": count,
            })

    return {
        "user_id": user_id,
        "time_range": time_range,
        "overview": {
            "total_questions": total,
            "accuracy": round(accuracy, 2),
            "study_days": study_days,
            "study_minutes": round(study_minutes, 1),
            "prev_week": {
                "total_questions": prev_total,
                "accuracy": round(prev_accuracy, 2),
                "study_days": prev_days,
                "study_minutes": round(prev_minutes, 1),
            },
        },
        "daily_trend": daily_trend,
        "mastery_bars": mastery_bars,
        "error_distribution": [
            {"type": etype, "count": cnt, "pct": round(cnt / sum(error_dist.values()), 2)}
            for etype, cnt in sorted(error_dist.items(), key=lambda x: -x[1])
        ],
        "hourly_heatmap": hourly_heatmap,
    }


# ──────────────────────────────────────────────
# 对话×练习 P2: 上下文触发 + 内联练习 + 练习回顾
# ──────────────────────────────────────────────

class ContextTriggerRequest(BaseModel):
    target_branch_id: str = ""       # 目标branch ID（空=当前活跃）
    subject_hint: str = ""           # 学科提示
    count: int = 3                   # 生成题数


class InlineAnswerRequest(BaseModel):
    block_id: str                    # 练习块的block_id
    answer: str                      # 学生答案
    explanation_text: str = ""       # 可选解释文本


class InlineHintRequest(BaseModel):
    block_id: str


class DialogueRecommendRequest(BaseModel):
    session_id: str


@router.post("/context-trigger")
async def trigger_from_context(req: ContextTriggerRequest):
    """
    从对话上下文触发练习：分析当前branch → 推断知识点+难度+Bloom → 创建session
    """
    from app.services.context_trigger import context_trigger
    from app.services.storage import storage

    data = storage.load(user_id)
    branch = None
    recent_messages = []

    if req.target_branch_id:
        branch = data.branches.get(req.target_branch_id)
    else:
        # 找第一个活跃分区
        for pid, partition in data.partitions.items():
            branch = data.branches.get(partition.active_branch_id)
            if branch:
                break

    if branch:
        for nid in branch.path[-5:]:
            node = data.nodes.get(nid)
            if node and not node.is_deleted:
                recent_messages.append(node)

    result = context_trigger.trigger(
        user_id=user_id,
        branch=branch,
        recent_messages=recent_messages,
        subject_hint=req.subject_hint,
        count=req.count,
    )
    return result


@router.post("/inline/create")
async def create_inline(req: ContextTriggerRequest):
    """
    创建内联练习：生成练习题作为 ResponseBlock
    """
    from app.services.inline_practice import inline_practice
    from app.services.context_trigger import context_trigger
    from app.services.storage import storage

    data = storage.load(user_id)
    branch = None
    recent_messages = []

    if req.target_branch_id:
        branch = data.branches.get(req.target_branch_id)
    else:
        for pid, partition in data.partitions.items():
            branch = data.branches.get(partition.active_branch_id)
            if branch:
                break

    if branch:
        for nid in branch.path[-5:]:
            node = data.nodes.get(nid)
            if node and not node.is_deleted:
                recent_messages.append(node)

    # 从对话推断选题
    ctx = context_trigger.trigger(
        user_id=user_id,
        branch=branch,
        recent_messages=recent_messages,
        subject_hint=req.subject_hint,
        count=req.count,
    )

    blocks = inline_practice.create_inline_question(
        user_id=user_id,
        skill_id=ctx.get("skill_ids", ["calculus_derivative"])[0],
        bloom_level=ctx.get("bloom_level", "understand"),
        difficulty=ctx.get("difficulty", 0.5),
        count=req.count,
    )

    return {"blocks": [b.model_dump() for b in blocks]}


@router.post("/inline/answer")
async def submit_inline_answer(req: InlineAnswerRequest):
    """
    提交内联练习答案
    """
    from app.services.inline_practice import inline_practice
    result = inline_practice.handle_answer(
        block_id=req.block_id,
        student_answer=req.answer,
        explanation_text=req.explanation_text or None,
    )
    return result


@router.post("/inline/hint")
async def get_inline_hint(req: InlineHintRequest):
    """
    获取内联练习下一级提示
    """
    from app.services.inline_practice import inline_practice
    return inline_practice.get_hint(req.block_id)


@router.get("/recall")
async def recall_practice(subject: str = "", days: int = 7):
    """
    练习回顾：生成自然语言练习总结
    """
    from app.services.practice_recall import practice_recall

    sessions = list(_sessions.values())
    result = practice_recall.generate_recall(
        sessions=sessions,
        days=days,
        subject_filter=subject or None,
    )
    return {"recall": result}


@router.post("/dialogue-recommend")
async def recommend_dialogue(req: DialogueRecommendRequest):
    """
    练习后推荐深度对话
    """
    from app.services.dialogue_recommender import practice_to_dialogue

    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    latest_error = None
    if session.attempts:
        last_attempt = session.attempts[-1]
        if not last_attempt.is_correct:
            latest_error = last_attempt.error_analysis

    recommendation = practice_to_dialogue.should_recommend(
        session=session,
        latest_error=latest_error,
    )

    return {"recommend": recommendation}


# ──────────────────────────────────────────────
# 学习行为分析 + 习惯养成
# ──────────────────────────────────────────────

@router.get("/behavior")
async def get_behavior_report(time_range: str = "week"):
    """
    学习行为分析报告：
    - 连续学习天数 (streak)
    - 最佳学习时段
    - 学习规律性评分
    - 疲劳曲线
    - 每日目标完成情况
    - 微习惯推荐
    - 番茄钟建议
    - 个性化行动建议
    """
    from datetime import datetime, timedelta
    from app.services.behavior_analyzer import behavior_analyzer
    from app.services.habit_formation import habit_formation

    user_id = "default_user"
    now = datetime.now()

    days_back = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
    cutoff = now - timedelta(days=days_back)

    # 汇集当期数据
    current_sessions = [
        s for s in _sessions.values()
        if s.user_id == user_id and s.started_at >= cutoff
    ]
    all_attempts = []
    for s in current_sessions:
        all_attempts.extend(s.attempts)

    # 今日数据
    today_str = now.strftime("%Y-%m-%d")
    today_attempts = [
        a for a in all_attempts
        if a.submitted_at.strftime("%Y-%m-%d") == today_str
    ]
    today_questions = len(today_attempts)
    today_correct = sum(1 for a in today_attempts if a.is_correct)
    today_accuracy = today_correct / today_questions if today_questions > 0 else 0.0

    # 构建分析器需要的输入
    daily_trend = []
    for i in range(days_back - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_attempts = [a for a in all_attempts if a.submitted_at.strftime("%Y-%m-%d") == day]
        daily_trend.append({
            "date": day[-5:],
            "questions": len(day_attempts),
            "correct": sum(1 for a in day_attempts if a.is_correct),
            "accuracy": sum(1 for a in day_attempts if a.is_correct) / max(len(day_attempts), 1),
        })

    hourly_heatmap = []
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for day_idx in range(7):
        for hour in [8, 10, 14, 16, 20, 22]:
            count = sum(
                1 for a in all_attempts
                if a.submitted_at.weekday() == day_idx and a.submitted_at.hour == hour
            )
            hourly_heatmap.append({
                "day": day_idx + 1, "day_name": day_names[day_idx],
                "hour": hour, "questions": count,
            })

    skill_states = bkt_engine.load_all_states(user_id)
    mastery_bars = [
        {
            "skill_id": sid, "p_known": round(s.p_known, 2),
            "mastery_level": bkt_engine.get_mastery_level(s),
            "attempt_count": s.attempt_count, "correct_count": s.correct_count,
        }
        for sid, s in skill_states.items() if s.attempt_count > 0
    ]
    mastery_bars.sort(key=lambda x: x["p_known"])

    total_sessions = len(current_sessions)
    total_minutes = sum(s.duration_minutes for s in current_sessions)
    study_days = len(set(s.started_at.strftime("%Y-%m-%d") for s in current_sessions))

    # 行为分析
    report = behavior_analyzer.analyze(
        daily_trend=daily_trend,
        hourly_heatmap=hourly_heatmap,
        mastery_bars=mastery_bars,
        total_sessions=total_sessions,
        total_minutes=total_minutes,
    )

    # 习惯养成
    goal = habit_formation.check_daily_goal(
        today_questions=today_questions,
        today_correct=today_correct,
        today_accuracy=today_accuracy,
        current_streak=report.current_streak,
        total_questions=len(all_attempts),
        study_days=study_days,
    )
    tiny_habits = habit_formation.get_tiny_habits(report.current_streak)
    pomodoro = habit_formation.get_pomodoro_recommendation(report.fatigue_drop_minute)

    return {
        "user_id": user_id,
        "behavior": report.to_dict(),
        "daily_goal": goal.to_dict(),
        "tiny_habits": [h.to_dict() for h in tiny_habits],
        "pomodoro": pomodoro,
    }
