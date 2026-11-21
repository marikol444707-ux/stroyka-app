import importlib.util
import unittest
from pathlib import Path


REPORT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "report-room-ownership-backfill.py"
spec = importlib.util.spec_from_file_location("report_room_ownership_backfill", REPORT_PATH)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class FakeConnection:
    def __init__(self):
        self.readonly = None
        self.closed = False

    def set_session(self, readonly=None, autocommit=None):
        self.readonly = readonly

    def cursor(self):
        return FakeCursor()

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append(sql)

    def fetchall(self):
        if "information_schema.columns" in self.statements[-1]:
            return []
        return []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RoomOwnershipReportTest(unittest.TestCase):
    def test_report_refuses_to_run_without_an_explicit_flag(self):
        self.assertEqual(report.main([]), 2)

    def test_report_rejects_any_mode_other_than_dry_run(self):
        self.assertEqual(report.main(["--apply"]), 2)

    def test_dry_run_reads_and_does_not_keep_the_connection(self):
        connection = FakeConnection()
        original = report.psycopg2.connect
        report.psycopg2.connect = lambda **_kwargs: connection
        try:
            import os
            previous = os.environ.get("ROOM_OWNERSHIP_REPORT")
            os.environ["ROOM_OWNERSHIP_REPORT"] = "1"
            os.environ.setdefault("DB_NAME", "room_ownership_test")
            os.environ.setdefault("DB_USER", "report")
            code = report.main(["--dry-run"])
        finally:
            report.psycopg2.connect = original
            if previous is None:
                os.environ.pop("ROOM_OWNERSHIP_REPORT", None)
            else:
                os.environ["ROOM_OWNERSHIP_REPORT"] = previous
        self.assertEqual(code, 0)
        self.assertTrue(connection.readonly)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
