#!/usr/bin/env python3
"""快速诊断：检查后端存储一致性"""
import json, urllib.request

BASE = "http://localhost:8000/api/conversations"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return f"ERR:{e.code}:{e.read().decode()[:200]}"
    except Exception as e:
        return f"ERR:{e}"

def GET(path): return api("GET", path)
def POST(path, data): return api("POST", path, data)

# Step 1: List partitions before
print("=== BEFORE ===")
r = json.loads(GET("/partitions"))
for p in r["partitions"]:
    print(f"  {p['id'][:12]} {p['emoji']} {p['name']}")

# Step 2: Create
print("\n=== CREATE ===")
r = json.loads(POST("/partitions", {"name": "DiagTest", "emoji": "🧪"}))
pid = r.get("partition") or r
pid = pid.get("id", pid.get("partition", {}).get("id"))
print(f"  Created PID: {pid}")

# Step 3: List partitions after
print("\n=== AFTER ===")
r = json.loads(GET("/partitions"))
found = False
for p in r["partitions"]:
    print(f"  {p['id'][:12]} {p['emoji']} {p['name']}")
    if p["id"] == pid:
        found = True
print(f"  New partition visible: {found}")

# Step 4: Check DB directly
print("\n=== PG DIRECT ===")
import subprocess
r = subprocess.run(
    ["PGPASSWORD=companion123", "psql", "-h", "localhost", "-p", "5432", "-U", "companion", "-d", "edu_companion",
     "-c", "SELECT id, name FROM conversation_partitions ORDER BY created_at DESC"],
    capture_output=True, text=True, timeout=10,
    env=None
)
print(r.stdout[:500] if r.stdout else r.stderr[:200])
