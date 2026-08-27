from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

from backend.db import DB_CONFIG


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> URL:
    port = DB_CONFIG.get("port")
    try:
        port = int(port) if port else None
    except (TypeError, ValueError):
        port = None
    return URL.create(
        "postgresql+psycopg2",
        username=DB_CONFIG.get("user") or None,
        password=DB_CONFIG.get("password") or None,
        host=DB_CONFIG.get("host") or None,
        port=port,
        database=DB_CONFIG.get("dbname") or None,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        _database_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
