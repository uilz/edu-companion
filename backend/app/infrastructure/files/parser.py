"""
文件解析服务 — MarkItDown 引擎 + catdoc 辅助 (旧版 .doc)

支持格式:
  PDF, DOCX, PPTX, XLSX, 图片(OCR), 音频, HTML, CSV, JSON, XML, ZIP
  旧版 .doc → catdoc (子进程)
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class MaterialParser:
    """基于 MarkItDown + catdoc 的统一文件解析器"""

    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
        ".md", ".txt", ".html", ".htm",
        ".csv", ".json", ".xml",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".svg", ".ico", ".tiff", ".tif", ".avif",
        ".mp3", ".wav", ".m4a", ".ogg",
        ".zip",
        # 视频
        ".mp4", ".avi", ".mov", ".mkv", ".webm",
        # 代码
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".cpp", ".c", ".h", ".hpp",
        ".sql", ".yaml", ".yml", ".toml", ".ini",
        ".rs", ".go", ".rb", ".php", ".swift",
        ".kt", ".scala", ".r", ".lua", ".sh",
        ".vue", ".svelte", ".dart", ".gradle", ".cmake",
        ".tex", ".m", ".mm", ".pl", ".pm",
        # 流程图/思维导图
        ".drawio", ".xmind", ".opml",
    }

    def __init__(self):
        self._md = None  # 延迟加载

    def _get_md(self):
        if self._md is None:
            from markitdown import MarkItDown
            self._md = MarkItDown()
        return self._md

    def parse(self, file_path: str, file_type: str = "") -> str:
        path = Path(file_path)
        if not path.exists():
            logger.error("文件不存在: %s", file_path)
            return ""

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.warning("不支持的文件格式: %s (扩展名: %s)", file_path, ext)
            return ""

        # 旧版 .doc → catdoc 提取文本
        if ext == ".doc":
            return self._parse_doc(file_path)

        try:
            md = self._get_md()
            result = md.convert(file_path)
            text = result.markdown or ""
            logger.info("MarkItDown 解析完成: %s → %d chars", path.name, len(text))
            return text
        except Exception as e:
            logger.error("MarkItDown 解析失败: %s — %s", file_path, e)
            return ""

    def _parse_doc(self, file_path: str) -> str:
        """用 catdoc 提取旧版 .doc 文件的纯文本"""
        path = Path(file_path)
        try:
            result = subprocess.run(
                ["catdoc", file_path],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                logger.info("catdoc 解析完成: %s → %d chars", path.name, len(text))
                return text
            else:
                logger.error("catdoc 失败: %s — %s", file_path, result.stderr.strip())
                return ""
        except FileNotFoundError:
            logger.error("catdoc 未安装，无法解析 .doc 文件: %s", file_path)
            return ""
        except subprocess.TimeoutExpired:
            logger.error("catdoc 超时: %s", file_path)
            return ""
        except Exception as e:
            logger.error("catdoc 异常: %s — %s", file_path, e)
            return ""

    def get_page_count(self, file_path: str) -> int:
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