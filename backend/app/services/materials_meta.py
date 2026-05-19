"""
资料元数据管理服务
P5: 资料→分区归属→分支引用

数据存储: ~/.companion/uploads/materials_meta.json
结构: {material_id: {partition_id, file_name, file_type, ...}}
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

META_DIR = Path.home() / ".companion" / "uploads"
META_FILE = META_DIR / "materials_meta.json"

# 默认未分类分区 ID
UNCATEGORIZED_PARTITION_ID = "__uncategorized__"


class MaterialsMetaStore:
    """材料元数据 JSON 存储"""

    def __init__(self):
        self._cache: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        """加载元数据（带缓存）"""
        if self._cache is not None:
            return self._cache
        META_DIR.mkdir(parents=True, exist_ok=True)
        if META_FILE.exists():
            try:
                self._cache = json.loads(META_FILE.read_text())
            except (json.JSONDecodeError, Exception):
                self._cache = {}
        else:
            self._cache = {}
        return self._cache

    def _save(self):
        """持久化到磁盘"""
        if self._cache is not None:
            META_FILE.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False))

    def get(self, material_id: str) -> dict | None:
        return self._load().get(material_id)

    def get_all(self) -> dict[str, dict]:
        return dict(self._load())

    def set(self, material_id: str, meta: dict):
        data = self._load()
        data[material_id] = meta
        self._save()

    def update(self, material_id: str, **kwargs):
        data = self._load()
        if material_id in data:
            data[material_id].update(kwargs)
        else:
            data[material_id] = kwargs
        self._save()

    def delete(self, material_id: str):
        data = self._load()
        data.pop(material_id, None)
        self._save()

    def list_by_partition(self, partition_id: str) -> list[dict]:
        """获取某分区下的所有资料"""
        result = []
        for mid, meta in self._load().items():
            pid = meta.get("partition_id", UNCATEGORIZED_PARTITION_ID)
            if pid == partition_id:
                result.append({"material_id": mid, **meta})
        return sorted(result, key=lambda x: x.get("created_at", ""), reverse=True)

    def search(self, query: str, partition_id: str | None = None) -> list[dict]:
        """按文件名搜索资料"""
        q = query.lower()
        result = []
        for mid, meta in self._load().items():
            if q in meta.get("file_name", "").lower():
                pid = meta.get("partition_id", UNCATEGORIZED_PARTITION_ID)
                if partition_id is None or pid == partition_id:
                    result.append({"material_id": mid, **meta})
        return sorted(result, key=lambda x: x.get("created_at", ""), reverse=True)

    def ensure_indexed(self) -> int:
        """
        扫描 uploads 目录，为所有未注册的文件自动创建元数据。
        归入「未分类」默认分区。
        返回新注册的文件数。
        """
        data = self._load()
        count = 0

        for fname in sorted(os.listdir(META_DIR)):
            fpath = META_DIR / fname
            if not fpath.is_file():
                continue
            if fname == "materials_meta.json":
                continue

            # 从文件名提取 material_id（前36位UUID）
            material_id = fname[:36] if len(fname) > 36 else os.path.splitext(fname)[0]
            if material_id in data:
                continue

            ext = os.path.splitext(fname)[1].lower()
            file_type_map = {
                ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx",
                ".md": "markdown", ".txt": "text",
                ".mp3": "mp3", ".wav": "wav", ".m4a": "m4a",
                ".ogg": "ogg", ".flac": "flac", ".aac": "aac",
                ".jpg": "jpg", ".jpeg": "jpg", ".png": "png",
                ".webp": "webp", ".bmp": "bmp",
            }

            data[material_id] = {
                "file_name": fname[37:] if len(fname) > 37 else fname,
                "file_type": file_type_map.get(ext, "unknown"),
                "file_size": fpath.stat().st_size,
                "partition_id": UNCATEGORIZED_PARTITION_ID,
                "purpose": "session",
                "status": "stored",
                "chunk_count": 0,
                "skills_covered": [],
                "created_at": datetime.fromtimestamp(fpath.stat().st_mtime).isoformat(),
                "indexed_at": None,
                "expires_at": None,
            }
            count += 1

        if count > 0:
            self._cache = data
            self._save()
            logger.info(f"materials_meta: 注册了 {count} 个新文件到「未分类」")

        return count

    def migrate_to_partition(self, material_id: str, partition_id: str):
        """将资料移动到指定分区"""
        data = self._load()
        if material_id in data:
            data[material_id]["partition_id"] = partition_id
            self._save()

    def get_stats_by_partition(self) -> dict[str, int]:
        """统计各分区的资料数量"""
        stats: dict[str, int] = {}
        for mid, meta in self._load().items():
            pid = meta.get("partition_id", UNCATEGORIZED_PARTITION_ID)
            stats[pid] = stats.get(pid, 0) + 1
        return stats


# 全局实例
materials_meta = MaterialsMetaStore()
