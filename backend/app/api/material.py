"""
资料管理 API v1.2

设计原则：
- 所有上传默认临时(session)，不自动索引，节省资源
- 用户手动"转为知识库"时才建立索引(embedding+pgvector)
- 系统智能推荐哪些临时资料值得转知识库
- 临时资料7天自动清理(可配置)
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
    purpose: str = Form("session"),  # 默认临时！
):
    """
    上传资料文件。
    默认 purpose=session（临时，不索引）。
    用户可通过 /promote 转为 permanent 触发索引。

    purpose:
      - session: 临时资料 — 仅保存文件，7天自动清理
      - permanent: 知识库资料 — 需要 /promote 转换后才会索引
      - reference: 参考资料 — 保存但不索引
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
    if purpose not in ("session", "permanent", "reference"):
        purpose = "session"

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

    logger.info("上传完成: %s (%s, %s, %d bytes)", file.filename, file_type, purpose, file_size)

    return {
        "material_id": material_id,
        "file_name": file.filename,
        "file_type": file_type,
        "file_size": file_size,
        "purpose": purpose,
        "status": "stored",
        "chunk_count": 0,
        "expires_at": (datetime.now() + timedelta(days=7)).isoformat() if purpose == "session" else None,
    }


@router.post("/{material_id}/promote")
async def promote_to_permanent(material_id: str):
    """
    将临时资料转为知识库资料，触发全文索引。
    这是从 session → permanent 的唯一通道。
    """
    conn = await _get_db_conn()
    storage_path = None

    if conn:
        try:
            # 查当前状态
            row = await conn.fetchrow(
                "SELECT storage_path, file_type, file_name, file_size FROM materials WHERE material_id=$1 AND user_id=$2",
                material_id, USER_ID,
            )
            if row:
                storage_path = row["storage_path"]
                file_type = row["file_type"]
                file_name = row["file_name"]
                file_size = row["file_size"]
            else:
                # DB中还没有记录（session未入库），先插入
                for f in os.listdir(UPLOAD_DIR):
                    if f.startswith(material_id):
                        storage_path = os.path.join(UPLOAD_DIR, f)
                        file_type = _file_type(os.path.splitext(f)[1])
                        file_name = f[37:] if len(f) > 37 else f
                        file_size = os.path.getsize(storage_path)
                        break
        finally:
            await conn.close()

    if not storage_path or not os.path.isfile(storage_path):
        raise HTTPException(404, "文件不存在，可能已被清理")

    # 检查是否可索引
    ext = os.path.splitext(storage_path)[1].lower()
    if ext not in INDEXABLE_EXTENSIONS:
        raise HTTPException(
            400,
            f"此文件类型({ext})不支持转为知识库。仅支持: {', '.join(INDEXABLE_EXTENSIONS)}"
        )

    # 触发索引
    from app.services.material_indexer import material_indexer
    result = await material_indexer.index_file(
        user_id=USER_ID,
        file_path=storage_path,
        file_name=file_name,
        file_type=file_type,
        file_size=file_size,
    )

    # 更新 purpose + storage_path
    conn = await _get_db_conn()
    if conn:
        try:
            await conn.execute(
                "UPDATE materials SET purpose='permanent', storage_path=$1, status=$2, chunk_count=$3 WHERE material_id=$4",
                storage_path, "ready", result["chunk_count"], result["material_id"],
            )
        finally:
            await conn.close()

    logger.info("已转为知识库: %s → %d chunks", file_name, result["chunk_count"])
    return {
        "material_id": result["material_id"],
        "file_name": file_name,
        "status": "ready",
        "chunk_count": result["chunk_count"],
    }


@router.get("/promote-suggestions")
async def suggest_promotions(limit: int = 5):
    """
    智能推荐：哪些临时资料值得转为知识库。

    规则：
    - 同一天上传 ≥3 个文件 → 可能是在批量上传讲义 → 推荐全部
    - PDF 文件 → 可能是讲义 → 推荐
    - 文件名含"讲义/笔记/教材/习题" → 推荐
    - 大文件(>500KB) → 可能是完整文档 → 推荐
    """
    suggestions = []
    scored = []

    for f in os.listdir(UPLOAD_DIR):
        fpath = os.path.join(UPLOAD_DIR, f)
        if not os.path.isfile(fpath):
            continue

        score = 0
        reasons = []
        name_lower = f.lower()
        ext = os.path.splitext(f)[1].lower()
        size = os.path.getsize(fpath)
        material_id = f[:36] if len(f) > 36 else f

        # 规则1: PDF → +3
        if ext == ".pdf":
            score += 3
            reasons.append("PDF文档")

        # 规则2: 文件名关键词 → +2
        for kw in ["讲义", "笔记", "教材", "习题", "课本", "复习", "期末", "期中", "chapter", "lecture"]:
            if kw in name_lower:
                score += 2
                reasons.append(f"含'{kw}'")
                break

        # 规则3: 大文件(>500KB) → +2
        if size > 500 * 1024:
            score += 2
            reasons.append(f"文档较大({size // 1024}KB)")

        # 规则4: Word/PPT → +1
        if ext in (".docx", ".pptx"):
            score += 1
            reasons.append("文档格式")

        # 规则5: 同一天有多个文件 → batch bonus
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        same_day = sum(
            1 for f2 in os.listdir(UPLOAD_DIR)
            if os.path.isfile(os.path.join(UPLOAD_DIR, f2))
            and abs(datetime.fromtimestamp(os.path.getmtime(os.path.join(UPLOAD_DIR, f2))) - mtime).days < 1
        )
        if same_day >= 3:
            score += 3
            reasons.append(f"同日上传{same_day}个文件")

        if score >= 2:
            scored.append({
                "material_id": material_id,
                "file_name": f[37:] if len(f) > 37 else f,
                "file_type": _file_type(ext),
                "file_size": size,
                "score": score,
                "reasons": reasons,
            })

    # 按评分排序
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"suggestions": scored[:limit]}


@router.get("")
async def list_materials(purpose: str = ""):
    """获取用户资料列表"""
    try:
        conn = await _get_db_conn()
        if conn:
            query = """SELECT material_id, file_name, file_type, file_size, 
                       status, purpose, chunk_count, skills_covered,
                       storage_path, created_at, indexed_at, expires_at
                       FROM materials WHERE user_id = $1"""
            params = [USER_ID]
            if purpose:
                query += " AND purpose = $2"
                params.append(purpose)
            query += " ORDER BY created_at DESC"
            rows = await conn.fetch(query, *params)
            await conn.close()

            db_materials = {row["material_id"]: row for row in rows}
        else:
            db_materials = {}

        # 合并文件系统中的资料（session未入库的）
        materials = []
        seen = set()

        for f in sorted(os.listdir(UPLOAD_DIR), reverse=True):
            fpath = os.path.join(UPLOAD_DIR, f)
            if not os.path.isfile(fpath):
                continue
            material_id = f[:36] if len(f) > 36 else f
            if material_id in seen:
                continue
            seen.add(material_id)

            row = db_materials.get(material_id)
            if row:
                materials.append({
                    "material_id": row["material_id"],
                    "file_name": row["file_name"],
                    "file_type": row["file_type"],
                    "file_size": row["file_size"],
                    "purpose": row["purpose"] or "session",
                    "status": row["status"],
                    "chunk_count": row["chunk_count"],
                    "skills_covered": row["skills_covered"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "indexed_at": row["indexed_at"].isoformat() if row["indexed_at"] else None,
                    "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
                })
            else:
                # 文件系统资料（session，未入库）
                ext = os.path.splitext(f)[1].lower()
                materials.append({
                    "material_id": material_id,
                    "file_name": f[37:] if len(f) > 37 else f,
                    "file_type": _file_type(ext),
                    "file_size": os.path.getsize(fpath),
                    "purpose": "session",
                    "status": "stored",
                    "chunk_count": 0,
                    "skills_covered": [],
                    "created_at": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                    "indexed_at": None,
                    "expires_at": (datetime.fromtimestamp(os.path.getmtime(fpath)) + timedelta(days=7)).isoformat(),
                })

        return {"materials": materials, "total": len(materials)}
    except Exception as e:
        logger.error(f"获取资料列表失败: {e}")
        return {"materials": [], "total": 0}


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
    """删除资料。DB级联删除chunks + 磁盘文件。"""
    storage_path = None
    try:
        conn = await _get_db_conn()
        if conn:
            row = await conn.fetchrow(
                "SELECT storage_path FROM materials WHERE material_id=$1 AND user_id=$2",
                material_id, USER_ID,
            )
            if row:
                storage_path = row["storage_path"]
            await conn.execute(
                "DELETE FROM materials WHERE material_id=$1 AND user_id=$2",
                material_id, USER_ID,
            )
            await conn.close()
    except Exception as e:
        logger.error(f"DB删除失败: {e}")

    if storage_path and os.path.isfile(storage_path):
        os.remove(storage_path)
    else:
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith(material_id):
                os.remove(os.path.join(UPLOAD_DIR, f))

    return {"ok": True, "material_id": material_id}


@router.post("/cleanup-sessions")
async def cleanup_session_materials():
    """清理过期session资料（7天）。可cron定时调用。"""
    deleted = 0
    try:
        conn = await _get_db_conn()
        if conn:
            rows = await conn.fetch(
                """SELECT material_id, storage_path FROM materials
                   WHERE user_id=$1 AND purpose='session'
                   AND (expires_at IS NULL OR expires_at < $2)""",
                USER_ID, datetime.now(),
            )
            for row in rows:
                await conn.execute("DELETE FROM materials WHERE material_id=$1", row["material_id"])
                if row["storage_path"] and os.path.isfile(row["storage_path"]):
                    os.remove(row["storage_path"])
                deleted += 1
            await conn.close()

        # 文件系统过期清理
        cutoff = datetime.now() - timedelta(days=7)
        for f in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(fpath) and datetime.fromtimestamp(os.path.getmtime(fpath)) < cutoff:
                os.remove(fpath)
                deleted += 1

        return {"ok": True, "deleted": deleted}
    except Exception as e:
        return {"ok": False, "error": str(e)}
