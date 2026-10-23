"""Execute scoped SELECTs on SQLite; not a PostgreSQL integration claim."""
import json
import sqlite3
import unittest

from fastapi import HTTPException

from .context import load_company_data


class SqlCursor:
    def __init__(self, db, ledger_exists=False):
        self.cursor = db.cursor()
        self.calls = []
        self.ledger_exists = ledger_exists
        self.special = False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        self.special = "to_regclass" in query
        if self.special:
            return
        query = query.replace("= ANY(%s)", "IN (SELECT value FROM json_each(?))")
        query = query.replace("%s", "?").replace("public.supplier_payment_operations", "supplier_payment_operations")
        self.cursor.execute(query, tuple(json.dumps(p) if isinstance(p, list) else p for p in params))

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return (self.ledger_exists,) if self.special else self.cursor.fetchone()


class AssistantCompanyIsolationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE projects(id INTEGER, name TEXT, status TEXT, company_id INTEGER);
            CREATE TABLE warehouse_main(id INTEGER, name TEXT, quantity NUMERIC, unit TEXT, company_id INTEGER);
            CREATE TABLE users(id INTEGER, name TEXT, active BOOLEAN);
            CREATE TABLE user_company_roles(user_id INTEGER, company_id INTEGER, role TEXT, active BOOLEAN);
            CREATE TABLE materials(id INTEGER, name TEXT, quantity NUMERIC, unit TEXT, project TEXT, company_id INTEGER);
            CREATE TABLE brigade_contracts(id INTEGER, project_name TEXT, brigade_name TEXT, status TEXT, company_id INTEGER, project_id INTEGER);
            CREATE TABLE project_payments(id INTEGER, project_name TEXT, amount NUMERIC, note TEXT, company_id INTEGER);
            CREATE TABLE supplier_payment_operations(id INTEGER, project_payment_id INTEGER);
            INSERT INTO projects VALUES (11,'Общий','В работе',1),(12,'Закрытый','В работе',1),(21,'Общий','В работе',2),(22,'Другой','В работе',2);
            INSERT INTO warehouse_main VALUES (1,'Склад А',10,'кг',1),(2,'Секретный склад Б',99,'кг',2),(3,'Бесхозный',5,'кг',NULL);
            INSERT INTO users VALUES (1,'Свой сотрудник',TRUE),(2,'Чужой сотрудник',TRUE),(3,'Отозванная роль',TRUE),(4,'Неактивный пользователь',FALSE);
            INSERT INTO user_company_roles VALUES (1,1,'сметчик',TRUE),(2,2,'директор',TRUE),(3,1,'директор',FALSE),(4,1,'директор',TRUE);
            INSERT INTO materials VALUES (1,'Материал А',10,'кг','Общий',1),(2,'Секретный материал Б',99,'кг','Общий',2),(3,'Ограниченный А',2,'кг','Закрытый',1),(4,'Бесхозный материал',4,'кг','Общий',NULL);
            INSERT INTO brigade_contracts VALUES (1,'Общий','Бригада А','Активно',1,11),(2,'Общий','Секретная бригада Б','Активно',2,21),(3,'Общий','Неверный project_id','Активно',1,21),(4,'Общий','Legacy А','Активно',1,NULL),(5,'Общий','Бесхозная бригада','Активно',NULL,NULL);
            INSERT INTO project_payments VALUES (1,'Общий',100,'Оплата А',1),(2,'Общий',999,'Секретная оплата Б',2),(3,'Общий',50,'Поставщик',1);
            INSERT INTO supplier_payment_operations VALUES(1,3);
        """)
        self.user = {"id": 42, "name": "Текущий", "role": "директор", "companyId": 1}

    def context(self, company=1, role="директор", assigned=None):
        return {"mode": "company", "companyId": company, "effectiveRole": role,
                "active": True, "companyActive": True, "assignedProjects": assigned or []}

    def load(self, context, ledger=False):
        self.cur = SqlCursor(self.db, ledger)
        return load_company_data(self.cur, self.user, context,
                                 warehouse_roles=("директор", "кладовщик", "прораб"),
                                 finance_roles=("директор", "бухгалтер"))

    def test_director_selected_company_never_receives_other_tenant_or_unowned_rows(self):
        data = self.load(self.context(), ledger=True)
        text = json.dumps(data, ensure_ascii=False)
        for forbidden in ("Секрет", "Чужой", "Бесхоз", "Отозванная роль", "Неактивный пользователь", "Неверный project_id", '"Поставщик"'):
            self.assertNotIn(forbidden, text)
        for allowed in ("Материал А", "Бригада А", "Legacy А", "Свой сотрудник", "Оплата А"):
            self.assertIn(allowed, text)
        self.assertTrue(all("LIMIT " in query for query, _ in self.cur.calls if "to_regclass" not in query))

    def test_effective_membership_overrides_global_director_role(self):
        data = self.load(self.context(role="мастер", assigned=["Общий"]))
        text = json.dumps(data, ensure_ascii=False)
        self.assertIn("Материал А", text)
        for forbidden in ("Закрытый", "Ограниченный", "Склад А", "Свой сотрудник", "Оплата А", "Секрет"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(data["staff_name_role_company"], [["Текущий", "мастер", "1"]])

    def test_all_companies_keeps_each_membership_role_and_project_scope(self):
        context = {"mode": "all_companies", "companyIds": [1, 2], "companies": [self.context(), self.context(2, "мастер", ["Другой"])]}
        data = self.load(context)
        self.assertIn("Другой", json.dumps(data, ensure_ascii=False))
        self.assertNotIn("Секрет", json.dumps(data, ensure_ascii=False))

    def test_empty_or_unrecognized_scope_is_fail_closed(self):
        for context in ({}, {"mode": "all_companies", "companies": []}):
            data = self.load(context)
            self.assertTrue(all(not rows for key, rows in data.items() if key != "limitations"))
        for context in (self.context(role=""), {**self.context(), "active": False}):
            with self.assertRaises(HTTPException):
                self.load(context)

    def test_same_project_name_does_not_grant_cross_company_access(self):
        data = self.load(self.context(2, "прораб", ["Общий"]))
        text = json.dumps(data, ensure_ascii=False)
        self.assertIn("Секретный материал Б", text)
        self.assertIn("Секретная бригада Б", text)
        self.assertNotIn("Материал А", text)
        self.assertNotIn("Бригада А", text)
        self.assertNotIn("Оплата А", text)

    def test_no_server_memory_between_user_company_requests(self):
        first = self.load(self.context())
        second = self.load(self.context(2))
        self.assertNotIn("Материал А", json.dumps(second, ensure_ascii=False))
        self.assertNotIn("Секретный материал Б", json.dumps(first, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
