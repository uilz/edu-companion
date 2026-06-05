"""
资料语义搜索服务 v3 — 真向量搜索 (DOUBLE PRECISION[])

关键设计：
- 使用 PostgreSQL 数组运算计算余弦相似度
- embedding 列 DOUBLE PRECISION[] 存储 384 维向量
- 余弦距离 < HIT_THRESHOLD 才命中
- 单层搜索：heading_path 拍平到 chunk
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 命中阈值：余弦距离 < 0.35 才注入 RAG
HIT_THRESHOLD = 0.35
# 向量维度
EMBEDDING_DIM = 384


class MaterialSearch:
    """资料语义搜索 — 真向量余弦相似度"""

    async def search(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        material_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        语义搜索用户资料。

        返回:
            [{"text", "heading_path", "material_id", "material_name",
              "chunk_index", "score"}, ...]
            score 是余弦距离 [0, 2]，越小越相关
        """
        query_vec = self._compute_embedding(query[:2000])
        if not query_vec:
            logger.warning("查询向量计算失败，回退全文搜索")
            return self._fallback_text_search(user_id, query, purpose, material_ids, top_k)

        try:
            from app.db.database import get_db
            db = get_db()

            conditions = ["mc.user_id = %s", "mc.embedding IS NOT NULL", "array_length(mc.embedding, 1) = %s"]
            params: list = [user_id, EMBEDDING_DIM]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)
            if material_ids:
                conditions.append(f"mc.material_id = ANY(%s)")
                params.append(material_ids)
            conditions.append("m.status = 'indexed'")

            # 向量搜索：手工计算余弦距离
            # cos_dist = 1 - (dot(A,B) / (||A|| * ||B||))
            # 用 PostgreSQL 数组运算
            vec_placeholder = "{" + ",".join(str(v) for v in query_vec) + "}"

            sql = f"""
                WITH qvec AS (
                    SELECT %s::double precision[] AS v
                )
                SELECT mc.text, mc.chunk_index, mc.material_id,
                       m.file_name as material_name,
                       1.0 - (
                            (SELECT sum(a*b) FROM unnest(mc.embedding, (SELECT v FROM qvec)) AS t(a,b))
                            / NULLIF(
                                sqrt((SELECT sum(a*a) FROM unnest(mc.embedding) AS t(a))) *
                                sqrt((SELECT sum(b*b) FROM unnest((SELECT v FROM qvec)) AS t(b))),
                                0
                            )
                        ) AS score
                FROM material_chunks mc
                JOIN materials m ON mc.material_id = m.material_id
                WHERE {' AND '.join(conditions)}
                ORDER BY score ASC
                LIMIT %s
            """
            params = [vec_placeholder] + params + [top_k]

            rows = db.fetchall(sql, tuple(params))
            results = []
            for r in rows:
                results.append({
                    "text": r["text"][:2000] if r.get("text") else "",
                    "heading_path": "",
                    "material_id": r["material_id"],
                    "material_name": r.get("material_name", ""),
                    "chunk_index": r.get("chunk_index", 0),
                    "score": float(r.get("score", 1.0)),
                })

            logger.info("向量搜索: q=%s results=%d top_score=%.4f",
                         query[:50], len(results),
                         results[0]["score"] if results else 1.0)
            return results

        except Exception as e:
            logger.error("向量搜索失败: %s，回退全文搜索", e)
            return self._fallback_text_search(user_id, query, purpose, material_ids, top_k)

    def _fallback_text_search(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        material_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """全文搜索回退方案"""
        try:
            from app.db.database import get_db
            db = get_db()

            conditions = ["mc.user_id = %s", "m.status = 'indexed'"]
            params: list = [user_id]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)
            if material_ids:
                conditions.append(f"mc.material_id = ANY(%s)")
                params.append(material_ids)

            sql = f"""
                SELECT mc.text, mc.chunk_index, mc.material_id,
                       m.file_name as material_name,
                       1.0 as score
                FROM material_chunks mc
                JOIN materials m ON mc.material_id = m.material_id
                WHERE {' AND '.join(conditions)}
                  AND to_tsvector('simple', coalesce(mc.text, '')) @@ plainto_tsquery('simple', %s)
                LIMIT %s
            """
            params.append(query[:500])
            params.append(top_k)

            rows = db.fetchall(sql, tuple(params))
            results = []
            for r in rows:
                results.append({
                    "text": r["text"][:2000] if r.get("text") else "",
                    "heading_path": "",
                    "material_id": r["material_id"],
                    "material_name": r.get("material_name", ""),
                    "chunk_index": r.get("chunk_index", 0),
                    "score": 1.0,  # 全文搜索无准确分数
                })
            return results
        except Exception as e:
            logger.debug("全文搜索回退也失败: %s", e)
            return []

    async def search_knowledge(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """知识库搜索（仅 library 文件）"""
        return await self.search(user_id, query, purpose="library", top_k=top_k)

    def should_inject_rag(self, results: list[dict]) -> bool:
        """判断是否应该注入 RAG

        条件：有结果 且 最佳匹配的余弦距离 < 阈值
        全文搜索回退结果 score=1.0 → 不注入（避免强行引用）
        """
        if not results:
            return False
        best_score = results[0].get("score", 1.0)
        return best_score < HIT_THRESHOLD

    def format_rag_context(self, results: list[dict]) -> str:
        """将搜索结果格式化为 RAG 上下文"""
        if not results:
            return ""

        parts = []
        for r in results[:5]:
            material = r.get("material_name", "未知资料")
            heading = r.get("heading_path", "")
            text = r.get("text", "")
            header = f"--- 资料：{material}"
            if heading:
                header += f" [{heading}]"
            parts.append(f"{header}\n{text}")

        return "\n\n".join(parts)

    def _compute_embedding(self, text: str) -> list[float] | None:
        try:
            from app.services.materials.material_common import compute_embedding
            return compute_embedding(text[:2000])
        except Exception:
            return None

    def search_sync(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """同步版搜索（供非 async 上下文调用，如 context_builder）

        使用向量搜索，有 embedding 列时走余弦相似度。
        """
        query_vec = self._compute_embedding(query[:2000])
        if not query_vec:
            return []

        try:
            from app.db.database import get_db
            db = get_db()

            conditions = [
                "mc.user_id = %s", "m.status = 'indexed'",
                "mc.embedding IS NOT NULL", f"array_length(mc.embedding, 1) = %s"
            ]
            params: list = [user_id, EMBEDDING_DIM]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)

            vec_placeholder = "{" + ",".join(str(v) for v in query_vec) + "}"

            sql = f"""
                WITH qvec AS (
                    SELECT %s::double precision[] AS v
                )
                SELECT mc.text, mc.material_id, m.file_name as material_name,
                       mc.chunk_index,
                       1.0 - (
                            (SELECT sum(a*b) FROM unnest(mc.embedding, (SELECT v FROM qvec)) AS t(a,b))
                            / NULLIF(
                                sqrt((SELECT sum(a*a) FROM unnest(mc.embedding) AS t(a))) *
                                sqrt((SELECT sum(b*b) FROM unnest((SELECT v FROM qvec)) AS t(b))),
                                0
                            )
                        ) AS score
                FROM material_chunks mc
                JOIN materials m ON mc.material_id = m.material_id
                WHERE {' AND '.join(conditions)}
                ORDER BY score ASC
                LIMIT %s
            """
            params = [vec_placeholder] + params + [top_k]

            rows = db.fetchall(sql, tuple(params))
            results = []
            for r in rows:
                results.append({
                    "text": r["text"][:2000] if r.get("text") else "",
                    "heading_path": "",
                    "material_id": r["material_id"],
                    "material_name": r.get("material_name", ""),
                    "chunk_index": r.get("chunk_index", 0),
                    "score": float(r.get("score", 1.0)),
                })
            return results
        except Exception as e:
            logger.debug("同步向量搜索失败: %s", e)
            return []


# 全局实例
material_search = MaterialSearch()
