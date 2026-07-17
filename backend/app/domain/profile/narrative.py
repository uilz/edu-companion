"""Profile 叙事生成器。

从 LearnerModel + GrowthSummary 生成「苹果果眼中的你」镜像叙事，
对齐 /vision/preview.html 中 Narrative.profileMirror() 与 Narrative.profilePrefs()。
"""

from __future__ import annotations

import html


def _esc(s: str) -> str:
    """转义用户数据中的 HTML 标签，防止 XSS。"""
    return html.escape(s, quote=True)


def build_mirror_narrative(
    profile: dict,
    growth_summary: dict,
) -> str:
    """生成「苹果果眼中的你」镜像叙事。

    返回带 <span class="highlight"> 标记的 HTML 字符串（已转义用户数据）。
    三段式：起点对比 → 学习偏好 → 状态观察。
    """
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    style = profile.get("learning_style", "")
    subjects = profile.get("subjects", []) or []

    # ── 学习偏好映射 ──────────────────────────
    style_map: dict[str, str] = {
        "kinesthetic": "更喜欢先动手算一遍，再回来看定义",
        "reading": "更喜欢先看例子，再理解定义",
        "visual": "更喜欢通过图表和示意图来理解概念",
        "auditory": "更喜欢通过听讲和讨论来吸收知识",
    }
    style_text = style_map.get(style, "有自己独特的学习节奏")

    # ── 最近在学的学科 ──
    subject_text = _esc(subjects[0]) if subjects else "还在探索不同领域"

    # ── 三段式生成 ────────────────────────────
    parts: list[str] = []

    if total == 0:
        parts.append(
            "我们刚开始。你最近在探索，我还在慢慢了解你的节奏。"
        )
        parts.append(f"你{style_text}。")
        return " ".join(parts)

    if total <= 2:
        parts.append(
            f"你最近在学<span class=\"highlight\">{subject_text}</span>，"
            "我还在慢慢了解你的节奏。"
        )
    elif total < 15:
        parts.append(
            "还记得刚开始的时候吗？"
            "到现在，你已经能自己解出不少问题了。"
        )
        parts.append(f"你{style_text}。")
    else:
        parts.append(
            "还记得你第一天开始学习的样子吗。"
            "一路走来，你已经掌握了很多之前觉得难的内容。"
        )
        parts.append(
            '你从绕着走，到现在会主动追问\u201c为什么\u201d。'
        )
        if streak >= 7:
            parts.append("你每周的节奏很稳，每次都能看到你在往前。")

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
) -> list[dict]:
    """生成「关于你的学习」偏好网格。

    返回 4 条具象偏好，对齐 preview.html 的 pref-grid：
      学习方式 / 学习节奏 / 最近在学 / 已经一起走过
    """
    total = growth_summary.get("total_sessions", 0)
    streak = growth_summary.get("streak_days", 0)
    style = profile.get("learning_style", "")
    subjects = profile.get("subjects", []) or []

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

    # 最近在学
    subject_value = _esc(subjects[0]) if subjects else "还在探索不同领域"

    # 已经一起走过
    if total == 0:
        sessions_text = "刚认识"
    elif total == 1:
        sessions_text = "1 次学习"
    else:
        sessions_text = f"{total} 次学习"

    return [
        {"label": "学习方式", "value": style_value},
        {"label": "学习节奏", "value": pace},
        {"label": "最近在学", "value": subject_value},
        {"label": "已经一起走过", "value": sessions_text},
    ]
