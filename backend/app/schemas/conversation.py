"""
对话系统数据模型 v4.0
层级：分区 → 领域 → 专题 → 对话 → 消息节点
树形消息结构，支持内联分支导航，不再有独立分支实体
"""

from __future__ import annotations

import time
from typing import Literal, Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


# ── Content Blocks（多模态内容块，不变） ──

class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    file_id: str

class AudioBlock(BaseModel):
    type: Literal["audio"] = "audio"
    file_id: str
    duration_ms: int | None = None
    transcription: str | None = None

class VideoBlock(BaseModel):
    type: Literal["video"] = "video"
    file_id: str
    duration_ms: int | None = None
    thumbnail_file_id: str | None = None
    transcription: str | None = None

class DocumentBlock(BaseModel):
    type: Literal["document"] = "document"
    file_id: str
    document_kind: str  # word/pdf/ppt/excel/markdown/code/other
    page_count: int | None = None
    text_content: str | None = None
    preview_text: str | None = None

ContentBlock = TextBlock | ImageBlock | AudioBlock | VideoBlock | DocumentBlock


# ── File Record（不变） ──

class FileRecord(BaseModel):
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
    is_cross: bool = False
    primary_partition: str = ""
    linked_partitions: list[str] = Field(default_factory=list)


# ── TreeNode（核心消息节点，branch_id → conversation_id） ──

class TreeNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    parent_id: str  # virtual root id if top-level
    children_ids: list[str] = Field(default_factory=list)  # alternative versions (for edit)
    partition_id: str
    conversation_id: str = ""  # v4: 替换 branch_id，默认为空向后兼容
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

    @model_validator(mode="before")
    @classmethod
    def _migrate_branch_id(cls, data: Any) -> Any:
        """向后兼容：branch_id → conversation_id"""
        if isinstance(data, dict):
            if "branch_id" in data and "conversation_id" not in data:
                data["conversation_id"] = data.pop("branch_id")
            elif "conversation_id" not in data:
                data["conversation_id"] = ""
        return data


# ── Link Node（不变，branch_id → conversation_id） ──

class LinkNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["link"] = "link"
    target_message_id: str
    target_partition_id: str
    target_conversation_id: str = ""
    source_partition_id: str
    source_conversation_id: str = ""
    preview_summary: str | None = None
    timestamp: float = Field(default_factory=time.time)

    @model_validator(mode="before")
    @classmethod
    def _migrate_branch_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for old, new in [("target_branch_id", "target_conversation_id"),
                              ("source_branch_id", "source_conversation_id")]:
                if old in data and new not in data:
                    data[new] = data.pop(old)
        return data


# ── Conversation（v4: 替换旧 Branch） ──

class Conversation(BaseModel):
    """专题下的一个对话线程。用户在专题下手动创建，非自动分叉。"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic_id: str
    name: str = ""
    path: list[str] = Field(default_factory=list)  # ordered message ids
    is_active: bool = True
    is_archived: bool = False
    summary: str | None = None
    summary_dirty: bool = False
    created_at: float = Field(default_factory=time.time)
    last_message_at: float = Field(default_factory=time.time)
    practice_sessions: list[str] = Field(default_factory=list)
    practice_summary: str = ""
    material_refs: list[str] = Field(default_factory=list)


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
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_id: str
    to_id: str
    relation: str = "prerequisite"
    label: str = ""
    weight: float = 1.0

class KnowledgeGraph(BaseModel):
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
    knowledge_states: dict[str, dict] = Field(default_factory=dict)
    practice_sessions: dict[str, dict] = Field(default_factory=dict)
    error_book: dict[str, list[dict]] = Field(default_factory=dict)
    knowledge_graphs: dict[str, KnowledgeGraph] = Field(default_factory=dict)
    event_log: list[dict] = Field(default_factory=list)
