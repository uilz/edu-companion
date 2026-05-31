"""
EdgeTTS 语音合成客户端 — 实现 AudioSynthesizer Protocol (Phase 5)

基于 edge-tts Python 库，支持:
- 文本→MP3 语音合成
- 按 skill_id 缓存（哈希去重）
- 返回标准化 dict {url, duration_ms, format, cache_hit}
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path

from app.config import COMPANION_HOME

logger = logging.getLogger("infra.tts")

# 缓存目录
CACHE_DIR = COMPANION_HOME / "audio"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 静态文件 URL 前缀（由 multimodal API 提供）
STATIC_PREFIX = "/api/multimodal/audio"


class EdgeTTSClient:
    """Edge TTS 合成器 — Microsoft Edge 免费 TTS 引擎"""

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        cache_dir: Path | None = None,
    ):
        self._voice = voice
        self._cache = cache_dir or CACHE_DIR
        self._cache.mkdir(parents=True, exist_ok=True)

    async def synthesize(
        self,
        text: str,
        skill_id: str = "",
        voice: str = "",
    ) -> dict:
        """将文本合成为语音"""
        import edge_tts

        from infra.tts_text_cleaner import strip_markdown_for_tts

        voice_name = voice or self._voice

        # 清洗 Markdown → 纯文本朗读
        clean_text = strip_markdown_for_tts(text)

        # 缓存检查
        cache_key = hashlib.sha256(
            f"{clean_text[:200]}|{voice_name}".encode()
        ).hexdigest()[:16]
        cache_file = self._cache / f"{cache_key}.mp3"

        if cache_file.exists():
            logger.debug("TTS cache hit: %s", cache_key)
            return {
                "url": f"{STATIC_PREFIX}/{cache_file.name}",
                "duration_ms": 0,  # 未测量
                "format": "mp3",
                "cache_hit": True,
            }

        # 合成
        try:
            communicate = edge_tts.Communicate(clean_text, voice_name)
            await communicate.save(str(cache_file))

            # ffmpeg 压缩：48kbps→24kbps，语音场景足够
            await self._compress(cache_file)

            logger.info("TTS synthesized: %s → %s", cache_key, cache_file.name)
            return {
                "url": f"{STATIC_PREFIX}/{cache_file.name}",
                "duration_ms": 0,
                "format": "mp3",
                "cache_hit": False,
            }
        except Exception as e:
            logger.error("TTS synthesize failed: %s", e)
            raise

    @staticmethod
    async def _compress(mp3_path: Path, target_bitrate: str = "24k") -> None:
        """用 ffmpeg 压缩 MP3 码率（语音 24kbps 足够清晰）"""
        import subprocess

        tmp = mp3_path.with_suffix(".tmp.mp3")
        try:
            proc = subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path),
                 "-codec:a", "libmp3lame", "-b:a", target_bitrate,
                 "-ar", "22050", "-ac", "1",
                 str(tmp)],
                capture_output=True, timeout=30,
            )
            if proc.returncode == 0 and tmp.stat().st_size < mp3_path.stat().st_size:
                tmp.replace(mp3_path)
                logger.debug("TTS compressed: %s → %dkbps", mp3_path.name, int(target_bitrate.rstrip("k")))
            else:
                tmp.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("TTS compress failed (using original): %s", e)
            tmp.unlink(missing_ok=True)

    async def synthesize_knowledge(
        self,
        skill_id: str,
        skill_name: str,
        explanation: str,
    ) -> dict:
        """为知识点生成专属语音讲解（带缓存）"""
        cache_file = self._cache / f"{skill_id}.mp3"

        if cache_file.exists():
            logger.debug("Knowledge audio cache hit: %s", skill_id)
            return {
                "url": f"{STATIC_PREFIX}/{skill_id}.mp3",
                "duration_ms": 0,
                "format": "mp3",
                "cache_hit": True,
            }

        # 提取精华内容（≤200字口语化）
        short_text = _extract_essence(explanation, max_chars=200)

        import edge_tts
        try:
            communicate = edge_tts.Communicate(short_text, self._voice)
            await communicate.save(str(cache_file))

            await self._compress(cache_file)

            logger.info("Knowledge TTS: %s → %s.mp3", skill_id, skill_id)
            return {
                "url": f"{STATIC_PREFIX}/{skill_id}.mp3",
                "duration_ms": 0,
                "format": "mp3",
                "cache_hit": False,
            }
        except Exception as e:
            logger.error("Knowledge TTS failed for %s: %s", skill_id, e)
            raise


def _extract_essence(text: str, max_chars: int = 200) -> str:
    """从知识点解释中提取口语化精华（简单截断策略）"""
    # 取第一段（到第一个句号或换行）
    first_para = text.split("\n")[0].strip()
    if len(first_para) > max_chars:
        # 尝试在 max_chars 内截断到完整句子
        cutoff = first_para.rfind("。", 0, max_chars)
        if cutoff > max_chars // 2:
            return first_para[: cutoff + 1]
        return first_para[:max_chars] + "…"
    return first_para
