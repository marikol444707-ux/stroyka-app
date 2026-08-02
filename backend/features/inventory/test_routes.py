import unittest

from fastapi import FastAPI
from pydantic import BaseModel

from .routes import register_inventory_module


class Payload(BaseModel):
    pass


class InventoryRouteRegistrationTests(unittest.TestCase):
    def test_registers_each_legacy_inventory_url_once(self):
        app = FastAPI()
        register_inventory_module(app, {
            "get_db": None,
            "require_roles": lambda *roles: (lambda: {}),
            "resolve_work_company_context": None,
            "effective_company_actors": None,
            "company_id_scope_filter": None,
            "can_see_all_company_data": None,
            "require_project_access": None,
            "user_project_names": None,
            "warehouse_roles": (),
            "project_document_roles": (),
            "worker_execution_roles": (),
            "tool_model": Payload,
            "tool_history_model": Payload,
            "inventory_model": Payload,
            "inventory_item_model": Payload,
        })

        actual = {(route.path, method) for route in app.routes for method in (route.methods or set())}
        expected = {
            ("/tools", "GET"), ("/tools", "POST"),
            ("/tools/{tool_id}", "PUT"), ("/tools/{tool_id}", "DELETE"),
            ("/tool-history", "GET"), ("/tool-history", "POST"),
            ("/inventory", "GET"), ("/inventory", "POST"),
            ("/inventory/{inventory_id}", "PUT"), ("/inventory/{inventory_id}", "DELETE"),
            ("/inventory/{inventory_id}/items", "GET"), ("/inventory/{inventory_id}/items", "POST"),
            ("/inventory-items", "POST"),
        }
        self.assertTrue(expected.issubset(actual))


if __name__ == "__main__":
    unittest.main()
