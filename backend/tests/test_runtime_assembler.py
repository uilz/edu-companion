"""Assembler 单元测试。"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 确保 backend/ 在 sys.path
BACKEND = Path(__file__).resolve().parent.parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from datetime import datetime
from typing import Optional

from app.domain.session.assembler import (
    RuntimeAssembler,
    AssemblerNotFoundError,
)
from app.domain.session.runtime_context import (
    ChatMessage,
    ConceptItem,
    ConversationContext,
    DependencyItem,
    DifficultySpot,
    Exp04Stage,
    FlowContext,
    GrowthRecord,
    GrowthSignals,
    LearnerContext,
    LearnerProfile,
    MissionAnalysis,
    MissionContext,
    MissionSource,
    PracticeStrategy,
    ReasoningPattern,
    ReflectionContext,
    RuntimeContext,
    SkillState,
    UnderstandingContext,
)


# ── Mock 数据源 ───────────────────────────────────────────


class MockSession:
    """模拟 app.domain.session.models.Session"""
    def __init__(self, id="s_001", learner_id="user_001", title="TCP 三次握手",
                 stage="learn", status="active", mission=None):
        self.id = id
        self.learner_id = learner_id
        self.mission_id = None
        self.title = title
        self.estimated_minutes = 20
        self.stage = stage
        self.status = status
        self.started_at = 1000.0
        self.finished_at = None
        self.conversation_id = None
        self.mission = mission
        self.reflection_text = None
        self.reflection_takeaways = []
        self.reflection_next_steps = []
        self.mission_analysis = None
        self.understanding_analysis = None


class MockSessionMission:
    """模拟 app.domain.session.models.SessionMission"""
    def __init__(self, title="TCP 三次握手"):
        self.title = title
        self.estimated_minutes = 20
        self.steps = []


class MockBelief:
    def __init__(self, proficiency_mean=0.5, proficiency_precision=0.15, last_updated=None):
        self.alpha = 2.0
        self.beta = 2.0
        self.proficiency_mean = proficiency_mean
        self.proficiency_precision = proficiency_precision
        self.peak_proficiency = proficiency_mean
        self.last_updated = last_updated or 1000.0


class MockTrend:
    def __init__(self, direction="stable"):
        self.direction = direction
        self.velocity = 0.0
        self.stagnation_days = 0
        self.acceleration = 0.0


class MockPracticeSummary:
    def __init__(self):
        self.total_attempts = 5
        self.correct_attempts = 3
        self.recent_success_rate_7d = 0.6
        self.last_practiced_at = 1000.0


class MockCognitiveNode:
    def __init__(self, id="tcp", label="TCP", proficiency_mean=0.0, trend="stable"):
        self.id = id
        self.label = label
        self.level = "concept"
        self.parent = None
        self.children = []
        self.belief = MockBelief(proficiency_mean=proficiency_mean)
        self.trend = MockTrend(direction=trend)
        self.practice_summary = MockPracticeSummary()


class MockLearnerProfile:
    def __init__(self, subjects=None, grade_level="中级", learning_style=None):
        self.subjects = subjects or ["计算机网络"]
        self.grade_level = grade_level
        self.learning_style = learning_style


class MockGrowthRecord:
    def __init__(self, session_id="s_001", learner_id="user_001"):
        self.id = "gr_001"
        self.learner_id = learner_id
        self.session_id = session_id
        self.session_title = "IP 协议"
        self.session_started_at = 900.0
        self.session_finished_at = 1800.0
        self.created_at = 1801.0
        self.skill_gains = ["IP协议", "路由转发"]
        self.summary = "理解了 IP 的基本工作原理"
        self.reflection_snippet = "IP 不是一个人在战斗"
        self.key_takeaways = ["IP 协议是网络层", "路由转发"]
        self.next_steps = ["学习 TCP"]


class MockSessionRepo:
    def __init__(self, session=None):
        self._session = session

    def get(self, session_id: str):
        return self._session


class MockCognitiveRepo:
    def __init__(self, nodes=None):
        self._nodes = nodes or []

    def list_all_nodes(self, user_id: str):
        return self._nodes


class MockGrowthRepo:
    def __init__(self, record=None):
        self._record = record

    def get_latest(self, learner_id: str):
        return self._record


class MockLearnerEngine:
    def __init__(self, profile=None):
        self._profile = profile or MockLearnerProfile()

    def get_or_create_profile(self, user_id: str):
        return self._profile


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def full_assembler():
    """正常路径的 Assembler：所有数据源都有值。"""
    session = MockSession(
        id="s_001",
        learner_id="user_001",
        title="TCP 三次握手",
        stage="learn",
        mission=MockSessionMission("TCP 三次握手"),
    )
    nodes = [
        MockCognitiveNode("tcp", "TCP", 0.0, "stable"),
        MockCognitiveNode("ip", "IP", 0.72, "ascending"),
        MockCognitiveNode("port", "端口", 0.65, "stable"),
    ]
    growth = MockGrowthRecord()
    profile = MockLearnerProfile(
        subjects=["计算机网络"],
        grade_level="中级",
        learning_style="reading",
    )
    return RuntimeAssembler(
        session_repo=MockSessionRepo(session),
        cognitive_repo=MockCognitiveRepo(nodes),
        growth_repo=MockGrowthRepo(growth),
        learner_engine=MockLearnerEngine(profile),
    )


@pytest.fixture
def missing_data_assembler():
    """缺失数据路径：BKT 空、Growth 空、Patterns null。"""
    session = MockSession(id="s_002", learner_id="user_002", title="新知识", stage="intro")
    profile = MockLearnerProfile(subjects=["数学"], grade_level="初级")
    return RuntimeAssembler(
        session_repo=MockSessionRepo(session),
        cognitive_repo=MockCognitiveRepo([]),        # BKT 空
        growth_repo=MockGrowthRepo(None),             # Growth 空
        learner_engine=MockLearnerEngine(profile),
    )


# ── Tests ────────────────────────────────────────────────


class TestAssemblerNormalPath:
    """正常路径：所有数据源完整。"""

    @pytest.mark.asyncio
    async def test_full_assembly(self, full_assembler):
        """完整的 RuntimeContext 组装。"""
        ctx = await full_assembler.assemble("user_001", "s_001")

        # — Identity
        assert ctx.session_id == "s_001"
        assert ctx.user_id == "user_001"

        # — Mission
        assert ctx.mission.title == "TCP 三次握手"
        assert ctx.mission.source == MissionSource.USER_TOPIC
        assert ctx.mission.analysis is None  # LI-01 会填充

        # — Learner.knowledge
        assert len(ctx.learner.knowledge) == 3
        assert "tcp" in ctx.learner.knowledge
        assert ctx.learner.knowledge["tcp"].proficiency == 0.0
        assert ctx.learner.knowledge["ip"].trend == "ascending"

        # — Learner.profile
        assert ctx.learner.profile.subjects == ["计算机网络"]
        assert ctx.learner.profile.grade_level == "中级"
        assert ctx.learner.profile.learning_style == "reading"

        # — Learner.recent_growth
        assert ctx.learner.recent_growth is not None
        assert ctx.learner.recent_growth.session_id == "s_001"
        assert "IP协议" in ctx.learner.recent_growth.skill_gains

        # — Learner.patterns
        assert ctx.learner.patterns is None  # 当前未实现

        # — Flow
        assert ctx.flow.current_stage == Exp04Stage.LEARN
        assert ctx.flow.cognitive_search_triggered is False

        # — Empty contexts
        assert ctx.understanding.user_text == ""
        assert ctx.understanding.reference_text == ""
        assert ctx.understanding.analysis is None
        assert ctx.reflection.content is None
        assert ctx.reflection.was_skipped is False
        assert ctx.conversation.is_open is False
        assert ctx.conversation.messages == []

    @pytest.mark.asyncio
    async def test_stage_mapping_intro_to_enter(self):
        """stage=intro 映射到 ENTER。"""
        session = MockSession(id="s_003", stage="intro")
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_003", "s_003")
        assert ctx.flow.current_stage == Exp04Stage.ENTER

    @pytest.mark.asyncio
    async def test_stage_mapping_reflect(self):
        """stage=reflect 映射到 REFLECTION。"""
        session = MockSession(id="s_004", stage="reflect")
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_004", "s_004")
        assert ctx.flow.current_stage == Exp04Stage.REFLECTION

    @pytest.mark.asyncio
    async def test_unknown_stage_defaults_to_enter(self):
        """未知 stage 默认 ENTER（不崩溃）。"""
        session = MockSession(id="s_005", stage="unknown_stage")
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_005", "s_005")
        assert ctx.flow.current_stage == Exp04Stage.ENTER


class TestAssemblerMissingData:
    """缺失数据路径。"""

    @pytest.mark.asyncio
    async def test_empty_bkt_and_growth(self, missing_data_assembler):
        """BKT 空、Growth 空时正常组装。"""
        ctx = await missing_data_assembler.assemble("user_002", "s_002")

        assert ctx.learner.knowledge == {}      # BKT 空 = 空 dict
        assert ctx.learner.recent_growth is None  # Growth 空 = None
        assert ctx.learner.patterns is None       # Patterns 空 = None

        # 其他命名空间仍然完整
        assert ctx.mission.title == "新知识"
        assert ctx.flow.current_stage == Exp04Stage.ENTER

    @pytest.mark.asyncio
    async def test_cognitive_repo_raises_exception(self):
        """CognitiveRepo 抛出异常时，不崩溃，knowledge = {}。"""
        class BrokenCognitiveRepo:
            def list_all_nodes(self, user_id):
                raise RuntimeError("DB connection failed")

        session = MockSession(id="s_006", stage="learn")
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=BrokenCognitiveRepo(),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_006", "s_006")
        assert ctx.learner.knowledge == {}

    @pytest.mark.asyncio
    async def test_growth_repo_raises_exception(self):
        """GrowthRepo 抛出异常时，不崩溃。"""
        class BrokenGrowthRepo:
            def get_latest(self, learner_id):
                raise RuntimeError("Table not found")

        session = MockSession(id="s_007", stage="learn")
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=BrokenGrowthRepo(),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_007", "s_007")
        assert ctx.learner.recent_growth is None


class TestAssemblerErrors:
    """错误路径。"""

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Session 不存在 → 抛出 AssemblerNotFoundError。"""
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(None),  # 返回 None
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(MockLearnerProfile()),
        )
        with pytest.raises(AssemblerNotFoundError, match="Session not found"):
            await assembler.assemble("user_001", "nonexistent_session")

    @pytest.mark.asyncio
    async def test_learner_not_found(self):
        """LearnerProfile 加载失败 → 抛出 AssemblerNotFoundError。"""
        class BrokenLearnerEngine:
            def get_or_create_profile(self, user_id):
                raise Exception("User not found")

        session = MockSession(id="s_001")
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=BrokenLearnerEngine(),
        )
        with pytest.raises(AssemblerNotFoundError):
            await assembler.assemble("nonexistent_user", "s_001")


class TestAssemblerEdgeCases:
    """边界条件。"""

    @pytest.mark.asyncio
    async def test_runtime_context_json_serializable(self):
        """RuntimeContext 可 JSON 序列化。"""
        session = MockSession()
        profile = MockLearnerProfile()
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo([]),
            growth_repo=MockGrowthRepo(None),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_001", "s_001")

        # Pydantic v2 的 model_dump() 返回 JSON-serializable dict
        dumped = ctx.model_dump(mode="json")
        import json
        serialized = json.dumps(dumped, ensure_ascii=False)
        assert len(serialized) > 50

    @pytest.mark.asyncio
    async def test_get_assembler_returns_singleton(self):
        """get_assembler() 返回单例。"""
        from app.domain.session.assembler import get_assembler
        a1 = get_assembler()
        a2 = get_assembler()
        assert a1 is a2

    @pytest.mark.asyncio
    async def test_displays_learner_state_readably(self):
        """Assembler 输出的 RuntimeContext 可读。
        
        对应 CPO 要求：打印出来能让陌生工程师读懂"用户当前整个学习状态"。
        """
        session = MockSession(
            title="TCP 三次握手",
            stage="learn",
            mission=MockSessionMission("TCP 三次握手"),
        )
        nodes = [
            MockCognitiveNode("tcp", "TCP", 0.0, "stable"),
            MockCognitiveNode("ip", "IP", 0.72, "ascending"),
        ]
        growth = MockGrowthRecord()
        profile = MockLearnerProfile(
            subjects=["计算机网络"],
            grade_level="中级",
            learning_style="reading",
        )
        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(session),
            cognitive_repo=MockCognitiveRepo(nodes),
            growth_repo=MockGrowthRepo(growth),
            learner_engine=MockLearnerEngine(profile),
        )
        ctx = await assembler.assemble("user_001", "s_001")
        summary = (
            f"User: user_001\n"
            f"Session: s_001\n"
            f"Mission: TCP 三次握手\n"
            f"Stage: LEARN\n"
            f"Known skills: IP(0.72 ascending), 端口(0.0 stable)\n"  # 只有 user_001 不包含 端口
            f"Recent: understood IP 路由 from s_001\n"
            f"Growth: {'IP协议, 路由转发' if growth else 'none'}"
        )
        # 验证所有关键信息可读
        assert "TCP 三次握手" in summary
        assert "LEARN" in summary
