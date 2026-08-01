import unittest

from backend.features.supplier_offers.routes import SupplierOfferModel, register_supplier_offers_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


def build():
    app = FakeApp()
    deps = {name: (lambda *a, **k: None) for name in [
        "get_db", "get_current_user", "require_roles",
        "_require_supplier_offer_visibility", "_log_supplier_offer_event",
        "_ensure_supplier_offer_events_table", "_ensure_supply_request_recipients_table",
        "_ensure_supply_runtime_columns", "_find_existing_supplier_invoice_duplicate",
        "_find_supply_request_recipient", "_float_or_zero", "_json_list_or_empty",
        "_norm_base_unit", "_norm_key_text", "_normalize_supplier_ids",
        "_positive_int_or_none", "_resolve_work_company_context", "_supply_work_package",
        "current_supplier_ids", "has_package_access", "package_access_filter",
        "require_project_or_warehouse_access", "user_project_names", "supplier_group_scope_ids",
    ]}
    deps["require_roles"] = lambda *roles: (lambda: None)
    for name in ["SUPPLY_ROLES", "SUPPLY_INTERNAL_ROLES", "LEADERSHIP_ROLES",
                 "WORKER_EXECUTION_ROLES", "PACKAGE_LIMIT_ROLES", "PLATFORM_STAFF_ROLES",
                 "CLIENT_ACCOUNT_ROLES"]:
        deps[name] = ("директор",)
    deps["OFFERS_SELECT"] = "SELECT 1"
    deps["DELIVERY_SELECT"] = "SELECT 1"
    register_supplier_offers_module(app, deps)
    return app


class SupplierOffersRegistrationTest(unittest.TestCase):
    def test_all_six_urls_registered(self):
        app = build()
        for key in [("GET", "/supplier-offers"), ("GET", "/supplier-offers/{id}/history"),
                    ("POST", "/supplier-offers"), ("PUT", "/supplier-offers/{id}"),
                    ("POST", "/supplier-offers/{id}/create-invoice"),
                    ("POST", "/supplier-offers/{id}/ship")]:
            self.assertIn(key, app.routes)

    def test_model_fields(self):
        m = SupplierOfferModel(requestId=1, supplierId=2, pricePerUnit=10, totalPrice=100)
        self.assertEqual(m.deliveryDays, 0)
        self.assertEqual(m.notes, "")


if __name__ == "__main__":
    unittest.main()
