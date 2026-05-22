"""
P1: 全站统一搜索 API
聚合搜索: 对话 → 资料 → 知识点 → 错题
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["搜索"])

USER_ID = "default_user"


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
):
    """
    全站统一搜索。
    并行查询 4 个数据源：对话、资料、知识点、错题。
    """
    import asyncio

    results = await asyncio.gather(
        _search_conversations(q, limit),
        _search_materials(q, limit),
        _search_knowledge(q, limit),
        _search_errors(q, limit),
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


async def _search_conversations(q: str, limit: int) -> list[SearchResultItem]:
    """搜索对话内容（节点 text_summary 模糊匹配）"""
    results: list[SearchResultItem] = []
    q_lower = q.lower()

    try:
        from app.services.storage import storage
        data = storage.load(USER_ID)

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


async def _search_materials(q: str, limit: int) -> list[SearchResultItem]:
    """搜索资料（已有语义搜索 API）"""
    results: list[SearchResultItem] = []

    try:
        from app.services.material_search import material_search as ms
        search_results = await ms.search(
            user_id=USER_ID, query=q, top_k=limit,
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
    except Exception:
        # DB 不可用时降级到元数据搜索
        from app.services.materials_meta import materials_meta
        q_lower = q.lower()
        for mid, meta in materials_meta.get_all().items():
            if q_lower in meta.get("file_name", "").lower():
                results.append(SearchResultItem(
                    type="material",
                    title=meta.get("file_name", ""),
                    subtitle=f"{meta.get('file_type', '')} · {meta.get('file_size', 0) // 1024}KB",
                    link=f"/chat",
                    score=0.7,
                    meta={"material_id": mid},
                ))
            if len(results) >= limit:
                break

    return results


async def _search_knowledge(q: str, limit: int) -> list[SearchResultItem]:
    """搜索知识点"""
    results: list[SearchResultItem] = []
    q_lower = q.lower()

    try:
        # ── CognitiveNode 搜索 (Phase 6) ──
        try:
            from app.db.database import get_db
            db = get_db()
            cog_rows = db.fetchall(
                "SELECT id, label, belief FROM cognitive_nodes "
                "WHERE user_id = %s AND (LOWER(id) LIKE %s OR LOWER(label) LIKE %s) "
                "LIMIT 10",
                (USER_ID, f"%{q_lower}%", f"%{q_lower}%")
            )
            for r in cog_rows:
                belief = r.get("belief", {})
                if isinstance(belief, str):
                    import json
                    try:
                        belief = json.loads(belief)
                    except Exception:
                        belief = {}
                mu = belief.get("proficiency_mean", 0.5) if isinstance(belief, dict) else 0.5
                label = r.get("label", r["id"])
                results.append(SearchResultItem(
                    type="knowledge",
                    title=label,
                    subtitle=f"掌握 {mu:.0%} (CognitiveNode)",
                    link=f"/graph?skill={r['id']}",
                    score=mu,
                    meta={"skill_id": r["id"], "mastery": mu},
                ))
        except Exception:
            pass

        from app.core.learner_model import learner_engine
        # 遍历知识点存储
        for skill_id, state in getattr(learner_engine, "_knowledge_states", {}).items():
            if q_lower in skill_id.lower():
                mastery = state.get("p_know", 0) if isinstance(state, dict) else 0.5
                results.append(SearchResultItem(
                    type="knowledge",
                    title=skill_id.replace("_", " ").title(),
                    subtitle=f"掌握 {mastery:.0%}",
                    link=f"/graph?skill={skill_id}",
                    score=mastery,
                    meta={"skill_id": skill_id, "mastery": mastery},
                ))

        # 也检查 userData knowledge_states
        from app.services.storage import storage
        data = storage.load(USER_ID)
        for skill_id, state in data.knowledge_states.items():
            if q_lower in skill_id.lower():
                mastery = state.get("p_know", state.get("mastery", 0.5))
                results.append(SearchResultItem(
                    type="knowledge",
                    title=skill_id.replace("_", " ").title(),
                    subtitle=f"掌握 {mastery:.0%}",
                    link=f"/graph?skill={skill_id}",
                    score=mastery,
                    meta={"skill_id": skill_id, "mastery": mastery},
                ))

        return results[:limit]

    except Exception as e:
        logger.error(f"知识点搜索失败: {e}")
        return []


async def _search_errors(q: str, limit: int) -> list[SearchResultItem]:
    """搜索错题"""
    results: list[SearchResultItem] = []
    q_lower = q.lower()

    try:
        from app.services.storage import storage
        data = storage.load(USER_ID)

        for error_list in data.error_book.values():
            for entry in error_list:
                if not isinstance(entry, dict):
                    continue
                question = (entry.get("question_text") or entry.get("question_id") or "").lower()
                if q_lower in question:
                    results.append(SearchResultItem(
                        type="error",
                        title=(entry.get("question_text") or entry.get("question_id") or "错题")[:80],
                        subtitle=f"错因: {entry.get('error_type', entry.get('attribution', '未知'))}",
                        link="/errors",
                        score=0.6,
                        meta={"error_id": entry.get("id", ""), "skill_id": entry.get("skill_id", "")},
                    ))

        return results[:limit]

    except Exception as e:
        logger.error(f"错题搜索失败: {e}")
        return []
