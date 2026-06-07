"""学习数据管理 API — 查看/删除/导出当前用户所有学习数据"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from shared.constants import DEFAULT_USER_ID
from app.services.common.storage import storage, get_admin_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/data", tags=["学习数据管理"])

USER_ID = DEFAULT_USER_ID


# ═══════════════════════════════════════════════════════════
# AdminRepository 懒初始化
# ═══════════════════════════════════════════════════════════

_admin_repo = None


def _get_admin_repo():
    """懒初始化 AdminRepository，JSON 模式下返回 None（不抛出异常）。"""
    global _admin_repo
    if _admin_repo is None:
        try:
            _admin_repo = get_admin_repo()
        except RuntimeError:
            _admin_repo = False  # 标记不可用
    return _admin_repo if _admin_repo is not False else None


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

    # 通过 AdminRepository 获取 PG 中的额外数据统计
    repo = _get_admin_repo()
    if repo:
        rows = repo.query("""
            SELECT 
                (SELECT COUNT(*) FROM practice_sessions) AS practice_sessions,
                (SELECT COUNT(*) FROM question_banks) AS question_banks,
                (SELECT COUNT(*) FROM questions) AS questions,
                (SELECT COUNT(*) FROM explain_cards) AS explain_cards,
                (SELECT COUNT(*) FROM messages) AS messages,
                (SELECT COUNT(*) FROM materials) AS materials
        """)
        if rows:
            overview.update({
                "practice_sessions": rows[0].get("practice_sessions", 0),
                "question_banks": rows[0].get("question_banks", 0),
                "questions": rows[0].get("questions", 0),
                "explain_cards": rows[0].get("explain_cards", 0),
                "messages": rows[0].get("messages", 0),
                "materials": rows[0].get("materials", 0),
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
async def list_practice_sessions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """获取练习会话列表"""
    repo = _get_admin_repo()
    if not repo:
        return {"ok": True, "sessions": [], "total": 0, "page": page, "page_size": page_size}
    offset = (page - 1) * page_size
    rows = repo.query(
        "SELECT * FROM practice_sessions ORDER BY created_at DESC LIMIT %s OFFSET %s",
        [page_size, offset]
    )
    total = repo.query("SELECT COUNT(*) as cnt FROM practice_sessions")
    total = total[0]["cnt"] if total else 0
    return {"ok": True, "sessions": rows, "total": total, "page": page, "page_size": page_size}


# ═══════════════════════════════════════════════════════════
# GET /explain-cards — 解释卡片列表
# ═══════════════════════════════════════════════════════════

@router.get("/explain-cards")
async def list_explain_cards(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """获取解释卡片列表"""
    repo = _get_admin_repo()
    if not repo:
        return {"ok": True, "cards": [], "total": 0, "page": page, "page_size": page_size}
    offset = (page - 1) * page_size
    rows = repo.query(
        "SELECT * FROM explain_cards ORDER BY created_at DESC LIMIT %s OFFSET %s",
        [page_size, offset]
    )
    total = repo.query("SELECT COUNT(*) as cnt FROM explain_cards")
    total = total[0]["cnt"] if total else 0
    return {"ok": True, "cards": rows, "total": total, "page": page, "page_size": page_size}


# ═══════════════════════════════════════════════════════════
# GET /materials — 材料列表
# ═══════════════════════════════════════════════════════════

@router.get("/materials")
async def list_materials(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """获取上传材料列表"""
    repo = _get_admin_repo()
    if not repo:
        return {"ok": True, "materials": [], "total": 0, "page": page, "page_size": page_size}
    offset = (page - 1) * page_size
    rows = repo.query(
        "SELECT * FROM materials ORDER BY created_at DESC LIMIT %s OFFSET %s",
        [page_size, offset]
    )
    total = repo.query("SELECT COUNT(*) as cnt FROM materials")
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
    repo = _get_admin_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="PostgreSQL 模式不可用")
    repo.execute("DELETE FROM practice_sessions WHERE id = %s", [session_id])
    repo.execute("DELETE FROM session_questions WHERE session_id = %s", [session_id])
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# DELETE /explain-card/{id} — 删除解释卡片
# ═══════════════════════════════════════════════════════════

@router.delete("/explain-card/{card_id}")
async def delete_explain_card(card_id: str):
    """删除指定解释卡片"""
    repo = _get_admin_repo()
    if not repo:
        raise HTTPException(status_code=400, detail="PostgreSQL 模式不可用")
    repo.execute("DELETE FROM explain_cards WHERE id = %s", [card_id])
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
    
    # 通过 AdminRepository 导出 PG 中的数据
    repo = _get_admin_repo()
    export.update({
        "practice_sessions": repo.query("SELECT * FROM practice_sessions") if repo else [],
        "explain_cards": repo.query("SELECT * FROM explain_cards") if repo else [],
        "materials": repo.query("SELECT * FROM materials") if repo else [],
        "question_banks": repo.query("SELECT * FROM question_banks") if repo else [],
    })
    
    json_str = json.dumps(export, ensure_ascii=False, default=str, indent=2)
    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=edu-companion-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"}
    )
