import unittest
import io
from unittest.mock import Mock, patch
from urllib.parse import quote

from fastapi import HTTPException

from .s3_namespace_migration_apply import (
    APPLY_CONFIRMATION,
    S3NamespaceMigrationApplyError,
    _build_cell_updates,
    _copy_storage_object_verified,
    _validate_apply_guards,
    run_s3_namespace_migration_apply,
)
from . import s3_namespace_migration_apply as apply_module


class S3NamespaceMigrationApplyTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "readyForApply": True,
            "summary": {
                "readyObjectCopies": 2,
                "affectedCells": 1,
            },
            "planSha256": "a" * 64,
        }

    def test_exact_confirmation_counts_and_sha_are_required(self):
        for field, value, expected in (
            ("confirm", "wrong", "apply_confirmation_invalid"),
            ("expected_copy_count", 3, "copy_count_mismatch"),
            ("expected_affected_cell_count", 2, "affected_cell_count_mismatch"),
            ("expected_plan_sha256", "b" * 64, "plan_sha256_mismatch"),
        ):
            kwargs = {
                "confirm": APPLY_CONFIRMATION,
                "expected_copy_count": 2,
                "expected_affected_cell_count": 1,
                "expected_plan_sha256": "a" * 64,
            }
            kwargs[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(S3NamespaceMigrationApplyError, expected):
                    _validate_apply_guards(self.report, **kwargs)

    def test_unready_plan_is_rejected_before_any_apply_work(self):
        report = {**self.report, "readyForApply": False}

        with self.assertRaisesRegex(
            S3NamespaceMigrationApplyError,
            "migration_plan_not_ready",
        ):
            _validate_apply_guards(
                report,
                confirm=APPLY_CONFIRMATION,
                expected_copy_count=2,
                expected_affected_cell_count=1,
                expected_plan_sha256="a" * 64,
            )

    def test_shared_urls_are_rewritten_in_one_cell_without_losing_shape(self):
        first = "https://storage.example/legacy/one.jpg"
        second = "https://storage.example/legacy/two.jpg"
        migrations = [
            {
                "sourceUrl": first,
                "destinationUrl": "https://storage.example/new/one.jpg",
                "cells": [("expenses.photo_url", 25)],
            },
            {
                "sourceUrl": second,
                "destinationUrl": "https://storage.example/new/two.jpg",
                "cells": [("expenses.photo_url", 25)],
            },
        ]
        records = [{
            "source": "expenses.photo_url",
            "recordId": 25,
            "value": f'["{first}","{second}"]',
        }]

        updates = _build_cell_updates(records, migrations)

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["referenceCount"], 2)
        self.assertEqual(
            updates[0]["newValue"],
            '["https://storage.example/new/one.jpg",'
            '"https://storage.example/new/two.jpg"]',
        )

    def test_missing_cell_or_reference_is_a_hard_failure(self):
        migration = {
            "sourceUrl": "https://storage.example/legacy/missing.jpg",
            "destinationUrl": "https://storage.example/new/missing.jpg",
            "cells": [("expenses.photo_url", 404)],
        }

        with self.assertRaisesRegex(
            S3NamespaceMigrationApplyError,
            "planned_cell_missing",
        ):
            _build_cell_updates([], [migration])

        with self.assertRaisesRegex(
            S3NamespaceMigrationApplyError,
            "planned_reference_missing",
        ):
            _build_cell_updates(
                [{
                    "source": "expenses.photo_url",
                    "recordId": 404,
                    "value": "https://storage.example/legacy/other.jpg",
                }],
                [migration],
            )

    def test_public_guard_report_never_needs_raw_storage_identifiers(self):
        # The guarded executor accepts only counts and the public plan SHA.
        # Raw object keys and URLs must never be supplied as confirmation data.
        _validate_apply_guards(
            self.report,
            confirm=APPLY_CONFIRMATION,
            expected_copy_count=2,
            expected_affected_cell_count=1,
            expected_plan_sha256="a" * 64,
        )

    def test_copy_verifies_source_and_destination_bytes(self):
        source = b"verified-photo"
        calls = []

        def open_object(*, key, **_kwargs):
            calls.append(("open", key))
            if key == "new/file.jpg" and calls.count(("open", key)) == 1:
                raise HTTPException(status_code=404, detail="missing")
            return io.BytesIO(source), len(source)

        put_object = Mock(return_value=True)
        result = _copy_storage_object_verified(
            "legacy/file.jpg",
            "new/file.jpg",
            open_object=open_object,
            put_object=put_object,
            storage_config={
                "endpoint_url": "https://storage.example",
                "bucket": "documents",
                "region": "ru-central1",
                "access_key": "access",
                "secret_key": "secret",
                "max_bytes": 1024,
            },
        )

        self.assertEqual(result["sizeBytes"], len(source))
        self.assertTrue(result["created"])
        self.assertEqual(len(result["sha256"]), 64)
        put_object.assert_called_once()
        self.assertEqual(put_object.call_args.kwargs["content"], source)

    def test_existing_exact_destination_is_reused_but_mismatch_is_rejected(self):
        source = b"verified-photo"

        def matching_open(**_kwargs):
            return io.BytesIO(source), len(source)

        put_object = Mock()
        result = _copy_storage_object_verified(
            "legacy/file.jpg",
            "new/file.jpg",
            open_object=matching_open,
            put_object=put_object,
            storage_config={"max_bytes": 1024},
        )
        self.assertFalse(result["created"])
        put_object.assert_not_called()

        def mismatching_open(*, key, **_kwargs):
            content = source if key.startswith("legacy/") else b"foreign-content"
            return io.BytesIO(content), len(content)

        with self.assertRaisesRegex(
            S3NamespaceMigrationApplyError,
            "destination_content_conflict",
        ):
            _copy_storage_object_verified(
                "legacy/file.jpg",
                "new/file.jpg",
                open_object=mismatching_open,
                put_object=Mock(),
                storage_config={"max_bytes": 1024},
            )

    def test_guarded_runner_copies_once_then_updates_and_registers(self):
        source_key = "uploads/Кисловодск-Лицей-4/own-expenses/shared.jpg"
        source_url = "https://storage.example/" + quote(source_key, safe="/")
        rows = self._runner_rows(source_url)
        connection = _ApplyConnection()
        migrate = Mock(return_value={
            "sha256": "c" * 64,
            "sizeBytes": 123,
            "created": True,
        })

        with patch.object(
            apply_module,
            "load_s3_registration_rows",
            return_value=rows,
        ):
            report = run_s3_namespace_migration_apply(
                Mock(return_value=connection),
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_copy_count=1,
                expected_affected_cell_count=2,
                expected_plan_sha256=self._runner_plan_sha(rows, {source_key}),
                verify_storage_key=Mock(return_value=True),
                migrate_storage_object=migrate,
            )

        self.assertTrue(report["committed"])
        self.assertEqual(report["objectCopyCount"], 1)
        self.assertEqual(report["updatedCellCount"], 2)
        self.assertEqual(report["registeredFileCount"], 1)
        self.assertEqual(report["sourceObjectsDeleted"], 0)
        self.assertNotIn("storage.example", str(report))
        self.assertNotIn("Кисловодск", str(report))
        migrate.assert_called_once()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        update_params = [
            params
            for query, params in connection.cursor_value.calls
            if "UPDATE" in query
        ]
        self.assertEqual(len(update_params), 2)
        self.assertTrue(all(
            params[0] == "/tenant-files/1/content"
            for params in update_params
        ))

    def test_default_runner_is_read_only_and_never_copies(self):
        source_key = "uploads/Кисловодск-Лицей-4/own-expenses/shared.jpg"
        source_url = "https://storage.example/" + quote(source_key, safe="/")
        rows = self._runner_rows(source_url)
        connection = _ApplyConnection()
        migrate = Mock()

        with patch.object(
            apply_module,
            "load_s3_registration_rows",
            return_value=rows,
        ):
            report = run_s3_namespace_migration_apply(
                Mock(return_value=connection),
                verify_storage_key=Mock(return_value=True),
                migrate_storage_object=migrate,
            )

        self.assertTrue(report["dryRun"])
        self.assertTrue(report["applySupported"])
        self.assertTrue(report["rolledBack"])
        migrate.assert_not_called()
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_concurrent_plan_change_rolls_back_without_database_writes(self):
        source_key = "uploads/Кисловодск-Лицей-4/own-expenses/shared.jpg"
        source_url = "https://storage.example/" + quote(source_key, safe="/")
        rows = self._runner_rows(source_url)
        changed_rows = (
            [{**rows[0][0], "value": source_url + "?changed"}, *rows[0][1:]],
            *rows[1:],
        )
        connection = _ApplyConnection()

        with patch.object(
            apply_module,
            "load_s3_registration_rows",
            side_effect=[rows, changed_rows],
        ):
            with self.assertRaisesRegex(
                S3NamespaceMigrationApplyError,
                "migration_plan_not_ready|plan_sha256_mismatch",
            ):
                run_s3_namespace_migration_apply(
                    Mock(return_value=connection),
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_copy_count=1,
                    expected_affected_cell_count=2,
                    expected_plan_sha256=self._runner_plan_sha(rows, {source_key}),
                    verify_storage_key=Mock(return_value=True),
                    migrate_storage_object=Mock(return_value={
                        "sha256": "c" * 64,
                        "sizeBytes": 123,
                        "created": True,
                    }),
                )

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        self.assertFalse(any(
            sql.startswith("UPDATE ") or sql.startswith("INSERT ")
            for sql, _params in connection.cursor_value.calls
        ))

    @staticmethod
    def _runner_rows(source_url):
        return (
            [
                {
                    "source": "expenses.photo_url",
                    "recordId": 26,
                    "value": source_url,
                    "companyId": 1,
                    "projectId": 7,
                    "ownershipVerified": True,
                },
                {
                    "source": "own_expenses.photo_url",
                    "recordId": 7,
                    "value": source_url,
                    "companyId": 1,
                    "projectId": 7,
                    "ownershipVerified": True,
                },
            ],
            [{
                "id": 1,
                "company_id": 1,
                "project_id": 7,
                "file_url": (
                    "https://storage.example/uploads/"
                    "company-1-project-7-expenses/expenses/known.jpg"
                ),
                "storage_key": (
                    "uploads/company-1-project-7-expenses/expenses/known.jpg"
                ),
            }],
            [{"id": 7, "company_id": 1, "name": "Кисловодск Лицей 4"}],
            {1},
        )

    @staticmethod
    def _runner_plan_sha(rows, verified_keys):
        from .s3_namespace_migration_plan import _prepare_s3_namespace_migration_plan

        report, _migrations = _prepare_s3_namespace_migration_plan(
            *rows,
            verified_source_keys=verified_keys,
            storage_prefixes=("uploads",),
        )
        return report["planSha256"]


class _ApplyCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((str(query), params))

    def fetchone(self):
        return {"id": 1}

    def close(self):
        pass


class _ApplyConnection:
    def __init__(self):
        self.cursor_value = _ApplyCursor()
        self.set_session = Mock()
        self.commit = Mock()
        self.rollback = Mock()
        self.close = Mock()

    def cursor(self, **_kwargs):
        return self.cursor_value


if __name__ == "__main__":
    unittest.main()
