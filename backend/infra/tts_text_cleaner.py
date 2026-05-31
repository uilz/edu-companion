"""
Markdown → 纯文本清洗（TTS 语音合成用）

将 Markdown 格式转为适合朗读的纯文本：
- 数学公式 $...$ / $$...$$ → 口语朗读（用 speech-rule-engine）
- 去除所有格式标记（* # ` ~ > []() 等）
- 保留语义内容，添加适当的停顿（句号/逗号）
- 删除代码块、图片链接等不可读内容
- 表格转为简洁文本
"""

from __future__ import annotations

import re
import subprocess
import os
from pathlib import Path

# Node.js 公式→语音脚本路径
_MATH_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "scripts" / "latex_to_speech.js"
)


def _latex_to_speech(latex: str) -> str:
    """调用 Node.js speech-rule-engine 将 LaTeX 转口语"""
    if not latex or not _MATH_SCRIPT.exists():
        return ""
    try:
        result = subprocess.run(
            ["node", str(_MATH_SCRIPT), latex],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def _convert_math(text: str) -> str:
    """将文本中的 $...$ 和 $$...$$ 公式转为口语"""
    # 行间公式 $$...$$
    def repl_display(m: re.Match) -> str:
        speech = _latex_to_speech(m.group(1))
        return speech if speech else "公式省略。"

    # 行内公式 $...$
    def repl_inline(m: re.Match) -> str:
        speech = _latex_to_speech(m.group(1))
        return speech if speech else ""

    text = re.sub(r"\$\$([\s\S]*?)\$\$", repl_display, text)
    text = re.sub(r"\$([^$\n]+?)\$", repl_inline, text)
    return text


def strip_markdown_for_tts(text: str, max_chars: int = 2000) -> str:
    """将 Markdown 文本转为适合 TTS 朗读的纯文本。

    Args:
        text: 原始 Markdown 文本
        max_chars: 最大字符数（Edge-TTS 对长文本可能超时）

    Returns:
        清洗后的纯文本
    """
    if not text:
        return ""

    s = text

    # ── 0. 先转换数学公式（在清洗前）──
    s = _convert_math(s)

    # ── 1. 删除不可朗读的块 ──

    # 围栏代码块 ```...```
    s = re.sub(r"```[\s\S]*?```", "代码省略。", s)

    # 行内代码 `...`
    s = re.sub(r"`([^`\n]+?)`", r"\1", s)

    # 图片 ![alt](url) → 提示
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", lambda m: f"图片：{m.group(1)}。" if m.group(1) else "", s)

    # 链接 [text](url) → 保留文字
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)

    # 纯 URL（不跟在 [ 后面的）
    s = re.sub(r"https?://\S+", "", s)

    # HTML 标签
    s = re.sub(r"<[^>]+>", "", s)

    # ── emoji ──
    s = re.sub(
        r"[\U0001F600-\U0001F64F"   # Emoticons
        r"\U0001F300-\U0001F5FF"   # Misc Symbols and Pictographs
        r"\U0001F680-\U0001F6FF"   # Transport and Map Symbols
        r"\U0001F1E0-\U0001F1FF"   # Regional Indicator Symbols (flags)
        r"\U00002600-\U000026FF"   # Misc Symbols
        r"\U00002700-\U000027BF"   # Dingbats
        r"\U0001F900-\U0001F9FF"   # Supplemental Symbols and Pictographs
        r"\U0001FA00-\U0001FA6F"   # Chess Symbols
        r"\U0001FA70-\U0001FAFF"   # Symbols and Pictographs Extended-A
        r"\U0000FE00-\U0000FE0F"   # Variation Selectors
        r"\U0000200D"              # Zero Width Joiner
        "]+", "", s)

    # ── 2. 处理结构性标记 ──

    # 标题 # ## ### → 去标记，加句号停顿
    s = re.sub(r"^#{1,6}\s+(.+)$", r"\1。", s, flags=re.MULTILINE)

    # 水平线 --- / *** / ___
    s = re.sub(r"^[-*_]{3,}\s*$", "。", s, flags=re.MULTILINE)

    # 块引用 > text → 去 >
    s = re.sub(r"^>\s?", "", s, flags=re.MULTILINE)

    # 表格行 | a | b | → 提取文字
    s = _convert_table_rows(s)

    # 无序列表 - item / * item → 去标记加逗号
    s = re.sub(r"^[\s]*[-*+]\s+", "", s, flags=re.MULTILINE)

    # 有序列表 1. item → 去编号
    s = re.sub(r"^[\s]*\d+\.\s+", "", s, flags=re.MULTILINE)

    # 任务列表 - [x] / - [ ]
    s = re.sub(r"^[\s]*[-*+]\s+\[[ x]\]\s+", "", s, flags=re.MULTILINE)

    # ── 3. 清理行内格式标记 ──

    # 粗体 **text** / __text__
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)

    # 斜体 *text* / _text_（注意不要误匹配单词中间的 _）
    s = re.sub(r"(?<!\w)\*([^\s*](?:[^*]*[^\s*])?)\*(?!\w)", r"\1", s)
    s = re.sub(r"(?<!\w)_([^\s_](?:[^_]*[^\s_])?)_(?!\w)", r"\1", s)

    # 删除线 ~~text~~
    s = re.sub(r"~~(.+?)~~", r"\1", s)

    # 高亮 ==text==
    s = re.sub(r"==(.+?)==", r"\1", s)

    # 脚注标记 [^1] [^note]
    s = re.sub(r"\[\^[^\]]+\]", "", s)

    # 残留的方括号（如引用标签 [1]）
    s = re.sub(r"\[(\d+)\]", r"第\1项", s)

    # ── 4. 清理空白和标点 ──

    # 多个句号合并
    s = re.sub(r"。{2,}", "。", s)

    # 多个换行 → 句号停顿
    s = re.sub(r"\n{2,}", "。", s)

    # 单个换行 → 逗号
    s = re.sub(r"\n", "。", s)

    # 句号后紧跟逗号 → 去掉逗号
    s = s.replace("。，", "。")

    # 多个逗号合并
    s = re.sub(r"，{2,}", "，", s)

    # 清理残留的格式符号
    s = re.sub(r"[#*~`>\\]", "", s)

    # 多个空格
    s = re.sub(r"\s{2,}", " ", s)

    # 首尾空白
    s = s.strip()

    # 截断
    if len(s) > max_chars:
        # 在句子边界截断
        cut = s.rfind("。", 0, max_chars)
        if cut > max_chars // 2:
            s = s[: cut + 1]
        else:
            s = s[:max_chars] + "……"

    return s


def _convert_table_rows(text: str) -> str:
    """将 Markdown 表格行转为简洁文本。

    | 姓名 | 分数 | → 姓名，分数
    | --- | --- | → （删除分隔行）
    | 张三 | 95 | → 张三，95
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # 跳过分隔行 | --- | --- |
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue
        # 表格行 | a | b | → 提取单元格
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            cells = [c for c in cells if c]  # 去空
            if cells:
                result.append("，".join(cells))
        else:
            result.append(line)
    return "\n".join(result)
