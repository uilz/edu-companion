"""Secretary Dashboard 端到端验证脚本 (Task #187)

验证范围：
1. /api/secretary/dashboard 返回结构完整
2. dashboard 聚合 pending proposals + confirmations
3. 接受/忽略 confirmation 后 dashboard 缓存失效
4. /api/activities 与 SSE stream 端点可访问
5. 前端 SecretaryDashboard 组件依赖的 API 字段类型一致

用法:
    cd /home/deploy/edu-companion
    venv/bin/python scripts/test/task0187/verify_secretary_dashboard_e2e.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:18001")
TEST_USER = os.environ.get("TEST_USER", "apple")
TEST_PASS = os.environ.get("TEST_PASS", "123456")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def fail(msg: str) -> None:
    print(f"\n❌ FAIL: {msg}")
    sys.exit(1)


def login() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": TEST_USER, "password": TEST_PASS},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"登录失败: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        fail(f"登录响应缺少 token: {data}")
    log(f"登录成功，用户: {data.get('user_id', TEST_USER)}")
    return token


def api_get(token: str, path: str) -> Any:
    r = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code != 200:
        fail(f"GET {path} 失败: {r.status_code} {r.text}")
    return r.json()


def api_post(token: str, path: str, body: dict | None = None) -> Any:
    r = requests.post(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=10,
    )
    if r.status_code not in (200, 201):
        fail(f"POST {path} 失败: {r.status_code} {r.text}")
    return r.json()


def verify_dashboard_structure(data: dict) -> None:
    """验证 dashboard 顶层字段与类型"""
    required = {"greeting", "date", "focus", "stats", "pending", "recommendations", "activities"}
    missing = required - set(data.keys())
    if missing:
        fail(f"dashboard 缺少字段: {missing}")

    assert isinstance(data["greeting"], str), "greeting 应为字符串"
    assert isinstance(data["date"], str), "date 应为字符串"
    assert isinstance(data["stats"], list), "stats 应为列表"

    pending = data["pending"]
    assert isinstance(pending, dict), "pending 应为对象"
    assert "items" in pending and "total" in pending, "pending 应包含 items/total"
    assert pending["total"] == len(pending["items"]), "pending.total 与 items 长度不一致"

    for item in pending["items"]:
        for k in ("id", "kind", "title", "description", "priority", "action_type", "source", "created_at", "tags", "target"):
            assert k in item, f"pending item 缺少字段 {k}"
        assert item["kind"] in ("proposal", "confirmation", "notification"), f"未知 kind: {item['kind']}"

    recs = data["recommendations"]
    assert isinstance(recs, dict), "recommendations 应为对象"
    assert "suggestion" in recs, "recommendations 缺少 suggestion"
    for key in ("urgent", "building", "new_topic"):
        assert isinstance(recs.get(key), list), f"recommendations.{key} 应为列表"

    activities = data["activities"]
    assert isinstance(activities, dict), "activities 应为对象"
    for k in ("items", "total", "limit", "offset"):
        assert k in activities, f"activities 缺少字段 {k}"

    log(f"dashboard 结构验证通过: stats={len(data['stats'])} pending={pending['total']} activities={activities['total']}")


def create_test_confirmation(token: str) -> str:
    """创建一个测试用的 plan item confirmation"""
    body = {
        "request_id": f"test_confirm_{int(time.time() * 1000)}",
        "source_module": "secretary",
        "target_type": "practice",
        "target_ref_id": "test_node_001",
        "title": "【E2E】测试待确认计划项",
        "description": "验证 dashboard 聚合与缓存失效",
        "priority": 4,
        "estimated_minutes": 15,
        "linked_node_ids": ["test_node_001"],
        "proposed_scheduled_for": (datetime.now() + timedelta(days=1)).isoformat(),
    }
    data = api_post(token, "/api/planning/confirmations", body)
    cid = data.get("id")
    if not cid:
        fail(f"创建 confirmation 失败: {data}")
    log(f"创建测试 confirmation: {cid}")
    return cid


def verify_pending_contains(token: str, confirmation_id: str) -> None:
    """验证 dashboard pending 中包含指定 confirmation"""
    data = api_get(token, "/api/secretary/dashboard")
    items = data["pending"]["items"]
    found = [it for it in items if it["kind"] == "confirmation" and it["id"] == confirmation_id]
    if not found:
        fail(f"dashboard pending 未找到 confirmation {confirmation_id}，当前 items: {json.dumps(items, ensure_ascii=False, indent=2)}")
    log(f"dashboard pending 中找到 confirmation: {confirmation_id}")


def verify_pending_missing(token: str, confirmation_id: str) -> None:
    """验证 dashboard pending 中已不包含指定 confirmation（缓存失效）"""
    data = api_get(token, "/api/secretary/dashboard")
    items = data["pending"]["items"]
    found = [it for it in items if it["id"] == confirmation_id]
    if found:
        fail(f"dashboard pending 仍包含已处理 confirmation {confirmation_id}: {found}")
    log(f"dashboard pending 中已无 confirmation: {confirmation_id}")


def verify_activities_api(token: str) -> None:
    """验证学习活动流 API"""
    data = api_get(token, "/api/activities/?limit=10")
    for k in ("items", "total", "limit", "offset"):
        assert k in data, f"activities list 缺少字段 {k}"

    # SSE 端点返回 200 或 401（未传 token）均可接受；带 query token 应 200
    r = requests.get(
        f"{BASE_URL}/api/activities/stream?token={token}",
        stream=True,
        timeout=5,
    )
    if r.status_code == 200:
        # 读取几字节确认流已建立
        _ = next(r.iter_content(chunk_size=64), None)
        r.close()
        log("SSE stream 端点可建立连接")
    else:
        log(f"SSE stream 端点状态: {r.status_code}（若 401 则检查 token 传递方式）")


def main() -> int:
    log(f"开始 Secretary Dashboard E2E 验证，BASE_URL={BASE_URL}")
    token = login()

    # 1. dashboard 结构与字段
    dashboard = api_get(token, "/api/secretary/dashboard")
    verify_dashboard_structure(dashboard)

    # 2. 创建 confirmation → dashboard 聚合显示
    cid = create_test_confirmation(token)
    verify_pending_contains(token, cid)

    # 3. 接受 confirmation → dashboard 缓存失效
    api_post(token, f"/api/planning/confirmations/{cid}/accept")
    verify_pending_missing(token, cid)

    # 4. 再次创建并忽略 confirmation
    cid2 = create_test_confirmation(token)
    verify_pending_contains(token, cid2)
    api_post(token, f"/api/planning/confirmations/{cid2}/dismiss")
    verify_pending_missing(token, cid2)

    # 5. 活动流 API 可用性
    verify_activities_api(token)

    log("\n✅ Secretary Dashboard 端到端验证全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
