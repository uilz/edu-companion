#!/usr/bin/env python3
"""
v3 → v4 数据迁移脚本
branch_id → conversation_id + Branch → Conversation 转换

运行方式:
  python migrate_v4.py [data_dir]

默认 data_dir: ~/.companion/data
"""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4


def _find_or_create_fallback_conversation(data: dict, partition_id: str) -> str:
    """为没有 conversation_id 的节点找一个归宿：按 partition → domain → topic → conversation 链查找"""
    import time

    topics = data.get("topics", {})
    conversations = data.get("conversations", {})

    # 先查找该分区下是否有活跃对话
    for tid, topic in topics.items():
        cid = topic.get("active_conversation_id", "")
        if cid and cid in conversations:
            return cid

    # 没有则创建默认 domain→topic→conversation
    cid = str(uuid4())
    conv = {
        "id": cid,
        "topic_id": "",
        "name": "默认对话",
        "path": [],
        "is_active": True,
        "is_archived": False,
        "summary": "",
        "material_refs": [],
        "created_at": time.time(),
        "last_message_at": time.time(),
    }
    data.setdefault("conversations", {})[cid] = conv
    _ensure_default_hierarchy(data, partition_id, cid)
    return cid


def migrate_file(filepath: Path) -> bool:
    """迁移单个 userData.json"""
    print(f"\n📂 {filepath}")

    with open(filepath) as f:
        data = json.load(f)

    changes = 0

    # 1. 迁移 nodes: branch_id → conversation_id（以及缺失 conversation_id 的节点）
    nodes = data.get("nodes", {})
    for nid, node in nodes.items():
        if "conversation_id" not in node:
            if "branch_id" in node:
                node["conversation_id"] = node.pop("branch_id")
                changes += 1
                print(f"  ✅ node {nid}: branch_id → conversation_id")
            else:
                # 节点完全没有 conversation_id → 查找所属分区的活跃对话
                partition_id = node.get("partition_id", "")
                conv_id = _find_or_create_fallback_conversation(data, partition_id)
                node["conversation_id"] = conv_id
                changes += 1
                print(f"  🔧 node {nid}: 补充 conversation_id={conv_id[:8]}")

    # 2. 迁移 response_blocks: branch_id → conversation_id
    rbs = data.get("response_blocks", {})
    for bid, block in rbs.items():
        if "conversation_id" not in block:
            if "branch_id" in block:
                block["conversation_id"] = block.pop("branch_id")
                changes += 1
                print(f"  ✅ response_block {bid}: branch_id → conversation_id")

    # 3. 迁移 link_nodes
    link_nodes = data.get("link_nodes", {})
    for lid, link in link_nodes.items():
        if "source_conversation_id" not in link:
            if "source_branch_id" in link:
                link["source_conversation_id"] = link.pop("source_branch_id")
                changes += 1
        if "target_conversation_id" not in link:
            if "target_branch_id" in link:
                link["target_conversation_id"] = link.pop("target_branch_id")
                changes += 1

    # 4. 迁移 branches → conversations
    branches = data.get("branches", {})
    conversations = data.get("conversations", {})
    if branches:
        for bid, branch in branches.items():
            if bid not in conversations:
                # Convert Branch → Conversation
                # Branch has: id, partition_id, name, path, is_active, is_archived, summary, material_refs, created_at, last_message_at
                # Conversation has: id, topic_id, name, path, is_active, is_archived, summary, created_at, last_message_at
                # Old Branch doesn't have topic_id — we need to create a default topic for it
                partition_id = branch.get("partition_id", "")
                conv = {
                    "id": branch.get("id", str(uuid4())),
                    "topic_id": "",  # will be set by auto-resolve
                    "name": branch.get("name", "迁移的对话"),
                    "path": branch.get("path", []),
                    "is_active": branch.get("is_active", False),
                    "is_archived": branch.get("is_archived", False),
                    "summary": branch.get("summary", ""),
                    "material_refs": branch.get("material_refs", []),
                    "created_at": branch.get("created_at", 0),
                    "last_message_at": branch.get("last_message_at", 0),
                }
                # Create default domain+ topic for this branch's partition
                _ensure_default_hierarchy(data, partition_id, conv["id"])
                conversations[conv["id"]] = conv

                changes += 1
                print(f"  ✅ branch {bid} → conversation {conv['id']} (partition={partition_id})")

        # Delete branches key
        del data["branches"]

    # 5. Ensure conversations key exists
    if "conversations" not in data:
        data["conversations"] = {}
    elif not isinstance(data["conversations"], dict):
        data["conversations"] = {}

    # 6. Ensure domains and topics exist (may be missing in old data)
    if "domains" not in data:
        data["domains"] = {}
    if "topics" not in data:
        data["topics"] = {}

    # 7. For any conversation with empty topic_id, create default domain+ topic
    for cid, conv in list(conversations.items()):
        if not conv.get("topic_id"):
            pids = set()
            for nid in conv.get("path", []):
                node = nodes.get(nid)
                if node and node.get("partition_id"):
                    pids.add(node["partition_id"])
            partition_id = next(iter(pids), "")
            if partition_id:
                _ensure_default_hierarchy(data, partition_id, cid)

    if changes == 0:
        print("  (无需迁移)")
        return False

    # Backup
    backup = filepath.with_suffix(".json.bak")
    with open(backup, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 备份: {backup}")

    # Write migrated
    with open(filepath, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 迁移完成 ({changes} 处更改)")
    return True


def _ensure_default_hierarchy(data: dict, partition_id: str, conversation_id: str):
    """确保 partition → domain → topic → conversation 链完整"""
    from uuid import uuid4
    import time

    domains = data.setdefault("domains", {})
    topics = data.setdefault("topics", {})
    partitions = data.get("partitions", {})

    # Find existing domain under this partition
    existing_domain = None
    for did, d in domains.items():
        if d.get("partition_id") == partition_id:
            existing_domain = d
            break

    if not existing_domain:
        part_name = partitions.get(partition_id, {}).get("name", "默认分区")
        did = str(uuid4())
        existing_domain = {
            "id": did,
            "partition_id": partition_id,
            "name": part_name,
            "emoji": "📚",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        domains[did] = existing_domain
        print(f"  🆕 创建领域: {existing_domain['name']} ({did[:8]})")

    domain_id = existing_domain["id"]

    # Find existing topic under this domain
    existing_topic = None
    for tid, t in topics.items():
        if t.get("domain_id") == domain_id:
            existing_topic = t
            break

    if not existing_topic:
        tid = str(uuid4())
        existing_topic = {
            "id": tid,
            "domain_id": domain_id,
            "name": "默认专题",
            "emoji": "📝",
            "active_conversation_id": conversation_id,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        topics[tid] = existing_topic
        print(f"  🆕 创建专题: {existing_topic['name']} ({tid[:8]})")

    # Set topic_id on conversation
    topic_id = existing_topic["id"]
    data["conversations"][conversation_id]["topic_id"] = topic_id

    # Set active_conversation_id on topic
    existing_topic["active_conversation_id"] = conversation_id


def main():
    base_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.companion/data").expanduser()
    print(f"🔍 扫描 {base_dir}")

    migrated = 0
    for user_dir in sorted(base_dir.iterdir()):
        if not user_dir.is_dir():
            continue
        data_file = user_dir / "userData.json"
        if data_file.exists():
            if migrate_file(data_file):
                migrated += 1

    print(f"\n{'='*50}")
    print(f"✅ 迁移完成: {migrated} 个用户数据文件已处理")
    print(f"   请重启后端: edu-companion-restart")


if __name__ == "__main__":
    main()
