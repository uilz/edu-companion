"""
AI 出题核心 — generate_and_save + handle_question_generation

流程：
1. handle_question_generation() 解析自然语言 → 提取参数（subject/skill/bloom/difficulty/count）
2. generate_and_save()  → 调用 QuestionGenerator → 转 v7 格式 → save → 返回
3. generate_for_conversation() → 结合对话上下文 → 生成 + 自动归属题库
"""

import asyncio
import json
import logging
from typing import Optional

from shared.constants import DEFAULT_USER_ID
from app.services.llm_service import llm_service
from app.services.question_generator import QuestionGenerator, get_question_generator
from app.services.practice_question_crud import add_question
from app.services.practice_question_bank import (
    _ensure_tables, resolve_bank_for_conversation, resolve_bank_for_node, get_bank,
)
from app.schemas.practice import BloomLevel, AnswerType

logger = logging.getLogger(__name__)

# ── Bloom 层级中英文映射 ──
BLOOM_ZH_MAP = {
    "记忆": BloomLevel.REMEMBER,
    "remember": BloomLevel.REMEMBER,
    "理解": BloomLevel.UNDERSTAND,
    "understand": BloomLevel.UNDERSTAND,
    "应用": BloomLevel.APPLY,
    "apply": BloomLevel.APPLY,
    "分析": BloomLevel.ANALYZE,
    "analyze": BloomLevel.ANALYZE,
    "评价": BloomLevel.EVALUATE,
    "evaluate": BloomLevel.EVALUATE,
    "创造": BloomLevel.CREATE,
    "create": BloomLevel.CREATE,
}

# ── 题型映射 ──
CONTENT_TYPE_MAP = {
    "单选": "choice",
    "choice": "choice",
    "选择": "choice",
    "多选": "multiple",
    "multiple": "multiple",
    "填空": "fill",
    "fill": "fill",
    "解答": "free_form",
    "free_form": "free_form",
    "计算": "calculation",
    "calculation": "calculation",
}


# ── 核心函数 ──


async def generate_and_save(
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
    subject: str = "数学",
    skill_id: str = "",
    bloom_level: str = "apply",
    difficulty: float = 0.5,
    count: int = 3,
    content_type: str = "choice",
    material_context: Optional[str] = None,
    cognitive_node_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    AI 出题并保存到题库。

    流程：
    1. 解析 bloom_level → BloomLevel 枚举
    2. 异步调用 sync QuestionGenerator.generate()（通过 run_in_executor）
    3. Question Pydantic → v7 题目 dict
    4. 逐题调用 add_question() 保存
    """
    _ensure_tables()

    # 解析 Bloom 级别
    bloom_enum = BLOOM_ZH_MAP.get(bloom_level.lower(), BloomLevel.APPLY) if isinstance(bloom_level, str) else bloom_level

    # 获取 QuestionGenerator（同步构造，但 generate 本身是同步的）
    gen = get_question_generator(llm_service)
    if not gen:
        gen = QuestionGenerator(llm_service)

    # 在 executor 中运行同步 LLM 调用
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(
        None,
        lambda: gen.generate(
            subject=subject,
            skill_id=skill_id or subject,
            bloom_level=bloom_enum,
            difficulty=difficulty,
            count=count,
            content_type=content_type,
            material_context=material_context,
        ),
    )

    if not questions:
        logger.warning("AI 出题生成 0 道题目")
        return []

    # 转 v7 格式并保存
    saved = []
    for q in questions:
        v7_q = add_question(
            bank_id=bank_id,
            user_id=user_id,
            question_type=CONTENT_TYPE_MAP.get(content_type, content_type),
            stem=q.text,
            answer=_extract_answer(q),
            options=_extract_options(q),
            analysis=q.explanation,
            difficulty=_map_difficulty(q.difficulty),
            cognitive_node_ids=cognitive_node_ids or ([skill_id] if skill_id else None),
            source="llm",
            metadata={
                "bloom_level": bloom_enum.value,
                "hints": q.hints,
                "tags": q.tags,
                "subject": subject,
                "skill_id": skill_id,
                "source_detail": q.source,
            },
        )
        saved.append(v7_q)

    logger.info("AI 出题完成: bank=%s, count=%d, skill=%s", bank_id, len(saved), skill_id)
    return saved


async def handle_question_generation(
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    node_id: Optional[str] = None,
    conversation_context: Optional[list[dict]] = None,
) -> dict:
    """
    高阶入口：自然语言 → 意图提取 → 出题 → 自动归属 → 返回结果。

    支持三种归属方式（优先级）：
    1. bank_id 明确指定
    2. conversation_id 自动解析
    3. node_id 自动解析
    """
    _ensure_tables()

    # 1. 用 LLM 提取出题参数
    params = await _extract_generation_params(user_message, conversation_context)
    logger.info("意图提取结果: %s", params)

    subject = params.get("subject", "数学")
    skill_id = params.get("skill_id", params.get("subject", "数学"))
    bloom_level = params.get("bloom_level", "apply")
    difficulty = float(params.get("difficulty", 0.5))
    count = int(params.get("count", 3))
    content_type = params.get("content_type", "choice")

    # 2. 确定题库归属
    resolved_bank_id = bank_id
    if not resolved_bank_id and conversation_id:
        resolved_bank_id = resolve_bank_for_conversation(conversation_id, user_id)
    if not resolved_bank_id and node_id:
        resolved_bank_id = resolve_bank_for_node(node_id, user_id)
    if not resolved_bank_id:
        resolved_bank_id = resolve_bank_for_conversation("", user_id)  # 回退到默认题库

    # 3. 获取 subject 上下文 — 从题库关联的认知节点
    bank_info = get_bank(resolved_bank_id, user_id)
    if bank_info and bank_info.get("ref_node_id"):
        from app.cognitive.storage import get_node
        node = get_node(bank_info["ref_node_id"], user_id)
        if node and node.label:
            # 用知识点标签来增强出题质量
            pass

    # 4. 生成并保存
    saved = await generate_and_save(
        bank_id=resolved_bank_id,
        user_id=user_id,
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        cognitive_node_ids=[skill_id] if skill_id and skill_id != subject else None,
    )

    # 5. 返回友好结果
    bank = get_bank(resolved_bank_id, user_id)
    return {
        "bank_id": resolved_bank_id,
        "bank_name": bank["name"] if bank else "",
        "generated": len(saved),
        "questions": saved,
        "params": {
            "subject": subject,
            "skill_id": skill_id,
            "bloom_level": bloom_level,
            "difficulty": difficulty,
            "count": count,
            "content_type": content_type,
        },
    }


async def generate_for_conversation(
    conversation_id: str,
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    conversation_context: Optional[list[dict]] = None,
) -> dict:
    """对话场景下出题：自动解析对话 → 归属题库 → 生成"""
    bank_id = resolve_bank_for_conversation(conversation_id, user_id)
    return await handle_question_generation(
        user_message=user_message,
        user_id=user_id,
        bank_id=bank_id,
        conversation_id=conversation_id,
        conversation_context=conversation_context,
    )


# ── 内部辅助 ──


async def _extract_generation_params(
    user_message: str,
    context: Optional[list[dict]] = None,
) -> dict:
    """
    用 LLM 从自然语言中提取出题参数。

    返回:
        {"subject": "...", "skill_id": "...", "bloom_level": "...",
         "difficulty": 0.5, "count": 3, "content_type": "choice"}
    """
    system_prompt = """你是一个出题参数提取器。分析用户消息，提取练习题生成参数。

返回JSON格式（只返回JSON，不要其他文字）：
{
  "subject": "学科名称（如数学/物理/英语/语文）",
  "skill_id": "知识点ID/名称（如 calculus_limit / 极限 / 一元二次方程）",
  "bloom_level": "认知层次（remember/understand/apply/analyze/evaluate/create）",
  "difficulty": 0.5,
  "count": 3,
  "content_type": "题型（choice/fill/free_form/calculation）"
}

规则：
- subject 未指明时默认为"数学"
- bloom_level 未指明时默认为"apply"
- difficulty 范围0-1，未指明时0.5
- count 范围1-10，未指明时3
- content_type 未指明时默认为"choice"
- skill_id 尽量提取具体知识点名称"""

    messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.extend(context[-3:])
    messages.append({"role": "user", "content": user_message})

    try:
        result_text = await llm_service.generate(
            messages=messages,
            task_type="fast",
            temperature=0.1,
            max_tokens=300,
        )
        # 解析 JSON
        clean = result_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        params = json.loads(clean.strip())
        # 参数校验
        params.setdefault("subject", "数学")
        params.setdefault("bloom_level", "apply")
        params.setdefault("difficulty", 0.5)
        params.setdefault("count", 3)
        params.setdefault("content_type", "choice")
        params["count"] = max(1, min(10, int(params.get("count", 3))))
        params["difficulty"] = max(0.0, min(1.0, float(params.get("difficulty", 0.5))))
        return params
    except Exception as e:
        logger.warning("出题参数提取失败: %s，使用默认值", e)
        return {
            "subject": "数学",
            "skill_id": "",
            "bloom_level": "apply",
            "difficulty": 0.5,
            "count": 3,
            "content_type": "choice",
        }


def _extract_answer(q) -> list:
    """从 Question Pydantic 提取答案（统一为 list）"""
    if q.options:
        return [opt.letter for opt in q.options if opt.is_correct]
    if q.correct_answer:
        return [q.correct_answer]
    return []


def _extract_options(q) -> list[dict]:
    """从 Question Pydantic 提取 options"""
    if not q.options:
        return []
    return [
        {
            "letter": opt.letter,
            "text": opt.text,
            "is_correct": opt.is_correct,
            "distractor_type": opt.distractor_type,
        }
        for opt in q.options
    ]


def _map_difficulty(d: float) -> int:
    """
    v7 用 1-5 整数难度，QuestionGenerator 返回 0-1 float。
    映射: 0-0.2→1, 0.2-0.4→2, 0.4-0.6→3, 0.6-0.8→4, 0.8-1.0→5
    """
    if d <= 0.2:
        return 1
    if d <= 0.4:
        return 2
    if d <= 0.6:
        return 3
    if d <= 0.8:
        return 4
    return 5
