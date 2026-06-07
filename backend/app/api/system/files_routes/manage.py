"""文件管理 — 管理：删除/更新/标签/回收站/文件夹/批量/清理/生成练习"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["文件管理"])


# ── 模型 ──

class FilePatchRequest(BaseModel):
    level: str | None = None
    parent_id: str | None = None
    file_name: str | None = None


class UpdateTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None


class BatchOperationRequest(BaseModel):
    material_ids: list[str]
    action: str  # "delete", "move", "add_tags", "remove_tags"
    target_folder_id: Optional[str] = None
    tags: Optional[list[str]] = None


# ── 删除 ──

@router.delete("/{material_id}", summary="删除文件")
async def delete_file(material_id: str, uid: str = Depends(current_user_id)):
    """删除文件及其分块和 TOC"""
    from app.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT storage_path FROM materials WHERE material_id = %s AND user_id = %s",
        (material_id, uid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    db.execute("DELETE FROM material_toc WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM material_chunks WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM materials WHERE material_id = %s", (material_id,))

    storage_path = row.get("storage_path", "")
    if storage_path:
        try:
            Path(storage_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("删除文件失败: %s — %s", storage_path, e)

    return {"status": "deleted", "material_id": material_id}


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


# ── 标签 ──

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


# ── 回收站操作 ──

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

    db.execute("DELETE FROM material_toc WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM material_chunks WHERE material_id = %s", (material_id,))
    db.execute("DELETE FROM materials WHERE material_id = %s", (material_id,))

    if row.get("storage_path"):
        try:
            Path(row["storage_path"]).unlink(missing_ok=True)
        except Exception:
            pass

    return {"ok": True, "message": "已永久删除"}


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


# ── 清理过期文件 ──

@router.post("/cleanup", summary="清理过期临时文件")
async def cleanup_temp_files(uid: str = Depends(current_user_id)):
    """清理过期的 session 文件"""
    from app.db.database import get_db
    db = get_db()

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


# ── 文件夹管理 ──

@router.post("/folder", summary="创建文件夹")
async def create_folder(body: CreateFolderRequest, uid: str = Depends(current_user_id)):
    """创建文件夹"""
    from app.db.database import get_db
    db = get_db()

    folder_id = f"folder_{uid[:8]}_{int(time.time())}"
    db.execute(
        """INSERT INTO materials (material_id, user_id, file_name, file_type, file_size,
                                  purpose, status, is_folder, parent_id, level)
           VALUES (%s, %s, %s, 'folder', 0, 'library', 'indexed', TRUE, %s, 'folder')""",
        (folder_id, uid, body.name, body.parent_id or ""),
    )
    return {"ok": True, "folder_id": folder_id, "name": body.name}


@router.patch("/folder/{folder_id}", summary="更新文件夹")
async def update_folder(
    folder_id: str,
    body: FilePatchRequest,
    uid: str = Depends(current_user_id),
):
    """更新文件夹名称或父文件夹"""
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

    db.execute(
        "UPDATE materials SET parent_id = '' WHERE parent_id = %s AND user_id = %s",
        (folder_id, uid),
    )
    db.execute(
        "UPDATE materials SET is_deleted = TRUE, deleted_at = NOW() WHERE material_id = %s",
        (folder_id,),
    )

    return {"ok": True, "message": "文件夹已删除，内部文件已移至根目录"}


# ── 生成练习 ──

class PracticeGenerateRequest(BaseModel):
    material_ids: list[str]
    count: int = 5
    skill_ids: list[str] | None = None


@router.post("/generate-practice", summary="基于文件生成练习")
async def generate_practice(body: PracticeGenerateRequest, uid: str = Depends(current_user_id)):
    """基于文件分块生成练习题"""
    from app.db.database import get_db
    db = get_db()

    placeholders = ",".join(["%s"] * len(body.material_ids))
    rows = db.fetchall(
        f"SELECT text, material_id FROM material_chunks WHERE material_id IN ({placeholders}) AND user_id = %s LIMIT 30",
        tuple(body.material_ids) + (uid,),
    )

    if not rows:
        raise HTTPException(status_code=400, detail="文件无有效内容，无法生成练习")

    context = "\n\n".join(r["text"][:1000] for r in rows[:5])

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

        import re
        try:
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


# ── 批量操作 ──

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
