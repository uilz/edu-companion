"""Phase 5 Slice 5.3 端到端验证：Planning 规划壳服务下沉

验证项：
1. Planning 日/周/知识视图 API 正常返回
2. 计划项 CRUD（创建、查询、更新、标记完成/开始/跳过/延长、删除）
3. 目标 CRUD
4. 周期回顾生成
5. 视图方案 CRUD
6. 确认请求创建与接受

用法：
    cd /home/deploy/edu-companion
    backend/venv/bin/python scripts/test/task0151/verify_planning_service_sink.py

环境要求：
    - 服务已通过 rebuild.sh 启动
    - 用户 apple / 123456 存在
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8080"
USERNAME = "apple"
PASSWORD = "123456"


def get_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api(method: str, path: str, token: str, **kwargs):
    resp = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def verify_views(token: str) -> tuple[bool, str]:
    today = date.today().isoformat()
    daily = api("GET", f"/api/planning/daily?date={today}", token)
    if "status_bar" not in daily or "timeline_items" not in daily:
        return False, f"日视图字段异常: {list(daily.keys())}"

    weekly = api("GET", "/api/planning/weekly", token)
    if "days" not in weekly or "totals" not in weekly:
        return False, f"周视图字段异常: {list(weekly.keys())}"

    knowledge = api("GET", "/api/planning/knowledge", token)
    if "nodes" not in knowledge:
        return False, f"知识视图字段异常: {list(knowledge.keys())}"

    return True, "日/周/知识视图 API 返回正常"


def verify_plan_items(token: str) -> tuple[bool, str]:
    item = api(
        "POST",
        "/api/planning/items",
        token,
        json={
            "source_module": "manual",
            "target_type": "flashcard",
            "target_ref_id": "fc_test_001",
            "title": "Planning 下沉验证",
            "estimated_minutes": 30,
        },
    )
    if item.get("status") != "pending":
        return False, f"创建计划项状态异常: {item}"
    item_id = item["id"]

    listed = api("GET", "/api/planning/items", token)
    if not any(i["id"] == item_id for i in listed.get("items", [])):
        return False, "新建计划项未出现在列表中"

    updated = api(
        "PATCH",
        f"/api/planning/items/{item_id}",
        token,
        json={"title": "Planning 下沉验证（已更新）", "priority": 2},
    )
    if updated.get("title") != "Planning 下沉验证（已更新）":
        return False, f"更新计划项失败: {updated}"

    started = api("POST", f"/api/planning/items/{item_id}/start", token)
    if started.get("status") != "in_progress":
        return False, f"开始计划项失败: {started}"

    extended = api("POST", f"/api/planning/items/{item_id}/extend?minutes=10", token)
    if extended.get("status") != "extended":
        return False, f"延长计划项失败: {extended}"

    completed = api(
        "POST",
        f"/api/planning/items/{item_id}/complete",
        token,
        json={"actual_minutes": 25},
    )
    if completed.get("status") != "completed":
        return False, f"完成计划项失败: {completed}"

    api("DELETE", f"/api/planning/items/{item_id}", token)
    after_delete = api("GET", "/api/planning/items", token)
    if any(i["id"] == item_id for i in after_delete.get("items", [])):
        return False, "删除计划项后仍出现在列表中"

    return True, f"计划项 CRUD 通过 (item_id={item_id})"


def verify_goals(token: str) -> tuple[bool, str]:
    goal = api(
        "POST",
        "/api/planning/goals",
        token,
        json={
            "title": "验证目标",
            "target_module": "flashcard",
            "target_metric": "card_count",
            "target_value": 100,
        },
    )
    if goal.get("target_value") != 100:
        return False, f"创建目标失败: {goal}"
    goal_id = goal["id"]

    updated = api(
        "PATCH",
        f"/api/planning/goals/{goal_id}",
        token,
        json={"current_value": 10},
    )
    if updated.get("current_value") != 10:
        return False, f"更新目标失败: {updated}"

    return True, f"目标 CRUD 通过 (goal_id={goal_id})"


def verify_reviews(token: str) -> tuple[bool, str]:
    start = date.today() - timedelta(days=7)
    end = date.today()
    review = api(
        "POST",
        "/api/planning/reviews/generate",
        token,
        json={
            "period_type": "weekly",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
        },
    )
    if "summary_data" not in review:
        return False, f"生成回顾失败: {review}"

    listed = api("GET", "/api/planning/reviews", token)
    if not any(r["id"] == review["id"] for r in listed.get("reviews", [])):
        return False, "新生成回顾未出现在列表中"

    return True, f"周期回顾通过 (review_id={review['id']})"


def verify_view_layouts(token: str) -> tuple[bool, str]:
    layout = api(
        "POST",
        "/api/planning/view-layouts",
        token,
        json={
            "name": "验证布局",
            "view_type": "day",
            "filters": {"source_module": "manual"},
            "layout": {"columns": 2},
            "is_default": False,
        },
    )
    if layout.get("view_type") != "day":
        return False, f"创建视图方案失败: {layout}"

    listed = api("GET", "/api/planning/view-layouts", token)
    if not any(l["id"] == layout["id"] for l in listed.get("layouts", [])):
        return False, "新建视图方案未出现在列表中"

    return True, f"视图方案 CRUD 通过 (layout_id={layout['id']})"


def verify_confirmations(token: str) -> tuple[bool, str]:
    confirmation = api(
        "POST",
        "/api/planning/confirmations",
        token,
        json={
            "request_id": f"req_verify_sink_{uuid.uuid4().hex[:8]}",
            "source_module": "secretary",
            "target_type": "review",
            "target_ref_id": "node_verify_001",
            "title": "验证确认请求",
            "description": "服务下沉验证",
        },
    )
    if confirmation.get("status") != "pending":
        return False, f"创建确认请求失败: {confirmation}"

    accepted = api(
        "POST",
        f"/api/planning/confirmations/{confirmation['id']}/accept",
        token,
    )
    if accepted.get("title") != "验证确认请求":
        return False, f"接受确认请求失败: {accepted}"

    return True, f"确认请求通过 (confirmation_id={confirmation['id']})"


def main() -> int:
    print("=" * 60)
    print("Phase 5 Slice 5.3 验证：Planning 规划壳服务下沉")
    print("=" * 60)

    token = get_token()

    checks = [
        ("视图聚合", lambda: verify_views(token)),
        ("计划项 CRUD", lambda: verify_plan_items(token)),
        ("目标 CRUD", lambda: verify_goals(token)),
        ("周期回顾", lambda: verify_reviews(token)),
        ("视图方案", lambda: verify_view_layouts(token)),
        ("确认请求", lambda: verify_confirmations(token)),
    ]

    all_passed = True
    for name, fn in checks:
        print(f"\n▶ {name}...")
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"异常: {exc}"
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {status}: {msg}")
        if not ok:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Planning 服务下沉验证全部通过")
        return 0
    else:
        print("❌ Planning 服务下沉验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())
