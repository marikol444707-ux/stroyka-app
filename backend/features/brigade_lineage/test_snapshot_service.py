import json
import unittest

from backend.features.brigade_lineage.readiness_report import sections_sha256
from backend.features.brigade_lineage.snapshot_service import (
    LineageResolutionError,
    SnapshotItemCoordinate,
    ensure_estimate_snapshot_lineages,
    resolve_snapshot_item,
)


def _sections(item=None):
    return [{
        "name": "Раздел",
        "items": [item or {
            "name": "Работа",
            "quantity": 2,
            "priceWork": 125,
            "priceMaterial": 25,
            "estimateItemKey": "work-1",
        }],
    }]


class SnapshotCursor:
    def __init__(self, *, estimate_row, snapshot_rows=None, inserted_id=91):
        self.estimate_row = estimate_row
        self.snapshot_rows = list(snapshot_rows or [])
        self.inserted_id = inserted_id
        self.calls = []
        self._result = None
        self._results = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "FROM public.estimates" in normalized:
            self._result = self.estimate_row
            self._results = []
        elif "FROM public.estimate_versions" in normalized:
            self._result = None
            self._results = list(self.snapshot_rows)
        elif normalized.startswith("INSERT INTO public.estimate_versions"):
            self._result = (self.inserted_id,)
            self._results = []
        else:
            raise AssertionError("unexpected SQL: " + normalized)

    def fetchone(self):
        return self._result

    def fetchall(self):
        return list(self._results)


class SnapshotItemResolutionTests(unittest.TestCase):
    def test_resolves_only_the_exact_coordinate_and_canonical_key(self):
        sections = _sections()

        resolved = resolve_snapshot_item(
            estimate_id=17,
            sections=sections,
            section_index=0,
            item_index=0,
            expected_item_key="work-1",
        )

        self.assertEqual(resolved.source_section_index, 0)
        self.assertEqual(resolved.source_item_index, 0)
        self.assertEqual(resolved.source_item_key, "work-1")
        self.assertEqual(resolved.item["name"], "Работа")

    def test_uses_only_the_documented_generated_key_when_both_keys_are_absent(self):
        resolved = resolve_snapshot_item(
            estimate_id=17,
            sections=_sections({"name": "Работа"}),
            section_index=0,
            item_index=0,
            expected_item_key="17:0:0",
        )

        self.assertEqual(resolved.source_item_key, "17:0:0")

    def test_rejects_conflicting_key_fields(self):
        with self.assertRaises(LineageResolutionError) as raised:
            resolve_snapshot_item(
                estimate_id=17,
                sections=_sections({
                    "estimateItemKey": "work-1",
                    "estimate_item_key": "work-2",
                }),
                section_index=0,
                item_index=0,
                expected_item_key="work-1",
            )

        self.assertEqual(raised.exception.code, "source_item_key_ambiguous")

    def test_rejects_noncanonical_or_mismatched_keys_without_name_fallback(self):
        cases = (
            (_sections({"name": "Работа", "estimateItemKey": " work-1"}), " work-1", "source_item_key_noncanonical"),
            (_sections({"name": "Работа", "estimateItemKey": "work-1"}), "work-2", "source_item_key_mismatch"),
            (_sections({"name": "Работа", "estimateItemKey": "work-1"}), "", "source_item_key_required"),
        )
        for sections, expected_key, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(LineageResolutionError) as raised:
                    resolve_snapshot_item(
                        estimate_id=17,
                        sections=sections,
                        section_index=0,
                        item_index=0,
                        expected_item_key=expected_key,
                    )
                self.assertEqual(raised.exception.code, code)

    def test_rejects_non_integer_and_out_of_range_coordinates(self):
        cases = (
            ("0", 0, "source_coordinate_invalid"),
            (True, 0, "source_coordinate_invalid"),
            (-1, 0, "source_coordinate_invalid"),
            (0, 3, "source_coordinate_not_found"),
        )
        for section_index, item_index, code in cases:
            with self.subTest(section_index=section_index, item_index=item_index):
                with self.assertRaises(LineageResolutionError) as raised:
                    resolve_snapshot_item(
                        estimate_id=17,
                        sections=_sections(),
                        section_index=section_index,
                        item_index=item_index,
                        expected_item_key="work-1",
                    )
                self.assertEqual(raised.exception.code, code)


class EstimateSnapshotPersistenceTests(unittest.TestCase):
    def _estimate_row(self, sections=None):
        return (17, 3, 8, "2.0", json.dumps(sections or _sections(), ensure_ascii=False))

    def _ensure(self, cursor):
        return ensure_estimate_snapshot_lineages(
            cursor,
            estimate_id=17,
            company_id=3,
            project_id=8,
            coordinates=[SnapshotItemCoordinate(0, 0, "work-1")],
            created_by="Директор",
        )[0]

    def test_locks_the_authoritative_owner_and_creates_one_hashed_snapshot(self):
        sections = _sections()
        cursor = SnapshotCursor(estimate_row=self._estimate_row(sections))

        lineage = self._ensure(cursor)

        self.assertEqual(lineage.source_type, "estimate")
        self.assertEqual(lineage.source_estimate_version_id, 91)
        self.assertEqual(lineage.source_item_key, "work-1")
        self.assertEqual(lineage.sections_sha256, sections_sha256(sections))
        self.assertTrue(lineage.snapshot_created)

        owner_sql, owner_params = cursor.calls[0]
        self.assertIn("WHERE id=%s AND company_id=%s AND project_id=%s", owner_sql)
        self.assertIn("FOR UPDATE", owner_sql)
        self.assertEqual(owner_params, (17, 3, 8))

        insert_sql, insert_params = cursor.calls[-1]
        self.assertIn("sections_sha256", insert_sql)
        self.assertEqual(insert_params[0], 17)
        self.assertEqual(insert_params[1], "2.0")
        self.assertEqual(insert_params[-1], sections_sha256(sections))
        self.assertEqual(str(insert_params[3]), "300")

    def test_reuses_one_verified_snapshot_without_inserting(self):
        sections = _sections()
        digest = sections_sha256(sections)
        cursor = SnapshotCursor(
            estimate_row=self._estimate_row(sections),
            snapshot_rows=[(71, json.dumps(sections, ensure_ascii=False), digest)],
        )

        lineage = self._ensure(cursor)

        self.assertEqual(lineage.source_estimate_version_id, 71)
        self.assertFalse(lineage.snapshot_created)
        self.assertFalse(any(sql.startswith("INSERT") for sql, _params in cursor.calls))
        snapshot_sql, snapshot_params = cursor.calls[1]
        self.assertIn("ORDER BY id LIMIT 2 FOR UPDATE", snapshot_sql)
        self.assertEqual(snapshot_params, (17, digest))

    def test_resolves_a_batch_with_one_lock_and_one_snapshot_lookup(self):
        sections = _sections()
        sections[0]["items"].append({
            "name": "Вторая работа",
            "quantity": 1,
            "priceWork": 50,
            "estimateItemKey": "work-2",
        })
        cursor = SnapshotCursor(estimate_row=self._estimate_row(sections))

        lineages = ensure_estimate_snapshot_lineages(
            cursor,
            estimate_id=17,
            company_id=3,
            project_id=8,
            coordinates=[
                SnapshotItemCoordinate(0, 0, "work-1"),
                SnapshotItemCoordinate(0, 1, "work-2"),
            ],
            created_by="Директор",
        )

        self.assertEqual([lineage.source_item_key for lineage in lineages], ["work-1", "work-2"])
        self.assertEqual(lineages[0].source_estimate_version_id, lineages[1].source_estimate_version_id)
        self.assertEqual(sum("FROM public.estimates" in sql for sql, _params in cursor.calls), 1)
        self.assertEqual(sum("FROM public.estimate_versions" in sql for sql, _params in cursor.calls), 1)
        self.assertEqual(sum(sql.startswith("INSERT") for sql, _params in cursor.calls), 1)

    def test_rejects_invalid_batches_before_locking_the_estimate(self):
        cases = (
            ([], "source_coordinates_required"),
            ([object()], "source_coordinate_invalid"),
            ([
                SnapshotItemCoordinate(0, 0, "work-1"),
                SnapshotItemCoordinate(0, 0, "work-1"),
            ], "source_coordinate_duplicate"),
        )
        for coordinates, code in cases:
            with self.subTest(code=code):
                cursor = SnapshotCursor(estimate_row=self._estimate_row())
                with self.assertRaises(LineageResolutionError) as raised:
                    ensure_estimate_snapshot_lineages(
                        cursor,
                        estimate_id=17,
                        company_id=3,
                        project_id=8,
                        coordinates=coordinates,
                    )
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(cursor.calls, [])

    def test_fails_closed_on_duplicate_or_corrupt_claimed_snapshots(self):
        sections = _sections()
        digest = sections_sha256(sections)
        cases = (
            ([(71, json.dumps(sections), digest), (72, json.dumps(sections), digest)], "snapshot_hash_ambiguous"),
            ([(71, json.dumps(_sections({"estimateItemKey": "other"})), digest)], "snapshot_hash_mismatch"),
        )
        for rows, code in cases:
            with self.subTest(code=code):
                cursor = SnapshotCursor(
                    estimate_row=self._estimate_row(sections),
                    snapshot_rows=rows,
                )
                with self.assertRaises(LineageResolutionError) as raised:
                    self._ensure(cursor)
                self.assertEqual(raised.exception.code, code)
                self.assertFalse(any(sql.startswith("INSERT") for sql, _params in cursor.calls))

    def test_stops_before_snapshot_lookup_when_owner_or_content_is_invalid(self):
        cases = (
            (None, "estimate_owner_not_found"),
            ((17, 3, 8, "2.0", "{}"), "snapshot_content_invalid"),
        )
        for estimate_row, code in cases:
            with self.subTest(code=code):
                cursor = SnapshotCursor(estimate_row=estimate_row)
                with self.assertRaises(LineageResolutionError) as raised:
                    self._ensure(cursor)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
