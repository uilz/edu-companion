"""资料系统领域服务 — 接入 real material pipeline

对接 app/services/material_* 的真正实现，
提供统一的资料管理入口。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("materials")


class MaterialServiceImpl:
    """资料管理领域服务 — 委托到 real material services"""

    def __init__(self, event_bus):
        self._bus = event_bus

    # ── 搜索 ──

    async def search(self, user_id: str, query: str, top_k: int = 10) -> list[dict]:
        """语义搜索已索引的资料内容

        Returns:
            [{text, heading_path, material_id, material_name, chunk_index, score}]
        """
        if not query.strip():
            return []

        try:
            from app.services.materials.material_search import material_search
            results = await material_search.search(
                user_id=user_id,
                query=query,
                top_k=top_k,
            )
            logger.info("Material search: user=%s q=%s results=%d", user_id, query[:50], len(results))
            return results
        except Exception as e:
            logger.error("Material search failed: user=%s q=%s error=%s", user_id, query[:50], e)
            return []

    # ── 出题 ──

    async def generate_questions(
        self, user_id: str, material_id: str, count: int = 5
    ) -> list[dict]:
        """基于资料分块，用 LLM 生成练习题

        Returns:
            [{type, question, options, answer, explanation, material_id}]
        """
        try:
            from app.db.database import get_db
            from app.services.llm.llm_service import llm_service

            db = get_db()
            rows = db.fetchall(
                "SELECT text FROM material_chunks WHERE material_id = %s AND user_id = %s LIMIT 5",
                (material_id, user_id),
            )

            if not rows:
                logger.warning("Material generate_q: no chunks for %s", material_id)
                return []

            context = "\n\n".join(r["text"][:1000] for r in rows)

            prompt = (
                f"基于以下资料内容，生成{count}道练习题。\n"
                f"要求：题型覆盖选择题和简答题，包含答案和解析。\n\n"
                f"资料内容：\n{context[:3000]}\n\n"
                f"请以JSON格式输出：\n"
                f'[{{"type":"choice|short","question":"...","options":["A.","B.","C.","D."],"answer":"...","explanation":"..."}}]'
            )

            response = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一个出题助手。严格按照JSON格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                task_type="chat",
                temperature=0.5,
                max_tokens=4096,
            )

            import re
            try:
                json_str = re.search(r'\[.*\]', response, re.DOTALL)
                questions = json.loads(json_str.group()) if json_str else json.loads(response)
            except (json.JSONDecodeError, Exception):
                questions = [{"question": response[:500], "type": "short", "answer": "", "explanation": ""}]

            # 标记来源
            for q in questions:
                q["material_id"] = material_id

            logger.info(
                "Material generate_q: material=%s count=%d generated=%d",
                material_id, count, len(questions),
            )
            return questions

        except Exception as e:
            logger.error("Material generate_q failed: material=%s error=%s", material_id, e)
            return []

    # ── 事件：索引完成 → AI 辅助 ──

    async def on_indexed(self, event) -> None:
        """事件: 索引完成 → 自动提取知识点标签 + 生成摘要

        从分块文本中：
        1. 提取核心知识点/技能标签
        2. 生成简短内容摘要
        3. 写回 materials 表 (skills_covered_json / summary)
        """
        user_id = getattr(event, "user_id", "?")
        material_id = getattr(event, "material_id", "?")
        chunk_count = getattr(event, "chunk_count", 0)

        logger.info(
            "Material: indexed user=%s material=%s chunks=%d",
            user_id, material_id, chunk_count,
        )

        if chunk_count == 0:
            logger.warning("Material: 0 chunks for %s, skipping post-processing", material_id)
            return

        try:
            # 1. 取前几个分块用于分析
            from app.db.database import get_db
            db = get_db()

            chunks = db.fetchall(
                "SELECT text FROM material_chunks WHERE material_id = %s ORDER BY chunk_index ASC LIMIT 3",
                (material_id,),
            )
            if not chunks:
                return

            sample_text = "\n\n".join(c["text"][:500] for c in chunks)

            # 2. 用 LLM 提取知识点标签 + 摘要
            from app.services.llm.llm_service import llm_service
            prompt = (
                "分析以下资料内容，提取：\n"
                "1. 涉及的知识点/技能标签（3-8个，纯名词短语）\n"
                "2. 100字以内的内容摘要\n\n"
                f"资料内容：\n{sample_text[:2000]}\n\n"
                "请以JSON格式输出：\n"
                '{"skills": ["标签1", "标签2", ...], "summary": "摘要..."}'
            )

            response = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是学习资料分析助手。严格输出JSON。"},
                    {"role": "user", "content": prompt},
                ],
                task_type="chat",
                temperature=0.3,
                max_tokens=1024,
            )

            # 3. 解析并写回
            import re
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

            # 4. 发布事件（可选：触发后续推荐）
            try:
                from shared.events import MaterialIndexed
                enriched_event = MaterialIndexed(
                    user_id=user_id,
                    material_id=material_id,
                    chunk_count=chunk_count,
                    skills=skills,
                    summary=summary,
                )
                self._bus.emit(enriched_event)
            except (ImportError, Exception):
                pass  # 事件类型可能未定义，容错

            logger.info(
                "📝 Material post-processed: %s skills=%d summary=%s",
                material_id, len(skills), summary[:50],
            )

        except Exception as e:
            logger.error("Material post-processing failed: %s — %s", material_id, e)
