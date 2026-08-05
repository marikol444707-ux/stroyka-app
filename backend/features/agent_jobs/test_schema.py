import unittest
from pathlib import Path

from backend.features.agent_jobs.schema import ensure_agent_jobs_schema


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql):
        self.calls.append(" ".join(sql.split()))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class AgentJobSchemaTests(unittest.TestCase):
    def test_schema_is_tenant_scoped_idempotent_and_worker_ready(self):
        connection = FakeConnection()

        ensure_agent_jobs_schema(lambda: connection)

        sql = "\n".join(connection.cursor_value.calls)
        self.assertIn("CREATE TABLE IF NOT EXISTS agent_jobs", sql)
        self.assertIn("company_id INT NOT NULL", sql)
        self.assertIn("project_id INT", sql)
        self.assertIn("project_scope_id INT GENERATED ALWAYS AS (COALESCE(project_id,0)) STORED", sql)
        self.assertIn("idempotency_key VARCHAR(180) NOT NULL", sql)
        self.assertIn("correlation_id VARCHAR(80) NOT NULL", sql)
        self.assertIn("attempts INT NOT NULL DEFAULT 0", sql)
        self.assertIn("max_attempts INT NOT NULL DEFAULT 3", sql)
        self.assertIn("locked_at TIMESTAMP", sql)
        self.assertIn("locked_by VARCHAR(120)", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS lease_token VARCHAR(64)", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMP", sql)
        self.assertIn(
            "UNIQUE (company_id, project_scope_id, job_type, idempotency_key)",
            sql,
        )
        self.assertIn("idx_agent_jobs_claim", sql)
        self.assertIn("idx_agent_jobs_lease", sql)
        self.assertIn("idx_agent_jobs_owner", sql)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_backend_initializes_agent_jobs_after_core_schema(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        source = " ".join(main_path.read_text(encoding="utf-8").split())

        self.assertIn("from backend.features.agent_jobs.schema import ensure_agent_jobs_schema", source)
        self.assertIn("init_db() ensure_agent_jobs_schema(get_db)", source)


if __name__ == "__main__":
    unittest.main()
