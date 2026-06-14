"""
资料解析服务 — MarkItDown 引擎

支持格式（由 MarkItDown 提供）：
  PDF, DOCX, PPTX, XLSX, 图片(OCR), 音频, HTML, CSV, JSON, XML, ZIP

设计原则：
- 统一入口，所有格式走 MarkItDown
- 输出为 Markdown 文本
- 大文件后台异步处理（由调用方控制）
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MaterialParser:
    """基于 MarkItDown 的统一文件解析器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".pptx", ".xlsx",
        ".md", ".txt", ".html", ".htm",
        ".csv", ".json", ".xml",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".mp3", ".wav", ".m4a", ".ogg",
        ".zip",
    }

    def __init__(self):
        self._md = None  # 延迟加载

    def _get_md(self):
        if self._md is None:
            from markitdown import MarkItDown
            self._md = MarkItDown()
        return self._md

    def parse(self, file_path: str, file_type: str = "") -> str:
        """
        解析文件为 Markdown。

        参数:
            file_path: 文件路径
            file_type: 文件类型（备用，从扩展名自动判断）

        返回:
            Markdown 文本。解析失败返回空字符串。
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("文件不存在: %s", file_path)
            return ""

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.warning("不支持的文件格式: %s (扩展名: %s)", file_path, ext)
            return ""

        try:
            md = self._get_md()
            result = md.convert(file_path)
            text = result.markdown or ""
            logger.info("MarkItDown 解析完成: %s → %d chars", path.name, len(text))
            return text
        except Exception as e:
            logger.error("MarkItDown 解析失败: %s — %s", file_path, e)
            return ""

    def get_page_count(self, file_path: str) -> int:
        """估算页数（用于判定是否建 TOC）"""
        path = Path(file_path)
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                import fitz
                doc = fitz.open(file_path)
                count = doc.page_count
                doc.close()
                return count
        except ImportError:
            logger.debug("pymupdf 未安装，无法获取 PDF 页数")
        except Exception as e:
            logger.debug("获取 PDF 页数失败: %s", e)
        return 0


# 全局实例
material_parser = MaterialParser()
