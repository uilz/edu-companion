"""
对话系统数据模型
基于树形结构的多分支对话系统，支持分区、分支、消息节点、跨分区链接等
"""

from __future__ import annotations

import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ── Content Blocks（多模态内容块） ──

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


# ── File Record ──

class FileRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    original_name: str
    storage_path: str
    mime_type: str
    file_size: int
    file_type: str  # image/audio/video/document
    processing_status: str = "pending"  # pending/processing/done/failed
    transcription: str | None = None
    text_content: str | None = None
    thumbnail_path: str | None = None
    ocr_text: str | None = None
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    page_count: int | None = None
    created_at: float = Field(default_factory=time.time)


# ── Cross Partition Mark ──

class CrossPartitionMark(BaseModel):
    is_cross: bool = False
    primary_partition: str = ""
    linked_partitions: list[str] = Field(default_factory=list)


# ── Tree Node ──

class TreeNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    parent_id: str  # virtual root id if top-level
    children_ids: list[str] = Field(default_factory=list)
    partition_id: str
    branch_id: str
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


# ── Link Node ──

class LinkNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["link"] = "link"
    target_message_id: str
    target_partition_id: str
    target_branch_id: str
    source_partition_id: str
    source_branch_id: str
    preview_summary: str | None = None
    timestamp: float = Field(default_factory=time.time)


# ── Branch ──

class Branch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    partition_id: str
    name: str = ""
    fork_point_id: str | None = None
    path: list[str] = Field(default_factory=list)  # ordered message ids from root to leaf
    is_active: bool = True
    is_archived: bool = False
    summary: str | None = None
    summary_dirty: bool = False
    created_at: float = Field(default_factory=time.time)
    last_message_at: float = Field(default_factory=time.time)
    # P0: 练习系统联动
    practice_sessions: list[str] = Field(default_factory=list)  # 关联的练习session_id
    practice_summary: str = ""  # "已练12题,正确率70%,薄弱:导数"


# ── Partition ──

class Partition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    subject: str = ""
    direction: str = "subject"  # subject/skill/project/interest/life
    emoji: str = "💬"
    color: str = "#0066FF"
    root_id: str  # virtual root node id
    active_branch_id: str = ""
    context_summary: str = ""
    summary_branches: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_active_at: float = Field(default_factory=time.time)
    message_count: int = 0
    total_tokens: int = 0


# ── User Data Root ──

class UserData(BaseModel):
    user_id: str
    # P0: 角色/组织隔离预留
    role: str = "student"  # student | teacher | admin
    org_id: str | None = None  # 组织/班级ID
    partitions: dict[str, Partition] = Field(default_factory=dict)
    branches: dict[str, Branch] = Field(default_factory=dict)
    nodes: dict[str, TreeNode] = Field(default_factory=dict)  # all nodes indexed by id
    link_nodes: dict[str, LinkNode] = Field(default_factory=dict)
    files: dict[str, FileRecord] = Field(default_factory=dict)
    active_partition_id: str | None = None
    response_blocks: dict[str, 'ResponseBlock'] = Field(default_factory=dict)
    background_jobs: dict[str, 'BackgroundJob'] = Field(default_factory=dict)
    # P2: 练习系统持久化（知识状态 + 练习会话）
    knowledge_states: dict[str, dict] = Field(default_factory=dict)  # skill_id → KnowledgeState dict
    practice_sessions: dict[str, dict] = Field(default_factory=dict)  # session_id → PracticeSession dict
    error_book: dict[str, list[dict]] = Field(default_factory=dict)  # user_id → ErrorBookEntry dicts


# ── Response Block（多模态响应块） ──

class ResponseBlock(BaseModel):
    """助手回复的内容块"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    message_id: str = ""
    partition_id: str = ""
    branch_id: str = ""
    type: str  # text | practice | video | image | mindmap | document
    status: str = "ready"  # streaming | ready | generating | failed
    content: dict = Field(default_factory=dict)
    order: int = 0
    sources: list[str] = Field(default_factory=list)  # 引用溯源 [来源: xxx]
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class BackgroundJob(BaseModel):
    """后台任务"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    status: str = "queued"  # queued | processing | done | failed
    params: dict = Field(default_factory=dict)
    result: dict | None = None
    progress: float = 0.0
    block_id: str = ""  # 关联的ResponseBlock ID
    partition_id: str = ""
    branch_id: str = ""
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    error: str | None = None
