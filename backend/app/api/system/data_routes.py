"""学习数据管理 API — 查看/删除/导出当前用户所有学习数据"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.domain.auth.dependencies import current_user_id
from app.services.common import get_data_repo, get_admin_repo
from app.services.knowledge.tree_ops import tree_ops

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/data", tags=["学习数据管理"])



# ═══════════════════════════════════════════════════════════
# AdminRepository（始终可用）
# ═══════════════════════════════════════════════════════════

_admin_repo = None


def _get_admin_repo():
    global _admin_repo
    if _admin_repo is None:
        _admin_repo = get_admin_repo()
    return _admin_repo


# ═══════════════════════════════════════════════════════════
# GET /overview — 学习数据概览
# ═══════════════════════════════════════════════════════════

@router.get("/overview")
async def data_overview(user_id: str = Depends(current_user_id)):
    """获取用户所有学习数据的概览统计"""
    data = get_data_repo().load(user_id)
    
    dir_nodes = data.directory_nodes or {}
    dir_count = sum(1 for n in dir_nodes.values() if n.node_type == "dir")
    conv_count = sum(1 for n in dir_nodes.values() if n.node_type == "conv")
    
    overview = {
        "directory_nodes": len(dir_nodes),
        "dirs": dir_count,
        "conversations": conv_count,
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
async def list_partitions(user_id: str = Depends(current_user_id)):
    """获取目录树结构"""
    tree = tree_ops.build_tree(user_id)
    
    # 统计各类型节点数量
    def count_nodes(nodes):
        dirs = convs = 0
        for n in nodes:
            if n["node_type"] == "dir":
                dirs += 1
                cd, cc = count_nodes(n.get("children", []))
                dirs += cd
                convs += cc
            else:
                convs += 1
        return dirs, convs
    
    dir_count, conv_count = count_nodes(tree)
    
    return {
        "ok": True,
        "tree": tree,
        "dir_count": dir_count,
        "conversation_count": conv_count,
    }


# ═══════════════════════════════════════════════════════════
# GET /knowledge-graphs — 知识图谱列表
# ═══════════════════════════════════════════════════════════

@router.get("/knowledge-graphs")
async def list_knowledge_graphs(user_id: str = Depends(current_user_id)):
    """获取所有知识图谱"""
    data = get_data_repo().load(user_id)
    graphs = []
    for gid, g in data.knowledge_graphs.items():
        dir_node = data.directory_nodes.get(gid)
        graphs.append({
            "partition_id": gid,
            "partition_name": dir_node.display_name if dir_node else "未知",
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
async def list_practice_sessions(user_id: str = Depends(current_user_id), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
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
async def list_explain_cards(user_id: str = Depends(current_user_id), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
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
async def list_materials(user_id: str = Depends(current_user_id), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
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
async def delete_partition_data(partition_id: str, user_id: str = Depends(current_user_id)):
    """删除指定目录节点及其所有子数据"""
    data = get_data_repo().load(user_id)
    if partition_id not in data.directory_nodes:
        raise HTTPException(status_code=404, detail="目录节点不存在")
    
    node = data.directory_nodes[partition_id]
    tree_ops.delete_node(user_id, partition_id)
    
    # 删除关联的知识图谱
    if partition_id in data.knowledge_graphs:
        del data.knowledge_graphs[partition_id]
        get_data_repo().save(user_id, data)
    
    return {"ok": True, "deleted": {"node_id": partition_id, "node_type": node.node_type, "name": node.display_name}}


# ═══════════════════════════════════════════════════════════
# DELETE /knowledge-graph/{partition_id} — 删除知识图谱
# ═══════════════════════════════════════════════════════════

@router.delete("/knowledge-graph/{partition_id}")
async def delete_knowledge_graph(partition_id: str, user_id: str = Depends(current_user_id)):
    """删除指定分区的知识图谱"""
    data = get_data_repo().load(user_id)
    if partition_id not in data.knowledge_graphs:
        raise HTTPException(status_code=404, detail="知识图谱不存在")
    del data.knowledge_graphs[partition_id]
    get_data_repo().save(user_id, data)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# DELETE /practice-session/{id} — 删除练习会话
# ═══════════════════════════════════════════════════════════

@router.delete("/practice-session/{session_id}")
async def delete_practice_session(session_id: str, user_id: str = Depends(current_user_id)):
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
async def delete_explain_card(card_id: str, user_id: str = Depends(current_user_id)):
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
async def export_all_data(user_id: str = Depends(current_user_id)):
    """导出当前用户所有学习数据为 JSON"""
    data = get_data_repo().load(user_id)
    
    export = {
        "exported_at": datetime.now().isoformat(),
        "user_id": user_id,
        "directory_nodes": {nid: n.model_dump(mode="json") for nid, n in data.directory_nodes.items()},
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
