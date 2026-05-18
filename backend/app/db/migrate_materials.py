"""
资料索引系统 — 数据库迁移脚本

在 PostgreSQL (pgvector) 中创建 materials 和 material_chunks 表。
运行: python -m app.db.migrate_materials
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

MIGRATION_SQL = """
-- 资料表
CREATE TABLE IF NOT EXISTS materials (
    material_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    chunk_count INT NOT NULL DEFAULT 0,
    question_count INT NOT NULL DEFAULT 0,
    skills_covered TEXT[] DEFAULT '{}',
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
CREATE INDEX IF NOT EXISTS idx_chunks_material ON material_chunks(material_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_user ON material_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON material_chunks(chunk_type);

-- pgvector 索引 (IVFFlat，用于近似最近邻搜索)
-- 先确保有足够数据再创建（至少 1000 条）
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
--     ON material_chunks USING ivfflat (embedding vector_cosine_ops) 
--     WITH (lists = 100);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_chunks_text_search 
    ON material_chunks USING GIN (to_tsvector('simple', text));

-- 审核表（可选，用于标记需要人工审核的chunk）
CREATE TABLE IF NOT EXISTS chunk_review_queue (
    id SERIAL PRIMARY KEY,
    chunk_id UUID REFERENCES material_chunks(chunk_id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE
);
"""


async def run_migration(database_url: str | None = None) -> None:
    """执行迁移"""
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            logger.warning("DATABASE_URL not set, skipping material tables migration")
            return

    import asyncpg
    conn = await asyncpg.connect(database_url)
    try:
        # 启用 pgvector 扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # 执行建表
        await conn.execute(MIGRATION_SQL)
        logger.info("✅ 资料索引表迁移完成: materials + material_chunks")
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migration())
