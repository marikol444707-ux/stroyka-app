import unittest

from backend.features.estimate_access.journal_keys import journal_item_keys


class JournalItemKeysTest(unittest.TestCase):
    def test_worker_visible_index_does_not_replace_stable_work_key(self):
        item = {
            "id": 1785866456840.5447,
            "workKey": "раздел-3-кабельная-канализация-помещения-коробка-679",
            "name": "Коробка ответвительная на стене",
        }
        keys = journal_item_keys(
            72, 2, 61, "Раздел 3. Кабельная канализация: помещения",
            item["name"], item,
        )
        self.assertIn(item["workKey"], keys)
        self.assertIn("72:2:61", keys)
        self.assertNotIn("72:2:12", keys)
        worker_materials = {item["workKey"]: [{"name": "Кабель", "quantity": 2}]}
        worker_params = {item["workKey"]: {"roomName": "Кабинет 1", "photoUrl": "/tenant-files/1/content"}}
        self.assertEqual([worker_materials[key] for key in keys if key in worker_materials],
                         [[{"name": "Кабель", "quantity": 2}]])
        self.assertEqual([worker_params[key] for key in keys if key in worker_params],
                         [{"roomName": "Кабинет 1", "photoUrl": "/tenant-files/1/content"}])

    def test_duplicate_names_stay_distinct_by_stable_key(self):
        first = {"workKey": "коробка-239"}
        second = {"workKey": "коробка-377"}
        first_keys = journal_item_keys(72, 2, 34, "Раздел 3", "Коробка ответвительная на стене", first)
        second_keys = journal_item_keys(72, 2, 61, "Раздел 3", "Коробка ответвительная на стене", second)
        self.assertIn("коробка-239", first_keys)
        self.assertNotIn("коробка-239", second_keys)
        self.assertIn("коробка-377", second_keys)
        self.assertNotIn("коробка-377", first_keys)

    def test_legacy_row_still_accepts_position_and_name(self):
        keys = journal_item_keys(72, 2, 61, "Раздел 3", "Монтаж", {"name": "Монтаж"})
        self.assertIn("72:2:61", keys)
        self.assertIn("2:61", keys)
        self.assertIn("Раздел 3|Монтаж", keys)


if __name__ == "__main__":
    unittest.main()
