"""
SQLAlchemy 2.0 会话管理

与 backend/app/infrastructure/db/database.py 读取相同环境变量，
提供同步 Session 工厂，供 repository 层使用。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_env_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path), override=True)

DB_NAME = os.environ.get("DB_NAME", "edu_companion")
DB_USER = os.environ.get("DB_USER", "companion")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@contextmanager
def get_db_session() -> Session:
    """获取一个 SQLAlchemy Session 的上下文管理器。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
