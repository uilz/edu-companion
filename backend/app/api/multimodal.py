"""
多模态 REST API

端点:
  POST /api/multimodal/transcribe  — 音频 → 文字（Whisper）
"""

from __future__ import annotations

import logging
import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multimodal", tags=["多模态"])


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

        with open(tmp_path, "rb") as f:
            response = await atranscription(
                model="whisper-1",
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
        except OSError:
            pass
