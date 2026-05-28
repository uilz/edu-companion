"""LLM 提案生成器 — 模板优先 + LLM 润色

工作流程:
  1. 模板引擎先生成结构化提案骨架
  2. LLM 润色标题和描述，注入协商语气
  3. LLM 不可用/超时则直接返回模板结果
"""

from __future__ import annotations

import json
import logging

from ..models import Proposal, DiagnosisReport

logger = logging.getLogger(__name__)

# ── 系统提示词（用于 LLM 润色） ──

SYSTEM_PROMPT = """你是一位聪明的教育助理，负责将系统生成的提案润色得更自然。

要求:
1. 保持提案的协商语气，不要让用户觉得被命令
2. 每条提案加上具体的、个性化的理由（基于掌握度和错误模式）
3. 语气积极、鼓励，含成长型思维
4. 每条提案控制在 1-2 句话，简洁不啰嗦
5. 保留原有的 emoji 和 action_type

输入格式:
{
  "proposals": [
    {"emoji": "✏️", "title": "...", "description": "...", "action_type": "practice", "kp_id": "...", "mastery": 0.3, "goal_distance": 0.5, "error_patterns": "...", "trend": "..."},
    ...
  ]
}

输出格式: 只返回 JSON 数组，每个元素有 title 和 description 两个字段。
不要输出任何解释、注释或 Markdown 格式。"""


class LLMProposalGenerator:
    """基于 LLM 的提案生成器（备降：模板）"""

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def polish_proposals(
        self,
        proposals: list[Proposal],
    ) -> list[Proposal]:
        """LLM 润色提案，不可用则原样返回"""
        if not proposals:
            return proposals

        polished = await self._try_llm_polish(proposals)
        if polished:
            # 保留原始优先级/action_type/payload，只覆盖 title 和 description
            for i, p in enumerate(polished):
                if i < len(proposals):
                    proposals[i].title = p.get("title", proposals[i].title)
                    proposals[i].description = p.get("description", proposals[i].description)
            return proposals
        return proposals

    async def generate_suggestion(
        self,
        diagnosis: DiagnosisReport,
        max_proposals: int = 3,
    ) -> list[Proposal]:
        """基于诊断报告生成 LLM 润色的建议"""
        # 1. 模板先生成骨架
        from .proposal_generator import ProposalGenerator
        template_gen = ProposalGenerator()
        proposals = template_gen.generate_from_diagnosis(diagnosis, max_proposals)

        # 2. LLM 润色
        if proposals:
            proposals = await self.polish_proposals(proposals)

        return proposals

    async def _try_llm_polish(
        self,
        proposals: list[Proposal],
    ) -> list[dict] | None:
        """尝试调用 LLM 润色，失败返回 None"""
        if not self._llm:
            logger.info("LLM 服务未注入，使用模板提案")
            return None

        try:
            input_data = [
                {
                    "emoji": p.emoji,
                    "title": p.title,
                    "description": p.description,
                    "action_type": p.action_type,
                    "mastery": p.payload.get("mastery", 0.5) if p.payload else 0.5,
                }
                for p in proposals
            ]

            response = await self._llm.chat(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps({"proposals": input_data}, ensure_ascii=False)}],
                temperature=0.7,
                max_tokens=500,
            )

            text = response
            if isinstance(response, dict):
                text = response.get("content", response.get("text", ""))

            # 清理可能的 Markdown 代码块包裹
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]
            if text.startswith("json"):
                text = text[4:]

            result = json.loads(text.strip())
            if isinstance(result, list) and len(result) == len(proposals):
                return result

            logger.warning(f"LLM 返回格式异常: {text[:200]}")
            return None

        except Exception as e:
            logger.warning(f"LLM 润色失败，回退模板: {e}")
            return None
