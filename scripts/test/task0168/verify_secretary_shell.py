"""Task #168 Secretary 秘书壳整理端到端验证脚本

验证范围：
  - 偏好、快照、仪表盘
  - 提案列表 / 模块列表 / onboarding / agent 偏好
  - 心情压力仪表盘
  - 事件摘要
  - 数据导出（只读）

用法：
  python scripts/test/task0168/verify_secretary_shell.py [--base-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TEST_USERNAME = "apple"
TEST_PASSWORD = "123456"


def api(method: str, path: str, token: str | None = None, **kwargs) -> Any:
    url = f"{DEFAULT_BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    try:
        return response.json()
    except Exception:
        return {"_raw": response.text, "_status": response.status_code}


def login() -> str | None:
    """通过默认测试账号获取 JWT token"""
    resp = api(
        "POST",
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = resp.get("access_token") or resp.get("token")
    if not token:
        print(f"登录失败: {resp}")
    return token


def verify_preferences(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/preferences", token)
    if not isinstance(data, dict):
        return False, f"preferences 返回格式异常: {data}"
    if "enabled_extensions" not in data:
        return False, f"preferences 缺少 enabled_extensions: {data}"
    return True, "preferences OK"


def verify_snapshot(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/snapshot", token)
    if not isinstance(data, dict):
        return False, f"snapshot 返回格式异常: {data}"
    required = {"cognitive_load", "weak_count", "stagnant_count", "streak_days", "summary"}
    missing = required - set(data.keys())
    if missing:
        return False, f"snapshot 缺少字段 {missing}: {data}"
    return True, "snapshot OK"


def verify_dashboard(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/dashboard", token)
    if not isinstance(data, dict):
        return False, f"dashboard 返回格式异常: {data}"
    required = {"greeting", "date", "focus", "stats", "pending", "recommendations", "activities"}
    missing = required - set(data.keys())
    if missing:
        return False, f"dashboard 缺少字段 {missing}: {data}"
    stats = data.get("stats")
    if not isinstance(stats, list) or len(stats) != 8:
        return False, f"dashboard stats 应为 8 张卡: {stats}"
    pending = data.get("pending")
    if not isinstance(pending, dict) or "items" not in pending:
        return False, f"dashboard pending 结构异常: {pending}"
    return True, "dashboard OK"


def verify_proposals_pending(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/proposals/pending", token)
    if not isinstance(data, list):
        return False, f"proposals/pending 返回格式异常: {data}"
    return True, f"proposals/pending OK ({len(data)} 条)"


def verify_modules(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/modules", token)
    if not isinstance(data, list):
        return False, f"modules 返回格式异常: {data}"
    return True, f"modules OK ({len(data)} 个模块)"


def verify_onboarding(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/onboarding", token)
    if not isinstance(data, dict):
        return False, f"onboarding 返回格式异常: {data}"
    required = {"is_cold_start", "total_nodes", "learned_nodes", "guide_steps", "current_step", "message"}
    missing = required - set(data.keys())
    if missing:
        return False, f"onboarding 缺少字段 {missing}: {data}"
    return True, "onboarding OK"


def verify_agent_preferences(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/agent/preferences", token)
    if not isinstance(data, dict):
        return False, f"agent/preferences GET 返回格式异常: {data}"
    if "confirm_mode" not in data or "auto_jump_threshold" not in data:
        return False, f"agent/preferences 缺少字段: {data}"

    # PUT 验证
    put_resp = api(
        "POST",
        "/api/secretary/agent/preferences",
        token,
        json={"confirm_mode": "smart", "auto_jump_threshold": 0.85},
    )
    if not isinstance(put_resp, dict) or put_resp.get("confirm_mode") != "smart":
        return False, f"agent/preferences POST 失败: {put_resp}"
    return True, "agent/preferences OK"


def verify_mood_stress_dashboard(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/mood-stress/dashboard", token)
    if not isinstance(data, dict):
        return False, f"mood-stress/dashboard 返回格式异常: {data}"
    return True, "mood-stress/dashboard OK"


def verify_events_summary(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/events/summary", token)
    if not isinstance(data, dict):
        return False, f"events/summary 返回格式异常: {data}"
    if "total_events" not in data or "counts" not in data:
        return False, f"events/summary 缺少字段: {data}"
    return True, "events/summary OK"


def verify_data_export(token: str) -> tuple[bool, str]:
    data = api("GET", "/api/secretary/data/export", token)
    if not isinstance(data, dict):
        return False, f"data/export 返回格式异常: {data}"
    if "user_id" not in data or "proposals" not in data:
        return False, f"data/export 缺少字段: {data}"
    return True, "data/export OK"


def verify_mood_stress_record(token: str) -> tuple[bool, str]:
    suffix = uuid.uuid4().hex[:8]
    resp = api(
        "POST",
        "/api/secretary/mood-stress/record",
        token,
        json={
            "emotion_tags": ["motivated"],
            "pressure_score": 5,
            "energy_score": 7,
            "text_note": f"验证记录 {suffix}",
        },
    )
    if not isinstance(resp, dict) or resp.get("status") != "ok":
        return False, f"mood-stress/record 失败: {resp}"
    return True, "mood-stress/record OK"


VERIFIERS = [
    verify_preferences,
    verify_snapshot,
    verify_dashboard,
    verify_proposals_pending,
    verify_modules,
    verify_onboarding,
    verify_agent_preferences,
    verify_mood_stress_dashboard,
    verify_mood_stress_record,
    verify_events_summary,
    verify_data_export,
]


def main() -> int:
    global DEFAULT_BASE_URL
    parser = argparse.ArgumentParser(description="Secretary shell end-to-end verification")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    args = parser.parse_args()
    DEFAULT_BASE_URL = args.base_url

    token = login()
    if not token:
        return 1

    passed = 0
    failed = 0
    for verifier in VERIFIERS:
        ok, msg = verifier(token)
        if ok:
            print(f"  ✅ {msg}")
            passed += 1
        else:
            print(f"  ❌ {verifier.__name__}: {msg}")
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败 / 共 {len(VERIFIERS)} 项")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
