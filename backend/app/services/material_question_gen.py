"""
基于用户资料生成练习题
MaterialQuestionGenerator

三种策略：
1. 原题提取 — 识别资料中已有的题目
2. 改题生成 — 修改原题的数值/条件
3. 知识点生成 — 根据资料知识点，LLM出新题
"""
from __future__ import annotations

import logging
from typing import Optional

from app.schemas.practice import (
    BloomLevel,
    Question,
    QuestionOption,
    AnswerType,
)
from app.services.llm_service import llm_service
from app.services.material_search import material_search

logger = logging.getLogger(__name__)

MATERIAL_QUESTION_SYSTEM_PROMPT = """你是一个练习题生成AI。根据用户提供的学习资料内容，生成与资料风格一致的练习题。

## 核心要求
1. **内容一致**：题目基于资料中的知识点和语境
2. **术语一致**：使用资料中的术语和符号风格
3. **格式统一**：与现有练习系统保持一致

## 输出格式
返回JSON数组：
[{
  "text": "题目文本（支持$LaTeX$公式）",
  "options": [
    {"letter": "A", "text": "选项内容", "is_correct": false, "distractor_type": "conceptual"},
    ...
  ],
  "correct_answer": "A",
  "explanation": "分步解析",
  "hints": ["方向提示", "步骤提示", "部分解法"],
  "difficulty": 0.5
}]
"""


class MaterialQuestionGenerator:
    """
    基于用户资料生成练习题
    
    核心价值：题目不是凭空生成，而是基于用户正在学的教材内容，
    确保术语一致、风格匹配、错误时能精确定位到教材章节。
    """

    async def generate_from_materials(
        self,
        user_id: str,
        material_ids: list[str],
        skill_id: Optional[str] = None,
        bloom_level: BloomLevel = BloomLevel.APPLY,
        difficulty: float = 0.5,
        count: int = 3,
        content_type: str = "choice",
    ) -> tuple[list[Question], list[dict]]:
        """
        基于用户指定资料生成练习题
        
        返回:
            (questions, source_chunks) — 题目列表 + 来源资料片段
        """
        # Step 1: 从资料中搜索相关内容
        search_query = skill_id or "知识点"
        search_results = await material_search.search(
            user_id=user_id,
            query=search_query,
            material_ids=material_ids,
            top_k=15,
        )

        if not search_results:
            logger.warning("未找到相关资料")
            return [], []

        # Step 2: 分类搜索结果
        question_chunks = [r for r in search_results if r.get("chunk_type") == "question"]
        knowledge_chunks = [r for r in search_results if r.get("chunk_type") != "question"]

        questions = []
        source_chunks = []

        # Step 3: 策略1 — 原题提取
        for chunk in question_chunks[:3]:
            q = self._extract_question_from_chunk(chunk)
            if q:
                questions.append(q)
                source_chunks.append(chunk)

        # Step 4: 策略2 — 改题生成（基于原题修改）
        remaining = count - len(questions)
        if remaining > 0 and question_chunks:
            from app.services.question_generator import get_question_generator
            generator = get_question_generator(llm_service)

            for chunk in question_chunks[:remaining]:
                # 用LLM基于原题生成变形题
                variant_qs = generator.generate(
                    subject=self._subject_from_chunk(chunk),
                    skill_id=skill_id or "general",
                    bloom_level=bloom_level,
                    difficulty=difficulty,
                    count=1,
                    content_type=content_type,
                    material_context=chunk.get("text", "")[:2000],
                )
                questions.extend(variant_qs)
                source_chunks.append(chunk)

        # Step 5: 策略3 — 知识点生成
        remaining = count - len(questions)
        if remaining > 0 and knowledge_chunks:
            from app.services.question_generator import get_question_generator
            generator = get_question_generator(llm_service)

            # 合并知识点chunk作为上下文
            context = "\n\n---\n\n".join(
                c.get("text", "")[:500] for c in knowledge_chunks[:5]
            )

            new_qs = generator.generate(
                subject=self._subject_from_chunks(knowledge_chunks),
                skill_id=skill_id or "general",
                bloom_level=bloom_level,
                difficulty=difficulty,
                count=min(remaining, 5),
                content_type=content_type,
                material_context=context,
            )
            questions.extend(new_qs)
            source_chunks.extend(knowledge_chunks[:len(new_qs)])

        logger.info(
            "从资料生成题目: %d题 (原题:%d 改题:%d 新题:%d)",
            len(questions),
            len([q for q in questions if getattr(q, 'source', '') == 'material_extract']),
            len([q for q in questions if getattr(q, 'source', '') == 'material_variant']),
            len([q for q in questions if getattr(q, 'source', '') == 'material_knowledge']),
        )

        return questions[:count], source_chunks[:count]

    def _extract_question_from_chunk(self, chunk: dict) -> Optional[Question]:
        """从chunk中提取已有题目（简化版，完整版需要LLM辅助）"""
        # MVP: 如果chunk标记为question类型，创建一条引用题
        # 完整版需要用LLM解析题干、选项、答案
        return Question(
            skill_id=chunk.get("skill_ids", ["general"])[0] if chunk.get("skill_ids") else "general",
            subject=self._subject_from_chunk(chunk),
            text=f"(来自你的资料) {chunk.get('text', '')[:300]}",
            options=[
                QuestionOption(letter="A", text="待LLM生成", is_correct=True),
            ],
            answer_type=AnswerType.CHOICE,
            correct_answer="A",
            explanation="此题来自你的学习资料，需LLM进一步解析",
            difficulty=0.5,
            source="material_extract",
            tags=["material", chunk.get("source_file", ""), chunk.get("chunk_id", "")],
        )

    def _subject_from_chunk(self, chunk: dict) -> str:
        """从chunk推断学科"""
        skills = chunk.get("skill_ids", [])
        for s in skills:
            if "calculus" in s or "math" in s:
                return "数学"
            if "physics" in s:
                return "物理"
            if "linear" in s:
                return "线代"
        return "通用"

    def _subject_from_chunks(self, chunks: list[dict]) -> str:
        for c in chunks:
            subj = self._subject_from_chunk(c)
            if subj != "通用":
                return subj
        return "通用"


# 全局实例
material_question_gen = MaterialQuestionGenerator()
