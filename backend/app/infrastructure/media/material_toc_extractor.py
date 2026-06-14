"""
TOC 提取引擎 v2 — 修复版

解析 Markdown 标题层次，生成目录树结构。

v2 修复:
- assign_chunk_ranges: 不再依赖错误的 chunk_start=0，改用 heading 文本匹配
- chunk_by_toc: 按标题文本匹配而非序号，防止代码块干扰
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TOCNode:
    """目录树节点"""
    level: int           # 1=H1, 2=H2, 3=H3 ...
    heading: str         # 标题文本
    parent: Optional["TOCNode"] = None
    children: list["TOCNode"] = field(default_factory=list)
    chunk_start: int = 0
    chunk_end: int = 0
    first_chunk_text: str = ""   # 首段前 200 字（用于 embedding）
    heading_line_index: int = 0  # 标题在文档中的行号


def extract_toc(markdown_text: str) -> list[TOCNode]:
    """
    从 Markdown 文本中提取目录树。

    参数:
        markdown_text: MarkItDown 输出的完整 Markdown

    返回:
        目录节点列表（平铺，含父子关系），按文档顺序
    """
    lines = markdown_text.split("\n")
    nodes: list[TOCNode] = []
    stack: list[TOCNode] = []

    for line_idx, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()

            # 跳过过长的标题（可能是误识别）
            if len(heading) > 200:
                continue

            node = TOCNode(level=level, heading=heading, heading_line_index=line_idx)

            # 维护父子关系：pop 直到栈顶 level < 当前 level
            while stack and stack[-1].level >= level:
                stack.pop()

            if stack:
                node.parent = stack[-1]
                stack[-1].children.append(node)

            stack.append(node)
            nodes.append(node)

    return nodes


def assign_chunk_ranges(toc_nodes: list[TOCNode], chunks: list[dict]) -> list[TOCNode]:
    """
    将分块序号关联到 TOC 节点。

    策略: 通过 heading 文本匹配确定每个 TOC 节点对应哪些 chunk。
    遍历 chunk，检查其 heading_path 是否匹配某个 TOC 节点。

    chunks 格式: [{"text": str, "heading_path": str, "index": int}, ...]
    heading_path 格式: "H1标题 > H2标题 > H3标题"
    """
    if not toc_nodes or not chunks:
        return toc_nodes

    # 初始化 chunk_start 为 -1（未设置）
    for tn in toc_nodes:
        tn.chunk_start = -1
        tn.chunk_end = -1

    # 构建 heading → TOCNode 映射
    heading_map: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        heading_map[tn.heading.strip().lower()] = tn

    # 遍历 chunks，匹配 heading_path 的最后一段
    for ci, chunk in enumerate(chunks):
        heading_path = chunk.get("heading_path", "")
        if not heading_path:
            continue

        # 取 heading_path 最后一级的标题
        parts = heading_path.split(" > ")
        last_heading = parts[-1].strip().lower() if parts else ""

        node = heading_map.get(last_heading)
        if node:
            if node.chunk_start == -1:
                node.chunk_start = ci
            node.chunk_end = ci

            # 记录首段内容
            if not node.first_chunk_text and chunk.get("text"):
                node.first_chunk_text = chunk["text"][:200]

    # 补漏: 未匹配到 chunk 的节点，范围设为 -1
    # 最后一个节点的 chunk_end 设为最后一个 chunk
    if toc_nodes:
        last_idx = len(chunks) - 1
        for tn in toc_nodes:
            if tn.chunk_start == -1:
                tn.chunk_start = 0
            if tn.chunk_end == -1:
                tn.chunk_end = last_idx

    # 确保 chunk_start <= chunk_end
    for tn in toc_nodes:
        if tn.chunk_start > tn.chunk_end:
            tn.chunk_end = tn.chunk_start

    return toc_nodes


def chunk_by_toc(markdown_text: str, toc_nodes: list[TOCNode], max_chunk_size: int = 1000) -> list[dict]:
    """
    按 TOC 分割 Markdown 为分块。

    策略:
    - 每个标题 + 其正文 = 一个 chunk
    - 超过 max_chunk_size 的 chunk 内按空行再分割
    - 无 TOC（小文件）：按空行分段

    返回：
        [{"text": str, "heading_path": str, "index": int}, ...]
    """
    if not toc_nodes:
        return _chunk_flat(markdown_text, max_chunk_size)

    # 构建 heading 文本 → TOCNode 映射（归一化后匹配）
    heading_to_node: dict[str, TOCNode] = {}
    for tn in toc_nodes:
        key = tn.heading.strip().lower()
        heading_to_node[key] = tn

    # 构建面包屑路径
    def _breadcrumb(node: TOCNode) -> str:
        parts = [node.heading]
        p = node.parent
        while p:
            parts.insert(0, p.heading)
            p = p.parent
        return " > ".join(parts)

    lines = markdown_text.split("\n")
    chunks: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            # 保存上一个 chunk
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    chunks.append({
                        "text": text,
                        "heading_path": current_heading,
                        "index": len(chunks),
                    })
                current_lines = []

            heading_text = m.group(2).strip()
            # 归一化匹配
            node = heading_to_node.get(heading_text.lower())
            if node:
                current_heading = _breadcrumb(node)
            else:
                # 未匹配的标题也用原始文本
                current_heading = heading_text

            current_lines.append(line)
        else:
            current_lines.append(line)

    # 最后一个 chunk
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append({
                "text": text,
                "heading_path": current_heading,
                "index": len(chunks),
            })

    # 大 chunk 再分割
    final_chunks: list[dict] = []
    for ch in chunks:
        if len(ch["text"]) > max_chunk_size:
            sub_chunks = _split_large_chunk(ch["text"], ch["heading_path"], max_chunk_size)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(ch)

    # 重新编号
    for i, ch in enumerate(final_chunks):
        ch["index"] = i

    return final_chunks


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
