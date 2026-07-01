"""BI 数据分析 — analyst+ 权限

GET /kpi                  顶部 KPI 卡片
GET /user-activity        用户活跃度
GET /mastery-distribution 知识点掌握度分布
GET /practice-trend       练习趋势（天数可选）
GET /top-wrong-questions  错题 TOP N
GET /subject-distribution 学科分布
GET /difficulty-distribution 难度分布
GET /user-engagement      用户参与度排名
GET /accuracy-trend       正确率趋势
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


@router.get("/kpi")
async def kpi(_: dict = Depends(require_role("analyst"))):
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")
    rows = repo.query("""
        SELECT
            (SELECT COUNT(*) FROM users) AS users_total,
            (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS users_active,
            (SELECT COUNT(*) FROM practice_attempts) AS attempts_total,
            (SELECT COUNT(*) FROM practice_attempts WHERE is_correct = TRUE) AS attempts_correct,
            (SELECT COUNT(*) FROM practice_sessions) AS sessions_total,
            (SELECT COUNT(*) FROM knowledge_nodes WHERE level = 'atom') AS atom_nodes,
            (SELECT COUNT(*) FROM questions) AS questions_total,
            (SELECT COUNT(*) FROM questions WHERE deleted_at IS NULL) AS questions_active
    """)
    r = rows[0] if rows else {}
    total = int(r.get("attempts_total", 0) or 0)
    correct = int(r.get("attempts_correct", 0) or 0)
    accuracy = (correct / total) if total else 0
    return {
        "users_total": int(r.get("users_total", 0) or 0),
        "users_active": int(r.get("users_active", 0) or 0),
        "attempts_total": total,
        "attempts_correct": correct,
        "accuracy": round(accuracy, 4),
        "sessions_total": int(r.get("sessions_total", 0) or 0),
        "atom_nodes": int(r.get("atom_nodes", 0) or 0),
        "questions_total": int(r.get("questions_total", 0) or 0),
        "questions_active": int(r.get("questions_active", 0) or 0),
    }


@router.get("/mastery-distribution")
async def mastery_distribution(_: dict = Depends(require_role("analyst"))):
    repo = _repo()
    rows = repo.query("""
        SELECT
            CASE
                WHEN (belief->>'proficiency_mean')::float < 0.2  THEN '0-0.2'
                WHEN (belief->>'proficiency_mean')::float < 0.4  THEN '0.2-0.4'
                WHEN (belief->>'proficiency_mean')::float < 0.6  THEN '0.4-0.6'
                WHEN (belief->>'proficiency_mean')::float < 0.8  THEN '0.6-0.8'
                ELSE '0.8-1.0'
            END AS bucket,
            COUNT(*) AS cnt
        FROM knowledge_nodes
        WHERE level = 'atom' AND (belief->>'proficiency_mean') IS NOT NULL
        GROUP BY bucket
        ORDER BY bucket
    """) or []
    return {"buckets": rows}


@router.get("/practice-trend")
async def practice_trend(
    days: int = Query(30, ge=1, le=180),
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    rows = repo.query(
        "SELECT DATE(created_at) AS day, "
        "       COUNT(*) AS attempts, "
        "       COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct "
        "FROM practice_attempts "
        "WHERE created_at > NOW() - (%s || ' days')::interval "
        "GROUP BY DATE(created_at) ORDER BY day",
        (str(days),),
    ) or []
    series = []
    for r in rows:
        attempts = int(r.get("attempts", 0) or 0)
        correct = int(r.get("correct", 0) or 0)
        series.append({
            "day": str(r.get("day") or ""),
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(correct / attempts, 4) if attempts else 0,
        })
    return {"days": days, "series": series}


@router.get("/top-wrong-questions")
async def top_wrong_questions(
    limit: int = Query(10, ge=1, le=50),
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    rows = repo.query(
        "SELECT q.id, q.stem, q.difficulty, q.bank_id, "
        "       COUNT(*) FILTER (WHERE pa.is_correct = FALSE) AS wrong_count, "
        "       COUNT(*) AS total_attempts "
        "FROM questions q "
        "LEFT JOIN practice_attempts pa ON pa.question_id = q.id "
        "WHERE q.deleted_at IS NULL "
        "GROUP BY q.id, q.stem, q.difficulty, q.bank_id "
        "ORDER BY wrong_count DESC, total_attempts DESC "
        "LIMIT %s",
        (limit,),
    ) or []
    return {"items": rows}


@router.get("/user-activity")
async def user_activity(
    days: int = Query(7, ge=1, le=90),
    _: dict = Depends(require_role("analyst")),
):
    repo = _repo()
    rows = repo.query("""
        SELECT
            COUNT(*) FILTER (WHERE last_login >= NOW() - INTERVAL '1 day')  AS dau_1d,
            COUNT(*) FILTER (WHERE last_login >= NOW() - INTERVAL '7 day')  AS wau_7d,
            COUNT(*) FILTER (WHERE last_login >= NOW() - INTERVAL '30 day') AS mau_30d,
            COUNT(*) AS total_users
        FROM users
    """) or [{}]
    r = rows[0]
    return {
        "dau": int(r.get("dau_1d", 0) or 0),
        "wau": int(r.get("wau_7d", 0) or 0),
        "mau": int(r.get("mau_30d", 0) or 0),
        "total": int(r.get("total_users", 0) or 0),
    }


@router.get("/subject-distribution")
async def subject_distribution(_: dict = Depends(require_role("analyst"))):
    """按学科的知识节点分布"""
    repo = _repo()
    rows = repo.query("""
        SELECT
            COALESCE(q.bank_id, 'unknown') AS subject,
            COUNT(DISTINCT q.id) AS questions,
            COUNT(DISTINCT cn.id) AS nodes
        FROM questions q
        FULL JOIN knowledge_nodes cn ON cn.id = q.id
        GROUP BY q.bank_id
        ORDER BY questions DESC
    """) or []
    return {"items": rows}


@router.get("/difficulty-distribution")
async def difficulty_distribution(_: dict = Depends(require_role("analyst"))):
    """题目难度分布"""
    repo = _repo()
    rows = repo.query("""
        SELECT
            CASE
                WHEN difficulty < 0.3 THEN 'easy'
                WHEN difficulty < 0.6 THEN 'medium'
                ELSE 'hard'
            END AS bucket,
            COUNT(*) AS cnt
        FROM questions
        WHERE deleted_at IS NULL
        GROUP BY bucket
        ORDER BY bucket
    """) or []
    return {"buckets": rows}


@router.get("/user-engagement")
async def user_engagement(
    limit: int = Query(10, ge=1, le=50),
    _: dict = Depends(require_role("analyst")),
):
    """用户参与度排名（按练习次数）"""
    repo = _repo()
    rows = repo.query(
        "SELECT pa.user_id, u.username, "
        "       COUNT(*) AS total_attempts, "
        "       COUNT(DISTINCT DATE(pa.created_at)) AS active_days, "
        "       COUNT(*) FILTER (WHERE pa.is_correct = TRUE) AS correct_attempts "
        "FROM practice_attempts pa "
        "LEFT JOIN users u ON u.id = pa.user_id "
        "GROUP BY pa.user_id, u.username "
        "ORDER BY total_attempts DESC LIMIT %s",
        (limit,),
    ) or []
    return {"items": rows, "limit": limit}


@router.get("/accuracy-trend")
async def accuracy_trend(
    days: int = Query(30, ge=1, le=180),
    _: dict = Depends(require_role("analyst")),
):
    """每日正确率趋势（最近 N 天）"""
    repo = _repo()
    rows = repo.query(
        "SELECT DATE(created_at) AS day, "
        "       COUNT(*) AS total, "
        "       COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct, "
        "       AVG(time_spent_seconds) AS avg_time_spent "
        "FROM practice_attempts "
        "WHERE created_at > NOW() - (%s || ' days')::interval "
        "GROUP BY DATE(created_at) ORDER BY day",
        (str(days),),
    ) or []
    series = []
    for r in rows:
        t = int(r.get("total", 0) or 0)
        c = int(r.get("correct", 0) or 0)
        series.append({
            "day": str(r.get("day") or ""),
            "total": t,
            "correct": c,
            "accuracy": round(c / t, 4) if t else 0,
            "avg_time_spent": round(float(r.get("avg_time_spent", 0) or 0), 2),
        })
    return {"days": days, "series": series}
