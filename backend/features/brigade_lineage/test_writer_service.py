import unittest

from backend.features.brigade_lineage.snapshot_service import EstimateSnapshotLineage
from backend.features.brigade_lineage.writer_service import (
    LineageWriteConflict,
    insert_pricelist_contract_item,
    load_existing_estimate_contract_items,
    write_estimate_contract_item,
)


class FakeCursor:
    def __init__(self, fetchone_results=(), fetchall_results=()):
        self.calls = []
        self.fetchone_results = list(fetchone_results)
        self.fetchall_results = list(fetchall_results)

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []


def estimate_lineage():
    return EstimateSnapshotLineage(
        source_type="estimate",
        source_estimate_version_id=41,
        source_section_index=2,
        source_item_index=5,
        source_item_key="work-2-5",
        sections_sha256="a" * 64,
        section={"name": "Стены"},
        item={"name": "Штукатурка"},
        snapshot_created=False,
    )


class PricelistContractItemWriterTests(unittest.TestCase):
    def test_pricelist_item_has_explicit_source_and_no_estimate_coordinates(self):
        cursor = FakeCursor()

        result = insert_pricelist_contract_item(
            cursor,
            contract_id=7,
            work_package="Отделка",
            name="Штукатурка",
            unit="м2",
            price=1000,
            category="Стены",
            coefficient=0.65,
        )

        sql, params = cursor.calls[0]
        self.assertIn("source_type", sql)
        self.assertEqual(params[:5], (7, "Стены", "Штукатурка", "Отделка", ""))
        self.assertEqual(params[6], 0)
        self.assertEqual(params[7:10], (1000.0, 650.0, 0))
        self.assertEqual(params[10:], ("pricelist", None, None, None, None))
        self.assertEqual(result, {"priceSmeta": 1000.0, "priceBrigade": 650.0})

    def test_non_finite_values_cannot_reach_contract_item_storage(self):
        for field, value in (("price", float("nan")), ("coefficient", float("inf"))):
            with self.subTest(field=field):
                cursor = FakeCursor()
                kwargs = {
                    "contract_id": 7,
                    "work_package": "Основная",
                    "name": "Работа",
                    "unit": "шт",
                    "price": 100,
                    "category": "",
                    "coefficient": 1,
                }
                kwargs[field] = value
                with self.assertRaises(ValueError):
                    insert_pricelist_contract_item(cursor, **kwargs)
                self.assertEqual(cursor.calls, [])


class EstimateContractItemWriterTests(unittest.TestCase):
    def test_existing_rows_are_loaded_once_for_the_complete_contract_batch(self):
        stored = (
            91, "Стены", "Штукатурка", "м2", 12, 1000, 650, "work-2-5",
            41, 2, 5, "work-2-5",
        )
        cursor = FakeCursor(fetchall_results=[[stored]])

        existing = load_existing_estimate_contract_items(
            cursor,
            contract_id=7,
            lineages=[estimate_lineage(), estimate_lineage()],
        )

        self.assertEqual(len(cursor.calls), 1)
        self.assertIn("source_estimate_version_id=ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (7, [41]))
        self.assertEqual(existing[(41, 2, 5, "work-2-5")], stored)

    def test_new_item_persists_the_complete_exact_lineage(self):
        cursor = FakeCursor(fetchone_results=[None, (91,)])

        result = write_estimate_contract_item(
            cursor,
            contract_id=7,
            work_package="Отделка",
            lineage=estimate_lineage(),
            section_name="Стены",
            name="Штукатурка",
            unit="м2",
            quantity=12,
            price_smeta=1000,
            price_brigade=650,
        )

        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO brigade_contract_items"))
        self.assertEqual(insert[1][10:], ("estimate", 41, 2, 5, "work-2-5"))
        self.assertEqual(result["id"], 91)
        self.assertTrue(result["inserted"])

    def test_exact_repeat_reuses_the_row_without_mutating_issued_values(self):
        stored = (91, "Старый раздел", "Выданная работа", "м2", 7.5, 900, 777, "work-2-5")
        cursor = FakeCursor(fetchone_results=[stored])

        result = write_estimate_contract_item(
            cursor,
            contract_id=7,
            work_package="Отделка",
            lineage=estimate_lineage(),
            section_name="Стены",
            name="Штукатурка",
            unit="м2",
            quantity=12,
            price_smeta=1000,
            price_brigade=650,
        )

        self.assertFalse(result["inserted"])
        self.assertEqual(result["quantity"], 7.5)
        self.assertEqual(result["priceBrigade"], 777.0)
        self.assertFalse(any(call[0].startswith("UPDATE brigade_contract_items") for call in cursor.calls))
        self.assertFalse(any(call[0].startswith("INSERT INTO brigade_contract_items") for call in cursor.calls))

    def test_compatibility_key_conflict_fails_closed(self):
        stored = (91, "Стены", "Штукатурка", "м2", 12, 1000, 650, "other-key")
        cursor = FakeCursor(fetchone_results=[stored])

        with self.assertRaises(LineageWriteConflict):
            write_estimate_contract_item(
                cursor,
                contract_id=7,
                work_package="Отделка",
                lineage=estimate_lineage(),
                section_name="Стены",
                name="Штукатурка",
                unit="м2",
                quantity=12,
                price_smeta=1000,
                price_brigade=650,
            )

        self.assertEqual(len(cursor.calls), 1)


if __name__ == "__main__":
    unittest.main()
