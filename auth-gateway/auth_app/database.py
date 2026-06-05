"""
认证网关独立数据库连接管理
不依赖后端任何模块
"""
from __future__ import annotations

import os
import psycopg2
import psycopg2.pool
from typing import Optional

# 自动加载 .env 文件
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

_db_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None


def get_db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "edu_companion"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    }


def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _db_pool
    if _db_pool is None:
        cfg = get_db_config()
        _db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=int(os.getenv("DB_POOL_MIN", "2")),
            maxconn=int(os.getenv("DB_POOL_MAX", "5")),
            **cfg,
        )
    return _db_pool


def get_db():
    """获取数据库连接（自动释放）"""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


class DB:
    """简化数据库操作类"""

    def __init__(self):
        self._pool = get_pool()

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    def execute(self, sql: str, params=None):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur
        finally:
            self._put_conn(conn)

    def fetchone(self, sql: str, params=None):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            if row:
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))
            return None
        finally:
            self._put_conn(conn)

    def fetchall(self, sql: str, params=None):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            self._put_conn(conn)


_db = DB()


def get_db_instance() -> DB:
    return _db
