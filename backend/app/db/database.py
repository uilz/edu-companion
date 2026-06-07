"""
PostgreSQL 数据库层 v2.0

连接池 + 建表 + 仓库方法。
pgvector 依赖可选（未安装时向量字段降级为 bytea）。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()  # 从 .env 加载环境变量

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# ── 配置 ──

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "edu_companion"),
    "user": os.environ.get("DB_USER", "companion"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
}

if not DB_CONFIG["password"]:
    logger.warning(
        "⚠️  DB_PASSWORD 未设置！数据库连接可能失败。"
        "请在 .env 或环境变量中设置 DB_PASSWORD。"
    )

# ── 建表 SQL ──

SCHEMA_SQL = """


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
-- 兼容旧表（缺少 skill_id 列的场景）
DO $$ BEGIN
    ALTER TABLE questions ADD COLUMN IF NOT EXISTS skill_id TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

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
    summary         TEXT DEFAULT '',
    expires_at      TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    indexed_at      TIMESTAMP
);
-- 兼容旧表
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS summary TEXT DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 所属层级
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS level TEXT DEFAULT 'partition';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS parent_id TEXT DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 标签字段
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS tags_json JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 软删除（回收站）
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 文件夹类型
DO $$ BEGIN
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS is_folder BOOLEAN DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

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
    indexing_status TEXT DEFAULT 'pending',
    heading_path    TEXT DEFAULT '',
    embedding       DOUBLE PRECISION[]
);
-- 兼容旧表（已存在的表加列）
DO $$ BEGIN
    ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS heading_path TEXT DEFAULT '';
    ALTER TABLE material_chunks ADD COLUMN IF NOT EXISTS embedding DOUBLE PRECISION[];
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 资料目录树（TOC）
CREATE TABLE IF NOT EXISTS material_toc (
    toc_id          TEXT PRIMARY KEY,
    material_id     TEXT NOT NULL,
    parent_toc_id   TEXT,
    level           INTEGER NOT NULL DEFAULT 1,
    heading         TEXT NOT NULL DEFAULT '',
    chunk_start     INTEGER DEFAULT 0,
    chunk_end       INTEGER DEFAULT 0,
    page_start      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_toc_material ON material_toc(material_id);
CREATE INDEX IF NOT EXISTS idx_toc_parent ON material_toc(parent_toc_id);


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
        """通过 Alembic 执行数据库迁移"""
        try:
            from alembic.config import Config
            from alembic import command
            from pathlib import Path

            alembic_cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "alembic.ini"))
            alembic_cfg.set_main_option("sqlalchemy.url", self._conn_str.replace(
                "dbname=", "postgresql+psycopg2://localhost/?dbname="
            ) if "postgresql+" not in self._conn_str else self._conn_str)

            # 用 app.db.database 的实际连接参数
            from app.db.database import DB_CONFIG
            url = (
                f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
                f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
            )
            alembic_cfg.set_main_option("sqlalchemy.url", url)

            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Alembic 迁移完成 (head)")
        except Exception as e:
            logger.warning("Alembic 迁移失败，回退到原始 SQL: %s", e)
            self._migrate_raw()

    def _migrate_raw(self) -> None:
        """回退迁移 — 使用原始 SQL 建表"""
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute(SCHEMA_SQL)

            from pathlib import Path
            for sql_file in ["conversation_schema.sql", "cognitive_schema.sql", "learning_schema.sql"]:
                sql_path = Path(__file__).parent / sql_file
                if sql_path.exists():
                    with open(sql_path) as f:
                        cur.execute(f.read())

            conn.commit()
            cur.close()
            self.put_conn(conn)
            logger.info("✅ 原始 SQL 迁移完成")
        except Exception as e:
            logger.error("原始 SQL 迁移失败: %s", e)
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
            conn.commit()  # 清除只读事务，防止连接池残留导致后续读不到新数据
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            self.put_conn(conn)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            conn.commit()  # 清除只读事务
            return [dict(r) for r in cur.fetchall()]
        except Exception:
            conn.rollback()
            raise
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

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """批量执行同一 SQL — 单次往返 (H4 性能优化)"""
        if not params_list:
            return
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            cur.executemany(sql, params_list)
            conn.commit()
        finally:
            cur.close()
            self.put_conn(conn)

    def execute_batch(self, operations: list[tuple[str, tuple]]) -> None:
        """事务内批量执行多条不同 SQL — 单次往返"""
        if not operations:
            return
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            for sql, params in operations:
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


def get_db_pool_stats() -> dict | None:
    """获取连接池统计（用于健康检查）"""
    global _db
    if _db is None or _db._pool is None:
        return None
    try:
        return {
            "total": _db._pool._maxsize,
            "available": _db._pool._pool.qsize(),
            "used": _db._pool._maxsize - _db._pool._pool.qsize(),
        }
    except Exception:
        return None
