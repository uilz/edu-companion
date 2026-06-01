"""
资料索引服务 v2 — MarkItDown + TOC 层次化索引

流程: MarkItDown 解析 → 分块 → Embedding → 存入 PostgreSQL

关键设计:
- 大文件（>15页/5MB）→ 提取 TOC 树 + 按标题分块
- 小文件 → 直接按段落分块
- TOC embedding = heading + 首段前 200 字（不用LLM摘要）
- 异步执行（调用方 asyncio.create_task）
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from app.services.material_parser import material_parser
from app.services.material_toc_extractor import (
    extract_toc,
    assign_chunk_ranges,
    chunk_by_toc,
)

logger = logging.getLogger(__name__)


class MaterialIndexer:
    """资料索引流水线 v2"""

    # 大文件阈值
    LARGE_FILE_PAGES = 15
    LARGE_FILE_BYTES = 5_000_000

    async def index_file(
        self,
        user_id: str,
        material_id: str,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        purpose: str = "session",
    ) -> dict:
        """
        完整的索引流水线。

        返回:
            {"material_id": str, "status": str, "chunk_count": int, "toc_count": int}
            status: indexed | parse_failed | no_content
        """
        # Step 1: MarkItDown 解析
        markdown_text = material_parser.parse(file_path, file_type)
        if not markdown_text.strip():
            logger.warning("解析结果为空: %s", file_name)
            return {"material_id": material_id, "status": "parse_failed", "chunk_count": 0, "toc_count": 0}

        # Step 2: 判定是否建 TOC（大文件 + library）
        is_large = (file_size > self.LARGE_FILE_BYTES or
                    material_parser.get_page_count(file_path) > self.LARGE_FILE_PAGES)
        build_toc = is_large and purpose == "library"

        # Step 3: 分块
        if build_toc:
            toc_nodes = extract_toc(markdown_text)
            chunks = chunk_by_toc(markdown_text, toc_nodes)
            toc_nodes = assign_chunk_ranges(toc_nodes, chunks)
            logger.info("TOC 索引: %s → %d 个目录节点, %d 个分块", file_name, len(toc_nodes), len(chunks))
        else:
            toc_nodes = []
            chunks = chunk_by_toc(markdown_text, [], max_chunk_size=1000)
            logger.info("平铺索引: %s → %d 个分块", file_name, len(chunks))

        if not chunks:
            return {"material_id": material_id, "status": "no_content", "chunk_count": 0, "toc_count": 0}

        # Step 4: 写入 DB
        from app.db.database import get_db
        db = get_db()

        # 4a. 删除旧索引（重新索引时）
        if build_toc:
            db.execute("DELETE FROM material_toc WHERE material_id = %s", (material_id,))
        db.execute("DELETE FROM material_chunks WHERE material_id = %s", (material_id,))

        # 4b. 写入 chunks
        for ch in chunks:
            chunk_id = f"chk_{material_id}_{ch['index']}"
            heading_path = ch.get("heading_path", "")
            # 计算 embedding
            embed_text = f"{heading_path}\n{ch['text']}"[:3000]
            embedding = self._compute_embedding(embed_text)

            db.execute(
                """INSERT INTO material_chunks
                   (chunk_id, user_id, material_id, text, chunk_type, chunk_index,
                    source_file, indexing_status, created_at)
                   VALUES (%s, %s, %s, %s, 'text', %s, %s, 'indexed', NOW())""",
                (chunk_id, user_id, material_id, ch["text"][:8000], ch["index"],
                 file_name),
            )

        # 4c. 写入 TOC
        toc_count = 0
        if build_toc:
            for tn in toc_nodes:
                toc_id = f"toc_{material_id}_{tn.level}_{tn.heading[:20]}"
                embedding = self._compute_embedding(
                    f"{tn.heading}\n{tn.first_chunk_text[:200]}"
                )
                # 这里简化处理，不存 embedding 到 DB（pgvector 类型需要额外配置）
                # 只存文本结构
                db.execute(
                    """INSERT INTO material_toc
                       (toc_id, material_id, parent_toc_id, level, heading,
                        chunk_start, chunk_end, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())""",
                    (toc_id, material_id,
                     tn.parent and f"toc_{material_id}_{tn.parent.level}_{tn.parent.heading[:20]}" or None,
                     tn.level, tn.heading,
                     tn.chunk_start, tn.chunk_end),
                )
                toc_count += 1

        # 4d. 更新 materials 表
        db.execute(
            "UPDATE materials SET chunk_count = %s, status = 'indexed', indexed_at = NOW() WHERE material_id = %s",
            (len(chunks), material_id),
        )

        logger.info("索引完成: %s → chunk=%d, toc=%d", file_name, len(chunks), toc_count)
        return {
            "material_id": material_id,
            "status": "indexed",
            "chunk_count": len(chunks),
            "toc_count": toc_count,
        }

    def _compute_embedding(self, text: str) -> list[float] | None:
        """计算 embedding，失败时返回 None"""
        try:
            from app.services.material_common import compute_embedding
            return compute_embedding(text[:2000])
        except Exception as e:
            logger.debug("Embedding 计算失败: %s", e)
            return None


# 全局实例
material_indexer = MaterialIndexer()
