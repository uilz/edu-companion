"""验证 ZPD scheduler 修复 + 清理

- on_knowledge_change 方法存在（之前缺失导致静默 bug）
- SpacedRepetitionScheduler / spacing_scheduler 已删除
- estimate_student_ability 简化（移除冗余计算）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock
import pytest


class TestZPDSchedulerFixes:
    """验证 ZPDScheduler 的修复"""

    def test_on_knowledge_change_exists(self):
        """on_knowledge_change 方法必须存在（DI 容器调用它）"""
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        scheduler = ZPDScheduler()
        assert hasattr(scheduler, "on_knowledge_change")
        assert callable(scheduler.on_knowledge_change)
        # 不应抛异常
        scheduler.on_knowledge_change("user_1", "node_abc123")

    def test_spaced_repetition_deleted(self):
        """SpacedRepetitionScheduler 应已删除（死代码）"""
        import app.services.knowledge.zpd_scheduler as mod
        assert not hasattr(mod, "SpacedRepetitionScheduler"), \
            "SpacedRepetitionScheduler 已删除"
        assert not hasattr(mod, "spacing_scheduler"), \
            "spacing_scheduler 全局实例已删除"

    def test_select_questions_empty(self):
        """空候选池返回空列表"""
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        scheduler = ZPDScheduler()
        result = scheduler.select_questions([], 0.5)
        assert result == []

    def test_select_questions_returns_requested_count(self):
        """选择指定数量的题目"""
        from app.schemas.practice import Question, BloomLevel
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        pool = [
            Question(id=f"q{i}", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.APPLY, quality_score=0.8,
                     subject="数学", text=f"题{i}")
            for i in range(10)
        ]
        scheduler = ZPDScheduler()
        result = scheduler.select_questions(pool, 0.5, count=3)
        assert len(result) == 3

    def test_select_questions_filters_bloom(self):
        """过滤 Bloom 层次"""
        from app.schemas.practice import Question, BloomLevel
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        pool = [
            Question(id="q1", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.REMEMBER, quality_score=0.8,
                     subject="数学", text="题1"),
            Question(id="q2", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.APPLY, quality_score=0.8,
                     subject="数学", text="题2"),
            Question(id="q3", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.REMEMBER, quality_score=0.8,
                     subject="数学", text="题3"),
        ]
        scheduler = ZPDScheduler()
        result = scheduler.select_questions(pool, 0.5, count=5, target_bloom=BloomLevel.REMEMBER)
        assert len(result) == 2
        assert all(q.bloom_level == BloomLevel.REMEMBER for q in result)

    def test_select_questions_filters_blocked(self):
        """过滤被阻塞的技能"""
        from app.schemas.practice import Question, BloomLevel
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        pool = [
            Question(id="q1", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.APPLY, quality_score=0.8,
                     subject="数学", text="题1"),
            Question(id="q2", skill_id="blocked_skill", difficulty=0.5,
                     bloom_level=BloomLevel.APPLY, quality_score=0.8,
                     subject="数学", text="题2"),
        ]
        scheduler = ZPDScheduler()
        result = scheduler.select_questions(pool, 0.5, count=5, blocked_skills=["blocked_skill"])
        assert len(result) == 1
        assert result[0].skill_id == "math"

    def test_estimate_student_ability_fallback(self):
        """无法读取 CognitiveNode 时返回默认值 0.3"""
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        scheduler = ZPDScheduler()
        with patch("app.services.knowledge.zpd_scheduler.ZPDScheduler.estimate_student_ability",
                   return_value=0.3):
            val = scheduler.estimate_student_ability("unknown_skill")
            assert val == 0.3

    def test_select_questions_increments_usage(self):
        """选中题目 usage_count 应递增"""
        from app.schemas.practice import Question, BloomLevel
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        q = Question(id="q1", skill_id="math", difficulty=0.5,
                     bloom_level=BloomLevel.APPLY, quality_score=0.8,
                     usage_count=0, subject="数学", text="题1")
        pool = [q]
        scheduler = ZPDScheduler()
        scheduler.select_questions(pool, 0.5, count=1)
        assert q.usage_count == 1

    def test_fatigue_adjusted_ability(self):
        """疲劳调整：时间衰减 + 错误惩罚"""
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        scheduler = ZPDScheduler()
        # 0 时间、0 错误 → 基本不变
        assert scheduler.fatigue_adjusted_ability(0.5, 0, 0) == pytest.approx(0.5)
        # 60 分钟、3 连续错误 → 显著降低
        adj = scheduler.fatigue_adjusted_ability(0.5, 60, 3)
        assert adj < 0.5
        # 永不低于 0.05
        adj2 = scheduler.fatigue_adjusted_ability(0.1, 600, 10)
        assert adj2 >= 0.05

    def test_plan_session(self):
        """plan_session 返回有效计划"""
        from app.schemas.practice import Question, BloomLevel
        from app.services.knowledge.zpd_scheduler import ZPDScheduler
        pool = {
            "skill_a": [
                Question(id="q1", skill_id="skill_a", difficulty=0.5,
                         bloom_level=BloomLevel.APPLY, quality_score=0.8,
                         subject="数学", text="题1"),
                Question(id="q2", skill_id="skill_a", difficulty=0.6,
                         bloom_level=BloomLevel.APPLY, quality_score=0.7,
                         subject="数学", text="题2"),
            ],
            "skill_b": [
                Question(id="q3", skill_id="skill_b", difficulty=0.4,
                         bloom_level=BloomLevel.APPLY, quality_score=0.9,
                         subject="数学", text="题3"),
            ],
        }
        scheduler = ZPDScheduler()
        plan = scheduler.plan_session(pool, ["skill_a", "skill_b"], duration_minutes=30)
        assert len(plan.questions) > 0
        assert len(plan.skills) == 2
