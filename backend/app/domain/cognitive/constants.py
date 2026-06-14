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

# ── Model defaults ──
DEFAULT_PARAMS: dict[str, float] = {
    "student.retrieval_sigma": 0.25,   # retrieval noise standard deviation
}
