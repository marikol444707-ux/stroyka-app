import unittest

from backend.features.company_messages.legacy_report import (
    build_legacy_message_report,
    run_legacy_message_report,
)


class FakeCursor:
    def __init__(self, counts, rows):
        self.counts = counts
        self.rows = list(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.counts

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.cursor_factory = None
        self.session_calls = []
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self.cursor_value

    def commit(self):
        raise AssertionError("dry-run report must not commit")

    def close(self):
        self.closed = True


class LegacyMessageReportTests(unittest.TestCase):
    def test_classifies_candidates_without_message_content(self):
        cursor = FakeCursor(
            {"scoped_rows": 3, "legacy_rows": 5},
            (
                {
                    "message_id": 10,
                    "author_id": 21,
                    "author_found": True,
                    "legacy_company_id": 1,
                    "active_company_ids": [1],
                },
                {
                    "message_id": 11,
                    "author_id": 22,
                    "author_found": True,
                    "legacy_company_id": 1,
                    "active_company_ids": [1, 2],
                },
                {
                    "message_id": 12,
                    "author_id": None,
                    "author_found": False,
                    "legacy_company_id": None,
                    "active_company_ids": [],
                },
                {
                    "message_id": 13,
                    "author_id": 404,
                    "author_found": False,
                    "legacy_company_id": None,
                    "active_company_ids": [],
                },
                {
                    "message_id": 14,
                    "author_id": 31,
                    "author_found": True,
                    "legacy_company_id": None,
                    "active_company_ids": [1],
                },
            ),
        )

        report = build_legacy_message_report(cursor)

        self.assertEqual(report["summary"], {
            "scopedRows": 3,
            "legacyRows": 5,
            "ready": 1,
            "ambiguous": 1,
            "unresolved": 3,
        })
        self.assertFalse(report["readyForBackfill"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(
            [item["status"] for item in report["candidates"]],
            ["ready", "ambiguous", "unresolved", "unresolved", "unresolved"],
        )
        self.assertEqual(report["candidates"][0]["proposedCompanyId"], 1)
        self.assertIsNone(report["candidates"][1]["proposedCompanyId"])
        self.assertEqual(report["candidates"][1]["activeCompanyIds"], [1, 2])
        self.assertEqual(report["candidates"][2]["reason"], "missing_author")
        self.assertEqual(report["candidates"][3]["reason"], "author_not_found")
        self.assertEqual(report["candidates"][4]["reason"], "missing_legacy_company")
        self.assertNotIn("text", str(report).lower())
        self.assertTrue(all(call[0].upper().startswith("SELECT ") for call in cursor.calls))

    def test_ready_report_accepts_single_legacy_company_source(self):
        cursor = FakeCursor(
            {"scoped_rows": 2, "legacy_rows": 1},
            ({
                "message_id": 20,
                "author_id": 30,
                "author_found": True,
                "legacy_company_id": 4,
                "active_company_ids": [],
            },),
        )

        report = build_legacy_message_report(cursor)

        self.assertTrue(report["readyForBackfill"])
        self.assertEqual(report["summary"]["ready"], 1)
        self.assertEqual(report["candidates"][0]["reason"], "legacy_company_only")
        self.assertEqual(report["candidates"][0]["proposedCompanyId"], 4)

    def test_runner_forces_read_only_session_and_closes_resources(self):
        cursor = FakeCursor({"scoped_rows": 0, "legacy_rows": 0}, ())
        connection = FakeConnection(cursor)

        report = run_legacy_message_report(lambda: connection)

        self.assertTrue(report["readyForBackfill"])
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_count_mismatch_fails_closed_even_when_candidates_are_ready(self):
        cursor = FakeCursor(
            {"scoped_rows": 0, "legacy_rows": 2},
            ({
                "message_id": 30,
                "author_id": 40,
                "author_found": True,
                "legacy_company_id": 5,
                "active_company_ids": [5],
            },),
        )

        report = build_legacy_message_report(cursor)

        self.assertFalse(report["reportConsistent"])
        self.assertFalse(report["readyForBackfill"])
        self.assertEqual(report["summary"]["ready"], 1)


if __name__ == "__main__":
    unittest.main()
