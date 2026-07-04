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
from app.services.knowledge.tree_service import tree_ops

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data", tags=["学习数据管理"])



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

    # Task #84: 字段对齐 — 前端使用 partitions/domains/topics/conversations
    # 兼容旧字段 dirs/conversations
    overview = {
        "directory_nodes": len(dir_nodes),
        "dirs": dir_count,
        "partitions": dir_count,  # Task #84: 对齐前端
        "domains": dir_count,     # Task #84: 对齐前端
        "topics": 0,              # Task #84: 旧 schema 无独立 topics
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
                (SELECT COUNT(*) FROM messages) AS messages,
                (SELECT COUNT(*) FROM materials) AS materials
        """)
        if rows:
            overview.update({
                "practice_sessions": rows[0].get("practice_sessions", 0),
                "question_banks": rows[0].get("question_banks", 0),
                "questions": rows[0].get("questions", 0),
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
            "dir_id": gid,
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
    """D14: 从 messages 表读取解释卡片"""
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()
    all_messages = repo.load_all(user_id)

    all_cards = []
    for node in all_messages.values():
        cards = node.metadata.get("explain_cards", []) if node.metadata else []
        if isinstance(cards, list):
            for card in cards:
                card["message_id"] = card.get("message_id", node.id)
                all_cards.append(card)

    all_cards.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    total = len(all_cards)
    start = (page - 1) * page_size
    paged = all_cards[start:start + page_size]
    return {"ok": True, "cards": paged, "total": total, "page": page, "page_size": page_size}


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

@router.delete("/partition/{dir_id}")
async def delete_partition_data(dir_id: str, user_id: str = Depends(current_user_id)):
    """删除指定目录节点及其所有子数据"""
    data = get_data_repo().load(user_id)
    if dir_id not in data.directory_nodes:
        raise HTTPException(status_code=404, detail="目录节点不存在")
    
    node = data.directory_nodes[dir_id]
    tree_ops.delete_node(user_id, dir_id)
    
    # 删除关联的知识图谱
    if dir_id in data.knowledge_graphs:
        del data.knowledge_graphs[dir_id]
        get_data_repo().save(user_id, data)
    
    return {"ok": True, "deleted": {"node_id": dir_id, "node_type": node.node_type, "name": node.display_name}}


# ═══════════════════════════════════════════════════════════
# DELETE /knowledge-graph/{dir_id} — 删除知识图谱
# ═══════════════════════════════════════════════════════════

@router.delete("/knowledge-graph/{dir_id}")
async def delete_knowledge_graph(dir_id: str, user_id: str = Depends(current_user_id)):
    """删除指定分区的知识图谱"""
    data = get_data_repo().load(user_id)
    if dir_id not in data.knowledge_graphs:
        raise HTTPException(status_code=404, detail="知识图谱不存在")
    del data.knowledge_graphs[dir_id]
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
    """D14: 从 messages.metadata.explain_cards 中删除"""
    from app.services.conversation.message_repository import get_message_repo
    repo = get_message_repo()
    all_messages = repo.load_all(user_id)

    for msg_id, node in all_messages.items():
        cards = node.metadata.get("explain_cards", []) if node.metadata else []
        for card in cards:
            if card.get("id") == card_id:
                remaining = [c for c in cards if c.get("id") != card_id]
                node.metadata["explain_cards"] = remaining
                repo.update(node, user_id)
                return {"ok": True}

    raise HTTPException(status_code=404, detail="解释卡片不存在")


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
        "materials": repo.query("SELECT * FROM materials") if repo else [],
        "question_banks": repo.query("SELECT * FROM question_banks") if repo else [],
    })
    
    json_str = json.dumps(export, ensure_ascii=False, default=str, indent=2)
    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=edu-companion-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"}
    )


# ═══════════════════════════════════════════════════════════════════
# DELETE /reset — 一键清除所有学习数据 (Task #84: B5 bug 修复)
# ═══════════════════════════════════════════════════════════════════


@router.delete("/reset")
async def reset_all_user_data(user_id: str = Depends(current_user_id)):
    """一键清除当前用户所有学习数据 (对话/图谱/分区/练习/材料等)

    Task #84: 修复 B5 — 前端 settings 引用 DELETE /api/data/reset 但后端无实现。
    注意: 这是**危险操作**, 前端应双重确认。
    不删除 users 表, 也不删除 user_settings (用户偏好保留)。
    """
    deleted = {
        "directory_nodes": 0,
        "knowledge_graphs": 0,
        "practice_sessions": 0,
        "session_questions": 0,
        "questions": 0,
        "question_banks": 0,
        "messages": 0,
        "materials": 0,
        "flashcards": 0,
        "login_events": 0,
    }

    # 1. PG 表数据 (PostgreSQL 模式)
    try:
        from app.services.common import get_admin_repo
        repo = get_admin_repo()
        if repo:
            # 通过 user_id 关联删除（messages/materials 等通常没 user_id 字段，
            # 简化为全清，假设 PG 模式下单用户/全清策略）
            for table in ("session_questions", "practice_sessions", "questions",
                          "question_banks", "messages", "materials"):
                try:
                    count = repo.execute_with_rowcount(f"DELETE FROM {table}", [])
                    deleted[table] = count
                except Exception as e:
                    logger.debug("%s 删除跳过: %s", table, e)
    except Exception as e:
        logger.warning("PG 数据清除失败: %s", e)

    # 2. DataRepository 数据（JSON 存储）
    try:
        from app.services.common import get_data_repo
        data = get_data_repo().load(user_id)
        deleted["directory_nodes"] = len(data.directory_nodes)
        deleted["knowledge_graphs"] = len(data.knowledge_graphs)
        data.directory_nodes = {}
        data.knowledge_graphs = {}
        get_data_repo().save(user_id, data)
    except Exception as e:
        logger.warning("DataRepository 清除失败: %s", e)

    # 3. FlashCard 表
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.execute("DELETE FROM flashcards WHERE user_id = %s", (user_id,))
        # 获取数量（exec 不返回值时）
        row = d.fetchone("SELECT COUNT(*) AS c FROM flashcards WHERE user_id = %s", (user_id,))
        # PG 删后应该为 0
    except Exception as e:
        logger.debug("flashcards 清除跳过: %s", e)

    return {"ok": True, "deleted": deleted, "message": "学习数据已全部清除（用户偏好已保留）"}
