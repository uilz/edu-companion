"""
文件管理 API — 上传/列表/搜索/索引/生成练习

双区设计：
- purpose=library: 知识库，永久保存，大文件建TOC
- purpose=session: 临时文件，生命周期跟随对话

功能：
- 文件上传 → 自动分类 + 后台异步索引
- 文件列表（分页、过滤、搜索）
- 文件详情 + 目录树 + 分块列表
- 语义搜索（全文+向量）
- 基于文件生成练习题
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from shared.constants import DEFAULT_USER_ID, get_user_id
from app.domain.auth.dependencies import current_user_id
from app.config import COMPANION_HOME

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])

# 模块级 EventBus（供 _index_background 复用）
_index_event_bus = None


def _get_index_event_bus():
    global _index_event_bus
    if _index_event_bus is None:
        from infra.event_bus import EventBus
        _index_event_bus = EventBus(handler_timeout=5.0)
    return _index_event_bus

# 上传目录
UPLOAD_DIR = COMPANION_HOME / "uploads"

# 支持的文件类型
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".md", ".txt", ".html", ".htm",
    ".csv", ".json", ".xml",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp3", ".wav", ".m4a", ".ogg",
    ".zip",
}


# ── 请求/响应模型 ──

class FileListItem(BaseModel):
    material_id: str
    file_name: str
    file_type: str
    file_size: int
    purpose: str
    status: str
    chunk_count: int
    toc_count: int
    skills: list[str] = Field(default_factory=list)
    level: str = "partition"
    parent_id: str = ""
    created_at: str
    indexed_at: str | None = None


class ChunkItem(BaseModel):
    chunk_index: int
    text: str
    heading_path: str
    chunk_type: str


class TOCItem(BaseModel):
    toc_id: str
    level: int
    heading: str
    parent_toc_id: str | None
    children: list["TOCItem"] = Field(default_factory=list)
    chunk_start: int
    chunk_end: int


class SearchRequest(BaseModel):
    query: str
    purpose: str | None = None
    material_ids: list[str] | None = None
    top_k: int = 10


class SearchResultItem(BaseModel):
    text: str
    heading_path: str
    material_id: str
    material_name: str
    chunk_index: int
    score: float


class PracticeGenerateRequest(BaseModel):
    material_ids: list[str]
    count: int = 5
    skill_ids: list[str] | None = None


# ── 工具函数 ──

def _classify_purpose(file_size: int, upload_source: str) -> str:
    """自动判定文件用途"""
    if file_size > 5_000_000:
        return "library"
    if upload_source == "files_page":
        return "library"
    return "session"


def _serialize_dt(val) -> str:
    """序列化 datetime"""
    if val is None:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


# ── API 端点 ──

@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = Form(default="auto"),
    upload_source: str = Form(default="files_page"),
    level: str = Form(default="partition"),
    parent_id: str = Form(default=""),
    uid: str = Depends(current_user_id),
):
    """
    上传文件，自动解析+索引。

    purpose: auto | library | session
    upload_source: files_page | chat
    level: partition | node — 所属层级
    parent_id: partition_id 或 node_id — 对应层级 ID
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    material_id = str(uuid.uuid4())
    content = await file.read()

    # 确定 purpose
    actual_purpose = purpose
    if purpose == "auto":
        actual_purpose = _classify_purpose(len(content), upload_source)

    # 保存文件
    user_dir = UPLOAD_DIR / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{material_id}{ext}"
    storage_path = user_dir / storage_name
    storage_path.write_bytes(content)

    # 写入 materials 表
    from app.db.database import get_db
    db = get_db()
    db.execute(
        """INSERT INTO materials (material_id, user_id, file_name, file_type, file_size,
           storage_path, purpose, status, chunk_count, level, parent_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'uploading', 0, %s, %s)""",
        (material_id, uid, file.filename, file_type(ext), len(content),
         str(storage_path), actual_purpose, level, parent_id),
    )

    # 后台异步索引
    import asyncio
    asyncio.ensure_future(_index_background(
        uid, material_id, str(storage_path), file.filename,
        file_type(ext), len(content), actual_purpose,
    ))

    logger.info("文件上传: %s (%s, %s, %d bytes)", file.filename, material_id, actual_purpose, len(content))
    return {
        "material_id": material_id,
        "file_name": file.filename,
        "file_size": len(content),
        "purpose": actual_purpose,
        "status": "uploading",
    }


def file_type(ext: str) -> str:
    """扩展名 → 文件类型"""
    if ext in (".pdf",):
        return "pdf"
    if ext in (".docx",):
        return "docx"
    if ext in (".pptx",):
        return "pptx"
    if ext in (".xlsx",):
        return "xlsx"
    if ext in (".md", ".txt"):
        return "document"
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
        return "image"
    if ext in (".mp3", ".wav", ".m4a", ".ogg"):
        return "audio"
    return "other"


async def _index_background(
    user_id: str, material_id: str, file_path: str,
    file_name: str, file_type: str, file_size: int, purpose: str,
):
    """后台异步索引"""
    try:
        from app.services.materials.material_indexer import material_indexer
        result = await material_indexer.index_file(
            user_id, material_id, file_path, file_name,
            file_type, file_size, purpose,
        )
        logger.info("后台索引完成: %s → %s", material_id, result["status"])

        # 触发 domain 层后处理：提取知识点标签 + 生成摘要
        chunk_count = result.get("chunk_count", 0)
        if chunk_count > 0:
            try:
                from domain.materials.service import MaterialServiceImpl

                # 构造简易事件对象触发 on_indexed
                class _IndexEvent:
                    user_id = user_id
                    material_id = material_id
                    chunk_count = chunk_count

                svc = MaterialServiceImpl(event_bus=_get_index_event_bus())
                await svc.on_indexed(_IndexEvent)
            except Exception as post_err:
                logger.warning("资料后处理跳过: %s — %s", material_id, post_err)
    except Exception as e:
        logger.error("后台索引失败: %s — %s", material_id, e)
        try:
            from app.db.database import get_db
            db = get_db()
            db.execute(
                "UPDATE materials SET status = 'index_failed' WHERE material_id = %s",
                (material_id,),
            )
        except Exception:
            pass


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

    # 默认不显示已删除文件
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

    # 总数
    count_sql = f"SELECT COUNT(*) as cnt FROM materials m WHERE {' AND '.join(conditions)}"
    count_row = db.fetchone(count_sql, tuple(params))
    total = count_row["cnt"] if count_row else 0

    # 分页
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


@router.delete("/{material_id}", summary="删除文件")
async def delete_file(material_id: str, uid: str = Depends(current_user_id)):
    """删除文件及其分块和 TOC"""
    from app.db.database import get_db
    db = get_db()

    # 获取文件路径（验证所有权）
    row = db.fetchone(
        "SELECT storage_path FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 级联删除
    db.execute("DELETE FROM material_toc WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM material_chunks WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM materials WHERE material_id = %s", (material_id,))

    # 删除磁盘文件
    storage_path = row.get("storage_path", "")
    if storage_path:
        try:
            Path(storage_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("删除文件失败: %s — %s", storage_path, e)

    return {"status": "deleted", "material_id": material_id}


class FilePatchRequest(BaseModel):
    level: str | None = None
    parent_id: str | None = None
    file_name: str | None = None


@router.patch("/{material_id}", summary="更新文件元数据")
async def patch_file(material_id: str, body: FilePatchRequest, uid: str = Depends(current_user_id)):
    """更新文件的所属层级"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    updates = []
    params: list[Any] = []
    if body.level is not None:
        updates.append("level = %s")
        params.append(body.level)
    if body.parent_id is not None:
        updates.append("parent_id = %s")
        params.append(body.parent_id)
    if body.file_name is not None:
        updates.append("file_name = %s")
        params.append(body.file_name)

    if updates:
        params.append(material_id)
        db.execute(
            f"UPDATE materials SET {', '.join(updates)} WHERE material_id = %s",
            tuple(params),
        )

    return {"ok": True, "material_id": material_id}


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

    # 构建树
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

    # 按 level + id 排序
    def sort_key(n):
        return (n["level"], n["heading"])

    for node in node_map.values():
        node["children"].sort(key=sort_key)
    roots.sort(key=sort_key)

    return {"toc": roots}


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
        # 获取该 TOC 节点的 chunk 范围
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


@router.post("/generate-practice", summary="基于文件生成练习")
async def generate_practice(body: PracticeGenerateRequest, uid: str = Depends(current_user_id)):
    """基于文件分块生成练习题"""
    from app.db.database import get_db
    db = get_db()

    # 读取文件分块
    placeholders = ",".join(["%s"] * len(body.material_ids))
    rows = db.fetchall(
        f"SELECT text, material_id FROM material_chunks WHERE material_id IN ({placeholders}) AND user_id = %s LIMIT 30",
        tuple(body.material_ids) + (uid,),
    )

    if not rows:
        raise HTTPException(status_code=400, detail="文件无有效内容，无法生成练习")

    context = "\n\n".join(r["text"][:1000] for r in rows[:5])

    # LLM 出题
    try:
        from app.services.llm.llm_service import llm_service
        prompt = (
            f"基于以下资料内容，生成{body.count}道练习题。\n"
            f"要求：题型覆盖选择题和简答题，包含答案和解析。\n\n"
            f"资料内容：\n{context[:3000]}\n\n"
            f"请以JSON格式输出：\n"
            f'[{{"type":"choice|short","question":"...","options":["A.","B.","C.","D."],"answer":"...","explanation":"..."}}]'
        )

        response = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是一个出题助手。严格按照JSON格式输出。"},
                {"role": "user", "content": prompt},
            ],
            task_type="chat",
            temperature=0.5,
            max_tokens=4096,
        )

        # 解析 JSON
        try:
            import re
            json_str = re.search(r'\[.*\]', response, re.DOTALL)
            if json_str:
                questions = json.loads(json_str.group())
            else:
                questions = json.loads(response)
        except (json.JSONDecodeError, Exception):
            questions = [{"question": response[:500], "type": "short", "answer": "", "explanation": ""}]

        return {"questions": questions, "count": len(questions)}

    except Exception as e:
        logger.error("练习生成失败: %s", e)
        raise HTTPException(status_code=500, detail=f"练习生成失败: {e}")


@router.post("/{material_id}/reindex", summary="重新索引文件")
async def reindex_file(material_id: str, uid: str = Depends(current_user_id)):
    """手动触发文件重新索引（用于修复 stuck 文件）"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT * FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    storage_path = row.get("storage_path", "")
    if not storage_path or not Path(storage_path).exists():
        raise HTTPException(status_code=400, detail="文件已从磁盘删除，无法重新索引")

    # 更新状态为 uploading 并触发后台索引
    db.execute(
        "UPDATE materials SET status = 'uploading', chunk_count = 0 WHERE material_id = %s",
        (material_id,),
    )

    import asyncio
    asyncio.ensure_future(_index_background(
        uid, material_id, storage_path, row["file_name"],
        row["file_type"], row.get("file_size", 0), row["purpose"],
    ))

    logger.info("手动触发重索引: %s", material_id)
    return {"material_id": material_id, "status": "uploading", "message": "已触发重新索引"}


async def recover_stuck_files():
    """服务启动时恢复 stuck 文件（uploading → 重新索引）"""
    from app.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT * FROM materials WHERE status = 'uploading'"
    )
    if not rows:
        return

    logger.info("🔧 发现 %d 个 stuck 文件，启动恢复...", len(rows))
    import asyncio
    for row in rows:
        storage_path = row.get("storage_path", "")
        if storage_path and Path(storage_path).exists():
            asyncio.ensure_future(_index_background(
                row["user_id"], row["material_id"], storage_path, row["file_name"],
                row["file_type"], row.get("file_size", 0), row["purpose"],
            ))
            logger.info("  恢复: %s", row["file_name"])
        else:
            db.execute(
                "UPDATE materials SET status = 'index_failed' WHERE material_id = %s",
                (row["material_id"],),
            )
            logger.warning("  跳过(文件丢失): %s", row["file_name"])

    logger.info("🔧 stuck 文件恢复完成")


@router.post("/cleanup", summary="清理过期临时文件")
async def cleanup_temp_files(uid: str = Depends(current_user_id)):
    """清理过期的 session 文件"""
    from app.db.database import get_db
    db = get_db()

    # 删除 30 天前的 session 文件
    rows = db.fetchall(
        """SELECT material_id, storage_path FROM materials
           WHERE user_id = %s AND purpose = 'session'
           AND created_at < NOW() - INTERVAL '30 days'""",
        (uid,),
    )

    count = 0
    for r in rows:
        db.execute("DELETE FROM material_toc WHERE material_id = %s", (r["material_id"],))
        db.execute("DELETE FROM material_chunks WHERE material_id = %s", (r["material_id"],))
        db.execute("DELETE FROM materials WHERE material_id = %s", (r["material_id"],))
        if r.get("storage_path"):
            try:
                Path(r["storage_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        count += 1

    return {"cleaned": count, "message": f"已清理 {count} 个过期临时文件"}


# ==================== 标签系统 ====================

class UpdateTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


@router.put("/{material_id}/tags", summary="更新文件标签")
async def update_file_tags(
    material_id: str,
    body: UpdateTagsRequest,
    uid: str = Depends(current_user_id),
):
    """为文件添加/更新标签"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_deleted = FALSE",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    db.execute(
        "UPDATE materials SET tags_json = %s WHERE material_id = %s",
        (json.dumps(body.tags), material_id),
    )
    return {"ok": True, "tags": body.tags}


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


# ==================== 回收站 ====================

@router.post("/{material_id}/trash", summary="移入回收站")
async def move_to_trash(material_id: str, uid: str = Depends(current_user_id)):
    """软删除文件到回收站"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_deleted = FALSE",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    db.execute(
        "UPDATE materials SET is_deleted = TRUE, deleted_at = NOW() WHERE material_id = %s",
        (material_id,),
    )
    return {"ok": True, "message": "已移入回收站"}


@router.post("/{material_id}/restore", summary="从回收站恢复")
async def restore_from_trash(material_id: str, uid: str = Depends(current_user_id)):
    """从回收站恢复文件"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_deleted = TRUE",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="回收站中无此文件")

    db.execute(
        "UPDATE materials SET is_deleted = FALSE, deleted_at = NULL WHERE material_id = %s",
        (material_id,),
    )
    return {"ok": True, "message": "已恢复"}


@router.delete("/{material_id}/permanent", summary="永久删除")
async def permanent_delete(material_id: str, uid: str = Depends(current_user_id)):
    """从回收站永久删除文件"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id, storage_path FROM materials WHERE material_id = %s AND user_id = %s AND is_deleted = TRUE",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="回收站中无此文件")

    # 删除关联数据
    db.execute("DELETE FROM material_toc WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM material_chunks WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM materials WHERE material_id = %s", (material_id,))

    # 删除物理文件
    if row.get("storage_path"):
        try:
            Path(row["storage_path"]).unlink(missing_ok=True)
        except Exception:
            pass

    return {"ok": True, "message": "已永久删除"}


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


@router.post("/trash/empty", summary="清空回收站")
async def empty_trash(uid: str = Depends(current_user_id)):
    """清空回收站"""
    from app.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT material_id, storage_path FROM materials WHERE user_id = %s AND is_deleted = TRUE",
        (uid,),
    )

    count = 0
    for r in rows:
        db.execute("DELETE FROM material_toc WHERE material_id = %s", (r["material_id"],))
        db.execute("DELETE FROM material_chunks WHERE material_id = %s", (r["material_id"],))
        db.execute("DELETE FROM materials WHERE material_id = %s", (r["material_id"],))
        if r.get("storage_path"):
            try:
                Path(r["storage_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        count += 1

    return {"ok": True, "cleaned": count, "message": f"已清空回收站 ({count} 个文件)"}


# ==================== 文件夹管理 ====================

class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None


@router.post("/folder", summary="创建文件夹")
async def create_folder(body: CreateFolderRequest, uid: str = Depends(current_user_id)):
    """创建文件夹"""
    from app.db.database import get_db
    import time
    db = get_db()

    folder_id = f"folder_{uid[:8]}_{int(time.time())}"
    db.execute(
        """INSERT INTO materials (material_id, user_id, file_name, file_type, file_size,
                                  purpose, status, is_folder, parent_id, level)
           VALUES (%s, %s, %s, 'folder', 0, 'library', 'indexed', TRUE, %s, 'folder')""",
        (folder_id, uid, body.name, body.parent_id or ""),
    )
    return {"ok": True, "folder_id": folder_id, "name": body.name}


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


@router.patch("/folder/{folder_id}", summary="更新文件夹")
async def update_folder(
    folder_id: str,
    body: UpdateFileMetaRequest,
    uid: str = Depends(current_user_id),
):
    """更新文件夹名称"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_folder = TRUE AND is_deleted = FALSE",
        (folder_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    updates = []
    params = []
    if body.file_name is not None:
        updates.append("file_name = %s")
        params.append(body.file_name)
    if body.parent_id is not None:
        updates.append("parent_id = %s")
        params.append(body.parent_id)

    if updates:
        params.extend([folder_id, uid])
        db.execute(
            f"UPDATE materials SET {', '.join(updates)} WHERE material_id = %s AND user_id = %s",
            tuple(params),
        )

    return {"ok": True}


@router.delete("/folder/{folder_id}", summary="删除文件夹")
async def delete_folder(folder_id: str, uid: str = Depends(current_user_id)):
    """删除文件夹（不删除内部文件，仅移除文件夹）"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_folder = TRUE AND is_deleted = FALSE",
        (folder_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    # 将内部文件移到根目录
    db.execute(
        "UPDATE materials SET parent_id = '' WHERE parent_id = %s AND user_id = %s",
        (folder_id, uid),
    )
    db.execute(
        "UPDATE materials SET is_deleted = TRUE, deleted_at = NOW() WHERE material_id = %s",
        (folder_id,),
    )

    return {"ok": True, "message": "文件夹已删除，内部文件已移至根目录"}


# ==================== 批量操作 ====================

class BatchOperationRequest(BaseModel):
    material_ids: list[str]
    action: str  # "delete", "move", "add_tags", "remove_tags"
    target_folder_id: Optional[str] = None
    tags: Optional[list[str]] = None


@router.post("/batch", summary="批量操作")
async def batch_operation(body: BatchOperationRequest, uid: str = Depends(current_user_id)):
    """批量操作文件"""
    from app.db.database import get_db
    db = get_db()

    if not body.material_ids:
        raise HTTPException(status_code=400, detail="未选择文件")

    results = {"success": 0, "failed": 0, "errors": []}

    for mid in body.material_ids:
        try:
            row = db.fetchone(
                "SELECT material_id FROM materials WHERE material_id = %s AND user_id = %s AND is_deleted = FALSE",
                (mid, uid),
            )
            if not row:
                results["failed"] += 1
                results["errors"].append(f"文件 {mid} 不存在")
                continue

            if body.action == "delete":
                db.execute(
                    "UPDATE materials SET is_deleted = TRUE, deleted_at = NOW() WHERE material_id = %s",
                    (mid,),
                )
            elif body.action == "move":
                db.execute(
                    "UPDATE materials SET parent_id = %s WHERE material_id = %s",
                    (body.target_folder_id or "", mid),
                )
            elif body.action == "add_tags":
                if body.tags:
                    current = db.fetchone("SELECT tags_json FROM materials WHERE material_id = %s", (mid,))
                    existing = current.get("tags_json", []) if current else []
                    if isinstance(existing, str):
                        existing = json.loads(existing)
                    new_tags = list(set(existing + body.tags))
                    db.execute(
                        "UPDATE materials SET tags_json = %s WHERE material_id = %s",
                        (json.dumps(new_tags), mid),
                    )
            elif body.action == "remove_tags":
                if body.tags:
                    current = db.fetchone("SELECT tags_json FROM materials WHERE material_id = %s", (mid,))
                    existing = current.get("tags_json", []) if current else []
                    if isinstance(existing, str):
                        existing = json.loads(existing)
                    new_tags = [t for t in existing if t not in body.tags]
                    db.execute(
                        "UPDATE materials SET tags_json = %s WHERE material_id = %s",
                        (json.dumps(new_tags), mid),
                    )

            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"文件 {mid}: {str(e)}")

    return results


# ==================== 文件统计 ====================

@router.get("/stats", summary="文件统计")
async def get_file_stats(uid: str = Depends(current_user_id)):
    """获取文件统计信息"""
    from app.db.database import get_db
    db = get_db()

    # 总数
    total = db.fetchone(
        "SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_size FROM materials WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE",
        (uid,),
    )

    # 按类型统计
    by_type = db.fetchall(
        """SELECT file_type, COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_size
           FROM materials
           WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           GROUP BY file_type
           ORDER BY count DESC""",
        (uid,),
    )

    # 按用途统计
    by_purpose = db.fetchall(
        """SELECT purpose, COUNT(*) as count
           FROM materials
           WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           GROUP BY purpose""",
        (uid,),
    )

    # 文件夹数
    folder_count = db.fetchone(
        "SELECT COUNT(*) as count FROM materials WHERE user_id = %s AND is_folder = TRUE AND is_deleted = FALSE",
        (uid,),
    )

    # 回收站数量
    trash_count = db.fetchone(
        "SELECT COUNT(*) as count FROM materials WHERE user_id = %s AND is_deleted = TRUE",
        (uid,),
    )

    # 最近上传
    recent = db.fetchall(
        """SELECT material_id, file_name, file_type, file_size, created_at
           FROM materials
           WHERE user_id = %s AND is_deleted = FALSE AND is_folder = FALSE
           ORDER BY created_at DESC LIMIT 5""",
        (uid,),
    )

    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

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
