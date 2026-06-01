"""
TOC 提取引擎
解析 Markdown 标题层次，生成目录树结构。

设计原则：
- 不使用 LLM，纯正则解析
- TOC 是给「人」看的导航结构，不是给「机器」搜的检索结构
- embedding = heading + 首段前 200 字（免费，不需要 LLM 摘要）
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


def extract_toc(markdown_text: str) -> list[TOCNode]:
    """
    从 Markdown 文本中提取目录树。

    参数:
        markdown_text: MarkItDown 输出的完整 Markdown

    返回:
        目录节点列表（平铺，含父子关系），按文档顺序
        根节点 level=0，对应整个文档
    """
    lines = markdown_text.split("\n")
    nodes: list[TOCNode] = []
    stack: list[TOCNode] = []  # 当前层级栈

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()

            node = TOCNode(level=level, heading=heading)

            # 维护父子关系：pop 直到栈顶 level < 当前 level
            while stack and stack[-1].level >= level:
                stack.pop()

            if stack:
                node.parent = stack[-1]
                stack[-1].children.append(node)
            else:
                # 根级 H1，parent 为 None
                pass

            stack.append(node)
            nodes.append(node)

    return nodes


def assign_chunk_ranges(toc_nodes: list[TOCNode], chunks: list[dict]) -> list[TOCNode]:
    """
    将分块序号关联到 TOC 节点。

    chunks 已按文档顺序排好，每个 chunk 有 chunk_index。
    遍历 chunk，找到它属于哪个 TOC 节点（chunk 位置在 heading 之后、下一个同/上级 heading 之前）。
    """
    if not toc_nodes or not chunks:
        return toc_nodes

    node_idx = 0
    for ci, chunk in enumerate(chunks):
        # 找到第一个 heading_index > chunk_index 的节点
        while node_idx < len(toc_nodes) and toc_nodes[node_idx].chunk_start <= ci:
            node_idx += 1
        if node_idx > 0:
            prev = toc_nodes[node_idx - 1]
            prev.chunk_end = ci
            # 记录首段内容
            if not prev.first_chunk_text and chunk.get("text"):
                prev.first_chunk_text = chunk["text"][:200]

    # 剩余节点覆盖到末尾
    if toc_nodes:
        toc_nodes[-1].chunk_end = len(chunks) - 1

    return toc_nodes


def chunk_by_toc(markdown_text: str, toc_nodes: list[TOCNode], max_chunk_size: int = 1000) -> list[dict]:
    """
    按 TOC 分割 Markdown 为分块。

    策略：
    - 每个 ### 及以上标题 + 其正文 = 一个 chunk
    - 超过 max_chunk_size 的 chunk 内按空行再分割
    - 无 TOC（小文件）：按空行分段

    返回：
        [{"text": str, "heading_path": str, "index": int}, ...]
    """
    if not toc_nodes:
        return _chunk_flat(markdown_text, max_chunk_size)

    lines = markdown_text.split("\n")
    chunks: list[dict] = []
    current_heading = ""
    current_lines: list[str] = []
    node_index = 0

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

            level = len(m.group(1))
            heading = m.group(2).strip()
            # 构建面包屑路径
            if toc_nodes and node_index < len(toc_nodes):
                node = toc_nodes[node_index]
                parts = [node.heading]
                p = node.parent
                while p:
                    parts.insert(0, p.heading)
                    p = p.parent
                current_heading = " > ".join(parts)
                node_index += 1
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
