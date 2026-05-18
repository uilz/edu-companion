"""
资料管理 API v1.1
上传、解析、索引、搜索用户学习资料

新增 v1.1:
- purpose 字段: permanent/session/reference，控制生命周期
- 修复删除 bug: 通过 storage_path 精确删除文件
- 支持音频格式 (.mp3/.wav/.m4a/.ogg)
- session 资料自动清理
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/materials", tags=["materials"])

USER_ID = "default_user"
UPLOAD_DIR = os.path.expanduser("~/.companion/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持的文件格式
INDEXABLE_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ALLOWED_EXTENSIONS = INDEXABLE_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS


# ── 请求/响应模型 ──

class SearchRequest(BaseModel):
    query: str
    material_ids: Optional[list[str]] = None
    skill_id: Optional[str] = None
    top_k: int = 10


class GenerateFromMaterialRequest(BaseModel):
    material_ids: list[str]
    skill_id: Optional[str] = None
    bloom_level: str = "understand"
    difficulty: float = 0.5
    count: int = 3
    content_type: str = "choice"


# ── Helpers ──

def _classify_purpose(file_type: str) -> str:
    """根据文件类型推断默认用途"""
    if file_type in ("pdf", "docx", "pptx"):
        return "permanent"   # 讲义/教材 → 永久保留
    if file_type in ("md", "txt"):
        return "reference"   # 笔记 → 保留但不强制全文索引
    if file_type in ("mp3", "wav", "m4a", "ogg", "flac", "aac"):
        return "session"     # 音频 → 默认临时
    if file_type in ("jpg", "jpeg", "png", "webp", "bmp"):
        return "session"     # 图片 → 默认临时（拍照题）
    return "session"


async def _get_db_conn():
    import asyncpg
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        return await asyncpg.connect(db_url)
    return None


# ── API ──

@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    purpose: str = Form("auto"),      # auto/permanent/session/reference
    auto_index: bool = Form(True),
):
    """
    上传资料文件

    purpose:
      - auto: 根据文件类型自动判断 (PDF→permanent, 图片→session, 音频→session)
      - permanent: 永久资料 — 全文索引，长期保留
      - session: 临时资料 — 不索引，仅保存文件，7天自动清理
      - reference: 参考资料 — 轻量索引(不embedding)，保留

    支持: PDF, Word, PPT, Markdown, TXT, JPG/PNG, MP3/WAV/M4A
    永久资料最大 50MB，临时资料最大 100MB
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"不支持的文件格式: {ext}。"
            f"文档: {', '.join(INDEXABLE_EXTENSIONS)} | "
            f"音频: {', '.join(AUDIO_EXTENSIONS)} | "
            f"图片: {', '.join(IMAGE_EXTENSIONS)}",
        )

    # 文件类型
    type_map = {
        ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx",
        ".md": "markdown", ".txt": "text",
        ".mp3": "mp3", ".wav": "wav", ".m4a": "m4a",
        ".ogg": "ogg", ".flac": "flac", ".aac": "aac",
        ".jpg": "jpg", ".jpeg": "jpg", ".png": "png",
        ".webp": "webp", ".bmp": "bmp",
    }
    file_type = type_map.get(ext, "unknown")

    # 用途
    if purpose == "auto":
        purpose = _classify_purpose(file_type)
    if purpose not in ("permanent", "session", "reference"):
        purpose = "session"

    # 大小限制
    max_size = 100 * 1024 * 1024 if purpose == "session" else 50 * 1024 * 1024

    # 保存文件
    material_id = str(uuid.uuid4())
    storage_name = f"{material_id}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)

    file_size = 0
    with open(storage_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
            file_size += len(chunk)

    if file_size > max_size:
        os.remove(storage_path)
        raise HTTPException(
            400, f"文件过大，最大 {max_size // (1024*1024)}MB"
        )

    logger.info(
        "上传完成: %s (%s, %s, %d bytes)",
        file.filename, file_type, purpose, file_size,
    )

    # 临时资料：不索引，直接返回
    if purpose == "session":
        return {
            "material_id": material_id,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": file_size,
            "purpose": purpose,
            "status": "stored",
            "chunk_count": 0,
            "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
        }

    # 参考资料：轻量索引（不embedding，节省向量空间）
    if purpose == "reference":
        # TODO: 轻量分块+关键词索引，不做embedding
        return {
            "material_id": material_id,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": file_size,
            "purpose": purpose,
            "status": "stored",
            "chunk_count": 0,
        }

    # 永久资料：完整索引流程
    if purpose == "permanent" and auto_index:
        try:
            from app.services.material_indexer import material_indexer
            result = await material_indexer.index_file(
                user_id=USER_ID,
                file_path=storage_path,
                file_name=file.filename or storage_name,
                file_type=file_type,
                file_size=file_size,
            )
            # 更新 storage_path
            conn = await _get_db_conn()
            if conn:
                try:
                    await conn.execute(
                        "UPDATE materials SET storage_path=$1 WHERE material_id=$2",
                        storage_path, result["material_id"],
                    )
                finally:
                    await conn.close()

            return {
                "material_id": result["material_id"],
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "purpose": purpose,
                "status": result["status"],
                "chunk_count": result["chunk_count"],
            }
        except Exception as e:
            logger.error(f"索引失败: {e}")
            return {
                "material_id": material_id,
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "purpose": purpose,
                "status": "stored_index_failed",
                "error": str(e),
            }

    return {
        "material_id": material_id,
        "file_name": file.filename,
        "file_type": file_type,
        "file_size": file_size,
        "purpose": purpose,
        "status": "stored",
    }


@router.get("")
async def list_materials(purpose: str = ""):
    """获取用户资料列表，可按 purpose 过滤"""
    try:
        conn = await _get_db_conn()
        if not conn:
            # 文件系统降级
            materials = []
            for f in os.listdir(UPLOAD_DIR):
                fpath = os.path.join(UPLOAD_DIR, f)
                if os.path.isfile(fpath):
                    name_without_uuid = f[37:] if len(f) > 37 else f
                    materials.append({
                        "material_id": f[:36],
                        "file_name": name_without_uuid or f,
                        "file_type": os.path.splitext(f)[1][1:],
                        "file_size": os.path.getsize(fpath),
                        "purpose": "unknown",
                        "status": "stored",
                        "chunk_count": 0,
                    })
            return {"materials": materials[:20], "total": len(materials)}

        query = """SELECT material_id, file_name, file_type, file_size, 
                   status, purpose, chunk_count, question_count, skills_covered,
                   storage_path, created_at, indexed_at, expires_at
                   FROM materials 
                   WHERE user_id = $1"""
        params = [USER_ID]

        if purpose:
            query += " AND purpose = $2"
            params.append(purpose)

        query += " ORDER BY created_at DESC"

        rows = await conn.fetch(query, *params)
        await conn.close()

        materials = []
        for row in rows:
            materials.append({
                "material_id": row["material_id"],
                "file_name": row["file_name"],
                "file_type": row["file_type"],
                "file_size": row["file_size"],
                "purpose": row["purpose"] or "permanent",
                "status": row["status"],
                "chunk_count": row["chunk_count"],
                "question_count": row["question_count"],
                "skills_covered": row["skills_covered"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "indexed_at": row["indexed_at"].isoformat() if row["indexed_at"] else None,
                "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
            })

        return {"materials": materials, "total": len(materials)}

    except Exception as e:
        logger.error(f"获取资料列表失败: {e}")
        return {"materials": [], "total": 0}


@router.post("/search")
async def search_materials(req: SearchRequest):
    """语义搜索用户资料"""
    from app.services.material_search import material_search as ms
    results = await ms.search(
        user_id=USER_ID,
        query=req.query,
        material_ids=req.material_ids,
        skill_id=req.skill_id,
        top_k=req.top_k,
    )
    return {"results": results, "query": req.query}


@router.get("/{material_id}/chunks")
async def get_material_chunks(material_id: str):
    """获取资料的所有分块"""
    try:
        conn = await _get_db_conn()
        if not conn:
            return {"chunks": []}

        rows = await conn.fetch(
            """SELECT chunk_id, text, chunk_type, skill_ids,
               source_file, page_number, chunk_index
               FROM material_chunks
               WHERE material_id = $1
               ORDER BY chunk_index""",
            material_id,
        )
        await conn.close()

        return {
            "chunks": [
                {
                    "chunk_id": row["chunk_id"],
                    "text": row["text"][:500],
                    "chunk_type": row["chunk_type"],
                    "skill_ids": row["skill_ids"],
                    "source_file": row["source_file"],
                    "page_number": row["page_number"],
                    "chunk_index": row["chunk_index"],
                }
                for row in rows
            ]
        }
    except Exception as e:
        logger.error(f"获取分块失败: {e}")
        return {"chunks": []}


@router.post("/generate-questions")
async def generate_from_materials(req: GenerateFromMaterialRequest):
    """基于用户资料生成练习题"""
    from app.services.material_question_gen import material_question_gen
    from app.schemas.practice import BloomLevel

    bloom = BloomLevel(req.bloom_level) if req.bloom_level else BloomLevel.APPLY

    questions, source_chunks = await material_question_gen.generate_from_materials(
        user_id=USER_ID,
        material_ids=req.material_ids,
        skill_id=req.skill_id,
        bloom_level=bloom,
        difficulty=req.difficulty,
        count=req.count,
        content_type=req.content_type,
    )

    return {
        "questions": [q.model_dump() for q in questions],
        "source_chunks": source_chunks,
        "count": len(questions),
    }


@router.delete("/{material_id}")
async def delete_material(material_id: str):
    """
    删除资料及其所有分块

    删除顺序：
    1. 从DB查 storage_path
    2. 删除DB记录（级联删除chunks）
    3. 删除磁盘文件
    """
    storage_path = None

    try:
        conn = await _get_db_conn()
        if conn:
            # 先查 storage_path
            row = await conn.fetchrow(
                "SELECT storage_path FROM materials WHERE material_id = $1 AND user_id = $2",
                material_id, USER_ID,
            )
            if row:
                storage_path = row["storage_path"]

            # 级联删除
            await conn.execute(
                "DELETE FROM materials WHERE material_id = $1 AND user_id = $2",
                material_id, USER_ID,
            )
            await conn.close()
    except Exception as e:
        logger.error(f"DB删除失败: {e}")
        # 继续尝试删文件

    # 删除磁盘文件（精确路径）
    if storage_path and os.path.isfile(storage_path):
        os.remove(storage_path)
        logger.info(f"已删除文件: {storage_path}")
    else:
        # 降级：尝试匹配UUID前缀
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith(material_id):
                fpath = os.path.join(UPLOAD_DIR, f)
                os.remove(fpath)
                logger.info(f"已删除文件(前缀匹配): {fpath}")

    return {"ok": True, "material_id": material_id}


@router.post("/cleanup-sessions")
async def cleanup_session_materials():
    """
    清理过期的 session 资料（7天自动删除）
    由 cron 或手动触发
    """
    deleted = 0
    try:
        conn = await _get_db_conn()
        if conn:
            rows = await conn.fetch(
                """SELECT material_id, storage_path FROM materials
                   WHERE user_id = $1 AND purpose = 'session'
                   AND (expires_at IS NULL OR expires_at < $2)""",
                USER_ID, datetime.now(),
            )
            for row in rows:
                # 删除DB记录
                await conn.execute(
                    "DELETE FROM materials WHERE material_id = $1",
                    row["material_id"],
                )
                # 删除文件
                if row["storage_path"] and os.path.isfile(row["storage_path"]):
                    os.remove(row["storage_path"])
                deleted += 1
            await conn.close()

        # 也清理文件系统中的孤立 session 文件
        cutoff = datetime.now() - timedelta(days=7)
        for f in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(fpath):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    deleted += 1

        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.error(f"清理失败: {e}")
        return {"ok": False, "error": str(e)}
