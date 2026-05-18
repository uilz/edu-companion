"""
资料管理 API
上传、解析、索引、搜索用户学习资料
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/materials", tags=["materials"])

# MVP 单用户
USER_ID = "default_user"
# 上传文件存储目录
UPLOAD_DIR = os.path.expanduser("~/.companion/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持的文件格式
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}


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


# ── API ──

@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    auto_index: bool = Form(True),
):
    """
    上传资料文件并触发索引
    
    支持：PDF, Word(.docx), PPT, Markdown, TXT
    最大 50MB
    """
    # 校验文件类型
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400, f"不支持的文件格式: {ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 保存文件
    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{file.filename}"
    storage_path = os.path.join(UPLOAD_DIR, safe_name)

    file_size = 0
    with open(storage_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB
            f.write(chunk)
            file_size += len(chunk)

    if file_size > 50 * 1024 * 1024:
        os.remove(storage_path)
        raise HTTPException(400, "文件过大，最大 50MB")

    # 文件类型映射
    type_map = {
        ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx",
        ".md": "markdown", ".txt": "text",
    }
    file_type = type_map.get(ext, "unknown")

    logger.info(
        "文件上传完成: %s (%s, %d bytes)", file.filename, file_type, file_size
    )

    # 触发索引
    if auto_index:
        try:
            from app.services.material_indexer import material_indexer
            result = await material_indexer.index_file(
                user_id=USER_ID,
                file_path=storage_path,
                file_name=file.filename or safe_name,
                file_type=file_type,
                file_size=file_size,
            )
            return {
                "material_id": result["material_id"],
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "status": result["status"],
                "chunk_count": result["chunk_count"],
            }
        except Exception as e:
            logger.error(f"索引失败: {e}")
            return {
                "material_id": file_id,
                "file_name": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "status": "uploaded_only",
                "error": str(e),
            }

    return {
        "material_id": file_id,
        "file_name": file.filename,
        "file_type": file_type,
        "file_size": file_size,
        "status": "uploaded",
    }


@router.get("")
async def list_materials():
    """获取用户资料列表"""
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return {"materials": [], "total": 0}

        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """SELECT material_id, file_name, file_type, file_size, 
                   status, chunk_count, question_count, skills_covered,
                   created_at, indexed_at
                   FROM materials 
                   WHERE user_id = $1
                   ORDER BY created_at DESC""",
                USER_ID,
            )
            materials = [
                {
                    "material_id": row["material_id"],
                    "file_name": row["file_name"],
                    "file_type": row["file_type"],
                    "file_size": row["file_size"],
                    "status": row["status"],
                    "chunk_count": row["chunk_count"],
                    "question_count": row["question_count"],
                    "skills_covered": row["skills_covered"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "indexed_at": row["indexed_at"].isoformat() if row["indexed_at"] else None,
                }
                for row in rows
            ]
            return {"materials": materials, "total": len(materials)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"获取资料列表失败: {e}")
        # 文件系统降级
        materials = []
        for f in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(fpath):
                materials.append({
                    "material_id": f[:8],
                    "file_name": f[9:] if len(f) > 9 else f,
                    "file_type": os.path.splitext(f)[1][1:],
                    "file_size": os.path.getsize(fpath),
                    "status": "uploaded",
                    "chunk_count": 0,
                })
        return {"materials": materials[:20], "total": len(materials)}


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
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return {"chunks": []}

        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """SELECT chunk_id, text, chunk_type, skill_ids,
                   source_file, page_number, chunk_index
                   FROM material_chunks
                   WHERE material_id = $1
                   ORDER BY chunk_index""",
                material_id,
            )
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
        finally:
            await conn.close()
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
    """删除资料及其所有分块"""
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            conn = await asyncpg.connect(db_url)
            try:
                # 级联删除（chunks有ON DELETE CASCADE）
                await conn.execute(
                    "DELETE FROM materials WHERE material_id = $1 AND user_id = $2",
                    material_id, USER_ID,
                )
            finally:
                await conn.close()

        # 也尝试删除文件
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith(material_id):
                os.remove(os.path.join(UPLOAD_DIR, f))

        return {"ok": True, "material_id": material_id}
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(500, str(e))
