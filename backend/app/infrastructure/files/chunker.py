"""
TOC 分块引擎 — 智能分块流水线

流程:
  Stage 1: _flatten_table_blobs()     — 表格内嵌标题探测 + 行拆分
  Stage 2: _detect_headings()         — 多策略标题检测 + 置信度评分
  Stage 3: _infer_heading_level()     — 层级推断 + 树构建
  Stage 4: _chunk_by_inline_headings()— 按内嵌标题分割 block

V2 → V3 变化:
  - 支持 `**一、实验目的**` 等粗体编号标题（.docx 表格输出）
  - 支持行内多标题探测（MarkItDown 表格行合并场景）
  - 置信度评分系统，可扩展任意标题格式
  - 语义回退接口（由 indexer.py 注入 embedding 函数）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── 数据结构 ──

@dataclass
class TOCNode:
    """目录树节点"""
    level: int
    heading: str
    parent: Optional["TOCNode"] = None
    children: list["TOCNode"] = field(default_factory=list)
    chunk_start: int = 0
    chunk_end: int = 0
    first_chunk_text: str = ""
    heading_line_index: int = 0
    _heading_score: float = 0.0  # 检测置信度，用于调试


# ── 标题检测配置 ──

# (regex_pattern, weight, desc)
_HEADING_PATTERNS: list[tuple[str, float, str]] = [
    # ATX markdown heading — 最高置信度
    (r"^(#{1,6})\s+(.+)", 1.0, "ATX"),
    # 行首粗体中文编号: **一、标题** **二、标题**
    (r"^\*\*([一二三四五六七八九十百千]+)[、．.]([^*]+)\*\*", 0.95, "bold_cn"),
    # 行首粗体英文编号: **1. 标题** **2. 标题**
    (r"^\*\*(\d+)[、．.]([^*]+)\*\*", 0.85, "bold_en"),
    # 行首纯中文编号: 一、标题  二、标题
    (r"^([一二三四五六七八九十百千]+)[、．](.+)$", 0.75, "plain_cn"),
    # 行首纯英文编号: 1. 标题  2. 标题  (1) 标题
    (r"^(\d+)[、．.)\)]\s*(.+)$", 0.65, "plain_en"),
    # 行首纯粗体行: **标题**（无编号，无标点结尾）
    (r"^\*\*([^*]+)\*\*$", 0.40, "bold_line"),
]

# 表格内标题探测（同一行内出现多个 **X、** 模式）
_INLINE_HEADING_RE = re.compile(r"\*\*([一二三四五六七八九十百千]+[、．.][^*]+?)\*\*")

# 层级推断：编号前缀 → level
_LEVEL_PATTERNS: list[tuple[str, int]] = [
    (r"^[一二三四五六七八九十百千]+[、．]", 1),         # 一、二、三
    (r"^\d+[、．]", 2),                                  # 1. 2. 3.
    (r"^\(\d+\)", 3),                                    # (1) (2)
    (r"^\d+\)", 3),                                      # 1) 2)
    (r"^[①②③④⑤⑥⑦⑧⑨⑩]", 3),                          # ① ②
    (r"^[\(（]?[a-zA-Z][\)）]", 3),                      # (a) (b)
]


# ── 公共工具 ──

def _is_in_fence(lines: list[str], line_idx: int) -> bool:
    """检测 line_idx 是否在 fence 代码块内"""
    count = 0
    for i in range(line_idx):
        stripped = lines[i].strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            count += 1
    return count % 2 == 1


# ── Stage 1: 表格扁平化预处理 ──

def _flatten_table_blobs(text: str) -> str:
    """检测表格行内是否包含多个章节标题，若是则按标题拆分。

    MarkItDown 将 docx 表格的每一格输出为一行 markdown 表格行：
      | **一、实验目的** ... **二、实验原理** ... |
    这种行内部包含多个标题，导致整个文档内容无法按章节分割。
    本函数检测这种模式，将一行拆为多行。
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and _has_multiple_inline_headings(stripped):
            parts = _split_table_row_at_headings(stripped)
            result.extend(parts)
        else:
            # 清理尾部多余的 |
            cleaned = line.rstrip()
            if not cleaned.startswith("|") and cleaned.endswith("|"):
                cleaned = cleaned.rstrip("|").rstrip()
            result.append(cleaned)
    return "\n".join(result)


def _has_multiple_inline_headings(line: str) -> bool:
    """检测一行内是否有多个粗体编号标题"""
    matches = _INLINE_HEADING_RE.findall(line)
    return len(matches) >= 2


def _split_table_row_at_headings(line: str) -> list[str]:
    """将包含多个标题的表格行拆成独立行

    输入: "| **一、实验目的** 内容... **二、实验原理** 内容... |"
    输出: ["| **一、实验目的** 内容... |", "| **二、实验原理** 内容... |"]
    """
    # 找到所有标题位置
    parts: list[str] = []
    prev_end = 0
    heading_positions = [(m.start(), m.end()) for m in _INLINE_HEADING_RE.finditer(line)]

    for i, (start, end) in enumerate(heading_positions):
        if i > 0:
            # 取上一个标题结束到当前标题开始之间的内容
            segment = line[prev_end:start].strip()
            # 去掉开头的表格分隔符
            segment = segment.lstrip("|").strip()
            # 去掉表格行尾的 |
            segment = segment.rstrip("|").strip()
            if segment:
                # 加入前一段的闭合
                content = line[heading_positions[i-1][1]:start].strip()
                content = content.lstrip("|").strip()
                content = content.rstrip("|").strip()
                content = line[heading_positions[i-1][0]:start].strip()
                result_line = f"| {content} |"
                if result_line not in parts and len(content) > 3:
                    parts.append(result_line)
        prev_end = start

    # 最后一段
    if heading_positions:
        last_content = line[heading_positions[0][0]:].strip()
        last_content = last_content.rstrip("|").strip()
        # 尝试将所有标题段落都提取出来
        for i, (start, end) in enumerate(heading_positions):
            if i + 1 < len(heading_positions):
                segment = line[start:heading_positions[i+1][0]]
            else:
                segment = line[start:]
            segment = segment.strip().rstrip("|").strip()
            if segment:
                result_line = f"| {segment} |"
                if result_line not in parts:
                    parts.append(result_line)

    return parts if parts else [line]


# ── Stage 2: 多策略标题检测 ──

def _detect_heading_score(line: str) -> tuple[float, str, int]:
    """对一行文本计算标题置信度评分。

    Returns:
        (score, heading_text, inferred_level) 或 (0, "", 0) 表示非标题
    """
    stripped = line.strip()
    if not stripped:
        return (0.0, "", 0)

    best_score = 0.0
    best_heading = ""
    best_level = 0

    for pattern, weight, desc in _HEADING_PATTERNS:
        m = re.match(pattern, stripped)
        if m:
            if desc == "ATX":
                level = len(m.group(1))
                heading = m.group(2).strip()
            elif desc == "bold_cn":
                level = 1
                heading = m.group(1) + "、" + m.group(2).strip()
            elif desc in ("bold_en",):
                level = 2
                heading = m.group(1) + ". " + m.group(2).strip()
            elif desc == "plain_cn":
                level = 1
                heading = m.group(1) + "、" + m.group(2).strip()
            elif desc == "plain_en":
                level = 2
                heading = m.group(1) + ". " + m.group(2).strip()
            elif desc == "bold_line":
                level = 2
                heading = m.group(1).strip()
            else:
                level = 2
                heading = m.group(2).strip() if m.lastindex >= 2 else m.group(1).strip()

            score = weight
            # 辅助加分：短行（<60字）且不以句号结尾 → 更像标题
            if len(stripped) < 60 and not stripped.rstrip().endswith(("。", ".", "！", "？")):
                score += 0.05
            # 加分：行尾无标点
            if not stripped.rstrip().endswith(("。", ".", "！", "？", ":", "：", ",", "，")):
                score += 0.03
            # 减分：行中包含大量文本 → 可能是正文不是标题
            if len(stripped) > 120:
                score -= 0.15
            # 减分：以冒号结尾 → 可能是 metadata 标签（学号：、姓名：）
            if stripped.rstrip().endswith("："):
                score -= 0.20
            # 减分：纯粗体行中不含中文字符 → 可能是代码/标记
            if desc == "bold_line" and not any('\u4e00' <= c <= '\u9fff' for c in heading):
                score -= 0.15

            score = min(score, 1.0)

            if score > best_score:
                best_score = score
                best_heading = heading
                best_level = level

    # 表格内行中标题检测（表格行内但不在行首的 **一、**）
    if best_score == 0.0 and stripped.startswith("|"):
        for m in _INLINE_HEADING_RE.finditer(stripped):
            heading_text = m.group(1).strip()
            # 检查是否在行首附近（前20字符内）
            if m.start() < 20:
                best_score = 0.80
                best_heading = heading_text
                best_level = 1
                break

    if best_score >= 0.50:
        best_heading = best_heading[:200]
        return (best_score, best_heading, best_level)
    return (0.0, "", 0)


def _infer_heading_level_from_text(heading_text: str) -> int:
    """从标题文本推断层级（独立于行检测，用于 TOC 构建）"""
    for pattern, level in _LEVEL_PATTERNS:
        if re.match(pattern, heading_text.strip()):
            return level
    return 2  # 默认


# ── Stage 3: 层级推断 + 树构建 ──

def extract_toc(markdown_text: str) -> list[TOCNode]:
    """增强版目录树提取 — 支持 `#` 标题 + 粗体编号标题 + 纯编号标题。

    策略：
      1. 先做表格扁平化预处理
      2. 第一遍：扫描行首 `#` 标题（V2 原有逻辑）
      3. 第二遍：对非标题行做置信度评分检测
      4. 合并结果，按行位置排序，去重
      5. 构建层级树
    """
    # Stage 1: 表格扁平化
    text = _flatten_table_blobs(markdown_text)
    lines = text.split("\n")

    # Stage 2: 多策略检测
    candidates: list[dict] = []  # {line_idx, heading, level, score, is_atx}

    for line_idx, line in enumerate(lines):
        if _is_in_fence(lines, line_idx):
            continue
        score, heading, detected_level = _detect_heading_score(line)
        if score >= 0.50 and heading:
            is_atx = score >= 1.0  # ATX markdown heading
            candidates.append({
                "line_idx": line_idx,
                "heading": heading,
                "level": detected_level if is_atx else _infer_heading_level_from_text(heading),
                "score": score,
                "is_atx": is_atx,
            })

    # 去重：相同 heading 只保留一次（保留第一个出现的）
    seen: set[str] = set()
    unique: list[dict] = []
    for c in candidates:
        key = c["heading"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    if not unique:
        return []

    # 第二遍：非 ATX 标题的层级相对于最近的 ATX 父标题偏移
    # 例如: # Chapter 1 (ATX level=1) → 一、Section (non-ATX inferred=1) → level=1+1=2
    last_atx_level = 0
    for c in unique:
        if c.get("is_atx"):
            last_atx_level = c["level"]
        elif last_atx_level > 0:
            c["level"] = last_atx_level + c["level"]

    # Stage 3: 构建树
    nodes: list[TOCNode] = []
    stack: list[TOCNode] = []

    for c in unique:
        node = TOCNode(
            level=c["level"],
            heading=c["heading"],
            heading_line_index=c["line_idx"],
            _heading_score=c["score"],
        )
        # 用栈维护层级
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            node.parent = stack[-1]
            stack[-1].children.append(node)
        stack.append(node)
        nodes.append(node)

    logger.debug("extract_toc v3: 检测到 %d 个标题（含 %d 个非 # 标题）",
                 len(nodes),
                 sum(1 for n in nodes if n._heading_score < 1.0))
    return nodes


# ── Stage 4: 按标题分割分块 ──

def _split_at_inline_headings(text_block: str, toc_nodes: list[TOCNode],
                               max_size: int) -> list[dict]:
    """在大段文本内部按识别到的标题分割（处理表格内多标题场景）。

    当 chunk_by_toc 遇到一个大 block 包含多个标题时调用。
    输入: "**一、实验目的** 内容... **二、实验原理** 内容..."
    输出: [{"text": "**一、实验目的** 内容...", "heading_path": "一、实验目的", ...}, ...]
    """
    if not toc_nodes or len(text_block) < max_size * 0.5:
        return []

    # 构建 heading → node 映射
    heading_map: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        heading_map[tn.heading.strip().lower()] = tn

    def _breadcrumb(node: TOCNode) -> str:
        parts = [node.heading]
        p = node.parent
        while p:
            parts.insert(0, p.heading)
            p = p.parent
        return " > ".join(parts)

    # 将标题文本转为模糊匹配模式（灵活处理空格差异）
    def _fuzzy_pattern(heading: str) -> str:
        """将标题转为宽松匹配正则：空格 → \\s+，其他字符 re.escape"""
        escaped = re.escape(heading)
        # 将转义后的空格 \ 替换为 \s+（允许一个或多个空白）
        return escaped.replace(r"\ ", r"\s+")

    # 按 heading 文本排序（按长度递减，优先匹配长标题）
    sorted_nodes = sorted(toc_nodes, key=lambda n: len(n.heading), reverse=True)

    # 查找每个标题在文本中的位置
    splits: list[tuple[int, str, TOCNode]] = []  # (position, heading_text, node)
    for tn in sorted_nodes:
        # 尝试多种模式匹配（模糊匹配，允许空格差异）
        patterns = [
            rf"\*\*{_fuzzy_pattern(tn.heading)}\*\*",
            _fuzzy_pattern(tn.heading),
        ]
        for pat in patterns:
            for m in re.finditer(pat, text_block):
                splits.append((m.start(), tn.heading, tn))
                break
            if any(s[1] == tn.heading for s in splits):
                break

    if len(splits) < 2:
        return []

    # 去重+按位置排序
    seen_heads: set[str] = set()
    unique_splits: list[tuple[int, str, TOCNode]] = []
    for pos, h, node in sorted(splits, key=lambda x: x[0]):
        if h not in seen_heads:
            seen_heads.add(h)
            unique_splits.append((pos, h, node))

    # 按位置分割文本
    chunks: list[dict] = []

    # 第一段：第一个标题之前的内容（封面等）
    first_pos = unique_splits[0][0]
    if first_pos > 0:
        preamble = text_block[:first_pos].strip()
        if preamble:
            chunks.append({
                "text": preamble, "heading_path": "",
                "index": len(chunks),
            })

    # 中间段落：按标题分割
    for i, (pos, heading, node) in enumerate(unique_splits):
        end_pos = unique_splits[i + 1][0] if i + 1 < len(unique_splits) else len(text_block)
        segment = text_block[pos:end_pos].strip()
        if not segment:
            continue

        heading_path = _breadcrumb(node)

        # 如果 segment 仍然太大，再按行分割
        if len(segment) > max_size:
            sub_paras = [p.strip() for p in segment.split("\n") if p.strip()]
            buffer = ""
            for sp in sub_paras:
                if len(buffer) + len(sp) < max_size:
                    buffer += ("\n" if buffer else "") + sp
                else:
                    if buffer:
                        chunks.append({
                            "text": buffer, "heading_path": heading_path,
                            "index": len(chunks),
                        })
                    buffer = sp
            if buffer:
                chunks.append({
                    "text": buffer, "heading_path": heading_path,
                    "index": len(chunks),
                })
        else:
            chunks.append({
                "text": segment, "heading_path": heading_path,
                "index": len(chunks),
            })

    return chunks


def chunk_by_toc(markdown_text: str, toc_nodes: list[TOCNode],
                 max_chunk_size: int = 1000,
                 embedding_fn: Callable | None = None) -> list[dict]:
    """按 TOC 分割 Markdown 为分块。

    行为：
      1. TOC 来自 `#` 标题 → 按行分割（V2 原有逻辑）
      2. TOC 来自粗体编号标题 → 尝试在文本内按标题位置分割
      3. 大 block 内包含多个标题 → _split_at_inline_headings()
      4. 全无结构 → _chunk_flat() 平铺
      5. embedding_fn 非 None 时启用语义回退
    """
    # ── 前置处理：同一大 paragraph 内包含多个标题 ──
    # 预处理：将表格行按内嵌标题拆分
    text = _flatten_table_blobs(markdown_text)

    if not toc_nodes:
        # 尝试在大段落内部找标题
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        big_paras = [p for p in paragraphs if len(p) > max_chunk_size * 0.6]
        if big_paras:
            # 重新对每个大段落做标题检测
            all_headings: list[TOCNode] = []
            for bp in big_paras:
                bp_toc = extract_toc(bp)
                all_headings.extend(bp_toc)
            if all_headings:
                # 用检测到的标题分割
                return _chunk_with_structure(text, all_headings, max_chunk_size)

        # 语义回退
        if embedding_fn:
            return _chunk_semantic(text, max_chunk_size, embedding_fn)
        return _chunk_flat(text, max_chunk_size)

    # ── 有 TOC 的情况 ──
    heading_to_node: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        key = tn.heading.strip().lower()
        heading_to_node[key] = tn

    def _breadcrumb(node: TOCNode) -> str:
        parts = [node.heading]
        p = node.parent
        while p:
            parts.insert(0, p.heading)
            p = p.parent
        return " > ".join(parts)

    # 检查 TOC 是否来自 `#` 标题（V2 逻辑）还是其他
    has_atx = any(n._heading_score >= 1.0 for n in toc_nodes if hasattr(n, '_heading_score'))

    if has_atx:
        # ── V2 兼容：按行分割（`#` 标题在独立行）──
        lines = text.split("\n")
        raw_chunks: list[dict] = []
        current_heading = ""
        current_lines: list[str] = []

        for line_idx, line in enumerate(lines):
            if _is_in_fence(lines, line_idx):
                current_lines.append(line)
                continue
            m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if m:
                if current_lines:
                    seg_text = "\n".join(current_lines).strip()
                    if seg_text:
                        raw_chunks.append({
                            "text": seg_text,
                            "heading_path": current_heading,
                            "index": len(raw_chunks),
                        })
                    current_lines = []
                heading_text = m.group(2).strip()
                node = heading_to_node.get(heading_text.lower())
                current_heading = _breadcrumb(node) if node else heading_text
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            seg_text = "\n".join(current_lines).strip()
            if seg_text:
                raw_chunks.append({
                    "text": seg_text,
                    "heading_path": current_heading,
                    "index": len(raw_chunks),
                })
    else:
        # ── V3：先用逐行正则检测（更健壮，处理空格差异），再用全文搜索兜底 ──
        raw_chunks = _chunk_by_bold_headings(text, toc_nodes, max_chunk_size)
        if not raw_chunks:
            raw_chunks = _split_at_inline_headings(text, toc_nodes, max_chunk_size)

    # 后处理：大 chunk 二次切分 + 过滤无效块
    MIN_CHUNK_CHARS = 3
    final_chunks: list[dict] = []
    for ch in raw_chunks:
        if len(ch["text"]) < MIN_CHUNK_CHARS:
            continue
        if len(ch["text"]) > max_chunk_size:
            sub = _split_large_chunk(ch["text"], ch["heading_path"], max_chunk_size)
            final_chunks.extend(sub)
        else:
            final_chunks.append(ch)

    for i, ch in enumerate(final_chunks):
        ch["index"] = i

    return final_chunks


def _chunk_by_bold_headings(text: str, toc_nodes: list[TOCNode],
                             max_size: int) -> list[dict]:
    """按行级粗体标题分割（辅助函数）"""
    lines = text.split("\n")
    heading_to_node: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        heading_to_node[tn.heading.strip().lower()] = tn

    def _breadcrumb(node: TOCNode) -> str:
        parts = [node.heading]
        p = node.parent
        while p:
            parts.insert(0, p.heading)
            p = p.parent
        return " > ".join(parts)

    chunks: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        score, heading, _ = _detect_heading_score(line)
        if score >= 0.50 and heading:
            key = heading.strip().lower()
            node = heading_to_node.get(key)
            if node:
                if current_lines:
                    seg_text = "\n".join(current_lines).strip()
                    if seg_text:
                        chunks.append({
                            "text": seg_text,
                            "heading_path": current_heading,
                            "index": len(chunks),
                        })
                    current_lines = []
                current_heading = _breadcrumb(node)
        current_lines.append(line)

    if current_lines:
        seg_text = "\n".join(current_lines).strip()
        if seg_text:
            chunks.append({
                "text": seg_text,
                "heading_path": current_heading,
                "index": len(chunks),
            })

    return chunks


def _chunk_with_structure(text: str, headings: list[TOCNode],
                           max_size: int) -> list[dict]:
    """用标题列表分割文本（通用函数）"""
    return _split_at_inline_headings(text, headings, max_size)


# ── 语义回退（Stage 4） ──

def _chunk_semantic(text: str, max_size: int,
                    embedding_fn: Callable) -> list[dict]:
    """语义分块：利用 embedding 相似度骤降检测段落边界。

    使用已有 embedding 模型计算滑动窗口的向量，
    相邻窗口相似度 < threshold 的位置视为段落边界。
    """
    try:
        # 按句/短段落分割为窗口
        windows = _split_into_windows(text, size=200)
        if len(windows) < 3:
            return _chunk_flat(text, max_size)

        # 计算每个窗口的 embedding
        vectors: list[list[float]] = []
        for w in windows:
            vec = embedding_fn(w)
            if vec:
                vectors.append(vec)

        if len(vectors) < 3:
            return _chunk_flat(text, max_size)

        # 计算相邻窗口余弦相似度
        boundaries = [0]
        for i in range(1, len(vectors)):
            sim = _cosine_sim(vectors[i - 1], vectors[i])
            if sim is not None and sim < 0.65:
                # 相似度骤降 → 语义边界
                char_pos = min(i * 200, len(text))
                boundaries.append(char_pos)

        boundaries.append(len(text))

        # 按边界组装 chunks
        chunks: list[dict] = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            segment = text[start:end].strip()
            if not segment:
                continue
            # 如果太大再递归切
            if len(segment) > max_size:
                sub_chunks = _chunk_flat(segment, max_size)
                for sc in sub_chunks:
                    sc["heading_path"] = ""
                    sc["index"] = len(chunks)
                    chunks.append(sc)
            else:
                chunks.append({
                    "text": segment,
                    "heading_path": "",
                    "index": len(chunks),
                })

        if not chunks:
            return _chunk_flat(text, max_size)
        return chunks

    except Exception as e:
        logger.debug("语义分块失败，降级到平铺: %s", e)
        return _chunk_flat(text, max_size)


def _split_into_windows(text: str, size: int) -> list[str]:
    """将文本分割为固定大小的重叠窗口"""
    # 先按句号/换行分割
    segments = re.split(r"(?<=[。！？\n])", text)
    windows: list[str] = []
    buffer = ""
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if len(buffer) + len(seg) < size:
            buffer += seg
        else:
            if buffer:
                windows.append(buffer)
            buffer = seg
    if buffer:
        windows.append(buffer)
    return windows or [text]


def _cosine_sim(a: list[float], b: list[float]) -> float | None:
    """计算两个向量的余弦相似度"""
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return None
    return dot / (na * nb)


# ── 传统分块（保留 V2 兼容） ──

def assign_chunk_ranges(toc_nodes: list[TOCNode], chunks: list[dict]) -> list[TOCNode]:
    """将分块序号关联到 TOC 节点。

    策略：
      1. 直接用 heading_path 匹配 chunk → TOC 节点（精确匹配）
      2. 未匹配的节点从子节点向上传播范围（父节点 = 子节点范围的并集）
      3. 既无自身匹配又无子节点匹配的节点 → -1, -1（不分配范围）
    """
    if not toc_nodes:
        return toc_nodes

    # 初始化所有节点为 -1
    for tn in toc_nodes:
        tn.chunk_start = -1
        tn.chunk_end = -1

    if not chunks:
        return toc_nodes

    # ── 第1步：通过 heading_path 精确匹配 ──
    # 构建 heading → node 映射（用 heading_path 的最后一段匹配）
    heading_map: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        heading_map[tn.heading.strip().lower()] = tn

    for ci, chunk in enumerate(chunks):
        heading_path = chunk.get("heading_path", "")
        if not heading_path:
            continue
        # 取 heading_path 的最后一段（最深层的标题）
        parts = heading_path.split(" > ")
        last_heading = parts[-1].strip().lower() if parts else ""
        node = heading_map.get(last_heading)
        if node:
            if node.chunk_start == -1:
                node.chunk_start = ci
            node.chunk_end = ci
            if not node.first_chunk_text and chunk.get("text"):
                node.first_chunk_text = chunk["text"][:200]

    # ── 第2步：子节点 → 父节点 向上传播（后序遍历）──
    # 父节点范围 = 所有直接子节点范围的并集
    def _propagate_up(node: TOCNode) -> tuple[int, int]:
        """后序遍历：先处理子节点，再计算父节点范围"""
        child_ranges: list[tuple[int, int]] = []
        for child in node.children:
            c_start, c_end = _propagate_up(child)
            if c_start != -1 and c_end != -1:
                child_ranges.append((c_start, c_end))

        if node.chunk_start != -1 and node.chunk_end != -1:
            # 节点自身已有匹配，保留
            return node.chunk_start, node.chunk_end

        if child_ranges:
            # 从子节点传播：取最小 start 和最大 end
            node.chunk_start = min(r[0] for r in child_ranges)
            node.chunk_end = max(r[1] for r in child_ranges)
            return node.chunk_start, node.chunk_end

        return -1, -1

    for root in [n for n in toc_nodes if n.parent is None]:
        _propagate_up(root)

    # 确保 chunk_start <= chunk_end
    for tn in toc_nodes:
        if tn.chunk_start > tn.chunk_end:
            tn.chunk_end = tn.chunk_start

    return toc_nodes


def _chunk_flat(text: str, max_size: int) -> list[dict]:
    """无 TOC 时的平铺分块"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[dict] = []
    buffer = ""
    for p in paragraphs:
        if len(buffer) + len(p) < max_size:
            buffer += ("\n\n" if buffer else "") + p
        else:
            if buffer:
                chunks.append({"text": buffer, "heading_path": "", "index": len(chunks)})
            buffer = p
    if buffer:
        chunks.append({"text": buffer, "heading_path": "", "index": len(chunks)})
    return chunks


def _split_large_chunk(text: str, heading_path: str, max_size: int) -> list[dict]:
    """按空行分割大 chunk"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[dict] = []
    buffer = ""
    for p in paragraphs:
        if len(buffer) + len(p) < max_size:
            buffer += ("\n\n" if buffer else "") + p
        else:
            if buffer:
                chunks.append({"text": buffer, "heading_path": heading_path, "index": 0})
            buffer = p
    if buffer:
        chunks.append({"text": buffer, "heading_path": heading_path, "index": 0})
    return chunks
