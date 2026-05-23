#!/usr/bin/env python3
"""Test messages/persist endpoint and capture traceback"""
import json, uuid, sys, traceback

sys.path.insert(0, "/home/deploy/edu-companion/backend")

# Setup minimal env
import os
os.environ["USE_JSON_STORAGE"] = "1"

from app.api.conversation import _add_message_to_tree, PersistMessageRequest, tree_ops, storage

USER_ID = "default_user"

# Create a conversation
data = storage.load(USER_ID)

# Create a partition with a real conversation
pid = str(uuid.uuid4())
cid = str(uuid.uuid4())

# Use tree_ops to create properly
from app.schemas.conversation import Partition, Domain, Topic, Conversation, TreeNode, TextBlock

partition = Partition(id=pid, name="TestPartition", emoji="🧪")
domain = Domain(partition_id=pid, name="TestDomain", emoji="📚")
topic = Topic(domain_id=domain.id, name="TestTopic", emoji="📝")
conv = Conversation(id=cid, topic_id=topic.id, name="TestConv", status="active")

root_id = str(uuid.uuid4())
root_node = TreeNode(
    id=root_id, parent_id=root_id, partition_id=pid,
    conversation_id=cid, role="assistant",
    content_blocks=[], text_summary="[root]"
)
root_node.partition_id = pid
partition.root_id = root_id

data.partitions[pid] = partition
data.domains[domain.id] = domain
data.topics[topic.id] = topic
data.conversations[cid] = conv
data.nodes[root_id] = root_node
storage.save(USER_ID, data)
print(f"Created conv: {cid}")

# Now test persist
try:
    result = _add_message_to_tree(cid, "user", "Hello World", "user", {"test": True})
    print(f"✅ Success: {json.dumps(result, indent=2)}")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)

# Verify message appears
data2 = storage.load(USER_ID)
messages = []
for nid in data2.conversations[cid].path:
    node = data2.nodes.get(nid)
    if node and not node.is_deleted:
        messages.append({"id": node.id, "role": node.role, "text": node.text_summary})
print(f"Messages in conv: {len(messages)}")
for m in messages:
    print(f"  {m['role']}: {m['text'][:50]}")
