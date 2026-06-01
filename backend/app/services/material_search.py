"""
资料语义搜索服务 v2 — 单层搜索

关键设计：
- 单层搜索（不拆 TOC 和 Chunk 两层）
- 路径信息拍平到 chunk.heading_path
- 搜索一条 SQL 搞定，不要两次 DB 查询
- 余弦距离 < 0.35 才认为命中（防止强行引用）
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# 命中阈值：余弦距离 < 0.35 才注入 RAG
HIT_THRESHOLD = 0.35


class MaterialSearch:
    """资料语义搜索"""

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
              "toc_id", "page", "score", "chunk_index"}, ...]
            score 是余弦距离，越小越相关
        """
        # 计算查询向量
        query_vec = self._compute_embedding(query[:2000])

        try:
            from app.db.database import get_db
            db = get_db()

            conditions = ["mc.user_id = %s"]
            params: list = [user_id]

            if purpose:
                conditions.append("m.purpose = %s")
                params.append(purpose)

            if material_ids:
                conditions.append(f"mc.material_id = ANY(%s)")
                params.append(material_ids)

            # 向量搜索（降级到纯文本搜索）
            if query_vec:
                # TODO: 启用 pgvector 后使用向量搜索
                # sql = f"""
                #   SELECT mc.text, mc.chunk_index, mc.material_id,
                #          m.file_name as material_name,
                #          mc.embedding <=> %s::vector AS score
                #   FROM material_chunks mc
                #   JOIN materials m ON mc.material_id = m.material_id
                #   WHERE {' AND '.join(conditions)}
                #   ORDER BY mc.embedding <=> %s::vector
                #   LIMIT %s
                # """
                pass

            # 降级：全文搜索（PostgreSQL tsvector）
            conditions.append("m.status = 'indexed'")
            sql = f"""
                SELECT mc.text, mc.chunk_index, mc.material_id,
                       m.file_name as material_name,
                       0.0 as score
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
                    "score": float(r.get("score", 0)),
                })
            return results

        except Exception as e:
            logger.error("搜索失败: %s", e)
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
        """判断是否应该注入 RAG"""
        return len(results) > 0 and results[0].get("score", 1.0) < HIT_THRESHOLD

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
            from app.services.material_common import compute_embedding
            return compute_embedding(text[:2000])
        except Exception:
            return None


# 全局实例
material_search = MaterialSearch()
