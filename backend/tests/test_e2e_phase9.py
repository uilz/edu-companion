#!/usr/bin/env python3
"""Phase 9 全链路 E2E 测试 — 验证核心数据通路（多用户模式）"""
import json, sys, os, subprocess, urllib.request, urllib.error

BASE = "http://localhost:8000"
AUTH_GATEWAY = "http://localhost:18001"

# ── 获取认证令牌 ──
CRED = {"username": os.environ.get("TEST_USER", "Apple_Admin"),
        "password": os.environ.get("TEST_PASS", "492210")}
TOKEN = None
USER_ID = None

try:
    req = urllib.request.Request(
        f"{AUTH_GATEWAY}/api/auth/login",
        data=json.dumps(CRED).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        login_data = json.loads(r.read().decode())
        TOKEN = login_data["access_token"]
        USER_ID = login_data["user"]["id"]
except Exception as e:
    print(f"  ⚠️  登录失败: {e} — 测试将使用无认证请求（可能 401）")

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP_{e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"_error": str(e)}

ok, fail = 0, 0

def check(name, condition, detail=""):
    global ok, fail
    if condition:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fail += 1
        print(f"  ❌ {name} — {detail}")

# ── 1. Health ──
print("\n── 1. Health ──")
r = api("GET", "/health")
check("健康检查", r.get("status") == "ok", str(r)[:100])

# ── 2. Classify API ──
print("\n── 2. Classify API ──")
r = api("POST", "/api/v2/classify", {
    "user_id": USER_ID or "test_user", "message": "导数的定义",
    "current_topic_id": "",
})
check("classify 返回 mode", "mode" in r, str(r)[:100])
check("classify 含 candidates", "candidates" in r)

# ── 3. CognitiveNode 更新链路 ──
print("\n── 3. CognitiveNode 更新链路 ──")
try:
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "companion",
         "-d", "edu_companion", "-t", "-A", "-F", "|",
         "-c", "SELECT COUNT(*) FROM cognitive_nodes"],
        capture_output=True, text=True,
        env={"PGPASSWORD": "companion123"},
        timeout=10,
    )
    node_count = result.stdout.strip()
    check("cognitive_nodes 表有数据", node_count.isdigit() and int(node_count) > 0, node_count)
except Exception as e:
    check("cognitive_nodes 表查询", False, str(e))

# 查询 learner_model 能读到掌握度
if USER_ID:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from app.core.learner_model import LearnerModelEngine
        lm = LearnerModelEngine()
        state = lm.get_knowledge_state(USER_ID, "数据科学.数据分析.统计学")
        check("learner_model 真实读取", state.get("mastery", 0) > 0 or state.get("status") == "active", str(state))
    except Exception as e:
        check("learner_model 读取", False, str(e))

# ── 4. Secretary API ──
print("\n── 4. Secretary 链路 ──")
uid_param = f"?user_id={USER_ID}" if USER_ID else ""
r = api("GET", f"/api/secretary/snapshot{uid_param}")
check("秘书快照可访问", "_error" not in r, str(r)[:100])

r = api("GET", f"/api/secretary/proposals/pending{uid_param}")
check("提案列表可访问", isinstance(r, list) or "_error" not in r, str(r)[:100])

r = api("GET", f"/api/secretary/modules{uid_param}")
check("秘书模块列表可访问", "_error" not in r, str(r)[:100])

# ── 5. 事件总线 ──
print("\n── 5. 事件总线状态 ──")
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from app.application.di import container
    handler_count = sum(len(v) for v in container.event_bus._handlers.values())
    check("事件总线有注册 handler", handler_count > 0, f"{handler_count} handlers")
    event_types = list(container.event_bus._handlers.keys())
    check("AnswerSubmitted 已订阅", "AnswerSubmitted" in event_types, str(event_types))
    check("CognitiveNodeMetadataChanged 已订阅", "CognitiveNodeMetadataChanged" in event_types, str(event_types))
except Exception as e:
    check("事件总线检查", False, str(e))

print("\n" + "=" * 60)
print(f"  测试结果: ✅ {ok} 通过  |  ❌ {fail} 失败  |  总计 {ok + fail}")
print("=" * 60)

# 作为 pytest 收集时不 exit（避免 SystemExit INTERNALERROR）
if __name__ == "__main__":
    sys.exit(0 if fail == 0 else 1)
