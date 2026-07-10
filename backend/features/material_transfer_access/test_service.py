import unittest

from fastapi import HTTPException

from backend.features.material_transfer_access.service import (
    material_transfer_visibility_filter,
    resolve_material_transfer_parent,
)


FULL_VIEW_ROLES = ("директор", "зам_директора", "кладовщик", "снабженец", "прораб")
WORKER_ROLES = ("мастер", "субподрядчик", "бригадир")
PACKAGE_LIMIT_ROLES = ("прораб", *WORKER_ROLES)


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class MaterialTransferAccessTests(unittest.TestCase):
    def test_visibility_scopes_full_role_by_company(self):
        sql, params = material_transfer_visibility_filter(
            [{"companyId": 2, "role": "кладовщик"}],
            FULL_VIEW_ROLES,
            WORKER_ROLES,
            PACKAGE_LIMIT_ROLES,
            ("прораб",),
        )
        self.assertEqual(params, [2])
        self.assertIn("mt.company_id=%s", sql)
        self.assertNotIn("to_user_id", sql)

    def test_worker_sees_only_own_project_package_transfers(self):
        sql, params = material_transfer_visibility_filter(
            [{
                "id": 17,
                "name": "Мастер",
                "companyId": 2,
                "role": "мастер",
                "assignedProjects": ["Лицей"],
                "assignedPackages": ["Общестрой"],
            }],
            FULL_VIEW_ROLES,
            WORKER_ROLES,
            PACKAGE_LIMIT_ROLES,
            ("прораб",),
        )
        self.assertEqual(params, [2, ["Лицей"], 17, "Мастер", ["Общестрой"]])
        self.assertIn("mt.to_user_id=%s", sql)
        self.assertIn("mt.work_package", sql)

    def test_worker_without_package_fails_closed(self):
        self.assertEqual(
            material_transfer_visibility_filter(
                [{"id": 17, "companyId": 2, "role": "мастер", "assignedProjects": ["Лицей"]}],
                FULL_VIEW_ROLES,
                WORKER_ROLES,
                PACKAGE_LIMIT_ROLES,
                ("прораб",),
            ),
            ("FALSE", []),
        )

    def test_resolver_scopes_transfer_and_project_by_company(self):
        cur = FakeCursor([
            (8, 2, 19, "Лицей", "Общестрой", 17, "Мастер", "Активна", False),
            (19, 2, "Лицей"),
        ])
        transfer = resolve_material_transfer_parent(cur, {"companyId": 2}, 8, for_update=True)
        self.assertEqual(transfer["projectId"], 19)
        self.assertEqual(transfer["companyId"], 2)
        self.assertEqual(cur.calls[0][1], (8, 2))
        self.assertTrue(cur.calls[0][0].endswith(" FOR UPDATE"))

    def test_cross_company_transfer_is_not_resolved(self):
        with self.assertRaises(HTTPException) as error:
            resolve_material_transfer_parent(FakeCursor([]), {"companyId": 2}, 8)
        self.assertEqual(error.exception.status_code, 404)

    def test_project_identity_mismatch_is_rejected(self):
        cur = FakeCursor([
            (8, 2, 19, "Лицей", "Общестрой", 17, "Мастер", "Активна", False),
            (19, 2, "Другой объект"),
        ])
        with self.assertRaises(HTTPException) as error:
            resolve_material_transfer_parent(cur, {"companyId": 2}, 8)
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
