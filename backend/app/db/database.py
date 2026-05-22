"""
PostgreSQL 数据库层 v2.0

连接池 + 建表 + 仓库方法。
pgvector 依赖可选（未安装时向量字段降级为 bytea）。
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()  # 从 .env 加载环境变量

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger(__name__)

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ── 配置 ──

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "edu_companion"),
    "user": os.environ.get("DB_USER", "companion"),
    "password": os.environ.get("DB_PASSWORD", "companion123"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
}

# ── 建表 SQL ──

SCHEMA_SQL = """
-- 知识状态
CREATE TABLE IF NOT EXISTS knowledge_states (
    user_id     TEXT NOT NULL,
    skill_id    TEXT NOT NULL,
    p_known     DOUBLE PRECISION DEFAULT 0.0,
    p_learned   DOUBLE PRECISION DEFAULT 0.0,
    p_guess     DOUBLE PRECISION DEFAULT 0.25,
    p_slip      DOUBLE PRECISION DEFAULT 0.1,
    p_transit   DOUBLE PRECISION DEFAULT 0.3,
    attempt_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    mastery_level TEXT DEFAULT '未接触',
    dimensions  JSONB DEFAULT '{}',
    misconception_flags JSONB DEFAULT '[]',
    pseudo_mastery_flags JSONB DEFAULT '[]',
    last_updated TIMESTAMP,
    PRIMARY KEY (user_id, skill_id)
);

-- 题库
CREATE TABLE IF NOT EXISTS questions (
    question_id     TEXT PRIMARY KEY,
    skill_id        TEXT NOT NULL,
    subject         TEXT DEFAULT '',
    bloom_level     TEXT DEFAULT 'understand',
    text            TEXT NOT NULL,
    options_json    JSONB DEFAULT '[]',
    correct_answer  TEXT DEFAULT '',
    explanation     TEXT DEFAULT '',
    hints_json      JSONB DEFAULT '[]',
    difficulty      DOUBLE PRECISION DEFAULT 0.5,
    answer_type     TEXT DEFAULT 'choice',
    source          TEXT DEFAULT 'llm',
    tags_json       JSONB DEFAULT '[]',
    quality_score   DOUBLE PRECISION DEFAULT 0.5,
    usage_count     INTEGER DEFAULT 0,
    avg_correct_rate DOUBLE PRECISION DEFAULT 0.0,
    status          TEXT DEFAULT 'active',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 练习会话
CREATE TABLE IF NOT EXISTS practice_sessions (
    session_id          TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    planned_skills_json JSONB DEFAULT '[]',
    question_ids_json   JSONB DEFAULT '[]',
    current_index       INTEGER DEFAULT 0,
    correct_count       INTEGER DEFAULT 0,
    total_hints_used    INTEGER DEFAULT 0,
    estimated_minutes   INTEGER DEFAULT 30,
    mode                TEXT DEFAULT 'adaptive',
    status              TEXT DEFAULT 'active',
    frustration_level   DOUBLE PRECISION DEFAULT 0.0,
    engagement_level    DOUBLE PRECISION DEFAULT 0.5,
    started_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMP
);

-- 答题记录
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    session_id      TEXT,
    user_answer     TEXT DEFAULT '',
    is_correct      BOOLEAN DEFAULT FALSE,
    time_spent_seconds DOUBLE PRECISION DEFAULT 0.0,
    hints_used      INTEGER DEFAULT 0,
    hint_levels_json JSONB DEFAULT '[]',
    explanation_text TEXT,
    explanation_score DOUBLE PRECISION,
    error_type      TEXT,
    error_subtype   TEXT DEFAULT '',
    misconception   TEXT,
    error_severity  DOUBLE PRECISION DEFAULT 0.0,
    error_suggestion TEXT DEFAULT '',
    bloom_level_attempted TEXT DEFAULT 'understand',
    knowledge_before_json JSONB DEFAULT '{}',
    knowledge_after_json  JSONB DEFAULT '{}',
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    submitted_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 错题本
CREATE TABLE IF NOT EXISTS error_book (
    entry_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    skill_id        TEXT NOT NULL,
    error_type      TEXT,
    misconception   TEXT,
    user_answer     TEXT DEFAULT '',
    correct_answer  TEXT DEFAULT '',
    question_text   TEXT DEFAULT '',
    review_count    INTEGER DEFAULT 0,
    next_review     TIMESTAMP DEFAULT NOW(),
    is_resolved     BOOLEAN DEFAULT FALSE,
    referenced_materials_json JSONB DEFAULT '[]',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 资料表
CREATE TABLE IF NOT EXISTS materials (
    material_id     TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    file_type       TEXT DEFAULT '',
    file_size       INTEGER DEFAULT 0,
    storage_path    TEXT DEFAULT '',
    purpose         TEXT DEFAULT 'session',
    status          TEXT DEFAULT 'uploading',
    chunk_count     INTEGER DEFAULT 0,
    question_count  INTEGER DEFAULT 0,
    skills_covered_json JSONB DEFAULT '[]',
    expires_at      TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    indexed_at      TIMESTAMP
);

-- 资料分块
CREATE TABLE IF NOT EXISTS material_chunks (
    chunk_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    material_id     TEXT NOT NULL,
    text            TEXT DEFAULT '',
    image_urls_json JSONB DEFAULT '[]',
    chunk_type      TEXT DEFAULT 'text',
    skill_ids_json  JSONB DEFAULT '[]',
    bloom_level     TEXT DEFAULT 'understand',
    difficulty_estimate DOUBLE PRECISION DEFAULT 0.5,
    source_file     TEXT DEFAULT '',
    page_number     INTEGER,
    chunk_index     INTEGER DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    indexed_at      TIMESTAMP,
    indexing_status TEXT DEFAULT 'pending'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_ks_user ON knowledge_states(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_skill ON questions(skill_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON practice_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON practice_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user_submitted ON attempts(user_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_errors_user ON error_book(user_id);
CREATE INDEX IF NOT EXISTS idx_materials_user ON materials(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_material ON material_chunks(material_id);
"""


class Database:
    """PostgreSQL 连接池管理器"""

    _instance: Optional["Database"] = None
    _pool: Optional[pool.ThreadedConnectionPool] = None

    def __init__(self) -> None:
        self._conn_str = (
            f"dbname={DB_CONFIG['dbname']} user={DB_CONFIG['user']} "
            f"password={DB_CONFIG['password']} host={DB_CONFIG['host']} "
            f"port={DB_CONFIG['port']}"
        )

    @classmethod
    def get(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_pool()
            cls._instance._migrate()
        return cls._instance

    def _init_pool(self) -> None:
        self._pool = pool.ThreadedConnectionPool(
            minconn=2, maxconn=10,
            dsn=self._conn_str,
        )
        logger.info("PostgreSQL 连接池已创建 (min=2, max=10)")

    def _migrate(self) -> None:
        """执行建表迁移"""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute(SCHEMA_SQL)

            # 对话系统表 (独立SQL文件)
            from pathlib import Path
            conv_sql_path = Path(__file__).parent / "conversation_schema.sql"
            if conv_sql_path.exists():
                with open(conv_sql_path) as f:
                    cur.execute(f.read())

            # CognitiveNode 表 (Phase 6)
            cog_sql_path = Path(__file__).parent / "cognitive_schema.sql"
            if cog_sql_path.exists():
                with open(cog_sql_path) as f:
                    cur.execute(f.read())

            conn.commit()
            cur.close()
            self.put_conn(conn)
            logger.info("数据库表结构已确认")
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")
            raise

    def get_conn(self):
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")
        return self._pool.getconn()

    def put_conn(self, conn) -> None:
        if self._pool:
            self._pool.putconn(conn)

    @asynccontextmanager
    async def cursor(self) -> AsyncIterator[Any]:
        """获取游标的上下文管理器（同步包装）"""
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            self.put_conn(conn)

    # ── 便捷查询方法 ──

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()
            self.put_conn(conn)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
            self.put_conn(conn)

    def execute(self, sql: str, params: tuple = ()) -> None:
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    def insert_returning(self, table: str, data: dict, returning: str = "question_id"
    ) -> Any:
        """插入并返回指定列"""
        conn = self.get_conn()
        try:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(f"%({k})s" for k in data)
            sql = (
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT (question_id) DO UPDATE SET "
                + ", ".join(f"{k} = EXCLUDED.{k}" for k in data if k != "question_id")
                + f" RETURNING {returning}"
            )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, self._serialize(data))
            row = cur.fetchone()
            conn.commit()
            return row[returning] if row else None
        finally:
            cur.close()
            self.put_conn(conn)

    def upsert(self, table: str, data: dict, pk_col: str) -> None:
        """插入或更新"""
        conn = self.get_conn()
        try:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(f"%({k})s" for k in data)
            update_cols = [k for k in data if k != pk_col]
            update_clause = ", ".join(f"{k} = EXCLUDED.{k}" for k in update_cols)
            sql = (
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT ({pk_col}) DO UPDATE SET {update_clause}"
            )
            cur = conn.cursor()
            cur.execute(sql, self._serialize(data))
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    @staticmethod
    def _serialize(data: dict) -> dict:
        """将 list/dict 转为 JSON 字符串"""
        return {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            for k, v in data.items()
        }

    @staticmethod
    def _deserialize(row: dict, json_cols: set[str] | None = None) -> dict:
        """将 JSON 字符串转回 list/dict"""
        if json_cols is None:
            json_cols = {
                "options_json", "hints_json", "tags_json", "planned_skills_json",
                "question_ids_json", "hint_levels_json", "knowledge_before_json",
                "knowledge_after_json", "referenced_materials_json", "dimensions",
                "misconception_flags", "pseudo_mastery_flags", "skills_covered_json",
                "image_urls_json", "skill_ids_json",
            }
        result = {}
        for k, v in row.items():
            if k in json_cols and isinstance(v, str):
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            else:
                result[k] = v
        return result


# ── 全局实例 ──

_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database.get()
    return _db
