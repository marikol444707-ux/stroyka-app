import unittest

from .grouping import build_supplier_relation_metadata


def normalize_name(value):
    return " ".join(str(value or "").lower().replace('"', "").split())


def identity_keys(row):
    keys = set()
    inn = str((row or {}).get("inn") or "").strip()
    email = str((row or {}).get("email") or "").strip().lower()
    if inn:
        keys.add("inn:" + inn)
    if email:
        keys.add("email:" + email)
    return keys


class SupplierDuplicateGroupingTests(unittest.TestCase):
    def test_manual_aliases_create_one_relation_group(self):
        suppliers = [
            {"id": 11, "name": "ИП Литашов Д. В.", "inn": "261908121534", "phone": "+7 988 114-32-26"},
            {"id": 12, "name": "ИП Литашов Денис Владимирович"},
        ]
        aliases = [
            {
                "supplier_id": 11,
                "alias_key": normalize_name("ИП Литашов Денис Владимирович"),
                "source": "manual_supplier_duplicate_link",
            },
            {
                "supplier_id": 12,
                "alias_key": normalize_name("ИП Литашов Д. В."),
                "source": "manual_supplier_duplicate_link",
            },
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[11]["relatedSupplierIds"], [11, 12])
        self.assertEqual(metadata[12]["relatedSupplierIds"], [11, 12])
        self.assertEqual(metadata[11]["canonicalSupplierId"], 11)
        self.assertEqual(metadata[11]["duplicateCount"], 2)

    def test_strong_identity_and_manual_aliases_are_transitive(self):
        suppliers = [
            {"id": 17, "name": "АО Сатурн Юг", "inn": "2312254452", "user_id": 7},
            {"id": 25, "name": "Сатурн", "inn": "2312254452"},
            {"id": 31, "name": "Сатурн старая карточка"},
        ]
        aliases = [
            {
                "supplier_id": 25,
                "alias_key": normalize_name("Сатурн старая карточка"),
                "source": "manual_supplier_duplicate_link",
            },
            {
                "supplier_id": 31,
                "alias_key": normalize_name("Сатурн"),
                "source": "manual_supplier_duplicate_link",
            },
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        for supplier_id in (17, 25, 31):
            self.assertEqual(metadata[supplier_id]["relatedSupplierIds"], [17, 25, 31])
            self.assertEqual(metadata[supplier_id]["canonicalSupplierId"], 17)

    def test_direct_supplier_id_link_survives_renames(self):
        suppliers = [
            {"id": 51, "name": "Новое имя основной карточки"},
            {"id": 52, "name": "Новое имя карточки-дубля"},
        ]
        aliases = [
            {
                "supplier_id": 51,
                "related_supplier_id": 52,
                "alias_key": "старое имя карточки дубля",
                "source": "manual_supplier_duplicate_link",
            }
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51, 52])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [51, 52])

    def test_one_way_legacy_manual_alias_does_not_create_an_identity_edge(self):
        suppliers = [
            {"id": 51, "name": "Основная карточка"},
            {"id": 52, "name": "Карточка-дубль"},
        ]
        aliases = [
            {
                "supplier_id": 51,
                "alias_key": normalize_name("Карточка-дубль"),
                "source": "manual_supplier_duplicate_link",
            }
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [52])

    def test_reciprocal_unique_legacy_manual_alias_remains_compatible(self):
        suppliers = [
            {"id": 51, "name": "Основная карточка"},
            {"id": 52, "name": "Карточка-дубль"},
        ]
        aliases = [
            {
                "supplier_id": 51,
                "alias_key": normalize_name("Карточка-дубль"),
                "source": "manual_supplier_duplicate_link",
            },
            {
                "supplier_id": 52,
                "alias_key": normalize_name("Основная карточка"),
                "source": "manual_supplier_duplicate_link",
            },
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51, 52])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [51, 52])

    def test_legacy_manual_alias_does_not_merge_non_unique_names(self):
        suppliers = [
            {"id": 1, "name": "Основной"},
            {"id": 2, "name": "Дубликат"},
            {"id": 3, "name": "Дубликат"},
        ]
        aliases = [
            {"supplier_id": 1, "alias_key": normalize_name("Дубликат"), "source": "manual_supplier_duplicate_link"},
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[1]["relatedSupplierIds"], [1])
        self.assertEqual(metadata[2]["relatedSupplierIds"], [2])
        self.assertEqual(metadata[3]["relatedSupplierIds"], [3])

    def test_reciprocal_legacy_alias_disambiguates_non_unique_target_name(self):
        suppliers = [
            {"id": 1, "name": "Основной"},
            {"id": 2, "name": "Дубликат"},
            {"id": 3, "name": "Дубликат"},
        ]
        aliases = [
            {"supplier_id": 1, "alias_key": normalize_name("Дубликат"), "source": "manual_supplier_duplicate_link"},
            {"supplier_id": 2, "alias_key": normalize_name("Основной"), "source": "manual_supplier_duplicate_link"},
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[1]["relatedSupplierIds"], [1, 2])
        self.assertEqual(metadata[2]["relatedSupplierIds"], [1, 2])
        self.assertEqual(metadata[3]["relatedSupplierIds"], [3])

    def test_stale_legacy_alias_does_not_follow_an_old_name_to_an_unrelated_supplier(self):
        suppliers = [
            {"id": 1, "name": "Основной"},
            {"id": 2, "name": "Дубликат переименован"},
            {"id": 3, "name": "Старое имя дубля"},
        ]
        aliases = [
            {"supplier_id": 1, "alias_key": normalize_name("Старое имя дубля"), "source": "manual_supplier_duplicate_link"},
            {"supplier_id": 2, "alias_key": normalize_name("Основной"), "source": "manual_supplier_duplicate_link"},
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[1]["relatedSupplierIds"], [1])
        self.assertEqual(metadata[2]["relatedSupplierIds"], [2])
        self.assertEqual(metadata[3]["relatedSupplierIds"], [3])

    def test_unlinked_name_only_suppliers_stay_separate(self):
        suppliers = [
            {"id": 51, "name": "АО ТД Электромонтаж"},
            {"id": 52, "name": 'АО "ТД "Электротехмонтаж"'},
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            [],
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [52])

    def test_weak_document_alias_does_not_merge_name_only_suppliers(self):
        suppliers = [
            {"id": 51, "name": "АО ТД Электромонтаж"},
            {"id": 52, "name": 'АО "ТД "Электротехмонтаж"'},
        ]
        aliases = [
            {
                "supplier_id": 51,
                "alias_key": normalize_name('АО "ТД "Электротехмонтаж"'),
                "source": "warehouse_invoice",
            }
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [52])

    def test_non_manual_related_id_is_not_an_approved_duplicate_link(self):
        suppliers = [
            {"id": 51, "name": "Поставщик 1"},
            {"id": 52, "name": "Поставщик 2"},
        ]
        aliases = [
            {
                "supplier_id": 51,
                "related_supplier_id": 52,
                "source": "warehouse_invoice",
            }
        ]

        metadata = build_supplier_relation_metadata(
            suppliers,
            aliases,
            identity_keys=identity_keys,
            normalize_name_key=normalize_name,
        )

        self.assertEqual(metadata[51]["relatedSupplierIds"], [51])
        self.assertEqual(metadata[52]["relatedSupplierIds"], [52])


if __name__ == "__main__":
    unittest.main()
