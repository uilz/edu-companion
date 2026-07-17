"""Growth 页面叙事生成器。

从 GrowthRecord 集合生成「你的成长」叙事段落与时间线，
供 Growth 页面与 Profile 页面复用。
"""

from __future__ import annotations

from datetime import datetime


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


def build_growth_insights(growth_summary: dict) -> list[dict]:
    """从 GrowthRecords 生成「苹果果的观察」洞察卡片。

    纯 rule-based，不调 AI。洞察类型：
    - skill_progress: 某个技能掌握度显著提升
    - time_pattern: 用户偏好的学习时间
    - consistency: 连续学习天数
    """
    records = growth_summary.get("recent_records", [])
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    insights: list[dict] = []

    if total == 0:
        return insights

    # 1. 技能进步洞察
    for r in records:
        for sg in r.get("skill_gains", []):
            after = sg.get("after", 0)
            delta = sg.get("delta", 0)
            skill = sg.get("skill", "")
            if after >= 0.6 and delta >= 0.3 and skill:
                insights.append({
                    "type": "skill_progress",
                    "text": f"你对「{skill}」的感觉在变——从薄弱到比较熟了。",
                    "icon": "📈",
                })
                break
        if insights:
            break

    # 2. 时间模式洞察
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_counts: dict[int, int] = {}
    for r in records:
        ts = r.get("session_started_at", 0)
        if ts:
            wd = datetime.fromtimestamp(ts).weekday()
            weekday_counts[wd] = weekday_counts.get(wd, 0) + 1
    if len(weekday_counts) >= 2:
        top = sorted(weekday_counts.items(), key=lambda x: -x[1])[:2]
        top_names = [weekdays[i] for i, _ in top]
        insights.append({
            "type": "time_pattern",
            "text": f"你偏好{top_names[0]}和{top_names[1]}学习，这是你的节奏。",
            "icon": "⏰",
        })

    # 3. 连续性洞察
    if streak >= 3:
        insights.append({
            "type": "consistency",
            "text": f"你已经连续{streak}天都在学习了，坚持本身就在告诉你：这件事对你很重要。",
            "icon": "🔥",
        })

    return insights[:4]


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
