"""
资料索引系统 — 数据库迁移脚本 v1.1

运行: python -m app.db.migrate_materials
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

MIGRATION_V1 = """
-- 资料表
CREATE TABLE IF NOT EXISTS materials (
    material_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    storage_path TEXT,
    purpose TEXT NOT NULL DEFAULT 'permanent',
    status TEXT NOT NULL DEFAULT 'uploaded',
    chunk_count INT NOT NULL DEFAULT 0,
    question_count INT NOT NULL DEFAULT 0,
    skills_covered TEXT[] DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ
);

-- 资料分块表 (带 embedding 向量)
CREATE TABLE IF NOT EXISTS material_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    material_id UUID NOT NULL REFERENCES materials(material_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    image_urls TEXT[] DEFAULT '{}',
    chunk_type TEXT NOT NULL DEFAULT 'text',
    skill_ids TEXT[] DEFAULT '{}',
    bloom_level TEXT DEFAULT 'understand',
    difficulty_estimate FLOAT DEFAULT 0.5,
    embedding vector(768),
    source_file TEXT NOT NULL,
    page_number INT,
    chunk_index INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    indexing_status TEXT NOT NULL DEFAULT 'done'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_materials_user ON materials(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_materials_purpose ON materials(user_id, purpose);
CREATE INDEX IF NOT EXISTS idx_chunks_material ON material_chunks(material_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_user ON material_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON material_chunks(chunk_type);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_chunks_text_search 
    ON material_chunks USING GIN (to_tsvector('simple', text));

-- 审核表
CREATE TABLE IF NOT EXISTS chunk_review_queue (
    id SERIAL PRIMARY KEY,
    chunk_id UUID REFERENCES material_chunks(chunk_id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE
);
"""

# v1.1 新增字段（对已有表做 ALTER）
MIGRATION_V1_1 = """
-- 添加 purpose 字段
ALTER TABLE materials ADD COLUMN IF NOT EXISTS purpose TEXT NOT NULL DEFAULT 'permanent';

-- 添加 storage_path 字段
ALTER TABLE materials ADD COLUMN IF NOT EXISTS storage_path TEXT;

-- 添加 expires_at 字段
ALTER TABLE materials ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- 更新已有记录的 storage_path（如果存在 UPLOAD_DIR 下的文件）
-- 这个需要应用层处理，SQL不做推断
"""


async def run_migration(database_url: str | None = None) -> None:
    """执行迁移"""
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            logger.warning("DATABASE_URL not set, skipping migration")
            return

    import asyncpg
    conn = await asyncpg.connect(database_url)
    try:
        # 启用 pgvector
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # 执行 v1 建表
        await conn.execute(MIGRATION_V1)

        # 执行 v1.1 升级
        try:
            await conn.execute(MIGRATION_V1_1)
        except Exception as e:
            logger.warning(f"v1.1 迁移部分失败（可能已执行过）: {e}")

        logger.info("✅ 资料索引表迁移完成 (v1.1)")
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migration())
