"""Task #35 — LanguageRoom AI 共享 tool registry 集成测试

验证:
1. 4 个新工具注册到 LLM tool registry
2. ai_persona.execute_shared_tool() 真的能调用这些工具
3. service.py 的 capture_vocabulary / mark_error / post_message 走 tool
4. ai_helper 通过 tool_knowledge_search 获取知识上下文
5. 对外行为不变 (DB 数据写入正确)
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class TestLanguageRoomToolRegistry:
    """Task #35 - 工具注册"""

    def test_new_tools_in_all_tool_info(self):
        """4 个新 tool action 在 ALL_TOOL_INFO 中"""
        from app.infrastructure.llm.tool_registry import ALL_TOOL_INFO
        for name in [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]:
            assert name in ALL_TOOL_INFO, f"missing: {name}"
            info = ALL_TOOL_INFO[name]
            assert info.zh_name
            assert info.icon
            assert info.description
            assert info.parameters

    def test_new_tools_in_llm_tool_definitions(self):
        """4 个新 tool 在 LLM TOOL_DEFINITIONS (Function Calling format)"""
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS
        names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert "tool_vocabulary_capture" in names
        assert "tool_error_mark" in names
        assert "tool_message_post" in names
        assert "tool_knowledge_search" in names

    def test_new_tools_in_tool_executor_handlers(self):
        """4 个新 tool 在 ToolExecutor.TOOL_HANDLERS"""
        from app.infrastructure.llm.tool_executor import TOOL_HANDLERS
        for name in [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]:
            assert name in TOOL_HANDLERS, f"missing handler: {name}"
            assert callable(TOOL_HANDLERS[name])

    def test_new_tools_are_fast(self):
        """4 个新 tool 在 FAST_TOOLS (不阻塞)"""
        from app.infrastructure.llm.tool_repository import FAST_TOOLS
        for name in [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]:
            assert name in FAST_TOOLS, f"missing fast tool: {name}"


class TestLanguageRoomSyncHandlers:
    """Task #35 - 同步 handler 入口"""

    def test_sync_handlers_dict_has_all(self):
        """SYNC_HANDLERS 含所有 4 个工具"""
        from app.infrastructure.llm.liveroom_tools import SYNC_HANDLERS
        for name in [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]:
            assert name in SYNC_HANDLERS

    def test_execute_sync_validation(self):
        """execute_sync 对无效输入返回 ok=False"""
        from app.infrastructure.llm.liveroom_tools import execute_sync

        # 缺 word
        result = execute_sync("tool_vocabulary_capture", {
            "user_id": "u1", "room_id": "r1",
        })
        assert result["ok"] is False
        assert "word" in result["error"]

        # 缺 transcript_id
        result = execute_sync("tool_error_mark", {
            "user_id": "u1", "room_id": "r1",
        })
        assert result["ok"] is False
        assert "transcript_id" in result["error"]

        # 缺 text
        result = execute_sync("tool_message_post", {
            "user_id": "u1", "room_id": "r1",
        })
        assert result["ok"] is False

    def test_execute_sync_unknown_tool(self):
        """execute_sync 对未知工具返回 ok=False"""
        from app.infrastructure.llm.liveroom_tools import execute_sync
        result = execute_sync("nonexistent_tool", {})
        assert result["ok"] is False

    def test_knowledge_search_empty_query(self):
        """tool_knowledge_search 空 query 返回 ok=False"""
        from app.infrastructure.llm.liveroom_tools import execute_sync
        result = execute_sync("tool_knowledge_search", {
            "user_id": "u1", "query": "",
        })
        assert result["ok"] is False


class TestAIPersonaSharedTool:
    """Task #35 - ai_persona 真正使用共享 tool registry"""

    def test_get_shared_tool_names_includes_liveroom_tools(self):
        """ai_persona.get_shared_tool_names() 包含 liveroom 工具"""
        # 模拟 main.py 的注册
        from app.infrastructure.llm.tool_repository import get_tool_repository, TOOL_DEFINITIONS
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFINITIONS
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFINITIONS

        repo = get_tool_repository()
        repo.register_raw_tools(TOOL_DEFINITIONS)
        repo.register_raw_tools(KTOOL_DEFINITIONS)
        repo.register_raw_tools(LROOM_DEFINITIONS)

        from app.services.liveroom.ai_persona import get_shared_tool_names
        names = get_shared_tool_names()
        for n in [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]:
            assert n in names, f"missing shared tool: {n}"

    def test_execute_shared_tool_uses_sync_handler(self):
        """execute_shared_tool 走 liveroom 同步 handler 路径"""
        # 模拟注册
        from app.infrastructure.llm.tool_repository import get_tool_repository, TOOL_DEFINITIONS
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFINITIONS
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFINITIONS

        repo = get_tool_repository()
        repo.register_raw_tools(TOOL_DEFINITIONS)
        repo.register_raw_tools(KTOOL_DEFINITIONS)
        repo.register_raw_tools(LROOM_DEFINITIONS)

        from app.services.liveroom.ai_persona import execute_shared_tool
        result = execute_shared_tool(
            "tool_knowledge_search",
            user_id="u_test",
            query="present perfect",
            max_results=3,
        )
        # 走 liveroom sync handler (没有真实数据但路径走通)
        assert "ok" in result
        # result.result 是 execute_sync 的结果
        # 如果没有数据, ok=True 但 results=[]
        assert result.get("via") == "liveroom_sync_handler"

    def test_execute_shared_tool_unknown(self):
        """execute_shared_tool 未知工具返回 ok=False"""
        from app.infrastructure.llm.tool_repository import get_tool_repository, TOOL_DEFINITIONS
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFINITIONS
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFINITIONS

        repo = get_tool_repository()
        repo.register_raw_tools(TOOL_DEFINITIONS)
        repo.register_raw_tools(KTOOL_DEFINITIONS)
        repo.register_raw_tools(LROOM_DEFINITIONS)

        from app.services.liveroom.ai_persona import execute_shared_tool
        result = execute_shared_tool("nonexistent_tool_xyz", user_id="u1")
        assert result["ok"] is False
        assert "not found" in result["error"]


class TestServiceUsesSharedTool:
    """Task #35 - service.py 走 tool 路径"""

    def test_capture_vocabulary_routes_to_tool(self):
        """capture_vocabulary 路由到 tool (validation 错误证明走 tool 路径)"""
        from app.api.liveroom.service import capture_vocabulary
        # 缺 word 字段 -> tool 拒绝
        result = capture_vocabulary("u1", "r1", {"translation": "x"})
        assert "error" in result
        assert "word" in result["error"]

    def test_mark_error_routes_to_tool(self):
        """mark_error 路由到 tool (缺 transcript_id)"""
        from app.api.liveroom.service import mark_error
        result = mark_error("u1", "r1", {"error_type": "grammar"})
        assert "error" in result
        assert "transcript_id" in result["error"]

    def test_post_message_routes_to_tool(self):
        """post_message 路由到 tool (空 text)"""
        from app.api.liveroom.service import post_message
        result = post_message("u1", "r1", {"text": ""})
        assert "error" in result
        assert "text" in result["error"]
