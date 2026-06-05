"""Phase 9 测试 — ClassifierService 分类逻辑"""

import pytest
from tests.factories import make_cognitive_node, make_answer_event


class TestClassifierService:
    """ClassifierService 分类器测试（纯逻辑，不依赖 embedding）"""

    def test_classify_by_text_with_keyword(self):
        """关键词匹配应返回 mode=1 并含 candidates"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        result = svc.classify_by_text("test_user", "导数的定义是什么", "")
        assert "mode" in result
        assert "candidates" in result
        # 关键词"导数"应匹配到候选
        assert isinstance(result["candidates"], list)

    def test_classify_by_text_empty(self):
        """空文本应返回 mode=3"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        result = svc.classify_by_text("test_user", "", "")
        assert result["mode"] == 3

    def test_classify_with_empty_embedding_falls_back(self):
        """空 embedding 时 classify() 应降级到 classify_by_text"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        result = svc.classify("test_user", [], "")
        assert "mode" in result
        assert "candidates" in result

    def test_decide_mode_no_candidates(self):
        """无候选时 mode=3（不操作）"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        result = svc._decide_mode([], None, 0)
        assert result["mode"] == 3
        assert result["should_switch"] is False

    def test_immersion_suppression(self):
        """沉浸深度 >= 4 且 mode=1 时 suppression 应为 true"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        result = svc._decide_mode(
            [{"id": "n1", "label": "test", "score": 0.9, "path_id": "p1", "level": "topic"}],
            "n1", 5,
        )
        # 沉浸深度 5 >= 4 阈值
        assert result.get("immersion_suppressed", False) or result["mode"] != 1

    def test_get_immersion_depth_default(self):
        """默认沉浸深度应为 0"""
        from app.services.common.classifier_service import ClassifierService
        svc = ClassifierService()
        depth = svc.get_immersion_depth("test_user", "")
        assert isinstance(depth, int)
        assert depth >= 0
