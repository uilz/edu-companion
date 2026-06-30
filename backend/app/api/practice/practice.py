"""练习系统API
端点：题目生成、会话管理、答题提交、统计查询
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.services.practice.engine import (
    get_hint_for_question,
    get_inline_hint,
    build_reply_text,
    update_cognitive_after_practice,
    get_cognitive_proficiency,
    list_practice_sessions,
    complete_practice_session,
    record_attempt,
    compute_practice_stats,
    compute_behavior_report_data,
)
from app.services.practice.practice_service import check_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice"])


def _get_metacognition_feedback(confidence_before: int | None, is_correct: bool) -> str:
    """根据自信度和正确性返回元认知反馈文案"""
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        else:
            return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    else:
        if is_correct:
            return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
        else:
            return "还有提升空间，继续努力"


# ──────────────────────────────────────────────
# Pydantic 请求模型
# ──────────────────────────────────────────────


class HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    time_spent_seconds: float = 0.0
    hints_used: int = 0
    confidence_before: int | None = None


class InlineAnswerRequest(BaseModel):
    block_id: str
    answer: str


class InlineHintRequest(BaseModel):
    block_id: str


# ──────────────────────────────────────────────
# 会话管理
# ──────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(user_id: str = Depends(current_user_id), limit: int = 20):
    """列出用户的所有会话"""
    return list_practice_sessions(user_id, limit)


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    dir_id: str | None = None,
    branch_id: str | None = None,
):
    """结束会话（如果有对话上下文，写入branch）"""
    result = complete_practice_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result["session"]

    # 写入对话branch
    if dir_id and branch_id:
        try:
            from app.services.practice.engine import integrate_practice_to_branch
            from app.schemas.practice import PracticeSession
            from datetime import datetime as dt

            ps = PracticeSession(
                user_id=user_id,
                question_ids=session.get("question_ids", []),
                planned_skills=session.get("planned_skills", []),
                correct_count=result["correct"],
                started_at=session.get("created_at", dt.now()),
                completed_at=dt.now(),
            )
            await integrate_practice_to_branch(user_id, ps, dir_id, branch_id)
        except Exception as e:
            logger.warning(f"练习结果写入branch失败: {e}")

    # 发布 SessionCompleted 事件
    try:
        from shared.events import SessionCompleted
        from app.application.di import container
        event = SessionCompleted(
            user_id=user_id,
            session_id=session_id,
            total_questions=result["total"],
            correct_count=result["correct"],
            accuracy=result["accuracy"],
            duration_minutes=session.get("estimated_minutes", 0),
        )
        asyncio.create_task(container.event_bus.publish(event))
    except Exception:
        logger.debug("SessionCompleted 事件发布失败", exc_info=True)

    return {
        "session": session,
        "accuracy": result["accuracy"],
        "struggling_skills": result["struggling"],
    }


# ──────────────────────────────────────────────
# 提示
# ──────────────────────────────────────────────


@router.post("/hint")
async def get_hint(req: HintRequest):
    """获取提示"""
    result = get_hint_for_question(req.question_id, req.current_level)
    if result is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


# ──────────────────────────────────────────────
# 独立练习答题提交
# ──────────────────────────────────────────────


@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest, user_id: str = Depends(current_user_id)):
    """独立练习 — 提交单题答案"""
    from app.infrastructure.db.database import get_db

    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE id = %s", (req.question_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")

    correct_answer = (row.get("answer") or "").strip()
    is_correct = check_answer(req.answer, correct_answer)
    explanation = row.get("analysis", "")
    skill_id = row.get("skill_id", "")

    # 更新 CognitiveNode
    knowledge_update = None
    if skill_id:
        cog = update_cognitive_after_practice(
            user_id=user_id,
            skill_id=skill_id,
            is_correct=is_correct,
            latency_ms=int(req.time_spent_seconds * 1000),
            confidence_before=req.confidence_before,
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": round(cog["p_before"], 4),
            "p_known_after": round(cog["p_after"], 4),
            "mastery_level": cog["mastery_label"],
        }

    # 记录答题
    record_attempt(
        user_id=user_id,
        session_id=req.session_id,
        question_id=req.question_id,
        answer=req.answer,
        is_correct=is_correct,
        time_spent_seconds=req.time_spent_seconds,
        hints_used=req.hints_used,
        confidence_before=req.confidence_before,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "knowledge_update": knowledge_update,
        "metacognition_feedback": _get_metacognition_feedback(req.confidence_before, is_correct),
    }


# ──────────────────────────────────────────────
# 对话内联练习（Inline Practice）
# ──────────────────────────────────────────────


@router.post("/inline/answer")
async def inline_answer(req: InlineAnswerRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 提交答案，读取 response_block 内容校验"""
    from app.services.common import get_data_repo
    from shared.knowledge_trace import get_cognitive_state
    from shared.constants import get_mastery_label

    data = get_data_repo().load(user_id)
    block = data.response_blocks.get(req.block_id)
    if not block:
        raise HTTPException(404, "Practice block not found")

    content = block.content or {}
    correct_answer = content.get("correct_answer", "").strip().upper()
    explanation = content.get("explanation") or content.get("reply_expected", "") or ""
    skill_id = content.get("skill_id", "")
    is_correct = req.answer.strip().upper() == correct_answer

    # 更新知识状态
    knowledge_update = {}
    if skill_id:
        state = get_cognitive_state(user_id, skill_id)
        cog = update_cognitive_after_practice(
            user_id=user_id,
            skill_id=skill_id,
            is_correct=is_correct,
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": cog["p_before"],
            "p_known_after": cog["p_after"],
            "mastery_level": get_mastery_label(state.p_known, state.attempt_count),
            "cognitive_proficiency": cog["cognitive_proficiency"],
        }

    correct_label = content.get("correct_answer", "")
    reply_text = build_reply_text(is_correct, correct_label, explanation)

    return {
        "is_correct": is_correct,
        "reply_text": reply_text,
        "knowledge_update": knowledge_update,
    }


@router.post("/inline/hint")
async def inline_hint(req: InlineHintRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 获取提示"""
    result = get_inline_hint(req.block_id, user_id)
    if result is None:
        raise HTTPException(404, "Practice block not found")
    return result


# ──────────────────────────────────────────────
# 统计 + 行为分析
# ──────────────────────────────────────────────


@router.get("/stats")
async def get_stats(user_id: str = Depends(current_user_id), time_range: str = "week"):
    """获取练习统计"""
    return compute_practice_stats(time_range=time_range, user_id=user_id)


@router.get("/behavior")
async def get_behavior_report(user_id: str = Depends(current_user_id), time_range: str = "week"):
    """学习行为分析报告"""
    return compute_behavior_report_data(time_range=time_range, user_id=user_id)


# ──────────────────────────────────────────────
# 题目质量监控
# ──────────────────────────────────────────────


@router.get("/quality")
async def get_quality_summary():
    """获取全量质量摘要"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    summary = quality_analyzer.analyze_all()
    return summary.to_dict()


@router.post("/quality/apply")
async def apply_quality_actions(dry_run: bool = True):
    """执行质量分析建议动作"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    result = quality_analyzer.apply_actions(dry_run=dry_run)
    return result


@router.get("/quality/detail/{question_id}")
async def get_question_quality(question_id: str):
    """获取单题质量分析"""
    from app.services.analytics.quality_analyzer import quality_analyzer
    result = quality_analyzer.analyze_question(question_id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return result.to_dict()


# ──────────────────────────────────────────────
# 统一知识状态 API (SharedKnowledgeState)
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# 自我解释评估（P0-R03）
# ──────────────────────────────────────────────


class SelfExplainRequest(BaseModel):
    explanation_text: str
    knowledge_node_id: str
    prompt_type: str = "retell"  # retell | example | contrast


@router.post("/self-explain")
async def evaluate_self_explain(req: SelfExplainRequest, user_id: str = Depends(current_user_id)):
    """评估学生的自我解释质量，结果写入 CognitiveNode"""
    import json
    import time

    from app.domain.cognitive import get_repo
    from app.domain.cognitive.models import Metacognition

    # 1. 获取知识节点概念名
    repo = get_repo()
    node = repo.get_node(req.knowledge_node_id, user_id)
    concept_name = node.label if node else req.knowledge_node_id

    # 2. 构建评估 prompt
    evaluation_prompt = f"""你是一个学习评估助手。
学生刚学习了「{concept_name}」。现在他用自己话做了如下解释：
「{req.explanation_text}」
请评估：
1. 准确性（A/B/C）——包含重大错误吗？
2. 完整性（完整/部分/缺失核心）——抓住了关键点吗？
3. 清晰度（清晰/模糊/混乱）——容易理解吗？
4. 一句话反馈（告诉学生哪里说得好、哪里可以改进）
输出格式（严格 JSON）：{{ "accuracy": "A|B|C", "completeness": "完整|部分|缺失核心", "clarity": "清晰|模糊|混乱", "feedback": "一句话反馈" }}"""

    # 3. 调用 LLM
    from app.infrastructure.llm.llm_service import llm_service
    try:
        raw = await llm_service.generate(
            messages=[{"role": "user", "content": evaluation_prompt}],
            task_type="explain",
            temperature=0.3,
            max_tokens=512,
        )
        # 解析 JSON
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"LLM 自我解释评估失败: {e}, raw={raw if 'raw' in dir() else 'N/A'}")
        result = {
            "accuracy": "B",
            "completeness": "部分",
            "clarity": "模糊",
            "feedback": f"评估暂不可用，请稍后重试",
        }

    # 4. 写入 CognitiveNode.deep_processing 和 metacognition
    try:
        node = repo.get_node(req.knowledge_node_id, user_id)
        if node:
            node.deep_processing.task_instances.append({
                "type": "self_explain",
                "prompt_type": req.prompt_type,
                "explanation_text": req.explanation_text[:500],
                "result": result,
                "timestamp": time.time(),
            })
            # 更新元认知校准
            accuracy_score = {"A": 0.9, "B": 0.6, "C": 0.3}.get(result.get("accuracy", "B"), 0.6)
            completeness_score = {"完整": 0.9, "部分": 0.5, "缺失核心": 0.2}.get(
                result.get("completeness", "部分"), 0.5
            )
            clarity_score = {"清晰": 0.9, "模糊": 0.5, "混乱": 0.2}.get(
                result.get("clarity", "模糊"), 0.5
            )
            overall = (accuracy_score + completeness_score + clarity_score) / 3

            old_meta = node.metacognition
            new_calibration = old_meta.calibration_error * 0.7 + abs(old_meta.self_assessment - overall) * 0.3
            node.metacognition = Metacognition(
                self_assessment=overall,
                calibration_error=round(new_calibration, 4),
                direction="accurate" if new_calibration < 0.3 else (
                    "overconfident" if overall > old_meta.self_assessment else "underconfident"
                ),
            )
            repo.upsert_node(node, user_id)
    except Exception as e:
        logger.warning(f"写入 CognitiveNode 失败: {e}")

    return {
        "accuracy": result.get("accuracy", "B"),
        "completeness": result.get("completeness", "部分"),
        "clarity": result.get("clarity", "模糊"),
        "feedback": result.get("feedback", ""),
        "concept_name": concept_name,
    }


@router.get("/knowledge/state")
async def get_knowledge_state():
    """获取统一知识状态"""
    from app.domain.knowledge import get_knowledge_query
    return get_knowledge_query().get_all_skills_summary()


# ──────────────────────────────────────────────
# 自信度校准报告
# ──────────────────────────────────────────────


@router.get("/confidence-report")
async def get_confidence_report(
    user_id: str = Depends(current_user_id),
    subject: str | None = None,
    days: int = 30,
):
    """自信度校准报告：按学科的偏差趋势、均值、建议"""
    from datetime import datetime, timedelta
    from app.infrastructure.db.database import get_db

    db = get_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    query = """SELECT pa.confidence_before, pa.is_correct, pa.created_at,
                      COALESCE(q.metadata->>'subject', 'general') as subject
               FROM practice_attempts pa
               LEFT JOIN questions q ON q.id = pa.question_id
               WHERE pa.user_id = %s
                 AND pa.confidence_before IS NOT NULL
                 AND pa.created_at >= %s
               ORDER BY pa.created_at DESC"""
    rows = db.fetchall(query, (user_id, cutoff))

    if not rows:
        return {
            "user_id": user_id,
            "days": days,
            "overall_bias": 0,
            "by_subject": [],
            "suggestion": "暂无自信度数据。开始练习时选择自信度，系统将为你提供校准分析。",
        }

    # 按学科分组
    by_subject: dict[str, list[dict]] = {}
    for r in rows:
        subj = r.get("subject", "general") or "general"
        cb = r.get("confidence_before")
        ic = r.get("is_correct", False)
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append({
            "confidence_before": cb,
            "is_correct": ic,
            "gap": cb - (4 if ic else 0),
        })

    if subject and subject in by_subject:
        subjects_to_report = {subject: by_subject[subject]}
    else:
        subjects_to_report = by_subject

    subject_results = []
    all_gaps = []

    for subj, items in sorted(subjects_to_report.items()):
        gaps = [it["gap"] for it in items]
        all_gaps.extend(gaps)
        avg_gap = sum(gaps) / len(gaps) if gaps else 0

        # 每日趋势
        daily: dict[str, list[float]] = {}
        for it in items:
            day = it.get("confidence_before")
            if day is not None:
                pass  # 简化：仅按学科聚合

        subject_results.append({
            "subject": subj,
            "sample_count": len(items),
            "mean_bias": round(avg_gap, 2),
            "direction": "overconfident" if avg_gap > 1 else ("underconfident" if avg_gap < -1 else "accurate"),
        })

    overall_bias = round(sum(all_gaps) / len(all_gaps), 2) if all_gaps else 0

    if overall_bias > 1.5:
        suggestion = "你有较明显的过度自信倾向，建议多做检验性练习，确认理解深度后再下结论。"
    elif overall_bias < -1.5:
        suggestion = "你往往低估自己，实际掌握度比预想高。建议尝试给别人讲解，增强信心。"
    elif abs(overall_bias) <= 0.5:
        suggestion = "你的自我评估非常准确，元认知能力优秀！继续保持。"
    else:
        suggestion = "自信度校准良好，略有偏差，继续关注。"

    return {
        "user_id": user_id,
        "days": days,
        "overall_bias": overall_bias,
        "by_subject": subject_results,
        "suggestion": suggestion,
    }
