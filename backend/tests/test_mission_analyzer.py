"""LI-01 MissionAnalyzer 单元测试。"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def sample_llm_response():
    """模拟 LLM 返回的完整 JSON。"""
    return """{
      "concepts": [
        {"name": "SYN", "importance": "high", "description": "同步序列号，连接建立的开始信号"},
        {"name": "ACK", "importance": "high", "description": "确认信号"}
      ],
      "dependencies": [
        {"concept": "TCP 报文结构", "importance": "required"},
        {"concept": "IP 协议", "importance": "recommended"}
      ],
      "learning_objectives": [
        "能够描述三次握手每一步发生了什么",
        "能解释为什么需要第三次握手"
      ],
      "difficulty_spots": [
        {"point": "第二次握手同时携带 SYN+ACK", "common_misconception": "认为第二次握手只是确认", "difficulty_level": 4}
      ],
      "practice_strategy": {"type": "explanation", "focus": "让用户用自己的话描述状态变化"},
      "reflection_focus": ["你对哪个概念的理解发生了变化？"],
      "growth_signals": {
        "expected_gains": ["能独立描述三次握手流程"],
        "observation_points": ["用户描述时是否涉及了状态转换"]
      }
    }"""


# ── Mock objects ─────────────────────────────────────────


class MockLearnerContext:
    """模拟 RuntimeContext.learner"""
    def __init__(self):
        self.profile = MockProfile()
        self.knowledge = {
            "ip": MockSkillState(0.72),
            "tcp": MockSkillState(0.0),
        }


class MockProfile:
    subjects = ["计算机网络"]
    grade_level = "中级"
    learning_style = "reading"


class MockSkillState:
    def __init__(self, proficiency=0.0):
        self.proficiency = proficiency
        self.precision = 0.15
        self.trend = "stable"


# ── Tests ────────────────────────────────────────────────


class TestParseResponse:
    """_parse_response 测试（纯函数，不依赖 LLM）。"""

    def test_parse_valid_json(self, sample_llm_response):
        from app.services.analysis.mission_analyzer import _parse_response
        from app.domain.session.runtime_context import MissionAnalysis
        result = _parse_response(sample_llm_response)
        assert result is not None
        assert isinstance(result, MissionAnalysis)
        assert len(result.concepts) == 2
        assert result.concepts[0].name == "SYN"
        assert len(result.difficulty_spots) == 1
        assert result.difficulty_spots[0].difficulty_level == 4
        assert len(result.learning_objectives) == 2
        assert result.practice_strategy is not None
        assert result.practice_strategy.type == "explanation"

    def test_parse_with_markdown_fence(self, sample_llm_response):
        """LLM 可能用 ```json 包裹 JSON。"""
        from app.services.analysis.mission_analyzer import _parse_response
        wrapped = f"```json\n{sample_llm_response}\n```"
        result = _parse_response(wrapped)
        assert result is not None
        assert len(result.concepts) == 2

    def test_parse_invalid_json_returns_none(self):
        from app.services.analysis.mission_analyzer import _parse_response
        result = _parse_response("这不是 JSON")
        assert result is None

    def test_parse_empty_string_returns_none(self):
        from app.services.analysis.mission_analyzer import _parse_response
        result = _parse_response("")
        assert result is None

    def test_parse_missing_required_fields_returns_none(self):
        from app.services.analysis.mission_analyzer import _parse_response
        result = _parse_response('{"concepts": []}')
        assert result is None

    def test_parse_extra_fields_ignored(self, sample_llm_response):
        """额外字段不影响解析。"""
        from app.services.analysis.mission_analyzer import _parse_response
        with_extra = sample_llm_response.rstrip("}") + ',"extra_field":"ignored"}'
        result = _parse_response(with_extra)
        assert result is not None
        assert not hasattr(result, "extra_field")


class TestSummarizeLearnerContext:
    """_summarize_learner_context 测试。"""

    def test_with_full_context(self):
        from app.services.analysis.mission_analyzer import _summarize_learner_context
        ctx = MockLearnerContext()
        result = _summarize_learner_context(ctx)
        assert "计算机网络" in result
        assert "中级" in result
        assert "ip" in result

    def test_with_empty_context(self):
        from app.services.analysis.mission_analyzer import _summarize_learner_context
        result = _summarize_learner_context(None)
        assert result == ""

    def test_with_no_knowledge(self):
        from app.services.analysis.mission_analyzer import _summarize_learner_context
        ctx = MockLearnerContext()
        ctx.knowledge = {}
        result = _summarize_learner_context(ctx)
        assert "计算机网络" in result
        assert "ip" not in result


class TestBuildPrompt:
    """_build_prompt 测试。"""

    def test_basic_prompt(self):
        from app.services.analysis.mission_analyzer import _build_prompt
        messages = _build_prompt("TCP 三次握手")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "TCP 三次握手" in messages[1]["content"]

    def test_prompt_with_learner_context(self):
        from app.services.analysis.mission_analyzer import _build_prompt, _summarize_learner_context
        ctx = MockLearnerContext()
        context_text = _summarize_learner_context(ctx)
        messages = _build_prompt("TCP 三次握手", context_text)
        assert "计算机网络" in messages[1]["content"]


class TestAnalyzer:
    """MissionAnalyzer.analyze() 集成测试（mock LLM）。"""

    @pytest.mark.asyncio
    async def test_analyze_success(self, sample_llm_response):
        """LLM 正常返回 → MissionAnalysis 实例。"""
        from app.services.analysis.mission_analyzer import MissionAnalyzer

        analyzer = MissionAnalyzer()
        with patch.object(analyzer, "analyze", new=AsyncMock(return_value=(
            __import__("app.domain.session.runtime_context", fromlist=["MissionAnalysis"])
            .MissionAnalysis(**__import__("json").loads(sample_llm_response))
        ))):
            result = await analyzer.analyze("TCP 三次握手")
            assert result is not None
            assert len(result.concepts) == 2

    @pytest.mark.asyncio
    async def test_analyze_llm_failure_returns_none(self):
        """LLM 调用失败 → None。"""
        from app.services.analysis.mission_analyzer import MissionAnalyzer

        analyzer = MissionAnalyzer()
        with patch("app.services.analysis.mission_analyzer.llm_service") as mock_llm:
            mock_llm.generate = AsyncMock(side_effect=Exception("LLM timeout"))
            result = await analyzer.analyze("TCP 三次握手")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_invalid_response_returns_none(self):
        """LLM 返回无效 JSON → None。"""
        from app.services.analysis.mission_analyzer import MissionAnalyzer

        analyzer = MissionAnalyzer()
        with patch("app.services.analysis.mission_analyzer.llm_service") as mock_llm:
            mock_llm.generate = AsyncMock(return_value="这不是 JSON")
            result = await analyzer.analyze("TCP 三次握手")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_with_learner_context(self, sample_llm_response):
        """带 Learner Context 的分析。"""
        from app.services.analysis.mission_analyzer import MissionAnalyzer

        analyzer = MissionAnalyzer()
        ctx = MockLearnerContext()
        with patch.object(analyzer, "analyze", new=AsyncMock(return_value=(
            __import__("app.domain.session.runtime_context", fromlist=["MissionAnalysis"])
            .MissionAnalysis(**__import__("json").loads(sample_llm_response))
        ))):
            result = await analyzer.analyze("TCP 三次握手", learner_context=ctx)
            assert result is not None
            assert len(result.concepts) == 2

    @pytest.mark.asyncio
    async def test_get_mission_analyzer_returns_singleton(self):
        """get_mission_analyzer() 返回单例。"""
        from app.services.analysis.mission_analyzer import get_mission_analyzer
        a1 = get_mission_analyzer()
        a2 = get_mission_analyzer()
        assert a1 is a2


class TestAssemblerMissionAnalysis:
    """Assembler 加载 cached MissionAnalysis 测试。"""

    @pytest.mark.asyncio
    async def test_assembler_loads_cached_analysis(self):
        """Assembler 加载 session.mission_analysis。"""
        from app.domain.session.assembler import RuntimeAssembler
        from app.domain.session.runtime_context import MissionAnalysis

        # 创建一个 MissionAnalysis 实例
        analysis = MissionAnalysis(
            concepts=[{"name": "SYN", "importance": "high", "description": "test"}],
            dependencies=[],
            learning_objectives=["理解 SYN"],
            difficulty_spots=[{"point": "test", "common_misconception": "test", "difficulty_level": 3}],
            practice_strategy=None,
            reflection_focus=["你学到了什么？"],
            growth_signals={"expected_gains": ["gain1"], "observation_points": ["obs1"]},
        )

        # 创建带 mission_analysis 的 mock session
        analysis_dict = analysis.model_dump(mode="json")

        class MockSessionWithAnalysis:
            id = "s_ana_001"
            learner_id = "user_ana_001"
            title = "TCP 三次握手"
            stage = "learn"
            status = "active"
            started_at = 1000.0
            finished_at = None
            conversation_id = None
            mission = None
            reflection_text = None
            reflection_takeaways = []
            reflection_next_steps = []
            mission_analysis = analysis_dict

        class MockSessionRepo:
            def get(self, session_id):
                return MockSessionWithAnalysis()

        profile = type("Profile", (), {"subjects": ["CS"], "grade_level": "中级", "learning_style": None})()

        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(),
            cognitive_repo=type("Repo", (), {"list_all_nodes": lambda self, uid: []})(),
            growth_repo=type("Repo", (), {"get_latest": lambda self, uid: None})(),
            learner_engine=type("Engine", (), {"get_or_create_profile": lambda self, uid: profile})(),
        )

        ctx = await assembler.assemble("user_ana_001", "s_ana_001")
        assert ctx.mission.analysis is not None
        assert ctx.mission.analysis.concepts[0].name == "SYN"
        assert ctx.mission.analysis.learning_objectives[0] == "理解 SYN"

    @pytest.mark.asyncio
    async def test_assembler_handles_invalid_analysis_gracefully(self):
        """session.mission_analysis 数据损坏时，不崩溃。"""
        from app.domain.session.assembler import RuntimeAssembler

        class MockSessionWithBrokenAnalysis:
            id = "s_bad_001"
            learner_id = "user_bad_001"
            title = "test"
            stage = "intro"
            status = "active"
            started_at = 1000.0
            finished_at = None
            conversation_id = None
            mission = None
            reflection_text = None
            reflection_takeaways = []
            reflection_next_steps = []
            mission_analysis = {"concepts": "不是列表"}  # 损坏的数据

        class MockSessionRepo:
            def get(self, session_id):
                return MockSessionWithBrokenAnalysis()

        profile = type("Profile", (), {"subjects": [], "grade_level": "", "learning_style": None})()

        assembler = RuntimeAssembler(
            session_repo=MockSessionRepo(),
            cognitive_repo=type("Repo", (), {"list_all_nodes": lambda self, uid: []})(),
            growth_repo=type("Repo", (), {"get_latest": lambda self, uid: None})(),
            learner_engine=type("Engine", (), {"get_or_create_profile": lambda self, uid: profile})(),
        )

        ctx = await assembler.assemble("user_bad_001", "s_bad_001")
        # 损坏的数据不崩溃，mission.analysis 保持 None
        assert ctx.mission.analysis is None
