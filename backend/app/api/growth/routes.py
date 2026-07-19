"""Growth API — GrowthEngine query endpoints.

Contract I7: Queryable history, not a dashboard. Today page shows narrative highlights.
"""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.application.di import get_growth_engine
from app.domain.auth.dependencies import current_user_id
from app.infrastructure.db.repositories.growth_repo import GrowthRepo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/growth", tags=["growth-engine"])


class MilestoneResponse(BaseModel):
    id: str
    workspace_id: str
    type: str
    title: str = ""
    description: str = ""
    concept_id: str = ""
    day_number: int = 0
    detected_at: str = ""


class SnapshotResponse(BaseModel):
    id: str
    workspace_id: str
    day_number: int
    session_count: int = 0
    concept_count: int = 0
    connection_count: int = 0
    top_concepts: str = ""
    created_at: str = ""


class TrajectoryResponse(BaseModel):
    from_day: int
    to_day: int
    delta_sessions: int = 0
    delta_concepts: int = 0


class ComputeSnapshotRequest(BaseModel):
    workspace_id: str


@router.get("/{workspace_id}/milestones", response_model=list[MilestoneResponse])
async def get_milestones(workspace_id: str, user_id: str = Depends(current_user_id)):
    """I3: Get milestones for a workspace. Contract: workspace-level (I1)."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    repo = GrowthRepo()
    milestones = repo.find_milestones(UUID(workspace_id))
    return [MilestoneResponse(
        id=str(m.id), workspace_id=str(m.workspace_id),
        type=m.type, title=m.title, description=m.description,
        concept_id=m.concept_id, day_number=m.day_number,
        detected_at=str(m.detected_at),
    ) for m in milestones]


@router.get("/milestones", response_model=list[MilestoneResponse])
async def get_user_milestones(user_id: str = Depends(current_user_id)):
    """I1: User-level milestones across all workspaces."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    repo = GrowthRepo()
    milestones = repo.find_milestones_by_user(UUID(user_id))
    return [MilestoneResponse(
        id=str(m.id), workspace_id=str(m.workspace_id),
        type=m.type, title=m.title, description=m.description,
        concept_id=m.concept_id, day_number=m.day_number,
        detected_at=str(m.detected_at),
    ) for m in milestones]


@router.get("/{workspace_id}/snapshots", response_model=list[SnapshotResponse])
async def get_snapshots(workspace_id: str, user_id: str = Depends(current_user_id)):
    """I4: Get daily evolution snapshots."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    repo = GrowthRepo()
    snaps = repo.find_snapshots(UUID(workspace_id))
    return [SnapshotResponse(
        id=str(s.id), workspace_id=str(s.workspace_id),
        day_number=s.day_number, session_count=s.session_count,
        concept_count=s.concept_count, connection_count=s.connection_count,
        top_concepts=s.top_concepts, created_at=str(s.created_at),
    ) for s in snaps]


@router.post("/{workspace_id}/snapshots", response_model=SnapshotResponse)
async def compute_snapshot(workspace_id: str, user_id: str = Depends(current_user_id)):
    """Manually trigger snapshot computation. Contract I5: non-destructive."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    engine = get_growth_engine()
    snap = await engine.compute_snapshot(workspace_id, user_id)
    return SnapshotResponse(
        id=str(snap.id), workspace_id=str(snap.workspace_id),
        day_number=snap.day_number, session_count=snap.session_count,
        concept_count=snap.concept_count, connection_count=snap.connection_count,
        top_concepts=snap.top_concepts, created_at=str(snap.created_at),
    )


@router.get("/{workspace_id}/trajectory", response_model=TrajectoryResponse)
async def get_trajectory(workspace_id: str,
                          from_day: int = Query(default=1),
                          to_day: int = Query(default=30),
                          user_id: str = Depends(current_user_id)):
    """I6: Cross-time comparison query."""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    engine = get_growth_engine()
    traj = await engine.get_trajectory(workspace_id, from_day, to_day)
    return TrajectoryResponse(**traj)
