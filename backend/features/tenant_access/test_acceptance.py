"""Acceptance checks for issues 35, 46, 47 and 51 on two companies."""
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.audit_ownership.routes import _allowed_company_ids
from backend.features.brigade_access.service import brigade_contract_visibility_filter
from backend.features.company_requisites.routes import register_company_requisites_module
from backend.features.crm.lead_notifications import enqueue_lead_owner_notification
from backend.features.customer_cabinet.record_scope import project_visibility
from backend.features.material_transfer_access.service import material_transfer_visibility_filter
from backend.features.project_access.service import project_visibility_filter
from backend.features.project_chat.company_backfill import plan_chat_owners
from backend.features.project_payment_access.service import (
    project_payment_visibility_filter,
    reversal_company_id,
)
from backend.features.supplier_access.service import supplier_offer_visibility_filter
from backend.features.work_journal.service import work_journal_visibility_filter

ROOT = Path(__file__).resolve().parents[3]
COMPANY_A = 7
COMPANY_B = 8
PROJECT = "Лицей"
FULL_PROJECT_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
DOCUMENT_ROLES = ("директор", "зам_директора", "прораб", "мастер")
FINANCE_ROLES = ("директор", "зам_директора", "бухгалтер")
AUDIT_ROLES = ("директор", "зам_директора", "бухгалтер")
JOURNAL_FULL = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
SUPPLY_INTERNAL = ("директор", "зам_директора", "снабженец", "кладовщик", "прораб", "бухгалтер")
WORKERS = ("мастер", "субподрядчик", "бригадир")
PACKAGES = ("прораб", "мастер", "субподрядчик", "бригадир")


def actor(role, company_id, projects=(), packages=("Основная",)):
    return {
        "id": company_id * 10,
        "role": role,
        "companyId": company_id,
        "name": "Сотрудник",
        "assignedProjects": list(projects),
        "assignedPackages": list(packages),
    }


def names_for(row):
    if row["role"] in ("директор", "зам_директора"):
        return None
    return list(row["assignedProjects"])


def company_params(params):
    return [value for value in params if isinstance(value, int)]


class RoleForeignCompanyMatrixTests(unittest.TestCase):
    def chains(self, row):
        project_sql, project_params = project_visibility_filter([row], FULL_PROJECT_ROLES)
        document_sql, document_params = project_visibility([row], DOCUMENT_ROLES, names_for)
        journal_sql, journal_params, _visible = work_journal_visibility_filter(
            [row],
            full_view_roles=JOURNAL_FULL,
            scoped_roles=("прораб", "стройконтроль", "технадзор"),
            worker_roles=WORKERS,
            customer_roles=("заказчик",),
            package_limit_roles=PACKAGES,
        )
        warehouse_sql, warehouse_params = material_transfer_visibility_filter(
            [row], SUPPLY_INTERNAL, WORKERS, PACKAGES, ("прораб",),
        )
        payment_sql, payment_params = project_payment_visibility_filter([row], FINANCE_ROLES)
        brigade_sql, brigade_params = brigade_contract_visibility_filter(
            [row],
            allowed_roles=(*FINANCE_ROLES, *WORKERS, "прораб"),
            full_view_roles=FINANCE_ROLES,
            worker_roles=WORKERS,
            package_limit_roles=PACKAGES,
            package_optional_roles=("прораб",),
        )
        return {
            "projects": (project_sql, project_params),
            "documents": (document_sql, document_params),
            "journal": (journal_sql, journal_params),
            "warehouse": (warehouse_sql, warehouse_params),
            "finance": (payment_sql, payment_params),
            "brigade": (brigade_sql, brigade_params),
        }

    def test_each_role_stays_inside_its_company(self):
        roles = (
            ("директор", ()),
            ("зам_директора", ()),
            ("прораб", (PROJECT,)),
            ("мастер", (PROJECT,)),
            ("поставщик", ()),
        )
        for role, projects in roles:
            for company, other in ((COMPANY_A, COMPANY_B), (COMPANY_B, COMPANY_A)):
                row = actor(role, company, projects)
                with self.subTest(role=role, company=company):
                    for chain, (sql, params) in self.chains(row).items():
                        self.assertNotIn(other, company_params(params), chain)
                        if role == "поставщик" or (role in ("прораб", "мастер") and chain == "finance"):
                            self.assertEqual(sql, "FALSE", chain)
                        else:
                            self.assertIn(company, company_params(params), chain)

    def test_supplier_offer_stays_on_the_request_company(self):
        sql, _params = supplier_offer_visibility_filter([41], 15)
        self.assertIn("scoped_request.company_id=supplier_offers.company_id", sql)
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "SELECT status, items_json FROM supply_requests WHERE id=%s AND company_id=%s",
            source,
        )
        self.assertNotIn("company_id=%s OR %s IS NULL", source)


class TwoClientProjectDocumentTests(unittest.TestCase):
    def test_same_project_name_does_not_cross_and_a_foreign_id_is_excluded(self):
        projects = [
            {"id": 1, "company_id": COMPANY_A, "name": PROJECT},
            {"id": 2, "company_id": COMPANY_B, "name": PROJECT},
        ]
        documents = [
            {"id": 11, "company_id": COMPANY_A, "project_id": 1, "project_name": PROJECT},
            {"id": 12, "company_id": COMPANY_B, "project_id": 2, "project_name": PROJECT},
            {"id": 13, "company_id": None, "project_id": None, "project_name": PROJECT},
        ]
        for company, own_project, own_document, foreign_document in (
            (COMPANY_A, 1, 11, 12),
            (COMPANY_B, 2, 12, 11),
        ):
            row = actor("директор", company)
            _sql, params = project_visibility_filter([row], FULL_PROJECT_ROLES)
            visible_projects = [item for item in projects if item["company_id"] in company_params(params)]
            self.assertEqual([item["id"] for item in visible_projects], [own_project])
            doc_sql, doc_params = project_visibility([row], DOCUMENT_ROLES, names_for)
            self.assertIn("p.company_id=%s", doc_sql)
            visible_documents = [
                item for item in documents
                if item["company_id"] in company_params(doc_params)
            ]
            self.assertEqual([item["id"] for item in visible_documents], [own_document])
            self.assertNotIn(foreign_document, [item["id"] for item in visible_documents])
            self.assertNotIn(13, [item["id"] for item in visible_documents])


class PaymentIsolationTests(unittest.TestCase):
    def test_direct_payment_and_brigade_and_requisites_stay_in_one_company(self):
        self.assertEqual(reversal_company_id(COMPANY_A, COMPANY_A, 1), COMPANY_A)
        with self.assertRaises(HTTPException):
            reversal_company_id(COMPANY_B, COMPANY_A, 1)
        with self.assertRaises(HTTPException):
            reversal_company_id(COMPANY_A, None, 2)
        sql, params = brigade_contract_visibility_filter(
            [actor("директор", COMPANY_A)],
            allowed_roles=FINANCE_ROLES,
            full_view_roles=FINANCE_ROLES,
        )
        self.assertIn("bc.company_id=%s", sql)
        self.assertEqual(company_params(params), [COMPANY_A])
        settlement = (ROOT / "backend" / "features" / "work_material_accounting" / "settlement.py").read_text(encoding="utf-8")
        self.assertIn("INSERT INTO work_contract_act_payments(payment_id,act_id,company_id,operation_id)", settlement)
        self.assertIn("WHERE a.contract_id=%s AND a.company_id=%s", settlement)

    def test_requisites_are_read_for_the_selected_company_only(self):
        class App:
            def __init__(self):
                self.routes = {}
            def get(self, path):
                return self._register("GET", path)
            def post(self, path):
                return self._register("POST", path)
            def _register(self, method, path):
                def decorate(handler):
                    self.routes[(method, path)] = handler
                    return handler
                return decorate

        class Cursor:
            def __init__(self):
                self.calls = []
            def execute(self, sql, params=()):
                self.calls.append((" ".join(sql.split()), tuple(params)))
            def fetchone(self):
                return {"company_id": COMPANY_A, "full_name": "Альянс", "inn": "1", "kpp": "", "ogrn": "",
                        "legal_address": "", "actual_address": "", "phone": "", "email": "",
                        "director_name": "", "director_position": "", "basis": "",
                        "bank_name": "", "bik": "", "rs": "", "ks": "", "short_name": "", "id": 1}
            def close(self):
                pass

        class Conn:
            def __init__(self, cursor):
                self.cursor_obj = cursor
            def cursor(self, **_kwargs):
                return self.cursor_obj
            def close(self):
                pass

        cursor = Cursor()
        app = App()
        register_company_requisites_module(app, {
            "get_db": lambda: Conn(cursor),
            "get_current_user": lambda: {},
            "resolve_work_company_context": lambda *args, **kwargs: {"mode": "company", "companyId": COMPANY_A},
            "effective_company_actors": lambda user, ctx: [],
            "positive_int_or_none": lambda value: int(value) if value else None,
            "finance_roles": FINANCE_ROLES,
        })
        app.routes[("GET", "/company-requisites")](x_company_id=str(COMPANY_B), x_company_mode="company", _current_user={"id": 1})
        _sql, params = cursor.calls[-1]
        self.assertEqual(params, (COMPANY_A,))
        self.assertNotIn(COMPANY_B, params)


class NotificationAuditTests(unittest.TestCase):
    def test_audit_and_lead_alerts_exclude_the_other_company_and_platform_rows(self):
        self.assertEqual(_allowed_company_ids([actor("директор", COMPANY_A)], AUDIT_ROLES), [COMPANY_A])
        self.assertEqual(_allowed_company_ids([actor("прораб", COMPANY_A, (PROJECT,))], AUDIT_ROLES), [])
        self.assertEqual(_allowed_company_ids([actor("поставщик", COMPANY_A)], AUDIT_ROLES), [])
        audit = (ROOT / "backend" / "features" / "audit_ownership" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("owner_scope='company'", audit)
        self.assertIn("company_id = ANY(%s)", audit)

        class Cursor:
            def __init__(self):
                self.calls = []
            def execute(self, sql, params=()):
                self.calls.append(sql)

        cursor = Cursor()
        queued = enqueue_lead_owner_notification(
            cursor, company_id=COMPANY_B, lead_id=4,
            environ={"LEAD_NOTIFY_TELEGRAM_CHAT_ID": "1", "LEAD_NOTIFY_COMPANY_ID": str(COMPANY_A)},
        )
        self.assertFalse(queued)
        self.assertEqual(cursor.calls, [])

    def test_chat_photos_follow_one_project_company(self):
        plan = plan_chat_owners(
            [
                {"id": 1, "company_id": COMPANY_A, "name": PROJECT},
                {"id": 2, "company_id": COMPANY_B, "name": PROJECT},
            ],
            [{"id": 9, "company_id": None, "project_name": PROJECT}],
        )
        self.assertEqual(plan["assignments"], [])
        unique = plan_chat_owners(
            [{"id": 1, "company_id": COMPANY_A, "name": "Склад"}],
            [{"id": 4, "company_id": None, "project_name": "Склад"}],
        )
        self.assertEqual(unique["assignments"], [{"id": 4, "company_id": COMPANY_A}])
        chat = (ROOT / "backend" / "features" / "project_chat" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("company_id=%s", chat)
        self.assertIn("INSERT INTO project_chat (project_name,company_id,", chat)


if __name__ == "__main__":
    unittest.main()
