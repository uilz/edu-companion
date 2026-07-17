"""Profile 叙事生成器单测。

覆盖 build_mirror_narrative 与 build_prefs 的边界场景与回归断言。
"""

import pytest

from app.domain.profile.narrative import build_mirror_narrative, build_prefs


# ── 测试 fixture ──────────────────────────────────────────

def _profile(**overrides) -> dict:
    base = {
        "user_id": "test-1",
        "nickname": "测试用户",
        "subjects": [],
        "learning_style": "reading",
    }
    base.update(overrides)
    return base


def _growth(**overrides) -> dict:
    base = {
        "total_sessions": 0,
        "streak_days": 0,
        "recent_records": [],
    }
    base.update(overrides)
    return base


# ── build_mirror_narrative ────────────────────────────────

class TestMirrorNarrative:
    """镜像叙事生成器测试。"""

    def test_zero_sessions_includes_beginning_tone(self):
        result = build_mirror_narrative(_profile(), _growth(total_sessions=0))
        assert "刚开始" in result or "刚开始" in result
        # 无 highlight（无学科）
        assert "我还在慢慢了解你的节奏" in result

    def test_one_session_includes_highlight(self):
        result = build_mirror_narrative(
            _profile(subjects=["微积分"]),
            _growth(total_sessions=1),
        )
        assert '<span class="highlight">' in result
        assert "微积分" in result

    def test_medium_sessions_includes_contrast(self):
        result = build_mirror_narrative(
            _profile(subjects=["线性代数"], learning_style="kinesthetic"),
            _growth(total_sessions=9, streak_days=5),
        )
        # 对齐 Vision preview.html 行 546：起点对比 + 学习偏好
        assert "一开始觉得" in result or "到现在能自己" in result
        assert "更喜欢先动手算一遍" in result

    def test_many_sessions_includes_long_term(self):
        result = build_mirror_narrative(
            _profile(subjects=["矩阵求逆"], learning_style="visual"),
            _growth(total_sessions=28, streak_days=14),
        )
        # 对齐 Vision preview.html 行 551-558：三个月起点对比 + 主动追问
        assert "三个月" in result
        assert "主动追问" in result
        assert "节奏非常稳定" in result

    def test_xss_escapes_script_tag(self):
        result = build_mirror_narrative(
            _profile(subjects=['<script>alert(1)</script>']),
            _growth(total_sessions=1),
        )
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_empty_subjects_uses_fallback(self):
        result = build_mirror_narrative(
            _profile(subjects=[]),
            _growth(total_sessions=2),
        )
        assert "还在探索" in result

    def test_unknown_style_uses_fallback(self):
        result = build_mirror_narrative(
            _profile(subjects=["英语"], learning_style="unknown_style"),
            _growth(total_sessions=5, streak_days=1),
        )
        assert "有自己独特的学习节奏" in result

    def test_many_sessions_with_weekday_pattern(self):
        """对齐 Vision 行 557：≥3 月学习应检测到学习时间模式。"""
        import time
        from datetime import datetime
        now = time.time()
        day = 86400
        # 构造周二(1) 周四(3) 各 2 次
        ts = []
        for offset in range(0, 30):
            t = now - offset * day
            if datetime.fromtimestamp(t).weekday() in (1, 3):
                ts.append(int(t))
                if len(ts) >= 4:
                    break
        result = build_mirror_narrative(
            _profile(subjects=["线性代数"], learning_style="reading"),
            _growth(
                total_sessions=20,
                streak_days=10,
                recent_records=[
                    {"session_started_at": ts[0], "skill_gains": [{"skill": "矩阵", "after": 0.8}]},
                    {"session_started_at": ts[1], "skill_gains": [{"skill": "向量", "after": 0.7}]},
                    {"session_started_at": ts[2], "skill_gains": [{"skill": "行列式", "after": 0.6}]},
                    {"session_started_at": ts[3], "skill_gains": [{"skill": "逆矩阵", "after": 0.5}]},
                ],
            ),
        )
        assert "学习时间最长" in result


    def test_many_sessions_with_first_record_quote(self):
        """≥15 次且有 first_record 时优先使用记忆系统引述。"""
        result = build_mirror_narrative(
            _profile(subjects=["微积分"], learning_style="reading"),
            _growth(
                total_sessions=20,
                streak_days=10,
                first_record={
                    "summary": "今天第一次接触极限概念，对 epsilon-delta 比较困惑",
                    "reflection_snippet": "极限的 epsilon-delta 定义好抽象",
                    "skill_gains": [{"skill": "极限", "before": 0.1, "after": 0.3}],
                },
            ),
        )
        # 应使用 first_record 的 reflection_snippet 引述
        assert "极限的 epsilon-delta 定义好抽象" in result
        assert "今天你已经能熟练运用了" in result

    def test_first_record_quote_takes_reflection_over_summary(self):
        """reflection_snippet 优先于 summary。"""
        result = build_mirror_narrative(
            _profile(subjects=["矩阵"], learning_style="reading"),
            _growth(
                total_sessions=10,
                streak_days=3,
                first_record={
                    "summary": "矩阵基础概念介绍",
                    "reflection_snippet": "矩阵乘法好难，位置总是搞混",
                },
            ),
        )
        assert "矩阵乘法好难" in result
        assert "矩阵基础概念介绍" not in result

    def test_missing_first_record_falls_back_to_generic(self):
        """没有 first_record 时回退到通用文案。"""
        result = build_mirror_narrative(
            _profile(subjects=["线性代数"], learning_style="visual"),
            _growth(total_sessions=20, streak_days=5),
        )
        assert "三个月前你" in result


# ── build_prefs ───────────────────────────────────────────

class TestBuildPrefs:
    """偏好网格生成器测试。"""

    def test_always_returns_four_items(self):
        prefs = build_prefs(_profile(), _growth())
        assert len(prefs) == 4
        labels = [p["label"] for p in prefs]
        assert labels == ["学习方式", "学习节奏", "最近在学", "已经一起走过"]

    def test_kinesthetic_style_maps_to_practice_first(self):
        prefs = build_prefs(
            _profile(learning_style="kinesthetic"),
            _growth(),
        )
        assert prefs[0]["value"] == "先实践，再看理论"

    def test_reading_style_maps_to_example_first(self):
        prefs = build_prefs(
            _profile(learning_style="reading"),
            _growth(),
        )
        assert prefs[0]["value"] == "先看例子，再看定义"

    def test_zero_sessions_shows_zero_pace(self):
        prefs = build_prefs(_profile(), _growth(total_sessions=0, streak_days=0))
        assert prefs[1]["value"] == "刚开始建立节奏"

    def test_high_streak_shows_daily_pace(self):
        prefs = build_prefs(
            _profile(),
            _growth(total_sessions=15, streak_days=7),
        )
        assert "本周" in prefs[1]["value"]
        assert "7" in prefs[1]["value"]

    def test_subject_appears_in_prefs(self):
        prefs = build_prefs(
            _profile(subjects=["微积分"]),
            _growth(),
        )
        assert prefs[2]["value"] == "微积分"

    def test_empty_subjects_fallback(self):
        prefs = build_prefs(_profile(subjects=[]), _growth())
        assert prefs[2]["value"] == "还在探索不同领域"

    def test_total_sessions_fallback_when_no_history(self):
        prefs = build_prefs(
            _profile(),
            _growth(total_sessions=12),
        )
        # 无 earliest record，回退到次数
        assert prefs[3]["value"] == "12 次学习"

    def test_zero_sessions_shows_new_label(self):
        prefs = build_prefs(_profile(), _growth(total_sessions=0))
        assert prefs[3]["value"] == "刚认识"

    def test_one_session_shows_just_started(self):
        prefs = build_prefs(_profile(), _growth(total_sessions=1))
        assert prefs[3]["value"] == "刚刚开始"

    def test_two_sessions_short_span_shows_count(self):
        """≥2 次但时间跨度<14 天则 fallback 到次数。"""
        import time
        now = time.time()
        day = 86400
        prefs = build_prefs(
            _profile(),
            _growth(
                total_sessions=2,
                streak_days=1,
                recent_records=[
                    {"session_started_at": now - 3 * day, "skill_gains": []},
                ],
            ),
        )
        assert prefs[3]["value"] == "2 次学习"

    def test_long_span_shows_relative_time(self):
        """对齐 GAP.md：≥14 天跨度时显示相对时间（N 周/N 个月）。"""
        import time
        now = time.time()
        day = 86400
        prefs = build_prefs(
            _profile(),
            _growth(
                total_sessions=12,
                streak_days=5,
                recent_records=[
                    {"session_started_at": now - day, "skill_gains": [{"skill": "矩阵", "after": 0.7}]},
                    {"session_started_at": now - 60 * day, "skill_gains": [{"skill": "向量", "after": 0.3}]},
                ],
            ),
        )
        assert "一起走过" in prefs[3]["value"]
        assert "个月" in prefs[3]["value"] or "周" in prefs[3]["value"]

    def test_first_record_overrides_relative_span(self):
        """first_record 的时间戳应覆盖 recent_records 的截断计算。"""
        import time
        now = time.time()
        day = 86400
        prefs = build_prefs(
            _profile(),
            _growth(
                total_sessions=28,
                streak_days=5,
                # recent_records 只有最近 5 条（最早 10 天前）
                recent_records=[
                    {"session_started_at": now - day, "skill_gains": []},
                    {"session_started_at": now - 10 * day, "skill_gains": []},
                ],
            ),
            first_record={
                "session_started_at": now - 90 * day,
                "summary": "第一次学习",
            },
        )
        # 应使用 first_record（90 天前），而非 recent_records（10 天前）
        assert "一起走过" in prefs[3]["value"]
        assert "个月" in prefs[3]["value"]

    def test_first_record_none_falls_back_to_recent(self):
        """first_record 为 None 时回退到 recent_records 计算。"""
        import time
        now = time.time()
        day = 86400
        prefs = build_prefs(
            _profile(),
            _growth(
                total_sessions=10,
                streak_days=3,
                recent_records=[
                    {"session_started_at": now - 30 * day, "skill_gains": []},
                ],
            ),
            first_record=None,
        )
        assert "一起走过" in prefs[3]["value"]
        assert "周" in prefs[3]["value"]  # 30 天 = 4 周（< 60 天归入周）

    def test_first_record_zero_ts_falls_back(self):
        """first_record.session_started_at 为 0 时回退到 recent_records。"""
        import time
        now = time.time()
        day = 86400
        prefs = build_prefs(
            _profile(),
            _growth(
                total_sessions=8,
                recent_records=[
                    {"session_started_at": now - 21 * day, "skill_gains": []},
                ],
            ),
            first_record={"session_started_at": 0, "summary": "无时间戳"},
        )
        assert "一起走过" in prefs[3]["value"]
        assert "周" in prefs[3]["value"]  # 21 天 = 3 周

    def test_xss_subjects_escaped_in_prefs(self):
        prefs = build_prefs(
            _profile(subjects=['<img src=x onerror=alert(1)>']),
            _growth(total_sessions=1),
        )
        assert "<img" not in prefs[2]["value"]
        assert "&lt;" in prefs[2]["value"]
