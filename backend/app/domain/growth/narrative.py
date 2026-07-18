"""Growth 页面叙事生成器。

从 GrowthRecord 集合生成「你的成长」叙事段落与时间线，
供 Growth 页面与 Profile 页面复用。
"""

from __future__ import annotations

from datetime import datetime


def build_growth_narrative(growth_summary: dict) -> str:
    """生成「你的成长」一句话叙事。

    对齐 Vision preview.html (行 564-568) Narrative.growthNarrative：
      - sessionsDone ≤ 2：刚开始的样子，每一次都更了解
      - sessionsDone < 15：这一个月感觉在变（从觉得难到慢慢上手）
      - sessionsDone ≥ 15：三个月完全不一样了（真切走过的）

    V1 不出现积分/等级/百分比，只用人话讲「时间在流动，你在变」。
    """
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    topic = _primary_topic(growth_summary)

    if total == 0:
        return "你刚刚开始认识苹果果，完成第一次学习后，这里会开始记录你的成长。"

    parts: list[str] = []

    # ── 时间深度分档（对齐 Vision 3 档） ──
    if total <= 2:
        # Vision 行 566：这是我们刚开始的样子
        parts.append("这是我们刚开始的样子。每一次学习，我都会更了解你一点。")
    elif total < 15:
        # Vision 行 567：这一个月，感觉在变（从难到上手）
        if topic:
            parts.append(
                f"你已经一起学了 {total} 次。"
                f"这一个月，你对「{topic}」的感觉在变。从觉得难，到慢慢上手。"
            )
        else:
            parts.append(
                f"你已经一起学了 {total} 次。"
                "这一个月，你的感觉在变。从觉得难，到慢慢上手。"
            )
    else:
        # Vision 行 568：三个月，完全不一样了
        if topic:
            parts.append(
                f"你已经一起学了 {total} 次。三个月。"
                f"你对「{topic}」的感觉完全不一样了。"
                "这不是分数能说的，是你真真切切走过来的。"
            )
        else:
            parts.append(
                f"你已经一起学了 {total} 次。三个月走过来了。"
                "这不是分数能说的，是你真真切切走过来的。"
            )

    # ── streak 维度 ──
    if streak >= 7 and total >= 3:
        parts.append("连续多天的坚持，你自己可能没注意到——但我知道。")
    elif streak >= 3 and total >= 3:
        parts.append("过去几天你保持了连续学习，节奏正在形成。")

    # ── 第一句话记忆（长期用户才引用，体现"我记得你开始的样子"） ──
    if total >= 15:
        first_record = growth_summary.get("first_record")
        if first_record:
            quote = (
                (first_record.get("reflection_snippet") or "").strip()
                or (first_record.get("summary") or "").strip()
            )
            if quote and len(quote) > 5:
                if len(quote) > 35:
                    quote = quote[:35] + "…"
                parts.append(
                    f"还记得你开始的时候说："
                    f"“{quote}”。"
                    f"今天你已经完全不一样了。"
                )

    return "".join(parts)


def _primary_topic(growth_summary: dict) -> str:
    """从最近 GrowthRecords 提取主要学习主题（取最近一条记录的第一个 skill）。"""
    records = growth_summary.get("recent_records", [])
    for r in records:
        skill_gains = r.get("skill_gains", [])
        if skill_gains:
            skill = skill_gains[0].get("skill", "")
            if skill:
                return skill
        # 兜底：用 session_title 提取主题，清理常见前缀
        title = r.get("session_title", "")
        if title:
            # 去掉 "练习:" / "测验:" / "主题:" 等前缀
            for sep in (":", "：", " ", "　"):
                if sep in title:
                    parts = title.split(sep, 1)
                    if len(parts) > 1 and len(parts[0]) <= 4:
                        title = parts[1].strip()
                        break
            if title:
                return title
    return ""


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

    # 4. 学习次数里程碑（≥3 次时显示，让用户感到被计数）
    if total >= 3:
        insights.append({
            "type": "milestone",
            "text": f"你已经完成了 {total} 次学习。每一次，都让你离自己想成为的样子更近一点。",
            "icon": "🍎",
        })

    return insights[:4]


def build_growth_timeline(growth_summary: dict) -> list[dict]:
    """从最近 GrowthRecords 构建「最近学会了什么」时间线。"""
    records = growth_summary.get("recent_records", [])
    result: list[dict] = []
    for idx, r in enumerate(records[:5]):
        # summary 优先级：reflection_snippet（用户自己的话）→ summary → session_title
        summary = (
            r.get("reflection_snippet", "")
            or r.get("summary", "")
            or r.get("session_title", "")
        )
        entry: dict = {
            "id": r.get("id", ""),
            "date": r.get("session_started_at", 0),
            "title": r.get("session_title", ""),
            "summary": summary,
            "is_latest": idx == 0,
        }
        result.append(entry)
    return result
