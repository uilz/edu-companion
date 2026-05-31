"""
Multimedia Service Protocols — 多媒体模块对外契约 (Phase 5)

定义 TTS 合成和图片生成的抽象接口。
实现类位于 infra/ 中。
"""

from __future__ import annotations

from typing import Protocol


class AudioSynthesizer(Protocol):
    """TTS 语音合成接口"""

    async def synthesize(
        self,
        text: str,
        skill_id: str = "",
        voice: str = "zh-CN-XiaoxiaoNeural",
    ) -> dict:
        """
        将文本合成为语音。

        Returns:
            {"url": str, "duration_ms": int, "format": "mp3", "cache_hit": bool}
        """
        ...

    async def synthesize_knowledge(
        self,
        skill_id: str,
        skill_name: str,
        explanation: str,
    ) -> dict:
        """
        为知识点生成专属语音讲解。

        自动提取精华内容（≤200字口语化），
        缓存到 COMPANION_HOME/audio/{skill_id}.mp3

        Returns:
            {"url": str, "duration_ms": int, "cache_hit": bool}
        """
        ...


class ImageRenderer(Protocol):
    """知识点配图渲染接口"""

    async def render_latex(
        self,
        formula: str,
        skill_id: str = "",
    ) -> dict:
        """
        LaTeX 公式 → SVG 图片。

        Returns:
            {"url": str, "format": "svg", "cache_hit": bool}
        """
        ...

    async def render_diagram(
        self,
        description: str,
        diagram_type: str = "concept",
        skill_id: str = "",
    ) -> dict:
        """
        概念/流程图 → SVG 图片。

        diagram_type: "concept" | "flow" | "comparison"

        Returns:
            {"url": str, "format": "svg", "cache_hit": bool}
        """
        ...

    async def render_for_knowledge(
        self,
        skill_id: str,
        skill_name: str,
        content: str,
    ) -> dict | None:
        """
        为知识点自动选择合适的配图方式。

        检测内容类型:
        - 含 $...$ → LaTeX 渲染
        - 含对比/分类 → 概念图
        - 其他 → None (跳过)

        Returns:
            {"url": str, "format": str} or None
        """
        ...
