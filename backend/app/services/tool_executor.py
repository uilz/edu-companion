"""
工具执行器 - 统一处理快/慢工具
"""
from __future__ import annotations
import logging
import re
from app.schemas.conversation import ResponseBlock

from shared.constants import DEFAULT_USER_ID
logger = logging.getLogger(__name__)

# ── 意图预判规则 ──
TOOL_RULES: dict[str, str] = {
    r"视频|bilibili|b站|讲解视频|搜.*视频|找.*视频|有.*视频吗|搜.*教程": "search_media",
    r"出.*题|练习|做题|测试|考我|来.*题": "generate_practice",
    r"画|图像|函数图|图表|可视化|示意图": "generate_image",
    r"思维导图|脑图|知识结构|整理.*知识|知识.*整理": "generate_mindmap",
    r"笔记|文档|PDF|讲义|总结.*笔记|笔记.*总结": "generate_document",
}

# 肯定回复 + AI 上次建议了某个工具 → 触发该工具
AI_SUGGESTION_PATTERNS: dict[str, str] = {
    r"(搜|找|看看?).*?(视频|教程|讲解)": "search_media",
    r"(做|来|出|练|试试).*?(题|练习)": "generate_practice",
    r"(画|生成).*?(图|图像|示意图)": "generate_image",
    r"(整理|生成|做).*?(思维导图|脑图|知识.*结构)": "generate_mindmap",
    r"(生成|整理|做|写).*?(笔记|文档|总结)": "generate_document",
}

AFFIRMATIVE_PATTERNS = re.compile(
    r"^(好[的啊吧呀]?|可以|嗯嗯?|行|试试|ok|yes|要[的得]?|来[吧]?|整[吧]?)$",
    re.IGNORECASE,
)


def predict_tools(text: str, previous_ai_text: str = "") -> list[str]:
    """规则预判：返回需要调用的工具列表。支持上下文感知（AI建议→用户同意）"""
    matched: set[str] = set()

    # 1. 直接匹配用户消息
    for pattern, tool in TOOL_RULES.items():
        if re.search(pattern, text):
            matched.add(tool)

    # 2. 上下文感知：用户肯定回复 + AI 上次建议了某个工具
    if AFFIRMATIVE_PATTERNS.match(text.strip()) and previous_ai_text:
        for pattern, tool in AI_SUGGESTION_PATTERNS.items():
            if re.search(pattern, previous_ai_text):
                matched.add(tool)

    return list(matched)

# ── 工具定义 (LLM tools格式) ──
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_media",
            "description": "搜索B站/YouTube/知乎等平台的学习视频和教程",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索内容/知识点"},
                    "platforms": {"type": "array", "items": {"type": "string"}, "description": "平台列表: bilibili/youtube/zhihu/baidu_wenku"},
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
FAST_TOOLS = {"search_media", "generate_practice"}
SLOW_TOOLS = {"generate_image", "generate_mindmap", "generate_document"}

# ── 工具处理器 ──
async def _handle_search_media(params: dict) -> dict:
    """多平台媒体搜索：生成搜索链接 + AI优化关键词"""
    query = params.get("query", "")
    platforms = params.get("platforms", ["bilibili", "zhihu", "youtube"])

    from app.services.media_search import media_search
    results = await media_search.search(query=query, platforms=platforms)
    return {"query": query, "platforms": results}


async def _handle_generate_practice(params: dict) -> dict:
    """生成练习题 — 对接真实练习系统"""
    subject = params.get("subject", "")
    kp = params.get("knowledge_point", subject)
    difficulty_str = params.get("difficulty", "进阶")
    count = params.get("count", 1)

    # 难度映射: 基础=0.3, 进阶=0.6, 挑战=0.9
    difficulty_map = {"基础": 0.3, "进阶": 0.6, "挑战": 0.9}
    difficulty = difficulty_map.get(difficulty_str, 0.6)

    try:
        from app.services.question_generator import get_question_generator
        from app.services.llm_service import llm_service
        from app.core.learner_model import learner_engine

        question_generator = get_question_generator(llm_service)

        # 调用题目生成器（同步方法）
        questions = question_generator.generate(
            subject=subject,
            skill_id=kp,
            difficulty=difficulty,
            count=min(count, 3),
        )

        if questions:
            # 创建练习会话
            session_id = learner_engine.create_session(
                user_id=DEFAULT_USER_ID,
                subject=subject,
            )
            return {
                "subject": subject,
                "knowledge_point": kp,
                "difficulty": difficulty_str,
                "count": len(questions),
                "session_id": session_id,
                "questions": [q.model_dump() if hasattr(q, 'model_dump') else q for q in questions],
            }

        return {
            "subject": subject,
            "knowledge_point": kp,
            "difficulty": difficulty_str,
            "count": 0,
            "message": f"当前题库中关于{kp}的题目不足，建议切换到搜索模式获取更多学习资源。",
        }
    except Exception as e:
        logger.warning("generate_practice fallback: %s", e)
        return {
            "subject": subject,
            "knowledge_point": kp,
            "difficulty": difficulty_str,
            "count": 0,
            "message": f"让我来为你讲解{subject}中的{kp}。首先，你目前对这个概念了解多少？",
            "fallback": True,
        }


async def _handle_generate_image(params: dict) -> dict:
    """生成配图 — Phase 5: 对接 SVGRenderer"""
    prompt = params.get("prompt", "")
    style = params.get("style", "diagram")

    try:
        from infra.svg_renderer import SVGRenderer
        renderer = SVGRenderer()

        if style == "chart":
            result = await renderer.render_diagram(prompt, "comparison")
        elif style == "illustration":
            result = await renderer.render_diagram(prompt, "concept")
        else:
            # 自动检测
            if "$" in prompt:
                result = await renderer.render_latex(prompt)
            else:
                result = await renderer.render_diagram(prompt, "concept")

        return {
            "prompt": prompt,
            "style": style,
            "url": result["url"],
            "format": result["format"],
            "cache_hit": result.get("cache_hit", False),
        }
    except Exception as e:
        logger.warning("generate_image fallback: %s", e)
        return {
            "prompt": prompt,
            "style": style,
            "url": None,
            "error": str(e),
            "status": "queued",
        }


async def _handle_generate_mindmap(params: dict) -> dict:
    """生成思维导图 — 从知识图谱获取真实子主题，fallback 到 LLM 生成"""
    topic = params.get("topic", "")
    depth = params.get("depth", 3)
    user_id = params.get("user_id", "")
    partition_id = params.get("partition_id", "")

    nodes = [{"id": "root", "label": topic, "level": 0}]
    edges = []

    # 尝试从知识图谱获取相关知识点
    subtopics = []
    if user_id and partition_id:
        try:
            from app.services.storage import storage as _mm_storage
            _data = _mm_storage.load(user_id)
            graph = _data.knowledge_graphs.get(partition_id)
            if graph and graph.nodes:
                # 找与 topic 相关的知识点
                topic_lower = topic.lower()
                for n in graph.nodes.values():
                    if not n.is_deleted and (
                        topic_lower in n.label.lower()
                        or n.label.lower() in topic_lower
                        or any(topic_lower in s.lower() for s in getattr(n, "tags", []) or [])
                    ):
                        subtopics.append(n.label)
                # 如果匹配不够，补充 mastery 最低的薄弱知识点
                if len(subtopics) < depth:
                    weak = sorted(
                        [n for n in graph.nodes.values() if not n.is_deleted and n.label not in subtopics],
                        key=lambda n: n.mastery,
                    )
                    for n in weak:
                        if len(subtopics) >= depth * 2:
                            break
                        subtopics.append(n.label)
        except Exception as e:
            logger.debug(f"知识图谱子主题获取失败: {e}")

    # fallback: 用 LLM 生成子主题
    if len(subtopics) < 2:
        try:
            from app.services.llm_service import llm_service
            resp = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是教育专家。给定主题，输出3-6个核心子主题，每行一个，不要编号。"},
                    {"role": "user", "content": f"主题: {topic}"},
                ],
                task_type="chat",
                temperature=0.5,
                max_tokens=200,
            )
            llm_topics = [line.strip().lstrip("0123456789.-、）) ") for line in resp.strip().split("\n") if line.strip()]
            subtopics = llm_topics[:depth * 2] if llm_topics else subtopics
        except Exception as e:
            logger.debug(f"LLM 子主题生成失败: {e}")

    # 最终 fallback
    if not subtopics:
        subtopics = ["定义", "核心概念", "应用", "练习"]

    for i, st in enumerate(subtopics[:depth * 2]):
        node_id = f"node_{i}"
        nodes.append({"id": node_id, "label": st, "level": 1})
        edges.append({"from": "root", "to": node_id})

    return {
        "topic": topic,
        "depth": depth,
        "nodes": nodes,
        "edges": edges,
        "status": "ready",
    }


async def _handle_generate_document(params: dict) -> dict:
    """生成学习文档/笔记 — MVP: 返回 Markdown 文本"""
    topic = params.get("topic", "")
    fmt = params.get("format", "markdown")

    # 调用 LLM 生成文档内容
    try:
        from app.services.llm_service import llm_service
        doc_prompt = f"""请为主题「{topic}」生成一份学习笔记，格式为{fmt}。

要求：
- 结构清晰，包含标题、要点、总结
- 使用中文
- 适合学生复习使用
- 长度适中（500-800字）"""

        content = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是一个专业的笔记整理助手。"},
                {"role": "user", "content": doc_prompt},
            ],
            task_type="explain",
            temperature=0.3,
            max_tokens=1024,
        )
    except Exception as e:
        logger.warning("generate_document LLM fallback: %s", e)
        content = f"# {topic}\n\n## 概述\n...\n\n> 文档生成中，请稍候..."

    return {
        "topic": topic,
        "format": fmt,
        "content": content,
        "status": "ready",
    }

TOOL_HANDLERS = {
    "search_media": _handle_search_media,
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
