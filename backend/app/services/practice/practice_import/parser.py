"""题库导入 — 文件/文本/JSON 解析"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import (
    QUESTION_NUM_PATTERNS, OPTION_PATTERNS,
    ANSWER_MARKERS, ANALYSIS_MARKERS, TYPE_KEYWORDS,
)

logger = logging.getLogger(__name__)


def parse_questions_from_text(text: str, source: str = "text") -> list[dict]:
    """从纯文本中解析出题目列表。"""
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
        try:
            from app.infrastructure.files.parser import material_parser
            md_text = material_parser.parse(str(path), ext)
            if md_text.strip():
                return parse_questions_from_text(md_text, ext)
        except Exception as e:
            logger.warning("MarkItDown 解析失败 %s: %s", file_path, e)

        if ext == ".docx":
            return _parse_docx_fallback(str(path))
        raise ValueError(f"无法解析文件: {path.name}")

    raise ValueError(f"不支持的文件格式: {ext}")


# ── 内部辅助 ──

def _infer_line_type(text: str) -> str:
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
                "stem": stem, "options": [], "answer": "", "analysis": "",
                "source_line": block.get("line", 0), "confidence": 0.7, "question_type": "single",
            }
        elif btype == "option" and current:
            for pat in OPTION_PATTERNS:
                m = pat.match(block["text"])
                if m:
                    current["options"].append({"label": m.group(1).upper(), "content": m.group(2).strip()})
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

    if current:
        questions.append(_finalize_question(current))
    return questions


def _finalize_question(q: dict) -> dict:
    opt_count = len(q.get("options") or [])
    if opt_count >= 2:
        q["question_type"] = "single"
    elif not q["options"]:
        q["question_type"] = "fill"
    else:
        q["question_type"] = "single"

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
    result = []
    for i, opt in enumerate(options):
        if isinstance(opt, dict):
            result.append({
                "label": opt.get("label", opt.get("letter", chr(65 + i))),
                "content": opt.get("content", opt.get("text", "")),
                "is_correct": opt.get("is_correct", False),
            })
        elif isinstance(opt, str):
            result.append({"label": chr(65 + i), "content": opt, "is_correct": False})
    return result


def _infer_type(item: dict) -> str:
    qtype = item.get("type", item.get("question_type", ""))
    if qtype in TYPE_KEYWORDS:
        return TYPE_KEYWORDS[qtype]
    opts = item.get("options", [])
    if len(opts) >= 2:
        return "single"
    return "fill"


def _infer_type_from_analysis(q: dict) -> str:
    opts = q.get("options", [])
    if len(opts) >= 2:
        return "single"
    stem = q.get("stem", "")
    if any(kw in stem for kw in ["判断", "是否正确", "对还是错"]):
        return "judge"
    return "fill"


def _estimate_difficulty(q: dict) -> int:
    return 3


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


# ── AI 修正（对解析结果后处理）──

def ai_correct_question(q: dict) -> dict:
    """用 AI 修正低置信度题目的解析结果"""
    if q.get("confidence", 1.0) >= 0.8:
        return q

    try:
        from app.infrastructure.llm.llm_service import llm_service
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
        from app.infrastructure.llm.llm_service import llm_service as llm
        result = llm.generate(
            messages=[
                {"role": "system", "content": "你是一个文档解析专家，擅长从非结构化文本中提取和修正练习题。"},
                {"role": "user", "content": prompt},
            ],
            task_type="fast",
            temperature=0.1,
            max_tokens=1000,
        )

        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        corrected = json.loads(clean.strip())

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


def match_cognitive_nodes(q: dict, user_id: str, top_k: int = 3) -> list[str]:
    """将题目内容匹配到认知节点"""
    try:
        from app.infrastructure.embedding_utils import compute_embedding
        from app.infrastructure.db.database import get_db
        db = get_db()

        text = f"{q.get('stem', '')} {q.get('analysis', '')}"[:1000]
        embedding = compute_embedding(text)
        if not embedding:
            return []

        import re
        keywords = re.findall(r'[\u4e00-\u9fff\w]{2,}', q.get("stem", ""))
        if not keywords:
            return []

        from app.domain.cognitive import get_repo
        nodes = get_repo().search_by_text(query=" ".join(keywords[:10]), user_id=user_id, limit=top_k)
        return [n.id for n in nodes if hasattr(n, 'id')] or []

    except Exception as e:
        logger.debug("认知节点匹配失败: %s", e)
        return []
