import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.company_context.service import company_id_scope_filter, effective_company_actors
from backend.features.checklist_items.routes import register_checklist_items_module
from backend.features.contracts.routes import ContractModel, register_contracts_module
from backend.features.material_aliases.routes import MaterialAliasModel, register_material_aliases_module
from backend.features.piecework.routes import PieceworkModel, register_piecework_module
from backend.features.project_checklists.routes import register_project_checklists_module
from backend.features.quality_journals.access import FIELDS, journal_operation


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


class MemoryCursor:
    def __init__(self, projects=(), rows=()):
        self.projects = list(projects)
        self.rows = list(rows)
        self.calls = []
        self.rowcount = 1
        self._one = None
        self._all = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        self._one = None
        self._all = []
        if "FROM projects WHERE name=%s" in normalized:
            name = params[0]
            self._all = [row for row in self.projects if row["name"] == name]
            return
        if "company_id=%s" in normalized and "SELECT" in normalized:
            company_id = params[-1]
            id_lookup = " WHERE id=%s" in normalized or "WHERE checklist_id=%s" in normalized
            matched = [
                row for row in self.rows
                if row.get("company_id") == company_id and (
                    not id_lookup or row.get("id") == params[0] or row.get("checklist_id") == params[0]
                )
            ]
            if "FROM project_checklists" in normalized and normalized.startswith("SELECT id,project_id"):
                self._all = [
                    (row["id"], row.get("project_id"), row.get("project_name"), "Чек", "", "В работе", "", "2026-11-21", row["company_id"])
                    for row in matched
                ]
            elif "FROM checklist_items" in normalized and normalized.startswith("SELECT"):
                self._all = [(row["id"], row.get("checklist_id"), "Пункт", False, "", "", 0) for row in matched]
                self._one = (matched[0]["checklist_id"],) if matched else None
            elif "SELECT project_name FROM project_checklists" in normalized:
                self._one = (matched[0]["project_name"],) if matched else None
            elif "owner_scope,company_id,project_id FROM project_checklists" in normalized:
                if matched:
                    row = matched[0]
                    self._one = (row["id"], row.get("project_name"), row.get("owner_scope"), row["company_id"], row.get("project_id"))
            else:
                self._one = matched[0] if matched else None
                self._all = matched
            self.rowcount = 1 if matched else 0
            return
        if normalized.startswith("INSERT") or normalized.startswith("UPDATE") or normalized.startswith("DELETE"):
            company_id = params[-1] if params else None
            self.rowcount = 1 if any(row.get("company_id") == company_id for row in self.rows) or normalized.startswith("INSERT") else 0
            if normalized.startswith("INSERT"):
                self._one = {"id": 100, "company_id": company_id, "project_id": params[-2] if len(params) > 1 else None,
                             "project_name": "", "alias_name": "Цемент", "canonical_name": "Цемент",
                             "canonical_unit": "", "source": "manual", "active": True, "updated_by": "", "updated_at": ""}
            return

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
        self.closed = False
        self.committed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def set_session(self, **_kwargs):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.closed = False

    def close(self):
        self.closed = True


def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
    if x_company_mode == "all_companies":
        if action != "read":
            raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")
        return {"mode": "all_companies", "companyIds": [1, 2], "companies": [company_context(1), company_context(2)]}
    selected = int(x_company_id or 0)
    if selected not in (1, 2):
        raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")
    role = user.get("role") or "директор"
    return company_context(selected, role)


def require_roles(*_roles):
    def dependency():
        return {}
    return dependency


def build_routes(register, cursor, **extra):
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

    deps = {
        "get_db": lambda: connection,
        "require_roles": require_roles,
        "get_current_user": lambda: {},
        "resolve_work_company_context": resolve,
        "effective_company_actors": effective_company_actors,
        "company_id_scope_filter": company_id_scope_filter,
        "can_see_all_company_data": lambda user: user.get("role") in ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
        "user_project_names": lambda user: user.get("assignedProjects") or ["Склад"],
        "require_project_access": lambda user, project: None if project in ("Склад", "", None) or user.get("role") == "директор" else (_ for _ in ()).throw(HTTPException(403, "Нет доступа к объекту")),
        "project_name_from_payload": lambda cur, data: data.get("projectName") or data.get("project") or "Склад",
        "require_work_journal_actor_access": lambda cur, journal_id, user: {"project": "Склад"},
        "lock_legacy_work_settlement": lambda cur: None,
        "require_legacy_work": lambda cur, ids: None,
        "contract_roles": ("директор", "мастер"),
        "create_roles": ("директор",),
        "delete_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "read_roles": ("директор", "прораб"),
        "write_roles": ("директор",),
        "journal_write_roles": ("директор", "прораб", "мастер"),
        "project_document_roles": ("директор",),
        "project_write_roles": ("директор",),
        "check_roles": ("директор",),
    }
    deps.update(extra)
    register(App(), deps)
    return app_routes


class CrossTenantFieldRecordTests(unittest.TestCase):
    def test_contract_list_update_and_delete_stay_in_the_selected_company(self):
        cursor = MemoryCursor(
            projects=[{"id": 12, "company_id": 1, "name": "Склад"}, {"id": 90, "company_id": 2, "name": "Склад"}],
            rows=[
                {"id": 1, "company_id": 1, "project": "Склад"},
                {"id": 2, "company_id": 2, "project": "Склад"},
            ],
        )
        routes = build_routes(register_contracts_module, cursor)
        own = routes[("GET", "/contracts")](
            _current_user={"id": 1, "role": "директор", "name": "АльянсСтрой"},
            x_company_id="1", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in own], [1])
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertEqual(params[-1], 1)
        foreign = routes[("GET", "/contracts")](
            _current_user={"id": 2, "role": "директор", "name": "Другая"},
            x_company_id="2", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in foreign], [2])
        routes[("POST", "/contracts")](
            ContractModel(masterId=3, masterName="Иван", contractNumber="1", project="Склад"),
            _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO contracts"))
        self.assertEqual(insert[1][-2], 1)
        self.assertEqual(insert[1][-1], 12)
        with self.assertRaises(HTTPException) as missing:
            routes[("DELETE", "/contracts/{id}")](
                id=2, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(missing.exception.status_code, 404)
        routes[("DELETE", "/contracts/{id}")](
            id=1, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        update = next(call for call in cursor.calls if call[0].startswith("UPDATE contracts"))
        self.assertIn("company_id=%s", update[0])
        self.assertEqual(update[1][-1], 1)

    def test_same_project_name_is_stored_on_the_selected_company_contract(self):
        cursor = MemoryCursor(projects=[{"id": 12, "company_id": 1, "name": "Склад"}, {"id": 90, "company_id": 2, "name": "Склад"}])
        routes = build_routes(register_contracts_module, cursor)
        routes[("POST", "/contracts")](
            ContractModel(masterId=3, masterName="Иван", contractNumber="1", project="Склад"),
            _current_user={"role": "директор"}, x_company_id="2", x_company_mode="company",
        )
        insert = cursor.calls[-1]
        self.assertEqual(insert[1][-2:], (2, 90))

    def test_piecework_list_and_delete_hide_the_other_company(self):
        cursor = MemoryCursor(rows=[
            {"id": 1, "company_id": 1, "project": "Склад", "work_journal_id": 4},
            {"id": 2, "company_id": 2, "project": "Склад", "work_journal_id": 8},
        ], projects=[{"id": 12, "company_id": 1, "name": "Склад"}])
        routes = build_routes(register_piecework_module, cursor)
        own = routes[("GET", "/piecework")](
            current_user={"id": 1, "role": "директор", "name": "АльянсСтрой"},
            x_company_id="1", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in own], [1])
        self.assertIn("company_id=%s", cursor.calls[-1][0])
        with self.assertRaises(HTTPException) as missing:
            routes[("DELETE", "/piecework/{id}")](
                id=2, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(missing.exception.status_code, 404)

    def test_checklist_and_items_do_not_cross_companies(self):
        cursor = MemoryCursor(
            projects=[{"id": 12, "company_id": 1, "name": "Склад"}, {"id": 90, "company_id": 2, "name": "Склад"}],
            rows=[
                {"id": 5, "company_id": 1, "project_name": "Склад", "owner_scope": "project", "project_id": 12, "checklist_id": 5},
                {"id": 6, "company_id": 2, "project_name": "Склад", "owner_scope": "project", "project_id": 90, "checklist_id": 6},
            ],
        )
        lists = build_routes(register_project_checklists_module, cursor)
        own = lists[("GET", "/project-checklists")](
            current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in own], [5])
        with self.assertRaises(HTTPException) as missing:
            lists[("DELETE", "/project-checklists/{id}")](
                id=6, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(missing.exception.status_code, 404)
        items = build_routes(register_checklist_items_module, cursor)
        listed = items[("GET", "/checklist-items/{checklist_id}")](
            checklist_id=5, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertTrue(all(call[1][-1] == 1 for call in cursor.calls if "checklist_items" in call[0] or "project_checklists" in call[0]))
        self.assertEqual(listed[0]["checklistId"], 5)
        with self.assertRaises(HTTPException) as foreign:
            items[("PUT", "/checklist-items/{id}")](
                id=6, data={"checked": True}, _current_user={"role": "директор"},
                x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(foreign.exception.status_code, 404)

    def test_material_alias_list_create_and_delete_use_the_selected_company(self):
        cursor = MemoryCursor(
            projects=[{"id": 12, "company_id": 1, "name": "Склад"}, {"id": 90, "company_id": 2, "name": "Склад"}],
            rows=[
                {"id": 1, "company_id": 1, "project_name": "Склад", "alias_name": "Цемент", "canonical_name": "Цемент",
                 "canonical_unit": "", "source": "manual", "active": True, "updated_by": "", "updated_at": ""},
                {"id": 2, "company_id": 2, "project_name": "Склад", "alias_name": "Чужой", "canonical_name": "Чужой",
                 "canonical_unit": "", "source": "manual", "active": True, "updated_by": "", "updated_at": ""},
            ],
        )
        routes = build_routes(register_material_aliases_module, cursor)
        own = routes[("GET", "/material-aliases")](
            project_name="Склад", current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in own], [1])
        routes[("POST", "/material-aliases")](
            MaterialAliasModel(projectName="Склад", aliasName="Песок", canonicalName="Песок"),
            current_user={"role": "директор", "name": "Анна"}, x_company_id="1", x_company_mode="company",
        )
        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO material_aliases"))
        self.assertEqual(insert[1][-2], 1)
        with self.assertRaises(HTTPException) as missing:
            routes[("DELETE", "/material-aliases/{id}")](
                id=2, current_user={"role": "директор", "name": "Анна"}, x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(missing.exception.status_code, 404)

    def test_original_company_still_sees_its_legacy_rows(self):
        cursor = MemoryCursor(rows=[
            {"id": 1, "company_id": 1, "project": "Склад"},
            {"id": 2, "company_id": 2, "project": "Склад"},
        ])
        contracts = build_routes(register_contracts_module, cursor)
        piecework = build_routes(register_piecework_module, cursor)
        original = {"id": 1, "role": "директор", "name": "АльянсСтрой"}
        own_contracts = contracts[("GET", "/contracts")](
            _current_user=original, x_company_id="1", x_company_mode="company",
        )
        own_piecework = piecework[("GET", "/piecework")](
            current_user=original, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in own_contracts], [1])
        self.assertEqual([row["id"] for row in own_piecework], [1])
        newer = {"id": 9, "role": "директор", "name": "Новый клиент"}
        foreign = contracts[("GET", "/contracts")](
            _current_user=newer, x_company_id="2", x_company_mode="company",
        )
        self.assertEqual([row["id"] for row in foreign], [2])


def journal_row(table, row_id, company_id, project_name):
    row = {field: "" for field in FIELDS[table]}
    row.update({
        "id": row_id, "company_id": company_id, "project_id": 12 if company_id == 1 else 90,
        "project_name": project_name, "status": "Активна", "quantity": 1, "cores_count": 1,
        "inspected": False, "ai_filled": False,
    })
    return row


class JournalCompanyScopeTests(unittest.TestCase):
    def operation(self, table, rows, company_id, **kwargs):
        cursor = MemoryCursor()
        seen = {}

        class Cursor(MemoryCursor):
            def execute(self, sql, params=()):
                normalized = " ".join(sql.split())
                self.calls.append((normalized, tuple(params)))
                self._one = {"id": 1}
                self._all = []
                if f"FROM {table}" in normalized:
                    company = params[0]
                    seen["company"] = company
                    seen["sql"] = normalized
                    self._all = [row for row in rows if row["company_id"] == company]
                    if kwargs.get("row_id") is not None:
                        self._all = [row for row in self._all if row["id"] == kwargs["row_id"]]

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        cursor = Cursor()
        connection = MemoryConnection(cursor)

        def get_db():
            return connection

        context = company_context(company_id)
        context.update(source="membership", membershipId=5)
        with patch("backend.features.quality_journals.access.resolve_request_company_context", return_value=context):
            result = journal_operation(
                {
                    "get_db": get_db,
                    "read_roles": ("директор",),
                    "write_roles": ("директор",),
                    "worker_roles": ("мастер",),
                    "visible_projects": lambda actor: None,
                    "package_filter": lambda actor, column: ("", []),
                    "platform_staff_roles": (),
                    "client_account_roles": (),
                },
                {"id": 7, "role": "директор"},
                {"X-Company-Id": str(company_id), "X-Company-Mode": "company"},
                table,
                **kwargs,
            )
        return result, seen

    def test_list_and_update_keep_same_named_projects_apart(self):
        rows = [
            journal_row("material_inspection_journal", 1, 1, "Склад"),
            journal_row("material_inspection_journal", 2, 2, "Склад"),
        ]
        own, seen = self.operation("material_inspection_journal", rows, 1, project_name="Склад")
        self.assertEqual([row["id"] for row in own], [1])
        self.assertIn("j.company_id=%s", seen["sql"])
        self.assertIn("p.company_id=j.company_id", seen["sql"])
        self.assertEqual(seen["company"], 1)
        with self.assertRaises(HTTPException) as missing:
            self.operation("material_inspection_journal", rows, 1, row_id=2, data={"remarks": "чужое"})
        self.assertEqual(missing.exception.status_code, 404)
        updated, _seen = self.operation("material_inspection_journal", rows, 1, row_id=1, data={"remarks": "своё"})
        self.assertEqual(updated, {"ok": True})

    def test_original_company_sees_its_journal_and_cable_rows(self):
        inspections = [journal_row("material_inspection_journal", 11, 1, "Лицей"), journal_row("material_inspection_journal", 12, 2, "Лицей")]
        cables = [journal_row("cable_journal", 21, 1, "Лицей"), journal_row("cable_journal", 22, 2, "Лицей")]
        own_inspections, _seen = self.operation("material_inspection_journal", inspections, 1)
        own_cables, _seen = self.operation("cable_journal", cables, 1)
        self.assertEqual([row["id"] for row in own_inspections], [11])
        self.assertEqual([row["companyId"] for row in own_inspections], [1])
        self.assertEqual([row["id"] for row in own_cables], [21])


if __name__ == "__main__":
    unittest.main()
