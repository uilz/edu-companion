"""Agent Tool Registry — 工具注册与自动发现 行为测试"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# 确保 backend/ 在 sys.path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ══════════════════════════════════════════════════════════════
#  Tracer Bullet: ToolRegistry 能自动发现 tools/ 目录下的工具
# ══════════════════════════════════════════════════════════════

class TestToolRegistryDiscovery:
    """工具注册表自动发现"""

    def test_discover_finds_tools_in_directory(self):
        """discover 应从 tools/ 目录发现并注册工具模块"""
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        # 创建临时 tools 目录，放入一个示例工具模块
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = Path(tmpdir)
            sample_tool = tools_dir / "sample_tools.py"
            sample_tool.write_text("""
from app.domain.secretary.tools.base import ToolDefinition, ToolResult

async def sample_handler(params: dict) -> ToolResult:
    return ToolResult(data={"ok": True})

TOOLS = [
    ToolDefinition(
        name="sample_tool",
        description="一个示例工具",
        parameters={"x": {"type": "integer", "description": "输入"}},
        handler=sample_handler,
    )
]
""")

            registry = ToolRegistry()
            count = registry.discover(str(tools_dir))

            assert count == 1
            assert "sample_tool" in registry.list_tools()


# ══════════════════════════════════════════════════════════════
#  ToolRegistry 核心行为
# ══════════════════════════════════════════════════════════════

class TestToolRegistryBehaviors:
    """工具注册、执行、schema 导出"""

    def test_register_and_get_tool(self):
        """register 后可通过 get_tool 获取工具定义"""
        from app.domain.secretary.tools.base import ToolDefinition, ToolResult
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        async def noop(params): return ToolResult()

        tool = ToolDefinition(
            name="test_echo",
            description="echo 工具",
            parameters={"msg": {"type": "string"}},
            handler=noop,
        )
        registry = ToolRegistry()
        registry.register(tool)

        found = registry.get_tool("test_echo")
        assert found is not None
        assert found.name == "test_echo"
        assert found.description == "echo 工具"

    @pytest.mark.asyncio
    async def test_execute_tool_returns_result(self):
        """execute 应异步执行工具并返回结果"""
        from app.domain.secretary.tools.base import ToolDefinition, ToolResult
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        async def greet(params):
            name = params.get("name", "World")
            return ToolResult(data={"greeting": f"Hello {name}"})

        tool = ToolDefinition(
            name="greet",
            description="打招呼",
            parameters={"name": {"type": "string"}},
            handler=greet,
        )
        registry = ToolRegistry()
        registry.register(tool)

        result = await registry.execute("greet", {"name": "Alice"})
        assert result.data["greeting"] == "Hello Alice"

    def test_get_schema_for_llm(self):
        """get_schema 应返回 LLM 用的 JSON Schema 列表"""
        from app.domain.secretary.tools.base import ToolDefinition, ToolResult
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        async def noop(params): return ToolResult()

        tool = ToolDefinition(
            name="start_practice",
            description="开始练习指定科目",
            parameters={
                "subject": {"type": "string", "description": "科目名称"},
                "count": {"type": "integer", "description": "题目数量"},
            },
            handler=noop,
            require_confirmation=True,
        )
        registry = ToolRegistry()
        registry.register(tool)

        schemas = registry.get_schema()
        assert len(schemas) == 1
        s = schemas[0]
        assert s["name"] == "start_practice"
        assert s["description"] == "开始练习指定科目"
        assert "subject" in s["parameters"]["properties"]
        assert s["parameters"]["properties"]["count"]["type"] == "integer"

    def test_list_tools_returns_all_names(self):
        """list_tools 返回所有已注册工具名称"""
        from app.domain.secretary.tools.base import ToolDefinition, ToolResult
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        async def noop(params): return ToolResult()

        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="a", description="a", parameters={}, handler=noop,
        ))
        registry.register(ToolDefinition(
            name="b", description="b", parameters={}, handler=noop,
        ))

        names = registry.list_tools()
        assert sorted(names) == ["a", "b"]

    def test_discover_skips_non_tool_files(self):
        """discover 应忽略不是 *_tools.py 的文件"""
        import tempfile
        from pathlib import Path
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = Path(tmpdir)
            (tools_dir / "not_a_tool.py").write_text("x = 1")
            (tools_dir / "README.md").write_text("# docs")

            registry = ToolRegistry()
            count = registry.discover(str(tools_dir))
            assert count == 0

    def test_discover_handles_missing_tools_attr(self):
        """discover 应忽略没有 TOOLS 属性的模块"""
        import tempfile
        from pathlib import Path
        from app.domain.secretary.tools.tool_registry import ToolRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = Path(tmpdir)
            (tools_dir / "empty_tools.py").write_text("x = 1")

            registry = ToolRegistry()
            count = registry.discover(str(tools_dir))
            assert count == 0