"""Verify QA transaction enforcement on the dedicated throwaway CI database.

Never run against a shared, QA, or production database. No schema changes are
made: the attempted DDL is rejected by PostgreSQL's READ ONLY transaction.
"""
import os
import re
import unittest

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

_ENABLED = os.getenv("COMPANY_CONTEXT_RUN_POSTGRES_INTEGRATION") == "1"
_DSN = os.getenv("COMPANY_CONTEXT_TEST_DATABASE_URL", "")


@unittest.skipUnless(_ENABLED and _DSN, "requires dedicated CI PostgreSQL database")
class QAReadOnlyPostgresTest(unittest.TestCase):
    def test_real_postgres_rejects_writes_during_qa_auth_transaction(self):
        name = parse_dsn(_DSN).get("dbname", "")
        if not re.fullmatch(r"stroyka_company_context_test(?:_[a-z0-9_]+)?", name):
            raise RuntimeError("refusing non-dedicated QA auth test database")
        conn = psycopg2.connect(_DSN)
        try:
            self.assertEqual(conn.get_dsn_parameters().get("dbname"), name)
            conn.autocommit = True  # mirror backend.db.get_db()
            conn.autocommit = False  # the actual QA endpoint fix
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SHOW transaction_read_only")
                self.assertEqual(cur.fetchone()["transaction_read_only"], "on")
                with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
                    cur.execute("CREATE TABLE public.__jev_qa_readonly_forbidden (id integer)")
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
