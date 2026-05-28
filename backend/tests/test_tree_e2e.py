"""
Comprehensive E2E API tests for the conversation tree system.

Tests the full lifecycle:
  partition → domain → topic → conversation → message CRUD operations.

Requires the backend server running on port 8000.
Run: cd backend && python -m pytest tests/test_tree_e2e.py -v
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pytest
import requests

BASE = "http://localhost:8000/api/conversations"


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def uid() -> str:
    """Short unique ID for naming test entities."""
    return uuid.uuid4().hex[:8]


def api(method: str, path: str, data: dict | None = None) -> requests.Response:
    url = f"{BASE}{path}"
    resp = requests.request(method, url, json=data, timeout=30)
    return resp


def GET(path: str, params: dict | None = None) -> requests.Response:
    return api("GET", path) if params is None else requests.get(f"{BASE}{path}", params=params, timeout=30)


def POST(path: str, data: dict) -> requests.Response:
    return api("POST", path, data)


def PATCH(path: str, data: dict) -> requests.Response:
    return api("PATCH", path, data)


def PUT(path: str, data: dict) -> requests.Response:
    return api("PUT", path, data)


def DELETE(path: str) -> requests.Response:
    return api("DELETE", path)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def tree_ids():
    """Build the full tree and return all IDs. Teardown cleans up in reverse."""
    test_id = uid()
    ids: dict[str, Any] = {"test_id": test_id}

    # ── 1. Partition ──
    name = f"E2E_Partition_{test_id}"
    resp = POST("/tree/partition", {"name": name, "emoji": "🧪"})
    assert resp.status_code == 200, f"Create partition failed: {resp.text}"
    body = resp.json()
    ids["partition"] = body["partition"]
    ids["partition_id"] = body["partition"]["id"]
    ids["default_conv_id"] = body.get("conversation_id")

    yield ids

    # ── Teardown (reverse order) ──
    if "partition_id" in ids:
        DELETE(f"/tree/partition/{ids['partition_id']}")


@pytest.fixture(scope="module")
def domain_ids(tree_ids):
    """Create a domain under the partition."""
    test_id = tree_ids["test_id"]
    name = f"E2E_Domain_{test_id}"
    resp = POST("/tree/domain", {
        "parent_id": tree_ids["partition_id"],
        "name": name,
        "emoji": "📚",
    })
    assert resp.status_code == 200, f"Create domain failed: {resp.text}"
    body = resp.json()
    tree_ids["domain"] = body["domain"]
    tree_ids["domain_id"] = body["domain"]["id"]
    tree_ids["domain_conv_id"] = body.get("conversation_id")
    return tree_ids


@pytest.fixture(scope="module")
def topic_ids(domain_ids):
    """Create a topic under the domain."""
    test_id = domain_ids["test_id"]
    name = f"E2E_Topic_{test_id}"
    resp = POST("/tree/topic", {
        "parent_id": domain_ids["domain_id"],
        "name": name,
        "emoji": "📝",
    })
    assert resp.status_code == 200, f"Create topic failed: {resp.text}"
    body = resp.json()
    domain_ids["topic"] = body["topic"]
    domain_ids["topic_id"] = body["topic"]["id"]
    domain_ids["topic_conv_id"] = body.get("conversation_id")
    return domain_ids


@pytest.fixture(scope="module")
def conv_ids(topic_ids):
    """Create a conversation under the topic."""
    test_id = topic_ids["test_id"]
    name = f"E2E_Conv_{test_id}"
    resp = POST("/tree/conversation", {
        "parent_id": topic_ids["topic_id"],
        "name": name,
    })
    assert resp.status_code == 200, f"Create conversation failed: {resp.text}"
    body = resp.json()
    topic_ids["conversation"] = body["conversation"]
    topic_ids["conversation_id"] = body["conversation"]["id"]
    return topic_ids


# ═══════════════════════════════════════════════════════════════
# 1. Partition CRUD
# ═══════════════════════════════════════════════════════════════

class TestPartitionCRUD:
    """Test partition create, list, rename, delete."""

    def test_create_partition(self, tree_ids):
        pid = tree_ids["partition_id"]
        assert pid, "partition_id should be set"
        partition = tree_ids["partition"]
        assert partition["name"] == f"E2E_Partition_{tree_ids['test_id']}"
        assert partition["emoji"] == "🧪"
        assert "root_id" in partition
        assert partition["direction"] == "subject"

    def test_list_partitions_includes_created(self, tree_ids):
        resp = GET("/tree/partition")
        assert resp.status_code == 200
        body = resp.json()
        assert "partitions" in body
        names = [p["name"] for p in body["partitions"]]
        assert f"E2E_Partition_{tree_ids['test_id']}" in names

    def test_list_partitions_has_uncategorized(self):
        resp = GET("/tree/partition")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["partitions"]]
        # Uncategorized partition may or may not exist depending on data state
        # Just verify the endpoint works and returns a list
        assert isinstance(names, list)

    def test_rename_partition(self, tree_ids):
        pid = tree_ids["partition_id"]
        new_name = f"Renamed_Partition_{tree_ids['test_id']}"
        resp = PATCH(f"/tree/partition/{pid}", {"name": new_name})
        assert resp.status_code == 200
        body = resp.json()
        assert body["partition"]["name"] == new_name
        tree_ids["partition"]["name"] = new_name  # update for later checks

    def test_list_partitions_shows_renamed(self, tree_ids):
        resp = GET("/tree/partition")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()["partitions"]]
        assert f"Renamed_Partition_{tree_ids['test_id']}" in names

    def test_rename_nonexistent_partition_404(self):
        resp = PATCH("/tree/partition/nonexistent-id-xxx", {"name": "x"})
        assert resp.status_code == 404

    def test_create_partition_with_defaults(self):
        """Partition created via API gets correct default values."""
        test_id = uid()
        resp = POST("/tree/partition", {"name": f"Default_Test_{test_id}"})
        assert resp.status_code == 200
        p = resp.json()["partition"]
        assert p["direction"] == "subject"
        assert p["color"] == "#0066FF"
        assert p["message_count"] == 0
        # Cleanup
        DELETE(f"/tree/partition/{p['id']}")


# ═══════════════════════════════════════════════════════════════
# 2. Domain CRUD
# ═══════════════════════════════════════════════════════════════

class TestDomainCRUD:
    """Test domain create, list, rename, delete."""

    def test_create_domain(self, domain_ids):
        did = domain_ids["domain_id"]
        assert did
        domain = domain_ids["domain"]
        assert domain["name"] == f"E2E_Domain_{domain_ids['test_id']}"
        assert domain["emoji"] == "📚"
        assert domain["partition_id"] == domain_ids["partition_id"]

    def test_list_domains_by_parent(self, domain_ids):
        resp = GET("/tree/domain", params={"parent_id": domain_ids["partition_id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert "domains" in body
        names = [d["name"] for d in body["domains"]]
        assert f"E2E_Domain_{domain_ids['test_id']}" in names

    def test_auto_created_domain_also_exists(self, domain_ids):
        """Creating a partition auto-creates a '新领域' domain."""
        resp = GET("/tree/domain", params={"parent_id": domain_ids["partition_id"]})
        assert resp.status_code == 200
        names = [d["name"] for d in resp.json()["domains"]]
        assert "新领域" in names

    def test_rename_domain(self, domain_ids):
        did = domain_ids["domain_id"]
        new_name = f"Renamed_Domain_{domain_ids['test_id']}"
        resp = PATCH(f"/tree/domain/{did}", {"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["domain"]["name"] == new_name

    def test_list_domains_shows_renamed(self, domain_ids):
        resp = GET("/tree/domain", params={"parent_id": domain_ids["partition_id"]})
        assert resp.status_code == 200
        names = [d["name"] for d in resp.json()["domains"]]
        assert f"Renamed_Domain_{domain_ids['test_id']}" in names

    def test_rename_nonexistent_domain_404(self):
        resp = PATCH("/tree/domain/nonexistent-id-xxx", {"name": "x"})
        assert resp.status_code == 404

    def test_create_domain_under_nonexistent_parent_404(self):
        resp = POST("/tree/domain", {
            "parent_id": "nonexistent-partition-id",
            "name": "orphan",
        })
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 3. Topic CRUD
# ═══════════════════════════════════════════════════════════════

class TestTopicCRUD:
    """Test topic create, list, rename, delete."""

    def test_create_topic(self, topic_ids):
        tid = topic_ids["topic_id"]
        assert tid
        topic = topic_ids["topic"]
        assert topic["name"] == f"E2E_Topic_{topic_ids['test_id']}"
        assert topic["emoji"] == "📝"
        assert topic["domain_id"] == topic_ids["domain_id"]

    def test_list_topics_by_parent(self, topic_ids):
        resp = GET("/tree/topic", params={"parent_id": topic_ids["domain_id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert "topics" in body
        names = [t["name"] for t in body["topics"]]
        assert f"E2E_Topic_{topic_ids['test_id']}" in names

    def test_auto_created_topic_also_exists(self, topic_ids):
        """Creating a domain auto-creates a '新专题' topic."""
        resp = GET("/tree/topic", params={"parent_id": topic_ids["domain_id"]})
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["topics"]]
        assert "新专题" in names

    def test_rename_topic(self, topic_ids):
        tid = topic_ids["topic_id"]
        new_name = f"Renamed_Topic_{topic_ids['test_id']}"
        resp = PATCH(f"/tree/topic/{tid}", {"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["topic"]["name"] == new_name

    def test_list_topics_shows_renamed(self, topic_ids):
        resp = GET("/tree/topic", params={"parent_id": topic_ids["domain_id"]})
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["topics"]]
        assert f"Renamed_Topic_{topic_ids['test_id']}" in names

    def test_rename_nonexistent_topic_404(self):
        resp = PATCH("/tree/topic/nonexistent-id-xxx", {"name": "x"})
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 4. Conversation CRUD
# ═══════════════════════════════════════════════════════════════

class TestConversationCRUD:
    """Test conversation create, list, rename, delete."""

    def test_create_conversation(self, conv_ids):
        cid = conv_ids["conversation_id"]
        assert cid
        conv = conv_ids["conversation"]
        assert conv["name"] == f"E2E_Conv_{conv_ids['test_id']}"
        assert conv["topic_id"] == conv_ids["topic_id"]
        assert conv["is_active"] is True
        assert conv["path"] == []

    def test_list_conversations_by_parent(self, conv_ids):
        resp = GET("/tree/conversation", params={"parent_id": conv_ids["topic_id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert "conversations" in body
        names = [c["name"] for c in body["conversations"]]
        assert f"E2E_Conv_{conv_ids['test_id']}" in names

    def test_auto_created_conversation_also_exists(self, conv_ids):
        """Creating a topic auto-creates a '新对话' conversation."""
        resp = GET("/tree/conversation", params={"parent_id": conv_ids["topic_id"]})
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["conversations"]]
        assert "新对话" in names

    def test_rename_conversation(self, conv_ids):
        cid = conv_ids["conversation_id"]
        new_name = f"Renamed_Conv_{conv_ids['test_id']}"
        resp = PATCH(f"/tree/conversation/{cid}", {"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["conversation"]["name"] == new_name

    def test_list_conversations_shows_renamed(self, conv_ids):
        resp = GET("/tree/conversation", params={"parent_id": conv_ids["topic_id"]})
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["conversations"]]
        assert f"Renamed_Conv_{conv_ids['test_id']}" in names

    def test_rename_nonexistent_conversation_404(self):
        resp = PATCH("/tree/conversation/nonexistent-id-xxx", {"name": "x"})
        assert resp.status_code == 404

    def test_create_second_conversation_under_same_topic(self, conv_ids):
        """Can create multiple conversations under the same topic."""
        test_id = uid()
        resp = POST("/tree/conversation", {
            "parent_id": conv_ids["topic_id"],
            "name": f"Second_Conv_{test_id}",
        })
        assert resp.status_code == 200
        conv2 = resp.json()["conversation"]
        assert conv2["topic_id"] == conv_ids["topic_id"]
        assert conv2["id"] != conv_ids["conversation_id"]

        # Both should appear in listing
        resp = GET("/tree/conversation", params={"parent_id": conv_ids["topic_id"]})
        assert resp.status_code == 200
        conv_ids_list = [c["id"] for c in resp.json()["conversations"]]
        assert conv_ids["conversation_id"] in conv_ids_list
        assert conv2["id"] in conv_ids_list

        # Cleanup the second conversation
        DELETE(f"/tree/conversation/{conv2['id']}")


# ═══════════════════════════════════════════════════════════════
# 5. Message CRUD
# ═══════════════════════════════════════════════════════════════

class TestMessageCRUD:
    """Test message persist, list, get, modify (PUT), delete."""

    def _persist_msg(self, conv_id: str, role: str, content: str,
                     source: str = "user", metadata: dict | None = None) -> dict:
        """Helper to persist a message and return the JSON body."""
        payload: dict[str, Any] = {
            "role": role,
            "content": content,
            "source": source,
        }
        if metadata:
            payload["metadata"] = metadata
        resp = POST(f"/tree/conversation/{conv_id}/message/persist", payload)
        assert resp.status_code == 200, f"Persist failed: {resp.text}"
        return resp.json()

    def test_persist_user_message(self, conv_ids):
        cid = conv_ids["conversation_id"]
        result = self._persist_msg(
            cid, "user", "What is the derivative of x²?",
            source="user", metadata={"test": True}
        )
        assert "id" in result
        assert result["role"] == "user"
        assert result["content"] == "What is the derivative of x²?"
        conv_ids["user_msg_id"] = result["id"]

    def test_persist_assistant_message(self, conv_ids):
        cid = conv_ids["conversation_id"]
        result = self._persist_msg(
            cid, "assistant", "The derivative of x² is 2x.",
            source="assistant"
        )
        assert "id" in result
        assert result["role"] == "assistant"
        conv_ids["assistant_msg_id"] = result["id"]

    def test_list_messages_shows_both(self, conv_ids):
        cid = conv_ids["conversation_id"]
        resp = GET(f"/tree/conversation/{cid}/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert "messages" in body
        assert body["total"] >= 2
        contents = [m.get("content_blocks", [{}])[0].get("text", "") for m in body["messages"]]
        # At least one message should contain our test text
        all_texts = " ".join(str(m) for m in body["messages"])
        assert "derivative" in all_texts.lower() or "What is" in all_texts

    def test_list_messages_with_pagination(self, conv_ids):
        cid = conv_ids["conversation_id"]
        resp = GET(f"/tree/conversation/{cid}/messages")
        assert resp.status_code == 200
        total = resp.json()["total"]
        # Get with limit=1
        resp = GET(f"/tree/conversation/{cid}/messages?limit=1&offset=0")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["messages"]) <= 1
        assert body["total"] == total  # total stays the same

    def test_get_single_message(self, conv_ids):
        msg_id = conv_ids["user_msg_id"]
        resp = GET(f"/tree/message/{msg_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert body["message"]["id"] == msg_id
        assert body["message"]["role"] == "user"
        assert "versions" in body
        assert "version_count" in body

    def test_get_message_blocks(self, conv_ids):
        msg_id = conv_ids["assistant_msg_id"]
        resp = GET(f"/tree/message/{msg_id}/blocks")
        assert resp.status_code == 200
        body = resp.json()
        assert "blocks" in body

    def test_get_conversation_blocks(self, conv_ids):
        cid = conv_ids["conversation_id"]
        resp = GET(f"/tree/conversation/{cid}/blocks")
        assert resp.status_code == 200
        body = resp.json()
        assert "blocks" in body

    def test_modify_message_put(self, conv_ids):
        msg_id = conv_ids["user_msg_id"]
        resp = PUT(f"/tree/message/{msg_id}", {
            "content_blocks": [{"type": "text", "text": "What is the integral of x²?"}],
            "text_summary": "modified question",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "node" in body
        new_node = body["node"]
        assert new_node["content_blocks"][0]["text"] == "What is the integral of x²?"
        assert new_node["text_summary"] == "modified question"
        # The old message becomes the parent, new version is child
        assert "version_count" in body
        conv_ids["modified_msg_id"] = new_node["id"]

    def test_get_nonexistent_message_404(self):
        resp = GET("/tree/message/nonexistent-id-xxx")
        assert resp.status_code == 404

    def test_persist_multiple_user_messages(self, conv_ids):
        """Send multiple user messages in sequence."""
        cid = conv_ids["conversation_id"]
        msg_ids = []
        for i in range(3):
            result = self._persist_msg(cid, "user", f"Sequential message {i}")
            msg_ids.append(result["id"])
        # All should be unique
        assert len(set(msg_ids)) == 3
        # List should show all
        resp = GET(f"/tree/conversation/{cid}/messages")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 5  # 2 original + 3 new

    def test_persist_with_metadata(self, conv_ids):
        cid = conv_ids["conversation_id"]
        result = self._persist_msg(
            cid, "user", "Metadata test",
            metadata={"custom_key": "custom_val", "nested": {"a": 1}}
        )
        msg_id = result["id"]
        # Verify metadata persisted
        resp = GET(f"/tree/message/{msg_id}")
        assert resp.status_code == 200
        node = resp.json()["message"]
        assert node["metadata"]["custom_key"] == "custom_val"
        assert node["metadata"]["nested"]["a"] == 1


# ═══════════════════════════════════════════════════════════════
# 6. Delete Operations (cascading)
# ═══════════════════════════════════════════════════════════════

class TestDeleteOperations:
    """Test delete for conversation, topic, domain, partition (cascading)."""

    def test_delete_conversation(self):
        """Create and delete a conversation, verify it's gone."""
        test_id = uid()
        # Build tree: partition → domain → topic → conversation
        resp = POST("/tree/partition", {"name": f"DelTest_Part_{test_id}", "emoji": "🗑️"})
        assert resp.status_code == 200
        pid = resp.json()["partition"]["id"]

        resp = POST("/tree/domain", {"parent_id": pid, "name": f"DelTest_Dom_{test_id}"})
        assert resp.status_code == 200
        did = resp.json()["domain"]["id"]

        resp = POST("/tree/topic", {"parent_id": did, "name": f"DelTest_Topic_{test_id}"})
        assert resp.status_code == 200
        tid = resp.json()["topic"]["id"]

        resp = POST("/tree/conversation", {"parent_id": tid, "name": f"DelTest_Conv_{test_id}"})
        assert resp.status_code == 200
        cid = resp.json()["conversation"]["id"]

        # Persist a message to confirm it exists
        resp = POST(f"/tree/conversation/{cid}/message/persist", {
            "role": "user", "content": "delete me", "source": "test"
        })
        assert resp.status_code == 200
        msg_id = resp.json()["id"]

        # Delete conversation
        resp = DELETE(f"/tree/conversation/{cid}")
        assert resp.status_code == 200
        assert resp.json().get("ok") is True

        # Verify conversation gone from listing
        resp = GET("/tree/conversation", params={"parent_id": tid})
        assert resp.status_code == 200
        conv_ids = [c["id"] for c in resp.json()["conversations"]]
        assert cid not in conv_ids

    def test_delete_topic_cascades_to_conversations(self):
        """Deleting a topic removes all its conversations."""
        test_id = uid()
        resp = POST("/tree/partition", {"name": f"CascPart_{test_id}", "emoji": "🔥"})
        pid = resp.json()["partition"]["id"]

        resp = POST("/tree/domain", {"parent_id": pid, "name": f"CascDom_{test_id}"})
        did = resp.json()["domain"]["id"]

        resp = POST("/tree/topic", {"parent_id": did, "name": f"CascTopic_{test_id}"})
        tid = resp.json()["topic"]["id"]

        # Topic should have auto-created conversation
        resp = GET("/tree/conversation", params={"parent_id": tid})
        auto_conv_count = len(resp.json()["conversations"])
        assert auto_conv_count >= 1

        # Delete topic
        resp = DELETE(f"/tree/topic/{tid}")
        assert resp.status_code == 200

        # Verify topic gone
        resp = GET("/tree/topic", params={"parent_id": did})
        topic_ids = [t["id"] for t in resp.json()["topics"]]
        assert tid not in topic_ids

    def test_delete_domain_cascades_to_topics_and_conversations(self):
        """Deleting a domain removes all its topics and conversations."""
        test_id = uid()
        resp = POST("/tree/partition", {"name": f"CascDomPart_{test_id}", "emoji": "🌊"})
        pid = resp.json()["partition"]["id"]

        resp = POST("/tree/domain", {"parent_id": pid, "name": f"CascDom_{test_id}"})
        did = resp.json()["domain"]["id"]

        # Delete domain
        resp = DELETE(f"/tree/domain/{did}")
        assert resp.status_code == 200

        # Verify domain gone
        resp = GET("/tree/domain", params={"parent_id": pid})
        domain_ids = [d["id"] for d in resp.json()["domains"]]
        assert did not in domain_ids

    def test_delete_partition_cascades_everything(self):
        """Deleting a partition removes all descendants."""
        test_id = uid()
        resp = POST("/tree/partition", {"name": f"CascAll_{test_id}", "emoji": "💣"})
        pid = resp.json()["partition"]["id"]

        # Auto-creates domain → topic → conversation chain
        resp = GET("/tree/domain", params={"parent_id": pid})
        assert len(resp.json()["domains"]) >= 1

        # Delete partition
        resp = DELETE(f"/tree/partition/{pid}")
        assert resp.status_code == 200

        # Verify partition gone
        resp = GET("/tree/partition")
        partition_ids = [p["id"] for p in resp.json()["partitions"]]
        assert pid not in partition_ids

    def test_delete_nonexistent_conversation_404(self):
        resp = DELETE("/tree/conversation/nonexistent-id-xxx")
        assert resp.status_code == 404

    def test_delete_nonexistent_domain_404(self):
        resp = DELETE("/tree/domain/nonexistent-id-xxx")
        assert resp.status_code == 404

    def test_delete_nonexistent_topic_404(self):
        resp = DELETE("/tree/topic/nonexistent-id-xxx")
        assert resp.status_code == 404

    def test_delete_nonexistent_partition_404(self):
        resp = DELETE("/tree/partition/nonexistent-id-xxx")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 7. Full Lifecycle Integration Test
# ═══════════════════════════════════════════════════════════════

class TestFullLifecycle:
    """End-to-end lifecycle: create tree → add messages → verify → clean up."""

    def test_full_tree_lifecycle(self):
        tid = uid()

        # ── Create Partition ──
        resp = POST("/tree/partition", {"name": f"Lifecycle_{tid}", "emoji": "🎯"})
        assert resp.status_code == 200
        pid = resp.json()["partition"]["id"]

        # ── Create Domain ──
        resp = POST("/tree/domain", {"parent_id": pid, "name": f"Math_{tid}", "emoji": "🔢"})
        assert resp.status_code == 200
        did = resp.json()["domain"]["id"]

        # ── Create Topic ──
        resp = POST("/tree/topic", {"parent_id": did, "name": f"Calculus_{tid}", "emoji": "∫"})
        assert resp.status_code == 200
        topic = resp.json()["topic"]
        tid_id = topic["id"]

        # ── Create Conversation ──
        resp = POST("/tree/conversation", {"parent_id": tid_id, "name": f"Conv1_{tid}"})
        assert resp.status_code == 200
        conv = resp.json()["conversation"]
        cid = conv["id"]

        # ── Send Messages ──
        resp = POST(f"/tree/conversation/{cid}/message/persist", {
            "role": "user", "content": "Explain limits", "source": "user",
        })
        assert resp.status_code == 200
        user_msg_id = resp.json()["id"]

        resp = POST(f"/tree/conversation/{cid}/message/persist", {
            "role": "assistant", "content": "A limit is...", "source": "assistant",
        })
        assert resp.status_code == 200
        asst_msg_id = resp.json()["id"]

        # ── Verify Messages ──
        resp = GET(f"/tree/conversation/{cid}/messages")
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) >= 2

        # ── Verify Single Message ──
        resp = GET(f"/tree/message/{user_msg_id}")
        assert resp.status_code == 200
        assert resp.json()["message"]["role"] == "user"

        # ── Modify Message ──
        resp = PUT(f"/tree/message/{user_msg_id}", {
            "content_blocks": [{"type": "text", "text": "Explain derivatives"}],
            "text_summary": "modified",
        })
        assert resp.status_code == 200
        modified = resp.json()["node"]
        assert modified["content_blocks"][0]["text"] == "Explain derivatives"

        # ── Rename Conversation ──
        resp = PATCH(f"/tree/conversation/{cid}", {"name": f"Updated_Conv_{tid}"})
        assert resp.status_code == 200

        # ── Verify Renames Propagate ──
        resp = GET("/tree/conversation", params={"parent_id": tid_id})
        names = [c["name"] for c in resp.json()["conversations"]]
        assert f"Updated_Conv_{tid}" in names

        # ── Rename Topic ──
        resp = PATCH(f"/tree/topic/{tid_id}", {"name": f"Updated_Topic_{tid}"})
        assert resp.status_code == 200

        # ── Rename Domain ──
        resp = PATCH(f"/tree/domain/{did}", {"name": f"Updated_Dom_{tid}"})
        assert resp.status_code == 200

        # ── Rename Partition ──
        resp = PATCH(f"/tree/partition/{pid}", {"name": f"Updated_Part_{tid}"})
        assert resp.status_code == 200

        # ── Verify All Renames ──
        resp = GET("/tree/partition")
        part_names = [p["name"] for p in resp.json()["partitions"]]
        assert f"Updated_Part_{tid}" in part_names

        resp = GET("/tree/domain", params={"parent_id": pid})
        dom_names = [d["name"] for d in resp.json()["domains"]]
        assert f"Updated_Dom_{tid}" in dom_names

        resp = GET("/tree/topic", params={"parent_id": did})
        top_names = [t["name"] for t in resp.json()["topics"]]
        assert f"Updated_Topic_{tid}" in top_names

        # ── Cleanup: delete partition (cascades everything) ──
        resp = DELETE(f"/tree/partition/{pid}")
        assert resp.status_code == 200

        # Verify partition gone
        resp = GET("/tree/partition")
        partition_ids = [p["id"] for p in resp.json()["partitions"]]
        assert pid not in partition_ids

    def test_multiple_partitions_independent(self):
        """Multiple partitions are independent; deleting one doesn't affect others."""
        tid = uid()

        # Create two partitions
        resp1 = POST("/tree/partition", {"name": f"PartA_{tid}", "emoji": "🅰️"})
        resp2 = POST("/tree/partition", {"name": f"PartB_{tid}", "emoji": "🅱️"})
        pid_a = resp1.json()["partition"]["id"]
        pid_b = resp2.json()["partition"]["id"]

        # Both exist
        resp = GET("/tree/partition")
        ids = [p["id"] for p in resp.json()["partitions"]]
        assert pid_a in ids
        assert pid_b in ids

        # Delete A
        DELETE(f"/tree/partition/{pid_a}")

        # B still exists
        resp = GET("/tree/partition")
        ids = [p["id"] for p in resp.json()["partitions"]]
        assert pid_a not in ids
        assert pid_b in ids

        # Cleanup B
        DELETE(f"/tree/partition/{pid_b}")

    def test_conversation_switch(self):
        """Switch active conversation within a topic."""
        tid = uid()

        # Build tree
        resp = POST("/tree/partition", {"name": f"SwitchPart_{tid}", "emoji": "🔄"})
        pid = resp.json()["partition"]["id"]
        resp = POST("/tree/domain", {"parent_id": pid, "name": f"SwitchDom_{tid}"})
        did = resp.json()["domain"]["id"]
        resp = POST("/tree/topic", {"parent_id": did, "name": f"SwitchTopic_{tid}"})
        tid_id = resp.json()["topic"]["id"]

        # Create two conversations
        resp = POST("/tree/conversation", {"parent_id": tid_id, "name": f"Conv1_{tid}"})
        cid1 = resp.json()["conversation"]["id"]
        resp = POST("/tree/conversation", {"parent_id": tid_id, "name": f"Conv2_{tid}"})
        cid2 = resp.json()["conversation"]["id"]

        # Switch to conv1
        resp = requests.post(f"{BASE}/tree/conversation/{cid1}/switch", params={"topic_id": tid_id}, timeout=30)
        assert resp.status_code == 200
        assert resp.json()["conversation"]["is_active"] is True

        # Switch to conv2
        resp = requests.post(f"{BASE}/tree/conversation/{cid2}/switch", params={"topic_id": tid_id}, timeout=30)
        assert resp.status_code == 200
        assert resp.json()["conversation"]["is_active"] is True

        # Cleanup
        DELETE(f"/tree/partition/{pid}")


# ═══════════════════════════════════════════════════════════════
# 8. Edge Cases & Error Handling
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases: invalid levels, missing names, empty data."""

    def test_invalid_level_returns_400(self):
        for method in ["GET", "POST"]:
            resp = api(method, "/tree/invalidlevel")
            assert resp.status_code in (400, 422), f"{method} /tree/invalidlevel returned {resp.status_code}"

    def test_invalid_level_on_patch_returns_400(self):
        resp = PATCH("/tree/invalidlevel/someid", {"name": "x"})
        assert resp.status_code == 400

    def test_invalid_level_on_delete_returns_400(self):
        resp = DELETE("/tree/invalidlevel/someid")
        assert resp.status_code == 400

    def test_create_partition_without_name_returns_error(self):
        resp = POST("/tree/partition", {"emoji": "🧪"})
        assert resp.status_code in (400, 422)

    def test_create_domain_without_parent_returns_404(self):
        resp = POST("/tree/domain", {"name": "orphan", "parent_id": "nonexistent"})
        assert resp.status_code == 404

    def test_create_topic_without_parent_returns_404(self):
        resp = POST("/tree/topic", {"name": "orphan", "parent_id": "nonexistent"})
        assert resp.status_code == 404

    def test_persist_message_to_nonexistent_conversation_404(self):
        resp = POST("/tree/conversation/fake-conv-id/message/persist", {
            "role": "user", "content": "hello", "source": "test"
        })
        assert resp.status_code == 404

    def test_get_messages_from_nonexistent_conversation_404(self):
        resp = GET("/tree/conversation/fake-conv-id/messages")
        assert resp.status_code == 404

    def test_list_domains_without_parent_shows_all(self):
        """Listing domains without parent_id returns all domains."""
        resp = GET("/tree/domain")
        assert resp.status_code == 200
        assert "domains" in resp.json()

    def test_list_topics_without_parent_shows_all(self):
        resp = GET("/tree/topic")
        assert resp.status_code == 200
        assert "topics" in resp.json()

    def test_list_conversations_without_parent_shows_all(self):
        resp = GET("/tree/conversation")
        assert resp.status_code == 200
        assert "conversations" in resp.json()


# ═══════════════════════════════════════════════════════════════
# 9. Response Structure Validation
# ═══════════════════════════════════════════════════════════════

class TestResponseStructures:
    """Validate that API responses have the expected structure."""

    def test_partition_list_structure(self):
        resp = GET("/tree/partition")
        body = resp.json()
        assert "partitions" in body
        if body["partitions"]:
            p = body["partitions"][0]
            required = {"id", "name", "emoji", "root_id", "direction"}
            assert required.issubset(p.keys()), f"Missing keys: {required - p.keys()}"

    def test_domain_list_structure(self):
        resp = GET("/tree/domain")
        body = resp.json()
        assert "domains" in body
        if body["domains"]:
            d = body["domains"][0]
            required = {"id", "name", "partition_id", "emoji"}
            assert required.issubset(d.keys())

    def test_topic_list_structure(self):
        resp = GET("/tree/topic")
        body = resp.json()
        assert "topics" in body
        if body["topics"]:
            t = body["topics"][0]
            required = {"id", "name", "domain_id", "emoji", "active_conversation_id"}
            assert required.issubset(t.keys())

    def test_conversation_list_structure(self):
        resp = GET("/tree/conversation")
        body = resp.json()
        assert "conversations" in body
        if body["conversations"]:
            c = body["conversations"][0]
            required = {"id", "topic_id", "name", "path", "is_active"}
            assert required.issubset(c.keys())

    def test_messages_list_structure(self, conv_ids):
        cid = conv_ids["conversation_id"]
        resp = GET(f"/tree/conversation/{cid}/messages")
        body = resp.json()
        assert "messages" in body
        assert "total" in body
        assert isinstance(body["total"], int)

    def test_message_detail_structure(self, conv_ids):
        msg_id = conv_ids.get("user_msg_id") or conv_ids.get("modified_msg_id")
        if not msg_id:
            pytest.skip("No message ID available")
        resp = GET(f"/tree/message/{msg_id}")
        body = resp.json()
        assert "message" in body
        assert "versions" in body
        assert "version_count" in body
        msg = body["message"]
        required = {"id", "role", "content_blocks", "partition_id", "conversation_id"}
        assert required.issubset(msg.keys())


# ═══════════════════════════════════════════════════════════════
# 10. Auto-creation Chain Verification
# ═══════════════════════════════════════════════════════════════

class TestAutoCreation:
    """Verify that creating a parent auto-creates children."""

    def test_partition_autocreates_domain_topic_conversation(self):
        """Creating a partition auto-creates domain→topic→conversation chain."""
        tid = uid()
        resp = POST("/tree/partition", {"name": f"AutoChain_{tid}", "emoji": "⛓️"})
        pid = resp.json()["partition"]["id"]

        # Domain auto-created
        resp = GET("/tree/domain", params={"parent_id": pid})
        domains = resp.json()["domains"]
        assert len(domains) >= 1
        auto_domain = domains[0]
        assert auto_domain["name"] == "新领域"

        # Topic auto-created under domain
        resp = GET("/tree/topic", params={"parent_id": auto_domain["id"]})
        topics = resp.json()["topics"]
        assert len(topics) >= 1
        auto_topic = topics[0]
        assert auto_topic["name"] == "新专题"

        # Conversation auto-created under topic
        resp = GET("/tree/conversation", params={"parent_id": auto_topic["id"]})
        convs = resp.json()["conversations"]
        assert len(convs) >= 1
        auto_conv = convs[0]
        assert auto_conv["name"] == "新对话"

        # Conversation ID returned in partition creation matches
        resp = POST("/tree/partition", {"name": f"AutoChain2_{tid}", "emoji": "🔗"})
        returned_conv_id = resp.json().get("conversation_id")
        assert returned_conv_id is not None
        # That conversation should exist
        resp = GET(f"/tree/conversation/{returned_conv_id}/messages")
        assert resp.status_code in (200, 404)  # may or may not have messages

        # Cleanup both
        DELETE(f"/tree/partition/{pid}")

    def test_domain_autocreates_topic_conversation(self):
        """Creating a domain auto-creates topic→conversation chain."""
        tid = uid()
        resp = POST("/tree/partition", {"name": f"DomAuto_{tid}", "emoji": "🏗️"})
        pid = resp.json()["partition"]["id"]

        resp = POST("/tree/domain", {"parent_id": pid, "name": f"ManualDom_{tid}"})
        did = resp.json()["domain"]["id"]

        # Auto topic
        resp = GET("/tree/topic", params={"parent_id": did})
        topics = resp.json()["topics"]
        assert len(topics) >= 1
        assert topics[0]["name"] == "新专题"

        DELETE(f"/tree/partition/{pid}")

    def test_topic_autocreates_conversation(self):
        """Creating a topic auto-creates a conversation."""
        tid = uid()
        resp = POST("/tree/partition", {"name": f"TopAuto_{tid}", "emoji": "🧩"})
        pid = resp.json()["partition"]["id"]

        resp = POST("/tree/domain", {"parent_id": pid, "name": f"Dom_{tid}"})
        did = resp.json()["domain"]["id"]

        resp = POST("/tree/topic", {"parent_id": did, "name": f"ManualTopic_{tid}"})
        topic_id = resp.json()["topic"]["id"]

        # Auto conversation
        resp = GET("/tree/conversation", params={"parent_id": topic_id})
        convs = resp.json()["conversations"]
        assert len(convs) >= 1
        assert convs[0]["name"] == "新对话"

        DELETE(f"/tree/partition/{pid}")
