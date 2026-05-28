"""
多模态 REST API

端点:
  POST /api/multimodal/tts         — 文字 → 语音（Edge-TTS）
  POST /api/multimodal/transcribe  — 音频 → 文字（Whisper）
  GET  /api/multimodal/audio/{file} — 获取生成的 TTS 音频
  GET  /api/multimodal/images/{file} — 获取生成的配图
"""

from __future__ import annotations

import logging
import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multimodal", tags=["多模态"])

# 多媒体文件根目录
AUDIO_DIR = Path(os.path.expanduser("~/.companion/audio"))
IMAGE_DIR = Path(os.path.expanduser("~/.companion/images"))


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取生成的 TTS 音频文件"""
    path = AUDIO_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"音频文件不存在: {filename}")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/images/{filename}")
async def get_image(filename: str):
    """获取生成的配图文件"""
    path = IMAGE_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"配图文件不存在: {filename}")
    media_type = "image/svg+xml" if filename.endswith(".svg") else "image/png"
    return FileResponse(path, media_type=media_type)


@router.post("/tts")
async def text_to_speech(request: dict):
    """
    Edge-TTS 文字转语音

    请求体: {"text": "要朗读的文本", "voice": "zh-CN-XiaoxiaoNeural"}
    返回: MP3 音频文件
    """
    text = request.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    voice = request.get("voice", "zh-CN-XiaoxiaoNeural")

    # 清理文本（去除 Markdown 符号）
    clean_text = (
        text.replace("\n\n", "。")
        .replace("\n", "，")
        [:2000]  # 限制长度
    )

    try:
        import edge_tts
        import uuid

        # 生成唯一文件名
        filename = f"tts_{uuid.uuid4().hex[:12]}.mp3"
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        output_path = AUDIO_DIR / filename

        # 使用 edge-tts 生成音频
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(str(output_path))

        logger.info(f"Edge-TTS generated: {filename} ({len(clean_text)} chars, voice={voice})")

        return {
            "audio_url": f"/api/multimodal/audio/{filename}",
            "voice": voice,
            "text_length": len(clean_text),
        }

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
        except OSError:
            pass
