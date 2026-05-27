#!/usr/bin/env python3
"""对话系统全面端到端测试"""
import json, uuid, sys, subprocess, urllib.request, urllib.error

BASE = "http://localhost:8000/api/conversations"
PRACTICE_BASE = "http://localhost:8000/api/practice"

def api(method, path, data=None, base=None):
    base_url = base or BASE
    url = f"{base_url}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return f"HTTP_{e.code}:{e.read().decode()[:200]}"
    except Exception as e:
        return f"ERR:{e}"

def GET(path): return api("GET", path)
def POST(path, data): return api("POST", path, data)
def PATCH(path, data): return api("PATCH", path, data)
def DELETE(path): return api("DELETE", path)

ok, fail = 0, 0
results = []

def check(name, actual, expected_substr=None, negate=False):
    global ok, fail
    s = str(actual)[:150]
    if expected_substr:
        if not negate:
            if expected_substr in s:
                results.append(f"  ✅ {name}")
                ok += 1
            else:
                results.append(f"  ❌ {name} — 期望含 '{expected_substr}' 实际 '{s}'")
                fail += 1
        else:
            if expected_substr in s:
                results.append(f"  ❌ {name} — 不应含 '{expected_substr}' 但 '{s}'")
                fail += 1
            else:
                results.append(f"  ✅ {name}")
                ok += 1
    else:
        results.append(f"  ❓ {name} — {s}")
        fail += 1

def http_check(name, actual, expected_code=200):
    """Check HTTP response code"""
    global ok, fail
    s = str(actual)[:150]
    if isinstance(actual, str) and actual.startswith(f"HTTP_{expected_code}"):
        results.append(f"  ✅ {name}")
        ok += 1
    elif isinstance(actual, str) and actual.startswith("HTTP_"):
        results.append(f"  ❌ {name} — 期望 {expected_code} 实际 {s}")
        fail += 1
    elif not actual.startswith("HTTP_"):
        results.append(f"  ✅ {name} — {s[:80]}")
        ok += 1
    else:
        results.append(f"  ❓ {name} — {s}")
        fail += 1

print("=" * 65)
print("  对话系统 · 全面功能测试")
print("=" * 65)

# ══════════════════════════════════
# 1. 分区 (Partition) CRUD
# ══════════════════════════════════
print("\n── 1. 分区 CRUD ──")
r = GET("/partitions")
check("GET /partitions", r, '"partitions"')
pid = uid = None

# Try to parse existing partitions
try:
    parts = json.loads(r).get("partitions", [])
    # Find an existing one or use first
    if parts:
        pid = parts[0]["id"]
        print(f"  📌 已有分区: {parts[0].get('emoji','')} {parts[0]['name']} ({pid[:12]})")
except:
    pass

uid = uuid.uuid4().hex[:8]

# Create
r = POST("/partitions", {"name": f"E2E测试_{uid}", "emoji": "🧪"})
check("POST /partitions", r, '"id"')
try: pid = json.loads(r).get("partition", json.loads(r)).get("id") or json.loads(r).get("id")
except: pass
if not pid:
    try: pid = json.loads(r).get("id")
    except: pass
print(f"  📌 新建PID: {pid}")

if pid:
    r = GET("/partitions")
    check("GET /partitions (验证创建)", r, uid)
    
    r = PATCH(f"/partitions/{pid}", {"name": f"E2E改名_{uid}"})
    http_check(f"PATCH /partitions/{pid}", r, 200)
    
    r = GET("/partitions")
    check("GET /partitions (验证改名)", r, f"E2E改名_{uid}")

# ══════════════════════════════════
# 2. 领域 (Domain) CRUD
# ══════════════════════════════════
print("\n── 2. 领域 CRUD ──")
if pid:
    r = POST("/domains", {"partition_id": pid, "name": f"领域_{uid}", "emoji": "📚"})
    check("POST /domains", r, '"id"')
    did = None
    try: did = json.loads(r).get("domain", json.loads(r)).get("id") or json.loads(r).get("id")
    except: pass
    
    if did:
        r = GET(f"/partitions/{pid}/domains")
        check("GET /partitions/{pid}/domains", r, f"领域_{uid}")
        
        r = PATCH(f"/domains/{did}", {"name": f"领域改名_{uid}"})
        http_check("PATCH /domains/{did}", r, 200)
        
        r = GET(f"/partitions/{pid}/domains")
        check("GET domains (验证改名)", r, f"领域改名_{uid}")

# ══════════════════════════════════
# 3. 专题 (Topic) CRUD
# ══════════════════════════════════
print("\n── 3. 专题 CRUD ──")
try:
    if did:
        r = POST("/topics", {"domain_id": did, "name": f"专题_{uid}", "emoji": "📝"})
        check("POST /topics", r, '"id"')
        tid = None
        try: tid = json.loads(r).get("topic", json.loads(r)).get("id") or json.loads(r).get("id")
        except: pass

        if tid:
            r = GET(f"/domains/{did}/topics")
            check("GET /domains/{did}/topics", r, f"专题_{uid}")

            r = PATCH(f"/topics/{tid}", {"name": f"专题改名_{uid}"})
            http_check("PATCH /topics/{tid}", r, 200)
except NameError:
    print("  skips (no domain created)")

# ══════════════════════════════════
# 4. 会话 (Conversation) CRUD
# ══════════════════════════════════
print("\n── 4. 会话 CRUD ──")
try:
    if tid:
        r = POST("/conversations", {"topic_id": tid, "name": f"会话_{uid}"})
        check("POST /conversations", r, '"id"')
        cid = None
        try: cid = json.loads(r).get("conversation", json.loads(r)).get("id") or json.loads(r).get("id")
        except: pass
        
        if cid:
            r = GET(f"/topics/{tid}/conversations")
            check("GET /topics/{tid}/conversations", r, f"会话_{uid}")
except NameError:
    print("  skips (no topic created)")

# ══════════════════════════════════
# 5. 消息流程
# ══════════════════════════════════
print("\n── 5. 消息流程 ──")
try:
    if cid:
        # Persist a user message
        r = POST("/messages/persist", {
            "conversation_id": cid, "role": "user",
            "content": "测试消息：极限的定义是什么？",
            "source": "user",
            "metadata": {"test": True}
        })
        check("POST /messages/persist", r, '"id"')
        
        r = GET(f"/conversations/{cid}/messages")
        check("GET /conversations/{cid}/messages", r, "极限的定义")
        
        # Persist an assistant response
        r = POST("/messages/persist", {
            "conversation_id": cid, "role": "assistant",
            "content": "极限是微积分的基础概念...",
            "source": "assistant",
            "metadata": {"test": True}
        })
        check("POST /messages/persist (assistant)", r, '"id"')
        
        r = GET(f"/conversations/{cid}/messages")
        check("GET messages (2条)", r, "微积分")

        # Get response blocks
        r = GET(f"/conversations/{cid}/blocks")
        check("GET /conversations/{cid}/blocks", r, '"blocks"')
        
        # Delete a message
        try:
            msgs = json.loads(GET(f"/conversations/{cid}/messages"))
            msgs_list = msgs if isinstance(msgs, list) else msgs.get("messages", [])
            if msgs_list:
                mid = msgs_list[0].get("id", msgs_list[0].get("message_id", ""))
                if mid:
                    r = DELETE(f"/messages/{mid}")
                    http_check("DELETE /messages/{id}", r, 200)
                    print(f"  📌 已删除消息: {mid[:12]}")
        except Exception as e:
            print(f"  ⚠️ 消息删除测试: {e}")
except NameError:
    print("  skips (no conversation created)")

# ══════════════════════════════════
# 6. 工作空间
# ══════════════════════════════════
# 6. 工作空间
# ══════════════════════════════════
print("\n── 6. 工作空间 ──")
try:
    if cid:
        result = subprocess.run(
            ["curl", "-s", "-w", "%{http_code}", "-X", "POST",
             f"http://localhost:8000/api/conversations/workspace/upload",
             "-F", "file=@/etc/hostname",
             "-F", f"conversation_id={cid}"],
            capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        print(f"  Upload 响应: {out[:100]}")
        check("Upload file (conversation_id)", out, "200")
        
        # List files
        result = subprocess.run(
            ["curl", "-s", f"http://localhost:8000/api/conversations/workspace/files?conversation_id={cid}"],
            capture_output=True, text=True, timeout=15
        )
        r = result.stdout.strip()
        check("GET workspace/files", r, '"files"')
        
        # Delete file
        try:
            data = json.loads(r)
            files = data.get("files", [])
            if files:
                fname = files[0].get("name", "")
                result2 = subprocess.run(
                    ["curl", "-s", f"http://localhost:8000/api/conversations/workspace/files/detail?conversation_id={cid}"],
                    capture_output=True, text=True, timeout=10
                )
                r2 = result2.stdout.strip()
                print(f"  📌 文件详情: {r2[:100]}")
        except Exception as e:
            print(f"  ⚠️ 文件清理: {e}")
except NameError:
    print("  skips (no conversation created)")

# ══════════════════════════════════
# 7. 软删 & 硬删会话
# ══════════════════════════════════
print("\n── 7. 软删/恢复 ──")
try:
    if cid and tid:
        # Soft delete
        r = DELETE(f"/conversations/{cid}")
        http_check("DELETE /conversations/{cid} (软删)", r, 200)
        
        # Should still appear but with deleted status
        r = GET(f"/topics/{tid}/conversations")
        check("GET topics (软删后)", r, uid)
        
        # Hard delete
        r = DELETE(f"/conversations/{cid}?hard=true")
        http_check("DELETE /conversations/{cid}?hard=true", r, 200)
        
        r = GET(f"/topics/{tid}/conversations")
        check("GET topics (硬删后, 不应含uid)", r, uid, negate=True)
except NameError:
    print("  skips (no conversation/topic created)")

# ══════════════════════════════════
# 8. 内联练习端点
# ══════════════════════════════════
print("\n── 8. 内联练习端点 ──")
r = api("POST", "/inline/answer", {"block_id": "nonexistent", "answer": "A"}, base=PRACTICE_BASE)
check("POST /api/practice/inline/answer", r, "Practice block")

r = api("POST", "/inline/hint", {"block_id": "nonexistent"}, base=PRACTICE_BASE)
check("POST /api/practice/inline/hint", r, "Practice block")

# ══════════════════════════════════
# 9. 未分类分区存在性
# ══════════════════════════════════
print("\n── 9. 未分类分区 ──")
r = GET("/partitions")
check("GET /partitions (未分类存在)", r, "__uncategorized__")

# ══════════════════════════════════
# 汇总
# ══════════════════════════════════
print("\n" + "=" * 65)
print(f"  测试结果: ✅ {ok} 通过  |  ❌ {fail} 失败  |  总计 {ok+fail}")
print("=" * 65)
for r in results:
    print(r)

# 作为 pytest 收集时不 exit（避免 SystemExit INTERNALERROR）
if __name__ != "__main__":
    pass
elif fail == 0:
    sys.exit(0)
else:
    sys.exit(1)
