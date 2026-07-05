"""
统一工具注册表 — 单一定义源（Single Source of Truth）

  所有工具的中文名、图标、LLM schema、block 类型、快慢分类 均在此定义。
  其他模块（tool_repository / tool_executor）从本文件派生所需结构，不再各自维护。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class ToolInfo:
    """单个工具的完整元信息"""
    name: str                        # 工具名（LLM function name）
    zh_name: str                     # 中文显示名
    icon: str                        # emoji 图标
    description: str                 # LLM function calling 描述
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    required: list[str] = field(default_factory=list)
    block_type: str | None = None    # 对应 ResponseBlock.type（video / practice / image / ...）
    is_slow: bool = False            # 是否耗时工具（需要后台轮询）
    is_inline: bool = False          # 是否在 pipeline 内直接处理（不经过 ToolExecutor）
    is_suspending: bool = False      # 是否需要挂起管线等待外部输入（如用户回答提问）


# ══════════════════════════════════════════════════════════════
#  核心对话工具
# ══════════════════════════════════════════════════════════════

ALL_TOOL_INFO: dict[str, ToolInfo] = {
    # ── 内联工具 ──
    "rename_conversation": ToolInfo(
        name="rename_conversation",
        zh_name="自动命名会话",
        icon="✏️",
        description="自动为对话命名（2-8 字），概括用户问题的核心主题",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "对话标题，2-8 字，概括用户问题的核心主题",
                },
            },
            "required": ["name"],
        },
        is_inline=True,
    ),

    # ── 多媒体/搜索 ──
    "search_media": ToolInfo(
        name="search_media",
        zh_name="搜索学习资源",
        icon="🔍",
        description="搜索B站/YouTube/知乎等平台的学习视频和教程",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索内容/知识点"},
                "platforms": {"type": "array", "items": {"type": "string"},
                              "description": "平台: bilibili/youtube/zhihu/baidu_wenku"},
            },
            "required": ["query"],
        },
        block_type="video",
    ),

    # ── 练习 ──
    "generate_practice": ToolInfo(
        name="generate_practice",
        zh_name="生成练习题",
        icon="📝",
        description="生成练习题。支持指定题库名称",
        parameters={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "学科"},
                "knowledge_point": {"type": "string", "description": "知识点"},
                "difficulty": {"type": "string", "enum": ["基础", "进阶", "挑战"], "default": "进阶"},
                "count": {"type": "integer", "description": "题目数量", "default": 2},
                "bank_name": {"type": "string", "description": "目标题库名称"},
            },
            "required": ["subject"],
        },
        block_type="practice",
    ),

    # ── 题库 ──
    "query_question_banks": ToolInfo(
        name="query_question_banks",
        zh_name="查询题库",
        icon="📚",
        description="查询已有的题库和题目",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_banks", "get_bank", "search_questions"],
                           "description": "list_banks/get_bank/search_questions"},
                "bank_id": {"type": "string", "description": "题库ID"},
                "keyword": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 20},
            },
            "required": ["action"],
        },
    ),
    "create_question_bank": ToolInfo(
        name="create_question_bank",
        zh_name="创建题库",
        icon="➕",
        description="创建一个新的题库",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "题库名称，如「编程-算法基础」"},
                "description": {"type": "string", "description": "题库描述"},
                "subject": {"type": "string", "description": "所属学科"},
            },
            "required": ["name"],
        },
    ),

    # ── 提问工具 ──
    "ask_question": ToolInfo(
        name="ask_question",
        zh_name="提问",
        icon="❓",
        description="向用户提问以促进互动，支持选择题或开放问答题。适用于引导思考、确认理解、收集意见等场景。",
        is_suspending=True,
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["choice", "open"],
                    "description": "提问类型：choice=选择题（提供选项让学生选择），open=开放问答题（让学生自由回答）",
                },
                "questions": {
                    "type": "array",
                    "description": "问题列表（支持一次性问多个问题）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "问题内容，清晰明确",
                            },
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "选择题选项（type=choice 时必填，建议2-4个选项）",
                            },
                        },
                        "required": ["question"],
                    },
                },
            },
            "required": ["type", "questions"],
        },
        block_type="question",
    ),

    # ── 秘书诊断 ──
    "secretary_diagnose": ToolInfo(
        name="secretary_diagnose",
        zh_name="学习诊断分析",
        icon="🩺",
        description="诊断当前学习状态，生成学习建议",
        parameters={
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["full", "quick"],
                          "description": "full=全量诊断, quick=快速评估", "default": "quick"},
            },
            "required": [],
        },
        block_type="tool_block",
    ),

    # ── 生成类（慢工具）──
    "generate_image": ToolInfo(
        name="generate_image",
        zh_name="生成图片",
        icon="🖼️",
        description="根据描述生成图片",
        block_type="image",
        is_slow=True,
    ),
    "generate_mindmap": ToolInfo(
        name="generate_mindmap",
        zh_name="生成思维导图",
        icon="🧠",
        description="根据知识点生成思维导图",
        block_type="mindmap",
        is_slow=True,
    ),
    "generate_document": ToolInfo(
        name="generate_document",
        zh_name="生成文档",
        icon="📄",
        description="根据内容生成结构化文档",
        block_type="document",
        is_slow=True,
    ),

    # ══════════════════════════════════════════
    #  知识树操作工具
    # ══════════════════════════════════════════
    "knowledge_add_node": ToolInfo(
        name="knowledge_add_node",
        zh_name="添加知识点",
        icon="🌱",
        description="在当前知识树节点下添加一个新子节点",
        parameters={
            "type": "object",
            "properties": {
                "parent_id": {"type": "string", "description": "父节点 ID"},
                "label": {"type": "string", "description": "节点名称/标题"},
                "brief": {"type": "string", "description": "节点简介说明"},
                "level": {"type": "string", "enum": ["domain", "topic", "concept"],
                          "description": "节点层级", "default": "concept"},
            },
            "required": ["parent_id", "label"],
        },
    ),
    "knowledge_edit_node": ToolInfo(
        name="knowledge_edit_node",
        zh_name="编辑知识点",
        icon="✍️",
        description="编辑知识树节点的信息（名称、简介等）",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "要编辑的节点 ID"},
                "label": {"type": "string", "description": "新的节点名称"},
                "brief": {"type": "string", "description": "新的节点简介"},
                "emoji": {"type": "string", "description": "节点 emoji 图标"},
            },
            "required": ["node_id"],
        },
    ),
    "knowledge_expand_node": ToolInfo(
        name="knowledge_expand_node",
        zh_name="展开知识树",
        icon="🌳",
        description="AI 自动为指定知识节点生成子节点，扩充知识树",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "要展开的节点 ID"},
                "depth": {"type": "integer", "description": "展开深度", "default": 1},
            },
            "required": ["node_id"],
        },
        is_slow=True,
    ),
    "knowledge_delete_node": ToolInfo(
        name="knowledge_delete_node",
        zh_name="删除节点",
        icon="🗑️",
        description="删除知识树节点",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "要删除的节点 ID"},
            },
            "required": ["node_id"],
        },
    ),
    "knowledge_add_relation": ToolInfo(
        name="knowledge_add_relation",
        zh_name="建立知识关联",
        icon="🔗",
        description="在两个知识树节点之间建立关联边",
        parameters={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "源节点 ID"},
                "target_id": {"type": "string", "description": "目标节点 ID"},
                "relation_type": {"type": "string", "description": "关系类型: prerequisite/extends/similar"},
            },
            "required": ["source_id", "target_id"],
        },
    ),
    "knowledge_get_node_context": ToolInfo(
        name="knowledge_get_node_context",
        zh_name="查询节点上下文",
        icon="🔎",
        description="查询知识树节点的上下文信息（父链/子链/关联节点）",
        parameters={
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "节点 ID"},
            },
            "required": ["node_id"],
        },
    ),
    "knowledge_search_nodes": ToolInfo(
        name="knowledge_search_nodes",
        zh_name="搜索知识节点",
        icon="🔍",
        description="在知识树中搜索节点",
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回结果数量", "default": 10},
            },
            "required": ["keyword"],
        },
    ),
    "knowledge_recommend": ToolInfo(
        name="knowledge_recommend",
        zh_name="学习推荐",
        icon="💡",
        description="基于当前知识树，推荐学习路径和薄弱点",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    # ── LanguageRoom 共享工具 (Task #35) ──
    "tool_vocabulary_capture": ToolInfo(
        name="tool_vocabulary_capture",
        zh_name="捕获生词",
        icon="📝",
        description="在 LanguageRoom 房间内捕获生词, 自动生成 FlashCard 数据卡",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "room_id": {"type": "string"},
                "transcript_id": {"type": "string"},
                "word": {"type": "string"},
                "translation": {"type": "string"},
            },
            "required": ["user_id", "room_id", "word"],
        },
    ),
    "tool_error_mark": ToolInfo(
        name="tool_error_mark",
        zh_name="标记错误",
        icon="❌",
        description="在 LanguageRoom 房间内标记用户转写片段为错误, 复用 ErrorBookEntry",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "room_id": {"type": "string"},
                "transcript_id": {"type": "string"},
                "error_type": {"type": "string"},
                "linked_node_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["user_id", "room_id", "transcript_id"],
        },
    ),
    "tool_message_post": ToolInfo(
        name="tool_message_post",
        zh_name="发送消息",
        icon="💬",
        description="在 LanguageRoom 房间内发送文字辅助消息, 复用 ExplainCard 浮卡",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "room_id": {"type": "string"},
                "text": {"type": "string"},
                "message_type": {"type": "string"},
            },
            "required": ["user_id", "room_id", "text"],
        },
    ),
    "tool_knowledge_search": ToolInfo(
        name="tool_knowledge_search",
        zh_name="知识搜索",
        icon="🔍",
        description="在知识树中搜索节点, AI 辅助者 (ai_helper) 在生成回答前调用以获取相关上下文",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["user_id", "query"],
        },
    ),
}


# ══════════════════════════════════════════════════════════════
#  派生辅助函数
# ══════════════════════════════════════════════════════════════

def get_all_tool_definitions() -> list[dict]:
    """生成 LLM function calling schema 列表（包含内联工具如 rename_conversation）"""
    defs = []
    for info in ALL_TOOL_INFO.values():
        schema = {
            "type": "function",
            "function": {
                "name": info.name,
                "description": info.description,
                "parameters": info.parameters,
            },
        }
        defs.append(schema)
    return defs


def get_tool_display_map() -> dict[str, dict]:
    """工具名 → {zh, icon} 映射（供 API 返回给前端）"""
    return {
        name: {"zh": info.zh_name, "icon": info.icon}
        for name, info in ALL_TOOL_INFO.items()
    }


def get_tool_block_types() -> dict[str, str]:
    """工具名 → ResponseBlock.type 映射"""
    return {
        name: info.block_type
        for name, info in ALL_TOOL_INFO.items()
        if info.block_type
    }


def get_fast_tools() -> set[str]:
    return {name for name, info in ALL_TOOL_INFO.items() if not info.is_slow}


def get_slow_tools() -> set[str]:
    return {name for name, info in ALL_TOOL_INFO.items() if info.is_slow}


def get_suspending_tools() -> set[str]:
    """返回所有需要挂起管线等待外部输入的工具名集合"""
    return {name for name, info in ALL_TOOL_INFO.items() if info.is_suspending}
