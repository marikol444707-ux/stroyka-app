import io
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from backend.features.public_file_ownership.s3_private_acl import (
    APPLY_CONFIRMATION,
    S3PrivateAclError,
    _prepare_s3_private_acl_plan,
    probe_s3_object_access,
    run_s3_private_acl_migration,
)


def _row(file_id, key, *, company_id=1, project_id=7, project_company_id=1):
    return {
        "id": file_id,
        "company_id": company_id,
        "verified_company_id": company_id,
        "project_id": project_id,
        "project_company_id": project_company_id,
        "file_url": "https://cdn.example/documents/" + key,
        "storage_key": key,
    }


class S3PrivateAclPlanTests(unittest.TestCase):
    def test_plan_selects_public_objects_without_exposing_urls_or_keys(self):
        public_key = "uploads/company-1-project-7-general/public.pdf"
        private_key = "uploads/company-1-project-7-general/private.pdf"
        report, selected = _prepare_s3_private_acl_plan(
            [_row(11, public_key), _row(12, private_key)],
            acl_by_key={public_key: "public", private_key: "private"},
        )

        self.assertTrue(report["readyForApply"])
        self.assertEqual(report["summary"]["registryS3Rows"], 2)
        self.assertEqual(report["summary"]["publicAclObjects"], 1)
        self.assertEqual(report["summary"]["privateAclObjects"], 1)
        self.assertEqual(report["summary"]["selectedObjects"], 1)
        self.assertEqual([item["fileId"] for item in report["selectedPreview"]], [11])
        self.assertNotIn(public_key, str(report))
        self.assertNotIn("cdn.example", str(report))
        self.assertEqual(selected[0]["storageKey"], public_key)

    def test_plan_blocks_invalid_ownership_missing_objects_and_duplicate_keys(self):
        duplicate = "uploads/company-1-project-7-general/duplicate.pdf"
        missing = "uploads/company-1-project-7-general/missing.pdf"
        invalid_owner = _row(14, "uploads/company-1-project-7-general/invalid.pdf")
        invalid_owner["project_company_id"] = 2
        missing_company = _row(
            15,
            "uploads/company-1-common-general/orphan.pdf",
            project_id=None,
            project_company_id=None,
        )
        missing_company["verified_company_id"] = None
        report, selected = _prepare_s3_private_acl_plan(
            [
                _row(11, duplicate),
                _row(12, duplicate),
                _row(13, missing),
                invalid_owner,
                missing_company,
            ],
            acl_by_key={duplicate: "public", missing: "missing"},
        )

        self.assertFalse(report["readyForApply"])
        self.assertEqual(selected, [])
        self.assertEqual(report["summary"]["invalidRegistryRows"], 2)
        self.assertIn("invalid_s3_registry_owner", report["blockers"])
        self.assertIn("duplicate_s3_storage_key", report["blockers"])
        self.assertIn("s3_object_missing", report["blockers"])

    def test_canary_limit_is_deterministic_and_part_of_plan(self):
        rows = [
            _row(11, "uploads/company-1-project-7-general/a.pdf"),
            _row(12, "uploads/company-1-project-7-general/b.pdf"),
        ]
        access = {row["storage_key"]: "public" for row in rows}
        first, selected_first = _prepare_s3_private_acl_plan(
            rows,
            acl_by_key=access,
            limit=1,
        )
        second, selected_second = _prepare_s3_private_acl_plan(
            list(reversed(rows)),
            acl_by_key=access,
            limit=1,
        )

        self.assertEqual(first["selectionMode"], "canary")
        self.assertEqual(first["planSha256"], second["planSha256"])
        self.assertEqual(selected_first, selected_second)
        self.assertEqual(first["summary"]["selectedObjects"], 1)

    def test_anonymous_probe_is_bounded_and_classifies_access(self):
        class Response(io.BytesIO):
            status = 206

            def getcode(self):
                return self.status

        class Opener:
            def __init__(self, result):
                self.result = result
                self.request = None

            def open(self, request, timeout):
                self.request = request
                if isinstance(self.result, Exception):
                    raise self.result
                return self.result

        config = {
            "endpoint_url": "https://storage.example",
            "bucket": "documents",
        }
        response = Response(b"x")
        opener = Opener(response)
        state = probe_s3_object_access(
            "uploads/company-1-project-7-general/file.pdf",
            storage_config=config,
            opener=opener,
        )

        self.assertEqual(state, "public")
        self.assertEqual(opener.request.get_header("Range"), "bytes=0-0")
        self.assertTrue(response.closed)

        for code, expected in ((403, "private"), (404, "missing"), (500, "unavailable")):
            error = urllib.error.HTTPError(
                "https://storage.example/documents/file.pdf",
                code,
                "error",
                {},
                None,
            )
            with self.subTest(code=code):
                self.assertEqual(
                    probe_s3_object_access(
                        "uploads/company-1-project-7-general/file.pdf",
                        storage_config=config,
                        opener=Opener(error),
                    ),
                    expected,
                )


class S3PrivateAclApplyTests(unittest.TestCase):
    def _connection(self):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        return connection

    def test_dry_run_attempts_no_acl_writes(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        connection = self._connection()
        set_acl = MagicMock()
        report = run_s3_private_acl_migration(
            lambda: connection,
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=lambda _key: "public",
            set_private_acl=set_acl,
            verify_authenticated=lambda _key: True,
            limit=1,
        )

        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        set_acl.assert_not_called()
        connection.rollback.assert_called_once()

    def test_apply_privatizes_one_guarded_object_and_rechecks_both_paths(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        connection = self._connection()
        states = iter(("public", "private"))
        probe = MagicMock(side_effect=lambda _key: next(states))
        set_acl = MagicMock(return_value=True)
        authenticated = MagicMock(return_value=True)
        dry = run_s3_private_acl_migration(
            lambda: self._connection(),
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=lambda _key: "public",
            limit=1,
        )

        applied = run_s3_private_acl_migration(
            lambda: connection,
            apply=True,
            confirm=APPLY_CONFIRMATION,
            expected_selected_count=1,
            expected_plan_sha256=dry["planSha256"],
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=probe,
            set_private_acl=set_acl,
            verify_authenticated=authenticated,
            limit=1,
        )

        self.assertTrue(applied["committed"])
        self.assertEqual(applied["writesAttempted"], 1)
        self.assertEqual(applied["privatizedObjects"], 1)
        set_acl.assert_called_once_with(key)
        authenticated.assert_called_once_with(key)
        connection.commit.assert_not_called()
        connection.rollback.assert_called_once()

    def test_apply_verifies_private_acl_even_while_bucket_read_remains_public(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        connection = self._connection()
        dry = run_s3_private_acl_migration(
            lambda: self._connection(),
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=lambda _key: "public",
            limit=1,
        )

        with patch(
            "backend.features.public_file_ownership.s3_private_acl."
            "probe_s3_object_access",
            return_value="public",
        ) as anonymous_probe:
            applied = run_s3_private_acl_migration(
                lambda: connection,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_selected_count=1,
                expected_plan_sha256=dry["planSha256"],
                load_rows=lambda _cur: [_row(11, key)],
                inspect_acl=MagicMock(side_effect=("public", "private")),
                set_private_acl=lambda _key: True,
                verify_authenticated=lambda _key: True,
                limit=1,
            )

        self.assertEqual(applied["privatizedObjects"], 1)
        anonymous_probe.assert_not_called()

    def test_apply_fails_closed_if_object_remains_public(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        dry = run_s3_private_acl_migration(
            lambda: self._connection(),
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=lambda _key: "public",
            limit=1,
        )
        connection = self._connection()

        with self.assertRaises(S3PrivateAclError) as error:
            run_s3_private_acl_migration(
                lambda: connection,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_selected_count=1,
                expected_plan_sha256=dry["planSha256"],
                load_rows=lambda _cur: [_row(11, key)],
                inspect_acl=lambda _key: "public",
                set_private_acl=lambda _key: True,
                verify_authenticated=lambda _key: True,
                limit=1,
            )

        self.assertEqual(str(error.exception), "s3_object_acl_still_public")
        connection.rollback.assert_called_once()

    def test_apply_rejects_unconfirmed_acl_update(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        dry = run_s3_private_acl_migration(
            lambda: self._connection(),
            load_rows=lambda _cur: [_row(11, key)],
            inspect_acl=lambda _key: "public",
            limit=1,
        )

        with self.assertRaises(S3PrivateAclError) as error:
            run_s3_private_acl_migration(
                lambda: self._connection(),
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_selected_count=1,
                expected_plan_sha256=dry["planSha256"],
                load_rows=lambda _cur: [_row(11, key)],
                inspect_acl=lambda _key: "public",
                set_private_acl=lambda _key: False,
                verify_authenticated=lambda _key: True,
                limit=1,
            )

        self.assertEqual(str(error.exception), "s3_acl_update_unconfirmed")

    def test_apply_rejects_inexact_guards_before_write(self):
        key = "uploads/company-1-project-7-general/public.pdf"
        set_acl = MagicMock()
        with self.assertRaises(S3PrivateAclError) as error:
            run_s3_private_acl_migration(
                lambda: self._connection(),
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_selected_count=2,
                expected_plan_sha256="wrong",
                load_rows=lambda _cur: [_row(11, key)],
                inspect_acl=lambda _key: "public",
                set_private_acl=set_acl,
                verify_authenticated=lambda _key: True,
                limit=1,
            )

        self.assertEqual(str(error.exception), "selected_count_mismatch")
        set_acl.assert_not_called()


if __name__ == "__main__":
    unittest.main()
