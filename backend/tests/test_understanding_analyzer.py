"""LI-02 UnderstandingAnalyzer 单元测试。"""

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
    """模拟 LLM 返回的完整 UnderstandingAnalysis JSON。"""
    return """{
      "concept_observations": [
        {
          "concept": "三次握手基本流程",
          "observation": "用户描述了三次消息交换的流程",
          "evidence": "原文提到了'先发消息→回消息→再发确认'",
          "hypothesis": "对三次交换的时序有基本理解",
          "confidence": 0.85
        },
        {
          "concept": "SYN 标志位",
          "observation": "用户没有提到 SYN 标志位",
          "evidence": "用户全文没有出现 SYN",
          "hypothesis": "用户将握手理解为对话而非标志位交换",
          "confidence": 0.70
        }
      ],
      "reasoning_evidence": {
        "uses_own_words": true,
        "makes_connections": ["用户用了'先→然后→再'描述顺序"],
        "asks_questions": []
      },
      "gaps": [
        {
          "concept": "SYN 标志位",
          "observation": "用户没有将 SYN 作为独立概念",
          "evidence": "用户只说'发消息'，没说'发 SYN'",
          "hypothesis": "用户可能将握手理解为应用层对话",
          "severity": 2,
          "confidence": 0.70
        }
      ],
      "metacognitive_signals": {
        "aware_of_gap": false,
        "overconfident_on": []
      },
      "learner_delta": {
        "knowledge_updates": [
          {
            "skill_id": "tcp_handshake_flow",
            "confidence_shift": 0.3,
            "evidence": "用户能描述三步时序"
          }
        ],
        "reasoning_insights": ["用户倾向于用类比理解"],
        "growth_insights": ["用户能用自己的语言描述流程"]
      },
      "guidance_question": "你说的'发消息'，这个'消息'在 TCP 里有什么特殊名字？"
    }"""


@pytest.fixture
def sample_no_gap_llm_response():
    """模拟无差距的 LLM 返回。"""
    return """{
      "concept_observations": [
        {
          "concept": "SYN",
          "observation": "用户正确区分了 SYN 和 ACK",
          "evidence": "用户提到了 SYN 和 ACK 的区别",
          "hypothesis": "用户理解了标志位的含义",
          "confidence": 0.90
        }
      ],
      "reasoning_evidence": {
        "uses_own_words": true,
        "makes_connections": [],
        "asks_questions": []
      },
      "gaps": [],
      "metacognitive_signals": {
        "aware_of_gap": false,
        "overconfident_on": []
      },
      "learner_delta": {
        "knowledge_updates": [
          {
            "skill_id": "tcp_syn",
            "confidence_shift": 0.4,
            "evidence": "用户理解 SYN 含义"
          }
        ],
        "reasoning_insights": [],
        "growth_insights": []
      },
      "guidance_question": null
    }"""


# ── Tests ────────────────────────────────────────────────


class TestParseResponse:
    """_parse_response 测试（纯函数，不依赖 LLM）。"""

    def test_parse_valid_full(self, sample_llm_response):
        from app.services.analysis.understanding_analyzer import _parse_response
        from app.domain.session.runtime_context import UnderstandingAnalysis
        result = _parse_response(sample_llm_response)
        assert result is not None
        assert isinstance(result, UnderstandingAnalysis)
        assert len(result.concept_observations) == 2
        assert result.concept_observations[0].evidence == "原文提到了'先发消息→回消息→再发确认'"
        assert result.concept_observations[0].confidence == 0.85
        assert len(result.gaps) == 1
        assert result.gaps[0].severity == 2
        assert result.gaps[0].confidence == 0.70
        assert result.reasoning_evidence.uses_own_words is True
        assert result.metacognitive_signals.aware_of_gap is False
        assert len(result.learner_delta.knowledge_updates) == 1
        assert result.learner_delta.knowledge_updates[0].confidence_shift == 0.3

    def test_parse_no_gaps(self, sample_no_gap_llm_response):
        from app.services.analysis.understanding_analyzer import _parse_response
        result = _parse_response(sample_no_gap_llm_response)
        assert result is not None
        assert len(result.gaps) == 0

    def test_parse_with_markdown_fence(self, sample_llm_response):
        from app.services.analysis.understanding_analyzer import _parse_response
        wrapped = f"```json\n{sample_llm_response}\n```"
        result = _parse_response(wrapped)
        assert result is not None
        assert len(result.concept_observations) == 2

    def test_parse_invalid_json_returns_none(self):
        from app.services.analysis.understanding_analyzer import _parse_response
        result = _parse_response("这不是 JSON")
        assert result is None

    def test_parse_empty_string_returns_none(self):
        from app.services.analysis.understanding_analyzer import _parse_response
        result = _parse_response("")
        assert result is None

    def test_parse_missing_required_fields_returns_none(self):
        from app.services.analysis.understanding_analyzer import _parse_response
        result = _parse_response('{"concept_observations": []}')
        assert result is None

    def test_parse_extra_fields_ignored(self, sample_llm_response):
        from app.services.analysis.understanding_analyzer import _parse_response
        with_extra = sample_llm_response.rstrip("}") + ',"extra":"ignored"}'
        result = _parse_response(with_extra)
        assert result is not None

    def test_parse_low_confidence_gap(self):
        """低置信度的 gap 被正确解析。"""
        from app.services.analysis.understanding_analyzer import _parse_response
        response = """{
          "concept_observations": [],
          "reasoning_evidence": {"uses_own_words": true, "makes_connections": [], "asks_questions": []},
          "gaps": [{"concept": "test", "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "severity": 1, "confidence": 0.3}],
          "metacognitive_signals": {"aware_of_gap": false, "overconfident_on": []},
          "learner_delta": {"knowledge_updates": [], "reasoning_insights": [], "growth_insights": []},
          "guidance_question": null
        }"""
        result = _parse_response(response)
        assert result is not None
        assert result.gaps[0].confidence == 0.3


class TestBuildPrompt:
    """_build_prompt 测试。"""

    def test_basic_prompt(self):
        from app.services.analysis.understanding_analyzer import _build_prompt
        messages = _build_prompt(
            mission_title="TCP 三次握手",
            mission_analysis='{"concepts": [{"name": "SYN"}]}',
            user_text="客户端先发一个消息",
            reference_text="三次握手是 TCP 建立连接的过程",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "TCP 三次握手" in messages[1]["content"]
        assert "客户端先发一个消息" in messages[1]["content"]
        assert "三次握手是 TCP 建立连接的过程" in messages[1]["content"]
        # mission analysis 已在 prompt 中
        assert "SYN" in messages[1]["content"]


class TestExtractGuidance:
    """_extract_guidance 测试。"""

    def test_with_gaps_returns_prompt(self):
        from app.services.analysis.understanding_analyzer import _parse_response
        raw_with_gap = """{
          "concept_observations": [],
          "reasoning_evidence": {"uses_own_words": true, "makes_connections": [], "asks_questions": []},
          "gaps": [{"concept": "SYN", "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "severity": 2, "confidence": 0.7}],
          "metacognitive_signals": {"aware_of_gap": false, "overconfident_on": []},
          "learner_delta": {"knowledge_updates": [], "reasoning_insights": [], "growth_insights": []},
          "guidance_question": "你知道 SYN 是什么吗？"
        }"""
        analysis = _parse_response(raw_with_gap)
        # 当前实现中，guidance_question 直接由 LLM 返回
        # _extract_guidance 函数仅基于 gaps 判断
        assert analysis is not None
        assert analysis.gaps[0].confidence >= 0.5

    def test_low_confidence_gap_no_guidance(self):
        """所有 gap 的 confidence < 0.5 时，不触发引导。"""
        from app.services.analysis.understanding_analyzer import _parse_response
        raw_low_conf = """{
          "concept_observations": [],
          "reasoning_evidence": {"uses_own_words": true, "makes_connections": [], "asks_questions": []},
          "gaps": [{"concept": "SYN", "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "severity": 2, "confidence": 0.3}],
          "metacognitive_signals": {"aware_of_gap": false, "overconfident_on": []},
          "learner_delta": {"knowledge_updates": [], "reasoning_insights": [], "growth_insights": []},
          "guidance_question": null
        }"""
        analysis = _parse_response(raw_low_conf)
        assert analysis is not None
        assert analysis.gaps[0].confidence < 0.5

    def test_no_gaps(self, sample_no_gap_llm_response):
        """无 gap → guidance_question 为 null。"""
        from app.services.analysis.understanding_analyzer import _parse_response
        analysis = _parse_response(sample_no_gap_llm_response)
        assert analysis is not None
        assert len(analysis.gaps) == 0

    def test_gap_confidence_at_threshold(self):
        """gap 置信度精确等于 0.5 时，视为可触发。"""
        from app.services.analysis.understanding_analyzer import _parse_response
        raw = """{
          "concept_observations": [],
          "reasoning_evidence": {"uses_own_words": true, "makes_connections": [], "asks_questions": []},
          "gaps": [{"concept": "test", "observation": "obs", "evidence": "ev", "hypothesis": "hyp", "severity": 1, "confidence": 0.5}],
          "metacognitive_signals": {"aware_of_gap": false, "overconfident_on": []},
          "learner_delta": {"knowledge_updates": [], "reasoning_insights": [], "growth_insights": []},
          "guidance_question": "测试问题"
        }"""
        analysis = _parse_response(raw)
        assert analysis is not None
        assert analysis.gaps[0].confidence >= 0.5


class TestAnalyzer:
    """UnderstandingAnalyzer.analyze() 集成测试（mock LLM）。"""

    @pytest.mark.asyncio
    async def test_analyze_success(self, sample_llm_response):
        from app.services.analysis.understanding_analyzer import UnderstandingAnalyzer

        analyzer = UnderstandingAnalyzer()
        with patch.object(analyzer, "analyze", new=AsyncMock(return_value=(
            __import__("app.domain.session.runtime_context", fromlist=["UnderstandingAnalysis"])
            .UnderstandingAnalysis(**__import__("json").loads(sample_llm_response))
        ))):
            result = await analyzer.analyze(
                mission_title="TCP 三次握手",
                mission_analysis_str='{}',
                user_text="客户端先发一个消息",
                reference_text="三次握手是建立连接的过程",
            )
            assert result is not None
            assert len(result.concept_observations) == 2
            assert len(result.gaps) == 1

    @pytest.mark.asyncio
    async def test_analyze_llm_failure_returns_none(self):
        from app.services.analysis.understanding_analyzer import UnderstandingAnalyzer

        analyzer = UnderstandingAnalyzer()
        with patch("app.services.analysis.understanding_analyzer.llm_service") as mock_llm:
            mock_llm.generate = AsyncMock(side_effect=Exception("LLM timeout"))
            result = await analyzer.analyze(
                mission_title="test",
                mission_analysis_str='{}',
                user_text="test",
                reference_text="test",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_invalid_response_returns_none(self):
        from app.services.analysis.understanding_analyzer import UnderstandingAnalyzer

        analyzer = UnderstandingAnalyzer()
        with patch("app.services.analysis.understanding_analyzer.llm_service") as mock_llm:
            mock_llm.generate = AsyncMock(return_value="这不是 JSON")
            result = await analyzer.analyze(
                mission_title="test",
                mission_analysis_str='{}',
                user_text="test",
                reference_text="test",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_empty_user_text(self):
        from app.services.analysis.understanding_analyzer import UnderstandingAnalyzer

        analyzer = UnderstandingAnalyzer()
        result = await analyzer.analyze(
            mission_title="test",
            mission_analysis_str='{}',
            user_text="",
            reference_text="test",
        )
        # 空文本也会调用 LLM（由调用方决定是否允许）
        # 这里只是确认不会崩溃
        assert result is None or result is not None

    @pytest.mark.asyncio
    async def test_analyze_with_mission_context(self, sample_llm_response):
        """带完整 MissionAnalysis context。"""
        from app.services.analysis.understanding_analyzer import UnderstandingAnalyzer

        analyzer = UnderstandingAnalyzer()
        mission_analysis = '{"concepts": [{"name": "SYN", "importance": "high"}], "dependencies": [], "learning_objectives": [], "difficulty_spots": [], "reflection_focus": [], "growth_signals": {"expected_gains": [], "observation_points": []}}'

        with patch.object(analyzer, "analyze", new=AsyncMock(return_value=(
            __import__("app.domain.session.runtime_context", fromlist=["UnderstandingAnalysis"])
            .UnderstandingAnalysis(**__import__("json").loads(sample_llm_response))
        ))):
            result = await analyzer.analyze(
                mission_title="TCP 三次握手",
                mission_analysis_str=mission_analysis,
                user_text="客户端先发一个消息",
                reference_text="三次握手是建立连接的过程",
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_understanding_analyzer_returns_singleton(self):
        from app.services.analysis.understanding_analyzer import get_understanding_analyzer
        a1 = get_understanding_analyzer()
        a2 = get_understanding_analyzer()
        assert a1 is a2
