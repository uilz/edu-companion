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

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from shared.constants import DEFAULT_USER_ID, get_user_id
from app.config import COMPANION_HOME

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])

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
):
    """
    上传文件，自动解析+索引。

    purpose: auto | library | session
    upload_source: files_page | chat
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    uid = get_user_id(None)
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
           storage_path, purpose, status, chunk_count)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'uploading', 0)""",
        (material_id, uid, file.filename, file_type(ext), len(content),
         str(storage_path), actual_purpose),
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
        from app.services.material_indexer import material_indexer
        result = await material_indexer.index_file(
            user_id, material_id, file_path, file_name,
            file_type, file_size, purpose,
        )
        logger.info("后台索引完成: %s → %s", material_id, result["status"])
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
):
    """获取文件列表（分页、过滤）"""
    uid = get_user_id(None)
    from app.db.database import get_db
    db = get_db()

    conditions = ["m.user_id = %s"]
    params: list[Any] = [uid]

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
async def get_file(material_id: str):
    """获取文件详情"""
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone(
        """SELECT m.*,
                  (SELECT COUNT(*) FROM material_toc t WHERE t.material_id = m.material_id) as toc_count
           FROM materials m WHERE m.material_id = %s""",
        (material_id,),
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
        "created_at": _serialize_dt(row.get("created_at")),
        "indexed_at": _serialize_dt(row.get("indexed_at")),
    }


@router.delete("/{material_id}", summary="删除文件")
async def delete_file(material_id: str):
    """删除文件及其分块和 TOC"""
    from app.db.database import get_db
    db = get_db()

    # 获取文件路径
    row = db.fetchone("SELECT storage_path FROM materials WHERE material_id = %s", (material_id,))
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


@router.get("/{material_id}/toc", summary="获取目录树")
async def get_toc(material_id: str):
    """获取文件的目录树"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM material_toc WHERE material_id = %s ORDER BY created_at ASC",
        (material_id,),
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
):
    """获取文件的分块列表"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["material_id = %s"]
    params: list[Any] = [material_id]

    if toc_id:
        # 获取该 TOC 节点的 chunk 范围
        toc = db.fetchone("SELECT chunk_start, chunk_end FROM material_toc WHERE toc_id = %s", (toc_id,))
        if toc:
            conditions.append("chunk_index BETWEEN %s AND %s")
            params.extend([toc["chunk_start"], toc["chunk_end"]])

    offset = (page - 1) * page_size
    sql = f"SELECT * FROM material_chunks WHERE {' AND '.join(conditions)} ORDER BY chunk_index ASC LIMIT %s OFFSET %s"
    params.extend([page_size, offset])
    rows = db.fetchall(sql, tuple(params))

    items = []
    for r in rows:
        items.append({
            "chunk_index": r["chunk_index"],
            "text": r["text"][:1000] if r.get("text") else "",
            "chunk_type": r.get("chunk_type", "text"),
            "page_number": r.get("page_number"),
        })

    return {"items": items, "page": page, "page_size": page_size}


@router.post("/search", summary="搜索文件内容")
async def search_files(body: SearchRequest):
    """语义搜索文件内容"""
    uid = get_user_id(None)
    from app.services.material_search import material_search
    results = await material_search.search(
        user_id=uid,
        query=body.query,
        purpose=body.purpose,
        material_ids=body.material_ids,
        top_k=body.top_k,
    )
    return {"results": results}


@router.post("/generate-practice", summary="基于文件生成练习")
async def generate_practice(body: PracticeGenerateRequest):
    """基于文件分块生成练习题"""
    uid = get_user_id(None)
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
        from app.services.llm_service import llm_service
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


@router.post("/cleanup", summary="清理过期临时文件")
async def cleanup_temp_files():
    """清理过期的 session 文件"""
    uid = get_user_id(None)
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
