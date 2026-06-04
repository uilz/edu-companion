"""
v7.0 智能题库系统 API
路由前缀: /api/v7/practice

遵循现有规范：
- TEXT ID、无外键约束
- 同步实现，复用 psycopg2 连接池
- user_id 默认值来自 shared.constants.DEFAULT_USER_ID
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from shared.constants import DEFAULT_USER_ID
from app.services.practice_question_crud import (
    add_question, update_question, delete_question,
    toggle_favorite, toggle_slash, batch_import_questions,
)
from app.services.practice_question_bank import (
    _ensure_tables, list_banks, get_bank, create_bank, delete_bank,
    list_questions, get_question, resolve_bank_for_conversation, resolve_bank_for_node,
)
from app.services.practice_question_gen import (
    generate_and_save, handle_question_generation, generate_for_conversation,
)
from app.services.practice_session import (
    create_session, get_session, submit_answer, complete_session, list_sessions,
)
from app.services.practice_scheduler import (
    get_due_questions, get_review_stats,
)
from app.services.practice_stats import (
    get_overview, get_daily_trend, get_session_history,
    get_error_distribution, get_weak_skills,
)
from app.services.practice_error_book import (
    get_error_book, get_error_session_stats, clear_mastered_errors,
)
from app.services.achievement_service import (
    check_achievements, get_all_achievements, get_recent_unlocks, get_badge_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/practice", tags=["v7题库"])


# ═══════════════════════════════════════════════
# 题库管理
# ═══════════════════════════════════════════════


@router.get("/banks")
async def api_list_banks(user_id: str = DEFAULT_USER_ID):
    """获取用户所有题库"""
    _ensure_tables()
    return list_banks(user_id)


@router.post("/banks")
async def api_create_bank(body: dict, user_id: str = DEFAULT_USER_ID):
    """创建题库"""
    _ensure_tables()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "题库名称不能为空")
    return create_bank(
        user_id=user_id,
        name=name,
        description=body.get("description", ""),
        ref_node_id=body.get("ref_node_id"),
        ref_node_level=body.get("ref_node_level"),
    )


@router.get("/banks/{bank_id}")
async def api_get_bank(bank_id: str, user_id: str = DEFAULT_USER_ID):
    """题库详情"""
    _ensure_tables()
    bank = get_bank(bank_id, user_id)
    if not bank:
        raise HTTPException(404, "题库不存在")
    return bank


@router.delete("/banks/{bank_id}")
async def api_delete_bank(bank_id: str, user_id: str = DEFAULT_USER_ID):
    """删除题库"""
    _ensure_tables()
    ok = delete_bank(bank_id, user_id)
    if not ok:
        raise HTTPException(404, "题库不存在")
    return {"deleted": bank_id}


# ═══════════════════════════════════════════════
# 题目管理
# ═══════════════════════════════════════════════


@router.get("/banks/{bank_id}/questions")
async def api_list_questions(
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    question_type: Optional[str] = None,
    status: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
):
    """题库题目列表"""
    _ensure_tables()
    return list_questions(
        bank_id, user_id,
        page=page, page_size=page_size,
        question_type=question_type,
        status=status,
        cognitive_node_id=cognitive_node_id,
    )


@router.post("/banks/{bank_id}/questions")
async def api_add_question(bank_id: str, body: dict, user_id: str = DEFAULT_USER_ID):
    """手动添加单题"""
    _ensure_tables()
    stem = body.get("stem", "").strip()
    if not stem:
        raise HTTPException(400, "题干不能为空")
    answer = body.get("answer", [])
    if not answer:
        raise HTTPException(400, "答案不能为空")

    return add_question(
        bank_id=bank_id,
        user_id=user_id,
        question_type=body.get("question_type", "single"),
        stem=stem,
        answer=answer,
        options=body.get("options"),
        analysis=body.get("analysis", ""),
        difficulty=body.get("difficulty", 3),
        cognitive_node_ids=body.get("cognitive_node_ids"),
        source=body.get("source", "manual"),
        metadata=body.get("metadata"),
    )


@router.get("/questions/{question_id}")
async def api_get_question(question_id: str, user_id: str = DEFAULT_USER_ID):
    """题目详情"""
    _ensure_tables()
    q = get_question(question_id, user_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    return q


@router.patch("/questions/{question_id}")
async def api_update_question(question_id: str, body: dict, user_id: str = DEFAULT_USER_ID):
    """更新题目"""
    _ensure_tables()
    q = update_question(question_id, user_id, **body)
    if not q:
        raise HTTPException(404, "题目不存在")
    return q


@router.delete("/questions/{question_id}")
async def api_delete_question(question_id: str, user_id: str = DEFAULT_USER_ID):
    """删除题目"""
    _ensure_tables()
    ok = delete_question(question_id, user_id)
    if not ok:
        raise HTTPException(404, "题目不存在")
    return {"deleted": question_id}


@router.post("/questions/{question_id}/favorite")
async def api_toggle_favorite(question_id: str, user_id: str = DEFAULT_USER_ID):
    """收藏/取消收藏"""
    _ensure_tables()
    now_fav = toggle_favorite(question_id, user_id)
    return {"is_favorite": now_fav}


@router.post("/questions/{question_id}/slash")
async def api_toggle_slash(question_id: str, user_id: str = DEFAULT_USER_ID):
    """斩题/恢复"""
    _ensure_tables()
    now_slashed = toggle_slash(question_id, user_id)
    return {"is_slashed": now_slashed}


# ═══════════════════════════════════════════════
# 题库→对话/知识点解析
# ═══════════════════════════════════════════════


@router.post("/resolve/conversation")
async def api_resolve_conversation(body: dict, user_id: str = DEFAULT_USER_ID):
    """解析对话应归属的题库"""
    _ensure_tables()
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        raise HTTPException(400, "conversation_id 不能为空")
    bank_id = resolve_bank_for_conversation(
        conversation_id, user_id,
        user_specified_bank_id=body.get("bank_id"),
    )
    bank = get_bank(bank_id, user_id)
    return {"bank_id": bank_id, "bank": bank}


@router.post("/resolve/node")
async def api_resolve_node(body: dict, user_id: str = DEFAULT_USER_ID):
    """解析知识点应归属的题库"""
    node_id = body.get("node_id", "")
    if not node_id:
        raise HTTPException(400, "node_id 不能为空")
    bank_id = resolve_bank_for_node(node_id, user_id)
    bank = get_bank(bank_id, user_id)
    return {"bank_id": bank_id, "bank": bank}


# ═══════════════════════════════════════════════
# AI 出题
# ═══════════════════════════════════════════════


@router.post("/generate")
async def api_generate(body: dict, user_id: str = DEFAULT_USER_ID):
    """AI 出题（自然语言指定参数）

    可选参数：
    - material_ids: list[str] — 指定参考已上传的资料出题
    """
    _ensure_tables()
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "请描述你想练习什么内容")
    bank_id = body.get("bank_id")
    conversation_id = body.get("conversation_id")
    node_id = body.get("node_id")
    material_ids = body.get("material_ids")

    result = await handle_question_generation(
        user_message=user_message,
        user_id=user_id,
        bank_id=bank_id,
        conversation_id=conversation_id,
        node_id=node_id,
        material_ids=material_ids,
    )
    return result


@router.post("/generate-from-materials")
async def api_generate_from_materials(body: dict, user_id: str = DEFAULT_USER_ID):
    """基于指定资料出题（显式参数，不通过自然语言提取）"""
    _ensure_tables()
    material_ids = body.get("material_ids", [])
    if not material_ids:
        raise HTTPException(400, "请指定至少一个资料")

    subject = body.get("subject", "通用")
    skill_id = body.get("skill_id", subject)
    bloom_level = body.get("bloom_level", "apply")
    difficulty = float(body.get("difficulty", 0.5))
    count = max(1, min(10, int(body.get("count", 5))))
    content_type = body.get("content_type", "choice")
    bank_id = body.get("bank_id")

    # 确定题库归属
    if not bank_id:
        bank_id = resolve_bank_for_conversation(f"materials_{hash(str(material_ids))}", user_id)

    # 获取参考资料上下文
    from app.services.practice_question_gen import get_material_context
    material_context = await get_material_context(material_ids, user_id)

    # 生成并保存
    saved = await generate_and_save(
        bank_id=bank_id,
        user_id=user_id,
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
    )

    bank = get_bank(bank_id, user_id)
    return {
        "bank_id": bank_id,
        "bank_name": bank["name"] if bank else "",
        "generated": len(saved),
        "questions": saved,
        "has_material_context": material_context is not None,
        "material_count": len(material_ids),
        "params": {
            "subject": subject,
            "skill_id": skill_id,
            "bloom_level": bloom_level,
            "difficulty": difficulty,
            "count": count,
            "content_type": content_type,
        },
    }


@router.post("/generate-from-conversation")
async def api_generate_from_conversation(body: dict, user_id: str = DEFAULT_USER_ID):
    """对话场景出题：自动识别对话内容并生成题目"""
    _ensure_tables()
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        raise HTTPException(400, "conversation_id 不能为空")
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "请描述你想练习什么内容")
    context = body.get("context")  # 可选：最近几条对话消息

    result = await generate_for_conversation(
        conversation_id=conversation_id,
        user_message=user_message,
        user_id=user_id,
        conversation_context=context,
        material_ids=body.get("material_ids"),
    )
    return result


# ═══════════════════════════════════════════════
# 练习会话
# ═══════════════════════════════════════════════


@router.post("/sessions")
async def api_create_session(body: dict, user_id: str = DEFAULT_USER_ID):
    """创建练习会话（含自适应选题）"""
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    return create_session(
        bank_id=bank_id,
        user_id=user_id,
        session_type=body.get("session_type", "practice"),
        mode=body.get("mode", "adaptive"),
        question_count=body.get("count", 10),
        config=body.get("config"),
        exclude_ids=body.get("exclude_ids"),
        cognitive_node_ids=body.get("cognitive_node_ids"),
    )


@router.get("/sessions")
async def api_list_sessions(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    """练习会话列表"""
    _ensure_tables()
    return list_sessions(
        user_id=user_id, bank_id=bank_id, status=status,
        limit=min(limit, 100), offset=max(offset, 0),
    )


@router.get("/sessions/{session_id}")
async def api_get_session(session_id: str, user_id: str = DEFAULT_USER_ID):
    """会话详情"""
    _ensure_tables()
    session = get_session(session_id, user_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    return session


@router.post("/sessions/{session_id}/submit")
async def api_submit_answer(session_id: str, body: dict, user_id: str = DEFAULT_USER_ID):
    """提交答题"""
    _ensure_tables()
    question_id = body.get("question_id", "")
    if not question_id:
        raise HTTPException(400, "question_id 不能为空")
    result = submit_answer(
        session_id=session_id,
        question_id=question_id,
        user_id=user_id,
        user_answer=body.get("answer"),
        time_spent=body.get("time_spent", 0),
        hints_used=body.get("hints_used", 0),
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sessions/{session_id}/complete")
async def api_complete_session(session_id: str, user_id: str = DEFAULT_USER_ID):
    """完成会话"""
    _ensure_tables()
    result = complete_session(session_id, user_id)
    if not result:
        raise HTTPException(404, "会话不存在")
    return result


# ═══════════════════════════════════════════════
# 复习调度
# ═══════════════════════════════════════════════


@router.get("/review/due")
async def api_review_due(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    limit: int = 20,
):
    """获取到期望习题"""
    _ensure_tables()
    return get_due_questions(
        user_id=user_id,
        bank_id=bank_id,
        cognitive_node_id=cognitive_node_id,
        limit=min(limit, 100),
    )


@router.get("/review/stats")
async def api_review_stats(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
):
    """复习统计概览"""
    _ensure_tables()
    return get_review_stats(user_id=user_id, bank_id=bank_id)


# ═══════════════════════════════════════════════
# 统计
# ═══════════════════════════════════════════════


@router.get("/stats/overview")
async def api_stats_overview(user_id: str = DEFAULT_USER_ID):
    """总体概览统计"""
    _ensure_tables()
    return get_overview(user_id)


@router.get("/stats/daily")
async def api_stats_daily(user_id: str = DEFAULT_USER_ID, days: int = 30):
    """每日练习趋势"""
    _ensure_tables()
    return get_daily_trend(user_id, days=min(days, 90))


@router.get("/stats/sessions")
async def api_stats_sessions(user_id: str = DEFAULT_USER_ID, limit: int = 10):
    """最近会话历史"""
    _ensure_tables()
    return get_session_history(user_id, limit=min(limit, 50))


@router.get("/stats/errors")
async def api_stats_errors(user_id: str = DEFAULT_USER_ID):
    """错题分布"""
    _ensure_tables()
    return get_error_distribution(user_id)


@router.get("/stats/weak-skills")
async def api_stats_weak_skills(user_id: str = DEFAULT_USER_ID):
    """薄弱知识点"""
    _ensure_tables()
    return get_weak_skills(user_id)


# ═══════════════════════════════════════════════
# 错题本
# ═══════════════════════════════════════════════


@router.get("/error-book")
async def api_error_book(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    min_wrongs: int = 1,
    sort_by: str = "wrongs_desc",
    page: int = 1,
    page_size: int = 20,
):
    """错题本列表"""
    _ensure_tables()
    return get_error_book(
        user_id=user_id, bank_id=bank_id,
        cognitive_node_id=cognitive_node_id,
        min_wrongs=min_wrongs, sort_by=sort_by,
        page=page, page_size=min(page_size, 100),
    )


@router.get("/error-book/stats")
async def api_error_book_stats(user_id: str = DEFAULT_USER_ID):
    """错题本概览"""
    _ensure_tables()
    return get_error_session_stats(user_id)


@router.post("/error-book/clear-mastered")
async def api_clear_mastered(user_id: str = DEFAULT_USER_ID):
    """清除已掌握的错题记录"""
    _ensure_tables()
    return clear_mastered_errors(user_id)


# ═══════════════════════════════════════════════
# 考试模式
# ═══════════════════════════════════════════════


@router.post("/exam")
async def api_create_exam(body: dict, user_id: str = DEFAULT_USER_ID):
    """创建考试（全功能模式：计时+答题卡+自动交卷+成绩报告）"""
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    count = max(5, min(100, int(body.get("count", 20))))
    duration = max(5, min(180, int(body.get("duration_minutes", 60))))
    from app.services.practice_exam import create_exam
    result = create_exam(
        user_id=user_id,
        bank_id=bank_id,
        count=count,
        duration_minutes=duration,
        config=body.get("config"),
        cognitive_node_ids=body.get("cognitive_node_ids"),
    )
    return result


@router.get("/exam/{session_id}/time")
async def api_exam_time(session_id: str, user_id: str = DEFAULT_USER_ID):
    """获取考试剩余时间"""
    from app.services.practice_exam import get_exam_time
    return get_exam_time(session_id, user_id)


@router.post("/exam/{session_id}/submit-all")
async def api_exam_submit_all(session_id: str, user_id: str = DEFAULT_USER_ID):
    """提交考试所有答案，生成成绩报告"""
    _ensure_tables()
    from app.services.practice_exam import submit_all_exam
    result = submit_all_exam(session_id, user_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/exam/{session_id}/result")
async def api_exam_result(session_id: str, user_id: str = DEFAULT_USER_ID):
    """获取考试成绩报告"""
    from app.services.practice_exam import get_exam_result
    return get_exam_result(session_id, user_id)


@router.get("/exam/{session_id}/answer-sheet")
async def api_exam_answer_sheet(session_id: str, user_id: str = DEFAULT_USER_ID):
    """获取答题卡状态"""
    from app.services.practice_exam import get_exam_answer_sheet
    return get_exam_answer_sheet(session_id, user_id)


# ═══════════════════════════════════════════════
# 成就/徽章
# ═══════════════════════════════════════════════


@router.get("/achievements")
async def api_get_achievements(user_id: str = DEFAULT_USER_ID):
    """获取所有成就及进度"""
    _ensure_tables()
    return get_all_achievements(user_id)


@router.get("/achievements/recent")
async def api_recent_achievements(user_id: str = DEFAULT_USER_ID, limit: int = 5):
    """最近解锁成就"""
    _ensure_tables()
    return get_recent_unlocks(user_id, limit=min(limit, 20))


@router.get("/achievements/stats")
async def api_achievement_stats(user_id: str = DEFAULT_USER_ID):
    """成就统计"""
    _ensure_tables()
    return get_badge_stats(user_id)


@router.post("/achievements/check")
async def api_check_achievements(user_id: str = DEFAULT_USER_ID):
    """手动触发成就检测"""
    _ensure_tables()
    newly = check_achievements(user_id)
    return {"newly_unlocked": newly, "count": len(newly)}


# ═══════════════════════════════════════════════
# 题库导入（多格式）
# ═══════════════════════════════════════════════


@router.post("/import/upload")
async def api_import_upload(body: dict, user_id: str = DEFAULT_USER_ID):
    """上传文件并解析预览（支持 docx/xlsx/txt/json）"""
    _ensure_tables()
    file_path = body.get("file_path", "").strip()
    if not file_path:
        raise HTTPException(400, "file_path 不能为空")
    file_type = body.get("file_type", "")
    bank_id = body.get("bank_id", "")
    from app.services.practice_import import preview_import
    try:
        return preview_import(file_path, file_type, user_id, bank_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("导入解析失败: %s", e)
        raise HTTPException(500, f"解析失败: {e}")


@router.post("/import/preview")
async def api_import_preview(body: dict, user_id: str = DEFAULT_USER_ID):
    """解析原始文本为题目预览（无需上传文件）"""
    _ensure_tables()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    from app.services.practice_import import parse_questions_from_text, ai_correct_question, match_cognitive_nodes
    questions = parse_questions_from_text(text)
    for q in questions:
        q = ai_correct_question(q)
        q["suggested_node_ids"] = match_cognitive_nodes(q, user_id)
    high = sum(1 for q in questions if q.get("confidence", 0) >= 0.8)
    return {"questions": questions, "stats": {"total": len(questions), "high_confidence": high, "low_confidence": len(questions) - high}}


@router.post("/import/confirm")
async def api_import_confirm(body: dict, user_id: str = DEFAULT_USER_ID):
    """确认导入题目到题库"""
    _ensure_tables()
    bank_id = body.get("bank_id", "").strip()
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    questions = body.get("questions", [])
    if not questions:
        raise HTTPException(400, "questions 不能为空")
    from app.services.practice_import import confirm_import
    return confirm_import(questions, bank_id, user_id)


# ═══════════════════════════════════════════════
# 秘书联动提案
# ═══════════════════════════════════════════════


@router.get("/secretary/proposals")
async def api_practice_secretary_proposals(
    user_id: str = DEFAULT_USER_ID,
    limit: int = 5,
):
    """获取练习相关的秘书提案"""
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals(user_id, limit=limit)
    practice_types = {"practice_error_alert", "practice_mastery_stuck", "practice_review_reminder", "practice_reflection"}
    filtered = [p for p in proposals if p.action_type in practice_types]
    result = []
    for p in filtered:
        result.append({
            "id": p.id,
            "emoji": p.emoji or "💡",
            "title": p.title,
            "description": p.description,
            "action_type": p.action_type,
            "payload": p.payload,
            "priority": p.priority,
            "created_at": p.created_at,
        })
    return {"proposals": result[:limit], "total": len(filtered)}


@router.post("/secretary/proposals/{proposal_id}/accept")
async def api_secretary_accept_proposal(proposal_id: str, body: dict = None, user_id: str = DEFAULT_USER_ID):
    """接受秘书提案"""
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "accepted", user_id)
    return {"status": "accepted"}


@router.post("/secretary/proposals/{proposal_id}/dismiss")
async def api_secretary_dismiss_proposal(proposal_id: str, user_id: str = DEFAULT_USER_ID):
    """忽略秘书提案"""
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "dismissed", user_id)
    return {"status": "dismissed"}


# ═══════════════════════════════════════════════
# 批量导入（JSON）
# ═══════════════════════════════════════════════


@router.post("/import/batch")
async def api_batch_import(body: dict, user_id: str = DEFAULT_USER_ID):
    """批量导入题目"""
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    questions = body.get("questions", [])
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    if not questions:
        raise HTTPException(400, "questions 不能为空")

    saved = batch_import_questions(bank_id, user_id, questions)
    return {
        "imported": len(saved),
        "questions": saved,
    }
