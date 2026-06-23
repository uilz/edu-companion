"""资料系统桩 — 原 domain/materials/service.py"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


class MaterialsStub:
    async def upload(self, user_id: str, file_path: str) -> dict:
        return {"status": "ok", "file_path": file_path}

    async def search(self, user_id: str, query: str, top_k: int = 10) -> list[dict]:
        if not query.strip():
            return []
        try:
            from app.infrastructure.files.search import material_search
            results = await material_search.search(
                user_id=user_id, query=query, top_k=top_k,
            )
            return results
        except Exception as e:
            logger.error("Material search failed: %s", e)
            return []

    async def generate_questions(self, user_id: str, material_id: str, count: int = 5) -> list[dict]:
        try:
            from app.infrastructure.db.database import get_db
            from app.infrastructure.llm.llm_service import llm_service

            db = get_db()
            rows = db.fetchall(
                "SELECT text FROM material_chunks WHERE material_id = %s AND user_id = %s LIMIT 5",
                (material_id, user_id),
            )
            if not rows:
                return []

            context = "\n\n".join(r["text"][:1000] for r in rows)
            prompt = (
                f"基于以下资料内容，生成{count}道练习题。\n"
                f"要求：题型覆盖选择题和简答题，包含答案和解析。\n\n"
                f"资料内容：\n{context[:3000]}\n\n"
                f'请以JSON格式输出：\n'
                f'[{{"type":"choice|short","question":"...","options":["A.","B.","C.","D."],"answer":"...","explanation":"..."}}]'
            )

            response = await llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一个出题助手。严格按照JSON格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                task_type="chat", temperature=0.5, max_tokens=4096,
            )

            try:
                json_str = re.search(r'\[.*\]', response, re.DOTALL)
                questions = json.loads(json_str.group()) if json_str else json.loads(response)
            except (json.JSONDecodeError, Exception):
                questions = [{"question": response[:500], "type": "short", "answer": "", "explanation": ""}]

            for q in questions:
                q["material_id"] = material_id
            return questions
        except Exception as e:
            logger.error("Material generate_q failed: %s", e)
            return []

    async def on_indexed(self, event) -> None:
        user_id = getattr(event, "user_id", "?")
        material_id = getattr(event, "material_id", "?")
        chunk_count = getattr(event, "chunk_count", 0)
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
            logger.info("Material post-processed: %s skills=%d", material_id, len(skills))
        except Exception as e:
            logger.error("Material post-processing failed: %s", e)
