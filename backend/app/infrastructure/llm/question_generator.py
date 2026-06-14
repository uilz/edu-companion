"""
LLM练习题生成服务
基于用户需求 + 知识点状态 + 用户资料，动态生成个性化练习题
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.config import settings
from app.schemas.practice import (
    AnswerType,
    BloomLevel,
    Question,
    QuestionOption,
)
from app.infrastructure.llm.llm_service import LLMService

logger = logging.getLogger(__name__)


# ── 生成提示词模板 ──

QUESTION_SYSTEM_PROMPT = """你是一个专业的练习题生成AI。根据学生的知识水平和需求，生成高质量练习题。

## 题目要求
1. **题型**：根据 content_type 生成对应题型
2. **Bloom层次**：严格按照指定的认知层次设计题目
3. **难度匹配**：difficulty 是0-1的连续值，0.3=基础，0.5=中等，0.8=困难
4. **干扰项设计**：
   - 选择题：每个错误选项对应一种学生常见的错误理解
   - 标注每个干扰项的 distractor_type（错因类型）
5. **解析**：提供清晰的分步解析
6. **提示**：提供3个渐进式提示（方向→步骤→部分解法）

## 输出格式
返回JSON数组，每个题目格式：
{
  "text": "题目文本（支持LaTeX数学公式，用$...$或$$...$$）",
  "bloom_level": "apply",
  "options": [
    {"letter": "A", "text": "选项内容", "is_correct": false, "distractor_type": "sign_error"},
    ...
  ],
  "correct_answer": "A",
  "explanation": "分步解析",
  "hints": ["方向提示", "步骤提示", "部分解法"],
  "difficulty": 0.5
}

## 学科知识要点
{knowledge_context}
"""


class QuestionGenerator:
    """
    LLM练习题生成器
    
    策略：
    1. 先查模板题库（命中率高 + 免费）
    2. 模板未命中 → LLM生成（灵活 + 有成本）
    3. LLM生成后缓存到模板库
    """

    # 预置模板（高频知识点）
    TEMPLATES = {
        "calculus_limit": """极限知识要点：
- 极限的定义（ε-δ语言）
- 重要极限：lim(x→0) sin(x)/x = 1, lim(x→∞) (1+1/x)^x = e
- 极限的运算法则（四则运算、复合函数）
- 无穷小与无穷大
- 单侧极限
- 夹逼定理""",

        "calculus_derivative": """导数知识要点：
- 导数的定义与几何意义
- 基本求导公式（幂函数、三角函数、指数函数、对数函数）
- 求导法则（四则运算、链式法则）
- 高阶导数
- 隐函数求导
- 参数方程求导""",

        "calculus_integral": """积分知识要点：
- 不定积分的定义与性质
- 基本积分公式
- 换元积分法
- 分部积分法
- 定积分的定义与性质
- 定积分的应用（面积、体积）""",

        "linear_matrix": """矩阵知识要点：
- 矩阵的定义与基本运算
- 矩阵的转置
- 特殊矩阵（单位阵、对角阵、对称阵）
- 矩阵的秩
- 逆矩阵
- 分块矩阵""",

        "linear_determinant": """行列式知识要点：
- 行列式的定义与性质
- 行列式的计算（展开法、初等变换）
- 克拉默法则
- Vandermonde行列式""",

        "probability": """概率论知识要点：
- 随机事件与概率
- 条件概率与贝叶斯公式
- 随机变量与分布函数
- 常见分布（二项、泊松、正态、指数）
- 数学期望与方差
- 大数定律与中心极限定理""",

        "physics_mechanics": """力学知识要点：
- 运动学（位移、速度、加速度）
- 牛顿运动定律
- 动量与冲量
- 功与能
- 刚体转动
- 简谐振动""",
    }

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self._cache: dict[str, list[Question]] = {}

    async def generate(
        self,
        subject: str,
        skill_id: str,
        bloom_level: BloomLevel = BloomLevel.APPLY,
        difficulty: float = 0.5,
        count: int = 3,
        content_type: str = "choice",
        material_context: Optional[str] = None,
    ) -> list[Question]:
        """
        生成练习题
        
        参数:
            subject: 学科
            skill_id: 知识点ID
            bloom_level: Bloom认知层次
            difficulty: 目标难度 0-1
            count: 生成数量
            content_type: 题型 (choice/fill/free_form)
            material_context: 用户资料上下文（可选）
        """
        knowledge_ctx = self.TEMPLATES.get(skill_id, f"{subject} - {skill_id}")
        if material_context:
            knowledge_ctx += f"\n\n用户学习资料内容：\n{material_context[:2000]}"

        bloom_labels = {"remember": "记忆", "understand": "理解", "apply": "应用", "analyze": "分析", "evaluate": "评价", "create": "创造"}
        bloom_zh = bloom_labels.get(bloom_level.value, bloom_level.value)
        type_zh = {"choice": "选择题（单选）", "multiple": "多选题", "fill": "填空题", "free_form": "解答题", "calculation": "计算题"}.get(content_type, content_type)

        prompt = f"""你是一个专业的练习题生成AI。请严格按照要求生成 {count} 道高质量的{subject}练习题。

## 知识点背景
{knowledge_ctx}

## 出题要求
- 题型：{type_zh}
- Bloom认知层次：{bloom_zh}
- 目标难度：{difficulty:.1f}（0最易~1最难）
- 题目内容要具体、有实际意义，包含真实的数值/表达式/情景
- 支持 LaTeX 数学公式（用 $...$ 或 $$...$$）

## 输出格式
直接返回JSON数组（不要markdown代码块包裹，不要其他文字），每个题目格式：
{{
  "text": "题目内容（含LaTeX）",
  "options": [
    {{"letter": "A", "text": "选项内容", "is_correct": true/false, "distractor_type": "错因类型"}},
    ...
  ],
  "correct_answer": "正确选项字母",
  "explanation": "解析（含LaTeX）",
  "difficulty": 0.5
}}
"""

        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                task_type="chat",
                temperature=0.7,
                max_tokens=4000,
            )

            questions_data = self._parse_llm_response(response)
            if not questions_data:
                logger.warning("LLM生成JSON解析失败，重试一次")
                response = await self.llm.generate(
                    messages=[{"role": "user", "content": prompt + "\n\n重要：只返回纯JSON数组，不要包含任何其他文字或markdown格式。"}],
                    task_type="chat",
                    temperature=0.1,
                    max_tokens=4000,
                )
                questions_data = self._parse_llm_response(response)
            if not questions_data:
                logger.warning("LLM生成失败，使用fallback模板")
                return self._generate_fallback(skill_id, subject, count)

            # 5. 构建Question对象
            questions = []
            for q_data in questions_data[:count]:
                question = Question(
                    skill_id=skill_id,
                    subject=subject,
                    bloom_level=bloom_level,
                    text=q_data.get("text", ""),
                    options=self._build_options(q_data.get("options", [])),
                    answer_type=AnswerType.CHOICE if content_type == "choice" else AnswerType.FILL,
                    correct_answer=q_data.get("correct_answer", ""),
                    explanation=q_data.get("explanation", ""),
                    hints=q_data.get("hints", []),
                    difficulty=q_data.get("difficulty", difficulty),
                    source="llm",
                    tags=[skill_id, subject, bloom_level.value],
                )
                questions.append(question)

            # 6. 缓存到模板库
            cache_key = f"{skill_id}_{bloom_level.value}_{int(difficulty*10)}"
            self._cache[cache_key] = questions

            return questions

        except Exception as e:
            logger.error(f"LLM题目生成异常: {e}")
            return self._generate_fallback(skill_id, subject, count)

    def _parse_llm_response(self, response: str) -> list[dict]:
        """解析LLM返回的JSON"""
        # 尝试提取JSON部分
        try:
            # 直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            logger.debug("Direct JSON parse failed, trying code block extraction")

        # 尝试从markdown代码块中提取
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                logger.debug("Code block JSON parse failed, trying array extraction")

        # 尝试找数组
        array_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', response)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except json.JSONDecodeError:
                logger.debug("Array regex JSON parse failed, giving up")

        logger.warning(f"无法解析LLM响应为JSON: {response[:200]}")
        return []

    def _build_options(self, options_data: list[dict]) -> list[QuestionOption]:
        """构建选项列表"""
        if not options_data:
            return []

        return [
            QuestionOption(
                letter=opt.get("letter", chr(65 + i)),
                text=opt.get("text", ""),
                is_correct=opt.get("is_correct", False),
                distractor_type=opt.get("distractor_type"),
            )
            for i, opt in enumerate(options_data)
        ]

    def _generate_fallback(
        self, skill_id: str, subject: str, count: int,
    ) -> list[Question]:
        """fallback题目生成（无需LLM）"""
        return [
            Question(
                skill_id=skill_id,
                subject=subject,
                text=f"关于{skill_id}的基础概念理解题 {i+1}",
                options=[
                    QuestionOption(letter="A", text="选项A", is_correct=True),
                    QuestionOption(letter="B", text="选项B", is_correct=False),
                    QuestionOption(letter="C", text="选项C", is_correct=False),
                    QuestionOption(letter="D", text="选项D", is_correct=False),
                ],
                correct_answer="A",
                explanation="这是基础题，请查阅相关教材",
                difficulty=0.3,
                source="fallback",
            )
            for i in range(count)
        ]


# 全局实例（延迟初始化）
question_generator: Optional[QuestionGenerator] = None


def get_question_generator(llm_service: LLMService) -> QuestionGenerator:
    global question_generator
    if question_generator is None:
        question_generator = QuestionGenerator(llm_service)
    return question_generator
