import unittest
from pathlib import Path

from backend.features.audit_ownership.routes import _allowed_company_ids
from backend.features.crm.lead_notifications import enqueue_lead_owner_notification
from backend.features.customer_cabinet.record_scope import project_visibility
from backend.features.material_transfer_access.service import material_transfer_visibility_filter
from backend.features.project_access.service import project_visibility_filter
from backend.features.project_payment_access.service import project_payment_visibility_filter
from backend.features.supplier_access.service import supplier_offer_visibility_filter
from backend.features.work_journal.service import work_journal_visibility_filter

ROOT = Path(__file__).resolve().parents[3]
COMPANY_A = 7
COMPANY_B = 8
PROJECT_A = "Лицей"
PROJECT_B = "Склад"
DOCUMENT_ROLES = ("директор", "зам_директора", "прораб", "мастер")
FINANCE_ROLES = ("директор", "зам_директора", "бухгалтер")
AUDIT_ROLES = ("директор", "зам_директора", "бухгалтер")
FULL_PROJECT_ROLES = ("директор", "зам_директора")


def actor(role, company_id, projects=(), packages=("Основная",)):
    return {
        "id": company_id * 10,
        "role": role,
        "companyId": company_id,
        "name": "Сотрудник",
        "assignedProjects": list(projects),
        "assignedPackages": list(packages),
    }


def visible_names(row):
    if row.get("role") in FULL_PROJECT_ROLES:
        return None
    return list(row.get("assignedProjects") or [])


class RoleChainAccessTests(unittest.TestCase):
    @staticmethod
    def _contains(value, params):
        return any(item == value or (isinstance(item, list) and value in item) for item in params)
    def chain(self):
        return [
            actor("директор", COMPANY_A),
            actor("зам_директора", COMPANY_A),
            actor("прораб", COMPANY_A, [PROJECT_A]),
            actor("мастер", COMPANY_A, [PROJECT_A]),
            actor("поставщик", COMPANY_A),
            actor("директор", COMPANY_B),
            actor("зам_директора", COMPANY_B),
            actor("прораб", COMPANY_B, [PROJECT_B]),
            actor("мастер", COMPANY_B, [PROJECT_B]),
            actor("поставщик", COMPANY_B),
        ]

    def test_documents_stay_inside_the_actor_company_and_assigned_project(self):
        for row in self.chain():
            sql, params = project_visibility([row], DOCUMENT_ROLES, visible_names)
            other = COMPANY_B if row["companyId"] == COMPANY_A else COMPANY_A
            with self.subTest(role=row["role"], company=row["companyId"]):
                self.assertNotIn(other, params)
                if row["role"] == "поставщик":
                    self.assertEqual((sql, params), ("FALSE", []))
                    continue
                self.assertIn(row["companyId"], params)
                self.assertIn("p.company_id=%s", sql)
                if row["role"] in ("прораб", "мастер"):
                    self.assertIn(PROJECT_A if row["companyId"] == COMPANY_A else PROJECT_B, params[1])
                    self.assertNotIn(PROJECT_B if row["companyId"] == COMPANY_A else PROJECT_A, params)

    def test_payments_follow_finance_roles_of_one_company(self):
        for row in self.chain():
            sql, params = project_payment_visibility_filter([row], FINANCE_ROLES)
            other = COMPANY_B if row["companyId"] == COMPANY_A else COMPANY_A
            with self.subTest(role=row["role"], company=row["companyId"]):
                self.assertNotIn(other, params)
                if row["role"] in FINANCE_ROLES:
                    self.assertEqual(params, [row["companyId"], row["companyId"]])
                    self.assertIn("owned_project.company_id=%s", sql)
                    self.assertIn("company_scope_verified=TRUE", sql)
                else:
                    self.assertEqual((sql, params), ("FALSE", []))

    def test_audit_log_hides_other_companies_and_field_roles(self):
        for row in self.chain():
            allowed = _allowed_company_ids([row], AUDIT_ROLES)
            with self.subTest(role=row["role"], company=row["companyId"]):
                if row["role"] in AUDIT_ROLES:
                    self.assertEqual(allowed, [row["companyId"]])
                else:
                    self.assertEqual(allowed, [])
        mixed = _allowed_company_ids(
            [actor("директор", COMPANY_A), actor("мастер", COMPANY_B)],
            AUDIT_ROLES,
        )
        self.assertEqual(mixed, [COMPANY_A])
        audit_source = (ROOT / "backend" / "features" / "audit_ownership" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("owner_scope='company'", audit_source)

    def test_projects_journal_and_warehouse_stay_in_the_actor_company(self):
        project_full = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
        journal_full = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
        supply_internal = ("директор", "зам_директора", "снабженец", "кладовщик", "прораб", "бухгалтер")
        workers = ("мастер", "субподрядчик", "бригадир")
        packages = ("прораб", "мастер", "субподрядчик", "бригадир")
        for row in self.chain():
            other = COMPANY_B if row["companyId"] == COMPANY_A else COMPANY_A
            own_project = PROJECT_A if row["companyId"] == COMPANY_A else PROJECT_B
            project_sql, project_params = project_visibility_filter([row], project_full)
            journal_sql, journal_params, _visible = work_journal_visibility_filter(
                [row],
                full_view_roles=journal_full,
                scoped_roles=("прораб", "стройконтроль", "технадзор"),
                worker_roles=workers,
                customer_roles=("заказчик",),
                package_limit_roles=packages,
            )
            warehouse_sql, warehouse_params = material_transfer_visibility_filter(
                [row],
                supply_internal,
                workers,
                packages,
                ("прораб",),
            )
            with self.subTest(role=row["role"], company=row["companyId"]):
                for params in (project_params, journal_params, warehouse_params):
                    self.assertNotIn(other, params)
                if row["role"] == "поставщик":
                    self.assertEqual(project_sql, "FALSE")
                    self.assertEqual(journal_sql, "FALSE")
                    self.assertEqual(warehouse_sql, "FALSE")
                    continue
                self.assertIn(row["companyId"], project_params)
                self.assertIn(row["companyId"], journal_params)
                self.assertIn(row["companyId"], warehouse_params)
                if row["role"] in ("прораб", "мастер"):
                    self.assertTrue(self._contains(own_project, project_params))
                    self.assertFalse(self._contains(
                        PROJECT_B if row["companyId"] == COMPANY_A else PROJECT_A,
                        project_params,
                    ))
                if row["role"] == "прораб":
                    self.assertTrue(self._contains(own_project, journal_params))
                if row["role"] == "мастер":
                    self.assertTrue(self._contains(own_project, warehouse_params))
                    self.assertIn(row["id"], journal_params)

    def test_supplier_offer_cannot_cross_the_request_company(self):
        sql, params = supplier_offer_visibility_filter([41], 15)
        self.assertIn("scoped_request.company_id=supplier_offers.company_id", sql)
        self.assertIn("mixed_recipient.company_id IS DISTINCT FROM supplier_offers.company_id", sql)
        self.assertNotIn(COMPANY_B, params)

    def test_lead_notification_is_not_sent_to_another_company(self):
        class Cursor:
            def __init__(self):
                self.calls = []

            def execute(self, sql, params=()):
                self.calls.append((sql, params))

        cursor = Cursor()
        queued = enqueue_lead_owner_notification(
            cursor,
            company_id=COMPANY_B,
            lead_id=15,
            environ={"LEAD_NOTIFY_TELEGRAM_CHAT_ID": "1001", "LEAD_NOTIFY_COMPANY_ID": str(COMPANY_A)},
        )
        self.assertFalse(queued)
        self.assertEqual(cursor.calls, [])

    def test_document_version_rejects_a_stamp_from_another_company(self):
        source = (ROOT / "backend" / "features" / "document_versions" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("v.company_id IS NULL OR v.company_id=h.company_id", source)


if __name__ == "__main__":
    unittest.main()
