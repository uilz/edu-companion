"""自我解释评估服务

评估学生对知识点的自我解释质量，并将结果写入 CognitiveNode。
"""
from __future__ import annotations

import json
import logging
import time

from app.domain.cognitive.models import Metacognition

logger = logging.getLogger(__name__)


async def evaluate_self_explanation(
    user_id: str,
    knowledge_node_id: str,
    explanation_text: str,
    prompt_type: str = "retell",
) -> dict:
    """评估学生的自我解释质量，结果写入 CognitiveNode。

    返回:
        {accuracy, completeness, clarity, feedback, concept_name}
    """
    from app.domain.cognitive import get_repo

    repo = get_repo()
    node = repo.get_node(knowledge_node_id, user_id)
    concept_name = node.label if node else knowledge_node_id

    evaluation_prompt = f"""你是一个学习评估助手。
学生刚学习了「{concept_name}」。现在他用自己话做了如下解释：
「{explanation_text}」
请评估：
1. 准确性（A/B/C）——包含重大错误吗？
2. 完整性（完整/部分/缺失核心）——抓住了关键点吗？
3. 清晰度（清晰/模糊/混乱）——容易理解吗？
4. 一句话反馈（告诉学生哪里说得好、哪里可以改进）
输出格式（严格 JSON）：{{ "accuracy": "A|B|C", "completeness": "完整|部分|缺失核心", "clarity": "清晰|模糊|混乱", "feedback": "一句话反馈" }}"""

    from app.infrastructure.llm.llm_service import llm_service
    try:
        raw = await llm_service.generate(
            messages=[{"role": "user", "content": evaluation_prompt}],
            task_type="explain",
            temperature=0.3,
            max_tokens=512,
        )
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"LLM 自我解释评估失败: {e}, raw={raw if 'raw' in dir() else 'N/A'}")
        result = {"accuracy": "B", "completeness": "部分", "clarity": "模糊", "feedback": "评估暂不可用，请稍后重试"}

    try:
        node = repo.get_node(knowledge_node_id, user_id)
        if node:
            node.deep_processing.task_instances.append({
                "type": "self_explain",
                "prompt_type": prompt_type,
                "explanation_text": explanation_text[:500],
                "result": result,
                "timestamp": time.time(),
            })
            accuracy_score = {"A": 0.9, "B": 0.6, "C": 0.3}.get(result.get("accuracy", "B"), 0.6)
            completeness_score = {"完整": 0.9, "部分": 0.5, "缺失核心": 0.2}.get(result.get("completeness", "部分"), 0.5)
            clarity_score = {"清晰": 0.9, "模糊": 0.5, "混乱": 0.2}.get(result.get("clarity", "模糊"), 0.5)
            overall = (accuracy_score + completeness_score + clarity_score) / 3

            old_meta = node.metacognition
            new_calibration = old_meta.calibration_error * 0.7 + abs(old_meta.self_assessment - overall) * 0.3
            node.metacognition = Metacognition(
                self_assessment=overall,
                calibration_error=round(new_calibration, 4),
                direction="accurate" if new_calibration < 0.3 else (
                    "overconfident" if overall > old_meta.self_assessment else "underconfident"
                ),
            )
            repo.upsert_node(node, user_id)
    except Exception as e:
        logger.warning(f"写入 CognitiveNode 失败: {e}")

    return {
        "accuracy": result.get("accuracy", "B"),
        "completeness": result.get("completeness", "部分"),
        "clarity": result.get("clarity", "模糊"),
        "feedback": result.get("feedback", ""),
        "concept_name": concept_name,
    }
