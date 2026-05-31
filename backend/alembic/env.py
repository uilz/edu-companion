"""
Alembic env.py — 从 app.db.database 读取连接配置

本项目不使用 SQLAlchemy ORM，因此：
- 连接 URL 从 app.db.database.DB_CONFIG 动态获取
- 迁移脚本手写 SQL（不依赖 ORM MetaData autogenerate）
"""

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# 确保 app 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import DB_CONFIG

config = context.config

# 动态构建 URL（覆盖 alembic.ini 中的静态值）
db_url = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = None  # 不使用 ORM autogenerate


def run_migrations_offline() -> None:
    """Offline 模式（生成 SQL 脚本）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online 模式（直接连库执行）"""
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
