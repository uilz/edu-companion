"""
错题本 — 所有错题集中展示与管理

聚合 practice_attempts 中 is_wrong=true 的记录，
按知识点/题库/错误次数分组，支持筛选和一键复习。
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_error_book(
    user_id: str,
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    min_wrongs: int = 1,
    sort_by: str = "wrongs_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    错题本查询。

    参数:
        min_wrongs: 最少错误次数过滤 (默认1=所有错题)
        sort_by: wrongs_desc / last_wrong_desc / difficulty_desc
        page, page_size: 分页

    返回:
        {items: [...], total, page, page_size, total_pages}
    """
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 聚合查询：每个错题的最新状态
    conditions = ["att.user_id = %s", "att.is_wrong = true"]
    params = [user_id]

    if bank_id:
        conditions.append("q.bank_id = %s")
        params.append(bank_id)
    if cognitive_node_id:
        conditions.append("%s = ANY(q.cognitive_node_ids)")
        params.append(cognitive_node_id)

    where = " AND ".join(conditions)

    # 总计数
    count_row = db.fetchone(
        f"""SELECT COUNT(DISTINCT att.question_id) as cnt
            FROM practice_attempts att
            JOIN questions q ON att.question_id = q.id AND q.deleted_at IS NULL
            WHERE {where}""",
        tuple(params),
    )
    total = count_row["cnt"] if count_row else 0

    # 排序
    order_map = {
        "wrongs_desc": "wrongs DESC",
        "wrongs_asc": "wrongs ASC",
        "last_wrong_desc": "last_wrong DESC",
        "last_wrong_asc": "last_wrong ASC",
        "difficulty_desc": "q.difficulty DESC",
        "difficulty_asc": "q.difficulty ASC",
    }
    order_sql = order_map.get(sort_by, "wrongs DESC")

    offset = (page - 1) * page_size

    rows = db.fetchall(
        f"""SELECT att.question_id,
                  q.bank_id, q.stem, q.options, q.question_type, q.difficulty,
                  q.cognitive_node_ids, q.analysis,
                  COUNT(*) as total_attempts,
                  SUM(CASE WHEN att.is_wrong THEN 1 ELSE 0 END) as wrongs,
                  MAX(CASE WHEN att.is_wrong THEN att.created_at ELSE NULL END) as last_wrong,
                  MAX(att.created_at) as last_done,
                  MAX(att.consecutive_correct) as max_consecutive
           FROM practice_attempts att
           JOIN questions q ON att.question_id = q.id AND q.deleted_at IS NULL
           WHERE {where}
           GROUP BY att.question_id, q.bank_id, q.stem, q.options,
                    q.question_type, q.difficulty, q.cognitive_node_ids, q.analysis
           ORDER BY {order_sql}
           LIMIT %s OFFSET %s""",
        tuple(params + [page_size, offset]),
    )

    from app.services.practice.practice_question_bank import _safe_json

    items = []
    for r in rows:
        wrongs = r["wrongs"] or 0
        total_att = r["total_attempts"] or 0
        mastered = (r["max_consecutive"] or 0) >= 3

        items.append({
            "question_id": r["question_id"],
            "bank_id": r["bank_id"],
            "stem": r["stem"],
            "options": _safe_json(r.get("options"), []),
            "question_type": r["question_type"],
            "difficulty": r["difficulty"],
            "cognitive_node_ids": r.get("cognitive_node_ids") or [],
            "analysis": r.get("analysis", ""),
            "total_attempts": total_att,
            "wrong_count": wrongs,
            "wrong_rate": round(wrongs / max(total_att, 1) * 100, 1),
            "mastered": mastered,
            "last_wrong": _safe_iso(r.get("last_wrong")),
            "last_done": _safe_iso(r.get("last_done")),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "cold_start": total == 0,
        "cold_start_hint": "还没有错题，继续练习吧！" if total == 0 else "",
    }


def get_error_session_stats(user_id: str) -> dict:
    """错题本概览统计"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 唯一错题数
    unique_wrong = db.fetchone(
        """SELECT COUNT(DISTINCT question_id) as cnt
           FROM practice_attempts
           WHERE user_id = %s AND is_wrong = true""",
        (user_id,),
    )
    unique_count = unique_wrong["cnt"] if unique_wrong else 0

    # 总错误次数
    total_wrongs = db.fetchone(
        """SELECT COUNT(*) as cnt
           FROM practice_attempts
           WHERE user_id = %s AND is_wrong = true""",
        (user_id,),
    )
    total_w = total_wrongs["cnt"] if total_wrongs else 0

    # 已掌握但曾经错过的（连续正确>=3）
    mastered_from_errors = db.fetchone(
        """SELECT COUNT(DISTINCT att.question_id) as cnt
           FROM practice_attempts att
           WHERE att.user_id = %s AND att.question_id IN (
               SELECT question_id FROM practice_attempts
               WHERE user_id = %s AND is_wrong = true
           )
           GROUP BY att.question_id
           HAVING MAX(att.consecutive_correct) >= 3""",
        (user_id, user_id),
    )
    mastered_count = mastered_from_errors["cnt"] if mastered_from_errors else 0

    # 知识点分布
    nodes = db.fetchall(
        """SELECT DISTINCT UNNEST(q.cognitive_node_ids) as node_id
           FROM practice_attempts att
           JOIN questions q ON att.question_id = q.id
           WHERE att.user_id = %s AND att.is_wrong = true
           AND q.deleted_at IS NULL AND q.cognitive_node_ids IS NOT NULL""",
        (user_id,),
    )

    return {
        "unique_wrong_questions": unique_count,
        "total_wrong_attempts": total_w,
        "mastered_from_errors": mastered_count,
        "still_weak": unique_count - mastered_count,
        "related_nodes": len(nodes),
    }


def review_error_question(
    question_id: str,
    user_id: str,
    is_correct: bool = False,
    time_spent: int = 0,
) -> dict:
    """错题复习提交：
    - 连续答对 2 次 → 标记为已掌握
    - 答错 → consecutive_correct 归零
    - 更新认知节点
    """
    from app.infrastructure.db.database import get_db
    from app.domain.cognitive import get_repo
    db = get_db()

    # 获取最近一次 attempt
    last = db.fetchone(
        """SELECT * FROM practice_attempts
           WHERE question_id = %s AND user_id = %s
           ORDER BY created_at DESC LIMIT 1""",
        (question_id, user_id),
    )
    if not last:
        return {"error": "该题没有练习记录", "mastered": False}

    current_cc = last.get("consecutive_correct", 0)
    current_wc = last.get("wrong_count", 1)
    node_ids = last.get("cognitive_node_ids") or []

    if is_correct:
        new_cc = current_cc + 1
        mastered = new_cc >= 2
        new_wc = current_wc
    else:
        new_cc = 0
        mastered = False
        new_wc = current_wc + 1

    now = datetime.now().isoformat()
    # 写入一条新的 review attempt
    attempt_id = f"rev_{question_id}_{int(__import__('time').time())}"
    db.execute(
        """INSERT INTO practice_attempts
           (id, session_id, question_id, user_id, user_answer, is_correct,
            time_spent_seconds, is_wrong, wrong_count, consecutive_correct,
            mastered, cognitive_node_ids, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (attempt_id, f"review_{question_id}", question_id, user_id,
         "[]", is_correct, time_spent, not is_correct, new_wc, new_cc,
         mastered, node_ids, now),
    )

    # 更新认知节点
    for nid in node_ids:
        try:
            get_repo().sync_from_practice_event(
                user_id=user_id, skill_id=nid,
                is_correct=is_correct, time_spent=float(time_spent), hints_used=0,
            )
        except Exception:
            pass

    return {
        "attempt_id": attempt_id,
        "mastered": mastered,
        "consecutive_correct": new_cc,
        "wrong_count": new_wc,
        "needs_more_review": not mastered,
    }


def get_error_materials(
    question_id: str,
    user_id: str,
    limit: int = 3,
) -> list[dict]:
    """根据错题关联的认知节点，推荐复习资料"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    q = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
        (question_id, user_id),
    )
    if not q:
        return []

    node_ids = q.get("cognitive_node_ids") or []
    if not node_ids:
        return []

    recommendations = []

    # 1. 查用户上传的资料中关联了这些节点的
    try:
        rows = db.fetchall(
            """SELECT m.id, m.filename, m.file_type, m.file_size, m.created_at
               FROM material_meta m
               WHERE m.user_id = %s AND m.skills_covered && %s
               ORDER BY m.created_at DESC LIMIT %s""",
            (user_id, node_ids, limit),
        )
        for r in rows:
            recommendations.append({
                "type": "material",
                "id": r["id"],
                "title": r["filename"],
                "file_type": r.get("file_type", ""),
                "reason": "这份资料涉及你答错的知识点",
            })
    except Exception:
        pass

    # 2. 查 learning_memory
    try:
        rows2 = db.fetchall(
            """SELECT id, title, content_preview FROM learning_memory
               WHERE user_id = %s AND cognitive_node_ids && %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, node_ids, limit),
        )
        for r in rows2:
            recommendations.append({
                "type": "learning_memory",
                "id": r["id"],
                "title": r.get("title") or "学习笔记",
                "preview": (r.get("content_preview") or "")[:100],
                "reason": "这是你关于该知识点的学习记录",
            })
    except Exception:
        pass

    return recommendations


def clear_mastered_errors(user_id: str) -> dict:
    """清除已掌握的错题记录（标记 mastered=true 的题目不再显示在错题本）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 找到所有 mastered 的题目 ID
    mastered_ids = db.fetchall(
        """SELECT question_id
           FROM practice_attempts
           WHERE user_id = %s AND consecutive_correct >= 3
           GROUP BY question_id""",
        (user_id,),
    )

    count = len(mastered_ids)
    logger.info("已掌握错题清除: user=%s, count=%d", user_id, count)
    return {"cleared": count, "message": f"已清除 {count} 道已掌握的错题记录"}


def _safe_iso(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
