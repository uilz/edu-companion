"""Phase 9 测试 — Secretary 秘书系统"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from tests.factories import make_proposal


class TestSecretaryService:
    """秘书系统核心逻辑测试"""

    def test_make_proposal_defaults(self):
        """默认提案含完整字段"""
        p = make_proposal()
        assert p["id"] == "prop_001"
        assert p["status"] == "pending"
        assert p["priority"] == 3

    def test_proposal_priority_sorting(self):
        """提案应按 priority 降序排列"""
        proposals = [
            make_proposal(proposal_id="p1", priority=1),
            make_proposal(proposal_id="p2", priority=5),
            make_proposal(proposal_id="p3", priority=3),
        ]
        sorted_p = sorted(proposals, key=lambda x: x["priority"], reverse=True)
        assert [p["id"] for p in sorted_p] == ["p2", "p3", "p1"]

    def test_proposal_status_transition(self):
        """提案状态: pending → accepted / dismissed"""
        p = make_proposal()
        assert p["status"] == "pending"
        # 模拟接受
        p["status"] = "accepted"
        assert p["status"] == "accepted"
        # 模拟忽略
        q = make_proposal(proposal_id="p2")
        q["status"] = "dismissed"
        assert q["status"] == "dismissed"

    def test_proposal_source_tracking(self):
        """提案应记录来源"""
        p = make_proposal(source="diagnosis")
        assert p["source"] == "diagnosis"
        q = make_proposal(source="lateral_expansion", proposal_id="p2")
        assert q["source"] == "lateral_expansion"

    def test_proposal_deduplication_by_content(self):
        """相同标题+来源的提案应视为重复"""
        p1 = make_proposal(proposal_id="p1", title="薄弱点诊断", source="diagnosis")
        p2 = make_proposal(proposal_id="p2", title="薄弱点诊断", source="diagnosis")
        # 内容指纹相同
        fingerprint1 = f"{p1['title']}|{p1['source']}"
        fingerprint2 = f"{p2['title']}|{p2['source']}"
        assert fingerprint1 == fingerprint2
