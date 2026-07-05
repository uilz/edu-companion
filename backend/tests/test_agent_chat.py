"""Agent Chat SSE 端点 — 行为测试"""

import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ══════════════════════════════════════════════════════════════
#  Agent Chat 端点
# ══════════════════════════════════════════════════════════════

class TestAgentChatEndpoint:
    """POST /api/secretary/agent/chat 流式端点"""

    @pytest.fixture
    def client(self):
        """创建 FastAPI TestClient"""
        from fastapi import FastAPI
        from app.api.system.secretary import router

        app = FastAPI()
        app.include_router(router)
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _mock_agent_llm(self):
        """mock agent_llm 避免真实 LLM 调用"""
        async def mock_agent_generate_stream(user_message, current_page, tool_schemas, user_id):
            yield {"type": "token", "delta": "你好！"}
            yield {"type": "token", "delta": "我来帮你。"}
            yield {"type": "done", "full_text": "你好！我来帮你。"}

        with patch(
            "app.domain.secretary.agent_llm.agent_generate_stream",
            side_effect=mock_agent_generate_stream,
        ):
            yield

    def test_chat_returns_sse_stream(self, client):
        """发送消息应返回 SSE 流式响应"""
        with client.stream(
            "POST",
            "/api/secretary/agent/chat?user_id=test_user",
            json={"message": "帮我复习微积分", "current_page": "/dashboard"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # 读取 SSE 事件
            events = []
            for line in response.iter_lines():
                if line and not line.startswith(":"):
                    events.append(line)
                if len(events) >= 3:
                    break

            # 至少应有 token 事件
            token_events = [e for e in events if e.startswith("event: token")]
            assert len(token_events) > 0

    def test_chat_creates_secretary_conversation(self, client):
        """chat 应为 secretary 类型创建会话"""
        with patch(
            "app.domain.secretary.tools.tool_registry.ToolRegistry.get_schema",
            return_value=[],
        ):
            with client.stream(
                "POST",
                "/api/secretary/agent/chat?user_id=test_user",
                json={"message": "你好", "current_page": "/learn"},
            ) as response:
                assert response.status_code == 200

    def test_chat_with_conv_id_reuses(self, client):
        """传入已有 conv_id 应复用会话"""
        with client.stream(
            "POST",
            "/api/secretary/agent/chat?user_id=test_user",
            json={
                "message": "继续",
                "current_page": "/learn",
                "conv_id": "conv_secretary_001",
            },
        ) as response:
            assert response.status_code == 200

    def test_chat_empty_message_returns_422(self, client):
        """空消息应返回 422 (Pydantic 验证失败)"""
        with client.stream(
            "POST",
            "/api/secretary/agent/chat?user_id=test_user",
            json={"message": "", "current_page": "/learn"},
        ) as response:
            assert response.status_code == 422


# ══════════════════════════════════════════════════════════════
#  Agent 偏好端点
# ══════════════════════════════════════════════════════════════

class TestAgentPreferences:
    """GET/POST /api/secretary/agent/preferences"""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from app.api.system.secretary import router

        app = FastAPI()
        app.include_router(router)
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _mock_storage(self):
        """mock 存储层，避免访问真实数据库"""
        from unittest.mock import MagicMock, patch

        mock_data = MagicMock()
        mock_data.secretary_prefs = {}

        with patch(
            "app.services.common.storage.storage.load",
            return_value=mock_data,
        ), patch(
            "app.services.common.storage.storage.save",
        ):
            yield

    def test_get_preferences_returns_defaults(self, client):
        """GET 偏好应返回默认值"""
        response = client.get("/api/secretary/agent/preferences?user_id=test_user")
        assert response.status_code == 200
        data = response.json()
        assert data["confirm_mode"] == "smart"
        assert data["auto_jump_threshold"] == 0.85

    def test_post_preferences_updates_values(self, client):
        """POST 偏好应更新并返回新值"""
        response = client.post(
            "/api/secretary/agent/preferences",
            json={
                "confirm_mode": "always",
                "auto_jump_threshold": 0.5,
            },
            params={"user_id": "test_user"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confirm_mode"] == "always"
        assert data["auto_jump_threshold"] == 0.5

    def test_post_preferences_invalid_mode_returns_422(self, client):
        """无效 confirm_mode 应返回 422"""
        response = client.post(
            "/api/secretary/agent/preferences",
            json={"confirm_mode": "invalid"},
            params={"user_id": "test_user"},
        )
        assert response.status_code == 422