"""
资料索引服务
分块 → Embedding → 存入 PostgreSQL pgvector
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.services.material_parser import material_parser
from app.services.material_common import get_pool, compute_embedding

logger = logging.getLogger(__name__)


class MaterialIndexer:
    """
    资料索引流水线
    
    流程: 解析 → 分块 → 知识点标注 → Embedding → 存储
    """

    async def index_file(
        self,
        user_id: str,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
    ) -> dict:
        """
        完整的索引流水线
        
        返回:
            {"material_id": str, "chunk_count": int, "status": str}
        """
        # Step 1: 解析文件
        raw_blocks = material_parser.parse(file_path, file_type)
        if not raw_blocks:
            return {"material_id": "", "chunk_count": 0, "status": "parse_failed"}

        # Step 2: 创建 Material 记录
        material_id = str(uuid.uuid4())
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO materials (material_id, user_id, file_name, file_type, 
                       file_size, storage_path, status, chunk_count)
                       VALUES ($1, $2, $3, $4, $5, $6, 'indexing', $7)""",
                    material_id, user_id, file_name, file_type,
                    file_size, file_path, len(raw_blocks),
                )

                # Step 3: 逐块索引
                for i, block in enumerate(raw_blocks):
                    await self._index_chunk(
                        conn, user_id, material_id, block,
                        chunk_index=i, source_file=file_name,
                    )

                # Step 4: 更新 material 状态
                await conn.execute(
                    """UPDATE materials 
                       SET status='ready', indexed_at=$1, chunk_count=$2
                       WHERE material_id=$3""",
                    datetime.now(), len(raw_blocks), material_id,
                )

        except Exception as e:
            logger.error(f"索引失败: {e}")
            return {"material_id": material_id, "chunk_count": 0, "status": "index_failed"}

        logger.info(
            "资料索引完成: %s → %d chunks, material_id=%s",
            file_name, len(raw_blocks), material_id,
        )
        return {
            "material_id": material_id,
            "chunk_count": len(raw_blocks),
            "status": "ready",
        }

    async def _index_chunk(
        self,
        conn,
        user_id: str,
        material_id: str,
        block: dict,
        chunk_index: int,
        source_file: str,
    ) -> None:
        """索引单个文本块：标注知识点 + Embedding + 存储"""

        text = block.get("text", "")
        if not text or len(text) < 10:
            return

        chunk_id = str(uuid.uuid4())
        page_num = block.get("page")
        chunk_type = self._classify_chunk_type(text)

        # 知识点标注（轻量级关键词匹配）
        skill_ids = self._detect_skills(text)

        # Embedding 向量化
        embedding = None
        try:
            emb_list = compute_embedding(text[:2000])  # 截断到 2000 字
            if emb_list:
                embedding = str(emb_list)  # pgvector 接受 list 格式的字符串
        except Exception as e:
            logger.warning(f"Embedding 失败: {e}")

        # 存储到 PostgreSQL
        if embedding:
            await conn.execute(
                """INSERT INTO material_chunks 
                   (chunk_id, user_id, material_id, text, chunk_type, skill_ids,
                    embedding, source_file, page_number, chunk_index, indexing_status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8, $9, $10, 'done')""",
                chunk_id, user_id, material_id, text[:10000], chunk_type,
                skill_ids, embedding, source_file, page_num, chunk_index,
            )
        else:
            # 无 embedding 时降级：只存文本，允许全文搜索
            await conn.execute(
                """INSERT INTO material_chunks
                   (chunk_id, user_id, material_id, text, chunk_type, skill_ids,
                    source_file, page_number, chunk_index, indexing_status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'done')""",
                chunk_id, user_id, material_id, text[:10000], chunk_type,
                skill_ids, source_file, page_num, chunk_index,
            )

    def _classify_chunk_type(self, text: str) -> str:
        """自动分类 chunk 类型"""
        text_lower = text.lower()

        # 题目检测
        question_markers = ["题目", "习题", "练习", "question", "q:", "求", "解", "证明", "计算"]
        solution_markers = ["解答", "解:", "答:", "答案", "解析", "solution", "answer"]

        question_score = sum(1 for m in question_markers if m in text_lower)
        solution_score = sum(1 for m in solution_markers if m in text_lower)

        if question_score >= 2 and solution_score == 0:
            return "question"
        elif solution_score >= 2:
            return "solution"
        elif any(kw in text_lower for kw in ["公式", "formula", "$"]):
            return "formula"
        elif any(kw in text_lower for kw in ["图", "figure", "table", "表", "图表"]):
            return "diagram"
        else:
            return "text"

    def _detect_skills(self, text: str) -> list[str]:
        """轻量级知识点检测（关键词匹配）"""
        text_lower = text.lower()
        skills = []

        SKILL_KEYWORDS = {
            "calculus_limit": ["极限", "limit"],
            "calculus_derivative": ["导数", "derivative", "求导", "斜率", "切线"],
            "calculus_integral": ["积分", "integral", "不定积分", "定积分"],
            "calculus_differential": ["微分", "differential"],
            "linear_matrix": ["矩阵", "matrix"],
            "linear_determinant": ["行列式", "determinant"],
            "linear_eigenvalue": ["特征值", "特征向量", "eigen"],
            "physics_mechanics": ["力学", "牛顿", "运动", "力"],
            "physics_electromagnetism": ["电磁", "电场", "磁场", "电流"],
        }

        for skill_id, keywords in SKILL_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower and skill_id not in skills:
                    skills.append(skill_id)
                    break

        return skills[:5]  # 最多5个知识点


# 全局实例
material_indexer = MaterialIndexer()
