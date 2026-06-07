"""Agent Tools 模块 — 行为测试"""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ══════════════════════════════════════════════════════════════
#  navigation_tools — 页面跳转
# ══════════════════════════════════════════════════════════════

class TestNavigationTools:
    """navigate_to_page / navigate_to_dashboard 工具"""

    @pytest.fixture
    def tools_module(self):
        import importlib.util
        tools_path = (
            BACKEND
            / "app"
            / "domain"
            / "secretary"
            / "tools"
            / "navigation_tools.py"
        )
        spec = importlib.util.spec_from_file_location(
            "navigation_tools", str(tools_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_module_exports_tools_list(self, tools_module):
        """模块应导出 TOOLS 列表"""
        assert hasattr(tools_module, "TOOLS")
        assert isinstance(tools_module.TOOLS, list)
        assert len(tools_module.TOOLS) > 0

    def test_navigate_to_page_tool_definition(self, tools_module):
        """navigate_to_page 工具应包含正确的定义"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "navigate_to_page" in tools

        tool = tools["navigate_to_page"]
        assert tool.description != ""
        assert "target" in tool.parameters
        assert tool.parameters["target"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_navigate_to_page_executes(self, tools_module):
        """navigate_to_page 执行应返回正确的路由结果"""
        tools = {t.name: t for t in tools_module.TOOLS}
        tool = tools["navigate_to_page"]

        result = await tool.handler({"target": "/knowledge-tree"})
        assert result.route_target == "/knowledge-tree"
        assert result.data is not None


# ══════════════════════════════════════════════════════════════
#  knowledge_tree_tools — 知识树操作
# ══════════════════════════════════════════════════════════════

class TestKnowledgeTreeTools:
    """search_knowledge_tree / expand_knowledge_node 工具"""

    @pytest.fixture
    def tools_module(self):
        import importlib.util
        tools_path = (
            BACKEND
            / "app"
            / "domain"
            / "secretary"
            / "tools"
            / "knowledge_tree_tools.py"
        )
        spec = importlib.util.spec_from_file_location(
            "knowledge_tree_tools", str(tools_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_module_exports_tools_list(self, tools_module):
        """模块应导出 TOOLS 列表"""
        assert hasattr(tools_module, "TOOLS")
        assert isinstance(tools_module.TOOLS, list)
        assert len(tools_module.TOOLS) > 0

    def test_search_knowledge_tree_tool_definition(self, tools_module):
        """search_knowledge_tree 工具应包含正确的参数定义"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "search_knowledge_tree" in tools

        tool = tools["search_knowledge_tree"]
        assert "query" in tool.parameters
        assert tool.parameters["query"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_search_knowledge_tree_executes(self, tools_module):
        """search_knowledge_tree 执行应返回路由结果"""
        tools = {t.name: t for t in tools_module.TOOLS}
        tool = tools["search_knowledge_tree"]

        result = await tool.handler({"query": "微积分"})
        assert result.data is not None
        assert result.route_target is not None

    def test_expand_knowledge_node_tool_definition(self, tools_module):
        """expand_knowledge_node 工具应包含节点 ID 参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "expand_knowledge_node" in tools

        tool = tools["expand_knowledge_node"]
        assert "node_id" in tool.parameters

    @pytest.mark.asyncio
    async def test_expand_knowledge_node_executes(self, tools_module):
        """expand_knowledge_node 执行应返回路由结果"""
        tools = {t.name: t for t in tools_module.TOOLS}
        tool = tools["expand_knowledge_node"]

        result = await tool.handler({"node_id": "node_001"})
        assert result.data is not None
        assert result.route_target is not None


# ══════════════════════════════════════════════════════════════
#  practice_tools — 练习/复习
# ══════════════════════════════════════════════════════════════

class TestPracticeTools:
    """start_practice / start_quiz 工具"""

    @pytest.fixture
    def tools_module(self):
        import importlib.util
        tools_path = (
            BACKEND
            / "app"
            / "domain"
            / "secretary"
            / "tools"
            / "practice_tools.py"
        )
        spec = importlib.util.spec_from_file_location(
            "practice_tools", str(tools_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_module_exports_tools_list(self, tools_module):
        """模块应导出 TOOLS 列表"""
        assert hasattr(tools_module, "TOOLS")
        assert isinstance(tools_module.TOOLS, list)
        assert len(tools_module.TOOLS) > 0

    def test_start_practice_tool_definition(self, tools_module):
        """start_practice 工具应包含 subject 参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "start_practice" in tools

        tool = tools["start_practice"]
        assert "subject" in tool.parameters
        assert tool.parameters["subject"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_start_practice_executes(self, tools_module):
        """start_practice 执行应返回路由结果"""
        tools = {t.name: t for t in tools_module.TOOLS}
        tool = tools["start_practice"]

        result = await tool.handler({"subject": "微积分"})
        assert result.data is not None
        assert result.route_target is not None

    def test_start_quiz_tool_definition(self, tools_module):
        """start_quiz 工具应包含 topic 参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "start_quiz" in tools

        tool = tools["start_quiz"]
        assert "topic" in tool.parameters

    @pytest.mark.asyncio
    async def test_start_quiz_executes(self, tools_module):
        """start_quiz 执行应返回路由结果"""
        tools = {t.name: t for t in tools_module.TOOLS}
        tool = tools["start_quiz"]

        result = await tool.handler({"topic": "极限"})
        assert result.data is not None
        assert result.route_target is not None


# ══════════════════════════════════════════════════════════════
#  learning_tools — 资源、计划、错题、日历
# ══════════════════════════════════════════════════════════════

class TestLearningTools:
    """search_resources / view_study_plan / review_errors / open_calendar"""

    @pytest.fixture
    def tools_module(self):
        import importlib.util
        tools_path = (
            BACKEND
            / "app"
            / "domain"
            / "secretary"
            / "tools"
            / "learning_tools.py"
        )
        spec = importlib.util.spec_from_file_location(
            "learning_tools", str(tools_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_module_exports_tools_list(self, tools_module):
        """模块应导出 TOOLS 列表"""
        assert hasattr(tools_module, "TOOLS")
        assert isinstance(tools_module.TOOLS, list)
        assert len(tools_module.TOOLS) == 4

    def test_search_resources_tool_definition(self, tools_module):
        """search_resources 应包含 keyword 参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "search_resources" in tools
        assert "keyword" in tools["search_resources"].parameters

    @pytest.mark.asyncio
    async def test_search_resources_executes(self, tools_module):
        """search_resources 执行应返回正确路由"""
        tools = {t.name: t for t in tools_module.TOOLS}
        result = await tools["search_resources"].handler({"keyword": "微积分"})
        assert result.route_target == "/resources"
        assert result.route_params == {"search": "微积分"}

    def test_view_study_plan_tool_definition(self, tools_module):
        """view_study_plan 应存在且无参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "view_study_plan" in tools
        assert tools["view_study_plan"].parameters == {}

    @pytest.mark.asyncio
    async def test_view_study_plan_executes(self, tools_module):
        """view_study_plan 执行应返回 /study 路由"""
        tools = {t.name: t for t in tools_module.TOOLS}
        result = await tools["view_study_plan"].handler({})
        assert result.route_target == "/study"

    def test_review_errors_tool_definition(self, tools_module):
        """review_errors 应包含 subject 参数"""
        tools = {t.name: t for t in tools_module.TOOLS}
        assert "review_errors" in tools
        assert "subject" in tools["review_errors"].parameters

    @pytest.mark.asyncio
    async def test_review_errors_executes(self, tools_module):
        """review_errors 执行应返回正确路由"""
        tools = {t.name: t for t in tools_module.TOOLS}
        result = await tools["review_errors"].handler({"subject": "数学"})
        assert result.route_target == "/errors"
        assert result.route_params == {"subject": "数学"}

    @pytest.mark.asyncio
    async def test_review_errors_without_subject(self, tools_module):
        """review_errors 无 subject 时也应返回路由"""
        tools = {t.name: t for t in tools_module.TOOLS}
        result = await tools["review_errors"].handler({})
        assert result.route_target == "/errors"

    @pytest.mark.asyncio
    async def test_open_calendar_executes(self, tools_module):
        """open_calendar 执行应返回 /calendar 路由"""
        tools = {t.name: t for t in tools_module.TOOLS}
        result = await tools["open_calendar"].handler({})
        assert result.route_target == "/calendar"