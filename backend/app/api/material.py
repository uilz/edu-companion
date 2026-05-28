"""
资料管理 API v2.0
P5: 资料→分区归属→分支引用

设计原则：
- 所有上传默认临时(session)，不自动索引
- 用户手动"转为知识库"时才建立索引
- 资料按分区组织，默认归入「未分类」
- 分支可引用资料（不复制，存引用关系）
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.shared.constants import DEFAULT_USER_ID
from app.services.materials_meta import materials_meta, UNCATEGORIZED_PARTITION_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/materials", tags=["materials"])

USER_ID = DEFAULT_USER_ID
UPLOAD_DIR = os.path.expanduser("~/.companion/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 文件格式
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

class UpdateMaterialRequest(BaseModel):
    partition_id: Optional[str] = None


# ── Helpers ──

def _file_type(ext: str) -> str:
    type_map = {
        ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx",
        ".md": "markdown", ".txt": "text",
        ".mp3": "mp3", ".wav": "wav", ".m4a": "m4a",
        ".ogg": "ogg", ".flac": "flac", ".aac": "aac",
        ".jpg": "jpg", ".jpeg": "jpg", ".png": "png",
        ".webp": "webp", ".bmp": "bmp",
    }
    return type_map.get(ext, "unknown")

def _ensure_indexed():
    """确保所有磁盘文件都有元数据"""
    materials_meta.ensure_indexed()


# ── API ──

@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    purpose: str = Form("session"),
    partition_id: str = Form(UNCATEGORIZED_PARTITION_ID),
):
    """
    上传资料文件。
    默认 purpose=session（临时，不索引）。
    partition_id 默认「未分类」。
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

    file_type = _file_type(ext)

    # 保存文件
    material_id = str(uuid.uuid4())
    storage_name = f"{material_id}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)

    file_size = 0
    with open(storage_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
            file_size += len(chunk)

    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        os.remove(storage_path)
        raise HTTPException(400, f"文件过大，最大 {max_size // (1024*1024)}MB")

    # 写入元数据
    created_at = datetime.now().isoformat()
    materials_meta.set(material_id, {
        "file_name": file.filename,
        "file_type": file_type,
        "file_size": file_size,
        "partition_id": partition_id,
        "purpose": purpose,
        "status": "stored",
        "chunk_count": 0,
        "skills_covered": [],
        "created_at": created_at,
        "indexed_at": None,
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat() if purpose == "session" else None,
    })

    logger.info("上传完成: %s (%s, %s, %d bytes) → partition=%s", file.filename, file_type, purpose, file_size, partition_id)

    return {
        "material_id": material_id,
        "file_name": file.filename,
        "file_type": file_type,
        "file_size": file_size,
        "purpose": purpose,
        "partition_id": partition_id,
        "status": "stored",
        "chunk_count": 0,
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat() if purpose == "session" else None,
    }


@router.get("")
async def list_materials(
    partition_id: str = "",
    purpose: str = "",
    search: str = "",
):
    """
    获取资料列表。
    支持 partition_id 过滤、purpose 过滤、文件名搜索。
    """
    _ensure_indexed()

    if search:
        materials = materials_meta.search(search, partition_id or None)
    elif partition_id:
        materials = materials_meta.list_by_partition(partition_id)
    else:
        # 全部（按分区统计返回）
        all_meta = materials_meta.get_all()
        materials = [
            {"material_id": mid, **meta}
            for mid, meta in all_meta.items()
        ]
        materials.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # purpose 过滤
    if purpose:
        materials = [m for m in materials if m.get("purpose") == purpose]

    return {
        "materials": materials,
        "total": len(materials),
        "stats_by_partition": materials_meta.get_stats_by_partition(),
    }


@router.patch("/{material_id}")
async def update_material(material_id: str, req: UpdateMaterialRequest):
    """更新资料元数据（如移动分区）"""
    meta = materials_meta.get(material_id)
    if not meta:
        raise HTTPException(404, "资料不存在")

    if req.partition_id is not None:
        materials_meta.migrate_to_partition(material_id, req.partition_id)
        logger.info("资料 %s → 分区 %s", material_id, req.partition_id)

    return {"ok": True, "material_id": material_id}


@router.post("/{material_id}/promote")
async def promote_to_permanent(material_id: str):
    """
    将临时资料转为知识库资料，触发索引。
    """
    meta = materials_meta.get(material_id)
    if not meta:
        raise HTTPException(404, "资料不存在")

    # 检查文件存在
    storage_path = None
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(material_id):
            storage_path = os.path.join(UPLOAD_DIR, f)
            break

    if not storage_path or not os.path.isfile(storage_path):
        raise HTTPException(404, "文件不存在，可能已被清理")

    ext = os.path.splitext(storage_path)[1].lower()
    if ext not in INDEXABLE_EXTENSIONS:
        raise HTTPException(
            400,
            f"此文件类型({ext})不支持转为知识库。仅支持: {', '.join(INDEXABLE_EXTENSIONS)}"
        )

    # 触发索引
    try:
        from app.services.material_indexer import material_indexer
        result = await material_indexer.index_file(
            user_id=USER_ID,
            file_path=storage_path,
            file_name=meta.get("file_name", ""),
            file_type=meta.get("file_type", ""),
            file_size=meta.get("file_size", 0),
        )
        materials_meta.update(material_id, status="ready", chunk_count=result.get("chunk_count", 0), indexed_at=datetime.now().isoformat())
    except Exception as e:
        logger.error(f"索引失败: {e}")
        raise HTTPException(500, f"索引失败: {e}")

    materials_meta.update(material_id, purpose="permanent")
    logger.info("已转为知识库: %s → %d chunks", meta.get("file_name"), result.get("chunk_count", 0))

    return {
        "material_id": material_id,
        "file_name": meta.get("file_name"),
        "status": "ready",
        "chunk_count": result.get("chunk_count", 0),
    }


@router.get("/promote-suggestions")
async def suggest_promotions(limit: int = 5):
    """智能推荐：哪些临时资料值得转为知识库。"""
    _ensure_indexed()
    scored = []

    for mid, meta in materials_meta.get_all().items():
        name_lower = meta.get("file_name", "").lower()
        file_type = meta.get("file_type", "")
        file_size = meta.get("file_size", 0)

        score = 0
        reasons = []

        if file_type == "pdf":
            score += 3
            reasons.append("PDF文档")

        for kw in ["讲义", "笔记", "教材", "习题", "课本", "复习", "期末", "期中", "chapter", "lecture"]:
            if kw in name_lower:
                score += 2
                reasons.append(f"含'{kw}'")
                break

        if file_size > 500 * 1024:
            score += 2
            reasons.append(f"文档较大({file_size // 1024}KB)")

        if file_type in ("docx", "pptx"):
            score += 1
            reasons.append("文档格式")

        if score >= 2:
            scored.append({
                "material_id": mid,
                "file_name": meta.get("file_name"),
                "file_type": file_type,
                "file_size": file_size,
                "score": score,
                "reasons": reasons,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"suggestions": scored[:limit]}


@router.post("/search")
async def search_materials(req: SearchRequest):
    """语义搜索知识库资料（仅 permanent）"""
    from app.services.material_search import material_search as ms
    results = await ms.search(
        user_id=USER_ID, query=req.query,
        material_ids=req.material_ids, skill_id=req.skill_id, top_k=req.top_k,
    )
    return {"results": results, "query": req.query}


@router.get("/{material_id}/chunks")
async def get_material_chunks(material_id: str):
    """获取资料分块"""
    try:
        conn = await _get_db_conn()
        if not conn:
            return {"chunks": []}
        rows = await conn.fetch(
            """SELECT chunk_id, text, chunk_type, skill_ids,
               source_file, page_number, chunk_index
               FROM material_chunks WHERE material_id = $1 ORDER BY chunk_index""",
            material_id,
        )
        await conn.close()
        return {"chunks": [dict(row) for row in rows]}
    except Exception as e:
        logger.error(f"获取分块失败: {e}")
        return {"chunks": []}


@router.post("/generate-questions")
async def generate_from_materials(req: GenerateFromMaterialRequest):
    """基于知识库资料生成练习题"""
    from app.services.material_question_gen import material_question_gen
    from app.schemas.practice import BloomLevel

    bloom = BloomLevel(req.bloom_level) if req.bloom_level else BloomLevel.APPLY
    questions, source_chunks = await material_question_gen.generate_from_materials(
        user_id=USER_ID, material_ids=req.material_ids,
        skill_id=req.skill_id, bloom_level=bloom,
        difficulty=req.difficulty, count=req.count, content_type=req.content_type,
    )
    return {
        "questions": [q.model_dump() for q in questions],
        "source_chunks": source_chunks,
        "count": len(questions),
    }


@router.delete("/{material_id}")
async def delete_material(material_id: str):
    """删除资料。元数据 + 磁盘文件。"""
    # 删除元数据
    materials_meta.delete(material_id)

    # 删除磁盘文件
    deleted = 0
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(material_id):
            os.remove(os.path.join(UPLOAD_DIR, f))
            deleted += 1

    # 同时删除数据库记录（如果有）
    try:
        conn = await _get_db_conn()
        if conn:
            await conn.execute(
                "DELETE FROM materials WHERE material_id=$1 AND user_id=$2",
                material_id, USER_ID,
            )
            await conn.close()
    except Exception:
        pass

    return {"ok": True, "material_id": material_id, "files_deleted": deleted}


@router.post("/cleanup-sessions")
async def cleanup_session_materials():
    """清理过期session资料（7天）。"""
    deleted = 0
    cutoff = datetime.now() - timedelta(days=7)

    for mid, meta in list(materials_meta.get_all().items()):
        try:
            expires_str = meta.get("expires_at")
            if expires_str:
                expires = datetime.fromisoformat(expires_str)
                if expires < cutoff:
                    materials_meta.delete(mid)
                    for f in os.listdir(UPLOAD_DIR):
                        if f.startswith(mid):
                            os.remove(os.path.join(UPLOAD_DIR, f))
                            deleted += 1
        except Exception:
            pass

    return {"ok": True, "deleted": deleted}


# ── 数据库连接 helper ──

async def _get_db_conn():
    import asyncpg
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        return await asyncpg.connect(db_url)
    return None
