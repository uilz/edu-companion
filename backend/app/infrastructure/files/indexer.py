"""
资料索引服务 — 智能分块流水线

流程: MarkItDown 解析 → 智能分块 → Embedding → 存入 PostgreSQL → LLM 后处理

关键设计:
- 始终尝试结构化分块（不限于大文件）
- 多策略标题检测（`#` 标题 + 粗体编号标题 + 纯编号标题）
- 表格内嵌标题探测（MarkItDown docx 表格行合并场景）
- 语义回退（复用已有 embedding 模型）
- 大文件 + library → 写入 TOC 表
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

from .parser import material_parser
from .chunker import extract_toc, assign_chunk_ranges, chunk_by_toc

logger = logging.getLogger(__name__)


class MaterialIndexer:
    """资料索引流水线 v3"""

    # 大文件阈值（仅控制是否写入 TOC 表）
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
            logger.warning("解析结果为空: %s — %s", file_name, file_type)
            # 图片/音频等媒体文件无文字内容属于正常情况，标记为 indexed 而非 failed
            if file_type in ("image", "audio", "video"):
                _update_material_status(material_id, "indexed")
                return {"material_id": material_id, "status": "indexed", "chunk_count": 0, "toc_count": 0}
            _update_material_status(material_id, "index_failed")
            return {"material_id": material_id, "status": "parse_failed", "chunk_count": 0, "toc_count": 0}

        # Step 2: 智能分块 — 始终尝试结构化检测
        # 先用 extract_toc 检测标题（支持 `#` + 粗体编号 + 纯编号）
        toc_nodes = extract_toc(markdown_text)
        has_heading_structure = bool(toc_nodes)

        # 判定是否写入 TOC 表（大文件 + library 或有标题结构）
        is_large = (file_size > self.LARGE_FILE_BYTES or
                    material_parser.get_page_count(file_path) > self.LARGE_FILE_PAGES)
        build_toc = (is_large and purpose == "library") or has_heading_structure

        # Step 3: 分块（传入 embedding_fn 启用语义回退）
        chunks = chunk_by_toc(
            markdown_text, toc_nodes,
            max_chunk_size=1000,
            embedding_fn=self._compute_embedding if not has_heading_structure else None,
        )

        if has_heading_structure and chunks:
            toc_nodes = assign_chunk_ranges(toc_nodes, chunks)

        logger.info(
            "索引 %s: %s → %d 分块, %d 标题, %s",
            file_name,
            "TOC" if has_heading_structure else "平铺",
            len(chunks), len(toc_nodes),
            f"TOC写入={build_toc}" if build_toc else "无TOC",
        )

        if not chunks:
            return {"material_id": material_id, "status": "no_content", "chunk_count": 0, "toc_count": 0}

        # Step 4: 写入 DB（单事务包裹，防局部失败）
        from app.infrastructure.db.database import get_db
        db = get_db()

        ops: list[tuple[str, tuple]] = []

        # 4a. 删除旧索引
        if build_toc:
            ops.append(("DELETE FROM material_toc WHERE material_id = %s", (material_id,)))
        ops.append(("DELETE FROM material_chunks WHERE material_id = %s", (material_id,)))

        # 4b. 写入 chunks（含 embedding）
        for ch in chunks:
            chunk_id = f"chk_{material_id}_{ch['index']}"
            heading_path = ch.get("heading_path", "")
            # 计算 embedding: heading + chunk 文本前 2000 字符
            embed_text = f"{heading_path}\n{ch['text']}"[:2000]
            embedding = self._compute_embedding(embed_text)
            # 转为 vector 字符串格式 [x,y,...] 供 pgvector 使用
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]" if embedding else None

            ops.append((
                """INSERT INTO material_chunks
                   (chunk_id, user_id, material_id, text, chunk_type, chunk_index,
                    source_file, heading_path, indexing_status, embedding_vec, created_at)
                   VALUES (%s, %s, %s, %s, 'text', %s, %s, %s, 'indexed', %s::vector, NOW())""",
                (chunk_id, user_id, material_id, ch["text"], ch["index"],
                 file_name, heading_path, embedding_str),
            ))

        # 4c. 写入 TOC
        toc_count = 0
        if build_toc and has_heading_structure:
            # 预计算所有 toc_id（用 id(tn) 做 key，TOCNode 为 dataclass 不可哈希）
            toc_ids: dict[int, str] = {}
            for tn in toc_nodes:
                tid = _toc_id(material_id, tn.level, tn.heading)
                toc_ids[id(tn)] = tid

            for tn in toc_nodes:
                pid = toc_ids.get(id(tn.parent)) if tn.parent else None
                ops.append((
                    """INSERT INTO material_toc
                       (toc_id, material_id, parent_toc_id, level, heading,
                        chunk_start, chunk_end, heading_line_index, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                    (toc_ids[id(tn)], material_id, pid,
                     tn.level, tn.heading,
                     tn.chunk_start, tn.chunk_end,
                     tn.heading_line_index),
                ))
                toc_count += 1

        # 4d. 更新 materials 表
        ops.append((
            "UPDATE materials SET chunk_count = %s, status = 'indexed', indexed_at = NOW() WHERE material_id = %s",
            (len(chunks), material_id),
        ))

        # 单事务提交
        try:
            db.execute_batch(ops)
        except Exception as e:
            logger.error("索引 DB 写入失败（事务回滚）: %s — %s", file_name, e)
            _update_material_status(material_id, "index_failed")
            return {"material_id": material_id, "status": "index_failed", "chunk_count": 0, "toc_count": 0}

        # Step 5: 后处理 — LLM 提取 skills + summary
        asyncio.ensure_future(self._post_process(user_id, material_id, len(chunks)))

        logger.info("索引完成: %s → chunk=%d, toc=%d",
                     file_name, len(chunks), toc_count)
        return {
            "material_id": material_id,
            "status": "indexed",
            "chunk_count": len(chunks),
            "toc_count": toc_count,
        }

    def _compute_embedding(self, text: str) -> list[float] | None:
        """计算 embedding，失败时返回 None"""
        try:
            from .embedding import compute_embedding
            return compute_embedding(text[:2000])
        except Exception as e:
            logger.debug("Embedding 计算失败: %s", e)
            return None

    async def _post_process(self, user_id: str, material_id: str, chunk_count: int) -> None:
        """索引后处理 — LLM 提取 skills + summary（内联到 indexer）"""
        if chunk_count == 0:
            return
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            chunks = db.fetchall(
                "SELECT text FROM material_chunks WHERE material_id = %s ORDER BY chunk_index ASC LIMIT 3",
                (material_id,),
            )
            if not chunks:
                return

            sample_text = "\n\n".join(c["text"][:500] for c in chunks)
            from app.infrastructure.llm.llm_service import llm_service

            prompt = (
                "分析以下资料内容，提取：\n"
                "1. 涉及的知识点/技能标签（3-8个，纯名词短语）\n"
                "2. 100字以内的内容摘要\n\n"
                f"资料内容：\n{sample_text[:2000]}\n\n"
                '请以JSON格式输出：\n'
                '{"skills": ["标签1", "标签2", ...], "summary": "摘要..."}'
            )

            response = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是学习资料分析助手。严格输出JSON。"},
                    {"role": "user", "content": prompt},
                ],
                task_type="chat", temperature=0.3, max_tokens=1024,
            )

            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                data = json.loads(json_match.group()) if json_match else json.loads(response)
            except (json.JSONDecodeError, Exception):
                data = {"skills": [], "summary": response[:100]}

            skills = data.get("skills", [])
            summary = data.get("summary", "")[:200]
            db.execute(
                "UPDATE materials SET skills_covered_json = %s, summary = %s WHERE material_id = %s",
                (json.dumps(skills, ensure_ascii=False), summary, material_id),
            )
            logger.info("后处理完成: %s skills=%d", material_id, len(skills))
        except Exception as e:
            logger.warning("后处理跳过（可重试）: %s — %s", material_id, e)


def _toc_id(material_id: str, level: int, heading: str) -> str:
    """用 hash 生成唯一 toc_id，防冲突"""
    raw = f"{material_id}_{level}_{heading}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"toc_{h}"


def _update_material_status(material_id: str, status: str) -> None:
    """更新 materials 表状态"""
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        db.execute(
            "UPDATE materials SET status = %s WHERE material_id = %s",
            (status, material_id),
        )
    except Exception as e:
        logger.debug("更新 material 状态失败: %s", e)


# 全局实例
material_indexer = MaterialIndexer()