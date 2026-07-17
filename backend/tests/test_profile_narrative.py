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
        assert "还记得刚开始的时候吗" in result
        assert "更喜欢先动手算一遍" in result

    def test_many_sessions_includes_long_term(self):
        result = build_mirror_narrative(
            _profile(subjects=["矩阵求逆"], learning_style="visual"),
            _growth(total_sessions=28, streak_days=14),
        )
        assert "还记得你第一天开始学习" in result
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

    def test_total_sessions_appears_in_sessions_label(self):
        prefs = build_prefs(
            _profile(),
            _growth(total_sessions=12),
        )
        assert "12 次学习" in prefs[3]["value"]

    def test_zero_sessions_shows_new_label(self):
        prefs = build_prefs(_profile(), _growth(total_sessions=0))
        assert prefs[3]["value"] == "刚认识"

    def test_xss_subjects_escaped_in_prefs(self):
        prefs = build_prefs(
            _profile(subjects=['<img src=x onerror=alert(1)>']),
            _growth(total_sessions=1),
        )
        assert "<img" not in prefs[2]["value"]
        assert "&lt;" in prefs[2]["value"]
