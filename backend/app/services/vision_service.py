"""视觉理解服务 v1.0

接收图片 → base64 → LiteLLM 视觉模型分析
支持 OCR 识别、题目理解、图文推理
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt 模板 ──

OCR_PROMPT = """你是一个 OCR 识别专家。请识别图片中的所有文字内容。

输出格式（JSON）：
{
  "text": "完整识别文本",
  "language": "zh/en",
  "has_formula": true/false,
  "formula_text": "如果有公式，提取的 LaTeX 公式（否则空字符串）"
}
只输出 JSON。"""

PROBLEM_UNDERSTAND_PROMPT = """你是一个教育 AI。用户发来一道题目的图片，请：

1. 识别题目文字
2. 判断学科（数学/物理/英语/语文/编程/其他）
3. 识别题目类型（选择/填空/解答/判断/其他）
4. 提取关键知识点
5. 给出简要解题思路（不直接给答案）

输出 JSON：
{
  "subject": "学科",
  "question_type": "题目类型",
  "question_text": "完整的题目文本",
  "key_points": ["知识点1", "知识点2"],
  "approach": "简要解题思路，50字以内",
  "difficulty": "简单/中等/困难"
}
只输出 JSON。"""

VISION_ANALYZE_PROMPT = """你是一个教育 AI。请分析这张图片并从学习角度回答以下问题：
1. 图片主要内容是什么？
2. 和学习/教育有什么关系？
3. 有什么值得注意的细节？

用中文回答，简洁明了，50字以内。"""


class VisionService:
    """视觉理解服务"""

    UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

    @classmethod
    def _image_to_base64(cls, image_path: str) -> str:
        """读取图片文件并转为 base64"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        with open(path, "rb") as f:
            img_data = f.read()

        # 自动判断 MIME 类型
        ext = path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(img_data).decode()}"

    @classmethod
    def _call_vision(
        cls, image_base64: str, prompt: str, system_prompt: str = "你是一个教育 AI。"
    ) -> str:
        """调用支持视觉的 LLM 模型分析图片"""
        try:
            model = settings.text_reasoning_model  # gpt-4o 等视觉模型

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_base64},
                        },
                    ],
                },
            ]

            import litellm
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Vision LLM 调用失败: {e}")
            raise

    @classmethod
    def _extract_json(cls, text: str) -> dict[str, Any]:
        """从 LLM 回复提取 JSON"""
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    @classmethod
    def save_upload(cls, file_data: bytes, filename: str) -> str:
        """保存上传文件，返回本地路径"""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        import uuid
        safe_name = f"{uuid.uuid4().hex[:12]}_{filename}"
        save_path = cls.UPLOAD_DIR / safe_name
        with open(save_path, "wb") as f:
            f.write(file_data)
        return str(save_path)

    @classmethod
    def ocr(cls, image_path: str) -> dict[str, Any]:
        """OCR 识别图片文字"""
        try:
            b64 = cls._image_to_base64(image_path)
            raw = cls._call_vision(b64, OCR_PROMPT)
            result = cls._extract_json(raw)
            if result:
                return result
            return {"text": raw, "language": "unknown", "has_formula": False, "formula_text": ""}
        except Exception as e:
            logger.error(f"OCR 失败: {e}")
            return {"text": "", "language": "unknown", "has_formula": False, "formula_text": "", "error": str(e)}

    @classmethod
    def understand_problem(cls, image_path: str) -> dict[str, Any]:
        """理解图片中的题目"""
        try:
            b64 = cls._image_to_base64(image_path)
            raw = cls._call_vision(b64, PROBLEM_UNDERSTAND_PROMPT)
            result = cls._extract_json(raw)
            if result:
                return result
            return {"subject": "未知", "question_text": raw[:200], "key_points": [], "difficulty": "未知"}
        except Exception as e:
            logger.error(f"题目理解失败: {e}")
            return {"subject": "未知", "error": str(e)}

    @classmethod
    def analyze_image(cls, image_path: str) -> dict[str, Any]:
        """通用图片分析"""
        try:
            b64 = cls._image_to_base64(image_path)
            raw = cls._call_vision(b64, VISION_ANALYZE_PROMPT)
            return {"description": raw[:200]}
        except Exception as e:
            logger.error(f"图片分析失败: {e}")
            return {"description": "", "error": str(e)}


# 全局实例
vision_service = VisionService()
