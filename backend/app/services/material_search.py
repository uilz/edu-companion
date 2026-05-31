"""
资料语义搜索服务
基于 pgvector 的向量搜索 + 全文搜索混合
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.material_common import get_pool, compute_embedding

logger = logging.getLogger(__name__)


class MaterialSearch:
    """
    用户资料的语义搜索
    
    两层搜索：
    1. 向量搜索（pgvector cosine distance）— 语义匹配
    2. 全文搜索（PostgreSQL tsvector）— 精确匹配
    
    混合排序：向量分 × 0.7 + 文本分 × 0.3
    """

    async def search(
        self,
        user_id: str,
        query: str,
        material_ids: Optional[list[str]] = None,
        skill_id: Optional[str] = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        语义搜索用户资料
        
        参数:
            user_id: 用户ID
            query: 搜索查询
            material_ids: 限定资料范围（可选）
            skill_id: 限定知识点（可选）
            top_k: 返回数量
        
        返回:
            list of SearchResult dicts
        """
        # 计算查询向量
        query_embedding = None
        try:
            query_embedding = compute_embedding(query[:2000])
        except Exception:
            logger.debug("Embedding 计算失败，降级使用全文搜索", exc_info=True)

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                if query_embedding:
                    return await self._vector_search(
                        conn, user_id, query_embedding, query,
                        material_ids, skill_id, top_k,
                    )
                else:
                    return await self._text_search(
                        conn, user_id, query,
                        material_ids, skill_id, top_k,
                    )
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    async def _vector_search(
        self, conn, user_id: str, embedding: list[float], query: str,
        material_ids: Optional[list[str]], skill_id: Optional[str],
        top_k: int,
    ) -> list[dict]:
        """向量搜索（主搜索方式）"""
        emb_str = str(embedding)

        conditions = ["c.user_id = $1", "c.embedding IS NOT NULL"]
        params: list = [user_id]

        if material_ids:
            conditions.append(f"c.material_id = ANY(${len(params)+1})")
            params.append(material_ids)
        if skill_id:
            conditions.append(f"${len(params)+1} = ANY(c.skill_ids)")
            params.append(skill_id)

        where_clause = " AND ".join(conditions)

        # 向量相似度 + 文本相关性 混合排序
        rows = await conn.fetch(
            f"""SELECT 
                c.chunk_id,
                c.text,
                c.chunk_type,
                c.skill_ids,
                c.source_file,
                c.page_number,
                c.material_id,
                1 - (c.embedding <=> ${len(params)+1}::vector) AS similarity
            FROM material_chunks c
            WHERE {where_clause}
            ORDER BY similarity DESC
            LIMIT ${len(params)+2}""",
            *params, emb_str, top_k,
        )

        return [
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"][:500],
                "chunk_type": row["chunk_type"],
                "skill_ids": row["skill_ids"],
                "source_file": row["source_file"],
                "page_number": row["page_number"],
                "material_id": row["material_id"],
                "similarity": round(row["similarity"], 4),
            }
            for row in rows
        ]

    async def _text_search(
        self, conn, user_id: str, query: str,
        material_ids: Optional[list[str]], skill_id: Optional[str],
        top_k: int,
    ) -> list[dict]:
        """全文搜索（降级方案，无embedding时使用）"""
        conditions = [
            "c.user_id = $1",
            "to_tsvector('simple', c.text) @@ plainto_tsquery('simple', $2)",
        ]
        params: list = [user_id, query]

        if material_ids:
            conditions.append(f"c.material_id = ANY(${len(params)+1})")
            params.append(material_ids)
        if skill_id:
            conditions.append(f"${len(params)+1} = ANY(c.skill_ids)")
            params.append(skill_id)

        where_clause = " AND ".join(conditions)

        rows = await conn.fetch(
            f"""SELECT 
                c.chunk_id, c.text, c.chunk_type, c.skill_ids,
                c.source_file, c.page_number, c.material_id,
                ts_rank(to_tsvector('simple', c.text), 
                        plainto_tsquery('simple', $2)) AS rank
            FROM material_chunks c
            WHERE {where_clause}
            ORDER BY rank DESC
            LIMIT ${len(params)+1}""",
            *params, top_k,
        )

        return [
            {
                "chunk_id": row["chunk_id"],
                "text": row["text"][:500],
                "chunk_type": row["chunk_type"],
                "skill_ids": row["skill_ids"],
                "source_file": row["source_file"],
                "page_number": row["page_number"],
                "material_id": row["material_id"],
                "similarity": round(row["rank"], 4),
            }
            for row in rows
        ]

    async def search_by_skill(
        self, user_id: str, skill_id: str, top_k: int = 5,
    ) -> list[dict]:
        """按知识点搜索资料片段（用于练习错误时关联资料）"""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT chunk_id, text, source_file, page_number, material_id
                       FROM material_chunks
                       WHERE user_id = $1 AND $2 = ANY(skill_ids)
                       ORDER BY chunk_index
                       LIMIT $3""",
                    user_id, skill_id, top_k,
                )

                return [
                    {
                        "chunk_id": row["chunk_id"],
                        "text": row["text"][:300],
                        "source_file": row["source_file"],
                        "page_number": row["page_number"],
                        "material_id": row["material_id"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"知识点搜索失败: {e}")
            return []


# 全局实例
material_search = MaterialSearch()
