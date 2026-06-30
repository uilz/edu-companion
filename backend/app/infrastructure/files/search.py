"""
资料语义搜索服务 — pgvector 向量搜索

关键设计：
- 使用 pgvector <-> 操作符计算余弦距离
- embedding_vec vector(384) 列存储
- 余弦距离 < HIT_THRESHOLD 才注入 RAG
- 单层搜索：heading_path 拍平到 chunk
- search_sync() 与 search() 共享同一内核，行为一致
"""
from __future__ import annotations

import logging

from .embedding import compute_embedding

logger = logging.getLogger(__name__)

# 命中阈值：余弦距离 < 0.35 才注入 RAG
HIT_THRESHOLD = 0.35


class MaterialSearch:
    """资料语义搜索 — 真向量余弦相似度"""

    # ── 公开 API ──────────────────────────────────────────────

    async def search(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        material_ids: list[str] | None = None,
        node_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        语义搜索用户资料（异步接口）。

        返回:
            [{"text", "heading_path", "material_id", "material_name",
              "chunk_index", "score"}, ...]
            score 是余弦距离 [0, 2]，越小越相关
        """
        results = self._search(user_id, query, purpose, material_ids, node_ids, top_k)
        if results is None:
            logger.warning("向量搜索失败，回退全文搜索")
            results = self._fallback_text_search(user_id, query, purpose, material_ids, node_ids, top_k)
        else:
            logger.info("向量搜索: q=%s results=%d top_score=%.4f",
                         query[:50], len(results),
                         results[0]["score"] if results else 1.0)
        return results

    def search_sync(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        node_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        同步版搜索（供非 async 上下文调用，如 context_builder）。

        与 search() 共享同一内核：向量搜索 → 全文回退，行为一致。
        返回字段完全对齐 search()，含 heading_path。
        """
        results = self._search(user_id, query, purpose, None, node_ids, top_k)
        if results is None:
            logger.debug("同步向量搜索失败，回退全文搜索")
            results = self._fallback_text_search(user_id, query, purpose, None, node_ids, top_k)
        return results

    async def search_knowledge(
        self,
        user_id: str,
        query: str,
        node_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """知识库搜索（仅 library 文件）"""
        return await self.search(user_id, query, purpose="library", node_ids=node_ids, top_k=top_k)

    # ── RAG 辅助 ────────────────────────────────────────────────

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

    # ── 共享内核 ────────────────────────────────────────────────

    def _search(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        material_ids: list[str] | None = None,
        node_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict] | None:
        """
        向量搜索内核（同步，search/search_sync 共享）。

        返回搜索结果列表，或 None 表示需要回退。
        """
        query_vec = compute_embedding(query[:2000])
        if not query_vec:
            return None

        try:
            from app.infrastructure.db.database import get_db
            db = get_db()

            conditions = ["mc.user_id = %s", "mc.embedding_vec IS NOT NULL"]
            params: list = [user_id]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)
            if material_ids:
                conditions.append("mc.material_id = ANY(%s)")
                params.append(material_ids)
            if node_ids:
                conditions.append("m.skills_covered_json ?| %s::text[]")
                params.append(node_ids)
            conditions.append("m.status = 'indexed'")

            query_vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

            sql = f"""
                SELECT mc.text, mc.chunk_index, mc.material_id,
                       m.file_name as material_name,
                       mc.heading_path,
                       mc.embedding_vec <-> %s::vector AS score
                FROM material_chunks mc
                JOIN materials m ON mc.material_id = m.material_id
                WHERE {' AND '.join(conditions)}
                ORDER BY score ASC
                LIMIT %s
            """
            params = [query_vec_str] + params + [top_k]

            rows = db.fetchall(sql, tuple(params))
            results = []
            for r in rows:
                results.append({
                    "text": r["text"][:2000] if r.get("text") else "",
                    "heading_path": r.get("heading_path") or "",
                    "material_id": r["material_id"],
                    "material_name": r.get("material_name", ""),
                    "chunk_index": r.get("chunk_index", 0),
                    "score": float(r.get("score", 1.0)),
                })
            return results

        except Exception as e:
            logger.debug("向量搜索内核失败: %s", e)
            return None

    # ── 回退方案 ────────────────────────────────────────────────

    def _fallback_text_search(
        self,
        user_id: str,
        query: str,
        purpose: str | None = None,
        material_ids: list[str] | None = None,
        node_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """全文搜索回退方案"""
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()

            conditions = ["mc.user_id = %s", "m.status = 'indexed'"]
            params: list = [user_id]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)
            if material_ids:
                conditions.append("mc.material_id = ANY(%s)")
                params.append(material_ids)
            if node_ids:
                conditions.append("m.skills_covered_json ?| %s::text[]")
                params.append(node_ids)

            sql = f"""
                SELECT mc.text, mc.chunk_index, mc.material_id,
                       m.file_name as material_name,
                       mc.heading_path,
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
                    "heading_path": r.get("heading_path") or "",
                    "material_id": r["material_id"],
                    "material_name": r.get("material_name", ""),
                    "chunk_index": r.get("chunk_index", 0),
                    "score": 1.0,
                })
            return results
        except Exception as e:
            logger.debug("全文搜索回退也失败: %s", e)
            return []


# 全局实例
material_search = MaterialSearch()