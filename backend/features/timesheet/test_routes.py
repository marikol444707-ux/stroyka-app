import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.features.company_context.service import (
    effective_company_actors,
    resolve_request_company_context,
)
from backend.features.timesheet.routes import TimesheetModel, register_timesheet_module


VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "прораб", "главный_инженер")
MANAGE_ROLES = ("директор", "зам_директора")
PLATFORM_ROLES = ("system_owner", "platform_admin", "platform_support", "billing_admin")
ACCOUNT_ROLES = ("account_owner", "account_admin")


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, effects=()):
        self.effects = list(effects)
        self.current = {}
        self.calls = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))
        self.current = self.effects.pop(0) if self.effects else {}
        self.rowcount = self.current.get("rowcount", -1)

    def fetchall(self):
        return list(self.current.get("rows", ()))

    def fetchone(self):
        return self.current.get("row")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def build(effects=(), context=None, actors=None, audit_calls=None):
    app = FakeApp()
    cursor = FakeCursor(effects)
    connection = FakeConnection(cursor)
    selected_context = context or {
        "mode": "company",
        "companyId": 10,
        "companyIds": [10],
        "role": "директор",
        "active": True,
        "companyActive": True,
    }
    selected_actors = actors if actors is not None else [
        {"companyId": 10, "role": "директор", "name": "Тест"}
    ]
    audits = audit_calls if audit_calls is not None else []

    def resolve_context(_cur, _user, _requested, _action, **_headers):
        return selected_context

    register_timesheet_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {"id": 1, "name": "Тест", "role": "подмена"},
        "resolve_work_company_context": resolve_context,
        "effective_company_actors": lambda _user, _context: selected_actors,
        "staff_view_roles": VIEW_ROLES,
        "staff_manage_roles": MANAGE_ROLES,
        "log_audit": lambda *args, **kwargs: audits.append((args, kwargs)),
    })
    return app, connection, cursor, audits


def call(handler, *args, **kwargs):
    kwargs.setdefault("x_company_id", "10")
    kwargs.setdefault("x_company_mode", "company")
    kwargs.setdefault("current_user", {"id": 1, "name": "Тест", "role": "подмена"})
    return handler(*args, **kwargs)


class TimesheetRoutesTest(unittest.TestCase):
    def test_registers_same_urls_without_global_role_gate(self):
        app, _conn, _cursor, _audits = build()
        self.assertEqual(set(app.routes), {
            ("GET", "/timesheet/{staff_id}"),
            ("POST", "/timesheet"),
            ("GET", "/timesheet"),
        })
        source = Path(register_timesheet_module.__code__.co_filename).read_text(encoding="utf-8")
        self.assertNotIn("require_roles", source)

    def test_list_joins_verified_staff_of_selected_company(self):
        app, conn, cursor, _audits = build(effects=[{
            "rows": [{"staff_id": 101, "day": "2026-07-01"}],
        }])
        rows = call(app.routes[("GET", "/timesheet")])
        self.assertEqual(rows, [{"staffId": 101, "day": "2026-07-01"}])
        sql, params = cursor.calls[-1]
        self.assertIn("JOIN public.staff s ON s.id = t.staff_id", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertIn("s.company_id=%s", sql)
        self.assertNotIn("ANY", sql)
        self.assertEqual(params, (10,))
        self.assertTrue(conn.closed)

    def test_all_companies_list_uses_only_viewable_memberships(self):
        app, _conn, cursor, _audits = build(
            effects=[{"rows": []}],
            context={
                "mode": "all_companies",
                "companyId": None,
                "companyIds": [10, 20, 30],
                "readOnly": True,
            },
            actors=[
                {"companyId": 10, "role": "директор", "name": "Тест"},
                {"companyId": 20, "role": "мастер", "name": "Тест"},
                {"companyId": 30, "role": "бухгалтер", "name": "Тест"},
            ],
        )
        call(
            app.routes[("GET", "/timesheet")],
            x_company_id=None,
            x_company_mode="all_companies",
        )
        sql, params = cursor.calls[-1]
        self.assertIn("s.company_id = ANY(%s)", sql)
        self.assertEqual(params, ([10, 30],))
        self.assertNotIn(20, params[0])

    def test_staff_days_hide_another_company(self):
        app, _conn, cursor, _audits = build(effects=[
            {"rows": []},
            {"row": None},
        ])
        with self.assertRaises(HTTPException) as error:
            call(app.routes[("GET", "/timesheet/{staff_id}")], staff_id=201)
        self.assertEqual(error.exception.status_code, 404)
        day_sql, day_params = cursor.calls[0]
        staff_sql, staff_params = cursor.calls[1]
        self.assertIn("JOIN public.staff s", day_sql)
        self.assertEqual(day_params, (201, 10))
        self.assertIn("company_scope_verified IS TRUE", staff_sql)
        self.assertEqual(staff_params, (201, 10))

    def test_empty_days_stay_visible_for_own_staff(self):
        app, _conn, _cursor, _audits = build(effects=[
            {"rows": []},
            {"row": {"id": 101}},
        ])
        result = call(app.routes[("GET", "/timesheet/{staff_id}")], staff_id=101)
        self.assertEqual(result, {"days": []})

    def test_toggle_adds_day_through_verified_staff_and_audits_company(self):
        app, connection, cursor, audits = build(effects=[
            {"row": {"id": 101, "name": "Анна", "project": "Объект А"}},
            {"row": None},
            {"rowcount": 1},
        ])
        result = call(
            app.routes[("POST", "/timesheet")],
            TimesheetModel(staffId=101, day="2026-07-09"),
        )
        self.assertEqual(result, {"ok": True})
        self.assertFalse(connection.autocommit)
        self.assertEqual(connection.commits, 1)
        staff_sql, staff_params = cursor.calls[0]
        insert_sql, insert_params = cursor.calls[2]
        self.assertIn("company_id=%s", staff_sql)
        self.assertIn("company_scope_verified IS TRUE", staff_sql)
        self.assertIn("FOR SHARE", staff_sql)
        self.assertEqual(staff_params, (101, 10))
        self.assertIn("INSERT INTO public.timesheet", insert_sql)
        self.assertIn("FROM public.staff s", insert_sql)
        self.assertNotIn("VALUES (%s,%s)", insert_sql)
        self.assertEqual(insert_params, ("2026-07-09", 101, 10))
        args, kwargs = audits[0]
        self.assertEqual(args[2], "timesheet_add")
        self.assertIn("Анна", args[5])
        self.assertEqual(args[6], "Объект А")
        self.assertEqual(kwargs["company_id"], 10)
        self.assertEqual(kwargs["owner_scope"], "company")

    def test_toggle_removes_existing_day(self):
        app, connection, cursor, audits = build(effects=[
            {"row": {"id": 101, "name": "Анна", "project": "Объект А"}},
            {"row": {"id": 7}},
            {"rowcount": 1},
        ])
        call(
            app.routes[("POST", "/timesheet")],
            TimesheetModel(staffId=101, day="2026-07-01"),
        )
        delete_sql, delete_params = cursor.calls[2]
        self.assertIn("DELETE FROM public.timesheet", delete_sql)
        self.assertIn("USING public.staff s", delete_sql)
        self.assertEqual(delete_params, (101, "2026-07-01", 10))
        self.assertEqual(audits[0][0][2], "timesheet_remove")
        self.assertEqual(connection.commits, 1)

    def test_toggle_rejects_foreign_staff_before_write(self):
        app, connection, cursor, audits = build(effects=[{"row": None}])
        with self.assertRaises(HTTPException) as error:
            call(
                app.routes[("POST", "/timesheet")],
                TimesheetModel(staffId=201, day="2026-07-03"),
            )
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(len(cursor.calls), 1)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(audits, [])

    def test_accountant_can_read_but_cannot_toggle(self):
        app, connection, cursor, _audits = build(
            actors=[{"companyId": 10, "role": "бухгалтер", "name": "Бухгалтер"}],
        )
        with self.assertRaises(HTTPException) as error:
            call(
                app.routes[("POST", "/timesheet")],
                TimesheetModel(staffId=101, day="2026-07-01"),
            )
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_unscoped_write_context_is_rejected(self):
        app, connection, cursor, _audits = build(context={"mode": "all_companies", "companyIds": [10]})
        with self.assertRaises(HTTPException) as error:
            call(
                app.routes[("POST", "/timesheet")],
                TimesheetModel(staffId=101, day="2026-07-01"),
                x_company_id=None,
                x_company_mode="all_companies",
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(connection.commits, 0)

    def test_foreman_membership_can_toggle_inside_company(self):
        app, _conn, cursor, audits = build(
            effects=[
                {"row": {"id": 101, "name": "Анна", "project": "Объект А"}},
                {"row": None},
                {"rowcount": 1},
            ],
            actors=[{"companyId": 10, "role": "прораб", "name": "Прораб"}],
        )
        call(
            app.routes[("POST", "/timesheet")],
            TimesheetModel(staffId=101, day="2026-07-11"),
            current_user={"id": 5, "name": "Прораб", "role": "мастер"},
        )
        self.assertEqual(cursor.calls[0][1], (101, 10))
        self.assertEqual(audits[0][0][1], "прораб")


def membership(user_id, company_id, role, *, is_default=False):
    return {
        "membership_id": user_id * 100 + company_id,
        "user_id": user_id,
        "company_id": company_id,
        "staff_id": None,
        "platform_account_id": 1,
        "role": role,
        "assigned_projects": [],
        "assigned_packages": [],
        "active": True,
        "is_default": is_default,
        "company_name": f"Компания {company_id}",
        "short_name": str(company_id),
        "company_active": True,
        "plan": "demo",
        "trial_until": None,
        "plan_expires_at": None,
        "payment_status": "active",
        "suspended_at": None,
    }


class MemoryCursor:
    def __init__(self, world):
        self.world = world
        self.calls = []
        self.rowcount = -1
        self._rows = []
        self._row = None
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        params = tuple(params or ())
        self.calls.append((compact, params))
        self.rowcount = -1
        self._rows = []
        self._row = None
        if "FROM user_company_roles m" in compact:
            user_id = params[0]
            self._rows = [
                dict(row)
                for row in self.world["memberships"]
                if row["user_id"] == user_id
            ]
            return
        if "FROM public.staff" in compact and "FOR SHARE" in compact:
            self._require_verified_company(compact)
            self._row = self._staff_row(params[0], {params[1]})
            return
        if "SELECT t.id" in compact and "FOR UPDATE OF t" in compact:
            self._require_verified_company(compact)
            staff = self._staff_row(params[0], {params[2]})
            if staff and params[1] in self.world["days"].get(params[0], []):
                self._row = {"id": 1}
            return
        if compact.startswith("DELETE FROM public.timesheet"):
            self._require_verified_company(compact)
            days = self.world["days"].get(params[0], [])
            if self._staff_row(params[0], {params[2]}) and params[1] in days:
                days.remove(params[1])
                self.rowcount = 1
            else:
                self.rowcount = 0
            return
        if compact.startswith("INSERT INTO public.timesheet"):
            self._require_verified_company(compact)
            if self._staff_row(params[1], {params[2]}):
                self.world["days"].setdefault(params[1], []).append(params[0])
                self.rowcount = 1
            else:
                self.rowcount = 0
            return
        if "SELECT t.day" in compact:
            company_ids = self._company_ids(compact, params[1:])
            if self._staff_row(params[0], company_ids):
                self._rows = [
                    {"day": day}
                    for day in sorted(self.world["days"].get(params[0], []))
                ]
            return
        if "SELECT s.id" in compact and "FROM public.staff s" in compact:
            company_ids = self._company_ids(compact, params[1:])
            staff = self._staff_row(params[0], company_ids)
            self._row = {"id": staff["id"]} if staff else None
            return
        if "SELECT t.staff_id, t.day" in compact:
            company_ids = self._company_ids(compact, params)
            rows = []
            for staff in sorted(self.world["staff"], key=lambda item: item["id"]):
                if staff["id"] in {
                    row["id"] for row in (self._staff_row(staff["id"], company_ids),) if row
                }:
                    for day in sorted(self.world["days"].get(staff["id"], [])):
                        rows.append({"staff_id": staff["id"], "day": day})
            self._rows = rows
            return
        raise AssertionError("Unexpected SQL: " + compact)

    def _require_verified_company(self, sql):
        if "company_scope_verified IS TRUE" not in sql or "company_id=%s" not in sql:
            raise AssertionError("Timesheet write is not locked to verified staff: " + sql)

    def _company_ids(self, sql, params):
        if "company_scope_verified IS TRUE" not in sql:
            raise AssertionError("Timesheet read skipped staff verification: " + sql)
        if " AND FALSE" in sql:
            return set()
        if "s.company_id = ANY(%s)" in sql:
            return set(params[-1])
        if "s.company_id=%s" in sql:
            return {params[-1]}
        raise AssertionError("Timesheet read is not company-scoped: " + sql)

    def _staff_row(self, staff_id, company_ids):
        for staff in self.world["staff"]:
            if staff["id"] == staff_id and staff["verified"] and staff["company_id"] in company_ids:
                return {
                    "id": staff["id"],
                    "name": staff["name"],
                    "project": staff["project"],
                }
        return None

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True


def sample_world():
    return {
        "memberships": [
            membership(1, 10, "директор", is_default=True),
            membership(2, 10, "директор", is_default=True),
            membership(2, 20, "директор"),
            membership(3, 10, "директор", is_default=True),
            membership(3, 20, "мастер"),
            membership(4, 10, "бухгалтер", is_default=True),
            membership(5, 10, "прораб", is_default=True),
        ],
        "staff": [
            {"id": 101, "company_id": 10, "name": "Анна", "project": "Объект А", "verified": True},
            {"id": 102, "company_id": 10, "name": "Черновик", "project": "", "verified": False},
            {"id": 201, "company_id": 20, "name": "Борис", "project": "Объект Б", "verified": True},
            {"id": 301, "company_id": 30, "name": "Чужая", "project": "", "verified": True},
        ],
        "days": {
            101: ["2026-07-01"],
            102: ["2026-07-02"],
            201: ["2026-07-03"],
            301: ["2026-07-04"],
        },
    }


class TimesheetCompanyIsolationTest(unittest.TestCase):
    def setUp(self):
        self.world = sample_world()
        self.user = {"id": 1, "name": "Анна Директор", "role": "подмена"}
        self.audits = []
        self.cursors = []

        def get_db():
            cursor = MemoryCursor(self.world)
            self.cursors.append(cursor)
            return FakeConnection(cursor)

        def resolve(cur, user, requested, action, **headers):
            return resolve_request_company_context(
                cur,
                user,
                requested,
                action,
                x_company_id=headers.get("x_company_id"),
                x_company_mode=headers.get("x_company_mode"),
                platform_staff_roles=PLATFORM_ROLES,
                client_account_roles=ACCOUNT_ROLES,
            )

        app = FastAPI()
        register_timesheet_module(app, {
            "get_db": get_db,
            "get_current_user": lambda: self.user,
            "resolve_work_company_context": resolve,
            "effective_company_actors": effective_company_actors,
            "staff_view_roles": VIEW_ROLES,
            "staff_manage_roles": MANAGE_ROLES,
            "log_audit": lambda *args, **kwargs: self.audits.append((args, kwargs)),
        })
        self.client = TestClient(app)

    def test_company_user_cannot_see_or_toggle_another_company(self):
        listed = self.client.get(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        foreign_days = self.client.get(
            "/timesheet/201",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        unverified = self.client.get(
            "/timesheet/102",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        own_days = self.client.get(
            "/timesheet/101",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        foreign_toggle = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 201, "day": "2026-07-03"},
        )
        wrong_company = self.client.get(
            "/timesheet",
            headers={"X-Company-Id": "20", "X-Company-Mode": "company"},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [{"staffId": 101, "day": "2026-07-01"}])
        self.assertNotIn("Борис", listed.text)
        self.assertNotIn("2026-07-03", listed.text)
        self.assertNotIn("2026-07-04", listed.text)
        self.assertEqual(foreign_days.status_code, 404)
        self.assertEqual(unverified.status_code, 404)
        self.assertEqual(own_days.json(), {"days": ["2026-07-01"]})
        self.assertEqual(foreign_toggle.status_code, 404)
        self.assertEqual(self.world["days"][201], ["2026-07-03"])
        self.assertEqual(wrong_company.status_code, 403)
        self.assertEqual(self.audits, [])

    def test_default_company_without_header_stays_inside_membership(self):
        listed = self.client.get("/timesheet")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [{"staffId": 101, "day": "2026-07-01"}])

    def test_all_companies_read_includes_only_memberships_with_view_role(self):
        self.user = {"id": 2, "name": "Две компании", "role": "подмена"}
        both = self.client.get("/timesheet", headers={"X-Company-Mode": "all_companies"})
        self.assertEqual(both.status_code, 200)
        self.assertEqual(both.json(), [
            {"staffId": 101, "day": "2026-07-01"},
            {"staffId": 201, "day": "2026-07-03"},
        ])
        foreign = self.client.get(
            "/timesheet/301",
            headers={"X-Company-Mode": "all_companies"},
        )
        self.assertEqual(foreign.status_code, 404)

        self.user = {"id": 3, "name": "Мастер во второй", "role": "директор"}
        limited = self.client.get("/timesheet", headers={"X-Company-Mode": "all_companies"})
        denied_company = self.client.get(
            "/timesheet/201",
            headers={"X-Company-Id": "20", "X-Company-Mode": "company"},
        )
        self.assertEqual(limited.json(), [{"staffId": 101, "day": "2026-07-01"}])
        self.assertEqual(denied_company.status_code, 403)

    def test_all_companies_write_and_other_company_toggle_are_rejected(self):
        self.user = {"id": 2, "name": "Две компании", "role": "директор"}
        aggregate = self.client.post(
            "/timesheet",
            headers={"X-Company-Mode": "all_companies"},
            json={"staffId": 101, "day": "2026-07-08"},
        )
        added = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 101, "day": "2026-07-08"},
        )
        removed = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 101, "day": "2026-07-01"},
        )
        self.assertEqual(aggregate.status_code, 400)
        self.assertEqual(added.status_code, 200)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.world["days"][101], ["2026-07-08"])
        self.assertEqual(self.world["days"][201], ["2026-07-03"])
        self.assertEqual([item[0][2] for item in self.audits], ["timesheet_add", "timesheet_remove"])
        self.assertEqual(self.audits[0][0][1], "директор")
        self.assertEqual(self.audits[0][1]["company_id"], 10)

    def test_accountant_reads_and_foreman_toggles_only_own_company(self):
        self.user = {"id": 4, "name": "Бухгалтер", "role": "бухгалтер"}
        listed = self.client.get(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        denied = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 101, "day": "2026-07-01"},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["staffId"], 101)
        self.assertEqual(denied.status_code, 403)

        self.user = {"id": 5, "name": "Прораб", "role": "подмена"}
        toggled = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 201, "day": "2026-07-03"},
        )
        self.assertEqual(toggled.status_code, 404)
        self.assertEqual(self.world["days"][201], ["2026-07-03"])

    def test_platform_roles_cannot_use_timesheet_as_a_work_tool(self):
        self.user = {"id": 9, "name": "Платформа", "role": "platform_admin"}
        selected = self.client.get(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
        )
        aggregate = self.client.get(
            "/timesheet",
            headers={"X-Company-Mode": "all_companies"},
        )
        foreign = self.client.get(
            "/timesheet/201",
            headers={"X-Company-Mode": "all_companies"},
        )
        write = self.client.post(
            "/timesheet",
            headers={"X-Company-Id": "10", "X-Company-Mode": "company"},
            json={"staffId": 101, "day": "2026-07-01"},
        )
        aggregate_write = self.client.post(
            "/timesheet",
            headers={"X-Company-Mode": "all_companies"},
            json={"staffId": 101, "day": "2026-07-01"},
        )
        self.assertEqual(selected.status_code, 403)
        self.assertIn("Платформенная роль", selected.json()["detail"])
        self.assertEqual(aggregate.status_code, 403)
        self.assertNotIn("2026-07-01", aggregate.text)
        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(write.status_code, 403)
        self.assertEqual(aggregate_write.status_code, 400)
        self.assertEqual(self.world["days"][101], ["2026-07-01"])
        self.assertEqual(self.world["days"][201], ["2026-07-03"])
        self.assertEqual(self.audits, [])


if __name__ == "__main__":
    unittest.main()
