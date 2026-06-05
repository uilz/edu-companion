"""
错题复习调度 — 基于间隔重复的智能复习引擎

算法:
- 简化的 SM-2 (SuperMemo) 变体
- 新错题 → 1天后复习
- 首次正确 → 3天后复查
- 连续2次正确 → 7天后复查
- 连续3+次正确 → 14天以上（EF 调整）

EF (Easiness Factor) 基于错题次数和难度:
  EF_base = 2.5 - wrong_count * 0.2
  间隔 = 基础间隔 * EF
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# ── 默认间隔（天） ──
INTERVALS = [1, 3, 7, 14, 30, 60]  # 第 N 次成功的间隔


def get_due_questions(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
    limit: int = 20,
    include_mastered: bool = False,
) -> list[dict]:
    """
    获取到期望习的题目。

    规则:
    1. 最近答错且未掌握的 → 最高优先
    2. 已掌握但超过复习间隔的 → 中等优先
    3. 从未做过的 → 低优先（已由 adaptive_select 覆盖）

    返回:
        [{question, due_status, priority_score, next_review_days}, ...]
    """
    from app.db.database import get_db
    db = get_db()

    # 查询所有活跃题目及其最近答题情况
    conditions = ["q.deleted_at IS NULL", "q.status = 'active'", "q.is_slashed = false"]
    params = [user_id]
    if bank_id:
        conditions.append("q.bank_id = %s")
        params.append(bank_id)
    if cognitive_node_id:
        conditions.append("%s = ANY(q.cognitive_node_ids)")
        params.append(cognitive_node_id)

    where = " AND ".join(conditions)

    questions = db.fetchall(
        f"""SELECT q.* FROM v7_questions q WHERE {where} ORDER BY q.created_at DESC""",
        tuple(params),
    )

    if not questions:
        return []

    # 获取这些题目的答题统计
    qids = [q["id"] for q in questions]
    if not qids:
        return []

    attempts = db.fetchall(
        """SELECT question_id,
                  COUNT(*) as total,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrongs,
                  MAX(CASE WHEN is_wrong THEN NULL ELSE created_at END) as last_correct,
                  MAX(CASE WHEN is_wrong THEN created_at ELSE NULL END) as last_wrong,
                  MAX(created_at) as last_done
           FROM v7_practice_attempts
           WHERE question_id = ANY(%s) AND user_id = %s
           GROUP BY question_id""",
        (qids, user_id),
    )
    attempt_map = {r["question_id"]: r for r in attempts}

    # 计算每道题的复习优先级
    now = time.time()
    now_dt = datetime.now()
    scored = []

    for q in questions:
        qid = q["id"]
        stat = attempt_map.get(qid, {})
        total = stat.get("total", 0) or 0
        wrongs = stat.get("wrongs", 0) or 0

        if total == 0:
            # 从未做过 — 不纳入复习调度
            continue

        last_correct = stat.get("last_correct")
        last_wrong = stat.get("last_wrong")
        last_done = stat.get("last_done")
        consecutive = _get_consecutive(db, qid, user_id)

        # 计算 EF
        difficulty = q.get("difficulty", 3)
        ef = max(1.3, min(2.5, 2.5 - wrongs * 0.2 - (difficulty - 3) * 0.1))

        # 当前连续正确次数 → 确定复习间隔
        interval_days = _calc_interval(consecutive, ef, wrongs)

        # 计算下次复习时间戳
        if last_correct:
            # 以最后一次正确为基准
            if isinstance(last_correct, str):
                last_dt = datetime.fromisoformat(str(last_correct))
            else:
                last_dt = last_correct
            next_review_ts = last_dt.timestamp() + interval_days * 86400
            next_review_dt = last_dt + timedelta(days=interval_days)
        elif last_done:
            if isinstance(last_done, str):
                last_dt = datetime.fromisoformat(str(last_done))
            else:
                last_dt = last_done
            next_review_ts = last_dt.timestamp() + interval_days * 86400
            next_review_dt = last_dt + timedelta(days=interval_days)
        else:
            next_review_ts = now
            next_review_dt = now_dt

        # 计算优先级分数（越小越紧急）
        days_overdue = (now - next_review_ts) / 86400 if next_review_ts < now else 0
        priority_score = -days_overdue  # 负数，超期越久越紧急

        # 错题加权
        if wrongs > 0:
            priority_score -= wrongs * 2  # 每错一次优先级+2

        # 未掌握加权
        mastered = consecutive >= 3
        if not mastered:
            priority_score -= 3  # 未掌握的题更紧急
        elif not include_mastered:
            continue  # 已掌握的跳过（除非要求包含）

        due = next_review_ts <= now
        days_until = max(0, (next_review_ts - now) / 86400)

        from app.services.practice.practice_question_bank import _safe_json

        scored.append({
            "question": {
                "id": q["id"],
                "bank_id": q["bank_id"],
                "question_type": q["question_type"],
                "stem": q["stem"],
                "options": _safe_json(q.get("options"), []),
                "difficulty": q.get("difficulty", 3),
                "cognitive_node_ids": q.get("cognitive_node_ids") or [],
            },
            "due": due,
            "days_overdue": round(days_overdue, 1),
            "days_until_next_review": round(days_until, 1),
            "priority_score": round(priority_score, 1),
            "consecutive_correct": consecutive,
            "wrong_count": wrongs,
            "mastered": mastered,
            "ef": round(ef, 2),
            "interval_days": interval_days,
        })

    # 按优先级排序（分数越小越靠前）
    scored.sort(key=lambda x: x["priority_score"])

    result = scored[:limit]
    logger.info(
        "复习调度: user=%s, total=%d, due=%d, limit=%d",
        user_id, len(scored), sum(1 for r in scored if r["due"]), limit,
    )
    return result


def get_review_stats(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
) -> dict:
    """复习统计：待复习数量 vs 已掌握"""
    due = get_due_questions(user_id, bank_id, limit=1000, include_mastered=True)
    total = len(due)
    due_count = sum(1 for d in due if d["due"])
    mastered_count = sum(1 for d in due if d["mastered"])
    not_mastered = total - mastered_count

    return {
        "total_questions_reviewed": total,
        "due_now": due_count,
        "mastered": mastered_count,
        "not_mastered": not_mastered,
        "due_in_1d": sum(1 for d in due if d["days_until_next_review"] <= 1 and not d["due"]),
        "due_in_7d": sum(1 for d in due if d["days_until_next_review"] <= 7),
        "average_ef": round(
            sum(d["ef"] for d in due) / max(len(due), 1), 2
        ) if due else 2.5,
    }


# ── 内部辅助 ──


def _calc_interval(consecutive: int, ef: float, wrongs: int) -> float:
    """
    计算下一次复习间隔（天）。

    SM-2 简化版:
    - 首次正确: 1天
    - 第2次: 3天
    - 第3次: 7天
    - 第4次+: 上次间隔 * EF
    - 曾经错过的题 间隔减半
    """
    idx = min(consecutive, len(INTERVALS) - 1)
    base = INTERVALS[idx]

    # EF 调整
    interval = base * (ef / 2.0)

    # 错题惩罚：曾经错过的题，间隔减半
    if wrongs > 0:
        interval *= 0.5
        # 如果最近还在错，间隔更短
        if consecutive == 0:
            interval = min(interval, 1.0)  # 最近答错 → 1天内复习

    return max(0.5, interval)  # 最少半天


def _get_consecutive(db, question_id: str, user_id: str) -> int:
    """查询某题最近连续正确次数"""
    row = db.fetchone(
        "SELECT consecutive_correct FROM v7_practice_attempts "
        "WHERE question_id = %s AND user_id = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (question_id, user_id),
    )
    return row["consecutive_correct"] if row else 0
