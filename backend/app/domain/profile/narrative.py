"""Profile 叙事生成器。

从 LearnerModel + GrowthSummary 生成「苹果果眼中的你」镜像叙事，
对齐 /vision/preview.html 中 Narrative.profileMirror() 与 Narrative.profilePrefs()。
"""

from __future__ import annotations

import html
from datetime import datetime


def _esc(s: str) -> str:
    """转义用户数据中的 HTML 标签，防止 XSS。"""
    return html.escape(s, quote=True)


def _primary_topic(growth_summary: dict) -> str:
    """从最近 GrowthRecords 提取主要学习主题。"""
    records = growth_summary.get("recent_records", [])
    for r in records:
        for sg in r.get("skill_gains", []):
            skill = sg.get("skill", "")
            if skill:
                return skill
        title = r.get("session_title", "")
        if title:
            return title
    return ""


def _weekday_pattern(growth_summary: dict) -> str | None:
    """提取用户偏好的学习星期（对齐 Vision 行 557「周二和周四」）。

    至少出现 2 个不同学习日，且 top1 频次 >= 2 才返回，避免单次偶然。
    """
    records = growth_summary.get("recent_records", [])
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    counts: dict[int, int] = {}
    for r in records:
        ts = r.get("session_started_at", 0)
        if ts:
            wd = datetime.fromtimestamp(ts).weekday()
            counts[wd] = counts.get(wd, 0) + 1
    if len(counts) < 2:
        return None
    top = sorted(counts.items(), key=lambda x: -x[1])[:2]
    if top[0][1] < 2:
        return None
    names = [weekdays[i] for i, _ in top]
    return "和".join(names)


def _first_record_quote(first_record: dict | None) -> str | None:
    """从第一条 GrowthRecord 提取用户引述用于起点对比。

    优先 reflection_snippet（最像用户自己的话），次选 summary。
    返回引述字符串（不含引号），长度 ≤ 35 字。
    """
    if not first_record:
        return None
    snippet = (first_record.get("reflection_snippet") or "").strip()
    if snippet and len(snippet) > 5:
        quote = snippet[:35]
        if len(snippet) > 35:
            quote += "…"
        return quote
    summary = (first_record.get("summary") or "").strip()
    if summary and len(summary) > 5:
        quote = summary[:35]
        if len(summary) > 35:
            quote += "…"
        return quote
    return None


def _build_contrast_sentence(
    primary: str,
    primary_text: str,
    first_quote: str | None,
    is_long_term: bool,
) -> str:
    """生成起点对比句，优先使用 first_record 引述。

    is_long_term: True 用于 ≥15 次（「三个月前你…」），False 用于 <15 次（「这一个月你…」）。
    """
    if not primary:
        if is_long_term:
            return (
                "还记得你第一天开始学习的样子吗。"
                "一路走来，你已经掌握了很多之前觉得难的内容。"
            )
        return (
            "还记得刚开始的时候吗？到现在，你已经能自己解出不少问题了。"
        )

    if first_quote:
        return (
            f"还记得你刚开始学{primary_text}时"
            f"<span class=\"highlight\">\u201c{_esc(first_quote)}\u201d</span>。"
            f"今天你已经能熟练运用了。"
        )

    if is_long_term:
        return (
            f"三个月前你<span class=\"highlight\">刚开始接触{primary_text}</span>。"
            "今天你已经能熟练运用了。"
        )
    return (
        f"你<span class=\"highlight\">一开始觉得{primary_text}很抽象</span>，"
        f"到现在能自己算出结果。"
    )


def build_mirror_narrative(
    profile: dict,
    growth_summary: dict,
) -> str:
    """生成「苹果果眼中的你」镜像叙事。

    返回带 <span class="highlight"> 标记的 HTML 字符串（已转义用户数据）。
    三段式：起点对比（Memory 驱动）→ 学习偏好 → 状态观察。

    对齐 Vision preview.html (行 538-562) Narrative.profileMirror。
    """
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    style = profile.get("learning_style", "")
    subjects = profile.get("subjects", []) or []
    topic = _primary_topic(growth_summary)
    first_record = growth_summary.get("first_record")

    first_quote = _first_record_quote(first_record)

    # ── 学习偏好映射 ──────────────────────────
    style_map: dict[str, str] = {
        "kinesthetic": "更喜欢先动手算一遍，再回来看定义",
        "reading": "更喜欢先看例子，再理解定义",
        "visual": "更喜欢通过图表和示意图来理解概念",
        "auditory": "更喜欢通过听讲和讨论来吸收知识",
    }
    style_text = style_map.get(style, "有自己独特的学习节奏")

    # ── 最近在学的学科 / 主题 ──
    # 优先用最近 skill（更精准），兜底用 subjects
    primary = topic or (subjects[0] if subjects else "")
    primary_text = _esc(primary) if primary else "还在探索不同领域"

    # ── 学习时间模式（Vision 行 557） ──
    weekday_text = _weekday_pattern(growth_summary)

    # ── 三段式生成 ────────────────────────────
    parts: list[str] = []

    if total == 0:
        parts.append(
            "我们刚开始。你最近在探索，我还在慢慢了解你的节奏。"
        )
        parts.append(f"你{style_text}。")
        return " ".join(parts)

    if total <= 2:
        # Vision 行 542-543：刚开始，还在了解节奏
        parts.append(
            f"我们刚开始。你最近在学<span class=\"highlight\">{primary_text}</span>，"
            "我还在慢慢了解你的节奏。"
        )
        parts.append(f"你{style_text}。")
    elif total < 15:
        # Vision 行 544-550：这一个月，起点对比 + 学习偏好
        parts.append(_build_contrast_sentence(primary, primary_text, first_quote, is_long_term=False))
        parts.append(f"你{style_text}。")
    else:
        # Vision 行 551-558：三个月，强烈起点对比 + 主动追问 + 时间模式
        parts.append(_build_contrast_sentence(primary, primary_text, first_quote, is_long_term=True))
        parts.append(
            '你从绕着走，到现在会主动追问\u201c为什么\u201d。'
        )
        if weekday_text:
            parts.append(f"你每周{weekday_text}学习时间最长。")

    # ── 状态观察 ─────────────────────────────
    if streak >= 14:
        parts.append("过去这段时间，你的学习节奏非常稳定。")
    elif streak >= 7:
        parts.append("过去这段时间，你正在养成稳定的学习习惯。")
    elif streak >= 3:
        parts.append("最近你开始了连续学习，是个不错的开始。")

    return " ".join(parts)


def build_prefs(
    profile: dict,
    growth_summary: dict,
    first_record: dict | None = None,
) -> list[dict]:
    """生成「关于你的学习」偏好网格。

    返回 4 条具象偏好，对齐 preview.html 的 pref-grid：
      学习方式 / 学习节奏 / 最近在学 / 已经一起走过

    「已经一起走过」增加相对时间感（对齐 GAP.md「动态相对时间标签」）。
    """
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    style = profile.get("learning_style", "")
    subjects = profile.get("subjects", []) or []
    records = growth_summary.get("recent_records", []) or []

    # 学习方式
    style_map: dict[str, str] = {
        "kinesthetic": "先实践，再看理论",
        "reading": "先看例子，再看定义",
        "visual": "通过图表理解概念",
        "auditory": "通过听讲吸收知识",
    }
    style_value = style_map.get(style, "还在观察中")

    # 学习节奏
    if streak >= 7:
        pace = f"本周 {streak} 天左右"
    elif streak >= 3:
        pace = "这几天都在学"
    elif streak > 0:
        pace = "正在开始"
    else:
        pace = "刚开始建立节奏"

    # 最近在学：优先 skill，兜底 subject
    topic = _primary_topic(growth_summary)
    recent_value = _esc(topic) if topic else (
        _esc(subjects[0]) if subjects else "还在探索不同领域"
    )

    # 已经一起走过：相对时间为主表达，次数为 fallback
    # 优先使用 first_record（完整历史的真实起点），兜底用 recent_records
    if first_record and first_record.get("session_started_at"):
        earliest_ts = first_record["session_started_at"]
    else:
        earliest_ts = _earliest_started_at(records)
    span_label = _relative_span(earliest_ts) if earliest_ts else ""

    if total == 0:
        sessions_text = "刚认识"
    elif total == 1:
        sessions_text = "刚刚开始"
    elif span_label:
        sessions_text = f"一起走过 {span_label}"
    else:
        sessions_text = f"{total} 次学习"

    return [
        {"label": "学习方式", "value": style_value},
        {"label": "学习节奏", "value": pace},
        {"label": "最近在学", "value": recent_value},
        {"label": "已经一起走过", "value": sessions_text},
    ]


def _earliest_started_at(records: list[dict]) -> int:
    """从记录列表取最早的 session_started_at。"""
    timestamps = [
        r.get("session_started_at", 0)
        for r in records
        if r.get("session_started_at", 0)
    ]
    return min(timestamps) if timestamps else 0


def _relative_span(earliest_ts: int) -> str:
    """从最早学习时间生成「N 周 / N 个月 / N 年」相对标签。"""
    import time as _time
    now = _time.time()
    day_diff = max(0, int((now - earliest_ts) // 86400))
    if day_diff < 14:
        return ""  # 太短，不显示相对时间
    if day_diff < 60:
        weeks = day_diff // 7
        return f"{weeks} 周"
    months = day_diff // 30
    if months < 12:
        return f"{months} 个月"
    years = day_diff // 365
    return f"{years} 年"
