"""参考资料服务

根据题目或知识点生成搜索关键词并检索外部资源（B站等）。
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def get_question_for_reference(question_id: str) -> dict | None:
    """获取用于参考资料搜索的题目（不校验用户归属）。"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    return db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )


async def generate_search_query_for_question(question: dict, user_id: str) -> str:
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
