"""
工具执行器 - 统一处理快/慢工具

工具定义（TOOL_DEFINITIONS）和意图检测已移至 tool_repository.py。
"""
from __future__ import annotations
import logging
from app.schemas.conversation import ResponseBlock
from app.infrastructure.llm.tool_repository import TOOL_DEFINITIONS, FAST_TOOLS, SLOW_TOOLS, _TOOL_TO_BLOCK_TYPE
from app.services.secretary.tool_handler import handle_secretary_diagnose
from app.infrastructure.llm.knowledge_ops_tools import TOOL_HANDLERS as KTOOL_HANDLERS, TOOL_DEFINITIONS as KTOOL_DEFINITIONS
from app.infrastructure.llm.liveroom_tools import TOOL_HANDLERS as LROOM_HANDLERS

logger = logging.getLogger(__name__)

# ── 工具处理器 ──
async def _handle_search_media(params: dict) -> dict:
    """多平台媒体搜索：生成搜索链接 + AI优化关键词"""
    query = params.get("query", "")
    platforms = params.get("platforms", ["bilibili", "zhihu", "youtube"])

    from app.infrastructure.media.media_search import media_search
    results = await media_search.search(query=query, platforms=platforms)
    return {"query": query, "platforms": results}


async def _handle_generate_practice(params: dict) -> dict:
    """生成练习题 — 对接练习系统（自动保存到题库）"""
    subject = params.get("subject", "")
    kp = params.get("knowledge_point", subject)
    difficulty_str = params.get("difficulty", "进阶")
    count = params.get("count", 2)
    conv_id = params.get("conv_id", "")
    user_text = params.get("knowledge_point", subject)
    bank_name = params.get("bank_name", "").strip() or None
    uid = params.get("user_id", "")

    try:
        from app.services.practice.practice_question_gen import handle_question_generation

        result = await handle_question_generation(
            user_message=user_text[:200],
            user_id=uid,
            conv_id=conv_id or None,
            bank_name=bank_name,
        )

        questions = result.get("questions", [])
        bank_id = result.get("bank_id", "")

        if questions:
            return {
                "subject": subject,
                "knowledge_point": kp,
                "difficulty": difficulty_str,
                "count": len(questions),
                "bank_id": bank_id,
                "questions": questions,
            }

        return {
            "subject": subject,
            "knowledge_point": kp,
            "difficulty": difficulty_str,
            "count": 0,
            "bank_id": bank_id,
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
        from app.infrastructure.svg_renderer import SVGRenderer
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
    dir_id = params.get("dir_id", "")

    nodes = [{"id": "root", "label": topic, "level": 0}]
    edges = []

    # 尝试从知识图谱获取相关知识点
    subtopics = []
    if user_id and dir_id:
        try:
            from app.services.common import get_data_repo as _mm_storage
            _data = _mm_storage().load(user_id)
            graph = _data.knowledge_graphs.get(dir_id)
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
            from app.infrastructure.llm.llm_service import llm_service
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
        from app.infrastructure.llm.llm_service import llm_service
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


# ── 题库工具处理器 ──


async def _handle_query_question_banks(params: dict) -> dict:
    """查询题库和题目，支持列出/搜索/查看详情"""
    action = params.get("action", "list_banks")
    bank_id = params.get("bank_id", "")
    keyword = params.get("keyword", "")
    limit = params.get("limit", 20)
    user_id = params.get("user_id", "")

    from app.services.practice.practice_question_bank import list_banks, get_bank

    try:
        if action == "list_banks":
            banks = list_banks(user_id) if user_id else []
            items = []
            for b in banks[:limit]:
                items.append({
                    "id": b.get("id"),
                    "name": b.get("name"),
                    "description": b.get("description", ""),
                    "question_count": b.get("real_count") or b.get("question_count", 0),
                    "created_at": b.get("created_at", ""),
                })
            return {
                "action": "list_banks",
                "total": len(banks),
                "banks": items,
                "summary": f"共有 {len(banks)} 个题库，当前显示 {len(items)} 个",
            }

        elif action == "get_bank" and bank_id:
            bank = get_bank(bank_id, user_id) if user_id else None
            if not bank:
                return {"action": "get_bank", "error": f"未找到题库: {bank_id}", "found": False}

            # 获取题库内的题目
            from app.infrastructure.db.database import get_db
            db = get_db()
            questions = db.fetchall(
                """SELECT id, stem, question_type, difficulty, bloom_level, metadata
                   FROM questions WHERE bank_id = %s AND deleted_at IS NULL
                   ORDER BY created_at DESC LIMIT %s""",
                (bank_id, limit),
            )
            q_list = []
            for q in questions:
                q_list.append({
                    "id": q["id"],
                    "stem": q["stem"][:100] + ("..." if len(q["stem"]) > 100 else ""),
                    "type": q["question_type"],
                    "difficulty": q["difficulty"],
                    "bloom": q.get("bloom_level", ""),
                })

            return {
                "action": "get_bank",
                "found": True,
                "bank": {
                    "id": bank.get("id"),
                    "name": bank.get("name"),
                    "description": bank.get("description", ""),
                    "question_count": bank.get("real_count") or bank.get("question_count", 0),
                },
                "questions": q_list,
                "summary": f"题库「{bank.get('name')}」共 {len(q_list)} 道题",
            }

        elif action == "search_questions":
            from app.infrastructure.db.database import get_db
            db = get_db()
            if bank_id:
                if keyword:
                    rows = db.fetchall(
                        """SELECT q.id, q.stem, q.question_type, q.difficulty, qb.name as bank_name
                           FROM questions q JOIN question_banks qb ON q.bank_id = qb.id
                           WHERE q.bank_id = %s AND q.deleted_at IS NULL
                             AND q.stem ILIKE %s
                           ORDER BY q.created_at DESC LIMIT %s""",
                        (bank_id, f"%{keyword}%", limit),
                    )
                else:
                    rows = db.fetchall(
                        """SELECT q.id, q.stem, q.question_type, q.difficulty, qb.name as bank_name
                           FROM questions q JOIN question_banks qb ON q.bank_id = qb.id
                           WHERE q.bank_id = %s AND q.deleted_at IS NULL
                           ORDER BY q.created_at DESC LIMIT %s""",
                        (bank_id, limit),
                    )
            else:
                if keyword:
                    rows = db.fetchall(
                        """SELECT q.id, q.stem, q.question_type, q.difficulty, qb.name as bank_name
                           FROM questions q JOIN question_banks qb ON q.bank_id = qb.id
                           WHERE q.deleted_at IS NULL AND q.stem ILIKE %s
                           ORDER BY q.created_at DESC LIMIT %s""",
                        (f"%{keyword}%", limit),
                    )
                else:
                    rows = []

            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "stem": r["stem"][:120] + ("..." if len(r["stem"]) > 120 else ""),
                    "type": r["question_type"],
                    "difficulty": r["difficulty"],
                    "bank_name": r.get("bank_name", ""),
                })

            return {
                "action": "search_questions",
                "keyword": keyword,
                "total": len(items),
                "questions": items,
                "summary": f"找到 {len(items)} 道题{'包含「' + keyword + '」' if keyword else ''}",
            }

        return {"action": action, "error": f"未知操作: {action}"}
    except Exception as e:
        logger.warning("query_question_banks error: %s", e)
        return {"action": action, "error": str(e), "summary": "查询题库失败"}


async def _handle_create_question_bank(params: dict) -> dict:
    """创建一个新的题库"""
    name = params.get("name", "").strip()
    description = params.get("description", "").strip()
    subject = params.get("subject", "").strip()
    uid = params.get("user_id", "")

    if not name:
        return {"error": "题库名称不能为空", "created": False}

    from app.services.practice.practice_question_bank import create_bank

    bank = create_bank(
        user_id=uid,
        name=name,
        description=description,
        auto_created=False,
    )
    if bank:
        return {
            "created": True,
            "bank": {
                "id": bank.get("id"),
                "name": bank.get("name"),
                "description": bank.get("description", ""),
            },
            "summary": f"已创建题库「{name}」，题库ID: {bank.get('id')}。接下来可以用 generate_practice 向其中添加题目。",
        }
    return {"error": "创建题库失败", "created": False}


async def _handle_ask_question(params: dict) -> dict:
    """提问工具 — 直接返回问题数据，由前端交互处理"""
    questions = params.get("questions", [])
    # 兼容旧版单问题格式
    if not questions and params.get("question"):
        questions = [
            {
                "question": params["question"],
                "options": params.get("options", []),
            }
        ]
    return {
        "type": params.get("type", "choice"),
        "questions": questions,
    }


TOOL_HANDLERS = {
    "search_media": _handle_search_media,
    "generate_practice": _handle_generate_practice,
    "query_question_banks": _handle_query_question_banks,
    "create_question_bank": _handle_create_question_bank,
    "generate_image": _handle_generate_image,
    "generate_mindmap": _handle_generate_mindmap,
    "generate_document": _handle_generate_document,
    "secretary_diagnose": handle_secretary_diagnose,
    "ask_question": _handle_ask_question,
    "rename_conversation": None,  # inline 处理, 见 reply_pipeline.py
}
# 合并知识树操作工具
TOOL_HANDLERS.update(KTOOL_HANDLERS)
# 合并 LanguageRoom 工具 (ADR 0004 决策 5)
TOOL_HANDLERS.update(LROOM_HANDLERS)

class ToolExecutor:
    """统一的工具执行器"""

    async def execute(self, tool_name: str, params: dict, user_id: str = "") -> ResponseBlock:
        """执行工具，返回 ResponseBlock"""
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return ResponseBlock(
                type=tool_name, status="failed",
                content={"error": f"Unknown tool: {tool_name}"}
            )

        # 注入 user_id 到 params
        if user_id:
            params = {**params, "user_id": user_id}

        if tool_name in FAST_TOOLS:
            return await self._execute_inline(tool_name, handler, params)
        else:
            return await self._create_placeholder(tool_name, params)

    async def _execute_inline(self, name: str, handler, params: dict) -> ResponseBlock:
        """快任务：直接执行"""
        try:
            result = await handler(params)
            # 前端期望的 block type 映射
            display_type = _TOOL_TO_BLOCK_TYPE.get(name, name)
            return ResponseBlock(type=display_type, status="ready", content=result)
        except Exception as e:
            return ResponseBlock(type=name, status="failed", content={"error": str(e)})

    async def _create_placeholder(self, name: str, params: dict) -> ResponseBlock:
        """慢任务：创建占位符"""
        display_type = _TOOL_TO_BLOCK_TYPE.get(name, name)
        return ResponseBlock(
            type=display_type, status="generating",
            content={"params": params, "progress": 0}
        )

    def get_tools_for_llm(self, tool_names: list[str] | None = None) -> list[dict]:
        """获取给LLM的工具定义"""
        if tool_names is None:
            return TOOL_DEFINITIONS
        return [t for t in TOOL_DEFINITIONS if t["function"]["name"] in tool_names]

    def create_response_block(self, message_id: str, dir_id: str, branch_id: str, block_type: str, content: dict, status: str = "ready", order: int = 0) -> ResponseBlock:
        """创建 ResponseBlock"""
        return ResponseBlock(
            message_id=message_id,
            dir_id=dir_id,
            branch_id=branch_id,
            type=block_type,
            status=status,
            content=content,
            order=order,
        )

tool_executor = ToolExecutor()
