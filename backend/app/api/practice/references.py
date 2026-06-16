"""
参考资料 API — 知识点/题目关联的多媒体资源搜索

功能:
1. 搜索 B站视频 (知识点讲解)
2. 后续可扩展: 图片搜索、文档搜索、音频搜索
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from app.domain.auth.dependencies import current_user_id
from app.infrastructure.media.bilibili_search import search_bilibili

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
    user_id: str = Depends(current_user_id),
):
    """根据知识点搜索参考资料（自动使用节点标签作为关键词）"""
    if not node_id:
        raise HTTPException(400, "node_id 不能为空")

    from app.domain.cognitive import get_repo
    node = get_repo().get_node(node_id, user_id)
    if not node:
        raise HTTPException(404, "知识点不存在")

    query = f"{node.label} 讲解"
    if source == "bilibili":
        result = await search_bilibili(query=query)
        result["node_label"] = node.label
        return result

    raise HTTPException(400, f"不支持的资源来源: {source}")


async def _generate_search_query(question: dict, user_id: str) -> str:
    """
    根据题目内容智能生成 B站 搜索关键词。

    策略:
    1. 优先使用 LLM 从题目中提取核心知识点 + 搜索词
    2. 若 LLM 失败，退化为: 认知节点标签 + 题干前30字
    3. 若都失败，使用题干前30字
    """
    stem = question.get("stem", "") or ""
    node_ids = question.get("cognitive_node_ids") or []

    # 收集认知节点标签作为上下文
    node_labels = []
    if node_ids:
        from app.domain.cognitive import get_repo
        for nid in node_ids[:3]:
            try:
                node = get_repo().get_node(nid, user_id)
                if node and node.label:
                    node_labels.append(node.label)
            except Exception:
                pass

    # 方案 A: 用 LLM 生成搜索词
    try:
        from app.infrastructure.llm.llm_service import llm_service

        context_parts = []
        if node_labels:
            context_parts.append(f"知识点标签: {'、'.join(node_labels)}")
        context_parts.append(f"题目: {stem[:300]}")

        prompt = (
            "你是一个教育搜索引擎优化专家。请根据以下题目内容，生成一段适合在B站搜索教学视频的搜索关键词。\n"
            "要求:\n"
            "- 提取题目考查的核心知识点/概念（2-4个）\n"
            "- 用空格连接关键词，末尾加上' 讲解'\n"
            "- 只需要输出搜索词本身，不要任何解释\n"
            "- 示例输出: '二次函数 利润最值 商品销售 讲解'\n"
            "- 示例输出: '现在完成时 被动语态 讲解'\n"
            "- 示例输出: '牛顿第二定律 受力分析 讲解'\n\n"
            f"{chr(10).join(context_parts)}"
        )

        result = await llm_service.generate(
            messages=[
                {"role": "system", "content": "你是一个教育搜索关键词生成专家。只输出搜索词，不要任何额外内容。"},
                {"role": "user", "content": prompt},
            ],
            task_type="chat",
            temperature=0.1,
            max_tokens=100,
        )
        query = result.strip().strip('"').strip("'")
        if query and len(query) > 4:
            logger.info("LLM 生成搜索词: %s", query)
            return query
    except Exception as e:
        logger.warning("LLM 生成搜索词失败: %s", e)

    # 方案 B: 认知节点标签 + 题干
    import re
    # 去掉题干中的特殊符号、数字过多片段，提取有意义的文本
    clean_stem = re.sub(r'[*_#`~\[\]()（）【】《》、，。！？；：""''\n\r]', ' ', stem)
    # 去掉纯数字和单位等噪音
    clean_stem = re.sub(r'\d+[件元页个只条块]?', '', clean_stem)
    meaningful = clean_stem.strip()[:40]

    if node_labels:
        query = f"{' '.join(node_labels)} {meaningful} 讲解"
    else:
        query = f"{meaningful} 讲解"

    return query.strip()


@router.get("/for-question")
async def api_references_for_question(
    question_id: str = Query("", description="题目ID"),
    source: str = Query("bilibili"),
    user_id: str = Depends(current_user_id),
):
    """根据题目搜索参考资料（使用 AI 提取核心知识点作为搜索词）"""
    if not question_id:
        raise HTTPException(400, "question_id 不能为空")

    from app.infrastructure.db.database import get_db
    db = get_db()
    question = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not question:
        raise HTTPException(404, "题目不存在")

    query = await _generate_search_query(question, user_id)

    if source == "bilibili":
        result = await search_bilibili(query=query)
        result["search_query"] = query
        return result

    raise HTTPException(400, f"不支持的资源来源: {source}")
