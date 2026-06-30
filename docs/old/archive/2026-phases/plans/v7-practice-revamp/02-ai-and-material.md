# AI 出题能力与自定义资料参考

> 基于已有 QuestionGenerator + Material/MaterialChunk 体系的增强方案。

---

## 1. 已有基础设施能力清单

### 1.1 QuestionGenerator（现有）

| 能力 | 说明 |
|------|------|
| LLM 生成 | 通过 `llm_service.chat()` 调用，支持任意模型 |
| 知识模板 | 预置 calculus/linear/probability/physics 等模板 |
| Bloom 层次 | REMEMBER → CREATE 六层 |
| 题型 | choice / fill / free_form / calculation |
| 难度控制 | 0~1 连续值 |
| 数量控制 | 任意 count |
| 资料上下文 | `material_context` 参数注入用户资料 |
| 缓存 | LLM 结果缓存到模板库 |
| Fallback | 生成失败时用 fallback 模板 |

### 1.2 Material / MaterialChunk（现有）

| 能力 | 说明 |
|------|------|
| 资料分块 | 上传文件自动分 chunk，每个 chunk 有 embedding |
| 知识点关联 | `skill_ids` 字段关联 CognitiveNode |
| 向量检索 | 可用 `vector_search()` 匹配资料 chunk |
| 题型标记 | `chunk_type`: text/question/solution/diagram/formula |

### 1.3 现有 Schema 中的关键字段

```python
class Question(BaseModel):
    source: str           # llm / manual / imported / material
    material_chunk_id: str | None  # 来自哪个资料 chunk
    skill_id: str         # 关联的知识点
    bloom_level: BloomLevel
    difficulty: float
    quality_score: float

class MaterialChunk(BaseModel):
    skill_ids: list[str]  # 关联的知识点列表
    embedding: list[float]
    chunk_type: str       # text/question/solution/diagram/formula

class ErrorBookEntry(BaseModel):
    referenced_materials: list[dict]  # 关联的参考资料
```

---

## 2. AI 出题能力增强

### 2.1 AI 出题 → 题库持久化

核心流程：AI 生成的题目直接存入 `questions` 表，与导入题同一模型。

```python
# backend/app/services/practice_ai_generator.py

"""
AI 出题 → questions 表持久化流程：

    ┌─────────────────┐
    │  手动出题请求     │  ← 用户选择知识点/频率/难度
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ QuestionGenerator │  ← 现有 LLM 引擎
    │ .generate()       │
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ 解析/验证 JSON   │  ← 校验字段完整性
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ 认知节点匹配     │  ← vector_search() 自动关联
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ 写入 questions 表 │  ← source = 'ai_generated'
    └─────────────────┘
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.db.database import get_db
from app.services.question_generator import QuestionGenerator
from app.services.practice_import_matcher import match_question_to_nodes
from app.config import settings

logger = logging.getLogger(__name__)


async def generate_and_save(
    bank_id: str,
    user_id: str,
    skill_id: str,
    subject: str,
    bloom_level: str = "apply",
    difficulty: float = 0.5,
    count: int = 3,
    content_type: str = "choice",
    material_context: Optional[str] = None,
    node_ids_for_matching: Optional[list[str]] = None,
) -> list[dict]:
    """
    用 LLM 生成题目，自动关联认知节点，持久化到 questions 表。

    返回已保存题目的 dict 列表。
    """
    from app.services.llm_service import llm_service
    generator = QuestionGenerator(llm_service)

    now = datetime.now().isoformat()

    # 1. 调用现有 LLM 生成引擎
    questions = generator.generate(
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
    )

    if not questions:
        logger.warning("AI 生成题目为空 (skill=%s)", skill_id)
        return []

    # 2. 逐题处理
    saved = []
    from app.db.database import get_db
    db = get_db()

    for q in questions:
        # 2a. 用题目内容 embedding 匹配认知节点
        matched = match_question_to_nodes(q.text, user_id, top_k=3)
        cognitive_ids = [m["id"] for m in matched if m["similarity"] > 0.35]

        # 2b. 生成唯一 ID
        question_id = f"aiq_{user_id}_{int(datetime.now().timestamp())}_{hash(q.text) % 10000}"

        # 2c. 构建选项 JSON
        options_json = []
        if q.options:
            for opt in q.options:
                options_json.append({
                    "label": opt.letter,
                    "content": opt.text,
                    "is_correct": opt.is_correct,
                    "distractor_type": opt.distractor_type,
                })

        # 2d. 答案格式
        answer = q.correct_answer
        if q.options:
            correct_labels = [o.letter for o in q.options if o.is_correct]
            answer = json.dumps(correct_labels)

        # 2e. 写入 questions 表
        try:
            db.execute(
                """INSERT INTO questions
                   (id, bank_id, user_id, question_type, stem, options, answer, analysis,
                    difficulty, cognitive_node_ids, source, metadata, status, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    question_id, bank_id, user_id,
                    content_type, q.text, json.dumps(options_json), answer,
                    q.explanation, q.difficulty,
                    cognitive_ids, "ai_generated",
                    json.dumps({
                        "bloom_level": bloom_level,
                        "subject": subject,
                        "skill_id": skill_id,
                        "hints": q.hints,
                        "material_context_used": bool(material_context),
                    }),
                    "active", now, now,
                ),
            )
            saved.append({
                "id": question_id,
                "stem": q.text[:80],
                "question_type": content_type,
                "difficulty": q.difficulty,
                "cognitive_node_ids": cognitive_ids,
                "explanation": q.explanation[:100],
            })
        except Exception as e:
            logger.error("保存 AI 题目失败: %s (question=%s)", e, q.text[:50])

    logger.info("AI 生成并保存了 %d 道题到题库 %s", len(saved), bank_id)
    return saved


async def bulk_generate(
    bank_id: str,
    user_id: str,
    plans: list[dict],
) -> list[dict]:
    """
    批量生成：一次调用生成多组知识点/多 Bloom 层次的题目。

    plans: [
        {"skill_id": "...", "subject": "...", "bloom_level": "apply", "count": 2, "difficulty": 0.5},
        {"skill_id": "...", "subject": "...", "bloom_level": "analyze", "count": 1, "difficulty": 0.7},
    ]
    """
    all_saved = []
    for plan in plans:
        saved = await generate_and_save(
            bank_id=bank_id,
            user_id=user_id,
            skill_id=plan["skill_id"],
            subject=plan.get("subject", ""),
            bloom_level=plan.get("bloom_level", "apply"),
            difficulty=plan.get("difficulty", 0.5),
            count=plan.get("count", 1),
            content_type=plan.get("content_type", "choice"),
            material_context=plan.get("material_context"),
        )
        all_saved.extend(saved)
    return all_saved
```

### 2.2 AI 出题的触发场景

| 场景 | 触发方式 | 说明 |
|------|---------|------|
| **手动出题** | 用户在前端选择知识点 + 难度 + 数量 | 直接调用 `generate_and_save()` |
| **自适应出题不够** | `adaptive_select()` 查不到足够题目时 | 自动触发 AI 生成补足 |
| **错题解析生成** | 练习后分析错题，AI 自动生成同类题 | 秘书提案附带同类题 |
| **考前冲刺** | 用户设考试目标，AI 按大纲批量组卷 | 配合秘书系统 |

```python
# 自适应出题的 AI 补足逻辑（在 adaptive_select 中增加）

async def adaptive_select_with_ai_fallback(
    bank_id: str, user_id: str, count: int, node_ids: list[str] | None = None
) -> list[dict]:
    """自适应选题 + 不足时 AI 补足"""
    selected = await adaptive_select(bank_id, user_id, count, node_ids)

    if len(selected) < count:
        shortage = count - len(selected)
        # 从薄弱节点中选一个批量出题补足
        if node_ids:
            target_id = node_ids[0]
        elif isinstance(selected, list) and len(selected) > 0:
            # 从已选题的认知节点中取一个
            cids = selected[0].get("cognitive_node_ids", [])
            target_id = cids[0] if cids else None
        else:
            target_id = None

        if target_id:
            ai_questions = await generate_and_save(
                bank_id=bank_id,
                user_id=user_id,
                skill_id=target_id,
                subject="",
                count=shortage,
            )
            selected.extend(ai_questions)

    return selected
```

### 2.3 AI 出题质量保障

```python
class AIQuestionQuality:
    """AI 出题质量保障机制"""

    @staticmethod
    def validate_question(data: dict) -> list[str]:
        """校验 AI 输出完整性，返回缺失字段列表"""
        errors = []
        if not data.get("stem"):
            errors.append("题干为空")
        if not data.get("correct_answer"):
            errors.append("答案为空")
        if data.get("question_type") in ("single", "multiple"):
            opts = data.get("options", [])
            if len(opts) < 2:
                errors.append("选项不足")
            correct_count = sum(1 for o in opts if o.get("is_correct"))
            if correct_count == 0:
                errors.append("无正确答案选项")
        return errors

    @staticmethod
    def score_quality(question: dict) -> float:
        """对题目质量评分 0~1，用于 quality_score 字段"""
        score = 0.5  # 基础分
        if question.get("explanation"):
            score += 0.15
        if question.get("hints") and len(question["hints"]) >= 2:
            score += 0.1
        if question.get("tags") and len(question["tags"]) >= 2:
            score += 0.05
        if question.get("cognitive_node_ids") and len(question["cognitive_node_ids"]) > 0:
            score += 0.1
        # 使用次数越多，置信度越高
        usage = question.get("usage_count", 0)
        score += min(0.1, usage * 0.01)
        return min(1.0, max(0.1, score))

    @staticmethod
    def mark_for_review(db, question_id: str, reason: str) -> None:
        """标记为待人工审核"""
        db.execute(
            "UPDATE questions SET status = 'under_review', metadata = metadata || %s WHERE id = %s",
            (json.dumps({"review_reason": reason}), question_id),
        )
```

---

## 3. 自定义资料参考能力

### 3.1 资料→出题：从资料自动生成练习

```python
# backend/app/services/practice_material_questions.py

"""
资料驱动的题目生成流程：

    用户上传资料
         │
         ▼
    MaterialChunk (含 embedding + skill_ids)
         │
         ▼
    match_question_to_nodes()  ← 资料 chunk → 认知节点
         │
         ▼
    AI 基于资料上下文出题     ← material_context 注入 chunk 原文
         │
         ▼
    写入 questions 表         ← material_chunk_id 记录来源
         │
         ▼
    前端: "基于你的资料生成了 5 道题"
"""


async def generate_questions_from_material(
    bank_id: str,
    user_id: str,
    material_id: str,
    count: int = 5,
) -> list[dict]:
    """
    基于用户上传的某份资料，生成练习题。

    流程：
    1. 检索该资料的 chunks
    2. 提取知识上下文（合并前 N 个 chunks）
    3. 调用 AI 出题引擎，注入资料上下文
    4. 存入题库，标记 source='material'
    """
    from app.db.database import get_db
    db = get_db()

    # 1. 获取资料信息
    material = db.fetchone(
        "SELECT * FROM material_meta WHERE material_id = %s AND user_id = %s",
        (material_id, user_id),
    )
    if not material:
        raise ValueError(f"资料不存在: {material_id}")

    # 2. 获取该资料的 chunks（从文件系统或数据库）
    # 假设 chunk 存在 app/services/material_indexer 中
    try:
        from app.services.material_indexer import get_material_chunks
        chunks = get_material_chunks(material_id, user_id)
    except ImportError:
        chunks = []

    # 3. 构建资料上下文
    context_parts = []
    skill_ids = set()
    for chunk in chunks[:10]:  # 取前 10 个 chunk
        if chunk.get("text"):
            context_parts.append(chunk["text"])
        for sid in chunk.get("skill_ids") or []:
            skill_ids.add(sid)

    material_context = "\n\n".join(context_parts)[:3000]

    # 4. 确定目标知识点
    target_skills = list(skill_ids) if skill_ids else [material.get("name", "general")]

    # 5. 生成题目
    from app.services.llm_service import llm_service
    generator = QuestionGenerator(llm_service)

    all_saved = []
    for skill_id in target_skills[:3]:  # 最多 3 个知识点
        questions = generator.generate(
            subject=material.get("file_type", "general"),
            skill_id=skill_id,
            count=max(1, count // len(target_skills[:3])),
            material_context=material_context,
        )
        for q in questions:
            saved = _save_ai_question(
                db, bank_id, user_id, q, material_id=material_id,
                context_preview=material_context[:200],
            )
            if saved:
                all_saved.append(saved)

    return all_saved


def _save_ai_question(
    db, bank_id: str, user_id: str, q,
    material_id: str | None = None,
    context_preview: str = "",
) -> dict | None:
    """将 AI 生成的 Question 对象写入 questions 表（内部工具函数）"""
    # ... (同 generate_and_save 的保存逻辑，额外写入 material_id)
    pass
```

### 3.2 错题→资料推荐

```python
# backend/app/services/practice_material_recommend.py

"""
错题关联资料推荐：

    学生答错某题
         │
         ▼
    题目关联了 cognitive_node_ids
         │
         ▼
    检索该节点的学习资料（memory_learning / material_meta）
         │
         ▼
    返回推荐资料列表
         │
         ▼
    前端显示: "推荐复习：你的笔记/上传资料中关于 [知识点] 的部分"
"""


async def recommend_materials_for_errors(
    user_id: str,
    error_question_ids: list[str],
    limit: int = 3,
) -> list[dict]:
    """
    根据错题关联的认知节点，推荐复习资料。
    综合检索两种来源：
    1. material_meta + chunks（用户上传的资料）
    2. learning_memory（AI 整理的笔记/摘要）
    """
    from app.db.database import get_db
    db = get_db()

    # 1. 收集错题涉及的认知节点
    placeholders = ", ".join(f"%s" for _ in error_question_ids)
    rows = db.fetchall(
        f"SELECT id, cognitive_node_ids, stem FROM questions "
        f"WHERE id IN ({placeholders}) AND user_id = %s",
        (*error_question_ids, user_id),
    )

    node_ids = set()
    for r in rows:
        for nid in r.get("cognitive_node_ids") or []:
            node_ids.add(nid)

    if not node_ids:
        return []

    node_list = list(node_ids)

    # 2. 查询资料中关联了这些节点的 chunks
    # 假设 material_chunks 表有 skill_ids 字段
    material_rows = db.fetchall(
        """SELECT DISTINCT m.material_id, m.file_name, m.file_type
           FROM material_meta m
           WHERE m.user_id = %s AND m.skills_covered && %s
           LIMIT %s""",
        (user_id, node_list, limit),
    )

    recommendations = []
    for r in material_rows:
        recommendations.append({
            "type": "material",
            "material_id": r["material_id"],
            "title": r["file_name"],
            "file_type": r["file_type"],
            "reason": "这份资料涉及你答错的知识点",
        })

    # 3. 查询 learning_memory 中的相关笔记
    try:
        from app.db.database import get_db as _db
        mem_rows = _db().fetchall(
            """SELECT id, title, content_preview FROM learning_memory
               WHERE user_id = %s AND cognitive_node_ids && %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, node_list, limit),
        )
        for r in mem_rows:
            recommendations.append({
                "type": "learning_memory",
                "memory_id": r["id"],
                "title": r["title"] or "学习笔记",
                "preview": (r.get("content_preview") or "")[:100],
                "reason": "这是你关于该知识点的学习记录",
            })
    except Exception:
        pass

    return recommendations
```

### 3.3 考试冲刺→资料组卷

```python
async def generate_exam_from_materials(
    bank_id: str,
    user_id: str,
    material_ids: list[str],
    question_counts: dict = None,
) -> dict:
    """
    基于指定的多份资料组成一张模拟卷。
    - 从每份资料中提取知识点
    - 按比例生成各章节题目
    - 生成完整试卷结构

    返回: { "session_id": ..., "questions": [...], "title": "..." }
    """
    if question_counts is None:
        question_counts = {"single": 15, "multiple": 5, "judge": 5}

    all_questions = []
    covered_skills = set()

    for mid in material_ids:
        qs = await generate_questions_from_material(
            bank_id, user_id, mid,
            count=sum(question_counts.values()) // len(material_ids),
        )
        all_questions.extend(qs)
        for q in qs:
            for nid in q.get("cognitive_node_ids", []):
                covered_skills.add(nid)

    # 创建考试 session
    session_id = f"exam_{user_id}_{int(datetime.now().timestamp())}"
    db = get_db()
    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            total_count, cognitive_node_ids, started_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            session_id, user_id, bank_id,
            "exam", "mixed",
            json.dumps({"source": "material_exam", "material_ids": material_ids}),
            len(all_questions), list(covered_skills),
            datetime.now().isoformat(),
        ),
    )

    return {
        "session_id": session_id,
        "title": "基于学习资料的模拟考试",
        "questions": all_questions,
        "total": len(all_questions),
        "covered_skills": len(covered_skills),
    }
```

---

## 4. AI 解析增强

### 4.1 AI 生成错题同类题

```python
async def generate_similar_question(
    bank_id: str,
    user_id: str,
    source_question_id: str,
    difficulty_shift: float = 0.0,
) -> dict | None:
    """
    根据某道错题，AI 生成一道同类但数值/情境不同的题目。
    用于错题复习中的"再做一道同类题"功能。

    流程：
    1. 获取原题内容 + 知识点
    2. 调用 LLM 生成变体（换数字、换场景、保留知识点）
    3. 存入题库，标记 source='ai_similar'
    4. 关联同一认知节点
    """
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND user_id = %s",
        (source_question_id, user_id),
    )
    if not row:
        return None

    from app.services.llm_service import llm_service

    prompt = f"""请根据以下题目，生成一道同知识点的变体题。
要求：
- 保持相同题型和知识点
- 更换具体数值或情境
- 保持难度大致相同
- 提供完整解析

原题：
{row['stem']}

答案：{row['answer']}

解析：{row.get('analysis', '')}
"""

    system = "你是一个擅长出题的教育专家。生成一道与原题知识点相同但具体内容不同的练习题。"

    response = llm_service.chat(system_prompt=system, user_prompt=prompt)

    # 解析并保存...
    # (与 generate_and_save 类似)
```

### 4.2 AI 解析与知识点讲解

```python
async def generate_explanation(question_id: str, user_id: str) -> dict:
    """
    对一道题生成深入讲解：不仅告诉你答案，还讲解知识原理。
    结果存入 explain_cards 表（复用现有解释卡片系统）。

    返回 explain_card 数据，前端可直接作为解释卡片展示。
    """
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND user_id = %s",
        (question_id, user_id),
    )
    if not row:
        return {"error": "题目不存在"}

    # 获取关联的认知节点信息
    node_labels = []
    for nid in row.get("cognitive_node_ids") or []:
        node = get_node(nid, user_id)
        if node:
            node_labels.append(node.label)

    from app.services.llm_service import llm_service

    prompt = f"""请深入讲解这道题涉及的知识原理：

题目：{row['stem']}

正确答案：{row['answer']}

解析：{row.get('analysis', '无')}

关联知识点：{', '.join(node_labels) if node_labels else '未知'}

请从以下方面讲解：
1. 这道题考的是什么知识点？
2. 解题的关键思路是什么？
3. 常见的错误理解有哪些？
4. 这个知识点在实际中怎么用？
"""

    system = "你是智能伴学 AI，用通俗易懂的语言讲解知识点，适合中学生理解。"
    explanation = llm_service.chat(system_prompt=system, user_prompt=prompt)

    return {
        "question_id": question_id,
        "explanation": explanation,
        "node_labels": node_labels,
        "suggested_actions": [
            {"type": "practice", "label": "再做一道同类题"},
            {"type": "explain", "label": "深入讲解这个知识点"},
        ],
    }
```

---

## 5. 整体数据流

### 5.1 题目来源与流向

```
                    ┌──────────────────┐
                    │   手动/批量出题    │  ← 用户指定知识点 + AI 生成
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │                  │
         ┌──────────┤   questions 表    ├──────────┐
         │          │                  │          │
         │          └────────┬─────────┘          │
         ▼                   ▼                    ▼
  ┌────────────┐    ┌──────────────┐    ┌──────────────┐
  │ 来源: import │    │ 来源: ai_gen  │    │ 来源: material│
  │ 导入题       │    │ AI 生成题     │    │ 资料生成题     │
  └────────────┘    └──────────────┘    └──────────────┘
         │                   │                    │
         └───────────────────┼────────────────────┘
                             ▼
                    ┌──────────────────┐
                    │  adaptive_select() │  ← 所有题目统一按掌握度调度
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │    练习/考试      │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ 认知模型更新      │  ← 反馈闭环
                    └──────────────────┘
```

### 5.2 错题→资料→AI 出题闭环

```
    学生答错
        │
        ▼
   cognitive_node_ids   ───→  recommend_materials_for_errors()
        │                              │
        │                              ▼
        │                   错题关联资料展示
        │                              │
        ▼                              ▼
  generate_similar_question()    generate_questions_from_material()
        │                              │
        └──────────┬───────────────────┘
                   ▼
          同类题/资料衍生题存入题库
                   │
                   ▼
            自适应出题中被再次选中
```

---

## 6. 新增 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/practice/questions/generate` | POST | AI 生成题目并存入题库 |
| `/api/practice/questions/generate-bulk` | POST | 批量生成（多知识点） |
| `/api/practice/questions/generate-from-material` | POST | 基于资料生成 |
| `/api/practice/questions/similar` | POST | 生成同类题变体 |
| `/api/practice/questions/explain` | POST | AI 深入讲解某题 |
| `/api/practice/errors/materials` | GET | 错题关联资料推荐 |
| `/api/practice/exam/from-materials` | POST | 基于多份资料组卷 |

---

## 7. 与 v7.0 主方案的集成

本方案扩展了 `01-design-proposal.md` 中以下部分：

| 原方案章节 | 增强内容 |
|-----------|---------|
| 3.1 自适应出题 | `adaptive_select_with_ai_fallback()` 不足时 AI 补足 |
| 3.2 练习模式 | 新增"基于资料练习"模式 |
| 3.3 考试模式 | `generate_exam_from_materials()` 资料组卷 |
| 3.4 错题本 | 错题关联资料推荐 + AI 生成同类题 |
| 6.0 题库导入 | 新增 AI 自动出题 + 资料衍生出题作为"非导入"来源 |
| 8.0 路线图 | 详见下方新增阶段 |

### 实施路线图补充

| 阶段 | 新增内容 |
|------|---------|
| 7.0.1 | AI 出题 API (`generate_and_save`) + 资料→认知节点匹配 |
| 7.0.2 | AI 出题作为自适应选题的 fallback |
| 7.0.3 | 资料组卷 (`generate_exam_from_materials`) |
| 7.0.4 | 错题同类题生成 (`generate_similar_question`) |
| 7.0.5 | 错题资料推荐 (`recommend_materials_for_errors`) |
| 7.0.6 | AI 深入讲解 (`generate_explanation` → 解释卡片联动) |
