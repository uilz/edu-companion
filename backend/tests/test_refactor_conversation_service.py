"""验证 Conversation 薄门面修复 — send_message 不再返回空 dict"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock, AsyncMock
import pytest


class TestConversationServiceSendMessage:
    """验证 send_message 委托到 domain/conversation/llm.py"""

    @pytest.mark.asyncio
    async def test_send_message_delegates_to_llm(self):
        """send_message 调用 llm.send_and_reply"""
        from app.domain.conversation.service import ConversationServiceImpl

        llm = MagicMock()
        bus = MagicMock()
        circuit = MagicMock()
        svc = ConversationServiceImpl(llm, bus, circuit)

        # send_and_reply 是方法内部 lazy import — 在 llm 模块级别 mock
        with patch("app.domain.conversation.llm.send_and_reply",
                   new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"ok": True, "reply": "hello"}

            # 使用 partition_id 直接调用
            result = await svc.send_message(
                "user_1", "你好", partition_id="p1", branch_id=None,
            )
            assert result["ok"] is True
            mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_without_partition(self):
        """没有 partition_id 和 branch_id 时返回错误"""
        from app.domain.conversation.service import ConversationServiceImpl

        llm = MagicMock()
        bus = MagicMock()
        circuit = MagicMock()
        svc = ConversationServiceImpl(llm, bus, circuit)

        result = await svc.send_message("user_1", "你好")
        assert result.get("error") is not None or result.get("ok") is False

    @pytest.mark.asyncio
    async def test_events_still_work(self):
        """事件监听器仍正常工作"""
        from app.domain.conversation.service import ConversationServiceImpl
        from shared.events import SessionCompleted

        llm = MagicMock()
        bus = MagicMock()
        circuit = MagicMock()
        svc = ConversationServiceImpl(llm, bus, circuit)

        event = SessionCompleted(
            user_id="u1", session_id="s1", accuracy=0.8,
            total_questions=10, duration_minutes=5,
        )
        # 不应抛异常
        await svc.on_session_completed(event)
        await svc.on_knowledge_updated(event)
        await svc.inject_practice_context("u1", "b1", {"key": "val"})
