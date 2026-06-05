"""
题库导入服务 — docx/xlsx/txt/json 多格式解析

流程:
1. upload → 上传文件 + 解析为结构化题目列表
2. preview → AI 修正 + 认知节点匹配（返回预览）
3. confirm → 确认导入 v7_questions 表
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# ── 正则模式 ──

QUESTION_NUM_PATTERNS = [
    re.compile(r'^(\d+)[.、）\)]\s*(.*)'),
    re.compile(r'^（(\d+)）\s*(.*)'),
    re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*(.*)'),
]

OPTION_PATTERNS = [
    re.compile(r'^([A-Da-d])[.、）\)]\s*(.*)'),
    re.compile(r'^（([A-Da-d])）\s*(.*)'),
]

ANSWER_MARKERS = ['答案', '正确答案', '【答案】', '参考答案', '答：']
ANALYSIS_MARKERS = ['解析', '【解析】', '答案解析', '解析：']

# 题型推断
TYPE_KEYWORDS = {
    "单选": "single",
    "single": "single",
    "多选": "multiple",
    "multiple": "multiple",
    "判断": "judge",
    "judge": "judge",
    "填空": "fill",
    "fill": "fill",
    "简答": "essay",
    "essay": "essay",
}


def parse_questions_from_text(text: str, source: str = "text") -> list[dict]:
    """
    从纯文本中解析出题目列表。

    返回:
        [{ stem, options[{label, content}], answer, analysis,
           question_type, confidence, source_line }]
    """
    lines = text.strip().split("\n")
    blocks = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        btype = _infer_line_type(line)
        blocks.append({"text": line, "type": btype, "line": i + 1})

    return _structure_questions(blocks)


def parse_questions_from_json(json_text: str) -> list[dict]:
    """从 JSON 格式解析题目列表"""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")

    if isinstance(data, dict):
        data = data.get("questions", data.get("items", [data]))
    if not isinstance(data, list):
        raise ValueError("JSON 应为题目数组或包含 questions 字段的对象")

    results = []
    for item in data:
        q = {
            "stem": item.get("stem", item.get("question", "")),
            "options": _normalize_options(item.get("options", [])),
            "answer": item.get("answer", item.get("correct_answer", "")),
            "analysis": item.get("analysis", item.get("explanation", "")),
            "question_type": _infer_type(item),
            "confidence": 0.9,
            "source_line": 0,
        }
        results.append(q)
    return results


def parse_file(file_path: str, file_type: str = "") -> list[dict]:
    """解析文件为题目列表"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = (file_type or path.suffix).lower()

    if ext == ".json":
        return parse_questions_from_json(path.read_text(encoding="utf-8"))

    if ext == ".txt":
        return parse_questions_from_text(path.read_text(encoding="utf-8"))

    if ext in (".docx", ".xlsx", ".pptx", ".pdf"):
        # 用 MarkItDown 转文本再解析
        try:
            from app.services.materials.material_parser import material_parser
            md_text = material_parser.parse(str(path), ext)
            if md_text.strip():
                return parse_questions_from_text(md_text, ext)
        except Exception as e:
            logger.warning("MarkItDown 解析失败 %s: %s", file_path, e)

        # fallback: 直接尝试原始解析
        if ext == ".docx":
            return _parse_docx_fallback(str(path))
        raise ValueError(f"无法解析文件: {path.name}")

    raise ValueError(f"不支持的文件格式: {ext}")


def ai_correct_question(q: dict) -> dict:
    """用 AI 修正低置信度题目的解析结果"""
    if q.get("confidence", 1.0) >= 0.8:
        return q

    try:
        from app.services.llm.llm_service import llm_service
    except ImportError:
        return q

    opts_str = "; ".join(
        f"{o['label']}. {o['content']}" for o in (q.get("options") or [])
    ) if q.get("options") else "无选项"

    prompt = f"""修正以下从文档中提取的题目，返回纯净 JSON（不要 markdown 代码块）：

当前解析：
- 题干：{q.get('stem', '')[:300]}
- 选项：{opts_str[:300]}
- 答案：{q.get('answer', '')}
- 解析：{q.get('analysis', '')[:200]}

返回 JSON 格式：
{{
  "stem": "修正后的题干",
  "question_type": "single|multiple|judge|fill|essay",
  "options": [{{"label": "A", "content": "选项内容", "is_correct": false}}],
  "answer": "A" 或 ["A"],  
  "analysis": "解析",
  "correction_notes": "修正了什么"
}}"""

    try:
        from app.services.llm.llm_service import llm_service as llm
        result = llm.generate(
            messages=[
                {"role": "system", "content": "你是一个文档解析专家，擅长从非结构化文本中提取和修正练习题。"},
                {"role": "user", "content": prompt},
            ],
            task_type="fast",
            temperature=0.1,
            max_tokens=1000,
        )

        # 解析 JSON
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        corrected = json.loads(clean.strip())

        # 合并到原题
        if corrected.get("stem"):
            q["stem"] = corrected["stem"]
        if corrected.get("question_type"):
            q["question_type"] = corrected["question_type"]
        if corrected.get("options"):
            q["options"] = corrected["options"]
        if corrected.get("answer"):
            q["answer"] = corrected["answer"]
        if corrected.get("analysis"):
            q["analysis"] = corrected["analysis"]
        q["confidence"] = 0.95
        q["ai_corrected"] = True

    except Exception as e:
        logger.debug("AI 修正失败: %s", e)

    return q


def match_cognitive_nodes(q: dict, user_id: str = DEFAULT_USER_ID, top_k: int = 3) -> list[str]:
    """将题目内容匹配到认知节点"""
    try:
        from app.services.common.classifier import compute_embedding
        from app.db.database import get_db
        db = get_db()

        text = f"{q.get('stem', '')} {q.get('analysis', '')}"[:1000]
        embedding = compute_embedding(text)
        if not embedding:
            return []

        # 降级：用关键词匹配知识点标签
        keywords = re.findall(r'[\u4e00-\u9fff\w]{2,}', q.get("stem", ""))
        if not keywords:
            return []

        from app.cognitive.storage import search_nodes
        nodes = search_nodes(
            user_id=user_id,
            query=" ".join(keywords[:10]),
            limit=top_k,
        )
        return [n.id for n in nodes if hasattr(n, 'id')] or []

    except Exception as e:
        logger.debug("认知节点匹配失败: %s", e)
        return []


def preview_import(
    file_path: str,
    file_type: str = "",
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
) -> dict:
    """
    解析文件 → 预览（含 AI 修正 + 认知节点匹配）

    返回:
        { questions: [...], stats: {total, high_conf, low_conf}, suggestions: {...} }
    """
    questions = parse_file(file_path, file_type)

    # AI 修正 + 认知节点匹配
    total = len(questions)
    high_conf = 0
    low_conf = 0

    for q in questions:
        q = ai_correct_question(q)
        if q.get("confidence", 0) >= 0.8:
            high_conf += 1
        else:
            low_conf += 1

        node_ids = match_cognitive_nodes(q, user_id)
        q["suggested_node_ids"] = node_ids

    return {
        "questions": questions,
        "stats": {
            "total": total,
            "high_confidence": high_conf,
            "low_confidence": low_conf,
        },
        "source_file": Path(file_path).name,
        "suggestions": {
            "suggested_bank": bank_id or "",
        },
    }


def confirm_import(
    questions: list[dict],
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """
    确认导入题目到题库。

    返回:
        { imported: int, errors: [...], questions: [...] }
    """
    from app.db.database import get_db
    from app.services.practice.practice_question_crud import add_question
    db = get_db()

    imported = 0
    errors = []
    saved_questions = []

    for i, q in enumerate(questions):
        try:
            stem = (q.get("stem") or "").strip()
            if not stem:
                errors.append({"index": i, "reason": "题干为空"})
                continue

            # 推断题型
            qtype = q.get("question_type") or _infer_type_from_analysis(q)
            if qtype not in ("single", "multiple", "judge", "fill", "essay"):
                qtype = "single"

            # 标准化答案
            answer_raw = q.get("answer", "")
            if isinstance(answer_raw, str):
                answer_raw = answer_raw.strip().upper()
                if qtype in ("single", "multiple"):
                    answer_list = [ch for ch in answer_raw if ch.isalpha()]
                else:
                    answer_list = [answer_raw]
            elif isinstance(answer_raw, list):
                answer_list = answer_raw
            else:
                answer_list = [str(answer_raw)]

            if not answer_list:
                errors.append({"index": i, "reason": "答案为空", "stem": stem[:50]})
                continue

            # 标准化选项
            options_raw = q.get("options") or []
            options_standard = []
            for opt in options_raw:
                if isinstance(opt, dict):
                    options_standard.append({
                        "letter": opt.get("label", opt.get("letter", "")),
                        "text": opt.get("content", opt.get("text", "")),
                        "is_correct": opt.get("is_correct", False),
                    })
                elif isinstance(opt, str):
                    # 纯字符串选项，尝试解析
                    options_standard.append({
                        "letter": chr(65 + len(options_standard)),
                        "text": opt,
                        "is_correct": False,
                    })

            # 保存
            v7_q = add_question(
                bank_id=bank_id,
                user_id=user_id,
                question_type=qtype,
                stem=stem,
                answer=answer_list,
                options=options_standard if options_standard else None,
                analysis=q.get("analysis", ""),
                difficulty=_estimate_difficulty(q),
                cognitive_node_ids=q.get("suggested_node_ids") or q.get("cognitive_node_ids"),
                source="import",
                metadata={
                    "import_confidence": q.get("confidence", 0.5),
                    "ai_corrected": q.get("ai_corrected", False),
                    "source_line": q.get("source_line", 0),
                },
            )
            saved_questions.append(v7_q)
            imported += 1

        except Exception as e:
            logger.warning("导入第 %d 题失败: %s", i, e)
            errors.append({"index": i, "reason": str(e)})

    return {
        "imported": imported,
        "errors": errors,
        "questions": saved_questions,
        "bank_id": bank_id,
        "error_count": len(errors),
    }


# ── 内部辅助 ──


def _infer_line_type(text: str) -> str:
    """推断行类型: question | option | answer | analysis | unknown"""
    for marker in ANSWER_MARKERS:
        if marker in text:
            return "answer"
    for marker in ANALYSIS_MARKERS:
        if marker in text:
            return "analysis"
    for pat in QUESTION_NUM_PATTERNS:
        if pat.match(text):
            return "question"
    for pat in OPTION_PATTERNS:
        if pat.match(text):
            return "option"
    return "unknown"


def _structure_questions(blocks: list[dict]) -> list[dict]:
    """将段落列表结构化为一组题目"""
    questions = []
    current = None

    for block in blocks:
        btype = block["type"]

        if btype == "question":
            if current:
                questions.append(_finalize_question(current))
            stem = block["text"]
            for pat in QUESTION_NUM_PATTERNS:
                m = pat.match(stem)
                if m:
                    stem = m.group(2).strip() if m.lastindex >= 2 else stem
                    break
            current = {
                "stem": stem,
                "options": [],
                "answer": "",
                "analysis": "",
                "source_line": block.get("line", 0),
                "confidence": 0.7,
                "question_type": "single",
            }

        elif btype == "option" and current:
            for pat in OPTION_PATTERNS:
                m = pat.match(block["text"])
                if m:
                    current["options"].append({
                        "label": m.group(1).upper(),
                        "content": m.group(2).strip(),
                    })
                    break

        elif btype == "answer" and current:
            for marker in ANSWER_MARKERS:
                current["answer"] = block["text"].replace(marker, "").strip()

        elif btype == "analysis" and current:
            for marker in ANALYSIS_MARKERS:
                current["analysis"] = block["text"].replace(marker, "").strip()

        elif btype == "unknown" and current:
            if not current["options"]:
                current["stem"] += "\n" + block["text"]
            # 有选项后忽略未知行

    if current:
        questions.append(_finalize_question(current))

    return questions


def _finalize_question(q: dict) -> dict:
    """完成题目构建：推断题型、计算置信度"""
    opt_count = len(q.get("options") or [])

    # 推断题型
    if opt_count >= 2:
        q["question_type"] = "single"
    elif not q["options"]:
        q["question_type"] = "fill"
    else:
        q["question_type"] = "single"

    # 置信度
    score = 0.7
    if q.get("answer"):
        score += 0.15
    if q.get("analysis"):
        score += 0.1
    if q.get("question_type") in ("single", "multiple") and len(q.get("options", [])) < 2:
        score -= 0.3
    q["confidence"] = min(1.0, max(0.1, score))

    return q


def _normalize_options(options: list) -> list[dict]:
    """标准化选项格式"""
    result = []
    for i, opt in enumerate(options):
        if isinstance(opt, dict):
            result.append({
                "label": opt.get("label", opt.get("letter", chr(65 + i))),
                "content": opt.get("content", opt.get("text", "")),
                "is_correct": opt.get("is_correct", False),
            })
        elif isinstance(opt, str):
            result.append({
                "label": chr(65 + i),
                "content": opt,
                "is_correct": False,
            })
    return result


def _infer_type(item: dict) -> str:
    """从 JSON 条目推断题型"""
    qtype = item.get("type", item.get("question_type", ""))
    if qtype in TYPE_KEYWORDS:
        return TYPE_KEYWORDS[qtype]
    opts = item.get("options", [])
    if len(opts) >= 2:
        return "single"
    return "fill"


def _infer_type_from_analysis(q: dict) -> str:
    """从题目内容推断题型"""
    opts = q.get("options", [])
    if len(opts) >= 2:
        return "single"
    stem = q.get("stem", "")
    if any(kw in stem for kw in ["判断", "是否正确", "对还是错"]):
        return "judge"
    return "fill"


def _estimate_difficulty(q: dict) -> int:
    """估算难度 1-5"""
    conf = q.get("confidence", 0.5)
    # 低置信度可能意味着题目复杂
    if conf < 0.5:
        return 3
    if conf < 0.7:
        return 3
    return 3  # 默认中等难度


def get_import_history(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """获取导入历史"""
    from app.db.database import get_db
    db = get_db()
    conditions = ["q.metadata->>'import_batch' IS NOT NULL", "q.deleted_at IS NULL"]
    params = []
    if bank_id:
        conditions.append("q.bank_id = %s")
        params.append(bank_id)
    where = " AND ".join(conditions)

    count_row = db.fetchone(
        f"SELECT COUNT(DISTINCT q.metadata->>'import_batch') as cnt FROM v7_questions q WHERE {where}",
        tuple(params) if params else None,
    )
    total = count_row["cnt"] if count_row else 0

    rows = db.fetchall(
        f"""SELECT q.metadata->>'import_batch' as batch_id,
                  q.bank_id,
                  MIN(q.created_at) as imported_at,
                  COUNT(*) as question_count,
                  COUNT(*) FILTER (WHERE q.status = 'active') as active_count
           FROM v7_questions q
           WHERE {where}
           GROUP BY batch_id, q.bank_id
           ORDER BY imported_at DESC
           LIMIT %s OFFSET %s""",
        tuple(params + [limit, offset]) if params else (limit, offset),
    )

    items = []
    for r in rows:
        bank = db.fetchone("SELECT name FROM v7_question_banks WHERE id = %s", (r["bank_id"],))
        items.append({
            "batch_id": r["batch_id"],
            "bank_id": r["bank_id"],
            "bank_name": bank["name"] if bank else "",
            "imported_at": _safe_iso(r.get("imported_at")),
            "question_count": r["question_count"],
            "active_count": r["active_count"],
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _safe_iso(val):
    """安全转换日期为 ISO 字符串"""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _parse_docx_fallback(file_path: str) -> list[dict]:
    """docx 备用解析（不依赖 MarkItDown）"""
    try:
        from docx import Document
        doc = Document(file_path)
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        return parse_questions_from_text("\n".join(lines), "docx")
    except ImportError:
        raise ValueError("python-docx 未安装，无法解析 .docx 文件")
    except Exception as e:
        raise ValueError(f"docx 解析失败: {e}")
