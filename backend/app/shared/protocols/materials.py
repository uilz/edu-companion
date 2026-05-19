"""
Material Service Protocol — 资料管理模块对外契约
"""

from __future__ import annotations

from typing import Protocol


class MaterialService(Protocol):
    """资料管理模块对外契约"""

    async def upload(
        self,
        file_path: str,
        user_id: str,
        partition_id: str | None = None,
    ) -> dict:
        """上传资料"""
        ...

    async def parse(
        self,
        material_id: str,
    ) -> dict:
        """解析资料内容"""
        ...

    async def index(
        self,
        material_id: str,
    ) -> None:
        """建立资料向量索引"""
        ...

    async def search(
        self,
        query: str,
        partition_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """搜索资料"""
        ...

    async def get_chunks(
        self,
        material_id: str,
    ) -> list[dict]:
        """获取资料分块"""
        ...

    async def generate_questions(
        self,
        material_id: str,
        count: int = 5,
    ) -> list[dict]:
        """根据资料出题"""
        ...

    async def delete(
        self,
        material_id: str,
    ) -> None:
        """删除资料"""
        ...
