import unittest
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from backend.features.company_context.service import (
    company_id_scope_filter,
    effective_company_actors,
)
from backend.features.inventory.routes import register_inventory_module


class Tool(BaseModel):
    name: str
    inventoryNumber: str = ""
    cost: float = 0
    status: str = "На складе"
    location: str = "Основной склад"
    project: str = ""
    masterId: Optional[int] = None
    masterName: str = ""
    issueType: str = ""
    photoUrl: str = ""
    notes: str = ""


class History(BaseModel):
    toolId: int
    toolName: str = ""
    action: str = "Проверка"
    fromLocation: str = ""
    toLocation: str = ""
    masterName: str = ""
    project: str = ""
    issueType: str = ""
    condition: str = ""
    date: str = ""
    createdBy: str = ""


class Inventory(BaseModel):
    project: str
    date: str = "2026-11-21"
    createdBy: str = "Анна"
    notes: str = ""


class InventoryItem(BaseModel):
    inventoryId: int
    materialName: str = "Цемент"
    unit: str = "шт"
    expected: float = 1
    actual: float = 1
    difference: float = 0
    notes: str = ""


class MemoryCursor:
    def __init__(self, tools=(), history=(), inventory=(), items=(), projects=()):
        self.tools = list(tools)
        self.history = list(history)
        self.inventory = list(inventory)
        self.items = list(items)
        self.projects = list(projects)
        self.calls = []
        self.rowcount = 0
        self._one = None
        self._all = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        bound = tuple(params)
        self.calls.append((normalized, bound))
        self.rowcount = 0
        self._one = None
        self._all = []
        if "to_regclass" in normalized:
            self._one = {"present": False, "name": None}
            return
        if "FROM projects WHERE name=%s" in normalized:
            name = bound[0]
            self._all = [row for row in self.projects if row["name"] == name]
            return
        if "FROM tools WHERE id=%s AND company_id=%s" in normalized:
            self._one = self._match(self.tools, bound[0], bound[1])
            return
        if "FROM tools WHERE TRUE" in normalized:
            self._all = self._scoped(self.tools, normalized, bound)
            return
        if normalized.startswith("UPDATE tools"):
            self.rowcount = 1 if self._match(self.tools, bound[-2], bound[-1]) else 0
            return
        if "DELETE FROM tool_history" in normalized or "DELETE FROM tools" in normalized:
            self.rowcount = 1
            return
        if "INSERT INTO tools" in normalized or "INSERT INTO tool_history" in normalized or "INSERT INTO inventory" in normalized or "INSERT INTO inventory_items" in normalized:
            self._one = {"id": 100, "company_id": bound[-2] if "inventory_items" not in normalized else bound[-2]}
            if "INSERT INTO tools" in normalized:
                self._one = {"id": 100, "company_id": bound[-2], "project_id": bound[-1]}
            elif "INSERT INTO tool_history" in normalized:
                self._one = {"id": 101, "company_id": bound[-2], "project_id": bound[-1]}
            elif "INSERT INTO inventory " in normalized:
                self._one = {"id": 102, "company_id": bound[-2], "project_id": bound[-1]}
            else:
                self._one = {"id": 103, "company_id": bound[-2], "project_id": bound[-1]}
            return
        if "FROM tool_history WHERE TRUE" in normalized:
            self._all = self._scoped(self.history, normalized, bound)
            return
        if "FROM inventory WHERE TRUE" in normalized:
            self._all = self._scoped(self.inventory, normalized, bound)
            return
        if "FROM inventory WHERE id=%s AND company_id=%s" in normalized:
            self._one = self._match(self.inventory, bound[0], bound[1])
            return
        if normalized.startswith("UPDATE inventory"):
            self.rowcount = 1 if self._match(self.inventory, bound[-2], bound[-1]) else 0
            return
        if "DELETE FROM inventory_items" in normalized or "DELETE FROM inventory " in normalized:
            self.rowcount = 1
            return
        if "FROM inventory_items WHERE inventory_id=%s AND company_id=%s" in normalized:
            inventory_id, company_id = bound
            self._all = [
                row for row in self.items
                if row.get("inventory_id") == inventory_id and row.get("company_id") == company_id
            ]
            return

    def _match(self, rows, row_id, company_id):
        return next((row for row in rows if row.get("id") == row_id and row.get("company_id") == company_id), None)

    def _scoped(self, rows, sql, params):
        if "company_id=%s" in sql:
            company_id = params[0]
            return [row for row in rows if row.get("company_id") == company_id]
        if "company_id = ANY(%s)" in sql:
            allowed = set(params[0])
            return [row for row in rows if row.get("company_id") in allowed]
        return list(rows)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)

    def close(self):
        pass


class MemoryConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = True
        self.committed = False
        self.rolled_back = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def require_project_access(user, project):
    if project not in (user.get("assignedProjects") or []):
        raise HTTPException(status_code=403, detail="Нет доступа к объекту")


def company_context(company_id, role="директор"):
    return {
        "mode": "company",
        "companyId": company_id,
        "company_id": company_id,
        "companyIds": [company_id],
        "role": role,
        "effectiveRole": role,
        "active": True,
        "companyActive": True,
        "assignedProjects": ["Склад"],
    }


def build(cursor):
    app_routes = {}
    connection = MemoryConnection(cursor)

    class App:
        def get(self, path):
            return self._register("GET", path)

        def post(self, path):
            return self._register("POST", path)

        def put(self, path):
            return self._register("PUT", path)

        def delete(self, path):
            return self._register("DELETE", path)

        def _register(self, method, path):
            def decorator(handler):
                app_routes[(method, path)] = handler
                return handler
            return decorator

    def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
        if x_company_mode == "all_companies":
            if action != "read":
                raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")
            return {
                "mode": "all_companies",
                "companyIds": [2, 4],
                "companies": [company_context(2), company_context(4)],
            }
        selected = int(x_company_id or 0)
        if selected not in (1, 2, 4):
            raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")
        role = user.get("role") if user.get("role") in ("директор", "главный_инженер") else "директор"
        return company_context(selected, role)

    def require_roles(*_roles):
        def dependency():
            return {}
        return dependency

    register_inventory_module(App(), {
        "get_db": lambda: connection,
        "require_roles": require_roles,
        "resolve_work_company_context": resolve,
        "effective_company_actors": effective_company_actors,
        "company_id_scope_filter": company_id_scope_filter,
        "can_see_all_company_data": lambda user: (user or {}).get("role") in ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
        "require_project_access": require_project_access,
        "user_project_names": lambda user: list(user.get("assignedProjects") or []),
        "warehouse_roles": ("директор", "зам_директора", "кладовщик", "снабженец", "прораб"),
        "project_document_roles": ("директор", "кладовщик", "прораб", "мастер"),
        "worker_execution_roles": ("мастер", "субподрядчик", "бригадир"),
        "tool_model": Tool,
        "tool_history_model": History,
        "inventory_model": Inventory,
        "inventory_item_model": InventoryItem,
    })
    return app_routes, connection


def director(company_id="2"):
    return {"id": 7, "role": "директор", "name": "Анна"}, {"x_company_id": company_id, "x_company_mode": "company"}


def sample_cursor():
    return MemoryCursor(
        tools=[
            {"id": 1, "company_id": 2, "project": "Склад", "name": "Дрель A", "owner_scope": "project", "project_id": 12, "location": "Склад", "master_id": None, "master_name": ""},
            {"id": 2, "company_id": 4, "project": "Склад", "name": "Дрель B", "owner_scope": "project", "project_id": 99, "location": "Склад", "master_id": None, "master_name": ""},
            {"id": 3, "company_id": None, "project": "Склад", "name": "Старая", "owner_scope": None, "project_id": None, "location": "Склад", "master_id": None, "master_name": ""},
        ],
        history=[
            {"id": 11, "company_id": 2, "tool_id": 1, "project": "Склад"},
            {"id": 12, "company_id": 4, "tool_id": 2, "project": "Склад"},
            {"id": 13, "company_id": None, "tool_id": 3, "project": "Склад"},
        ],
        inventory=[
            {"id": 21, "company_id": 2, "project": "Склад", "owner_scope": "project", "project_id": 12},
            {"id": 22, "company_id": 4, "project": "Склад", "owner_scope": "project", "project_id": 99},
            {"id": 23, "company_id": None, "project": "Склад", "owner_scope": None, "project_id": None},
        ],
        items=[
            {"id": 31, "inventory_id": 21, "company_id": 2, "material_name": "Своё"},
            {"id": 32, "inventory_id": 22, "company_id": 4, "material_name": "Чужое"},
        ],
        projects=[
            {"id": 12, "company_id": 2, "name": "Склад"},
            {"id": 99, "company_id": 4, "name": "Склад"},
            {"id": 13, "company_id": 2, "name": "Склад"},
        ],
    )


class InventoryTenantRouteTests(unittest.TestCase):
    def test_tool_list_hides_the_other_company_and_unowned_rows(self):
        cursor = sample_cursor()
        routes, _connection = build(cursor)
        user, scope = director()
        rows = routes[("GET", "/tools")](current_user=user, **scope)
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertNotIn("IS NULL", sql)
        self.assertEqual(params[0], 2)
        self.assertEqual([row["id"] for row in rows], [1])

    def test_all_companies_read_lists_only_member_companies(self):
        cursor = sample_cursor()
        routes, _connection = build(cursor)
        rows = routes[("GET", "/tools")](
            current_user={"id": 7, "role": "директор", "name": "Анна"},
            x_company_mode="all_companies",
        )
        sql, params = cursor.calls[0]
        self.assertIn("company_id = ANY(%s)", sql)
        self.assertEqual(params[0], [2, 4])
        self.assertEqual(sorted(row["id"] for row in rows), [1, 2])

    def test_same_project_name_is_stored_for_the_selected_company(self):
        cursor = MemoryCursor(projects=[{"id": 12, "company_id": 2, "name": "Склад"}, {"id": 99, "company_id": 4, "name": "Склад"}])
        routes, connection = build(cursor)
        user, scope = director("2")
        routes[("POST", "/tools")](Tool(name="Дрель", project="Склад"), current_user=user, **scope)
        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO tools"))
        self.assertEqual(insert[1][-3:], ("project", 2, 12))
        self.assertNotIn(99, insert[1])
        self.assertNotIn(4, insert[1][-3:])
        self.assertTrue(connection.committed)

    def test_project_from_another_company_is_rejected_before_insert(self):
        cursor = MemoryCursor(projects=[{"id": 99, "company_id": 4, "name": "Склад"}])
        routes, connection = build(cursor)
        user, scope = director("2")
        with self.assertRaises(HTTPException) as error:
            routes[("POST", "/tools")](Tool(name="Дрель", project="Склад"), current_user=user, **scope)
        self.assertEqual(error.exception.status_code, 403)
        self.assertFalse(any(call[0].startswith("INSERT") for call in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_ambiguous_project_inside_the_company_is_rejected(self):
        cursor = MemoryCursor(projects=[
            {"id": 12, "company_id": 2, "name": "Склад"},
            {"id": 13, "company_id": 2, "name": "Склад"},
        ])
        routes, _connection = build(cursor)
        user, scope = director()
        with self.assertRaises(HTTPException) as error:
            routes[("POST", "/tools")](Tool(name="Дрель", project="Склад"), current_user=user, **scope)
        self.assertEqual(error.exception.status_code, 403)

    def test_update_and_delete_of_another_company_tool_are_not_found(self):
        for method, path in (("PUT", "/tools/{tool_id}"), ("DELETE", "/tools/{tool_id}")):
            with self.subTest(method=method):
                cursor = sample_cursor()
                routes, connection = build(cursor)
                user, scope = director("2")
                kwargs = {"tool": Tool(name="Чужая")} if method == "PUT" else {}
                with self.assertRaises(HTTPException) as error:
                    routes[(method, path)](tool_id=2, current_user=user, **scope, **kwargs)
                self.assertEqual(error.exception.status_code, 404)
                self.assertFalse(any(call[0].startswith(("UPDATE", "DELETE")) for call in cursor.calls))
                self.assertTrue(connection.rolled_back)

    def test_update_and_delete_keep_the_selected_company(self):
        cursor = sample_cursor()
        routes, connection = build(cursor)
        user, scope = director("2")
        routes[("PUT", "/tools/{tool_id}")](tool_id=1, tool=Tool(name="Дрель A", project=""), current_user=user, **scope)
        update = next(call for call in cursor.calls if call[0].startswith("UPDATE tools"))
        self.assertIn("company_id=%s", update[0])
        self.assertEqual(update[1][-2:], (1, 2))
        self.assertTrue(connection.committed)

        cursor = sample_cursor()
        routes, connection = build(cursor)
        routes[("DELETE", "/tools/{tool_id}")](tool_id=1, current_user=user, **scope)
        deletes = [call for call in cursor.calls if call[0].startswith("DELETE")]
        self.assertEqual(len(deletes), 2)
        self.assertTrue(all("company_id=%s" in sql and params[-1] == 2 for sql, params in deletes))
        self.assertTrue(connection.committed)

    def test_history_list_and_create_stay_inside_the_selected_company(self):
        cursor = sample_cursor()
        routes, _connection = build(cursor)
        user, scope = director()
        rows = routes[("GET", "/tool-history")](current_user=user, **scope)
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertNotIn("IS NULL", sql)
        self.assertEqual(params[0], 2)
        self.assertEqual([row["id"] for row in rows], [11])

        cursor = sample_cursor()
        routes, connection = build(cursor)
        with self.assertRaises(HTTPException) as error:
            routes[("POST", "/tool-history")](
                History(toolId=2, toolName="Дрель B", action="Выдача", project="Склад"),
                current_user=user, **scope,
            )
        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(any(call[0].startswith("INSERT") for call in cursor.calls))

        cursor = sample_cursor()
        routes, connection = build(cursor)
        routes[("POST", "/tool-history")](
            History(toolId=1, toolName="Подмена", action="Выдача", project="Склад"),
            current_user=user, **scope,
        )
        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO tool_history"))
        self.assertEqual(insert[1][-3:], ("project", 2, 12))
        self.assertNotIn(4, insert[1])
        self.assertTrue(connection.committed)

    def test_inventory_list_update_delete_and_items_hide_the_other_company(self):
        cursor = sample_cursor()
        routes, _connection = build(cursor)
        user, scope = director()
        rows = routes[("GET", "/inventory")](current_user=user, **scope)
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertNotIn("IS NULL", cursor.calls[0][0])
        self.assertEqual([row["id"] for row in rows], [21])

        for method, path in (("PUT", "/inventory/{inventory_id}"), ("DELETE", "/inventory/{inventory_id}")):
            with self.subTest(method=method):
                cursor = sample_cursor()
                routes, _connection = build(cursor)
                kwargs = {"data": {"status": "Закрыта"}} if method == "PUT" else {}
                with self.assertRaises(HTTPException) as error:
                    routes[(method, path)](inventory_id=22, current_user=user, **scope, **kwargs)
                self.assertEqual(error.exception.status_code, 404)
                self.assertFalse(any(call[0].startswith(("UPDATE", "DELETE")) for call in cursor.calls))

        cursor = sample_cursor()
        routes, connection = build(cursor)
        routes[("PUT", "/inventory/{inventory_id}")](
            inventory_id=21, data={"status": "Закрыта"}, current_user=user, **scope,
        )
        update = next(call for call in cursor.calls if call[0].startswith("UPDATE inventory"))
        self.assertEqual(update[1], ("Закрыта", 21, 2))

        cursor = sample_cursor()
        routes, _connection = build(cursor)
        with self.assertRaises(HTTPException) as error:
            routes[("GET", "/inventory/{inventory_id}/items")](inventory_id=22, current_user=user, **scope)
        self.assertEqual(error.exception.status_code, 404)

        cursor = sample_cursor()
        routes, _connection = build(cursor)
        items = routes[("GET", "/inventory/{inventory_id}/items")](inventory_id=21, current_user=user, **scope)
        item_sql = next(call for call in cursor.calls if "inventory_items" in call[0])
        self.assertIn("company_id=%s", item_sql[0])
        self.assertEqual(item_sql[1], (21, 2))
        self.assertEqual([row["id"] for row in items], [31])

        cursor = sample_cursor()
        routes, _connection = build(cursor)
        with self.assertRaises(HTTPException) as error:
            routes[("POST", "/inventory-items")](
                InventoryItem(inventoryId=22), current_user=user, **scope,
            )
        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(any(call[0].startswith("INSERT") for call in cursor.calls))

    def test_original_company_still_sees_its_rows_and_a_newer_company_does_not(self):
        cursor = MemoryCursor(
            tools=[
                {"id": 1, "company_id": 1, "project": "Склад", "name": "Перфоратор", "owner_scope": "project", "project_id": 12, "location": "Склад", "master_id": None, "master_name": ""},
                {"id": 2, "company_id": 2, "project": "Склад", "name": "Новая дрель", "owner_scope": "project", "project_id": 20, "location": "Склад", "master_id": None, "master_name": ""},
            ],
            history=[
                {"id": 11, "company_id": 1, "tool_id": 1, "project": "Склад"},
                {"id": 12, "company_id": 2, "tool_id": 2, "project": "Склад"},
            ],
            inventory=[
                {"id": 21, "company_id": 1, "project": "Склад", "owner_scope": "project", "project_id": 12},
                {"id": 22, "company_id": 2, "project": "Склад", "owner_scope": "project", "project_id": 20},
            ],
        )
        routes, _connection = build(cursor)
        original = {"id": 1, "role": "директор", "name": "АльянсСтрой"}
        own_tools = routes[("GET", "/tools")](current_user=original, x_company_id="1", x_company_mode="company")
        own_history = routes[("GET", "/tool-history")](current_user=original, x_company_id="1", x_company_mode="company")
        own_inventory = routes[("GET", "/inventory")](current_user=original, x_company_id="1", x_company_mode="company")
        self.assertEqual([row["id"] for row in own_tools], [1])
        self.assertEqual([row["id"] for row in own_history], [11])
        self.assertEqual([row["id"] for row in own_inventory], [21])

        newer = {"id": 7, "role": "директор", "name": "Новый клиент"}
        foreign_tools = routes[("GET", "/tools")](current_user=newer, x_company_id="2", x_company_mode="company")
        foreign_history = routes[("GET", "/tool-history")](current_user=newer, x_company_id="2", x_company_mode="company")
        foreign_inventory = routes[("GET", "/inventory")](current_user=newer, x_company_id="2", x_company_mode="company")
        self.assertEqual([row["id"] for row in foreign_tools], [2])
        self.assertEqual([row["id"] for row in foreign_history], [12])
        self.assertEqual([row["id"] for row in foreign_inventory], [22])
        self.assertNotIn(1, [row["id"] for row in foreign_tools])

    def test_chief_engineer_deletes_only_the_selected_company_tool(self):
        user = {"id": 8, "role": "главный_инженер", "name": "Инженер"}
        scope = {"x_company_id": "2", "x_company_mode": "company"}
        cursor = sample_cursor()
        routes, connection = build(cursor)
        routes[("DELETE", "/tools/{tool_id}")](tool_id=1, current_user=user, **scope)
        deletes = [call for call in cursor.calls if call[0].startswith("DELETE")]
        self.assertEqual(len(deletes), 2)
        self.assertTrue(all(params[-1] == 2 for _sql, params in deletes))
        self.assertTrue(connection.committed)

        cursor = sample_cursor()
        routes, connection = build(cursor)
        with self.assertRaises(HTTPException) as error:
            routes[("DELETE", "/tools/{tool_id}")](tool_id=2, current_user=user, **scope)
        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(any(call[0].startswith("DELETE") for call in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_all_companies_cannot_create_or_move_a_tool(self):
        cursor = sample_cursor()
        routes, connection = build(cursor)
        with self.assertRaises(HTTPException) as error:
            routes[("POST", "/tools")](
                Tool(name="Общая"),
                current_user={"id": 7, "role": "директор", "name": "Анна"},
                x_company_mode="all_companies",
            )
        self.assertEqual(error.exception.status_code, 400)
        self.assertFalse(any(call[0].startswith("INSERT") for call in cursor.calls))
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
