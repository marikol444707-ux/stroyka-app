import unittest
from unittest.mock import Mock

from .service import (
    SupplyProjectIdentityError,
    resolve_supply_project,
)


class SupplyProjectIdentityTests(unittest.TestCase):
    def test_exact_id_must_belong_to_company_and_match_name(self):
        cur = Mock()
        cur.fetchone.return_value = {
            "id": 17, "company_id": 4, "name": "Лицей", "archived": False,
        }
        result = resolve_supply_project(
            cur, company_id=4, project_id=17, project_name="Лицей"
        )
        self.assertEqual((result.project_id, result.project_name), (17, "Лицей"))
        cur.execute.assert_called_once_with(
            "SELECT id,company_id,name,COALESCE(archived,FALSE) AS archived "
            "FROM projects WHERE id=%s AND company_id=%s",
            (17, 4),
        )

    def test_name_fallback_rejects_duplicate_inside_company(self):
        cur = Mock()
        cur.fetchall.return_value = [
            {"id": 17, "company_id": 4, "name": "Лицей", "archived": False},
            {"id": 18, "company_id": 4, "name": "Лицей", "archived": False},
        ]
        with self.assertRaisesRegex(SupplyProjectIdentityError, "несколько объектов"):
            resolve_supply_project(cur, company_id=4, project_name="Лицей")

    def test_archived_project_is_rejected(self):
        cur = Mock()
        cur.fetchone.return_value = {
            "id": 17, "company_id": 4, "name": "Лицей", "archived": True,
        }
        with self.assertRaisesRegex(SupplyProjectIdentityError, "архивного объекта"):
            resolve_supply_project(
                cur, company_id=4, project_id=17, project_name="Лицей"
            )

    def test_main_warehouse_has_no_project_id(self):
        cur = Mock()
        result = resolve_supply_project(
            cur, company_id=4, project_name="Основной склад"
        )
        self.assertIsNone(result.project_id)
        cur.execute.assert_not_called()

    def test_main_warehouse_rejects_unrelated_project_id(self):
        with self.assertRaisesRegex(SupplyProjectIdentityError, "не используется"):
            resolve_supply_project(
                Mock(), company_id=4, project_id=17, project_name="Основной склад"
            )
