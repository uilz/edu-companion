"""
AI 出题核心 — generate_and_save + handle_question_generation

流程：
1. handle_question_generation() 解析自然语言 → 提取参数（subject/skill/bloom/difficulty/count）
2. generate_and_save()  → 调用 QuestionGenerator → 转标准格式 → save → 返回
3. generate_for_conversation() → 结合对话上下文 → 生成 + 自动归属题库

格式化/校验逻辑委托给 question_formatter.py 中的纯函数。
"""

import json
import logging
from typing import Optional

from app.infrastructure.llm.llm_service import llm_service
from app.infrastructure.llm.question_generator import QuestionGenerator, get_question_generator
from app.services.practice.practice_question_crud import add_question
from app.services.practice.practice_question_bank import (
    _ensure_tables, resolve_bank_for_conversation, resolve_bank_for_node, get_bank,
)
from app.services.practice.question_formatter import (
    parse_bloom_level,
    parse_content_type,
    extract_answer,
    extract_options,
    map_difficulty,
    validate_question,
    score_quality,
    BLOOM_ZH_MAP,
    CONTENT_TYPE_MAP,
)
from app.schemas.practice import BloomLevel, AnswerType

logger = logging.getLogger(__name__)


# ── 核心函数 ──


async def generate_and_save(
    bank_id: str,
    user_id: str,
    subject: str = "数学",
    skill_id: str = "",
    bloom_level: str = "apply",
    difficulty: float = 0.5,
    count: int = 3,
    content_type: str = "choice",
    material_context: Optional[str] = None,
    material_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
    reference_mode: Optional[str] = None,
) -> list[dict]:
    """
    AI 出题并保存到题库。

    reference_mode: 参考资料模式
        - "inspiration" (灵感参考): 资料仅供启发，可自由拓展
        - "reference" (一般参考): 题目与资料相关但不完全限制
        - "strict" (严格参照): 题目必须完全基于资料内容
    """
    _ensure_tables()

    # 解析 Bloom 级别
    bloom_enum = BLOOM_ZH_MAP.get(bloom_level.lower(), BloomLevel.APPLY) if isinstance(bloom_level, str) else bloom_level

    # 获取 QuestionGenerator（同步构造，但 generate 本身是同步的）
    gen = get_question_generator(llm_service)
    if not gen:
        gen = QuestionGenerator(llm_service)

    # 直接调用 async generate
    questions = await gen.generate(
        subject=subject,
        skill_id=skill_id or subject,
        bloom_level=bloom_enum,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
        reference_mode=reference_mode,
    )

    if not questions:
        logger.warning("AI 出题生成 0 道题目")
        return []

    # 转标准格式并保存
    saved = []
    for q in questions:
        saved_q = add_question(
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
        # 记录资料-题目关联（R2-4）
        if material_ids and saved_q and saved_q.get("id"):
            _record_material_question(material_ids, saved_q["id"], user_id)
        saved.append(saved_q)

    logger.info("AI 出题完成: bank=%s, count=%d, skill=%s", bank_id, len(saved), skill_id)
    return saved


async def get_material_context(
    material_ids: list[str] | None,
    user_id: str,
    max_chunks: int = 10,
) -> str | None:
    """从已上传资料中检索内容块，拼接为出题上下文字符串。

    流程：
    1. 按 material_ids 从 material_chunks 表拉取文本
    2. 拼接为 ``--- 资料：文件名\n内容`` 格式
    3. 截断最多 max_chunks 个块
    """
    if not material_ids:
        return None

    from app.infrastructure.db.database import get_db
    db = get_db()

    placeholders = ",".join(["%s"] * len(material_ids))
    rows = db.fetchall(
        f"""SELECT mc.text, mc.material_id, m.file_name as material_name
            FROM material_chunks mc
            JOIN materials m ON mc.material_id = m.material_id
            WHERE mc.material_id IN ({placeholders})
              AND mc.user_id = %s
              AND m.status = 'indexed'
            ORDER BY mc.chunk_index
            LIMIT %s""",
        tuple(material_ids) + (user_id, max_chunks),
    )

    if not rows:
        return None

    parts = []
    for r in rows:
        text = (r["text"] or "")[:2000]
        name = r.get("material_name", "未知资料")
        parts.append(f"--- 资料：{name}\n{text}")

    return "\n\n".join(parts)


async def handle_question_generation(
    user_message: str,
    user_id: str,
    bank_id: Optional[str] = None,
    bank_name: Optional[str] = None,
    conv_id: Optional[str] = None,
    node_id: Optional[str] = None,
    conversation_context: Optional[list[dict]] = None,
    material_ids: Optional[list[str]] = None,
    reference_mode: Optional[str] = None,
) -> dict:
    """
    高阶入口：自然语言 → 意图提取 → 出题 → 自动归属 → 返回结果。

    支持三种归属方式（优先级）：
    1. bank_id 明确指定
    2. bank_name 按名称查找或创建
    3. conv_id 自动解析
    4. node_id 自动解析

    支持指定参考资料出题（material_ids）：
    从已上传资料中提取内容块，注入到 AI 出题的 material_context 中。
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

    # 2. 确定题库归属（按优先级）
    resolved_bank_id = bank_id
    if not resolved_bank_id and bank_name:
        # 按名称查找或创建
        from app.services.practice.practice_question_bank import list_banks, create_bank
        existing = [b for b in list_banks(user_id) if b.get("name") == bank_name]
        if existing:
            resolved_bank_id = existing[0]["id"]
            logger.info("按名称找到现有题库: %s (%s)", bank_name, resolved_bank_id)
        else:
            new_bank = create_bank(
                user_id=user_id,
                name=bank_name,
                description=f"AI自动创建的题库: {bank_name}",
                auto_created=True,
            )
            if new_bank:
                resolved_bank_id = new_bank["id"]
                logger.info("按名称创建新题库: %s (%s)", bank_name, resolved_bank_id)
    if not resolved_bank_id and conv_id:
        resolved_bank_id = resolve_bank_for_conversation(conv_id, user_id)
    if not resolved_bank_id and node_id:
        resolved_bank_id = resolve_bank_for_node(node_id, user_id)
    if not resolved_bank_id:
        resolved_bank_id = resolve_bank_for_conversation("", user_id)  # 回退到默认题库

    # 3. 获取 subject 上下文 — 从题库关联的认知节点（增强出题）
    bank_info = get_bank(resolved_bank_id, user_id)

    # 4. 获取参考资料上下文（新增）
    material_context = None
    if material_ids or (bank_info and bank_info.get("ref_material_ids")):
        ids = material_ids or (bank_info.get("ref_material_ids") or [])
        material_context = await get_material_context(ids, user_id)
        if material_context:
            logger.info("注入参考资料上下文: %d 个资料, %d 字符", len(ids), len(material_context))

    # 5. 生成并保存（注入 material_context + reference_mode）
    saved = await generate_and_save(
        bank_id=resolved_bank_id,
        user_id=user_id,
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
        cognitive_node_ids=[skill_id] if skill_id and skill_id != subject else None,
        reference_mode=reference_mode,
    )

    # 6. 返回友好结果
    bank = get_bank(resolved_bank_id, user_id)
    return {
        "bank_id": resolved_bank_id,
        "bank_name": bank["name"] if bank else "",
        "generated": len(saved),
        "questions": saved,
        "has_material_context": material_context is not None,
        "params": {
            "subject": subject,
            "skill_id": skill_id,
            "bloom_level": bloom_level,
            "difficulty": difficulty,
            "count": count,
            "content_type": content_type,
        },
    }


async def generate_from_materials_request(
    body: dict,
    user_id: str,
) -> dict:
    """基于指定资料出题的请求级入口：参数归一化 → 题库解析 → 资料上下文 → 生成 → 响应组装。"""
    _ensure_tables()

    material_ids = body.get("material_ids", [])
    subject = body.get("subject", "通用")
    skill_id = body.get("skill_id", subject)
    bloom_level = body.get("bloom_level", "apply")
    difficulty = float(body.get("difficulty", 0.5))
    count = max(1, min(10, int(body.get("count", 5))))
    content_type = body.get("content_type", "choice")
    bank_id = body.get("bank_id")
    reference_mode = body.get("reference_mode", "reference")

    if not bank_id:
        bank_id = resolve_bank_for_conversation(
            f"materials_{hash(str(material_ids))}", user_id
        )

    material_context = None
    if material_ids:
        material_context = await get_material_context(material_ids, user_id)

    saved = await generate_and_save(
        bank_id=bank_id,
        user_id=user_id,
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
        reference_mode=reference_mode,
    )

    bank = get_bank(bank_id, user_id)
    return {
        "bank_id": bank_id,
        "bank_name": bank["name"] if bank else "",
        "generated": len(saved),
        "questions": saved,
        "has_material_context": material_context is not None,
        "material_count": len(material_ids),
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
    conv_id: str,
    user_message: str,
    user_id: str,
    conversation_context: Optional[list[dict]] = None,
    material_ids: Optional[list[str]] = None,
    reference_mode: Optional[str] = None,
) -> dict:
    """对话场景下出题：自动解析对话 → 归属题库 → 生成"""
    bank_id = resolve_bank_for_conversation(conv_id, user_id)
    return await handle_question_generation(
        user_message=user_message,
        user_id=user_id,
        bank_id=bank_id,
        conv_id=conv_id,
        conversation_context=conversation_context,
        material_ids=material_ids,
        reference_mode=reference_mode,
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


# ── (validate_question / score_quality 已移至 question_formatter.py) ──


# ── 批量出题 ──


async def bulk_generate(
    bank_id: str,
    plans: list[dict],
    user_id: str,
    material_ids: Optional[list[str]] = None,
) -> dict:
    """
    批量出题：一次调用生成多组不同知识点/不同 Bloom 层次的题目。

    plans:
        [
            {"skill_id": "...", "subject": "...", "bloom_level": "apply", "count": 2, "difficulty": 0.5, "content_type": "choice"},
            {"skill_id": "...", "subject": "...", "bloom_level": "analyze", "count": 1, "difficulty": 0.7},
        ]
    """
    if not plans:
        return {"generated": 0, "questions": [], "errors": []}

    # 获取参考资料上下文（所有 plan 共用）
    material_context = None
    if material_ids:
        material_context = await get_material_context(material_ids, user_id)

    all_questions = []
    all_errors = []

    for i, plan in enumerate(plans):
        try:
            skill_id = plan.get("skill_id", "").strip()
            if not skill_id:
                all_errors.append({"plan_index": i, "reason": "skill_id 为空"})
                continue

            saved = await generate_and_save(
                bank_id=bank_id,
                user_id=user_id,
                subject=plan.get("subject", "通用"),
                skill_id=skill_id,
                bloom_level=plan.get("bloom_level", "apply"),
                difficulty=float(plan.get("difficulty", 0.5)),
                count=max(1, min(5, int(plan.get("count", 1)))),
                content_type=plan.get("content_type", "choice"),
                material_context=material_context,
            )
            all_questions.extend(saved)

            # 质量校验
            for q in saved:
                errors = validate_question(q)
                if errors:
                    logger.info("质量校验警告: skill=%s, errors=%s", skill_id, errors)

        except Exception as e:
            logger.warning("批量出题第 %d 组失败: %s", i, e)
            all_errors.append({"plan_index": i, "reason": str(e)})

    return {
        "generated": len(all_questions),
        "questions": all_questions,
        "errors": all_errors,
        "bank_id": bank_id,
        "plan_count": len(plans),
    }


# ── 同类变体 ──


async def generate_similar(
    question_id: str,
    user_id: str,
    count: int = 3,
) -> list[dict]:
    """
    基于已有题目生成同类变体。

    流程:
    1. 从 questions 获取原题
    2. 用 LLM 生成相似但不同的题目（同知识点、同难度、不同问法）
    3. 保存到同一题库
    """
    from app.infrastructure.db.database import get_db
    from app.infrastructure.llm.question_generator import QuestionGenerator
    db = get_db()

    # 1. 获取原题
    row = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not row:
        logger.warning("题目不存在: %s", question_id)
        return []

    stem = row["stem"]
    bank_id = row["bank_id"]
    qtype = row["question_type"]
    difficulty = row.get("difficulty", 3)
    node_ids = row.get("cognitive_node_ids") or []
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    # 2. 构建 prompt：让 LLM 生成同类题
    gen = get_question_generator(llm_service)
    if not gen:
        gen = QuestionGenerator(llm_service)

    prompt = (
        f"参考以下题目，生成 {count} 道同知识点、同难度、但不同问法的同类变体题。\n\n"
        f"原题：{stem[:300]}\n"
        f"知识点：{', '.join(node_ids[:3]) if node_ids else '通用'}\n"
        f"难度：{difficulty}/5\n"
        f"题型：{qtype}\n\n"
        f"要求：\n"
        f"1. 覆盖相同的知识点\n"
        f"2. 难度保持一致\n"
        f"3. 问法不同，不能与原题相同或过于相似\n"
        f"4. 如果是选择题，打乱正确选项位置\n"
    )

    try:
        questions = await gen.generate(
            subject=metadata.get("subject", "通用"),
            skill_id=node_ids[0] if node_ids else "通用",
            bloom_level=metadata.get("bloom_level", "apply"),
            difficulty=difficulty / 5.0,
            count=count,
            content_type=qtype,
            material_context=prompt,
        )
    except Exception as e:
        logger.warning("同类变体生成失败: %s", e)
        return []

    if not questions:
        return []

    # 3. 保存到同一题库
    saved = []
    for q in questions:
        saved_q = add_question(
            bank_id=bank_id,
            user_id=user_id,
            question_type=CONTENT_TYPE_MAP.get(qtype, qtype),
            stem=q.text,
            answer=_extract_answer(q),
            options=_extract_options(q),
            analysis=q.explanation,
            difficulty=difficulty,
            cognitive_node_ids=node_ids if node_ids else None,
            source="llm",
            metadata={
                "bloom_level": metadata.get("bloom_level", "apply"),
                "hints": q.hints,
                "tags": q.tags,
                "subject": metadata.get("subject", "通用"),
                "skill_id": node_ids[0] if node_ids else "",
                "is_variant_of": question_id,
                "source_detail": q.source,
            },
        )
        saved.append(saved_q)

    logger.info("同类变体: original=%s, generated=%d", question_id, len(saved))
    return saved


# ── 错题→相似题变体 (ADR 0011 Q7) ──


async def generate_similar_from_error(
    attempt_id: str,
    user_id: str,
    count: int = 3,
) -> list[dict]:
    """
    基于错题 attempt 的错因分析定向生成变体 (ADR 0011 Q7)。

    流程:
    1. 从 practice_attempts 获取 attempt 记录
    2. 读取 error_analysis 中的 error_type
    3. 根据错因类型定制 prompt:
       - "概念混淆" → 生成概念辨析题
       - "计算失误" → 生成同类计算但简单数值
       - "审题不清" → 生成更清晰分步题
    4. 保存到原题所在题库
    """
    from app.infrastructure.db.database import get_db
    from app.infrastructure.llm.question_generator import QuestionGenerator
    db = get_db()

    # 1. 获取 attempt 记录
    attempt = db.fetchone(
        "SELECT * FROM practice_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not attempt:
        logger.warning("Attempt 不存在: %s", attempt_id)
        return []

    question_id = attempt["question_id"]
    user_answer = attempt.get("user_answer") or []
    if isinstance(user_answer, str):
        try:
            user_answer = json.loads(user_answer)
        except Exception:
            user_answer = [user_answer]

    # 2. 获取原题
    question = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not question:
        logger.warning("原题不存在: %s", question_id)
        return []

    stem = question["stem"]
    bank_id = question["bank_id"]
    qtype = question["question_type"]
    difficulty = question.get("difficulty", 3)
    node_ids = question.get("cognitive_node_ids") or []
    metadata = question.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    # 3. 读取错因分析
    error_analysis = attempt.get("error_analysis") or {}
    if isinstance(error_analysis, str):
        try:
            error_analysis = json.loads(error_analysis)
        except Exception:
            error_analysis = {}
    error_type = error_analysis.get("error_type", error_analysis.get("distractor_type", "unknown"))
    error_pattern = attempt.get("error_pattern", "")

    # 4. 根据错因类型定制 prompt
    error_prompts = {
        "conceptual": "这道题涉及概念混淆。请生成概念辨析题，帮助区分易混淆的概念。",
        "concept_confusion": "这道题涉及概念混淆。请生成概念辨析题，帮助区分易混淆的概念。",
        "procedural": "这道题是解题步骤错误。请生成同类但步骤更清晰的题，附带分步提示。",
        "computation": "这道题是计算失误。请生成同类计算题，但使用更简单的数值，帮助练习计算准确度。",
        "calculation_error": "这道题是计算失误。请生成同类计算题，但使用更简单的数值，帮助练习计算准确度。",
        "sign_error": "这道题是符号错误。请生成同类题，重点练习符号处理。",
        "reading": "这道题是审题不清。请生成结构更清晰、步骤更明确的题。",
        "careless": "这道题是粗心大意。请生成同类题，题面加入关键提示，帮助养成仔细审题的习惯。",
    }

    error_hint = error_prompts.get(
        error_type,
        error_prompts.get(
            error_pattern,
            f"这道题答错了（错因: {error_type or error_pattern or '未知'}）。请生成同类题帮助巩固。",
        ),
    )

    # 5. 构建 prompt
    prompt = (
        f"参考以下错题，生成 {count} 道针对性变体题。\n\n"
        f"原题：{stem[:300]}\n"
        f"知识点：{', '.join(node_ids[:3]) if node_ids else '通用'}\n"
        f"难度：{difficulty}/5\n"
        f"题型：{qtype}\n"
        f"学生错因：{error_hint}\n\n"
        f"要求：\n"
        f"1. 覆盖相同的知识点\n"
        f"2. 难度保持一致或略低\n"
        f"3. 针对错因类型设计，帮助学生纠正错误\n"
    )

    gen = get_question_generator(llm_service)
    if not gen:
        gen = QuestionGenerator(llm_service)

    try:
        questions = await gen.generate(
            subject=metadata.get("subject", "通用"),
            skill_id=node_ids[0] if node_ids else "通用",
            bloom_level=metadata.get("bloom_level", "apply"),
            difficulty=difficulty / 5.0,
            count=count,
            content_type=qtype,
            material_context=prompt,
        )
    except Exception as e:
        logger.warning("错题变体生成失败: %s", e)
        return []

    if not questions:
        return []

    # 6. 保存到同一题库
    saved = []
    for q in questions:
        saved_q = add_question(
            bank_id=bank_id,
            user_id=user_id,
            question_type=CONTENT_TYPE_MAP.get(qtype, qtype),
            stem=q.text,
            answer=_extract_answer(q),
            options=_extract_options(q),
            analysis=q.explanation,
            difficulty=difficulty,
            cognitive_node_ids=node_ids if node_ids else None,
            source="llm",
            metadata={
                "bloom_level": metadata.get("bloom_level", "apply"),
                "hints": q.hints,
                "tags": q.tags,
                "subject": metadata.get("subject", "通用"),
                "skill_id": node_ids[0] if node_ids else "",
                "is_error_variant_of": question_id,
                "error_type": error_type,
                "source_detail": q.source,
            },
        )
        saved.append(saved_q)

    logger.info("错题变体: attempt=%s, error_type=%s, generated=%d", attempt_id, error_type, len(saved))
    return saved


# ── AI 深入讲解 ──


async def explain_question(
    question_id: str,
    user_id: str,
    style: str = "detailed",
) -> dict:
    """
    AI 深入讲解某道题。

    参数:
        question_id: 题目 ID
        style: "detailed" | "simple" | "step_by_step" | "analogy"

    返回:
        { question, explanation, key_points, related_concepts, examples }
    """
    from app.infrastructure.db.database import get_db
    from app.infrastructure.llm.llm_service import llm_service as llm
    db = get_db()

    row = db.fetchone(
        """SELECT q.*, b.name as bank_name
           FROM questions q
           LEFT JOIN question_banks b ON q.bank_id = b.id
           WHERE q.id = %s""",
        (question_id,),
    )
    if not row:
        return {"error": "题目不存在"}

    stem = row["stem"]
    options = row.get("options") or []
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            options = []
    answer = row.get("answer") or []
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except Exception:
            answer = [answer]
    analysis = row.get("explanation", "") or row.get("analysis", "")
    node_ids = row.get("cognitive_node_ids") or []

    # 获取知识点标签
    node_labels = []
    for nid in node_ids[:3]:
        try:
            from app.domain.cognitive import get_repo
            node = get_repo().get_node(nid, user_id)
            if node and node.label:
                node_labels.append(node.label)
        except Exception:
            pass

    style_prompts = {
        "simple": "用最简单的语言，给初学者解释这道题。",
        "detailed": "深入讲解这道题，包括概念、原理、常见错误。",
        "step_by_step": "分步骤讲解解题过程，每一步都说明原因。",
        "analogy": "用生活中的类比来帮助理解这道题的知识点。",
    }

    prompt = f"""请{style_prompts.get(style, style_prompts["detailed"])}

题目：{stem[:500]}
"""
    if options:
        opt_text = "\n".join(
            f"{o.get('letter', '')}. {o.get('text', o.get('content', ''))}"
            for o in (options if isinstance(options, list) else [])
        )
        prompt += f"选项：\n{opt_text}\n"
    if analysis:
        prompt += f"已知解析：{analysis[:500]}\n"

    prompt += f"""
请用 JSON 格式回答：
{{
    "key_points": ["核心概念1", "核心概念2"],       // 2-4个
    "explanation": "详细讲解文本（300-800字）",
    "common_mistakes": ["常见错误1", "常见错误2"],    // 1-3个
    "learning_tips": ["学习建议1", "学习建议2"],       // 1-2个
    "related_concepts": ["相关概念1", "相关概念2"]    // 1-3个
}}"""

    try:
        result_text = await llm.generate(
            messages=[
                {"role": "system", "content": "你是一个耐心、擅长讲解的 AI 导师，能用清晰的语言解释复杂的知识点。"},
                {"role": "user", "content": prompt},
            ],
            task_type="chat",
            temperature=0.3,
            max_tokens=2000,
        )

        clean = result_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        explanation_data = json.loads(clean.strip())
    except Exception as e:
        logger.warning("AI 讲解生成失败: %s", e)
        explanation_data = {
            "explanation": analysis[:500] if analysis else "无法生成讲解",
            "key_points": [],
            "common_mistakes": [],
            "learning_tips": [],
            "related_concepts": [],
        }

    return {
        "question_id": question_id,
        "stem": stem[:200],
        "answer": answer,
        "explanation": analysis,
        "node_labels": node_labels,
        "style": style,
        **explanation_data,
    }


def _extract_answer(q) -> list:
    """从 Question Pydantic 提取答案（统一为 list）— 委托给 formatter"""
    return extract_answer(q)


def _extract_options(q) -> list[dict]:
    """从 Question Pydantic 提取 options — 委托给 formatter"""
    return extract_options(q)


def _map_difficulty(d: float) -> int:
    """难度映射 0~1 → 1~5 — 委托给 formatter"""
    return map_difficulty(d)


def _record_material_question(material_ids: list[str], question_id: str, user_id: str) -> None:
    """记录资料-题目关联（R2-4）"""
    from app.infrastructure.db.database import get_db
    try:
        db = get_db()
        rows = db.fetchall(
            "SELECT material_id FROM materials WHERE material_id = ANY(%s) AND user_id = %s",
            (material_ids, user_id),
        )
        for r in rows:
            db.execute(
                "INSERT INTO practice_material_questions (material_id, question_id, user_id, created_at) "
                "VALUES (%s, %s, %s, NOW()) ON CONFLICT DO NOTHING",
                (r["material_id"], question_id, user_id),
            )
        logger.debug("关联资料-题目: q=%s, materials=%d", question_id, len(rows))
    except Exception as e:
        logger.warning("资料-题目关联失败（不影响出题）: %s", e)
