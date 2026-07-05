"""LanguageRoom STT/TTS 服务

依据 docs/modules/language-room/overview.md §3.1 + ADR 0004 决策 4
"STT: 通过 LiveKit 的 STT 插件或独立 Whisper 服务"
"TTS: 通过 LiveKit 的 TTS 插件或独立云服务（用于 AI 角色）"

复用现有基础设施:
  - STT: 复用 app.api.system.multimodal 提供的 Whisper via LiteLLM
  - TTS: 复用 app.api.system.multimodal 提供的 Edge-TTS

本服务提供:
  1. 流式 STT 段拼接（合并短句为完整句）
  2. 多语种 TTS 语音映射
  3. AI 角色专属语音选择（基于 ai_personas 配置）
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


# ── 语种 → Edge-TTS voice 映射 ──

VOICE_MAP: dict[str, str] = {
    "en": "en-US-AriaNeural",
    "en-US": "en-US-AriaNeural",
    "en-GB": "en-GB-RyanNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-IsabellaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
}


def resolve_voice(language: str, gender: str = "") -> str:
    """根据语种和性别选择合适的 TTS voice

    gender: female / male / empty (使用默认女声)
    """
    base = VOICE_MAP.get(language, "en-US-AriaNeural")
    # Edge-TTS 中带 "Neural" 的 voice 性别不明显；此处保留扩展点
    return base


# ── STT: 复用 Whisper via LiteLLM ──


@dataclass
class SttRequest:
    """STT 转写请求"""
    audio_path: str
    language: str = "auto"        # auto / en / zh / ...
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""


@dataclass
class SttResult:
    """STT 转写结果"""
    text: str
    language: str = ""
    confidence: float = 0.0
    duration_seconds: float = 0.0
    started_at: float = field(default_factory=time.time)
    ended_at: float = field(default_factory=time.time)


async def transcribe_audio(req: SttRequest) -> SttResult:
    """Whisper STT 转写

    复用现有 multimodal 服务（litellm.atranscription）
    """
    from app.infrastructure.db.database import get_db
    from app.config import settings

    started = time.time()
    try:
        from litellm import atranscription

        with open(req.audio_path, "rb") as f:
            kwargs = {
                "model": settings.whisper_model,
                "file": f,
            }
            if req.language and req.language != "auto":
                kwargs["language"] = req.language
            response = await atranscription(**kwargs)

        text = response.text if hasattr(response, "text") else str(response)
        lang = getattr(response, "language", req.language) or req.language
        return SttResult(
            text=text.strip() if text else "",
            language=str(lang),
            confidence=0.0,  # Whisper 不返回置信度
            duration_seconds=time.time() - started,
            started_at=started,
            ended_at=time.time(),
        )
    except Exception as e:
        logger.error("STT 转写失败: %s", e)
        return SttResult(
            text="",
            language=req.language,
            duration_seconds=time.time() - started,
            started_at=started,
            ended_at=time.time(),
        )


# ── TTS: 复用 Edge-TTS ──


@dataclass
class TtsRequest:
    """TTS 合成请求"""
    text: str
    language: str = "en"
    voice: str = ""                # 显式指定 voice, 优先级高于 language
    rate: str = "+0%"              # 语速
    pitch: str = "+0Hz"


async def synthesize_speech(req: TtsRequest) -> bytes:
    """Edge-TTS 语音合成

    返回完整音频字节流（mp3 格式）
    """
    try:
        import edge_tts

        voice = req.voice or resolve_voice(req.language)
        # 清洗 Markdown
        try:
            from app.infrastructure.tts_text_cleaner import strip_markdown_for_tts
            text = strip_markdown_for_tts(req.text, max_chars=400)
        except ImportError:
            text = req.text[:400]

        communicate = edge_tts.Communicate(text, voice, rate=req.rate, pitch=req.pitch)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
    except Exception as e:
        logger.error("TTS 合成失败: %s", e)
        return b""


async def synthesize_speech_stream(req: TtsRequest) -> AsyncIterator[bytes]:
    """Edge-TTS 流式合成"""
    try:
        import edge_tts

        voice = req.voice or resolve_voice(req.language)
        try:
            from app.infrastructure.tts_text_cleaner import strip_markdown_for_tts
            text = strip_markdown_for_tts(req.text, max_chars=400)
        except ImportError:
            text = req.text[:400]

        communicate = edge_tts.Communicate(text, voice, rate=req.rate, pitch=req.pitch)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    except Exception as e:
        logger.error("TTS 流式合成失败: %s", e)
        return


# ── AI 角色语音选择 ──


def select_voice_for_persona(persona: dict) -> str:
    """根据 AI 角色配置选择 TTS 语音

    persona 字段:
      - target_language: 语种
      - gender_voice: 性别
      - speech_rate: slow/normal/fast
    """
    lang = persona.get("target_language", "en")
    gender = persona.get("gender_voice", "")
    voice = resolve_voice(lang, gender)

    # 性别适配：Edge-TTS 中 Neural voice 一些有 Male/Female 区分
    male_voices = {
        "en-US": "en-US-GuyNeural",
        "zh-CN": "zh-CN-YunxiNeural",
        "ja-JP": "ja-JP-KeitaNeural",
    }
    if gender.lower() in ("male", "m"):
        prefix = lang if "-" in lang else "en-US"
        voice = male_voices.get(prefix, voice)

    return voice


def tts_request_for_persona(persona: dict, text: str) -> TtsRequest:
    """根据 AI 角色配置构造 TTS 请求"""
    rate = "+0%"
    speech_rate = persona.get("speech_rate", "normal")
    if speech_rate == "slow":
        rate = "-15%"
    elif speech_rate == "fast":
        rate = "+15%"

    return TtsRequest(
        text=text,
        language=persona.get("target_language", "en"),
        voice=select_voice_for_persona(persona),
        rate=rate,
    )


# ── STT 段合并工具 ──


@dataclass
class TranscriptBuffer:
    """实时转写缓冲区：合并短片段为完整句"""
    user_id: str
    room_id: str
    buffer: str = ""
    last_update: float = field(default_factory=time.time)
    silence_threshold: float = 1.5  # 1.5 秒静默后提交

    def append(self, text: str) -> Optional[str]:
        """追加片段；返回完整句（如果已触发静默）"""
        if not text:
            return None
        self.buffer = (self.buffer + " " + text).strip() if self.buffer else text.strip()
        self.last_update = time.time()
        return None

    def maybe_flush(self) -> Optional[str]:
        """根据静默时间判断是否应提交"""
        if not self.buffer:
            return None
        if time.time() - self.last_update >= self.silence_threshold:
            text = self.buffer
            self.buffer = ""
            return text
        return None
