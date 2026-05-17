"""
工具执行器 - 统一处理快/慢工具
"""
from __future__ import annotations
import logging
import re
import time
from uuid import uuid4
from app.schemas.conversation import ResponseBlock, BackgroundJob

logger = logging.getLogger(__name__)

# ── 意图预判规则 ──
TOOL_RULES: dict[str, str] = {
    r"视频|bilibili|b站|讲解视频|搜.*视频": "search_bilibili",
    r"出.*题|练习|做题|测试|考我|来.*题": "generate_practice",
    r"画|图像|函数图|图表|可视化|示意图": "generate_image",
    r"思维导图|脑图|知识结构|整理.*知识|知识.*整理": "generate_mindmap",
    r"笔记|文档|PDF|讲义|总结.*笔记|笔记.*总结": "generate_document",
}

def predict_tools(text: str) -> list[str]:
    """规则预判：返回需要调用的工具列表"""
    matched: set[str] = set()
    for pattern, tool in TOOL_RULES.items():
        if re.search(pattern, text):
            matched.add(tool)
    return list(matched)

# ── 工具定义 (LLM tools格式) ──
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_bilibili",
            "description": "搜索B站教学视频",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "description": "返回数量", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_practice",
            "description": "生成练习题",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "学科"},
                    "knowledge_point": {"type": "string", "description": "知识点"},
                    "difficulty": {"type": "string", "enum": ["基础", "进阶", "挑战"], "default": "进阶"},
                    "count": {"type": "integer", "description": "题目数量", "default": 1},
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "生成图片（函数图像、概念图、示意图等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图片描述"},
                    "style": {"type": "string", "enum": ["diagram", "illustration", "chart"], "default": "diagram"},
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mindmap",
            "description": "生成思维导图",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "主题"},
                    "depth": {"type": "integer", "description": "层级深度", "default": 3},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_document",
            "description": "生成学习文档/笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "主题"},
                    "format": {"type": "string", "enum": ["pdf", "markdown", "word"], "default": "markdown"},
                },
                "required": ["topic"],
            },
        },
    },
]

# ── 工具分类 ──
FAST_TOOLS = {"search_bilibili", "generate_practice"}
SLOW_TOOLS = {"generate_image", "generate_mindmap", "generate_document"}

# ── 工具处理器 ──
async def _handle_search_bilibili(params: dict) -> dict:
    """搜索B站视频 (MVP: 返回模拟数据)"""
    query = params.get("query", "")
    limit = params.get("limit", 3)
    # MVP: 模拟搜索结果
    return {
        "results": [
            {
                "title": f"【教学】{query}详解 - 从入门到精通",
                "url": "https://www.bilibili.com/video/BV1example",
                "thumbnail": "",
                "duration": "15:32",
                "author": "知识区UP主",
            }
        ][:limit],
        "query": query,
    }

async def _handle_generate_practice(params: dict) -> dict:
    """生成练习题 (MVP: 返回模拟数据)"""
    subject = params.get("subject", "")
    kp = params.get("knowledge_point", "")
    difficulty = params.get("difficulty", "进阶")
    return {
        "subject": subject,
        "knowledge_point": kp,
        "difficulty": difficulty,
        "question": f"关于{subject}中{kp}的练习题（MVP占位）",
        "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
        "answer": "A",
        "explanation": "这是一道关于" + kp + "的基础练习题。",
    }

async def _handle_generate_image(params: dict) -> dict:
    """生成图片 (MVP: 返回占位)"""
    return {"prompt": params.get("prompt", ""), "url": None, "status": "queued"}

async def _handle_generate_mindmap(params: dict) -> dict:
    """生成思维导图 (MVP: 返回占位)"""
    return {"topic": params.get("topic", ""), "nodes": [], "edges": [], "status": "queued"}

async def _handle_generate_document(params: dict) -> dict:
    """生成文档 (MVP: 返回占位)"""
    return {"topic": params.get("topic", ""), "format": params.get("format", "markdown"), "url": None, "status": "queued"}

TOOL_HANDLERS = {
    "search_bilibili": _handle_search_bilibili,
    "generate_practice": _handle_generate_practice,
    "generate_image": _handle_generate_image,
    "generate_mindmap": _handle_generate_mindmap,
    "generate_document": _handle_generate_document,
}


class ToolExecutor:
    """统一的工具执行器"""

    async def execute(self, tool_name: str, params: dict) -> ResponseBlock:
        """执行工具，返回 ResponseBlock"""
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return ResponseBlock(
                type=tool_name, status="failed",
                content={"error": f"Unknown tool: {tool_name}"}
            )

        if tool_name in FAST_TOOLS:
            return await self._execute_inline(tool_name, handler, params)
        else:
            return await self._create_placeholder(tool_name, params)

    async def _execute_inline(self, name: str, handler, params: dict) -> ResponseBlock:
        """快任务：直接执行"""
        try:
            result = await handler(params)
            return ResponseBlock(type=name, status="ready", content=result)
        except Exception as e:
            return ResponseBlock(type=name, status="failed", content={"error": str(e)})

    async def _create_placeholder(self, name: str, params: dict) -> ResponseBlock:
        """慢任务：创建占位符"""
        return ResponseBlock(
            type=name, status="generating",
            content={"params": params, "progress": 0}
        )

    def get_tools_for_llm(self, tool_names: list[str] | None = None) -> list[dict]:
        """获取给LLM的工具定义"""
        if tool_names is None:
            return TOOL_DEFINITIONS
        return [t for t in TOOL_DEFINITIONS if t["function"]["name"] in tool_names]

    def create_response_block(self, message_id: str, partition_id: str, branch_id: str, block_type: str, content: dict, status: str = "ready", order: int = 0) -> ResponseBlock:
        """创建 ResponseBlock"""
        return ResponseBlock(
            message_id=message_id,
            partition_id=partition_id,
            branch_id=branch_id,
            type=block_type,
            status=status,
            content=content,
            order=order,
        )

tool_executor = ToolExecutor()
