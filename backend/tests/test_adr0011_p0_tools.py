"""ADR 0011 P0 工具实现测试 — 结构化校验 + 错因分析 + 时间异常检测"""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ══════════════════════════════════════════════════════════════
# Q6: 结构化输出校验
# ══════════════════════════════════════════════════════════════

class TestQuestionValidator:
    """Pydantic 校验链"""

    def test_valid_question_passes(self):
        """合法的题目应通过校验"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption

        q = GeneratedQuestion(
            text="计算 $\\int_0^1 x^2 dx$",
            options=[
                GeneratedOption(letter="A", text="$\\frac{1}{3}$", is_correct=True),
                GeneratedOption(letter="B", text="$\\frac{1}{2}$", is_correct=False, distractor_type="integration_error"),
                GeneratedOption(letter="C", text="1", is_correct=False, distractor_type="concept_confusion"),
                GeneratedOption(letter="D", text="$\\frac{1}{4}$", is_correct=False, distractor_type="calculation_error"),
            ],
            correct_answer="A",
            explanation="用牛顿-莱布尼茨公式计算",
            hints=["用牛顿-莱布尼茨公式", "先求不定积分", "代入上下限"],
            difficulty=0.5,
            bloom_level="apply",
        )
        assert q.text == "计算 $\\int_0^1 x^2 dx$"
        assert q.bloom_level == "apply"
        assert len(q.options) == 4

    def test_invalid_bloom_rejected(self):
        """无效的 bloom_level 应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="test question",
                options=[
                    GeneratedOption(letter="A", text="correct", is_correct=True),
                    GeneratedOption(letter="B", text="wrong", is_correct=False),
                ],
                correct_answer="A",
                bloom_level="invalid_level",
            )

    def test_no_correct_option_rejected(self):
        """没有正确答案的选项应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="test question",
                options=[
                    GeneratedOption(letter="A", text="wrong1", is_correct=False),
                    GeneratedOption(letter="B", text="wrong2", is_correct=False),
                ],
                correct_answer="A",
                bloom_level="apply",
            )

    def test_correct_answer_not_in_options_rejected(self):
        """correct_answer 不在选项字母中应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="test question",
                options=[
                    GeneratedOption(letter="A", text="wrong1", is_correct=False),
                    GeneratedOption(letter="B", text="correct", is_correct=True),
                ],
                correct_answer="C",  # C 不存在
                bloom_level="apply",
            )

    def test_too_few_options_rejected(self):
        """少于2个选项应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="test question",
                options=[GeneratedOption(letter="A", text="only", is_correct=True)],
                correct_answer="A",
                bloom_level="apply",
            )

    def test_text_too_short_rejected(self):
        """题目文本太短应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="ab",  # 少于5字符
                options=[
                    GeneratedOption(letter="A", text="correct", is_correct=True),
                    GeneratedOption(letter="B", text="wrong", is_correct=False),
                ],
                correct_answer="A",
                bloom_level="apply",
            )

    def test_difficulty_out_of_range_rejected(self):
        """难度超出范围应被拒绝"""
        from app.services.practice.question_validator import GeneratedQuestion, GeneratedOption
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            GeneratedQuestion(
                text="test question here",
                options=[
                    GeneratedOption(letter="A", text="correct", is_correct=True),
                    GeneratedOption(letter="B", text="wrong", is_correct=False),
                ],
                correct_answer="A",
                difficulty=1.5,  # > 1.0
                bloom_level="apply",
            )

    def test_validate_generated_questions_filters_invalid(self):
        """validate_generated_questions 应过滤无效题目"""
        from app.services.practice.question_validator import validate_generated_questions

        data = [
            {"text": "valid question", "options": [{"letter": "A", "text": "ok", "is_correct": True}, {"letter": "B", "text": "no", "is_correct": False}], "correct_answer": "A", "bloom_level": "apply"},
            {"text": "ab", "options": [{"letter": "A", "text": "ok", "is_correct": True}], "correct_answer": "A", "bloom_level": "apply"},  # 无效：text太短
            {"text": "another valid", "options": [{"letter": "A", "text": "ok", "is_correct": True}, {"letter": "B", "text": "no", "is_correct": False}], "correct_answer": "A", "bloom_level": "understand"},
        ]
        results = validate_generated_questions(data)
        assert len(results) == 2

    def test_parse_and_validate_handles_valid_json(self):
        """parse_and_validate_llm_response 应正确处理有效 JSON"""
        from app.services.practice.question_validator import parse_and_validate_llm_response

        response = '[{"text": "test question", "options": [{"letter": "A", "text": "ok", "is_correct": true}, {"letter": "B", "text": "no", "is_correct": false}], "correct_answer": "A", "bloom_level": "apply"}]'
        results = parse_and_validate_llm_response(response)
        assert len(results) == 1
        assert results[0]["text"] == "test question"

    def test_parse_and_validate_handles_markdown_code_block(self):
        """parse_and_validate_llm_response 应能处理 markdown 代码块中的 JSON"""
        from app.services.practice.question_validator import parse_and_validate_llm_response

        response = """以下是生成的题目：
```json
[{"text": "test question", "options": [{"letter": "A", "text": "ok", "is_correct": true}, {"letter": "B", "text": "no", "is_correct": false}], "correct_answer": "A", "bloom_level": "apply"}]
```
"""
        results = parse_and_validate_llm_response(response)
        assert len(results) == 1
        assert results[0]["text"] == "test question"

    def test_parse_and_validate_returns_empty_for_garbage(self):
        """parse_and_validate_llm_response 应对无效输入返回空列表"""
        from app.services.practice.question_validator import parse_and_validate_llm_response

        results = parse_and_validate_llm_response("not json at all")
        assert results == []


# ══════════════════════════════════════════════════════════════
# A2: LLM 错因分析
# ══════════════════════════════════════════════════════════════

class TestErrorAnalysis:
    """错因分析"""

    def test_classify_error_basic_with_distractor(self):
        """基础分类应识别 distractor_type"""
        from app.services.practice.error_analysis import classify_error_basic

        result = classify_error_basic(
            question={"stem": "test"},
            user_answer=["B"],
            correct_answer=["A"],
            selected_option={"letter": "B", "distractor_type": "sign_error"},
        )
        assert result["error_type"] == "sign_error"
        assert result["misconception"] == "符号错误"

    def test_classify_error_basic_empty_answer(self):
        """空答案应识别为 knowledge_gap"""
        from app.services.practice.error_analysis import classify_error_basic

        result = classify_error_basic(
            question={"stem": "test"},
            user_answer=[],  # 空答案
            correct_answer=["A"],
        )
        assert result["error_type"] == "knowledge_gap"

    def test_classify_error_basic_unknown(self):
        """无特殊标记时返回 unknown"""
        from app.services.practice.error_analysis import classify_error_basic

        result = classify_error_basic(
            question={"stem": "test"},
            user_answer=["B"],
            correct_answer=["A"],
        )
        assert result["error_type"] == "unknown"
        assert result["confidence"] == 0.3


# ══════════════════════════════════════════════════════════════
# A5: 时间异常检测
# ══════════════════════════════════════════════════════════════

class TestTimeAnomaly:
    """时间异常检测"""

    def test_stuck_pattern(self):
        """用时过长但答错 → 卡住"""
        from app.services.practice.time_anomaly import detect_time_anomaly

        result = detect_time_anomaly(
            attempt={"duration_seconds": 100, "is_correct": False},
            user_stats={"avg_duration_seconds": 30},
        )
        assert result is not None
        assert "卡住" in result

    def test_careless_pattern(self):
        """用时过短但答错 → 粗心"""
        from app.services.practice.time_anomaly import detect_time_anomaly

        result = detect_time_anomaly(
            attempt={"duration_seconds": 5, "is_correct": False},
            user_stats={"avg_duration_seconds": 30},
        )
        assert result is not None
        assert "粗心" in result

    def test_concept_pattern(self):
        """用时正常但答错 → 概念问题"""
        from app.services.practice.time_anomaly import detect_time_anomaly

        result = detect_time_anomaly(
            attempt={"duration_seconds": 25, "is_correct": False},
            user_stats={"avg_duration_seconds": 30},
        )
        assert result is not None
        assert "概念问题" in result

    def test_correct_no_anomaly(self):
        """答对且用时正常 → 无异常"""
        from app.services.practice.time_anomaly import detect_time_anomaly

        result = detect_time_anomaly(
            attempt={"duration_seconds": 30, "is_correct": True},
            user_stats={"avg_duration_seconds": 30},
        )
        assert result is None

    def test_no_stats_returns_none(self):
        """无统计数据时返回 None"""
        from app.services.practice.time_anomaly import detect_time_anomaly

        result = detect_time_anomaly(
            attempt={"duration_seconds": 30, "is_correct": False},
            user_stats={"avg_duration_seconds": 0},
        )
        assert result is None

    def test_get_time_anomaly_stats(self):
        """统计函数应正确汇总"""
        from app.services.practice.time_anomaly import get_time_anomaly_stats

        attempts = [
            {"duration_seconds": 100, "is_correct": False},
            {"duration_seconds": 5, "is_correct": False},
            {"duration_seconds": 25, "is_correct": False},
        ]
        stats = get_time_anomaly_stats("test_user", attempts)
        assert stats["total_attempts"] == 3
        assert stats["anomalies"]["stuck"] == 1
        assert stats["anomalies"]["careless"] == 1
        assert stats["anomalies"]["concept"] == 1
        assert stats["primary_pattern"] in ("stuck", "careless", "concept")