"""LI-04 SessionMissionProvider 单元测试。"""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ── Mock objects ──────────────────────────────────────────


class MockSession:
    def __init__(self, title="TCP 三次握手", stage="learn", mission_analysis=None, mission=None):
        self.id = "s_001"
        self.learner_id = "user_001"
        self.title = title
        self.stage = stage
        self.status = "active"
        self.mission = mission
        self.mission_analysis = mission_analysis


class MockSessionMission:
    def __init__(self, title="TCP 三次握手"):
        self.title = title
        self.estimated_minutes = 20
        self.steps = []


class MockSessionRepo:
    def __init__(self, sessions=None):
        self._sessions = sessions or []

    def list_active_by_learner(self, user_id):
        return self._sessions


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_mission_analysis():
    return {
        "concepts": [
            {"name": "SYN", "importance": "high", "description": "同步序列号"},
            {"name": "ACK", "importance": "high", "description": "确认信号"},
        ],
        "learning_objectives": [
            "能够描述三次握手每一步发生了什么",
            "能解释为什么需要第三次握手",
        ],
        "difficulty_spots": [
            {"point": "第二次握手同时携带 SYN+ACK", "common_misconception": "认为第二次握手只是确认", "difficulty_level": 4},
        ],
        "dependencies": [],
        "practice_strategy": None,
        "reflection_focus": [],
        "growth_signals": {"expected_gains": [], "observation_points": []},
    }


@pytest.fixture
def context_input():
    return type("ContextInput", (), {
        "user_id": "user_001",
        "dir_id": "dir_001",
        "user_text": "你好",
        "conv_id": "conv_001",
    })()


# ── Tests ────────────────────────────────────────────────


class TestSessionMissionProvider:
    """SessionMissionProvider.build() 测试。"""

    @pytest.mark.asyncio
    async def test_with_active_session_and_analysis(self, sample_mission_analysis, context_input):
        """活跃 Session + 完整 MissionAnalysis → 包含概念/目标/难点。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session = MockSession(
            title="TCP 三次握手",
            stage="learn",
            mission_analysis=sample_mission_analysis,
            mission=MockSessionMission("TCP 三次握手"),
        )
        repo = MockSessionRepo(sessions=[session])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is not None
        text = result.text
        assert "TCP 三次握手" in text
        assert "SYN" in text
        assert "ACK" in text
        assert "能够描述三次握手每一步发生了什么" in text
        assert "第二次握手同时携带 SYN+ACK" in text
        assert "常见误区" in text
        assert "learn" in text  # stage
        assert "引导思考" in text  # 对话原则

    @pytest.mark.asyncio
    async def test_with_active_session_no_analysis(self, context_input):
        """活跃 Session 但没有 MissionAnalysis → 只有标题 + 阶段。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session = MockSession(title="TCP 三次握手", stage="intro")
        repo = MockSessionRepo(sessions=[session])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is not None
        text = result.text
        assert "TCP 三次握手" in text
        assert "intro" in text
        assert "SYN" not in text  # 没有 analysis，所以不包含概念

    @pytest.mark.asyncio
    async def test_no_active_session(self, context_input):
        """无活跃 Session → None。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        repo = MockSessionRepo(sessions=[])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is None

    @pytest.mark.asyncio
    async def test_session_without_title(self, context_input):
        """Session 无标题 → None。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session = MockSession(title="")
        repo = MockSessionRepo(sessions=[session])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is None

    @pytest.mark.asyncio
    async def test_repo_exception_returns_none(self, context_input):
        """Repo 抛出异常 → None（不崩溃）。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        class BrokenRepo:
            def list_active_by_learner(self, user_id):
                raise RuntimeError("DB error")

        provider = SessionMissionProvider(session_repo=BrokenRepo())

        result = await provider.build(context_input)
        assert result is None

    @pytest.mark.asyncio
    async def test_corrupted_mission_analysis_graceful(self, context_input):
        """MissionAnalysis 数据损坏 → 仍然返回标题 + 阶段（不崩溃）。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session = MockSession(
            title="TCP",
            stage="learn",
            mission_analysis={"concepts": "不是列表"},  # 损坏的数据
            mission=MockSessionMission("TCP"),
        )
        repo = MockSessionRepo(sessions=[session])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is not None
        text = result.text
        assert "TCP" in text
        assert "learn" in text

    @pytest.mark.asyncio
    async def test_pipeline_accepts_provider(self, sample_mission_analysis):
        """SessionMissionProvider 可以被 Context Pipeline 接受。"""
        from app.domain.conversation.context_pipeline import (
            ContextPipeline,
            ContextInput as CI,
        )
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session = MockSession(
            title="TCP",
            stage="learn",
            mission_analysis=sample_mission_analysis,
            mission=MockSessionMission("TCP"),
        )
        repo = MockSessionRepo(sessions=[session])
        provider = SessionMissionProvider(session_repo=repo)

        pipeline = ContextPipeline([provider])

        from dataclasses import dataclass, field
        @dataclass
        class TestInput:
            user_id: str = "user_001"
            dir_id: str = "dir_001"
            user_text: str = "你好"
            conv_id: str = ""
            previous_payloads: dict = field(default_factory=dict)
            agent_label: str = ""

        result = await pipeline.assemble(TestInput())
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_multiple_active_sessions(self, context_input):
        """多个活跃 Session 时取第一个。"""
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )

        session1 = MockSession(title="Session 1", stage="intro")
        session2 = MockSession(title="Session 2", stage="learn")
        repo = MockSessionRepo(sessions=[session1, session2])
        provider = SessionMissionProvider(session_repo=repo)

        result = await provider.build(context_input)
        assert result is not None
        assert "Session 1" in result.text  # 取第一个
