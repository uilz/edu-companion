#!/usr/bin/env python3
"""
v3 → v4 数据迁移（精简版）
处理三种遗留数据：branch_id → conversation_id / 缺省 conversation_id / branches 转 conversations

用法: python3 ~/edu-companion/scripts/migrate_v4.py
"""
import json
import time
from pathlib import Path
from uuid import uuid4

BASE = Path.home() / ".companion" / "data"


def _ensure_chain(data: dict, partition_id: str, conv_id: str, now: float):
    """确保 partition → domain → topic → conversation 链条完整"""
    domains = data.setdefault("domains", {})
    topics = data.setdefault("topics", {})
    convs = data.setdefault("conversations", {})

    # find/create domain
    dom = next((d for d in domains.values() if d.get("partition_id") == partition_id), None)
    if not dom:
        pname = data.get("partitions", {}).get(partition_id, {}).get("name", "默认")
        dom = {"id": str(uuid4()), "partition_id": partition_id, "name": pname,
               "emoji": "📚", "created_at": now, "updated_at": now}
        domains[dom["id"]] = dom
    # find/create topic
    top = next((t for t in topics.values() if t.get("domain_id") == dom["id"]), None)
    if not top:
        top = {"id": str(uuid4()), "domain_id": dom["id"], "name": "默认专题",
               "emoji": "📝", "active_conversation_id": conv_id,
               "created_at": now, "updated_at": now}
        topics[top["id"]] = top
    # link conversation
    if conv_id in convs:
        convs[conv_id]["topic_id"] = top["id"]
    top["active_conversation_id"] = conv_id


def migrate(path: Path) -> int:
    with open(path) as f:
        data = json.load(f)
    changes = 0
    now = time.time()

    # 1. nodes: branch_id → conversation_id / 补缺
    for nid, n in data.get("nodes", {}).items():
        if "conversation_id" not in n:
            if "branch_id" in n:
                n["conversation_id"] = n.pop("branch_id")
                print(f"  node {nid[:8]}  branch_id → conversation_id")
            else:
                pid = n.get("partition_id", "")
                # 找同分区已有对话，没有则建默认
                convs = data.get("conversations", {})
                cid = next((c["id"] for c in convs.values() if c.get("topic_id")), None)
                if not cid:
                    cid = str(uuid4())
                    convs[cid] = {"id": cid, "topic_id": "", "name": "默认对话",
                                  "path": [], "is_active": True, "is_archived": False,
                                  "summary": "", "material_refs": [],
                                  "created_at": now, "last_message_at": now}
                    _ensure_chain(data, pid, cid, now)
                n["conversation_id"] = cid
                print(f"  node {nid[:8]}  补 conversation_id={cid[:8]}")
            changes += 1

    # 2. branches → conversations
    branches = data.pop("branches", {})
    convs = data.setdefault("conversations", {})
    for bid, b in branches.items():
        if bid not in convs:
            pid = b.get("partition_id", "")
            c = {"id": b.get("id", str(uuid4())), "topic_id": "",
                 "name": b.get("name", "迁移对话"), "path": b.get("path", []),
                 "is_active": b.get("is_active", False), "is_archived": b.get("is_archived", False),
                 "summary": b.get("summary", ""), "material_refs": b.get("material_refs", []),
                 "created_at": b.get("created_at", now), "last_message_at": b.get("last_message_at", now)}
            convs[c["id"]] = c
            _ensure_chain(data, pid, c["id"], now)
            print(f"  branch {bid[:8]} → conversation")
            changes += 1

    # 3. response_blocks: branch_id → conversation_id
    for bid, b in data.get("response_blocks", {}).items():
        if "branch_id" in b and "conversation_id" not in b:
            b["conversation_id"] = b.pop("branch_id")
            changes += 1

    # 4. link_nodes
    for lid, ln in data.get("link_nodes", {}).items():
        for o, n in [("source_branch_id", "source_conversation_id"),
                      ("target_branch_id", "target_conversation_id")]:
            if o in ln and n not in ln:
                ln[n] = ln.pop(o)
                changes += 1

    if changes:
        bak = path.with_suffix(".json.v3.bak")
        bak.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  ✅ {changes} 处修改，备份 → {bak.name}")
    else:
        print("  ✅ 数据已是最新")
    return changes


if __name__ == "__main__":
    print(f"🔍 {BASE}")
    total = 0
    for d in sorted(BASE.glob("*/userData.json")):
        print(f"\n📂 {d.parent.name}")
        total += migrate(d)
    print(f"\n{'='*40}\n{'✅ 无需操作' if total == 0 else f'✅ 迁移 {total} 处，重启后端: edu-companion-restart'}")
