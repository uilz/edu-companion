"""Planning 数据转换器 — DB row → API dict"""
from __future__ import annotations

import json


def row_to_plan_item(r: dict) -> dict:
    """normalize plan_items row → API dict"""
    linked = r.get("linked_node_ids")
    if isinstance(linked, str):
        try:
            linked = json.loads(linked)
        except (json.JSONDecodeError, TypeError):
            linked = []
    metadata = r.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "source_module": r["source_module"],
        "target_type": r["target_type"],
        "target_ref_id": r["target_ref_id"],
        "title": r["title"],
        "description": r.get("description", ""),
        "estimated_minutes": r.get("estimated_minutes") or 0,
        "actual_minutes": r.get("actual_minutes"),
        "linked_node_ids": linked or [],
        "priority": r.get("priority") or 0,
        "is_mood_rule_affected": bool(r.get("is_mood_rule_affected")),
        "status": r.get("status", "pending"),
        "scheduled_for": r.get("scheduled_for"),
        "started_at": r.get("started_at"),
        "completed_at": r.get("completed_at"),
        "skipped_at": r.get("skipped_at"),
        "plan_date": r.get("plan_date"),
        "metadata": metadata or {},
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }


def row_to_goal(r: dict) -> dict:
    target = r.get("target_value") or 0
    current = r.get("current_value") or 0
    progress = min(1.0, current / target) if target > 0 else 0.0
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "title": r["title"],
        "description": r.get("description", ""),
        "target_module": r["target_module"],
        "target_metric": r["target_metric"],
        "target_value": target,
        "current_value": current,
        "deadline": r.get("deadline"),
        "status": r.get("status", "active"),
        "progress_pct": progress,
        "created_at": r.get("created_at"),
        "completed_at": r.get("completed_at"),
    }


def row_to_review(r: dict) -> dict:
    data = r.get("summary_data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            data = {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "period_type": r["period_type"],
        "period_start": r["period_start"],
        "period_end": r["period_end"],
        "summary_data": data or {},
        "user_note": r.get("user_note", ""),
        "created_at": r.get("created_at"),
    }


def row_to_view_layout(r: dict) -> dict:
    def _j(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v or {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "name": r["name"],
        "view_type": r["view_type"],
        "filters": _j(r.get("filters")),
        "layout": _j(r.get("layout")),
        "is_default": bool(r.get("is_default")),
        "created_at": r.get("created_at"),
    }


def row_to_confirmation(r: dict) -> dict:
    """normalize plan_item_confirmations row → API dict"""
    linked = r.get("linked_node_ids")
    if isinstance(linked, str):
        try:
            linked = json.loads(linked)
        except (json.JSONDecodeError, TypeError):
            linked = []
    metadata = r.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "request_id": r["request_id"],
        "suggestion_id": r.get("suggestion_id"),
        "source_module": r.get("source_module", "secretary"),
        "target_type": r["target_type"],
        "target_ref_id": r["target_ref_id"],
        "title": r["title"],
        "description": r.get("description", ""),
        "priority": r.get("priority") or 0,
        "estimated_minutes": r.get("estimated_minutes") or 10,
        "linked_node_ids": linked or [],
        "proposed_scheduled_for": r.get("proposed_scheduled_for"),
        "status": r.get("status", "pending"),
        "expires_at": r.get("expires_at"),
        "accepted_at": r.get("accepted_at"),
        "dismissed_at": r.get("dismissed_at"),
        "metadata": metadata or {},
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }
