"""题库导入服务 — docx/xlsx/txt/json 多格式解析

流程:
1. upload → 上传文件 + 解析为结构化题目列表
2. preview → AI 修正 + 认知节点匹配（返回预览）
3. confirm → 确认导入 questions 表

子模块：
- parser: 文件/文本/JSON 解析 + AI 修正 + 认知节点匹配
- service: 预览/确认/导入历史 业务流程编排
"""
from __future__ import annotations

import re

# ── 正则模式（共享）──

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

TYPE_KEYWORDS = {
    "单选": "single", "single": "single",
    "多选": "multiple", "multiple": "multiple",
    "判断": "judge", "judge": "judge",
    "填空": "fill", "fill": "fill",
    "简答": "essay", "essay": "essay",
}

# ── 公开 API（便捷导入）──

from .parser import (
    parse_questions_from_text,
    parse_questions_from_json,
    parse_file,
    ai_correct_question,
    match_cognitive_nodes,
)
from .service import (
    preview_import,
    confirm_import,
    get_import_history,
)

__all__ = [
    "parse_questions_from_text",
    "parse_questions_from_json",
    "parse_file",
    "ai_correct_question",
    "match_cognitive_nodes",
    "preview_import",
    "confirm_import",
    "get_import_history",
]
