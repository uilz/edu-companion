"""Phase 9 测试：ClassifierService 文本降级分类"""

import pytest


class TestClassifierService:
    """ClassifierService 的文本降级分类测试"""

    def test_keyword_score_math(self):
        """高等数学关键词应该匹配到 '高等数学' 分区"""
        from app.services.classifier_service import classifier_service

        result = classifier_service._keyword_score("导数的定义是什么")
        assert len(result) >= 1
        assert result[0]["partition"] == "高等数学"
        assert result[0]["score"] > 0

    def test_keyword_score_multi_subject(self):
        """多学科关键词应返回多个候选"""
        from app.services.classifier_service import classifier_service

        result = classifier_service._keyword_score("矩阵的特征值和概率分布")
        partitions = {r["partition"] for r in result}
        assert "线性代数" in partitions
        assert "概率论" in partitions

    def test_keyword_score_empty(self):
        """无关键词应返回空列表"""
        from app.services.classifier_service import classifier_service

        result = classifier_service._keyword_score("你好，今天天气不错")
        assert result == []

    def test_keyword_score_programming(self):
        """编程关键词应匹配到 '程序设计'"""
        from app.services.classifier_service import classifier_service

        result = classifier_service._keyword_score("Python 链表反转算法")
        assert len(result) >= 1
        assert result[0]["partition"] == "程序设计"

    def test_decide_mode_no_candidates(self):
        """无候选时返回 mode 3"""
        from app.services.classifier_service import classifier_service

        result = classifier_service._decide_mode([], None)
        assert result["mode"] == 3
        assert result["should_switch"] == False

    def test_decide_mode_single_new_topic(self):
        """单一候选且与当前 topic 不同 → mode 2"""
        from app.services.classifier_service import classifier_service

        candidates = [
            {"id": "t1", "label": "导数", "path_id": "高等数学.微积分.导数", "score": 0.85},
        ]
        result = classifier_service._decide_mode(candidates, "t0")
        assert result["mode"] == 2
        assert result["should_switch"] == True

    def test_decide_mode_same_topic(self):
        """单一候选与当前 topic 相同 → mode 3"""
        from app.services.classifier_service import classifier_service

        candidates = [
            {"id": "t1", "label": "导数", "path_id": "高等数学.微积分.导数", "score": 0.85},
        ]
        result = classifier_service._decide_mode(candidates, "t1")
        assert result["mode"] == 3
        assert result["should_switch"] == False

    def test_decide_mode_multi_close(self):
        """多个候选得分接近 → mode 1（跨主题讨论）"""
        from app.services.classifier_service import classifier_service

        candidates = [
            {"id": "t1", "label": "导数", "path_id": "高数.微积分.导数", "score": 0.85},
            {"id": "t2", "label": "极限", "path_id": "高数.微积分.极限", "score": 0.72},
        ]
        # 0.72 * 1.5 > 0.85 => 接近
        result = classifier_service._decide_mode(candidates, None)
        assert result["mode"] == 1
        assert result["should_switch"] == True

    def test_decide_mode_multi_dominant(self):
        """第一候选远超第二 → 切换模式"""
        from app.services.classifier_service import classifier_service

        candidates = [
            {"id": "t1", "label": "导数", "path_id": "高数.微积分.导数", "score": 0.90},
            {"id": "t2", "label": "线性代数", "path_id": "线性代数.矩阵", "score": 0.20},
        ]
        # 0.20 * 1.5 < 0.90 => 单一领先
        result = classifier_service._decide_mode(candidates, "t0")
        assert result["mode"] == 2
        assert result["should_switch"] == True

    def test_classify_by_text_empty_text(self):
        """空文本应返回 mode 3"""
        from app.services.classifier_service import classifier_service

        result = classifier_service.classify_by_text("test_user", "", None)
        assert result["mode"] == 3

    def test_classify_fallback_without_embedding(self):
        """classify() 在无 embedding 时调用 classify_by_text"""
        from app.services.classifier_service import classifier_service

        result = classifier_service.classify("test_user", [], None)
        assert "mode" in result
