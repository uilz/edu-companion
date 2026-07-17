"""Growth 页面叙事生成器。

从 GrowthRecord 集合生成「你的成长」叙事段落与时间线，
供 Growth 页面与 Profile 页面复用。
"""

from __future__ import annotations


def build_growth_narrative(growth_summary: dict) -> str:
    """生成「你的成长」一句话叙事（V1 不出现积分/等级/百分比）。"""
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)

    if total == 0:
        return "你刚刚开始认识苹果果，完成第一次学习后，这里会开始记录你的成长。"

    parts: list[str] = []
    parts.append(
        "你已经在苹果果完成了第一次学习。" if total == 1 else f"你已经完成了{total}次学习。"
    )

    if streak >= 7:
        parts.append("连续多天的坚持，说明你正在认真对待自己的成长。")
    elif streak >= 3:
        parts.append("过去几天你保持了连续学习，节奏正在形成。")

    return "".join(parts)


def build_growth_timeline(growth_summary: dict) -> list[dict]:
    """从最近 GrowthRecords 构建「最近学会了什么」时间线。"""
    records = growth_summary.get("recent_records", [])
    result: list[dict] = []
    for idx, r in enumerate(records[:5]):
        entry: dict = {
            "id": r.get("id", ""),
            "date": r.get("session_started_at", 0),
            "title": r.get("session_title", ""),
            "summary": r.get("summary", "") or r.get("session_title", ""),
            "is_latest": idx == 0,
        }
        result.append(entry)
    return result
