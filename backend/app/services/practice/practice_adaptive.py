"""
自适应选题算法

策略（分层优先级）：
1. 错题优先 — 错误次数多的权重最高
2. 新题穿插 — 从未做过的题目保证一定比例
3. 薄弱知识点 — 通过 cognitive_node_ids 加权
4. 难度自适应 — 根据近期正确率调整目标难度
5. Bloom 层次覆盖 — 保证各认知层次都有

选择逻辑委托给 adaptive_scorer.py 中的纯函数。
"""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from app.services.practice.adaptive_scorer import (
    compute_node_mastery,
    has_mastery_data,
    filter_by_mastery,
    pick_from_pool,
    cold_start_select,
    pick_difficult_questions,
    ensure_bloom_coverage,
    select_by_mastery_layers,
    safe_json as _safe_json,
)

logger = logging.getLogger(__name__)


def _ensure_bloom_coverage(
    questions: list[dict],
    distribution: Optional[dict[str, int]] = None,
    full_pool: Optional[list[dict]] = None,
) -> list[dict]:
    """保证 Bloom 层次覆盖 — 委托给 adaptive_scorer"""
    return ensure_bloom_coverage(questions, distribution, full_pool)


# ══════════════════════════════════════════════════════════════
# 自适应算法 — 6:3:1 分层 + AI fallback
# ══════════════════════════════════════════════════════════════


def adaptive_select(
    bank_id: str,
    user_id: str,
    count: int = 10,
    mode: str = "adaptive",
    exclude_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
    enable_ai_fallback: bool = True,
    subject_hint: Optional[str] = None,
) -> list[dict]:
    """
    自适应选题（6:3:1 分层 + AI fallback）。

    参数:
        bank_id: 题库ID
        user_id: 用户ID
        count: 选题数量
        mode: adaptive / review / challenge / new
        exclude_ids: 排除的题目ID
        cognitive_node_ids: 限定的知识点范围
        enable_ai_fallback: 题目不足时是否 AI 生成补足
        subject_hint: AI fallback 时使用的学科提示
    """
    from app.infrastructure.db.database import get_db
    db = get_db()

    exclude = set(exclude_ids or [])

    # 1. 获取题库所有活跃题目
    questions = db.fetchall(
        """SELECT q.* FROM questions q
           WHERE q.bank_id = %s AND q.deleted_at IS NULL AND q.status = 'active'
           AND q.is_slashed = false
           ORDER BY q.created_at DESC""",
        (bank_id,),
    )

    if not questions:
        logger.info("题库 %s 无可用题目，尝试 AI fallback", bank_id)
        return _ai_fallback(bank_id, user_id, count, cognitive_node_ids, subject_hint=subject_hint) if enable_ai_fallback else []

    # 2. 过滤排除 + 知识点范围
    pool = [q for q in questions if q["id"] not in exclude]
    if cognitive_node_ids:
        pool = [
            q for q in pool
            if q.get("cognitive_node_ids") and any(
                cid in (q["cognitive_node_ids"] or []) for cid in cognitive_node_ids
            )
        ]

    if not pool:
        logger.info("过滤后无可用题目 bank=%s, 尝试 AI fallback", bank_id)
        return _ai_fallback(bank_id, user_id, count, cognitive_node_ids, subject_hint=subject_hint) if enable_ai_fallback else []

    # 3. 获取历史作答统计 + 按知识点计算掌握度
    qids = [q["id"] for q in pool]
    stats_raw = db.fetchall(
        """SELECT question_id,
                  COUNT(*) as total,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrongs,
                  MAX(created_at) as last_done
           FROM practice_attempts
           WHERE question_id = ANY(%s) AND user_id = %s
           GROUP BY question_id""",
        (qids, user_id),
    )
    stats_map = {r["question_id"]: r for r in stats_raw}

    # 4. 计算每个知识点的掌握度（从所有题目的统计推算）
    node_mastery = _compute_node_mastery(pool, stats_map)

    # 5. 6:3:1 分层选题
    selected = _select_by_mastery_layers(
        pool=pool,
        stats_map=stats_map,
        node_mastery=node_mastery,
        count=count,
        mode=mode,
    )

    # 6. Bloom 覆盖（主动重平衡）
    selected = _ensure_bloom_coverage(selected, full_pool=pool)

    # 7. 脱敏
    result = []
    for q in selected:
        item = _row_to_safe(q)
        stat = stats_map.get(q["id"], {})
        item["_attempts"] = stat.get("total", 0) or 0
        item["_wrongs"] = stat.get("wrongs", 0) or 0
        result.append(item)

    # 8. AI fallback 补足（如果选的还不够）
    if len(result) < count and enable_ai_fallback:
        shortage = count - len(result)
        logger.info("AI fallback 补题: %d 道不足", shortage)
        ai_questions = _ai_fallback(bank_id, user_id, shortage, cognitive_node_ids, subject_hint=subject_hint)
        if ai_questions:
            result.extend(ai_questions)

    logger.info(
        "adaptive: bank=%s, mode=%s, pool=%d, selected=%d%s",
        bank_id, mode, len(pool), len(result),
        " (with AI fallback)" if len(result) > len(selected) else "",
    )
    return result


def _compute_node_mastery(
    questions: list[dict],
    stats_map: dict[str, dict],
) -> dict[str, float]:
    """统计每个知识点的掌握度（0~1）— 委托给 adaptive_scorer"""
    return compute_node_mastery(questions, stats_map)


def _select_by_mastery_layers(
    pool: list[dict],
    stats_map: dict[str, dict],
    node_mastery: dict[str, float],
    count: int,
    mode: str = "adaptive",
    epsilon: float = 0.1,
) -> list[dict]:
    """按掌握度分层选题 — 委托给 adaptive_scorer"""
    return select_by_mastery_layers(pool, stats_map, node_mastery, count, mode, epsilon)


def _filter_by_mastery(
    questions: list[dict],
    node_mastery: dict[str, float],
    min_mastery: float = 0.0,
    max_mastery: float = 1.0,
) -> list[dict]:
    """按掌握度范围过滤题目 — 委托给 adaptive_scorer"""
    return filter_by_mastery(questions, node_mastery, min_mastery, max_mastery)


def _has_mastery_data(q: dict, node_mastery: dict[str, float]) -> bool:
    """检查题目是否有掌握度数据 — 委托给 adaptive_scorer"""
    return has_mastery_data(q, node_mastery)


def _pick_from_pool(
    pool: list[dict],
    stats_map: dict[str, dict],
    count: int,
    min_attempts: int = 0,
    max_attempts: int = 999,
    min_mastery: float = 0.0,
    max_mastery: float = 1.0,
    node_mastery: Optional[dict[str, float]] = None,
    epsilon: float = 0.1,
) -> list[dict]:
    """从候选池中按条件选题 — 委托给 adaptive_scorer"""
    return pick_from_pool(pool, stats_map, count, min_attempts, max_attempts, max_mastery, min_mastery, node_mastery)


def _pick_difficult_questions(pool: list[dict], count: int) -> list[dict]:
    """挑战模式：选高难度题 — 委托给 adaptive_scorer"""
    return pick_difficult_questions(pool, count)


def _cold_start_select(pool: list[dict], stats_map: dict[str, dict], count: int) -> list[dict]:
    """冷启动选题 — 委托给 adaptive_scorer"""
    return cold_start_select(pool, stats_map, count)


def _ai_fallback(
    bank_id: str,
    user_id: str,
    count: int,
    cognitive_node_ids: Optional[list[str]] = None,
    subject_hint: Optional[str] = None,
) -> list[dict]:
    """AI 补题：当题库不够时自动生成"""
    try:
        from app.services.practice.practice_question_gen import generate_and_save

        skill_id = cognitive_node_ids[0] if cognitive_node_ids else ""

        # 推断学科：优先使用外部提示，其次从 cognitive_node_ids 推断，最后回退
        subject = subject_hint or ""
        if not subject and cognitive_node_ids:
            # 尝试从认知节点查找学科信息
            try:
                from app.domain.cognitive import get_repo
                for nid in cognitive_node_ids:
                    node = get_repo().get_node(nid, user_id)
                    if node and hasattr(node, 'subject') and node.subject:
                        subject = node.subject
                        break
            except Exception:
                pass
        if not subject:
            # 从题库元数据推测
            try:
                from app.infrastructure.db.database import get_db
                db = get_db()
                bank = db.fetchone(
                    "SELECT metadata FROM question_banks WHERE id = %s",
                    (bank_id,),
                )
                if bank:
                    meta = _safe_json(bank.get("metadata"), {})
                    subject = meta.get("subject", "") or meta.get("topic", "") or ""
            except Exception:
                pass
        if not subject:
            subject = "数学"  # 最终回退

        saved = generate_and_save(
            bank_id=bank_id,
            user_id=user_id,
            subject=subject,
            skill_id=skill_id,
            count=min(count, 5),
            content_type="choice",
        )
        # 转成 safe 格式
        result = []
        for q in saved:
            result.append({
                "id": q["id"],
                "bank_id": bank_id,
                "question_type": q.get("question_type", "single"),
                "stem": q.get("stem", ""),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", 3),
                "cognitive_node_ids": q.get("cognitive_node_ids") or [],
                "metadata": q.get("metadata", {}),
            })
        logger.info("AI fallback 生成了 %d 道题", len(result))
        return result
    except Exception as e:
        logger.warning("AI fallback 失败: %s", e)
        return []


def _row_to_safe(row: dict) -> dict:
    """将数据库行转成安全返回（不含答案）"""
    from app.services.practice.practice_question_bank import _safe_json
    return {
        "id": row["id"],
        "bank_id": row["bank_id"],
        "question_type": row["question_type"],
        "stem": row["stem"],
        "options": _safe_json(row.get("options"), []),
        "difficulty": row.get("difficulty", 3),
        "cognitive_node_ids": row.get("cognitive_node_ids") or [],
        "metadata": _safe_json(row.get("metadata"), {}),
    }
