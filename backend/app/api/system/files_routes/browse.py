"""文件管理 — 浏览：列表/详情/搜索/下载/TOC/分块/标签/统计"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, JSONResponse
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
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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

# 扩展名 → MIME 映射（用于预览时正确渲染）
EXT_MEDIA_TYPE = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".bmp": "image/bmp", ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon", ".tiff": "image/tiff", ".tif": "image/tiff", ".avif": "image/avif",
    ".html": "text/html", ".htm": "text/html",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".md": "text/markdown", ".txt": "text/plain",
    ".csv": "text/csv", ".json": "application/json", ".xml": "application/xml",
}

@router.get("/{material_id}/download", summary="下载文件")
async def download_file(material_id: str, uid: str = Depends(current_user_id)):
    """下载文件"""
    from app.infrastructure.db.database import get_db
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

    # 根据文件扩展名设置正确的 Content-Type，使浏览器能正确渲染预览
    ext = Path(row["file_name"]).suffix.lower()
    media_type = EXT_MEDIA_TYPE.get(ext, "application/octet-stream")

    return FileResponse(
        path=storage_path,
        filename=row["file_name"],
        media_type=media_type,
    )


# ── 预览 ──

# 浏览器原生可渲染的媒体类型（直接返回原文件，流式加载）
PREVIEW_INLINE_EXTS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif", ".avif",
    ".pdf",
    ".html", ".htm",
    ".mp3", ".wav", ".m4a", ".ogg",
    ".mp4", ".webm", ".mkv", ".mov", ".avi",
})

# MarkItDown 处理的文件类型（返回 chunks 的 markdown 文本）
PREVIEW_MARKDOWN_EXTS = frozenset({
    ".pptx", ".xlsx", ".xls", ".zip", ".doc", ".drawio", ".xmind", ".opml", ".vsdx", ".vsd",
})

# 纯文本类型（返回原文件内容）
PREVIEW_TEXT_EXTS = frozenset({
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".log",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".hpp",
    ".sql", ".rs", ".go", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".lua", ".sh",
    ".vue", ".svelte", ".dart", ".gradle", ".cmake", ".tex", ".m", ".mm", ".pl", ".pm",
})

@router.get("/{material_id}/preview", summary="统一预览")
async def preview_file(material_id: str, uid: str = Depends(current_user_id)):
    """
    统一预览端点：根据文件类型返回不同格式。
    - 图片/PDF/HTML/音视频 → 返回原文件（Content-Disposition: inline），浏览器直接渲染
    - DOCX → 返回原文件（前端 mammoth.js 渲染）
    - PPTX/XLSX/ZIP → 返回 MarkItDown 分块 markdown 文本
    - 代码/文本 → 返回文件内容
    """
    from app.infrastructure.db.database import get_db
    db = get_db()
    row = db.fetchone(
        "SELECT file_name, storage_path, file_type FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    storage_path = row.get("storage_path", "")
    if not storage_path or not Path(storage_path).exists():
        raise HTTPException(status_code=404, detail="文件已丢失")

    ext = Path(row["file_name"]).suffix.lower()

    # ── 浏览器原生渲染：直接返回原文件 ──
    if ext in PREVIEW_INLINE_EXTS:
        media_type = EXT_MEDIA_TYPE.get(ext, "application/octet-stream")
        return FileResponse(
            path=storage_path,
            media_type=media_type,
            headers={"Content-Disposition": "inline", "Cache-Control": "public, max-age=3600"},
        )

    # ── DOCX：返回原文件，前端用 mammoth.js 渲染 ──
    if ext == ".docx":
        return FileResponse(
            path=storage_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "inline", "Cache-Control": "public, max-age=3600"},
        )

    # ── MarkItDown 处理后的文件：返回分块 markdown ──
    if ext in PREVIEW_MARKDOWN_EXTS:
        chunks = db.fetchall(
            "SELECT text FROM material_chunks WHERE material_id = %s AND user_id = %s ORDER BY chunk_index",
            (material_id, uid),
        )
        if chunks:
            text = "\n\n---\n\n".join(c["text"] for c in chunks)
            return JSONResponse({"type": "markdown_chunks", "content": text, "from_chunks": True})
        return JSONResponse({"type": "empty", "content": "", "from_chunks": True})

    # ── 纯文本/代码 ──
    if ext in PREVIEW_TEXT_EXTS:
        try:
            with open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            text = ""
        return JSONResponse({"type": "text", "content": text, "from_chunks": False, "lang": ext.lstrip(".")})

    # ── 不支持的类型 ──
    raise HTTPException(status_code=415, detail=f"不支持预览该文件类型: {ext}")


# ── TOC ──

@router.get("/{material_id}/toc", summary="获取目录树")
async def get_toc(material_id: str, uid: str = Depends(current_user_id)):
    """获取文件的目录树"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT t.* FROM material_toc t
           JOIN materials m ON t.material_id = m.material_id
           WHERE t.material_id = %s AND m.user_id = %s
           ORDER BY t.chunk_start ASC""",
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
        return n.get("chunk_start", 0)

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
    from app.infrastructure.db.database import get_db
    db = get_db()

    conditions = ["material_id = %s", "user_id = %s"]
    params: list[Any] = [material_id, uid]

    if toc_id:
        toc = db.fetchone("SELECT chunk_start, chunk_end FROM material_toc WHERE toc_id = %s", (toc_id,))
        if toc:
            conditions.append("chunk_index BETWEEN %s AND %s")
            params.extend([toc["chunk_start"], toc["chunk_end"]])

    offset = (page - 1) * page_size
    sql = f"SELECT chunk_index, text, chunk_type, heading_path FROM material_chunks WHERE {' AND '.join(conditions)} ORDER BY chunk_index ASC LIMIT %s OFFSET %s"
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
    from app.infrastructure.files.search import material_search
    results = await material_search.search(
        user_id=uid,
        query=body.query,
        purpose=body.purpose,
        material_ids=body.material_ids,
        top_k=body.top_k,
    )
    return {"results": results}


# ── 搜索扩展 R2-3: 文件内搜索 + 单 chunk 全文 + 相似分块 ──


@router.post("/{material_id}/search", summary="在文件内搜索")
async def search_within_file(
    material_id: str,
    body: SearchRequest,
    uid: str = Depends(current_user_id),
):
    """在指定文件内语义搜索"""
    from app.infrastructure.files.search import material_search
    results = await material_search.search(
        user_id=uid,
        query=body.query,
        material_ids=[material_id],
        top_k=body.top_k,
    )
    return {"results": results}


@router.get("/{material_id}/chunks/{chunk_index}/full", summary="获取分块全文")
async def get_chunk_full(
    material_id: str,
    chunk_index: int,
    uid: str = Depends(current_user_id),
):
    """获取单个分块的完整文本（无截断）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT chunk_index, text, heading_path, source_file, chunk_type "
        "FROM material_chunks "
        "WHERE material_id = %s AND chunk_index = %s AND user_id = %s",
        (material_id, chunk_index, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="分块不存在")

    return {
        "chunk_index": row["chunk_index"],
        "text": row.get("text", ""),
        "heading_path": row.get("heading_path", ""),
        "source_file": row.get("source_file", ""),
        "chunk_type": row.get("chunk_type", "text"),
    }


@router.post("/chunks/{chunk_id}/similar", summary="搜索相似分块")
async def search_similar_chunks(
    chunk_id: str,
    top_k: int = Query(default=5, le=20),
    uid: str = Depends(current_user_id),
):
    """以指定 chunk 为 query 搜索语义相似的分块"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    source = db.fetchone(
        "SELECT text, material_id, user_id FROM material_chunks WHERE chunk_id = %s",
        (chunk_id,),
    )
    if not source:
        raise HTTPException(status_code=404, detail="分块不存在")
    if source["user_id"] != uid:
        raise HTTPException(status_code=403, detail="无权限")

    from app.infrastructure.files.search import material_search
    results = await material_search.search(
        user_id=uid,
        query=source["text"][:500],
        material_ids=[source["material_id"]] if source["material_id"] else None,
        top_k=top_k,
    )
    return {"query_chunk": chunk_id, "results": results}
