"""
练习-秘书联动集成 — 错题诊断/掌握停滞/复习提醒/反思引导

在每次 submit_answer() 和 complete_session() 完成后调用，
生成对应提案写入 secretary_proposals 表。

提案类型:
1. practice_error_alert    — 某知识点错题积累达阈值
2. practice_mastery_stuck  — 掌握度停滞不升
3. practice_review_reminder — 到期复习提醒
4. practice_reflection     — 练习后反思引导
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional


logger = logging.getLogger(__name__)

# 阈值配置
ERROR_THRESHOLD = 3          # 同一知识点累积错题数触发诊断
MASTERY_STALL_THRESHOLD = 5  # 连续练习无提升次数触发干预
REVIEW_INTERVAL_DAYS = 3     # 离上次错误超过 N 天触发复习提醒


def check_and_generate_proposals(
    user_id: str,
    session_id: str,
    session_type: str = "practice",
) -> int:
    """
    练习完成后主入口：检查各条件，生成提案。
    返回新生成的提案数。
    """
    count = 0

    try:
        if _check_error_accumulation(user_id, session_id):
            if _generate_error_alert(user_id, session_id):
                count += 1
    except Exception as e:
        logger.debug("错题积累检查失败: %s", e)

    try:
        if _check_mastery_stall(user_id, session_id):
            if _generate_mastery_intervention(user_id, session_id):
                count += 1
    except Exception as e:
        logger.debug("掌握度检查失败: %s", e)

    try:
        if _generate_review_reminder(user_id):
            count += 1
    except Exception as e:
        logger.debug("复习提醒生成失败: %s", e)

    try:
        if session_type != "exam" and _generate_reflection_prompt(user_id, session_id):
            count += 1
    except Exception as e:
        logger.debug("反思引导生成失败: %s", e)

    return count


# ── 条件检测 ──


def _check_error_accumulation(user_id: str, session_id: str) -> bool:
    """检查是否有知识点的错题累积达到阈值"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        """SELECT sq.question_id, q.cognitive_node_ids
           FROM session_questions sq
           JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s AND sq.is_correct = false""",
        (session_id,),
    )

    for r in rows:
        node_ids = r.get("cognitive_node_ids") or []
        for nid in node_ids:
            if not nid:
                continue
            # 统计该知识点的总错题数
            wrong = db.fetchone(
                """SELECT COUNT(*) as cnt FROM practice_attempts pa
                   JOIN session_questions sq ON pa.session_id = sq.session_id
                   JOIN questions q ON sq.question_id = q.id
                   WHERE pa.user_id = %s AND pa.is_wrong = true
                   AND q.cognitive_node_ids @> ARRAY[%s]""",
                (user_id, nid),
            )
            if wrong and wrong["cnt"] >= ERROR_THRESHOLD:
                logger.info("错题累积触发诊断: node=%s, wrong=%d", nid, wrong["cnt"])
                return True
    return False


def _check_mastery_stall(user_id: str, session_id: str) -> bool:
    """检查是否有知识点连续练习多次但未掌握"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 获取本 session 涉及的认知节点
    sq_rows = db.fetchall(
        """SELECT q.cognitive_node_ids
           FROM session_questions sq
           JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s""",
        (session_id,),
    )

    node_ids = set()
    for r in sq_rows:
        for nid in (r.get("cognitive_node_ids") or []):
            if nid:
                node_ids.add(nid)

    for nid in node_ids:
        # 查该节点近 N 次练习的正确率
        attempts = db.fetchall(
            """SELECT is_correct FROM practice_attempts pa
               JOIN session_questions sq ON pa.session_id = sq.session_id
               JOIN questions q ON sq.question_id = q.id
               WHERE pa.user_id = %s
               AND q.cognitive_node_ids @> ARRAY[%s]
               ORDER BY pa.created_at DESC
               LIMIT %s""",
            (user_id, nid, MASTERY_STALL_THRESHOLD),
        )
        if len(attempts) >= MASTERY_STALL_THRESHOLD:
            correct_count = sum(1 for a in attempts if a["is_correct"])
            # 5 次中只对了 ≤1 次 → 掌握停滞
            if correct_count <= 1:
                logger.info("掌握停滞: node=%s, %d attempts, %d correct", nid, len(attempts), correct_count)
                return True
    return False


# ── 提案生成 ──


def _generate_error_alert(user_id: str, session_id: str) -> bool:
    """生成错题诊断提案"""
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.proposal_store import ProposalStore
    from app.domain.secretary.models import Proposal

    db = get_db()

    # 获取本 session 中错题最多的知识点
    rows = db.fetchall(
        """SELECT q.cognitive_node_ids, q.stem
           FROM session_questions sq
           JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s AND sq.is_correct = false
           ORDER BY sq.sort_order
           LIMIT 3""",
        (session_id,),
    )

    if not rows:
        return False

    # 取第一个错题的知识点
    node_id = None
    for r in rows:
        ids = r.get("cognitive_node_ids") or []
        if ids:
            node_id = ids[0]
            break

    # 获取知识点标签
    node_label = node_id or "当前知识点"
    try:
        from app.domain.cognitive import get_repo
        node = get_repo().get_node(node_id, user_id)
        if node and node.label:
            node_label = node.label
    except Exception:
        pass

    # 统计该节点总错题数
    wrong_count = 0
    if node_id:
        wr = db.fetchone(
            """SELECT COUNT(*) as cnt FROM practice_attempts pa
               JOIN session_questions sq ON pa.session_id = sq.session_id
               JOIN questions q ON sq.question_id = q.id
               WHERE pa.user_id = %s AND pa.is_wrong = true
               AND q.cognitive_node_ids @> ARRAY[%s]""",
            (user_id, node_id),
        )
        if wr:
            wrong_count = wr["cnt"]

    proposal = Proposal(
        emoji="📌",
        title=f"「{node_label}」已错 {wrong_count} 题",
        description=f"你在「{node_label}」上已经错了 {wrong_count} 道题了。要不要我帮你梳理一下核心概念？",
        action_type="practice_error_alert",
        payload={
            "kp_id": node_id or "",
            "node_label": node_label,
            "wrong_count": wrong_count,
            "session_id": session_id,
            "source_question": rows[0]["stem"][:80] if rows else "",
        },
        priority=1,
        generated_by="practice_secretary",
    )

    store = ProposalStore()
    store.save_proposal(proposal, user_id, session_id)
    return True


def _generate_mastery_intervention(user_id: str, session_id: str) -> bool:
    """生成掌握度停滞干预提案"""
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.proposal_store import ProposalStore
    from app.domain.secretary.models import Proposal

    db = get_db()

    sq_rows = db.fetchall(
        """SELECT q.cognitive_node_ids
           FROM session_questions sq
           JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s""",
        (session_id,),
    )

    node_id = None
    for r in sq_rows:
        ids = r.get("cognitive_node_ids") or []
        if ids:
            node_id = ids[0]
            break

    node_label = node_id or "这个知识点"
    try:
        from app.domain.cognitive import get_repo
        node = get_repo().get_node(node_id, user_id) if node_id else None
        if node and node.label:
            node_label = node.label
    except Exception:
        pass

    proposal = Proposal(
        emoji="🤔",
        title=f"「{node_label}」遇到瓶颈了",
        description=f"你在「{node_label}」上练习了好几次，但正确率提升不明显。要不要换种方式？我可以讲解、出题，或者帮你梳理知识结构。",
        action_type="practice_mastery_stuck",
        payload={
            "kp_id": node_id or "",
            "node_label": node_label,
            "session_id": session_id,
        },
        priority=2,
        generated_by="practice_secretary",
    )

    store = ProposalStore()
    store.save_proposal(proposal, user_id, session_id)
    return True


def _generate_review_reminder(user_id: str) -> bool:
    """生成复习提醒提案"""
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.proposal_store import ProposalStore
    from app.domain.secretary.models import Proposal

    db = get_db()

    # 统计待复习的错题
    due = db.fetchone(
        """SELECT COUNT(*) as cnt FROM practice_attempts pa
           WHERE pa.user_id = %s AND pa.is_wrong = true
           AND pa.mastered = false
           AND pa.created_at < NOW() - INTERVAL '%s days'""",
        (user_id, REVIEW_INTERVAL_DAYS),
    )

    due_count = due["cnt"] if due else 0
    if due_count < 1:
        return False

    # 查有没有同类型的 pending 提案（去重）
    existing = db.fetchone(
        """SELECT id FROM secretary_proposals
           WHERE user_id = %s AND action_type = 'practice_review_reminder'
           AND status = 'pending' LIMIT 1""",
        (user_id,),
    )
    if existing:
        return False  # 已存在同类提案，不重复

    proposal = Proposal(
        emoji="📚",
        title=f"你有 {due_count} 道错题该复习了",
        description=f"有些错题已经过了 {REVIEW_INTERVAL_DAYS} 天没有复习了。趁还没忘记，花几分钟回顾一下吧。",
        action_type="practice_review_reminder",
        payload={
            "due_count": due_count,
            "days_threshold": REVIEW_INTERVAL_DAYS,
        },
        priority=2,
        generated_by="practice_secretary",
    )

    store = ProposalStore()
    store.save_proposal(proposal, user_id)
    return True


def _generate_reflection_prompt(user_id: str, session_id: str) -> bool:
    """生成练习后反思引导"""
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.proposal_store import ProposalStore
    from app.domain.secretary.models import Proposal

    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return False

    total = session.get("total_count", 0)
    if total < 3:
        return False  # 题太少不需要反思

    # 查同 session 是否有反思提案
    existing = db.fetchone(
        """SELECT id FROM secretary_proposals
           WHERE user_id = %s AND action_type = 'practice_reflection'
           AND payload->>'session_id' = %s LIMIT 1""",
        (user_id, session_id),
    )
    if existing:
        return False

    correct = session.get("correct_count", 0)
    wrong = session.get("wrong_count", 0)

    if wrong == 0:
        description = "这次练习全对了！你觉得哪道题最有挑战？有没有什么新的发现？"
    elif correct >= wrong:
        description = "做得不错！回顾一下，有没有哪道题让你印象特别深刻？"
    else:
        description = "这次错得有点多哦。别灰心，我们来看看问题出在哪里——你觉得主要是概念不清还是粗心？"

    proposal = Proposal(
        emoji="💭",
        title="练习后的小反思",
        description=description,
        action_type="practice_reflection",
        payload={
            "session_id": session_id,
            "correct": correct,
            "wrong": wrong,
            "total": total,
        },
        priority=3,
        generated_by="practice_secretary",
    )

    store = ProposalStore()
    store.save_proposal(proposal, user_id, session_id)
    return True
