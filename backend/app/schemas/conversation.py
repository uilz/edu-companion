"""
对话系统数据模型
层级：DirectoryNode 统一模型 → 对话 → 消息节点
树形消息结构，支持内联分支导航，不再有独立分支实体
"""

from __future__ import annotations

import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.directory_node import DirectoryNode


# ── Content Blocks（多模态内容块，不变） ──

class TextBlock(BaseModel):
    """纯文本内容块"""
    type: Literal["text"] = "text"
    text: str

class ImageBlock(BaseModel):
    """图片内容块"""
    type: Literal["image"] = "image"
    file_id: str

class AudioBlock(BaseModel):
    """音频内容块，含可选的转写文本"""
    type: Literal["audio"] = "audio"
    file_id: str
    duration_ms: int | None = None
    transcription: str | None = None

class VideoBlock(BaseModel):
    """视频内容块，含可选的缩略图和转写"""
    type: Literal["video"] = "video"
    file_id: str
    duration_ms: int | None = None
    thumbnail_file_id: str | None = None
    transcription: str | None = None

class DocumentBlock(BaseModel):
    """文档内容块，支持 word/pdf/ppt/excel/markdown/code 等类型"""
    type: Literal["document"] = "document"
    file_id: str
    document_kind: str  # word/pdf/ppt/excel/markdown/code/other
    page_count: int | None = None
    text_content: str | None = None
    preview_text: str | None = None

class QuoteBlock(BaseModel):
    """引用内容块 — 类似文件附件，展示引用的原文"""
    type: Literal["quote"] = "quote"
    source_message_id: str           # 被引用消息 ID
    source_conv_id: str      # 被引用消息所在会话 ID
    char_start: int = 0              # 选中文本起始偏移
    char_end: int = 0                # 选中文本结束偏移
    quoted_text: str                 # 引用的原文

class ToolBlock(BaseModel):
    """工具调用块 — 记录工具调用的全生命周期"""
    type: Literal["tool"] = "tool"
    tool_call_id: str = ""
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    status: str = "pending"  # pending | running | done | error
    result_block_type: str | None = None  # 结果的 block 类型（text/image/video...）
    result_content: dict | None = None    # 结果数据
    error: str | None = None
    tool_round: int = 0

class ReasoningBlock(BaseModel):
    """推理思考块 — LLM 的 reasoning_content"""
    type: Literal["reasoning"] = "reasoning"
    text: str = ""
    status: str = "streaming"  # streaming | done

ContentBlock = TextBlock | ImageBlock | AudioBlock | VideoBlock | DocumentBlock | QuoteBlock | ToolBlock | ReasoningBlock


# ── File Record（不变） ──

class FileRecord(BaseModel):
    """文件记录，记录上传的媒体/文档文件元数据"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    original_name: str
    storage_path: str
    mime_type: str
    file_size: int
    file_type: str  # image/audio/video/document
    processing_status: str = "pending"
    transcription: str | None = None
    text_content: str | None = None
    thumbnail_path: str | None = None
    ocr_text: str | None = None
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    page_count: int | None = None
    created_at: float = Field(default_factory=time.time)


# ── SubBranchRef（子支引用锚点） ──

class SubBranchRef(BaseModel):
    """子支引用锚点 — 记录子支是从父会话的哪条消息、哪个文本范围创建的"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_message_id: str           # 父会话中被引用的消息 ID
    char_start: int = 0              # 选中文本在消息纯文本中的起始偏移
    char_end: int = 0                # 选中文本的结束偏移
    quoted_text: str = ""            # 引用的原文（冗余存储，方便展示）
    child_conv_id: str = ""  # 子支会话 ID
    created_at: float = Field(default_factory=time.time)


# ── TreeNode（已迁移 → MessageNode in directory_node.py） ──
# 保留 TreeNode 别名使旧导入兼容。引用 MessageNode 的代码应直接:
#   from app.schemas.directory_node import MessageNode
from app.schemas.directory_node import MessageNode as TreeNode


# ── Link Node ──

class LinkNode(BaseModel):
    """链接节点，记录跨对话的消息引用关系"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["link"] = "link"
    target_message_id: str
    target_conv_id: str
    source_conv_id: str
    preview_summary: str | None = None
    timestamp: float = Field(default_factory=time.time)


# ── Conversation──

class Conversation(BaseModel):
    """对话线程，可挂载到任意 DirectoryNode 层级下。
    type 字段区分对话类型：normal（对话系统）/ tree_exploration（知识树探索）/ temporary（临时）。
    直接父级通过 DirectoryNode.parent_id 确定，不再在 Conversation 中冗余存储。"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = "normal"       # "normal" | "tree_exploration" | "temporary"
    # ── 对话属性 ──
    name: str = ""
    path: list[str] = Field(default_factory=list)  # ordered message ids
    is_active: bool = True
    is_archived: bool = False
    summary: str | None = None
    summary_dirty: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_message_at: float = Field(default_factory=time.time)
    practice_sessions: list[str] = Field(default_factory=list)
    practice_summary: str = ""
    material_refs: list[str] = Field(default_factory=list)
    # ── Phase 8 融合会话 ──
    primary_node_id: str | None = None  # 关联 cognitive_nodes.id (topic 级)
    is_temporary: bool = False          # 临时会话标记（旧字段，逐步迁移到 type）
    # ── 子支相关 ──
    parent_conv_id: str = ""           # 父会话 ID（空=顶层会话）
    parent_sub_branch_ref: SubBranchRef | None = None  # 作为子支时的引用锚点
    sub_branch_ids: list[str] = Field(default_factory=list)  # 直接子支会话 ID 列表
    depth: int = 0                             # 子支深度（0=顶层，1=一级子支...）
    metadata: dict = Field(default_factory=dict)  # 通用元数据（如 socratic_question_count）


# ── Knowledge Graph ──

class KGNode(BaseModel):
    """知识图谱节点，代表一个知识点概念"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    description: str = ""
    mastery: float = 0.0
    mastery_level: str = "未接触"
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    created_by: str = "ai"
    created_at: float = Field(default_factory=time.time)
    conv_ids: list[str] = Field(default_factory=list)

class KGEdge(BaseModel):
    """知识图谱边，描述知识点间的关系（如 prerequisite）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_id: str
    to_id: str
    relation: str = "prerequisite"
    label: str = ""
    weight: float = 1.0

class KnowledgeGraph(BaseModel):
    """知识图谱，由directory_node (dir/conv) 关联组织，不再依赖 dir_id"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    nodes: dict[str, KGNode] = Field(default_factory=dict)
    edges: list[KGEdge] = Field(default_factory=list)
    generated_by: str = "ai"
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


# ── Response Block ──

class ResponseBlock(BaseModel):
    """助教回复块，包含各类多模态回复内容（文本/练习/视频/思维导图等）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    message_id: str = ""
    dir_id: str = ""
    conv_id: str = ""
    type: str  # text | practice | video | image | audio | mindmap | document
    status: str = "ready"
    content: dict = Field(default_factory=dict)
    order: int = 0
    sources: list[str] = Field(default_factory=list)
    tool_name: str = ""  # 调用此块的工具名（如 search_media）
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class BackgroundJob(BaseModel):
    """后台任务记录，用于异步处理长时间运行的操作"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    status: str = "queued"
    params: dict = Field(default_factory=dict)
    result: dict | None = None
    progress: float = 0.0
    block_id: str = ""
    conv_id: str = ""
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    error: str | None = None


# ── User Data Root（DirectoryNode 版本） ──

class UserData(BaseModel):
    """用户数据根模型 — DirectoryNode 版本"""
    user_id: str
    role: str = "student"
    org_id: str | None = None

    # ── 统一目录 (取代 partitions/domains/topics/conversations) ──
    directory_nodes: dict[str, 'DirectoryNode'] = Field(default_factory=dict)

    # ── 消息节点 ──
    nodes: dict[str, TreeNode] = Field(default_factory=dict)  # 消息 (保留 TreeNode 名称兼容)
    link_nodes: dict[str, LinkNode] = Field(default_factory=dict)
    files: dict[str, FileRecord] = Field(default_factory=dict)
    response_blocks: dict[str, 'ResponseBlock'] = Field(default_factory=dict)
    background_jobs: dict[str, 'BackgroundJob'] = Field(default_factory=dict)

    # Legacy fields
    practice_sessions: dict[str, dict] = Field(default_factory=dict)
    error_book: dict[str, list[dict]] = Field(default_factory=dict)
    knowledge_graphs: dict[str, KnowledgeGraph] = Field(default_factory=dict)
    event_log: list[dict] = Field(default_factory=list)

    # ── 秘书系统数据 ──
    secretary_prefs: dict = Field(default_factory=lambda: {
        "enabled_extensions": ["review_reminder", "fatigue_manager", "daily_brief"],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "max_proactive_per_day": 5,
    })
    policy_memory: dict = Field(default_factory=lambda: {
        "ignore_counts": {},
        "accept_counts": {},
    })

    # — 旧模型合成属性已删除 (DirectoryNode 为唯一模型) —
