"""
对话系统数据模型 v4.0
层级：分区 → 领域 → 专题 → 对话 → 消息节点
树形消息结构，支持内联分支导航，不再有独立分支实体
"""

from __future__ import annotations

import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


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
    source_conversation_id: str      # 被引用消息所在会话 ID
    char_start: int = 0              # 选中文本起始偏移
    char_end: int = 0                # 选中文本结束偏移
    quoted_text: str                 # 引用的原文

ContentBlock = TextBlock | ImageBlock | AudioBlock | VideoBlock | DocumentBlock | QuoteBlock


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


# ── Cross Partition Mark（不变） ──

class CrossPartitionMark(BaseModel):
    """跨分区标记，记录消息是否关联到其他分区"""
    is_cross: bool = False
    primary_partition: str = ""
    linked_partitions: list[str] = Field(default_factory=list)


# ── SubBranchRef（子支引用锚点） ──

class SubBranchRef(BaseModel):
    """子支引用锚点 — 记录子支是从父会话的哪条消息、哪个文本范围创建的"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_message_id: str           # 父会话中被引用的消息 ID
    char_start: int = 0              # 选中文本在消息纯文本中的起始偏移
    char_end: int = 0                # 选中文本的结束偏移
    quoted_text: str = ""            # 引用的原文（冗余存储，方便展示）
    child_conversation_id: str = ""  # 子支会话 ID
    created_at: float = Field(default_factory=time.time)


# ── TreeNode（核心消息节点，branch_id → conversation_id） ──

class TreeNode(BaseModel):
    """消息节点，构成对话的树形结构。支持多版本（编辑时在同一父节点下产生同级兄弟版本）。"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    parent_id: str  # virtual root id if top-level
    children_ids: list[str] = Field(default_factory=list)  # alternative versions (for edit)
    partition_id: str
    conversation_id: str  # v4: 替换 branch_id
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    text_summary: str = ""
    summary: str | None = None
    cross_partition: CrossPartitionMark | None = None
    role: str  # "user" | "assistant"
    timestamp: float = Field(default_factory=time.time)
    token_count: int = 0
    is_deleted: bool = False
    is_archived: bool = False
    has_modified_version: bool = False
    links_to: list[str] = Field(default_factory=list)
    linked_from: list[str] = Field(default_factory=list)
    discussed_skill_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    # ── 子支相关 ──
    has_sub_branches: bool = False
    sub_branch_ids: list[str] = Field(default_factory=list)
    sub_branch_summaries: list[dict] = Field(default_factory=list)
    # 每个 summary: {"conversation_id": str, "quoted_text": str, "summary": str}


# ── Link Node（不变，branch_id → conversation_id） ──

class LinkNode(BaseModel):
    """链接节点，记录跨对话/跨分区的消息引用关系"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["link"] = "link"
    target_message_id: str
    target_partition_id: str
    target_conversation_id: str
    source_partition_id: str
    source_conversation_id: str
    preview_summary: str | None = None
    timestamp: float = Field(default_factory=time.time)


# ── Conversation（v4: 替换旧 Branch） ──

class Conversation(BaseModel):
    """专题下的一个对话线程。用户在专题下手动创建，非自动分叉。
    path 字段按序记录消息节点 ID 列表。"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic_id: str
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
    is_temporary: bool = False          # 临时会话标记
    # ── 子支相关 ──
    parent_conversation_id: str = ""           # 父会话 ID（空=顶层会话）
    parent_sub_branch_ref: SubBranchRef | None = None  # 作为子支时的引用锚点
    sub_branch_ids: list[str] = Field(default_factory=list)  # 直接子支会话 ID 列表
    depth: int = 0                             # 子支深度（0=顶层，1=一级子支...）
    metadata: dict = Field(default_factory=dict)  # 通用元数据（如 socratic_question_count）


# ── Topic（v4 新增） ──

class Topic(BaseModel):
    """领域下的专题，例如「微积分」「线性代数」"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    domain_id: str
    name: str
    emoji: str = "📝"
    active_conversation_id: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


# ── Domain（v4 新增） ──

class Domain(BaseModel):
    """分区下的领域，例如「分析」「代数」「几何」"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    partition_id: str
    name: str
    emoji: str = "📚"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


# ── Partition（清理 active_branch_id） ──

class Partition(BaseModel):
    """顶层分区，代表一个学习方向或科目大类。包含虚拟根节点和上下文摘要。"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    subject: str = ""
    direction: str = "subject"
    emoji: str = "💬"
    color: str = "#0066FF"
    root_id: str  # virtual root node id
    context_summary: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_active_at: float = Field(default_factory=time.time)
    message_count: int = 0
    total_tokens: int = 0
    domain_tags: list[str] = Field(default_factory=list)
    domain_confidence: float = 0.0


# ── Knowledge Graph（不变） ──

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

class KGEdge(BaseModel):
    """知识图谱边，描述知识点间的关系（如 prerequisite）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_id: str
    to_id: str
    relation: str = "prerequisite"
    label: str = ""
    weight: float = 1.0

class KnowledgeGraph(BaseModel):
    """知识图谱，按分区组织的知识点网络"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    partition_id: str
    name: str = ""
    nodes: dict[str, KGNode] = Field(default_factory=dict)
    edges: list[KGEdge] = Field(default_factory=list)
    generated_by: str = "ai"
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


# ── Response Block（branch_id → conversation_id） ──

class ResponseBlock(BaseModel):
    """助教回复块，包含各类多模态回复内容（文本/练习/视频/思维导图等）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    message_id: str = ""
    partition_id: str = ""
    conversation_id: str = ""
    type: str  # text | practice | video | image | audio | mindmap | document
    status: str = "ready"
    content: dict = Field(default_factory=dict)
    order: int = 0
    sources: list[str] = Field(default_factory=list)
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
    partition_id: str = ""
    conversation_id: str = ""
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    error: str | None = None


# ── User Data Root（v4: branches→conversations, +domains, +topics） ──

class UserData(BaseModel):
    """用户数据根模型，包含 v4 完整层级结构：分区→领域→专题→对话→消息节点"""
    user_id: str
    role: str = "student"
    org_id: str | None = None
    # ── v4 层级 ──
    partitions: dict[str, Partition] = Field(default_factory=dict)
    domains: dict[str, Domain] = Field(default_factory=dict)
    topics: dict[str, Topic] = Field(default_factory=dict)
    conversations: dict[str, Conversation] = Field(default_factory=dict)  # 替换旧 branches
    nodes: dict[str, TreeNode] = Field(default_factory=dict)
    link_nodes: dict[str, LinkNode] = Field(default_factory=dict)
    files: dict[str, FileRecord] = Field(default_factory=dict)
    active_partition_id: str | None = None
    response_blocks: dict[str, 'ResponseBlock'] = Field(default_factory=dict)
    background_jobs: dict[str, 'BackgroundJob'] = Field(default_factory=dict)

    # Legacy field kept for JSONB backward compatibility; data migrated to separate table.
    practice_sessions: dict[str, dict] = Field(default_factory=dict)
    # Legacy field kept for JSONB backward compatibility; data migrated to separate table.
    error_book: dict[str, list[dict]] = Field(default_factory=dict)
    knowledge_graphs: dict[str, KnowledgeGraph] = Field(default_factory=dict)
    event_log: list[dict] = Field(default_factory=list)
