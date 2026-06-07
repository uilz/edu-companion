"""文件管理 — 上传 + 后台索引 + 重索引 + stuck 恢复"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from shared.constants import DEFAULT_USER_ID, get_user_id
from app.domain.auth.dependencies import current_user_id
from app.config import COMPANION_HOME

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])

# 上传目录
UPLOAD_DIR = COMPANION_HOME / "uploads"

# 模块级 EventBus（供 _index_background 复用）
_index_event_bus = None


def _get_index_event_bus():
    global _index_event_bus
    if _index_event_bus is None:
        from infra.event_bus import EventBus
        _index_event_bus = EventBus(handler_timeout=5.0)
    return _index_event_bus


# 支持的文件类型
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".md", ".txt", ".html", ".htm",
    ".csv", ".json", ".xml",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp3", ".wav", ".m4a", ".ogg",
    ".zip",
}


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


# ── 上传 ──

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

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    material_id = str(uuid.uuid4())
    content = await file.read()

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


# ── 后台索引 ──

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

        chunk_count = result.get("chunk_count", 0)
        if chunk_count > 0:
            try:
                from domain.materials.service import MaterialServiceImpl

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


# ── 重索引 ──

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
