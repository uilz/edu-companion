"""Cognitive subsystem constants.

Kept alongside the cognitive package; referenced by events.py.
Values here are tunable defaults.  Override via Settings when needed.
"""

# ── Event processing ──
PRACTICE_EVENT_MAX: int = 200          # max recent practice events to retain per user
CONTEXT_HISTORY_MAX: int = 50          # max dialogue context entries to keep

# ── Belief decline detection ──
DECLINE_THRESHOLD: float = 0.15        # proficiency drop above this = decline
DECLINE_DANGER_THRESHOLD: float = 0.5  # proficiency below this = danger zone

# ── Mastery level thresholds (统一 threshold, 所有模块共用) ──
# 历史分歧: profiles.py 用 0.9, adaptive_planner.py 用 0.8 → 现统一为 0.8
# 原因: 与 BKT get_mastery_level 保持一致, 避免模块间漂移
# 阈值含义: (threshold, label) 表示 mean < threshold → label
MASTERY_THRESHOLD: float = 0.8
MASTERY_TIERS: tuple[tuple[float, str], ...] = (
    (0.3, "未接触"),    # mean < 0.3
    (0.6, "初学"),       # 0.3 ≤ mean < 0.6
    (0.8, "发展中"),     # 0.6 ≤ mean < 0.8
    (0.9, "接近掌握"),   # 0.8 ≤ mean < 0.9
)
# mean ≥ 0.9 → "已掌握"

def proficiency_to_mastery_level(mean: float) -> str:
    """统一 proficiency_mean → 掌握等级 字符串

    修复 (2026-07-04)：原本分散在 profiles.py 和 adaptive_planner.py
    两份不一致的实现，现统一到此处。
    """
    for threshold, label in MASTERY_TIERS:
        if mean < threshold:
            return label
    return "已掌握"

# ── Model defaults ──
DEFAULT_PARAMS: dict[str, float] = {
    "student.retrieval_sigma": 0.25,   # retrieval noise standard deviation
}
