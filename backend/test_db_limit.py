import pytest
from backend.db import limit_offset_sql

def test_limit_offset_sql_default_none():
    sql, params = limit_offset_sql(None, 0)
    assert sql.strip().upper().startswith('LIMIT')
    assert params[0] == 200
    assert params[1] == 0
