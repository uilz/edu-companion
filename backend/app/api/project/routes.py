"""Project API — Routes

按 docs/modules/project-based-exploration/overview.md 与 events.md 实现。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id
from app.services import project as project_service
from app.services.project import (
    versioning,
    node_ref,
)
from app.api.project.schemas import (
    ProjectCreate,
    ProjectUpdate,
    NodeCreate,
    NodeUpdate,
    RollbackRequest,
    DiffRequest,
    TemplateCreate,
    InstantiateFromTemplate,
    MilestoneCreate,
    MilestoneUpdate,
    CopyNodesRequest,
    ExportRequest,
)
from shared.events import (
    ProjectCreated,
    ProjectNodeCreated,
    ProjectNodeUpdated,
    ProjectNodeVersionCreated,
    ProjectNodeRolledBack,
    ProjectNodeCompleted,
    ProjectNodeExported,
    ProjectMilestoneMarked,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["项目工作台"])


# ───────────────────────────────────────────────
# 辅助
# ───────────────────────────────────────────────


def _publish(event) -> None:
    """把领域事件投到 EventBus（fire-and-forget）。

    委托给 publish_event_safe (Task 架构 P0-1) — 自动适配 sync/async 上下文，
    避免在 routes 层手写 asyncio.get_running_loop() (Python 3.10+ 部分 deprecated)。
    """
    from app.infrastructure.event_bus_utils import publish_event_safe
    publish_event_safe(event)


# ───────────────────────────────────────────────
# Project CRUD
# ───────────────────────────────────────────────


@router.post("/", summary="创建项目")
async def create_project(
    body: ProjectCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    proj = project_service.create_project(
        user_id=user_id,
        name=body.name,
        description=body.description,
        template_id=body.template_id,
        template_version=body.template_version,
        tags=body.tags,
    )
    _publish(ProjectCreated(
        project_id=proj["id"],
        user_id=user_id,
        name=proj["name"],
        template_id=proj.get("template_id") or "",
        template_version=proj.get("template_version") or 0,
    ))
    return proj


@router.get("/", summary="列出项目")
async def list_projects(
    user_id: str = Depends(current_user_id),
    status: str | None = Query(default=None),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    return {"projects": project_service.list_projects(user_id, status)}


@router.get("/{project_id}", summary="查询项目")
async def get_project(
    project_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    proj = project_service.get_project(user_id, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    nodes = project_service.list_nodes(user_id, project_id)
    milestones = project_service.list_milestones(user_id, project_id)
    return {**proj, "nodes": nodes, "milestones": milestones}


@router.patch("/{project_id}", summary="更新项目")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    proj = project_service.update_project(
        user_id=user_id,
        project_id=project_id,
        name=body.name,
        description=body.description,
        status=body.status,
        tags=body.tags,
    )
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return proj


@router.delete("/{project_id}", summary="删除项目")
async def delete_project(
    project_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.delete_project(user_id, project_id)
    return {"status": "deleted", "project_id": project_id}


# ───────────────────────────────────────────────
# Node CRUD
# ───────────────────────────────────────────────


@router.post("/{project_id}/nodes", summary="创建节点")
async def create_node(
    project_id: str,
    body: NodeCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    node = project_service.create_node(
        user_id=user_id,
        project_id=project_id,
        type=body.type,
        title=body.title,
        parent_id=body.parent_id,
        description=body.description,
        tags=body.tags,
        content=body.content,
        rows=body.rows,
        columns=body.columns,
        language=body.language,
        code=body.code,
        explanation=body.explanation,
        material_id=body.material_id,
        chunk_id_range=body.chunk_id_range,
        fragments=body.fragments,
    )
    if not node:
        raise HTTPException(status_code=404, detail="项目不存在或创建失败")

    # 解析描述中的 @引用
    if node.get("description"):
        try:
            node_ref.sync_node_references(user_id, project_id, node["id"], node["description"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("sync_node_references: %s", exc)

    _publish(ProjectNodeCreated(
        project_id=project_id,
        user_id=user_id,
        node_id=node["id"],
        parent_id=node.get("parent_id") or "",
        type=node["type"],
        title=node["title"],
    ))
    return node


@router.get("/{project_id}/nodes", summary="列出节点")
async def list_nodes(
    project_id: str,
    user_id: str = Depends(current_user_id),
    include_archived: bool = False,
    parent_id: str | None = None,
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    return {"nodes": project_service.list_nodes(user_id, project_id, include_archived, parent_id)}


@router.get("/{project_id}/nodes/{node_id}", summary="查询节点")
async def get_node(
    project_id: str,
    node_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    node = project_service.get_node(user_id, project_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    return node


@router.patch("/{project_id}/nodes/{node_id}", summary="更新节点")
async def update_node(
    project_id: str,
    node_id: str,
    body: NodeUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    payload = body.model_dump(exclude_none=True)
    node = project_service.update_node(user_id, project_id, node_id, payload)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 计算 changed_fields
    changed_fields: list[str] = []
    for k in payload:
        changed_fields.append(k)

    _publish(ProjectNodeUpdated(
        project_id=project_id,
        user_id=user_id,
        node_id=node_id,
        version=node.get("version", 1),
        changed_fields=changed_fields,
    ))
    return node


@router.delete("/{project_id}/nodes/{node_id}", summary="删除节点")
async def delete_node(
    project_id: str,
    node_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.delete_node(user_id, project_id, node_id)
    return {"status": "deleted", "node_id": node_id}


@router.post("/{project_id}/nodes/{node_id}/archive", summary="归档/恢复节点")
async def archive_node(
    project_id: str,
    node_id: str,
    archived: bool = True,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    node = project_service.archive_node(user_id, project_id, node_id, archived)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    return node


@router.post("/{project_id}/nodes/{node_id}/complete", summary="标记节点完成")
async def complete_node(
    project_id: str,
    node_id: str,
    completed: bool = True,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    node = project_service.complete_node(user_id, project_id, node_id, completed)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    if completed:
        # events.md 3.1.1: ProjectNodeCompleted 只能由 user/auto/imported 触发
        _publish(ProjectNodeCompleted(
            project_id=project_id,
            user_id=user_id,
            node_id=node_id,
            completion_method="manual",
            linked_node_ids=node.get("linked_node_ids") or [],
        ))
    return node


# Task #89: 节点 status 变更 (看板拖拽用)
class NodeStatusUpdate(BaseModel):
    status: str = Field(..., description="pending | active | completed | archived")


@router.patch(
    "/{project_id}/nodes/{node_id}/status",
    summary="更新节点 status (Task #89 看板)",
)
async def update_node_status(
    project_id: str,
    node_id: str,
    body: NodeStatusUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        node = project_service.update_node_status(
            user_id, project_id, node_id, body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    return node


# Task #89: 节点 reorder (拖拽重排用)
class NodeReorderRequest(BaseModel):
    parent_id: str | None = None
    node_ids_in_order: list[str] = Field(..., min_length=1)


@router.post(
    "/{project_id}/nodes/reorder",
    summary="重排同父级节点顺序 (Task #89 拖拽)",
)
async def reorder_nodes(
    project_id: str,
    body: NodeReorderRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    ok = project_service.reorder_nodes(
        user_id, project_id, body.node_ids_in_order,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="重排失败")
    return {"status": "reordered", "count": len(body.node_ids_in_order)}


# ───────────────────────────────────────────────
# Versioning
# ───────────────────────────────────────────────


@router.get("/{project_id}/nodes/{node_id}/versions", summary="查询版本历史")
async def get_node_versions(
    project_id: str,
    node_id: str,
    limit: int = 50,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    return {"versions": versioning.list_versions(node_id, limit)}


@router.post("/{project_id}/nodes/{node_id}/rollback", summary="回滚到指定版本")
async def rollback_node(
    project_id: str,
    node_id: str,
    body: RollbackRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    # 获取当前 version（用于事件 from_version）
    node = project_service.get_node(user_id, project_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    from_version = node.get("version", 1)

    result = versioning.rollback_to_version(
        node_id=node_id,
        target_version=body.target_version,
        fields=body.fields,
    )
    if not result:
        raise HTTPException(status_code=400, detail="回滚失败：目标版本不存在或无可回滚字段")

    # 重新加载
    node = project_service.get_node(user_id, project_id, node_id)
    _publish(ProjectNodeRolledBack(
        project_id=project_id,
        user_id=user_id,
        node_id=node_id,
        from_version=from_version,
        to_version=body.target_version,
        rolled_back_fields=result.get("changed_fields", []),
    ))
    _publish(ProjectNodeVersionCreated(
        project_id=project_id,
        user_id=user_id,
        node_id=node_id,
        version_number=result.get("version_number", 0),
        is_rollback=True,
        rolled_back_from_version=body.target_version,
        change_source="rollback",
        changed_fields=result.get("changed_fields", []),
    ))
    return {"node": node, "version": result}


@router.post("/{project_id}/nodes/{node_id}/diff", summary="比较两个版本")
async def diff_node_versions(
    project_id: str,
    node_id: str,
    body: DiffRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    return versioning.diff_versions(node_id, body.version_a, body.version_b)


# ───────────────────────────────────────────────
# Milestones
# ───────────────────────────────────────────────


@router.post("/{project_id}/milestones", summary="创建里程碑")
async def create_milestone(
    project_id: str,
    body: MilestoneCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    m = project_service.create_milestone(
        user_id=user_id,
        project_id=project_id,
        milestone_name=body.milestone_name,
        snapshot_data=body.snapshot_data,
        is_user_marked=body.is_user_marked,
    )
    _publish(ProjectMilestoneMarked(
        project_id=project_id,
        user_id=user_id,
        milestone_id=m["id"],
        milestone_name=m["milestone_name"],
        snapshot_data=m["snapshot_data"],
        is_user_marked=m["is_user_marked"],
    ))
    return m


@router.get("/{project_id}/milestones", summary="列出里程碑")
async def list_milestones(
    project_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    return {"milestones": project_service.list_milestones(user_id, project_id)}


@router.get("/{project_id}/milestones/{milestone_id}", summary="查询单个里程碑")
async def get_milestone(
    project_id: str,
    milestone_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    m = project_service.get_milestone(user_id, project_id, milestone_id)
    if not m:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    return m


@router.patch("/{project_id}/milestones/{milestone_id}", summary="更新里程碑")
async def update_milestone(
    project_id: str,
    milestone_id: str,
    body: MilestoneUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    m = project_service.update_milestone(
        user_id=user_id,
        project_id=project_id,
        milestone_id=milestone_id,
        milestone_name=body.milestone_name,
        snapshot_data=body.snapshot_data,
        is_user_marked=body.is_user_marked,
    )
    if not m:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    return m


@router.delete("/{project_id}/milestones/{milestone_id}", summary="删除里程碑")
async def delete_milestone(
    project_id: str,
    milestone_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    ok = project_service.delete_milestone(user_id, project_id, milestone_id)
    if not ok:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    return {"status": "deleted", "milestone_id": milestone_id}


# ───────────────────────────────────────────────
# Templates
# ───────────────────────────────────────────────


@router.get("/_templates/all", summary="列出模板")
async def list_templates(
    category: str | None = None,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    # 确保系统预置模板已注入
    project_service.seed_default_templates()
    return {"templates": project_service.list_templates(category)}


@router.post("/_templates", summary="创建模板")
async def create_template(
    body: TemplateCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    tpl = project_service.create_template(
        user_id=user_id,
        name=body.name,
        structure=body.structure,
        description=body.description,
        category=body.category,
        placeholder_schema=body.placeholder_schema,
        is_system=False,
    )
    return tpl


@router.post("/from-template", summary="从模板创建项目")
async def create_from_template(
    body: InstantiateFromTemplate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    try:
        proj = project_service.instantiate_from_template(
            user_id=user_id,
            template_id=body.template_id,
            name=body.name,
            placeholder_values=body.placeholder_values,
        )
    except ValueError as exc:
        # instantiate_from_template 在模板不存在时 raise ValueError("模板不存在")
        # 路由层兜底为 404，避免泄漏 500
        raise HTTPException(status_code=404, detail=str(exc))
    if proj:
        _publish(ProjectCreated(
            project_id=proj["id"],
            user_id=user_id,
            name=proj["name"],
            template_id=body.template_id,
            template_version=proj.get("template_version") or 0,
        ))
    return proj


# ───────────────────────────────────────────────
# Cross-project copy
# ───────────────────────────────────────────────


@router.post("/{project_id}/copy-nodes", summary="从其他项目复制节点")
async def copy_nodes_into_project(
    project_id: str,
    body: CopyNodesRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    try:
        created = node_ref.copy_nodes_across_projects(
            user_id=user_id,
            source_project_id=body.source_project_id,
            target_project_id=project_id,
            node_ids=body.node_ids,
            mode=body.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"created": created}


# ───────────────────────────────────────────────
# Export
# ───────────────────────────────────────────────


@router.post("/{project_id}/nodes/{node_id}/export", summary="导出节点到其他模块")
async def export_node(
    project_id: str,
    node_id: str,
    body: ExportRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    project_service.ensure_tables()
    # target_module 由 Pydantic CrossModuleTarget 枚举在 schema 层校验（422），
    # 此处直接使用，不再重复 try/except
    target = body.target_module

    node = project_service.get_node(user_id, project_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    target_ref_id = body.target_ref_id or ""
    _publish(ProjectNodeExported(
        project_id=project_id,
        user_id=user_id,
        node_id=node_id,
        target_module=target,
        target_ref_id=target_ref_id,
        export_data=body.export_data,
    ))
    return {
        "status": "exported",
        "node_id": node_id,
        "target_module": target.value,
        "target_ref_id": target_ref_id,
    }
