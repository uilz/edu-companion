"""文件管理 — 上传 + 后台索引 + 重索引 + stuck 恢复"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from app.domain.auth.dependencies import current_user_id
from shared.constants import get_user_id
from app.domain.auth.dependencies import current_user_id
from app.config import COMPANION_HOME

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])

# 上传目录
UPLOAD_DIR = COMPANION_HOME / "uploads"


# 支持的文件类型
ALLOWED_EXTENSIONS = {
    # 文档
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".md", ".txt", ".html", ".htm", ".csv", ".json", ".xml",
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif", ".avif",
    # 音频
    ".mp3", ".wav", ".m4a", ".ogg",
    # 视频
    ".mp4", ".avi", ".mov", ".mkv", ".webm",
    # 压缩
    ".zip",
    # 代码
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".cpp", ".c", ".h", ".hpp",
    ".sql", ".yaml", ".yml", ".toml", ".ini",
    ".rs", ".go", ".rb", ".php", ".swift",
    ".kt", ".scala", ".r", ".lua", ".sh",
    ".vue", ".svelte", ".dart", ".gradle", ".cmake",
    ".tex", ".m", ".mm", ".pl", ".pm",
    # 流程图/思维导图
    ".drawio", ".xmind", ".opml",
}

# 最大文件大小限制（50MB）
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ── 工具函数 ──

def _classify_purpose(file_size: int, upload_source: str) -> str:
    """自动判定文件用途"""
    if file_size > 5_000_000:
        return "library"
    if upload_source == "files_page":
        return "library"
    return "session"


def file_type(ext: str) -> str:
    """扩展名 → 文件类型"""
    if ext in (".pdf",):
        return "pdf"
    if ext in (".docx", ".doc"):
        return "docx"
    if ext in (".pptx", ".ppt"):
        return "pptx"
    if ext in (".xlsx", ".xls"):
        return "xlsx"
    if ext in (".md", ".txt", ".html", ".htm"):
        return "document"
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif", ".avif"):
        return "image"
    if ext in (".mp3", ".wav", ".m4a", ".ogg"):
        return "audio"
    if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return "video"
    if ext in (
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".cpp", ".c", ".h", ".hpp",
        ".sql", ".yaml", ".yml", ".toml", ".ini",
        ".rs", ".go", ".rb", ".php", ".swift",
        ".kt", ".scala", ".r", ".lua", ".sh",
        ".vue", ".svelte", ".dart", ".gradle", ".cmake",
        ".tex", ".m", ".mm", ".pl", ".pm",
    ):
        return "code"
    if ext in (".drawio", ".xmind", ".opml"):
        return "diagram"
    return "other"


# ── 上传 ──

async def _do_upload(
    file: UploadFile,
    purpose: str,
    upload_source: str,
    level: str,
    parent_id: str,
    uid: str,
) -> dict:
    """上传核心逻辑（可被 API 路由和 workspace 入口共用）"""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    # 文件大小限制检查
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE // (1024 * 1024)}MB）")

    material_id = str(uuid.uuid4())
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
    from app.infrastructure.db.database import get_db
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
        "file_type": file_type(ext),
        "status": "uploading",
    }


@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = Form(default="auto"),
    upload_source: str = Form(default="files_page"),
    level: str = Form(default="partition"),
    parent_id: str = Form(default=""),
    uid: str = Depends(current_user_id),
):
    """上传文件，自动解析+索引。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    return await _do_upload(file, purpose, upload_source, level, parent_id, uid)


# ── 后台索引 ──

async def _index_background(
    user_id: str, material_id: str, file_path: str,
    file_name: str, file_type: str, file_size: int, purpose: str,
):
    """后台异步索引"""
    try:
        from app.infrastructure.files.indexer import material_indexer
        result = await material_indexer.index_file(
            user_id, material_id, file_path, file_name,
            file_type, file_size, purpose,
        )
        logger.info("后台索引完成: %s → %s", material_id, result["status"])
    except Exception as e:
        logger.error("后台索引失败: %s — %s", material_id, e)
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            db.execute(
                "UPDATE materials SET status = 'index_failed' WHERE material_id = %s",
                (material_id,),
            )
        except Exception:
            pass


# ── 重索引 ──

@router.post("/{material_id}/reindex", summary="重新索引文件")
async def reindex_file(material_id: str, uid: str = Depends(current_user_id)):
    """手动触发文件重新索引（用于修复 stuck 文件）"""
    from app.infrastructure.db.database import get_db
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
    from app.infrastructure.db.database import get_db
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
