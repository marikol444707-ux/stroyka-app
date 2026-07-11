import os
import subprocess
import sys
import unittest
from pathlib import Path

from backend.features.estimate_changes.ownership_report import (
    build_estimate_change_ownership_report,
    run_estimate_change_ownership_report,
)


class FakeCursor:
    def __init__(self, result_sets):
        self.result_sets = [list(rows) for rows in result_sets]
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.result_sets.pop(0) if self.result_sets else []

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
        raise AssertionError("ownership audit must not commit")

    def close(self):
        self.closed = True


class EstimateChangeOwnershipReportTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-pycache"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from features.estimate_changes.ownership_report import "
                "build_estimate_change_ownership_report",
            ],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_classifies_strong_ready_and_review_owners_without_business_content(self):
        cursor = FakeCursor((
            (
                {"column_name": "id"},
                {"column_name": "project_name"},
                {"column_name": "estimate_id"},
                {"column_name": "included_in_estimate_id"},
                {"column_name": "project_id"},
                {"column_name": "company_id"},
            ),
            (
                {"change_id": 1, "project_name": "Alpha", "estimate_id": None, "included_estimate_id": None, "project_id": 10, "company_id": 1},
                {"change_id": 2, "project_name": "Alpha", "estimate_id": 100, "included_estimate_id": None, "project_id": None, "company_id": None},
                {"change_id": 3, "project_name": "Beta", "estimate_id": None, "included_estimate_id": None, "project_id": None, "company_id": None},
                {"change_id": 4, "project_name": "Duplicate", "estimate_id": None, "included_estimate_id": None, "project_id": None, "company_id": None},
                {"change_id": 5, "project_name": "Alpha", "estimate_id": 999, "included_estimate_id": None, "project_id": None, "company_id": None},
                {"change_id": 6, "project_name": "Wrong", "estimate_id": 100, "included_estimate_id": None, "project_id": None, "company_id": None},
                {"change_id": 7, "project_name": "Alpha", "estimate_id": 100, "included_estimate_id": 200, "project_id": None, "company_id": None},
            ),
            (
                {"project_id": 10, "company_id": 1, "project_name": "Alpha"},
                {"project_id": 11, "company_id": 1, "project_name": "Beta"},
                {"project_id": 12, "company_id": 1, "project_name": "Duplicate"},
                {"project_id": 20, "company_id": 2, "project_name": "Duplicate"},
                {"project_id": 22, "company_id": 2, "project_name": "Gamma"},
            ),
            (
                {"estimate_id": 100, "company_id": 1, "project_id": 10, "project_name": "Alpha"},
                {"estimate_id": 200, "company_id": 2, "project_id": 22, "project_name": "Gamma"},
            ),
        ))

        report = build_estimate_change_ownership_report(cursor)

        self.assertEqual(report["columns"], {"companyId": True, "projectId": True})
        self.assertEqual(report["summary"], {
            "totalRows": 7,
            "storedRows": 1,
            "legacyRows": 6,
            "ready": 2,
            "ambiguous": 1,
            "unresolved": 1,
            "mismatched": 2,
        })
        self.assertFalse(report["readyForBackfill"])
        self.assertEqual(report["readyByCompany"], {"1": 2})
        self.assertEqual([row["changeId"] for row in report["readyPreview"]], [2, 3])
        self.assertEqual(
            [(row["changeId"], row["reason"]) for row in report["needsReview"]],
            [
                (4, "project_name_ambiguous"),
                (5, "estimate_not_found"),
                (6, "row_project_name_mismatch"),
                (7, "included_estimate_owner_mismatch"),
            ],
        )
        change_query = cursor.calls[1][0].lower()
        for forbidden in ("description", "notes", "photo_url", "price", "total", "uw.reason"):
            self.assertNotIn(forbidden, change_query)
        self.assertTrue(all(sql.upper().startswith("SELECT ") for sql, _params in cursor.calls))

    def test_report_works_before_owner_columns_exist(self):
        cursor = FakeCursor((
            (
                {"column_name": "id"},
                {"column_name": "project_name"},
                {"column_name": "estimate_id"},
                {"column_name": "included_in_estimate_id"},
            ),
            ({"change_id": 8, "project_name": "Alpha", "estimate_id": None, "included_estimate_id": None, "project_id": None, "company_id": None},),
            ({"project_id": 10, "company_id": 1, "project_name": "Alpha"},),
            (),
        ))

        report = build_estimate_change_ownership_report(cursor)

        self.assertEqual(report["columns"], {"companyId": False, "projectId": False})
        self.assertEqual(report["summary"]["ready"], 1)
        self.assertTrue(report["readyForBackfill"])
        self.assertIn("NULL::INT AS company_id", cursor.calls[1][0])
        self.assertIn("NULL::INT AS project_id", cursor.calls[1][0])
        self.assertNotIn("uw.company_id", cursor.calls[1][0])
        self.assertNotIn("uw.project_id", cursor.calls[1][0])

    def test_runner_forces_read_only_session_and_closes_resources(self):
        cursor = FakeCursor((
            ({"column_name": "id"}, {"column_name": "project_name"}),
            (),
            (),
            (),
        ))
        connection = FakeConnection(cursor)

        report = run_estimate_change_ownership_report(lambda: connection)

        self.assertTrue(report["readyForBackfill"])
        self.assertEqual(connection.session_calls, [{"readonly": True, "autocommit": False}])
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_previews_are_truncated_without_losing_summary_counts(self):
        ready_rows = tuple(
            {
                "change_id": index,
                "project_name": "Alpha",
                "estimate_id": None,
                "included_estimate_id": None,
                "project_id": None,
                "company_id": None,
            }
            for index in range(1, 102)
        )
        review_rows = tuple(
            {
                "change_id": index,
                "project_name": "Missing",
                "estimate_id": None,
                "included_estimate_id": None,
                "project_id": None,
                "company_id": None,
            }
            for index in range(102, 203)
        )
        cursor = FakeCursor((
            ({"column_name": "id"}, {"column_name": "project_name"}),
            ready_rows + review_rows,
            ({"project_id": 10, "company_id": 1, "project_name": "Alpha"},),
            (),
        ))

        report = build_estimate_change_ownership_report(cursor)

        self.assertEqual(report["summary"]["totalRows"], 202)
        self.assertEqual(report["summary"]["ready"], 101)
        self.assertEqual(report["summary"]["unresolved"], 101)
        self.assertEqual(len(report["readyPreview"]), 100)
        self.assertEqual(len(report["needsReview"]), 100)
        self.assertTrue(report["readyPreviewTruncated"])
        self.assertTrue(report["reviewListTruncated"])


if __name__ == "__main__":
    unittest.main()
