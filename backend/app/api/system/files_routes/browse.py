"""文件管理 — 浏览：列表/详情/搜索/下载/TOC/分块/标签/统计"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])


def _serialize_dt(val) -> str:
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


# ── 列表 ──

@router.get("", summary="文件列表")
async def list_files(
    purpose: str = Query(default=None),
    status: str = Query(default=None),
    file_type_filter: str = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=100),
    search: str = Query(default=None),
    tag: str = Query(default=None),
    parent_id: str = Query(default=None),
    include_folders: bool = Query(default=True),
    include_deleted: bool = Query(default=False),
    uid: str = Depends(current_user_id),
):
    """获取文件列表（分页、过滤）"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["m.user_id = %s"]
    params: list[Any] = [uid]

    if include_deleted:
        conditions.append("m.is_deleted = TRUE")
    else:
        conditions.append("m.is_deleted = FALSE")

    if not include_folders:
        conditions.append("m.is_folder = FALSE")

    if purpose:
        conditions.append("m.purpose = %s")
        params.append(purpose)
    if status:
        conditions.append("m.status = %s")
        params.append(status)
    if file_type_filter:
        conditions.append("m.file_type = %s")
        params.append(file_type_filter)
    if search:
        conditions.append("m.file_name ILIKE %s")
        params.append(f"%{search}%")
    if tag:
        conditions.append("m.tags_json @> %s")
        params.append(json.dumps([tag]))
    if parent_id is not None:
        if parent_id == "":
            conditions.append("(m.parent_id = '' OR m.parent_id IS NULL)")
        else:
            conditions.append("m.parent_id = %s")
            params.append(parent_id)

    count_sql = f"SELECT COUNT(*) as cnt FROM materials m WHERE {' AND '.join(conditions)}"
    count_row = db.fetchone(count_sql, tuple(params))
    total = count_row["cnt"] if count_row else 0

    offset = (page - 1) * page_size
    sql = f"""
        SELECT m.*,
               (SELECT COUNT(*) FROM material_toc t WHERE t.material_id = m.material_id) as toc_count
        FROM materials m
        WHERE {' AND '.join(conditions)}
        ORDER BY m.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([page_size, offset])
    rows = db.fetchall(sql, tuple(params))

    items = []
    for r in rows:
        skills = []
        if r.get("skills_covered_json"):
            try:
                skills = json.loads(r["skills_covered_json"]) if isinstance(r["skills_covered_json"], str) else (r["skills_covered_json"] or [])
            except (json.JSONDecodeError, TypeError):
                skills = []

        tags = r.get("tags_json", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        items.append({
            "material_id": r["material_id"],
            "file_name": r["file_name"],
            "file_type": r["file_type"],
            "file_size": r["file_size"],
            "purpose": r["purpose"],
            "status": r["status"],
            "chunk_count": r["chunk_count"],
            "toc_count": r.get("toc_count", 0),
            "skills": skills,
            "summary": r.get("summary", ""),
            "level": r.get("level", "partition") or "partition",
            "parent_id": r.get("parent_id", "") or "",
            "tags": tags,
            "is_folder": r.get("is_folder", False),
            "is_deleted": r.get("is_deleted", False),
            "deleted_at": _serialize_dt(r.get("deleted_at")),
            "created_at": _serialize_dt(r.get("created_at")),
            "indexed_at": _serialize_dt(r.get("indexed_at")),
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/tags", summary="获取所有标签")
async def get_all_tags(uid: str = Depends(current_user_id)):
    """获取用户所有文件的标签集合"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT tags_json FROM materials WHERE user_id = %s AND is_deleted = FALSE AND tags_json != '[]'",
        (uid,),
    )
    all_tags = set()
    for row in rows:
        tags = row.get("tags_json", [])
        if isinstance(tags, str):
            tags = json.loads(tags)
        all_tags.update(tags)
    return {"tags": sorted(all_tags)}


@router.get("/trash", summary="回收站列表")
async def get_trash(uid: str = Depends(current_user_id)):
    """获取回收站中的文件"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT material_id, file_name, file_type, file_size, purpose,
                  deleted_at, created_at
           FROM materials
           WHERE user_id = %s AND is_deleted = TRUE
           ORDER BY deleted_at DESC""",
        (uid,),
    )
    return {"files": [dict(r) for r in rows]}


@router.get("/folders", summary="文件夹列表")
async def get_folders(uid: str = Depends(current_user_id), parent_id: str = Query("")):
    """获取文件夹列表"""
    from app.db.database import get_db
    db = get_db()
    if parent_id:
        rows = db.fetchall(
            """SELECT material_id, file_name, created_at,
                      (SELECT COUNT(*) FROM materials m2 WHERE m2.parent_id = m.material_id AND m2.is_deleted = FALSE) as child_count
               FROM materials m
               WHERE user_id = %s AND is_folder = TRUE AND is_deleted = FALSE AND parent_id = %s
               ORDER BY created_at DESC""",
            (uid, parent_id),
        )
    else:
        rows = db.fetchall(
            """SELECT material_id, file_name, created_at,
                      (SELECT COUNT(*) FROM materials m2 WHERE m2.parent_id = m.material_id AND m2.is_deleted = FALSE) as child_count
               FROM materials m
               WHERE user_id = %s AND is_folder = TRUE AND is_deleted = FALSE AND (parent_id = '' OR parent_id IS NULL)
               ORDER BY created_at DESC""",
            (uid,),
        )
    return {"folders": [dict(r) for r in rows]}


@router.get("/stats", summary="文件统计")
async def get_file_stats(uid: str = Depends(current_user_id)):
    """获取文件统计信息"""
    from app.db.database import get_db
    db = get_db()
    total = db.fetchone(
        "SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_size FROM materials WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE",
        (uid,),
    )
    by_type = db.fetchall(
        """SELECT file_type, COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_size
           FROM materials WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           GROUP BY file_type ORDER BY count DESC""",
        (uid,),
    )
    by_purpose = db.fetchall(
        """SELECT purpose, COUNT(*) as count
           FROM materials WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           GROUP BY purpose""",
        (uid,),
    )
    folder_count = db.fetchone(
        "SELECT COUNT(*) as count FROM materials WHERE user_id = %s AND is_folder = TRUE AND is_deleted = FALSE",
        (uid,),
    )
    trash_count = db.fetchone(
        "SELECT COUNT(*) as count FROM materials WHERE user_id = %s AND is_deleted = TRUE",
        (uid,),
    )
    recent = db.fetchall(
        """SELECT material_id, file_name, file_type, file_size, created_at
           FROM materials WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           ORDER BY created_at DESC LIMIT 5""",
        (uid,),
    )

    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024: return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024: return f"{size_bytes / (1024 * 1024):.1f} MB"
        else: return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    return {
        "total_files": total["count"],
        "total_size": total["total_size"],
        "total_size_formatted": format_size(total["total_size"]),
        "by_type": [dict(r) for r in by_type],
        "by_purpose": [dict(r) for r in by_purpose],
        "folder_count": folder_count["count"],
        "trash_count": trash_count["count"],
        "recent_files": [dict(r) for r in recent],
    }


# ── 详情 ──

@router.get("/{material_id}", summary="文件详情")
async def get_file(material_id: str, uid: str = Depends(current_user_id)):
    """获取文件详情"""
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone(
        """SELECT m.*,
                  (SELECT COUNT(*) FROM material_toc t WHERE t.material_id = m.material_id) as toc_count
           FROM materials m WHERE m.material_id = %s AND m.user_id = %s""",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    skills = []
    if row.get("skills_covered_json"):
        try:
            skills = json.loads(row["skills_covered_json"]) if isinstance(row["skills_covered_json"], str) else (row["skills_covered_json"] or [])
        except (json.JSONDecodeError, TypeError):
            skills = []

    return {
        "material_id": row["material_id"],
        "file_name": row["file_name"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "purpose": row["purpose"],
        "status": row["status"],
        "storage_path": row["storage_path"],
        "chunk_count": row["chunk_count"],
        "toc_count": row.get("toc_count", 0),
        "skills": skills,
        "summary": row.get("summary", ""),
        "level": row.get("level", "partition") or "partition",
        "parent_id": row.get("parent_id", "") or "",
        "created_at": _serialize_dt(row.get("created_at")),
        "indexed_at": _serialize_dt(row.get("indexed_at")),
    }


# ── 下载 ──

@router.get("/{material_id}/download", summary="下载文件")
async def download_file(material_id: str, uid: str = Depends(current_user_id)):
    """下载文件"""
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT file_name, storage_path FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    storage_path = row.get("storage_path", "")
    if not storage_path or not Path(storage_path).exists():
        raise HTTPException(status_code=404, detail="文件已丢失")

    return FileResponse(
        path=storage_path,
        filename=row["file_name"],
        media_type="application/octet-stream",
    )


# ── TOC ──

@router.get("/{material_id}/toc", summary="获取目录树")
async def get_toc(material_id: str, uid: str = Depends(current_user_id)):
    """获取文件的目录树"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT t.* FROM material_toc t
           JOIN materials m ON t.material_id = m.material_id
           WHERE t.material_id = %s AND m.user_id = %s
           ORDER BY t.created_at ASC""",
        (material_id, uid),
    )

    node_map: dict[str, dict] = {}
    roots: list[dict] = []

    for r in rows:
        node = {
            "toc_id": r["toc_id"],
            "level": r["level"],
            "heading": r["heading"],
            "parent_toc_id": r.get("parent_toc_id"),
            "children": [],
            "chunk_start": r.get("chunk_start", 0),
            "chunk_end": r.get("chunk_end", 0),
        }
        node_map[node["toc_id"]] = node

    for node in node_map.values():
        parent_id = node["parent_toc_id"]
        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node)
        else:
            roots.append(node)

    def sort_key(n):
        return (n["level"], n["heading"])

    for node in node_map.values():
        node["children"].sort(key=sort_key)
    roots.sort(key=sort_key)

    return {"toc": roots}


# ── 分块 ──

@router.get("/{material_id}/chunks", summary="获取分块列表")
async def get_chunks(
    material_id: str,
    toc_id: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    uid: str = Depends(current_user_id),
):
    """获取文件的分块列表"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["material_id = %s", "user_id = %s"]
    params: list[Any] = [material_id, uid]

    if toc_id:
        toc = db.fetchone("SELECT chunk_start, chunk_end FROM material_toc WHERE toc_id = %s", (toc_id,))
        if toc:
            conditions.append("chunk_index BETWEEN %s AND %s")
            params.extend([toc["chunk_start"], toc["chunk_end"]])

    offset = (page - 1) * page_size
    sql = f"SELECT chunk_index, text, chunk_type, page_number, heading_path FROM material_chunks WHERE {' AND '.join(conditions)} ORDER BY chunk_index ASC LIMIT %s OFFSET %s"
    params.extend([page_size, offset])
    rows = db.fetchall(sql, tuple(params))

    items = []
    for r in rows:
        items.append({
            "chunk_index": r["chunk_index"],
            "text": r["text"][:1000] if r.get("text") else "",
            "chunk_type": r.get("chunk_type", "text"),
            "page_number": r.get("page_number"),
            "heading_path": r.get("heading_path", ""),
        })

    return {"items": items, "page": page, "page_size": page_size}


# ── 搜索 ──

class SearchRequest(BaseModel):
    query: str
    purpose: str | None = None
    material_ids: list[str] | None = None
    top_k: int = 10


@router.post("/search", summary="搜索文件内容")
async def search_files(body: SearchRequest, uid: str = Depends(current_user_id)):
    """语义搜索文件内容"""
    from app.services.materials.material_search import material_search
    results = await material_search.search(
        user_id=uid,
        query=body.query,
        purpose=body.purpose,
        material_ids=body.material_ids,
        top_k=body.top_k,
    )
    return {"results": results}
