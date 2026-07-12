"""Phase 3 端到端验证：跨壳学习活动实时同步与多源聚合冲突解决

验证项：
1. SSE 端点可连接并返回 connected 事件
2. 完成练习会话后，SSE 客户端收到 activity_created 事件
3. 高优先级来源（practice）覆盖低优先级来源（secretary）
4. 低优先级来源（secretary）不覆盖高优先级来源（practice）
5. 同一 idempotency_key 再次写入返回 activity_updated

用法：
    cd /home/deploy/edu-companion
    backend/venv/bin/python scripts/test/task0118/verify_phase3_realtime_sync.py

环境要求：
    - 后端服务运行在 http://127.0.0.1:8080（Nginx 网关）
    - 用户 apple / 123456 存在
"""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "backend"))

from app.application.handlers.learning_activity_handler import _upsert_activity_sync

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


def sse_collect(token: str, duration: float = 8.0) -> list[str]:
    """在后台线程收集 SSE 事件。"""
    events: list[str] = []
    stop_event = threading.Event()

    def _collect() -> None:
        try:
            with requests.get(
                f"{BASE_URL}/api/activities/stream?token={token}",
                stream=True,
                timeout=duration + 5,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if stop_event.is_set():
                        break
                    if line:
                        events.append(line)
        except Exception as exc:
            events.append(f"ERROR: {exc}")

    thread = threading.Thread(target=_collect)
    thread.start()
    return events, stop_event, thread


def create_and_complete_session(token: str) -> str:
    """创建、启动并完成一个练习会话，返回 session_id。"""
    # 列出通用题库
    banks = requests.get(
        f"{BASE_URL}/api/practice/banks",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    ).json()
    default_bank = next((b for b in banks if b["id"].endswith("_default")), banks[0])
    bank_id = default_bank["id"]

    session = requests.post(
        f"{BASE_URL}/api/practice/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"bank_id": bank_id, "session_type": "practice", "count": 1},
        timeout=10,
    ).json()
    session_id = session["session_id"]

    # 启动会话
    requests.patch(
        f"{BASE_URL}/api/practice/sessions/{session_id}/start",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    ).raise_for_status()

    # 完成会话
    requests.post(
        f"{BASE_URL}/api/practice/sessions/{session_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    ).raise_for_status()

    return session_id


def verify_sse_delivery(token: str) -> tuple[bool, str, str]:
    """验证 SSE 能收到 activity_created 事件。返回 (ok, msg, session_id)。"""
    events, stop_event, thread = sse_collect(token, duration=8.0)
    time.sleep(1.0)  # 等待 SSE 连接建立

    session_id = create_and_complete_session(token)
    time.sleep(2.0)  # 等待事件处理与推送

    stop_event.set()
    thread.join(timeout=5.0)

    parsed: list[dict] = []
    for line in events:
        if line.startswith("data: "):
            try:
                parsed.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass

    connected = any(e.get("event") == "connected" for e in parsed)
    created = any(
        e.get("event") == "activity_created"
        and e.get("data", {}).get("idempotency_key") == f"session:{session_id}"
        for e in parsed
    )

    if not connected:
        return False, f"SSE 未收到 connected 事件: {events[:5]}", session_id
    if not created:
        return False, f"SSE 未收到 activity_created 事件: {parsed}", session_id
    return True, f"SSE 正常收到 activity_created (session={session_id})", session_id


def verify_conflict_resolution(user_id: str) -> tuple[bool, str, str]:
    """验证多源聚合冲突解决。返回 (ok, msg, idempotency_key)。"""
    key = f"test_conflict:{uuid.uuid4().hex[:8]}"

    # 1) secretary 先写入（低优先级）
    low_record = {
        "user_id": user_id,
        "activity_type": "test_conflict",
        "module": "secretary",
        "idempotency_key": key,
        "title": "secretary 来源",
        "description": "低优先级",
        "status": "completed",
        "timestamp": None,
        "deep_link": "",
        "meta": {"round": 1},
    }
    low_id, low_type = _upsert_activity_sync(low_record)
    if low_type != "activity_created":
        return False, f"secretary 首次写入应为 created，实际 {low_type}", key

    # 2) practice 覆盖（高优先级）
    high_record = {
        "user_id": user_id,
        "activity_type": "test_conflict",
        "module": "practice",
        "idempotency_key": key,
        "title": "practice 来源",
        "description": "高优先级覆盖",
        "status": "completed",
        "timestamp": None,
        "deep_link": "/practice",
        "meta": {"round": 2},
    }
    high_id, high_type = _upsert_activity_sync(high_record)
    if high_type != "activity_updated":
        return False, f"practice 覆盖 secretary 应为 updated，实际 {high_type}", key
    if high_id != low_id:
        return False, "覆盖后 activity_id 发生变化，违反幂等性", key

    # 3) secretary 再次写入，不应覆盖
    low_again, low_again_type = _upsert_activity_sync(low_record)
    if low_again_type != "skipped":
        return False, f"secretary 不应覆盖 practice，实际 {low_again_type}", key

    return True, f"冲突解决正常: practice 覆盖 secretary，secretary 不反向覆盖 (key={key})", key


def verify_idempotent_update(user_id: str) -> tuple[bool, str, str]:
    """验证同一 practice 来源再次写入返回 updated。返回 (ok, msg, idempotency_key)。"""
    key = f"test_idempotent:{uuid.uuid4().hex[:8]}"
    record = {
        "user_id": user_id,
        "activity_type": "test_idempotent",
        "module": "practice",
        "idempotency_key": key,
        "title": "首次",
        "description": "首次写入",
        "status": "completed",
        "timestamp": None,
        "deep_link": "",
        "meta": {"round": 1},
    }
    first_id, first_type = _upsert_activity_sync(record)
    if first_type != "activity_created":
        return False, f"首次写入应为 created，实际 {first_type}", key

    record["title"] = "第二次"
    record["description"] = "更新描述"
    record["meta"] = {"round": 2}
    second_id, second_type = _upsert_activity_sync(record)
    if second_type != "activity_updated":
        return False, f"同一 practice 再次写入应为 updated，实际 {second_type}", key
    if second_id != first_id:
        return False, "更新后 activity_id 发生变化，违反幂等性", key

    return True, f"幂等更新正常 (key={key})", key


def cleanup_test_activities(user_id: str, session_id: str, keys: list[str]) -> None:
    """清理验证过程中创建的测试学习活动记录。"""
    from app.infrastructure.db.session import get_db_session
    from app.infrastructure.db.models.learning_activity import LearningActivityORM

    with get_db_session() as session:
        query = session.query(LearningActivityORM).filter(
            LearningActivityORM.user_id == user_id,
        )
        or_filters = [LearningActivityORM.idempotency_key.like("test_%")]
        if session_id:
            or_filters.append(
                LearningActivityORM.idempotency_key == f"session:{session_id}"
            )
        query = query.filter(__import__("sqlalchemy").or_(*or_filters))
        deleted = query.delete(synchronize_session=False)
        session.commit()
        print(f"\n🧹 清理 {deleted} 条测试学习活动记录")


def main() -> int:
    print("=" * 60)
    print("Phase 3 验证：跨壳学习活动实时同步与多源聚合冲突解决")
    print("=" * 60)

    token = get_token()
    user_id = "u_f65eb04e5c6b"  # apple 用户固定 id

    checks = [
        ("SSE 实时推送", lambda: verify_sse_delivery(token)),
        ("多源聚合冲突解决", lambda: verify_conflict_resolution(user_id)),
        ("幂等更新", lambda: verify_idempotent_update(user_id)),
    ]

    all_passed = True
    sse_session_id = ""
    test_keys: list[str] = []

    for name, fn in checks:
        print(f"\n▶ {name}...")
        try:
            ok, msg, key = fn()
        except Exception as exc:
            ok, msg, key = False, f"异常: {exc}", ""
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {status}: {msg}")
        if not ok:
            all_passed = False

        if name == "SSE 实时推送":
            sse_session_id = key
        else:
            test_keys.append(key)

    cleanup_test_activities(user_id, sse_session_id, test_keys)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Phase 3 全部验证通过")
        return 0
    else:
        print("❌ Phase 3 验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())
