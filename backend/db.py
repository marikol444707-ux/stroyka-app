"""Database connection and SQL paging helpers."""

from typing import Optional
import os

import psycopg2

from backend import config  # Loads backend/.env before DB_CONFIG is built.


DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "stroyka"),
    "user": os.getenv("DB_USER", "nikolas"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn


def limit_offset_sql(limit: Optional[int] = None, offset: int = 0):
    if limit is None:
        return "", []
    try:
        limit_value = int(limit)
    except Exception:
        limit_value = 100
    try:
        offset_value = int(offset or 0)
    except Exception:
        offset_value = 0
    limit_value = max(1, min(limit_value, 500))
    offset_value = max(0, min(offset_value, 100000))
    return " LIMIT %s OFFSET %s", [limit_value, offset_value]
