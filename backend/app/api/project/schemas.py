"""Project API — Pydantic schemas"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.events import CrossModuleTarget


# ── Project ──


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    template_id: str | None = None
    template_version: int | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    tags: list[str] | None = None


# ── Node ──


class NodeCreate(BaseModel):
    type: int = Field(ge=1, le=7)
    title: str = Field(min_length=1, max_length=300)
    parent_id: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    content: dict | None = None
    rows: list | None = None
    columns: list | None = None
    language: str | None = None
    code: str | None = None
    explanation: str | None = None
    material_id: str | None = None
    chunk_id_range: dict | None = None
    fragments: list | None = None


class NodeUpdate(BaseModel):
    """节点更新请求（所有字段可选，缺失字段不会被版本化）。"""
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    content: dict | None = None
    rows: list | None = None
    columns: list | None = None
    language: str | None = None
    code: str | None = None
    explanation: str | None = None
    material_id: str | None = None
    chunk_id_range: dict | None = None
    fragments: list | None = None
    linked_node_ids: list[str] | None = None
    linked_material_ids: list[str] | None = None
    linked_card_ids: list[str] | None = None
    cross_project_refs: list[dict] | None = None


# ── Versioning ──


class RollbackRequest(BaseModel):
    target_version: int
    fields: list[str] | None = None  # None = 回滚所有变更字段


class DiffRequest(BaseModel):
    version_a: int
    version_b: int


# ── Templates ──


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    structure: dict
    placeholder_schema: dict | None = None
    is_system: bool = False


class InstantiateFromTemplate(BaseModel):
    template_id: str
    name: str
    placeholder_values: dict[str, Any] = Field(default_factory=dict)


# ── Milestone ──


class MilestoneCreate(BaseModel):
    milestone_name: str
    snapshot_data: dict | None = None
    is_user_marked: bool = True


class MilestoneUpdate(BaseModel):
    """里程碑更新请求（所有字段可选）。

    注意：snapshot_data 通常是创建时自动计算的快照，更新时不传则保持原值。
    重新生成 snapshot 可显式传 ``snapshot_data=None``，由 service 端重新计算。
    """
    milestone_name: str | None = None
    snapshot_data: dict | None = None
    is_user_marked: bool | None = None


# ── Cross-project copy ──


class CopyNodesRequest(BaseModel):
    source_project_id: str
    node_ids: list[str]
    mode: str = "link_copy"  # link_copy | deep_copy


# ── Export ──


class ExportRequest(BaseModel):
    target_module: CrossModuleTarget = CrossModuleTarget.FLASHCARD
    target_ref_id: str | None = None
    export_data: dict = Field(default_factory=dict)
