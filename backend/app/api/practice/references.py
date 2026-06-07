"""
参考资料 API — 知识点/题目关联的多媒体资源搜索

功能:
1. 搜索 B站视频 (知识点讲解)
2. 后续可扩展: 图片搜索、文档搜索、音频搜索
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from shared.constants import DEFAULT_USER_ID
from app.services.materials.bilibili_search import search_bilibili

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v7/practice/references", tags=["参考资料"])


@router.get("/search")
async def api_search_references(
    q: str = Query("", description="搜索关键词"),
    source: str = Query("bilibili", description="资源来源: bilibili"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=30),
    order: str = Query("totalrank", description="排序: totalrank/click/pubdate/dm"),
):
    """搜索参考资料（视频/图文等）"""
    if not q.strip():
        raise HTTPException(400, "搜索关键词不能为空")

    if source == "bilibili":
        result = await search_bilibili(
            query=q.strip(),
            page=page,
            page_size=page_size,
            order=order,
        )
        return result

    raise HTTPException(400, f"不支持的资源来源: {source}")


@router.get("/for-node")
async def api_references_for_node(
    node_id: str = Query("", description="知识点ID"),
    source: str = Query("bilibili"),
):
    """根据知识点搜索参考资料（自动使用节点标签作为关键词）"""
    if not node_id:
        raise HTTPException(400, "node_id 不能为空")

    from app.cognitive.storage import get_node
    node = get_node(node_id, DEFAULT_USER_ID)
    if not node:
        raise HTTPException(404, "知识点不存在")

    query = f"{node.label} 讲解"
    if source == "bilibili":
        result = await search_bilibili(query=query)
        result["node_label"] = node.label
        return result

    raise HTTPException(400, f"不支持的资源来源: {source}")


@router.get("/for-question")
async def api_references_for_question(
    question_id: str = Query("", description="题目ID"),
    source: str = Query("bilibili"),
):
    """根据题目搜索参考资料（使用题干的认知节点标签或题干关键词）"""
    if not question_id:
        raise HTTPException(400, "question_id 不能为空")

    from app.db.database import get_db
    db = get_db()
    question = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not question:
        raise HTTPException(404, "题目不存在")

    # 优先使用认知节点标签作为搜索词
    node_ids = question.get("cognitive_node_ids") or []
    if node_ids:
        from app.cognitive.storage import get_node
        node = get_node(node_ids[0], DEFAULT_USER_ID)
        if node and node.label:
            query = f"{node.label} 讲解"
        else:
            query = question["stem"][:30]
    else:
        query = question["stem"][:30]

    if source == "bilibili":
        result = await search_bilibili(query=query)
        result["search_query"] = query
        return result

    raise HTTPException(400, f"不支持的资源来源: {source}")
