import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from backend.features.supplier_access.subscription_scope import (
    resolve_supplier_offer_subscription_context,
)


class SupplierOfferSubscriptionScopeTests(unittest.TestCase):
    def resolve(self, *, method="PUT", path="/supplier-offers/9", role="поставщик", row=None):
        cur = Mock()
        cur.fetchone.return_value = row or {"company_id": 7, "request_company_id": 7}
        require_visibility = Mock()
        result = resolve_supplier_offer_subscription_context(
            cur, {"id": 42, "role": role, "companyId": 999}, method, path,
            require_supplier_offer_visibility=require_visibility,
        )
        return result, cur, require_visibility

    def test_exact_offer_mutations_resolve_actual_owner_after_canonical_access_check(self):
        for method, path in (("PUT", "/supplier-offers/9"),
                             ("POST", "/supplier-offers/9/create-invoice"),
                             ("POST", "/supplier-offers/9/ship")):
            with self.subTest(method=method, path=path):
                result, cur, require_visibility = self.resolve(method=method, path=path)
                self.assertEqual(result, {"mode": "company", "companyId": 7})
                self.assertEqual(require_visibility.call_args.args[1:],
                                 (9, {"id": 42, "role": "поставщик", "companyId": 999}))
                self.assertEqual(cur.execute.call_args.args[1], (9,))

    def test_other_roles_methods_and_nearby_paths_keep_default_company_resolution(self):
        for overrides in ({"role": "директор"}, {"role": ""}, {"method": "GET"},
                          {"method": "DELETE"}, {"method": "POST"},
                          {"path": "/supplier-offers/9/history"},
                          {"path": "/supplier-offers/9/ship/extra", "method": "POST"},
                          {"path": "/supplier-offers"}, {"path": "/supplier-offers/0"},
                          {"path": "/supplier-invoices/9"}):
            with self.subTest(overrides=overrides):
                result, cur, require_visibility = self.resolve(**overrides)
                self.assertIsNone(result)
                require_visibility.assert_not_called()
                cur.execute.assert_not_called()

    def test_unauthorized_or_unlinked_supplier_is_denied_before_loading_owner(self):
        cur = Mock()
        require_visibility = Mock(side_effect=HTTPException(403, "Нет доступа к КП"))
        with self.assertRaises(HTTPException) as caught:
            resolve_supplier_offer_subscription_context(
                cur, {"id": 42, "role": "поставщик"}, "PUT", "/supplier-offers/9",
                require_supplier_offer_visibility=require_visibility,
            )
        self.assertEqual(caught.exception.status_code, 403)
        cur.execute.assert_not_called()

    def test_missing_invalid_or_mixed_company_chain_fails_closed(self):
        for row in (None, {"company_id": None, "request_company_id": 7},
                    {"company_id": 0, "request_company_id": 0},
                    {"company_id": 7, "request_company_id": 8}):
            with self.subTest(row=row):
                cur = Mock()
                cur.fetchone.return_value = row
                with self.assertRaises(HTTPException) as caught:
                    resolve_supplier_offer_subscription_context(
                        cur, {"id": 42, "role": "поставщик"}, "PUT", "/supplier-offers/9",
                        require_supplier_offer_visibility=Mock(),
                    )
                self.assertEqual(caught.exception.status_code, 409)

    def test_database_failure_propagates_to_fail_closed_middleware(self):
        cur = Mock()
        cur.execute.side_effect = RuntimeError("DB unavailable")
        with self.assertRaises(RuntimeError):
            resolve_supplier_offer_subscription_context(
                cur, {"id": 42, "role": "поставщик"}, "PUT", "/supplier-offers/9",
                require_supplier_offer_visibility=Mock(),
            )

    def test_runtime_registration_injects_existing_visibility_boundary(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / "main.py").read_text())
        registration = next(node.value for node in tree.body
                            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name)
                            and node.value.func.id == "register_subscription_read_only_middleware")
        deps = registration.args[1]
        resolver = next(value for key, value in zip(deps.keys, deps.values)
                        if isinstance(key, ast.Constant)
                        and key.value == "resolve_resource_subscription_context")
        self.assertIn("_require_supplier_offer_visibility", ast.unparse(resolver))
        self.assertIn("resolve_supplier_offer_subscription_context", ast.unparse(resolver))


if __name__ == "__main__":
    unittest.main()
