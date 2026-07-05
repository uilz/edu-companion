"""Project API — Service Layer

薄包装层，将 HTTP 层与领域服务解耦，便于复用 (task 层 / 定时任务)。
"""
from __future__ import annotations

import logging
from typing import Any

from app.services import project as project_service
from app.services.project import versioning, node_ref

logger = logging.getLogger(__name__)


# ── Project ──


def list_projects(user_id: str, status: str | None = None) -> list[dict]:
    project_service.ensure_tables()
    return project_service.list_projects(user_id, status)


def get_project(user_id: str, project_id: str) -> dict | None:
    project_service.ensure_tables()
    return project_service.get_project(user_id, project_id)


def create_project(
    user_id: str,
    name: str,
    description: str | None = None,
    template_id: str | None = None,
    template_version: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    project_service.ensure_tables()
    return project_service.create_project(
        user_id=user_id,
        name=name,
        description=description,
        template_id=template_id,
        template_version=template_version,
        tags=tags,
    )


def delete_project(user_id: str, project_id: str) -> bool:
    return project_service.delete_project(user_id, project_id)


# ── Node ──


def list_nodes(
    user_id: str,
    project_id: str,
    include_archived: bool = False,
    parent_id: str | None = None,
) -> list[dict]:
    project_service.ensure_tables()
    return project_service.list_nodes(user_id, project_id, include_archived, parent_id)


def get_node(user_id: str, project_id: str, node_id: str) -> dict | None:
    project_service.ensure_tables()
    return project_service.get_node(user_id, project_id, node_id)


def create_node(user_id: str, project_id: str, payload: dict) -> dict | None:
    project_service.ensure_tables()
    return project_service.create_node(user_id=user_id, project_id=project_id, **payload)


def create_node_batch(user_id: str, project_id: str, nodes: list[dict]) -> list[dict | None]:
    """批量创建节点（公共 API）。

    用于跨项目复制 / 跨模块导入 / 模板实例化等场景，
    内部走 project_service.create_node_batch，避免在外部直写 SQL。
    """
    project_service.ensure_tables()
    return project_service.create_node_batch(
        user_id=user_id, project_id=project_id, nodes=nodes,
    )


def update_node(
    user_id: str,
    project_id: str,
    node_id: str,
    payload: dict,
) -> dict | None:
    project_service.ensure_tables()
    return project_service.update_node(user_id, project_id, node_id, payload)


def delete_node(user_id: str, project_id: str, node_id: str) -> bool:
    return project_service.delete_node(user_id, project_id, node_id)


def archive_node(user_id: str, project_id: str, node_id: str, archived: bool) -> dict | None:
    return project_service.archive_node(user_id, project_id, node_id, archived)


def complete_node(user_id: str, project_id: str, node_id: str, completed: bool) -> dict | None:
    return project_service.complete_node(user_id, project_id, node_id, completed)


# ── Versioning ──


def list_versions(node_id: str, limit: int = 50) -> list[dict]:
    return versioning.list_versions(node_id, limit)


def rollback_to_version(
    node_id: str,
    target_version: int,
    fields: list[str] | None = None,
) -> dict | None:
    return versioning.rollback_to_version(node_id, target_version, fields)


def diff_versions(node_id: str, version_a: int, version_b: int) -> dict:
    return versioning.diff_versions(node_id, version_a, version_b)


# ── Milestones ──


def create_milestone(
    user_id: str,
    project_id: str,
    milestone_name: str,
    snapshot_data: dict | None = None,
    is_user_marked: bool = True,
) -> dict:
    project_service.ensure_tables()
    return project_service.create_milestone(
        user_id=user_id,
        project_id=project_id,
        milestone_name=milestone_name,
        snapshot_data=snapshot_data,
        is_user_marked=is_user_marked,
    )


def list_milestones(user_id: str, project_id: str) -> list[dict]:
    project_service.ensure_tables()
    return project_service.list_milestones(user_id, project_id)


# ── Templates ──


def list_templates(category: str | None = None) -> list[dict]:
    project_service.ensure_tables()
    project_service.seed_default_templates()
    return project_service.list_templates(category)


def create_template(
    user_id: str,
    name: str,
    structure: dict,
    description: str | None = None,
    category: str | None = None,
    placeholder_schema: dict | None = None,
) -> dict:
    project_service.ensure_tables()
    return project_service.create_template(
        user_id=user_id,
        name=name,
        structure=structure,
        description=description,
        category=category,
        placeholder_schema=placeholder_schema,
        is_system=False,
    )


def instantiate_from_template(
    user_id: str,
    template_id: str,
    name: str,
    placeholder_values: dict | None = None,
) -> dict:
    project_service.ensure_tables()
    return project_service.instantiate_from_template(
        user_id=user_id,
        template_id=template_id,
        name=name,
        placeholder_values=placeholder_values,
    )


# ── Cross-project copy ──


def copy_nodes_across_projects(
    user_id: str,
    source_project_id: str,
    target_project_id: str,
    node_ids: list[str],
    mode: str = "link_copy",
) -> list[dict]:
    project_service.ensure_tables()
    return node_ref.copy_nodes_across_projects(
        user_id=user_id,
        source_project_id=source_project_id,
        target_project_id=target_project_id,
        node_ids=node_ids,
        mode=mode,
    )


def sync_node_references(
    user_id: str,
    project_id: str,
    source_node_id: str,
    text: str,
) -> int:
    project_service.ensure_tables()
    return node_ref.sync_node_references(user_id, project_id, source_node_id, text)
