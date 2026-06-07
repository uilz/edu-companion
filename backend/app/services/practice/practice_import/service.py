"""题库导入 — 预览/AI 修正/认知节点匹配/确认/历史"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from shared.constants import DEFAULT_USER_ID
from .parser import (
    parse_file, ai_correct_question, match_cognitive_nodes,
    _infer_type_from_analysis, _estimate_difficulty,
)

logger = logging.getLogger(__name__)


def preview_import(
    file_path: str,
    file_type: str = "",
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
) -> dict:
    """
    解析文件 → 预览（含 AI 修正 + 认知节点匹配）
    """
    questions = parse_file(file_path, file_type)

    total = len(questions)
    high_conf = 0
    low_conf = 0

    for q in questions:
        q = ai_correct_question(q)
        if q.get("confidence", 0) >= 0.8:
            high_conf += 1
        else:
            low_conf += 1

        node_ids = match_cognitive_nodes(q, user_id)
        q["suggested_node_ids"] = node_ids

    return {
        "questions": questions,
        "stats": {"total": total, "high_confidence": high_conf, "low_confidence": low_conf},
        "source_file": Path(file_path).name,
        "suggestions": {"suggested_bank": bank_id or ""},
    }


def confirm_import(
    questions: list[dict],
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """确认导入题目到题库"""
    from app.db.database import get_db
    from app.services.practice.practice_question_crud import add_question
    db = get_db()

    imported = 0
    errors = []
    saved_questions = []

    for i, q in enumerate(questions):
        try:
            stem = (q.get("stem") or "").strip()
            if not stem:
                errors.append({"index": i, "reason": "题干为空"})
                continue

            qtype = q.get("question_type") or _infer_type_from_analysis(q)
            if qtype not in ("single", "multiple", "judge", "fill", "essay"):
                qtype = "single"

            answer_raw = q.get("answer", "")
            if isinstance(answer_raw, str):
                answer_raw = answer_raw.strip().upper()
                if qtype in ("single", "multiple"):
                    answer_list = [ch for ch in answer_raw if ch.isalpha()]
                else:
                    answer_list = [answer_raw]
            elif isinstance(answer_raw, list):
                answer_list = answer_raw
            else:
                answer_list = [str(answer_raw)]

            if not answer_list:
                errors.append({"index": i, "reason": "答案为空", "stem": stem[:50]})
                continue

            options_raw = q.get("options") or []
            options_standard = []
            for opt in options_raw:
                if isinstance(opt, dict):
                    options_standard.append({
                        "letter": opt.get("label", opt.get("letter", "")),
                        "text": opt.get("content", opt.get("text", "")),
                        "is_correct": opt.get("is_correct", False),
                    })
                elif isinstance(opt, str):
                    options_standard.append({
                        "letter": chr(65 + len(options_standard)),
                        "text": opt, "is_correct": False,
                    })

            saved_q = add_question(
                bank_id=bank_id, user_id=user_id,
                question_type=qtype, stem=stem, answer=answer_list,
                options=options_standard if options_standard else None,
                analysis=q.get("analysis", ""),
                difficulty=_estimate_difficulty(q),
                cognitive_node_ids=q.get("suggested_node_ids") or q.get("cognitive_node_ids"),
                source="import",
                metadata={
                    "import_confidence": q.get("confidence", 0.5),
                    "ai_corrected": q.get("ai_corrected", False),
                    "source_line": q.get("source_line", 0),
                },
            )
            saved_questions.append(saved_q)
            imported += 1
        except Exception as e:
            logger.warning("导入第 %d 题失败: %s", i, e)
            errors.append({"index": i, "reason": str(e)})

    return {
        "imported": imported, "errors": errors,
        "questions": saved_questions, "bank_id": bank_id,
        "error_count": len(errors),
    }


def get_import_history(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """获取导入历史"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["q.metadata->>'import_batch' IS NOT NULL", "q.deleted_at IS NULL"]
    params = []
    if bank_id:
        conditions.append("q.bank_id = %s")
        params.append(bank_id)
    where = " AND ".join(conditions)

    count_row = db.fetchone(
        f"SELECT COUNT(DISTINCT q.metadata->>'import_batch') as cnt FROM questions q WHERE {where}",
        tuple(params) if params else None,
    )
    total = count_row["cnt"] if count_row else 0

    rows = db.fetchall(
        f"""SELECT q.metadata->>'import_batch' as batch_id, q.bank_id,
                  MIN(q.created_at) as imported_at,
                  COUNT(*) as question_count,
                  COUNT(*) FILTER (WHERE q.status = 'active') as active_count
           FROM questions q WHERE {where}
           GROUP BY batch_id, q.bank_id
           ORDER BY imported_at DESC LIMIT %s OFFSET %s""",
        tuple(params + [limit, offset]) if params else (limit, offset),
    )

    items = []
    for r in rows:
        bank = db.fetchone("SELECT name FROM question_banks WHERE id = %s", (r["bank_id"],))
        items.append({
            "batch_id": r["batch_id"],
            "bank_id": r["bank_id"],
            "bank_name": bank["name"] if bank else "",
            "imported_at": _safe_iso(r.get("imported_at")),
            "question_count": r["question_count"],
            "active_count": r["active_count"],
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _safe_iso(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
