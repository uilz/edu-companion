"""
Phase 10: 笔记 + 目标 + 探索项目 API

功能：
- user_notes CRUD（高亮/自我解释/反思/笔记）
- learning_goals 设定与管理
- exploration_projects 生成与查询
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from shared.constants import DEFAULT_USER_ID, get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/learning", tags=["学习增强"])


# ════════════════════════════════════════
# 请求体
# ════════════════════════════════════════

class NoteCreate(BaseModel):
    content: str
    type: str = "note"          # highlight | explain | reflect | note
    source_text: str = ""
    node_ids: list[str] = Field(default_factory=list)
    message_id: str = ""
    conversation_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoalCreate(BaseModel):
    node_id: str
    node_label: str = ""
    target_mastery: float = 0.8
    target_date: Optional[str] = None
    priority: int = 2
    notes: str = ""


class GoalUpdate(BaseModel):
    target_mastery: Optional[float] = None
    target_date: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    current_mastery: Optional[float] = None
    notes: Optional[str] = None


class ProjectGenerateRequest(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    title_hint: str = ""


# ════════════════════════════════════════
# Notes CRUD
# ════════════════════════════════════════

def _note_row(n: dict) -> dict:
    """标准化笔记输出"""
    return {
        "id": n["id"],
        "user_id": n["user_id"],
        "content": n["content"],
        "type": n["type"],
        "source_text": n["source_text"],
        "node_ids": json.loads(n["node_ids"]) if isinstance(n["node_ids"], str) else (n["node_ids"] or []),
        "message_id": n["message_id"],
        "conversation_id": n["conversation_id"],
        "metadata": json.loads(n["metadata"]) if isinstance(n["metadata"], str) else (n["metadata"] or {}),
        "created_at": n["created_at"].isoformat() if hasattr(n["created_at"], "isoformat") else str(n["created_at"]),
    }


@router.post("/notes", summary="创建笔记")
async def create_note(body: NoteCreate, user_id: str = Query(default=None)):
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    note_id = f"note_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uid}"

    db.execute(
        """INSERT INTO user_notes (id, user_id, content, type, source_text, node_ids, message_id, conversation_id, metadata)
           VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)""",
        (
            note_id, uid, body.content, body.type, body.source_text,
            json.dumps(body.node_ids, ensure_ascii=False),
            body.message_id or None, body.conversation_id or None,
            json.dumps(body.metadata, ensure_ascii=False),
        ),
    )
    logger.info("笔记已创建: %s (type=%s, nodes=%s)", note_id, body.type, body.node_ids)
    return {"id": note_id, "status": "created"}


@router.get("/notes", summary="查询笔记")
async def list_notes(
    user_id: str = Query(default=None),
    node_id: str = Query(default=None),
    note_type: str = Query(default=None, alias="type"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s"]
    params: list[Any] = [uid]

    if node_id:
        conditions.append("node_ids @> %s::jsonb")
        params.append(json.dumps([node_id]))
    if note_type:
        conditions.append("type = %s")
        params.append(note_type)

    sql = f"SELECT * FROM user_notes WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = db.fetchall(sql, tuple(params))
    return [_note_row(r) for r in rows]


@router.get("/notes/{note_id}", summary="获取单个笔记")
async def get_note(note_id: str):
    from app.db.database import get_db
    db = get_db()
    row = db.fetchone("SELECT * FROM user_notes WHERE id = %s", (note_id,))
    if not row:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return _note_row(row)


@router.delete("/notes/{note_id}", summary="删除笔记")
async def delete_note(note_id: str):
    from app.db.database import get_db
    db = get_db()
    db.execute("DELETE FROM user_notes WHERE id = %s", (note_id,))
    return {"status": "deleted", "id": note_id}


@router.post("/notes/aggregate", summary="整理笔记（LLM）")
async def aggregate_notes(
    user_id: str = Query(default=None),
    node_ids: list[str] = Query(default=None),
    time_range: str = Query(default="week"),  # week | month | all
):
    """
    将笔记汇聚为结构化复习文档。
    使用 LLM 将原始笔记整理为分类、有逻辑的复习材料。
    """
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    params: list[Any] = [uid]
    conditions = ["user_id = %s"]

    if node_ids:
        conditions.append("node_ids ?| %s::text[]")
        params.append(node_ids)
    if time_range == "week":
        conditions.append("created_at >= NOW() - INTERVAL '7 days'")
    elif time_range == "month":
        conditions.append("created_at >= NOW() - INTERVAL '30 days'")

    sql = f"SELECT * FROM user_notes WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
    rows = db.fetchall(sql, tuple(params))

    if not rows:
        return {"total": 0, "notes": [], "organized": "", "message": "暂无笔记可整理"}

    notes = [_note_row(r) for r in rows]

    # ── LLM 整理 ──
    try:
        from app.services.llm_service import llm_service

        notes_text = "\n\n".join(
            f"[{n['type']}] {n['content']}"
            f"{' — 原文: ' + n['source_text'] if n['source_text'] else ''}"
            for n in notes
        )

        time_label = {"week": "本周", "month": "本月", "all": "全部"}.get(time_range, time_range)

        system_prompt = (
            "你是一个学习整理助手。将用户的笔记整理为一份结构清晰的复习文档。\n\n"
            "整理要求：\n"
            "1. 按主题/知识点分类归纳\n"
            "2. 每类用简短标题概括\n"
            "3. 保留关键概念和核心理解\n"
            "4. 标注笔记类型（自我解释/反思/笔记）\n"
            "5. 对每类内容加一句[掌握程度]或[复习建议]\n"
            "6. 使用中文，Markdown格式\n"
            "7. 开头用一两句话总结整体学习状态\n"
        )

        user_prompt = (
            f"请整理我{time_label}的学习笔记（共{len(notes)}条）：\n\n{notes_text}"
        )

        organized = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            task_type="chat",
            temperature=0.3,
            max_tokens=2048,
        )

        return {
            "total": len(notes),
            "notes": notes,
            "organized": organized,
            "message": "LLM 整理完成",
        }

    except Exception as e:
        logger.warning("LLM 整理失败，返回原始列表: %s", e)
        return {
            "total": len(notes),
            "notes": notes,
            "organized": "",
            "message": f"LLM 整理暂不可用: {e}",
        }


# ════════════════════════════════════════
# Goals CRUD
# ════════════════════════════════════════

def _goal_row(g: dict) -> dict:
    return {
        "id": g["id"],
        "user_id": g["user_id"],
        "node_id": g["node_id"],
        "node_label": g["node_label"],
        "target_mastery": float(g["target_mastery"]),
        "target_date": str(g["target_date"]) if g.get("target_date") else None,
        "current_mastery": float(g["current_mastery"] or 0),
        "priority": int(g["priority"]),
        "status": g["status"],
        "notes": g["notes"] or "",
        "created_at": g["created_at"].isoformat() if hasattr(g["created_at"], "isoformat") else str(g["created_at"]),
    }


@router.post("/goals", summary="设定学习目标")
async def create_goal(body: GoalCreate, user_id: str = Query(default=None)):
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    goal_id = f"goal_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uid}"
    target_dt = None
    if body.target_date:
        try:
            target_dt = date.fromisoformat(body.target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="target_date 格式无效，使用 YYYY-MM-DD")

    db.execute(
        """INSERT INTO learning_goals (id, user_id, node_id, node_label, target_mastery, target_date, priority, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (goal_id, uid, body.node_id, body.node_label, body.target_mastery, target_dt, body.priority, body.notes),
    )
    logger.info("学习目标已创建: %s -> %s (mastery=%s)", goal_id, body.node_id, body.target_mastery)
    return {"id": goal_id, "status": "created"}


@router.get("/goals", summary="查询学习目标")
async def list_goals(
    user_id: str = Query(default=None),
    node_id: str = Query(default=None),
    status: str = Query(default=None),
):
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s"]
    params: list[Any] = [uid]

    if node_id:
        conditions.append("node_id = %s")
        params.append(node_id)
    if status:
        conditions.append("status = %s")
        params.append(status)

    sql = f"SELECT * FROM learning_goals WHERE {' AND '.join(conditions)} ORDER BY priority ASC, target_date ASC"
    rows = db.fetchall(sql, tuple(params))
    return [_goal_row(r) for r in rows]


@router.put("/goals/{goal_id}", summary="更新学习目标")
async def update_goal(goal_id: str, body: GoalUpdate):
    from app.db.database import get_db
    db = get_db()

    updates: list[str] = []
    params: list[Any] = []

    for field in ("target_mastery", "priority", "current_mastery", "status", "notes"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)

    if body.target_date:
        try:
            target_dt = date.fromisoformat(body.target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="target_date 格式无效")
        updates.append("target_date = %s")
        params.append(target_dt)

    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    updates.append("updated_at = NOW()")
    params.append(goal_id)

    db.execute(f"UPDATE learning_goals SET {', '.join(updates)} WHERE id = %s", tuple(params))
    return {"status": "updated", "id": goal_id}


# ════════════════════════════════════════
# Exploration Projects
# ════════════════════════════════════════

def _project_row(p: dict) -> dict:
    return {
        "id": p["id"],
        "user_id": p["user_id"],
        "title": p["title"],
        "description": p["description"],
        "goal": p["goal"],
        "node_ids": json.loads(p["node_ids"]) if isinstance(p["node_ids"], str) else (p["node_ids"] or []),
        "prerequisites": json.loads(p["prerequisites"]) if isinstance(p["prerequisites"], str) else (p["prerequisites"] or []),
        "deliverables": json.loads(p["deliverables"]) if isinstance(p["deliverables"], str) else (p["deliverables"] or []),
        "status": p["status"],
        "difficulty": float(p["difficulty"]),
        "estimated_hours": float(p["estimated_hours"]),
        "source": p["source"],
        "metadata": json.loads(p["metadata"]) if isinstance(p["metadata"], str) else (p["metadata"] or {}),
        "created_at": p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"]),
    }


@router.post("/projects/generate", summary="生成探索项目")
async def generate_project(
    body: ProjectGenerateRequest,
    user_id: str = Query(default=None),
):
    """基于当前知识点生成小型探索项目。"""
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    # 查询选中节点的信息
    projects = []
    for nid in body.node_ids:
        node = db.fetchone("SELECT id, label FROM cognitive_nodes WHERE id = %s AND user_id = %s", (nid, uid))

        # 构造一个基于模板的项目
        project_id = f"proj_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uid}_{nid.split('.')[-1]}"
        label = node["label"] if node else nid.split(".")[-1]

        title = body.title_hint or f"{label} 探索实践"
        description = f"通过动手实践深入理解「{label}」的概念和应用"

        db.execute(
            """INSERT INTO exploration_projects (id, user_id, title, description, goal, node_ids, status, source)
               VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'suggested', 'system')""",
            (project_id, uid, title, description,
             f"通过项目实践掌握 {label} 的核心概念与应用场景",
             json.dumps([nid], ensure_ascii=False)),
        )
        projects.append({
            "id": project_id,
            "title": title,
            "description": description,
            "node_id": nid,
            "status": "suggested",
        })

    logger.info("探索项目已生成: %d 个", len(projects))
    return {"projects": projects}


@router.get("/projects", summary="查询探索项目")
async def list_projects(
    user_id: str = Query(default=None),
    status: str = Query(default=None),
):
    uid = get_user_id(user_id)
    from app.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s"]
    params: list[Any] = [uid]

    if status:
        conditions.append("status = %s")
        params.append(status)

    sql = f"SELECT * FROM exploration_projects WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
    rows = db.fetchall(sql, tuple(params))
    return [_project_row(r) for r in rows]
