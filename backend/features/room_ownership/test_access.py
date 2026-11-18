import unittest

from fastapi import HTTPException

from backend.features.room_ownership.access import RoomOwnership
from backend.features.company_context.service import effective_company_user


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.description = [("id",)]

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        if "project_name" in sql.lower():
            self.description = [("company_id",), ("project_id",), ("project_name",)]

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = list(self.rows)
        self.rows = []
        return rows


def scope():
    def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
        if x_company_mode == "all_companies" and action == "write":
            raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")
        company_id = int(x_company_id or 2)
        return {
            "mode": "company", "companyId": company_id, "role": "директор",
            "effectiveRole": "директор", "active": True, "companyActive": True,
            "assignedProjects": ["Объект"],
        }

    return RoomOwnership(
        resolve,
        lambda user, context: [effective_company_user({**user, "id": user.get("id") or 1}, context)],
        full_view_roles=("директор",),
        platform_staff_roles=("system_owner",),
        read_roles=("директор", "прораб"),
        write_roles=("директор",),
    )


class RoomOwnershipAccessTest(unittest.TestCase):
    def test_company_list_never_includes_null_owners(self):
        actors, mode = scope().actors(Cursor(), {"id": 1, "role": "директор"}, None, write=False)
        join, where, params = scope().list_clause(actors, mode)
        self.assertIn("p.company_id=r.company_id", join)
        self.assertIn("p.company_id=%s", where)
        self.assertEqual(params, [2])
        self.assertNotIn("IS NULL", where)

    def test_foreign_project_id_is_not_found_in_the_selected_company(self):
        cursor = Cursor()
        ownership = scope()
        actors, _mode = ownership.actors(cursor, {"id": 1, "role": "директор"}, None, write=True)
        with self.assertRaises(HTTPException) as error:
            ownership.verified_project(cursor, actors[0], {"projectId": 11, "project": "Объект"})
        self.assertEqual(error.exception.status_code, 404)
        self.assertIn("company_id=%s", cursor.calls[-1][0])
        self.assertEqual(cursor.calls[-1][1][1], 2)

    def test_verified_project_uses_the_selected_company_not_a_forged_owner(self):
        cursor = Cursor(rows=[(12, 2, "Склад")])
        ownership = scope()
        actors, _mode = ownership.actors(cursor, {"id": 1, "role": "директор"}, None, write=True)
        parent = ownership.verified_project(cursor, actors[0], {"project": "Склад", "companyId": 3})
        self.assertEqual((parent["companyId"], parent["id"], parent["name"]), (2, 12, "Склад"))

    def test_platform_cannot_claim_an_unowned_row(self):
        cursor = Cursor(rows=[(5,)])
        with self.assertRaises(HTTPException) as error:
            scope().mutable_row(cursor, "rooms", 5, [{"role": "system_owner"}], "platform_unowned")
        self.assertEqual(error.exception.status_code, 409)

    def test_hidden_company_row_is_not_found(self):
        cursor = Cursor()
        ownership = scope()
        actors, mode = ownership.actors(cursor, {"id": 1, "role": "директор"}, None, write=True)
        with self.assertRaises(HTTPException) as error:
            ownership.mutable_row(cursor, "room_works", 8, actors, mode)
        self.assertEqual(error.exception.status_code, 404)

    def test_stored_journal_owner_must_be_unique_inside_its_company(self):
        from backend.features.room_ownership.access import resolve_stored_project_owner
        cursor = Cursor(rows=[(10, 2, "Объект"), (11, 2, "Объект")])
        with self.assertRaises(HTTPException) as error:
            resolve_stored_project_owner(cursor, 2, "Объект")
        self.assertEqual(error.exception.status_code, 409)
        unique = Cursor(rows=[(12, 2, "Склад")])
        parent = resolve_stored_project_owner(unique, 2, "Склад")
        self.assertEqual((parent["companyId"], parent["id"]), (2, 12))


if __name__ == "__main__":
    unittest.main()
