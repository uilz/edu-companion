"""
PostgreSQL 数据库层

连接池 + 建表 + 仓库方法。
pgvector 依赖可选（未安装时向量字段降级为 bytea）。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# 从 config/.env 加载环境变量
_env_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path), override=False)

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
        return cls._instance

    def _init_pool(self) -> None:
        self._pool = pool.ThreadedConnectionPool(
            minconn=2, maxconn=10,
            dsn=self._conn_str,
        )
        logger.info("PostgreSQL 连接池已创建 (min=2, max=10)")

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
