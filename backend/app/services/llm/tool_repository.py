"""
ToolRepository — 统一工具聚合中心

替换 tool_executor.py 和 secretary/tools/tool_registry.py。

职责：
  1. 自动发现：扫描多个目录的工具定义
  2. 多操作合并：同一 *_tools.py 的多个工具 → 1 个工具 + action 参数
  3. 意图检测：基于策略的文本→工具匹配
  4. LLM Schema：生成统一的 Function Calling schema
  5. 工具分类：按类别索引工具

合并规则：
  同一 *_tools.py 文件中的 TOOLS 列表 → 合并为 1 个 tool_{module}，
  每个原始 tool 作为 action 参数的一个选项。
  e.g. start_practice + start_quiz → tool_practice(action: "start_practice" | "start_quiz", ...)
"""

from __future__ import annotations

import importlib.util
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from app.schemas.conversation import ResponseBlock

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════


@dataclass
class ToolParam:
    """工具参数定义"""
    type: str = "string"
    description: str = ""
    enum: list[str] | None = None
    default: Any = None


@dataclass
class ToolAction:
    """合并后的 Action（对应原始 tool）"""
    name: str
    description: str
    params: dict[str, ToolParam] = field(default_factory=dict)
    handler: Callable | None = None
    route: dict | None = None


@dataclass
class ToolDefinition:
    """统一工具定义（合并后）"""
    name: str             # e.g. "tool_practice"
    description: str
    category: str = ""    # practice / media / learning / knowledge / navigation / search
    actions: dict[str, ToolAction] = field(default_factory=dict)
    # 通用参数（非 action 维度的参数，如 query, subject）
    common_params: dict[str, ToolParam] = field(default_factory=dict)
    # 是否为合并后的复合工具
    is_composite: bool = False


@dataclass
class ToolIntent:
    """意图检测结果"""
    tool_name: str
    action: str | None = None   # 对复合工具
    confidence: float = 1.0
    params: dict = field(default_factory=dict)


class IntentStrategy(Protocol):
    """意图检测策略接口"""

    def detect(self, text: str, context: str) -> list[ToolIntent]: ...


# ═══════════════════════════════════════════════
# 内置策略：正则意图检测
# ═══════════════════════════════════════════════

# 用户消息 → 工具名（action 可选）
DIRECT_PATTERNS: dict[str, tuple[str, str | None]] = {
    r"视频|bilibili|b站|讲解视频|搜.*视频|找.*视频|有.*视频吗|搜.*教程": ("tool_search", "search_media"),
    r"出.*题|练习|做题|测试|考我|来.*题|生成.*题|练一练": ("tool_practice", "generate_practice"),
    r"画.*(?!思维|脑)|函数图|图表|可视化|示意图|画图|画.*函数|画.*图像": ("tool_media", "generate_image"),
    r"思维导图|脑图|知识结构|整理.*知识|知识.*整理|画.*思维|画.*脑图": ("tool_media", "generate_mindmap"),
    r"笔记|文档|PDF|讲义|总结.*笔记|笔记.*总结": ("tool_media", "generate_document"),
    r"有什么题库|查看题库|我的题库|有哪些题库": ("tool_practice", "query_question_banks"),
    r"搜.*题库|创建.*题库|新建.*题库": ("tool_practice", "create_question_bank"),
    r"(搜索|找|查找).*(资源|资料|教程)": ("tool_learning", "search_resources"),
    r"(查看|打开).*(计划|日程|安排)": ("tool_learning", "view_study_plan"),
    r"错题|复习.*题|回顾.*题": ("tool_learning", "review_errors"),
    r"(打开|查看).*(日历|日程)": ("tool_learning", "open_calendar"),
    r"(搜索|打开|查看).*(知识树|知识图谱)": ("tool_knowledge", "search_knowledge_tree"),
    r"(跳转|导航|去|打开).*(页面|仪表盘|首页|练习|学习|专注)": ("tool_navigation", "navigate_to_page"),
}

# AI 建议 → 用户肯定 → 工具
AI_SUGGESTION_PATTERNS: dict[str, tuple[str, str | None]] = {
    r"(搜|找|看看?).*?(视频|教程|讲解)": ("tool_search", "search_media"),
    r"(做|来|出|练|试试).*?(题|练习)": ("tool_practice", "generate_practice"),
    r"(画|生成).*?(图|图像|示意图)": ("tool_media", "generate_image"),
    r"(整理|生成|做).*?(思维导图|脑图|知识.*结构)": ("tool_media", "generate_mindmap"),
    r"(生成|整理|做|写).*?(笔记|文档|总结)": ("tool_media", "generate_document"),
    r"(查|看|浏览|打开).*?(题库|练习)": ("tool_practice", "query_question_banks"),
    r"(创建|新建|建).*?(题库|练习.*库)": ("tool_practice", "create_question_bank"),
}

AFFIRMATIVE_RE = re.compile(
    r"^(好[的啊吧呀]?|可以|嗯嗯?|行|试试|ok|yes|要[的得]?|来[吧]?|整[吧]?)$",
    re.IGNORECASE,
)


class RegexIntentDetector:
    """基于正则的意图检测策略（可替换为 LLM 分类器）"""

    def detect(self, text: str, context: str = "") -> list[ToolIntent]:
        matched: dict[str, str | None] = {}

        # 1. 直接匹配用户消息（后匹配的更具体，覆盖前者）
        for pattern, (tool_name, action) in DIRECT_PATTERNS.items():
            if re.search(pattern, text):
                matched[tool_name] = action

        # 2. 上下文感知：用户肯定 + AI 上次建议
        if AFFIRMATIVE_RE.match(text.strip()) and context:
            for pattern, (tool_name, action) in AI_SUGGESTION_PATTERNS.items():
                if re.search(pattern, context):
                    matched[tool_name] = action

        return [ToolIntent(tool_name=name, action=action) for name, action in matched.items()]


# ═══════════════════════════════════════════════
# ToolRepository
# ═══════════════════════════════════════════════


class ToolRepository:
    """工具聚合中心 — 自动发现 + 合并 + 意图检测 + LLM Schema"""

    _instance: ToolRepository | None = None

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._categories: dict[str, list[str]] = {}  # "practice" → ["tool_practice"]
        self._detector: IntentStrategy = RegexIntentDetector()

    @classmethod
    def get_instance(cls) -> ToolRepository:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 自动发现 ──

    def discover(self, source_dirs: list[str]) -> int:
        """扫描工具目录，自动发现并合并工具

        每个 *_tools.py → 合并为一个 tool_{module_name}，
        原始 TOOLS 列表作为 actions。
        同时也扫描 LLM 格式的 TOOL_DEFINITIONS（tool_executor.py 风格）。
        """
        total = 0
        for src_dir in source_dirs:
            base = Path(src_dir)
            if not base.exists():
                logger.warning("Tool source directory not found: %s", src_dir)
                continue

            for py_file in sorted(base.glob("*_tools.py")):
                module_name = py_file.stem  # e.g. "learning_tools"
                tool_name = f"tool_{module_name.replace('_tools', '')}"

                spec = importlib.util.spec_from_file_location(
                    f"tool_repo.{module_name}", str(py_file),
                )
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                tools = getattr(module, "TOOLS", [])
                if not tools:
                    continue

                # 合并同一模块的工具
                merged = self._merge_tools(tool_name, module_name, tools)
                self._tools[merged.name] = merged
                self._categorize(merged)
                total += len(tools)
                logger.info(
                    "Merged %d tools → %s (%d actions): %s",
                    len(tools), merged.name, len(merged.actions),
                    list(merged.actions.keys()),
                )

        return total

    def _merge_tools(
        self, tool_name: str, module_name: str, tools: list,
    ) -> ToolDefinition:
        """合并同一模块的多个工具 → 1 个工具 + action 参数"""
        actions: dict[str, ToolAction] = {}
        all_params: set[str] = set()
        category = module_name.replace("_tools", "")

        for tool in tools:
            # 收集参数名
            params = {}
            for pname, pdef in (getattr(tool, "parameters", {}) or {}).items():
                if isinstance(pdef, dict):
                    params[pname] = ToolParam(
                        type=pdef.get("type", "string"),
                        description=pdef.get("description", ""),
                        enum=pdef.get("enum"),
                        default=pdef.get("default"),
                    )
                else:
                    params[pname] = ToolParam(description=str(pdef))
                all_params.add(pname)

            actions[tool.name] = ToolAction(
                name=tool.name,
                description=getattr(tool, "description", tool.name),
                params=params,
                handler=getattr(tool, "handler", None),
                route=getattr(tool, "route", None),
            )

        # 公共参数：所有 action 共享的参数
        common_param_names = set.intersection(*[set(a.params.keys()) for a in actions.values()]) if actions else set()

        return ToolDefinition(
            name=tool_name,
            description=f"复合工具 — {module_name}（{len(actions)} 个操作）",
            category=category,
            actions=actions,
            common_params={
                pname: ToolParam(type="string", description=f"多个操作共用: {pname}")
                for pname in common_param_names
            },
            is_composite=len(actions) > 1,
        )

    def _categorize(self, tool: ToolDefinition) -> None:
        """按类别索引工具"""
        cat = tool.category or "general"
        if cat not in self._categories:
            self._categories[cat] = []
        self._categories[cat].append(tool.name)

    # ── 注册（手动添加 LLM 格式工具） ──

    def register_raw_tools(self, definitions: list[dict]) -> None:
        """注册 LLM Function Calling 格式的工具定义（来自 tool_executor.py）"""
        for tool_def in definitions:
            func = tool_def.get("function", {})
            name = func.get("name", "")
            if not name:
                continue

            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])

            # 构建 ToolAction 及其参数
            actions = {}
            for pname, pdef in params.items():
                tp = ToolParam(
                    type=pdef.get("type", "string"),
                    description=pdef.get("description", ""),
                    enum=pdef.get("enum"),
                    default=pdef.get("default"),
                )
                # 参数名作为 key，保证 schema 生成正确
                actions[pname] = ToolAction(
                    name=pname,
                    description=pdef.get("description", ""),
                    params={pname: tp},
                )

            # 不合并 — 每个 LLM 工具独立存在
            if name not in self._tools:
                self._tools[name] = ToolDefinition(
                    name=name,
                    description=func.get("description", ""),
                    category="llm_raw",
                    actions=actions,
                )

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        self._categorize(tool)

    # ── 查询 ──

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def by_category(self, cat: str) -> list[ToolDefinition]:
        names = self._categories.get(cat, [])
        return [t for t in (self._tools.get(n) for n in names) if t]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def list_actions(self, tool_name: str) -> list[str]:
        tool = self._tools.get(tool_name)
        return list(tool.actions.keys()) if tool else []

    # ── 意图检测 ──

    def detect_intent(self, text: str, context: str = "") -> list[ToolIntent]:
        """检测文本中的工具意图"""
        return self._detector.detect(text, context)

    def set_detector(self, detector: IntentStrategy) -> None:
        self._detector = detector

    # ── LLM Schema ──

    def to_llm_schema(self) -> list[dict]:
        """生成 LLM Function Calling schema（合并后）"""
        schemas = []
        for tool in self._tools.values():
            if tool.is_composite:
                # 复合工具：action 作为第一个参数
                schema = self._build_composite_schema(tool)
            else:
                schema = self._build_simple_schema(tool)
            schemas.append(schema)
        return schemas

    def _build_composite_schema(self, tool: ToolDefinition) -> dict:
        """构建复合工具 schema"""
        action_enum = list(tool.actions.keys())
        action_desc_map = {
            aname: a.description for aname, a in tool.actions.items()
        }

        properties = {
            "action": {
                "type": "string",
                "enum": action_enum,
                "description": "选择要执行的操作: " + "; ".join(
                    f"{k}={v}" for k, v in action_desc_map.items()
                ),
            },
        }

        # 添加所有 action 的独特参数
        for aname, action in tool.actions.items():
            for pname, pdef in action.params.items():
                if pname not in properties:
                    prop = {"type": pdef.type, "description": pdef.description}
                    if pdef.enum:
                        prop["enum"] = pdef.enum
                    properties[pname] = prop

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": ["action"],
                },
            },
        }

    def _build_simple_schema(self, tool: ToolDefinition) -> dict:
        """构建简单工具 schema（非复合）"""
        properties = {}
        required = []
        for aname, action in tool.actions.items():
            for pname, pdef in action.params.items():
                prop = {"type": pdef.type, "description": pdef.description}
                if pdef.enum:
                    prop["enum"] = pdef.enum
                properties[pname] = prop
                required.append(pname)

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    # ── 执行 ──

    async def execute(
        self, tool_name: str, action: str, params: dict,
        user_id: str = "", **kwargs,
    ) -> ResponseBlock | Any:
        """执行工具（合并后）"""
        tool = self._tools.get(tool_name)
        if not tool:
            raise KeyError(f"Tool not found: {tool_name}")

        if tool.is_composite and action:
            tool_action = tool.actions.get(action)
            if not tool_action:
                raise KeyError(f"Action {action} not found in tool {tool_name}")
            if tool_action.handler:
                result = await tool_action.handler(params)
                return result

        # Fallback: 使用旧 tool_executor
        from app.services.llm.tool_executor import tool_executor
        return await tool_executor.execute(tool_name, params, user_id=user_id)


# 全局单例
def get_tool_repository() -> ToolRepository:
    return ToolRepository.get_instance()