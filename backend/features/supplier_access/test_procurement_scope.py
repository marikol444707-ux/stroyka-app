"""Regression proofs for the existing supplier recommendation endpoints."""

import ast
import os
from pathlib import Path
from typing import Optional
import unittest

from fastapi import Depends, Header, HTTPException
import psycopg2.extras
from backend.features.supplier_access.procurement_scope import (
    authorize_procurement_document, procurement_read_cursor,
)


MAIN = Path(__file__).resolve().parents[2] / "main.py"
NAMES = ("suggest_suppliers_for_request", "compare_kp_for_request")


class Cursor:
    def __init__(self, company_id=2, populated=False):
        self.company_id = company_id
        self.populated = populated
        self.calls = []
        self.closed = False

    def execute(self, query, params=()):
        self.calls.append((" ".join(query.split()), params))

    def fetchone(self):
        return {"id": 7, "company_id": self.company_id, "material_name": "Кабель",
                "category": "Электрика", "project": "Одинаковое имя", "work_package": "Основная",
                "quantity": 10, "unit": "м"}

    def fetchall(self):
        if self.populated:
            query, params = self.calls[-1]
            if "FROM company_supplier_links" in query:
                return [{"id": 10, "name": "Свой поставщик", "category": "Электрика",
                         "specialization": "", "rating": 2, "companySupplierLinkId": 20}]
            if "FROM suppliers" in query:
                return [{"id": 99, "name": "Чужая связь", "rating": 5, "specialization": ""}]
            if "FROM supply_history" in query:
                return [{"supplier_id": 10, "deliveries": 1 if "company_id=%s" in query else 200}]
            if "FROM supplier_offers" in query:
                if "price_per_unit" not in query:
                    return []
                ids = [10, 11] if "o.company_id=%s" in query else [10, 11, 99]
                return [{"id": identity, "supplier_id": identity, "supplier_name": "Поставщик " + str(identity),
                         "price_per_unit": 100, "total_price": 1000, "delivery_days": 3,
                         "payment_terms": "По факту", "vat_included": True, "valid_until": None,
                         "supplier_message": "", "rating": 2} for identity in ids]
        return []

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.autocommit = True
        self.closed = False
        self.rollbacks = 0

    def cursor(self, **kwargs):
        return self.cur

    def close(self):
        self.closed = True

    def rollback(self):
        self.rollbacks += 1


def load_routes(connection, *, package_allowed=True):
    def resolve_actor(cur, user, company_id, mode, **kwargs):
        if not company_id:
            raise HTTPException(409, "Компания заявки не определена")
        if company_id != user["company_id"]:
            raise HTTPException(403, "Компания недоступна")
        return {"companyId": company_id}, {**user, "role": "прораб"}

    namespace = {
        "Optional": Optional, "Depends": Depends, "Header": Header,
        "HTTPException": HTTPException, "psycopg2": psycopg2,
        "os": os, "YANDEX_API_KEY": "", "YANDEX_FOLDER_ID": "",
        "generate_supply_kp_comparison": lambda *args, **kwargs: "Сравнение своих КП",
        "SUPPLY_INTERNAL_ROLES": ("директор", "прораб"),
        "PLATFORM_STAFF_ROLES": (), "CLIENT_ACCOUNT_ROLES": (),
        "PACKAGE_LIMIT_ROLES": ("прораб",), "get_current_user": lambda: {},
        "require_roles": lambda *args: (lambda: {}), "get_db": lambda: connection,
        "authorize_procurement_document": authorize_procurement_document,
        "procurement_read_cursor": procurement_read_cursor,
        "resolve_resource_company_actor": resolve_actor,
        "require_project_access": lambda *args: None,
        "require_project_or_warehouse_access": lambda *args: None,
        "has_package_access": lambda *args: package_allowed,
    }
    functions = [node for node in ast.parse(MAIN.read_text()).body
                 if isinstance(node, ast.FunctionDef) and node.name in NAMES]
    for node in functions:
        node.decorator_list = []
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace


class ProcurementScopeTest(unittest.TestCase):
    def test_rating_and_delivery_history_never_prove_material_capability(self):
        connection = Connection(Cursor(company_id=1, populated=True))
        result = load_routes(connection)[NAMES[0]](
            7, current_user={"id": 1, "role": "директор", "company_id": 1},
        )
        self.assertEqual(result["aiRecommendedCount"], 0)
        self.assertTrue(all(row.get("capabilityStatus") == "not_checked" for row in result["suppliers"]))
        self.assertTrue(all(row["aiRecommend"] is False for row in result["suppliers"]))

    def test_authorized_reads_use_only_company_links_history_and_offers(self):
        for name in NAMES:
            with self.subTest(route=name):
                connection = Connection(Cursor(company_id=1, populated=True))
                result = load_routes(connection)[name](
                    7, current_user={"id": 1, "role": "директор", "company_id": 1},
                )
                if name == NAMES[0]:
                    self.assertEqual([row["id"] for row in result["suppliers"]], [10])
                    self.assertEqual(result["suppliers"][0]["deliveriesCount"], 1)
                    self.assertEqual(result["suppliers"][0]["rating"], 2)
                else:
                    self.assertEqual({row["offerId"] for row in result["ranking"]}, {10, 11})
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.closed)
                self.assertTrue(connection.cur.closed)
                self.assertFalse(any(query.startswith(("INSERT", "UPDATE", "DELETE", "ALTER"))
                                     for query, _ in connection.cur.calls))

    def test_foreign_company_with_same_project_name_is_denied_before_supplier_reads(self):
        for name in NAMES:
            with self.subTest(route=name):
                cursor = Cursor(company_id=2)
                connection = Connection(cursor)
                route = load_routes(connection)[name]
                with self.assertRaises(HTTPException) as error:
                    route(7, current_user={"id": 1, "role": "директор", "company_id": 1})
                self.assertEqual(error.exception.status_code, 403)
                self.assertFalse(any("FROM suppliers" in query or "FROM supplier_offers" in query
                                     for query, _ in cursor.calls))
                self.assertTrue(connection.closed)
                self.assertTrue(cursor.closed)

    def test_missing_company_and_forbidden_package_fail_closed(self):
        for company_id, package_allowed, expected in ((None, True, 409), (1, False, 403)):
            for name in NAMES:
                with self.subTest(route=name, expected=expected):
                    connection = Connection(Cursor(company_id))
                    route = load_routes(connection, package_allowed=package_allowed)[name]
                    with self.assertRaises(HTTPException) as error:
                        route(7, current_user={"id": 1, "role": "директор", "company_id": 1})
                    self.assertEqual(error.exception.status_code, expected)
                    self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
