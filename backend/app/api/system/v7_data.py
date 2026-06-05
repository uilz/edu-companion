"""学习数据管理 API — 查看/删除/导出当前用户所有学习数据"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from shared.constants import DEFAULT_USER_ID
from app.services.common.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/data", tags=["学习数据管理"])

USER_ID = DEFAULT_USER_ID


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _get_db():
    from app.services.common.storage import storage
    data = storage.load(USER_ID)
    # 尝试获取 PostgreSQL 连接
    try:
        from app.services.common.storage import storage as st
        if hasattr(st, "_pg_pool") and st._pg_pool:
            return st._pg_pool
    except Exception:
        pass
    return None


def _pg_query(sql: str, params: list = None):
    """执行 PG 查询并返回结果列表"""
    import asyncpg
    pool = _get_db()
    if not pool:
        return []
    try:
        import asyncio
        async def _run():
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *(params or []))
                return [dict(r) for r in rows]
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception:
        return []


def _pg_execute(sql: str, params: list = None):
    """执行 PG 写操作"""
    pool = _get_db()
    if not pool:
        return None
    try:
        import asyncio
        async def _run():
            async with pool.acquire() as conn:
                return await conn.execute(sql, *(params or []))
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# GET /overview — 学习数据概览
# ═══════════════════════════════════════════════════════════

@router.get("/overview")
async def data_overview():
    """获取用户所有学习数据的概览统计"""
    data = storage.load(USER_ID)
    
    overview = {
        "partitions": len(data.partitions),
        "domains": len(data.domains),
        "topics": len(data.topics),
        "conversations": len(data.conversations),
        "knowledge_graphs": len(data.knowledge_graphs),
        "graph_nodes": sum(len(g.nodes) for g in data.knowledge_graphs.values()),
        "graph_edges": sum(len(g.edges) for g in data.knowledge_graphs.values()),
    }

    # 尝试获取 PG 中的数据统计
    pg_stats = _pg_query("""
        SELECT 
            (SELECT COUNT(*) FROM v7_practice_sessions) AS practice_sessions,
            (SELECT COUNT(*) FROM v7_question_banks) AS question_banks,
            (SELECT COUNT(*) FROM v7_questions) AS questions,
            (SELECT COUNT(*) FROM explain_cards) AS explain_cards,
            (SELECT COUNT(*) FROM messages) AS messages,
            (SELECT COUNT(*) FROM materials) AS materials
    """)
    if pg_stats:
        overview.update({
            "practice_sessions": pg_stats[0].get("practice_sessions", 0),
            "question_banks": pg_stats[0].get("question_banks", 0),
            "questions": pg_stats[0].get("questions", 0),
            "explain_cards": pg_stats[0].get("explain_cards", 0),
            "messages": pg_stats[0].get("messages", 0),
            "materials": pg_stats[0].get("materials", 0),
        })

    return {"ok": True, "overview": overview}


# ═══════════════════════════════════════════════════════════
# GET /partitions — 分区列表
# ═══════════════════════════════════════════════════════════

@router.get("/partitions")
async def list_partitions():
    """获取所有分区及其子结构"""
    data = storage.load(USER_ID)
    partitions = []
    for pid, p in data.partitions.items():
        domains = [d.model_dump(mode="json") for d in data.domains.values() if d.partition_id == pid]
        topics = []
        for d in data.domains.values():
            if d.partition_id == pid:
                for t in data.topics.values():
                    if t.domain_id == d.id:
                        topics.append(t.model_dump(mode="json"))
        conversations = []
        for t in data.topics.values():
            for c in data.conversations.values():
                if c.topic_id == t.id:
                    conversations.append(c.model_dump(mode="json"))
        
        partitions.append({
            "partition": p.model_dump(mode="json"),
            "domains": domains,
            "topics": topics,
            "conversations": conversations,
            "domain_count": len(domains),
            "topic_count": len(topics),
            "conversation_count": len(conversations),
        })
    return {"ok": True, "partitions": partitions}


# ═══════════════════════════════════════════════════════════
# GET /knowledge-graphs — 知识图谱列表
# ═══════════════════════════════════════════════════════════

@router.get("/knowledge-graphs")
async def list_knowledge_graphs():
    """获取所有知识图谱"""
    data = storage.load(USER_ID)
    graphs = []
    for gid, g in data.knowledge_graphs.items():
        partition = data.partitions.get(gid)
        graphs.append({
            "partition_id": gid,
            "partition_name": partition.name if partition else "未知",
            "name": g.name,
            "version": g.version,
            "node_count": len(g.nodes),
            "edge_count": len(g.edges),
            "nodes": {nid: n.model_dump(mode="json") for nid, n in g.nodes.items()},
            "edges": [e.model_dump(mode="json") for e in g.edges],
        })
    return {"ok": True, "knowledge_graphs": graphs}


# ═══════════════════════════════════════════════════════════
# GET /practice-sessions — 练习会话列表
# ═══════════════════════════════════════════════════════════

@router.get("/practice-sessions")
async def list_practice_sessions(page: int = 1, page_size: int = 20):
    """获取练习会话列表"""
    offset = (page - 1) * page_size
    rows = _pg_query(
        "SELECT * FROM v7_practice_sessions ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        [page_size, offset]
    )
    total = _pg_query("SELECT COUNT(*) as cnt FROM v7_practice_sessions")
    total = total[0]["cnt"] if total else 0
    return {"ok": True, "sessions": rows, "total": total, "page": page, "page_size": page_size}


# ═══════════════════════════════════════════════════════════
# GET /explain-cards — 解释卡片列表
# ═══════════════════════════════════════════════════════════

@router.get("/explain-cards")
async def list_explain_cards(page: int = 1, page_size: int = 20):
    """获取解释卡片列表"""
    offset = (page - 1) * page_size
    rows = _pg_query(
        "SELECT * FROM explain_cards ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        [page_size, offset]
    )
    total = _pg_query("SELECT COUNT(*) as cnt FROM explain_cards")
    total = total[0]["cnt"] if total else 0
    return {"ok": True, "cards": rows, "total": total, "page": page, "page_size": page_size}


# ═══════════════════════════════════════════════════════════
# GET /materials — 材料列表
# ═══════════════════════════════════════════════════════════

@router.get("/materials")
async def list_materials(page: int = 1, page_size: int = 20):
    """获取上传材料列表"""
    offset = (page - 1) * page_size
    rows = _pg_query(
        "SELECT * FROM materials ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        [page_size, offset]
    )
    total = _pg_query("SELECT COUNT(*) as cnt FROM materials")
    total = total[0]["cnt"] if total else 0
    return {"ok": True, "materials": rows, "total": total, "page": page, "page_size": page_size}


# ═══════════════════════════════════════════════════════════
# DELETE /partition/{id} — 删除分区（含所有子数据）
# ═══════════════════════════════════════════════════════════

@router.delete("/partition/{partition_id}")
async def delete_partition_data(partition_id: str):
    """删除指定分区及其所有子数据（领域、专题、对话、知识图谱）"""
    data = storage.load(USER_ID)
    if partition_id not in data.partitions:
        raise HTTPException(status_code=404, detail="分区不存在")
    
    # 删除子领域
    domain_ids = [d.id for d in data.domains.values() if d.partition_id == partition_id]
    for did in domain_ids:
        del data.domains[did]
    
    # 删除子专题
    topic_ids = [t.id for t in data.topics.values() if t.domain_id in domain_ids]
    for tid in topic_ids:
        del data.topics[tid]
    
    # 删除子对话
    conv_ids = [c.id for c in data.conversations.values() if c.topic_id in topic_ids]
    for cid in conv_ids:
        del data.conversations[cid]
    
    # 删除知识图谱
    if partition_id in data.knowledge_graphs:
        del data.knowledge_graphs[partition_id]
    
    # 删除分区
    del data.partitions[partition_id]
    
    storage.save(USER_ID, data)
    return {"ok": True, "deleted": {"partition_id": partition_id, "domains": len(domain_ids), "topics": len(topic_ids), "conversations": len(conv_ids)}}


# ═══════════════════════════════════════════════════════════
# DELETE /knowledge-graph/{partition_id} — 删除知识图谱
# ═══════════════════════════════════════════════════════════

@router.delete("/knowledge-graph/{partition_id}")
async def delete_knowledge_graph(partition_id: str):
    """删除指定分区的知识图谱"""
    data = storage.load(USER_ID)
    if partition_id not in data.knowledge_graphs:
        raise HTTPException(status_code=404, detail="知识图谱不存在")
    del data.knowledge_graphs[partition_id]
    storage.save(USER_ID, data)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# DELETE /practice-session/{id} — 删除练习会话
# ═══════════════════════════════════════════════════════════

@router.delete("/practice-session/{session_id}")
async def delete_practice_session(session_id: str):
    """删除指定练习会话"""
    _pg_execute("DELETE FROM v7_practice_sessions WHERE id = $1", [session_id])
    _pg_execute("DELETE FROM v7_session_questions WHERE session_id = $1", [session_id])
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# DELETE /explain-card/{id} — 删除解释卡片
# ═══════════════════════════════════════════════════════════

@router.delete("/explain-card/{card_id}")
async def delete_explain_card(card_id: str):
    """删除指定解释卡片"""
    _pg_execute("DELETE FROM explain_cards WHERE id = $1", [card_id])
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# POST /export — 导出所有学习数据
# ═══════════════════════════════════════════════════════════

@router.post("/export")
async def export_all_data():
    """导出当前用户所有学习数据为 JSON"""
    data = storage.load(USER_ID)
    
    export = {
        "exported_at": datetime.now().isoformat(),
        "user_id": USER_ID,
        "partitions": {pid: p.model_dump(mode="json") for pid, p in data.partitions.items()},
        "domains": {did: d.model_dump(mode="json") for did, d in data.domains.items()},
        "topics": {tid: t.model_dump(mode="json") for tid, t in data.topics.items()},
        "conversations": {cid: c.model_dump(mode="json") for cid, c in data.conversations.items()},
        "knowledge_graphs": {gid: g.model_dump(mode="json") for gid, g in data.knowledge_graphs.items()},
    }
    
    # 尝试导出 PG 数据
    practice_sessions = _pg_query("SELECT * FROM v7_practice_sessions")
    explain_cards = _pg_query("SELECT * FROM explain_cards")
    materials = _pg_query("SELECT * FROM materials")
    question_banks = _pg_query("SELECT * FROM v7_question_banks")
    
    export.update({
        "practice_sessions": practice_sessions,
        "explain_cards": explain_cards,
        "materials": materials,
        "question_banks": question_banks,
    })
    
    json_str = json.dumps(export, ensure_ascii=False, default=str, indent=2)
    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=edu-companion-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"}
    )