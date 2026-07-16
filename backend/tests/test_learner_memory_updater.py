"""LI-03 LearnerMemoryUpdater 单元测试。"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).resolve().parent.parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.domain.session.runtime_context import (
    LearnerDelta,
    KnowledgeUpdate,
)


# ── Mock 对象 ────────────────────────────────────────────


class MockBelief:
    def __init__(self, alpha=2.0, beta=2.0, last_updated=None):
        self.alpha = alpha
        self.beta = beta
        s = alpha + beta
        self.proficiency_mean = alpha / s if s > 0 else 0.5
        self.proficiency_precision = s
        self.peak_proficiency = alpha / s if s > 0 else 0.5
        self.last_updated = last_updated or time.time()


class MockCognitiveNode:
    def __init__(self, id="tcp", label="TCP", belief=None):
        self.id = id
        self.label = label
        self.belief = belief or MockBelief()


class MockGrowthRecord:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self, mode="json"):
        return {"id": getattr(self, "id", "gr_001"), "summary": getattr(self, "summary", "")}


class MockCognitiveRepo:
    def __init__(self):
        self.nodes = {}

    def get_node(self, node_id, user_id="default"):
        return self.nodes.get(node_id)

    def upsert_node(self, node, user_id="default"):
        self.nodes[node.id] = node


class MockCognitiveRegistry:
    def execute(self, operation, **kwargs):
        # 模拟 belief_update 的执行结果
        belief_state = kwargs.get("belief_state", {})
        alpha = belief_state.get("belief_alpha", 2.0)
        beta = belief_state.get("belief_beta", 2.0)
        success = kwargs.get("success", True)
        weight = kwargs.get("weight", 1.0)

        if success:
            alpha += weight
        else:
            beta += weight

        return {
            "subsystem": "belief",
            "method": "belief_update",
            "result_summary": f"alpha={alpha} beta={beta}",
            "belief_after": {
                "belief_alpha": alpha,
                "belief_beta": beta,
                "belief_evidence_count": 1,
                "belief_last_updated": time.time(),
                "stability_factor": 0.5,
                "forgetting_rate": 0.1,
                "last_information_gain": 0.1,
                "total_information_gain": 0.5,
            },
            "information_gain": 0.1,
        }


class MockGrowthRepo:
    def __init__(self):
        self.records = []

    def save(self, record):
        self.records.append(record)
        return record


class MockLearnerEngine:
    def __init__(self):
        self.updated = False

    def get_or_create_profile(self, user_id):
        return MagicMock()

    def update_profile(self, user_id, updates):
        self.updated = True


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_learner_delta():
    return LearnerDelta(
        knowledge_updates=[
            KnowledgeUpdate(skill_id="tcp", confidence_shift=0.3, evidence="用户能描述三步时序"),
            KnowledgeUpdate(skill_id="tcp_syn", confidence_shift=0.4, evidence="用户理解 SYN"),
        ],
        reasoning_insights=["用户倾向于用类比理解"],
        growth_insights=["用户能用自己的语言描述流程"],
    )


@pytest.fixture
def updater_with_mocks():
    """带完整 mock 依赖的 LearnerMemoryUpdater。"""
    cognitive_repo = MockCognitiveRepo()
    cognitive_repo.nodes["tcp"] = MockCognitiveNode(id="tcp", label="TCP", belief=MockBelief(alpha=3.0, beta=5.0))
    cognitive_repo.nodes["tcp_syn"] = MockCognitiveNode(id="tcp_syn", label="SYN", belief=MockBelief(alpha=2.0, beta=2.0))

    registry = MockCognitiveRegistry()
    growth_repo = MockGrowthRepo()
    learner_engine = MockLearnerEngine()

    from app.services.memory.learner_memory_updater import LearnerMemoryUpdater
    return LearnerMemoryUpdater(
        cognitive_repo=cognitive_repo,
        cognitive_registry=registry,
        growth_repo=growth_repo,
        learner_engine=learner_engine,
    ), cognitive_repo, growth_repo


# ── Tests ────────────────────────────────────────────────


class TestHelperFunctions:
    """_confidence_shift_to_belief_params 测试。"""

    def test_positive_shift(self):
        from app.services.memory.learner_memory_updater import _confidence_shift_to_belief_params
        success, weight = _confidence_shift_to_belief_params(0.3)
        assert success is True
        assert weight == 0.6  # min(0.3 * 2, 1.0)

    def test_negative_shift(self):
        from app.services.memory.learner_memory_updater import _confidence_shift_to_belief_params
        success, weight = _confidence_shift_to_belief_params(-0.4)
        assert success is False
        assert weight == 0.8  # min(0.4 * 2, 1.0)

    def test_zero_shift(self):
        from app.services.memory.learner_memory_updater import _confidence_shift_to_belief_params
        success, weight = _confidence_shift_to_belief_params(0.0)
        assert success is True
        assert weight == 0.0

    def test_max_shift(self):
        from app.services.memory.learner_memory_updater import _confidence_shift_to_belief_params
        success, weight = _confidence_shift_to_belief_params(1.0)
        assert success is True
        assert weight == 1.0

    def test_max_negative_shift(self):
        from app.services.memory.learner_memory_updater import _confidence_shift_to_belief_params
        success, weight = _confidence_shift_to_belief_params(-1.0)
        assert success is False
        assert weight == 1.0


class TestApplyKnowledgeUpdate:
    """_apply_knowledge_update 测试。"""

    def test_successful_update(self, updater_with_mocks):
        updater, cognitive_repo, _ = updater_with_mocks
        result = updater._apply_knowledge_update(
            user_id="user_001",
            skill_id="tcp",
            confidence_shift=0.3,
            evidence="理解 TCP 流程",
        )
        assert result is not None
        assert result["skill"] == "tcp"
        assert result["before"] == 0.375  # 3.0 / (3.0 + 5.0)
        assert result["after"] > result["before"]
        assert "evidence" in result

        # 验证 CognitiveNode 被更新
        node = cognitive_repo.nodes["tcp"]
        assert node.belief.alpha == 3.6  # 3.0 + 0.6
        assert node.belief.proficiency_mean > 0.375

    def test_negative_update_decreases_proficiency(self, updater_with_mocks):
        updater, cognitive_repo, _ = updater_with_mocks
        result = updater._apply_knowledge_update(
            user_id="user_001",
            skill_id="tcp_syn",
            confidence_shift=-0.5,
            evidence="用户混淆了 SYN",
        )
        assert result is not None
        node = cognitive_repo.nodes["tcp_syn"]
        assert node.belief.beta == 3.0  # 2.0 + 1.0
        assert node.belief.proficiency_mean < 0.5

    def test_node_not_found(self, updater_with_mocks):
        updater, _, _ = updater_with_mocks
        result = updater._apply_knowledge_update(
            user_id="user_001",
            skill_id="nonexistent",
            confidence_shift=0.3,
            evidence="test",
        )
        assert result is None


class TestApplyLearnerDelta:
    """apply_learner_delta 集成测试。"""

    @pytest.mark.asyncio
    async def test_full_flow(self, updater_with_mocks, sample_learner_delta):
        updater, cognitive_repo, growth_repo = updater_with_mocks

        result = await updater.apply_learner_delta(
            user_id="user_001",
            session_id="s_001",
            session_title="TCP 三次握手",
            session_started_at=time.time() - 1800,
            learner_delta=sample_learner_delta,
            reflection={
                "content": "今天学到了 TCP 三次握手",
                "key_takeaways": ["SYN 是连接请求"],
            },
        )

        assert result["bkt_updated"] == 2  # 更新了两个节点
        assert len(result["growth_record_id"]) > 0  # GrowthRecord 已创建
        assert result["patterns_updated"] is True  # 推理模式已更新

        # 验证 BKT 更新
        tcp_node = cognitive_repo.nodes["tcp"]
        assert tcp_node.belief.alpha > 3.0  # alpha 增加

        # 验证 GrowthRecord 已保存
        assert len(growth_repo.records) == 1
        record = growth_repo.records[0]
        assert record.summary == "今天学到了 TCP 三次握手"

    @pytest.mark.asyncio
    async def test_no_learner_delta(self, updater_with_mocks):
        """无 learner_delta 时仍然创建 GrowthRecord。"""
        updater, _, growth_repo = updater_with_mocks

        result = await updater.apply_learner_delta(
            user_id="user_001",
            session_id="s_002",
            session_title="新知识",
            session_started_at=time.time() - 900,
            learner_delta=None,
            reflection={
                "content": "今天学了很多",
                "key_takeaways": [],
            },
        )

        assert result["bkt_updated"] == 0
        assert len(result["growth_record_id"]) > 0
        assert len(growth_repo.records) == 1

    @pytest.mark.asyncio
    async def test_skipped_reflection(self, updater_with_mocks, sample_learner_delta):
        """Reflection 跳过时，用 growth_insights 生成最小记录。"""
        updater, _, growth_repo = updater_with_mocks

        result = await updater.apply_learner_delta(
            user_id="user_001",
            session_id="s_003",
            session_title="TCP 三次握手",
            session_started_at=time.time() - 1800,
            learner_delta=sample_learner_delta,
            reflection=None,  # 跳过
        )

        assert result["bkt_updated"] == 2
        assert result["incomplete"] is True
        record = growth_repo.records[0]
        assert "自己的语言描述" in record.summary or record.summary != ""

    @pytest.mark.asyncio
    async def test_empty_knowledge_updates(self, updater_with_mocks):
        """空 knowledge_updates 时不更新 BKT。"""
        updater, _, growth_repo = updater_with_mocks

        empty_delta = LearnerDelta(
            knowledge_updates=[],
            reasoning_insights=[],
            growth_insights=[],
        )

        result = await updater.apply_learner_delta(
            user_id="user_001",
            session_id="s_004",
            session_title="测试",
            session_started_at=time.time(),
            learner_delta=empty_delta,
            reflection={"content": "测试", "key_takeaways": []},
        )

        assert result["bkt_updated"] == 0
        assert len(growth_repo.records) == 1

    @pytest.mark.asyncio
    async def test_get_memory_updater_returns_singleton(self):
        from app.services.memory.learner_memory_updater import get_memory_updater
        a1 = get_memory_updater()
        a2 = get_memory_updater()
        assert a1 is a2
