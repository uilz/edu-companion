"""
多模态 REST API

端点:
  POST /api/multimodal/tts         — 文字 → 语音（Edge-TTS，非流式）
  GET  /api/multimodal/tts          — 文字 → 语音（Edge-TTS，流式，直接返回音频）
  POST /api/multimodal/transcribe  — 音频 → 文字（Whisper）
  GET  /api/multimodal/audio/{file} — 获取生成的 TTS 音频
"""

from __future__ import annotations

import logging
import tempfile
import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.config import COMPANION_HOME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multimodal", tags=["多模态"])

# 多媒体文件根目录
AUDIO_DIR = COMPANION_HOME / "audio"
IMAGE_DIR = COMPANION_HOME / "images"


def _clean_text(text: str) -> str:
    """清理 Markdown 文本，去除格式符号"""
    try:
        from app.infrastructure.tts_text_cleaner import strip_markdown_for_tts
        return strip_markdown_for_tts(text, max_chars=400)
    except ImportError:
        return (
            text.replace("\n\n", "。")
            .replace("\n", "，")[:400]
        )


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取生成的 TTS 音频文件"""
    path = AUDIO_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"音频文件不存在: {filename}")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/tts")
async def text_to_speech_stream(
    text: str = Query(..., description="要朗读的文本"),
    voice: str = Query("zh-CN-XiaoxiaoNeural", description="语音名称"),
):
    """
    Edge-TTS 流式语音合成（GET）

    浏览器可直接用 <audio src="..."> 播放，支持流式播放。
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本不能为空")

    clean_text = _clean_text(text)

    try:
        import edge_tts

        communicate = edge_tts.Communicate(clean_text, voice)

        async def generate():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        logger.info(f"Edge-TTS streaming: {len(clean_text)} chars, voice={voice}")
        return StreamingResponse(generate(), media_type="audio/mpeg")

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="edge-tts 未安装，请运行: pip install edge-tts",
        )
    except Exception as e:
        logger.error(f"Edge-TTS streaming failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"语音合成失败: {str(e)}",
        )


@router.post("/tts")
async def text_to_speech(request: dict):
    """
    Edge-TTS POST 流式语音合成

    请求体: {"text": "原始 Markdown 文本（含公式）", "voice": "zh-CN-XiaoxiaoNeural"}
    返回: audio/mpeg 流式音频（后端统一清洗 Markdown + 转换公式）
    """
    text = request.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    voice = request.get("voice", "zh-CN-XiaoxiaoNeural")
    clean_text = _clean_text(text)

    try:
        import edge_tts

        communicate = edge_tts.Communicate(clean_text, voice)

        async def generate():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        logger.info(f"Edge-TTS streaming POST: {len(clean_text)} chars, voice={voice}")
        return StreamingResponse(generate(), media_type="audio/mpeg")

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="edge-tts 未安装，请运行: pip install edge-tts",
        )
    except Exception as e:
        logger.error(f"Edge-TTS failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"语音合成失败: {str(e)}",
        )


@router.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    上传音频文件，返回 Whisper 转录文本。

    支持格式: WAV, WebM, MP3, M4A
    最大大小: 25MB
    """
    # 验证
    ALLOWED_TYPES = {
        "audio/wav", "audio/webm", "audio/mp3", "audio/mpeg",
        "audio/mp4", "audio/x-m4a", "audio/ogg", "audio/flac",
    }
    if audio_file.content_type and audio_file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的音频格式: {audio_file.content_type}。支持: WAV, WebM, MP3, M4A, OGG, FLAC",
        )

    # 读取到临时文件
    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio_file.read()
        if len(content) > 25 * 1024 * 1024:
            os.unlink(tmp.name)
            raise HTTPException(status_code=400, detail="音频文件不能超过 25MB")
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 调用 Whisper via LiteLLM
        from litellm import atranscription
        from app.config import settings

        with open(tmp_path, "rb") as f:
            response = await atranscription(
                model=settings.whisper_model,
                file=f,
            )

        transcription = response.text if hasattr(response, "text") else str(response)
        logger.info(f"Transcribed {len(content)} bytes → {len(transcription)} chars")

        return {
            "transcription": transcription.strip(),
            "language": getattr(response, "language", "zh"),
            "duration_ms": 0,
        }

    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"语音转写失败: {str(e)}",
        )
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError as e:
            logger.warning("Failed to clean up temp file %s: %s", tmp_path, e)
