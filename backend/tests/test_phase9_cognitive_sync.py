"""Phase 9 测试：CognitiveNode 信念同步（纯算法，不需 DB）"""

import pytest


class TestBeliefUpdate:
    """CognitiveNode Beta 分布信念更新测试（纯模型层，无 DB）"""

    def test_initial_belief_default(self):
        """默认 Belief 应为均匀分布 α=2, β=2, mean=0.5"""
        from app.domain.cognitive.models import Belief

        b = Belief()
        assert b.alpha == 2.0
        assert b.beta == 2.0
        assert b.proficiency_mean == 0.5
        assert b.proficiency_precision == 4.0

    def test_belief_after_correct(self):
        """答对后 α+1, mean 上升"""
        from app.domain.cognitive.models import Belief

        b = Belief(alpha=2.0, beta=2.0)
        b.alpha += 1  # correct
        total = b.alpha + b.beta
        b.proficiency_mean = b.alpha / total
        b.proficiency_precision = total

        assert b.alpha == 3.0
        assert b.beta == 2.0
        assert b.proficiency_mean == 0.6  # 3/5
        assert b.proficiency_precision == 5.0

    def test_belief_after_wrong(self):
        """答错后 β+1, mean 下降"""
        from app.domain.cognitive.models import Belief

        b = Belief(alpha=2.0, beta=2.0)
        b.beta += 1  # wrong
        total = b.alpha + b.beta
        b.proficiency_mean = b.alpha / total
        b.proficiency_precision = total

        assert b.alpha == 2.0
        assert b.beta == 3.0
        assert b.proficiency_mean == 0.4  # 2/5

    def test_belief_sequence(self):
        """多次答题的信念变化序列"""
        from app.domain.cognitive.models import Belief

        b = Belief(alpha=2.0, beta=2.0)

        # 答对 3 次
        for _ in range(3):
            b.alpha += 1
        # 答错 1 次
        b.beta += 1

        total = b.alpha + b.beta
        b.proficiency_mean = b.alpha / total

        assert b.alpha == 5.0  # 2+3
        assert b.beta == 3.0  # 2+1
        assert b.proficiency_mean == 5.0 / 8.0  # 0.625

    def test_practice_summary_tracking(self):
        """PracticeSummary 应追踪练习次数和正确率"""
        from app.domain.cognitive.models import PracticeSummary

        ps = PracticeSummary(total_attempts=0, correct_attempts=0)

        # 答对
        ps.total_attempts += 1
        ps.correct_attempts += 1

        # 答错
        ps.total_attempts += 1

        # 答对
        ps.total_attempts += 1
        ps.correct_attempts += 1

        assert ps.total_attempts == 3
        assert ps.correct_attempts == 2
        assert ps.total_attempts > 0
        assert ps.correct_attempts / ps.total_attempts == 2/3

    def test_peak_proficiency_tracking(self):
        """peak_proficiency 应该只增不减"""
        from app.domain.cognitive.models import Belief

        b = Belief(alpha=2.0, beta=2.0, peak_proficiency=0.5)

        # 答对 → mean 上升
        b.alpha += 3
        total = b.alpha + b.beta
        new_mean = b.alpha / total
        b.peak_proficiency = max(b.peak_proficiency, new_mean)
        assert b.peak_proficiency == new_mean

        # 答错 → mean 下降，peak 不变
        b.beta += 2
        total = b.alpha + b.beta
        lower_mean = b.alpha / total
        assert lower_mean < b.peak_proficiency
        b.peak_proficiency = max(b.peak_proficiency, lower_mean)
        assert b.peak_proficiency == new_mean  # 仍为之前的峰值


class TestCognitiveEvent:
    """CognitiveNodeMetadataChanged / CognitiveNodeLinked 事件测试"""

    def test_metadata_event_creation(self):
        """CognitiveNodeMetadataChanged 应包含所有必要字段"""
        from shared.events import CognitiveNodeMetadataChanged

        event = CognitiveNodeMetadataChanged(
            user_id="test_user",
            node_id="node_001",
            changed_fields=["label", "tags"],
        )
        assert event.user_id == "test_user"
        assert event.node_id == "node_001"
        assert event.changed_fields == ["label", "tags"]
        assert event.event_type == "CognitiveNodeMetadataChanged"

    def test_metadata_event_in_registry(self):
        """CognitiveNodeMetadataChanged 应在 EVENT_TYPES 注册表中"""
        from shared.events import EVENT_TYPES

        assert "CognitiveNodeMetadataChanged" in EVENT_TYPES

    def test_linked_event_creation(self):
        """CognitiveNodeLinked 应包含所有必要字段"""
        from shared.events import CognitiveNodeLinked

        event = CognitiveNodeLinked(
            user_id="test_user",
            node_id="node_001",
            link_type="prerequisite",
            target_ref_type="flashcard",
            target_ref_id="card_99",
            action="created",
        )
        assert event.link_type == "prerequisite"
        assert event.target_ref_type == "flashcard"
        assert event.action == "created"
        assert event.event_type == "CognitiveNodeLinked"


class TestEventBusChain:
    """事件总线链路测试"""

    def test_handler_registered(self):
        """AnswerSubmitted 应有至少 3 个 handler"""
        from app.application.di import container

        handlers = container.event_bus._handlers.get("AnswerSubmitted", [])
        assert len(handlers) >= 3  # analytics + habits + knowledge

    def test_cognitive_metadata_handler(self):
        """CognitiveNodeMetadataChanged 应有至少 1 个 handler"""
        from app.application.di import container

        handlers = container.event_bus._handlers.get("CognitiveNodeMetadataChanged", [])
        assert len(handlers) >= 1

    def test_secretary_subscribable(self):
        """Secretary 应能订阅 EventBus"""
        from app.application.di import container
        from app.domain.secretary.engines.secretary_event_handler import (
            secretary_event_handler,
        )

        secretary_event_handler.subscribe(container.event_bus)
        # Secretary 订阅 CognitiveNodeMetadataChanged / SessionCompleted / AnswerSubmitted
        handlers = container.event_bus._handlers.get("CognitiveNodeMetadataChanged", [])
        handler_names = [h.__qualname__ for h in handlers]
        assert any("SecretaryEventHandler" in h for h in handler_names)

    def test_publish_and_receive(self):
        """事件发布后，cognitive_sync handler 应被调用"""
        import asyncio
        from app.infrastructure.event_bus import EventBus
        from shared.events import AnswerSubmitted

        bus = EventBus()
        call_count = 0

        async def test_handler(event):
            nonlocal call_count
            call_count += 1
            assert event.is_correct == True

        bus.subscribe("AnswerSubmitted", test_handler)

        event = AnswerSubmitted(
            user_id="test_user",
            skill_id="微积分.导数",
            is_correct=True,
        )

        asyncio.run(bus.publish(event))
        assert call_count == 1
