"""
多媒体领域服务 — Phase 5 核心编排

职责:
1. 监听 AssistantReplied 事件 → 触发语音合成 + 配图生成
2. 生成完成后执行后续推送
3. 异常隔离: 单个生成失败不影响对话主流程

依赖规则:
- 只依赖 Protocol (AudioSynthesizer, ImageRenderer)
- 实现通过 DI 容器注入
- 不直接操作 WebSocket
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from shared.events import (
    AssistantReplied,
)

if TYPE_CHECKING:
    from shared.protocols.multimedia import AudioSynthesizer, ImageRenderer
    from infra.event_bus import EventBus

logger = logging.getLogger("multimedia")


class MultimediaService:
    """多媒体生成服务"""

    def __init__(
        self,
        tts: AudioSynthesizer,
        renderer: ImageRenderer,
        event_bus: EventBus,
    ):
        self._tts = tts
        self._renderer = renderer
        self._bus = event_bus

    async def on_assistant_replied(self, event: AssistantReplied) -> None:
        """
        事件: AI 完成回复 → 异步生成多媒体系列

        策略:
        1. 语音: 始终为回复内容生成 TTS（异步、非阻塞）
        2. 配图: 检测内容是否含公式 → LaTeX → SVG
        """
        logger.info(
            "🎬 Multimedia triggered: user=%s msg=%s math=%s skills=%s",
            event.user_id, event.message_id[:8],
            event.contains_math, event.skill_ids,
        )

        tasks = []

        # 1. TTS 语音合成
        if event.content:
            tasks.append(self._synthesize_audio(event))

        # 2. 配图生成
        if event.contains_math or event.skill_ids:
            tasks.append(self._render_images(event))

        if tasks:
            # 并行执行，不影响对话流程
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Multimedia task failed: %s", result)

    async def _synthesize_audio(self, event: AssistantReplied) -> None:
        """TTS 语音合成"""
        try:
            skill_id = event.skill_ids[0] if event.skill_ids else event.message_id[:12]
            result = await self._tts.synthesize(
                text=event.content[:500],  # 取前500字符
                skill_id=skill_id,
            )

            logger.info("✅ TTS done: %s", result["url"])
        except Exception as e:
            logger.error("❌ TTS failed: %s", e)

    async def _render_images(self, event: AssistantReplied) -> None:
        """知识点配图生成"""
        try:
            skill_id = event.skill_ids[0] if event.skill_ids else event.message_id[:12]

            # 检测内容类型并生成对应配图
            result = await self._renderer.render_for_knowledge(
                skill_id=skill_id,
                skill_name="",
                content=event.content,
            )

            if result:
                logger.info("✅ Image rendered: %s", result["url"])
        except Exception as e:
            logger.error("❌ Image rendering failed: %s", e)
