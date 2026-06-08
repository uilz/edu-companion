"""
P1: 全站统一搜索 API
聚合搜索: 对话 → 资料 → 知识点 → 错题
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["搜索"])


class SearchResultItem(BaseModel):
    type: str  # conversation | material | knowledge | error
    title: str
    subtitle: str = ""
    link: str = ""
    score: float = 0.0
    meta: dict = {}


class UnifiedSearchResponse(BaseModel):
    query: str
    conversations: list[SearchResultItem]
    materials: list[SearchResultItem]
    knowledge: list[SearchResultItem]
    errors: list[SearchResultItem]
    total: int


@router.get("", response_model=UnifiedSearchResponse)
async def unified_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(5, ge=1, le=20),
    user_id: str = Depends(current_user_id),
):
    """
    全站统一搜索。
    并行查询 4 个数据源：对话、资料、知识点、错题。
    """
    import asyncio

    results = await asyncio.gather(
        _search_conversations(q, limit, user_id),
        _search_materials(q, limit, user_id),
        _search_knowledge(q, limit, user_id),
        _search_errors(q, limit, user_id),
    )

    convs, mats, know, errs = results

    return UnifiedSearchResponse(
        query=q,
        conversations=convs,
        materials=mats,
        knowledge=know,
        errors=errs,
        total=len(convs) + len(mats) + len(know) + len(errs),
    )


async def _search_conversations(q: str, limit: int, user_id: str) -> list[SearchResultItem]:
    """搜索对话内容（节点 text_summary 模糊匹配）"""
    results: list[SearchResultItem] = []
    q_lower = q.lower()

    try:
        from app.services.common import get_data_repo
        data = get_data_repo().load(user_id)

        for node_id, node in data.nodes.items():
            if node.is_deleted or node.is_archived:
                continue
            if node.role != "user":
                continue  # 只搜用户消息

            text = (node.text_summary or "").lower()
            if q_lower not in text:
                continue

            # 取 partition name
            partition_name = ""
            if node.partition_id in data.partitions:
                partition_name = data.partitions[node.partition_id].name

            results.append(SearchResultItem(
                type="conversation",
                title=node.text_summary[:80] or "(无摘要)",
                subtitle=f"{partition_name} · 分支: {node.branch_id[:8]}",
                link=f"/chat?partition={node.partition_id}&branch={node.branch_id}",
                score=0.85,
                meta={"node_id": node_id, "partition_id": node.partition_id},
            ))

        # 按时间排序
        results.sort(key=lambda r: data.nodes.get(r.meta.get("node_id", ""), None) and -data.nodes[r.meta["node_id"]].timestamp if r.meta.get("node_id") in data.nodes else 0)
        return results[:limit]

    except Exception as e:
        logger.error(f"对话搜索失败: {e}")
        return []


async def _search_materials(q: str, limit: int, user_id: str) -> list[SearchResultItem]:
    """搜索资料（已有语义搜索 API）"""
    results: list[SearchResultItem] = []

    try:
        from app.services.materials.material_search import material_search as ms
        search_results = await ms.search(
            user_id=user_id, query=q, top_k=limit,
        )
        for r in search_results:
            results.append(SearchResultItem(
                type="material",
                title=r.get("source_file", ""),
                subtitle=f"匹配度 {r.get('similarity', 0):.0%}",
                link=f"/chat",
                score=r.get("similarity", 0),
                meta={
                    "material_id": r.get("material_id", ""),
                    "chunk_id": r.get("chunk_id", ""),
                    "text_preview": (r.get("text", "") or "")[:100],
                },
            ))
    except Exception as e:
        logger.error(f"资料搜索失败: {e}")

    return results[:limit]


async def _search_knowledge(q: str, limit: int, user_id: str) -> list[SearchResultItem]:
    """搜索知识点（模糊匹配 name / description）"""
    results: list[SearchResultItem] = []

    try:
        from app.db.database import get_db
        db = get_db()
        q_lower = q.lower().strip()

        rows = db.fetchall(
            "SELECT node_id, label, description, subject "
            "FROM cognitive_nodes "
            "WHERE user_id = %s "
            "  AND (LOWER(label) LIKE %s OR LOWER(description) LIKE %s) "
            "LIMIT %s",
            (user_id, f"%{q_lower}%", f"%{q_lower}%", limit),
        )
        for row in rows:
            results.append(SearchResultItem(
                type="knowledge",
                title=row["label"],
                subtitle=f"{row['subject']} · {row['description'][:60] if row['description'] else ''}",
                link=f"/knowledge?node_id={row['node_id']}",
                score=0.9,
            ))
    except Exception as e:
        logger.error(f"知识点搜索失败: {e}")

    return results[:limit]


async def _search_errors(q: str, limit: int, user_id: str) -> list[SearchResultItem]:
    """搜索错题（按题目内容）"""
    results: list[SearchResultItem] = []

    try:
        from app.db.database import get_db
        db = get_db()
        q_lower = q.lower().strip()

        rows = db.fetchall(
            "SELECT question_id, question_content, correct_answer, skill_id "
            "FROM practice_questions "
            "WHERE user_id = %s LIMIT %s",
            (user_id, limit),
        )
        for row in rows:
            content = (row["question_content"] or "").lower()
            if q_lower not in content:
                continue
            results.append(SearchResultItem(
                type="error",
                title=(row["question_content"] or "")[:80],
                subtitle=f"技能: {row['skill_id']}",
                link=f"/practice/error-book?question_id={row['question_id']}",
                score=0.85,
            ))
    except Exception as e:
        logger.error(f"错题搜索失败: {e}")

    return results[:limit]
