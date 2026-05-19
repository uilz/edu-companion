#!/usr/bin/env python3
"""
智能每日摘要 — no_agent cron 脚本
每天早上 7:30 推送昨日学习总结 + 今日推荐

数据源：
- GET /api/progress/default_user/stats (daily stats)
- BKT 引擎 (mastery changes)
- GET /api/knowledge/ready (recommendations)

用法：python3 daily-summary.py
输出到 stdout，空输出 = 静默不推送
"""

import json
import sys
import os
from datetime import datetime, timedelta

# ── 配置 ──
API_BASE = os.environ.get("EDU_API_BASE", "http://localhost:8000")
USER_ID = "default_user"

# ── 文案池 ──
GREETINGS = [
    "早安 ☀️ 新的一天，新的进步",
    "早上好 🌅 昨天的努力都算数",
    "醒来就是战斗力 💪",
    "新的一天，继续加油！🚀",
]

ENCOURAGES = [
    "坚持下去，复利效应正在发生 📈",
    "每一个知识点都是未来的砖瓦 🧱",
    "今天比昨天多会一点，就是胜利 ✨",
    "学习是一场马拉松，不是冲刺 🏃",
    "你的努力都在被悄悄记录着 📊",
]

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def fetch_json(url: str) -> dict | None:
    """简易 HTTP GET + JSON 解析"""
    try:
        import urllib.request
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def get_daily_stats() -> dict | None:
    """获取昨日统计数据"""
    data = fetch_json(f"{API_BASE}/api/progress/{USER_ID}/stats")
    if not data:
        return None
    daily = data.get("daily", {})
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    # 优先用昨天的数据，没有就用今天的
    day_data = daily.get(yesterday) or daily.get(today)
    if not day_data:
        return None

    total = day_data.get("total", 0)
    correct = day_data.get("correct", 0)

    if total == 0:
        return None  # 昨天没学习，静默

    accuracy = correct / total if total > 0 else 0

    # 前天对比
    day_before = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    prev_data = daily.get(day_before) or {"total": 0}

    return {
        "date": yesterday,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "prev_total": prev_data.get("total", 0),
    }


def get_streak() -> int:
    """获取连续学习天数"""
    data = fetch_json(f"{API_BASE}/api/progress/{USER_ID}/profile")
    if data:
        return data.get("streak_days", 0)
    return 0


def get_recommendations() -> list[dict]:
    """获取今日推荐练习的技能"""
    data = fetch_json(f"{API_BASE}/api/knowledge/ready?user_id={USER_ID}")
    if data:
        ready = data.get("ready", [])
        return ready[:3]  # 最多 3 个
    return []


def trend_arrow(curr: int, prev: int) -> str:
    """环比箭头"""
    if curr > prev:
        return f"↑{curr - prev}"
    if curr < prev:
        return f"↓{prev - curr}"
    return "→"


def main():
    # 1. 获取昨日数据
    stats = get_daily_stats()
    if not stats or stats["total"] == 0:
        sys.exit(0)  # 静默

    # 2. 获取 streak
    streak = get_streak()

    # 3. 获取推荐
    recs = get_recommendations()

    # 4. 随机文案
    import random
    greet = random.choice(GREETINGS)
    encourage = random.choice(ENCOURAGES)

    # 5. 组装输出
    date_str = stats["date"]
    weekday = WEEKDAYS[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    acc_pct = round(stats["accuracy"] * 100)

    lines = [
        greet,
        "",
        f"{date_str} · 星期{weekday}",
        "",
        f"📝 答题 {stats['total']} 题  {trend_arrow(stats['total'], stats['prev_total'])}",
        f"✅ 正确 {stats['correct']} 题 · 正确率 {acc_pct}%",
    ]

    if streak > 0:
        lines.append(f"🔥 连续学习 {streak} 天！")

    if recs:
        lines.append("")
        lines.append("🎯 今日推荐")
        for r in recs:
            skill_id = r if isinstance(r, str) else r.get("skill_id", str(r))
            lines.append(f"· {skill_id}")

    lines.append("")
    lines.append(encourage)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
