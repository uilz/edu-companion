"""自信度校准报告服务

按学科/时间段聚合 practice_attempts 的 confidence_before 与正确性，
输出偏差趋势、均值与学习建议。
"""
from __future__ import annotations

from datetime import datetime, timedelta


def get_confidence_report(
    user_id: str,
    subject: str | None = None,
    days: int = 30,
) -> dict:
    """自信度校准报告：按学科的偏差趋势、均值、建议。"""
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
