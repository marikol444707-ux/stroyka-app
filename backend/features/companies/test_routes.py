import unittest

import psycopg2.extras
from fastapi import FastAPI

from backend.features.companies.routes import register_companies_module


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.factory = None
        self.sql = ""

    def execute(self, sql, params=()):
        self.sql = " ".join(sql.split())
        self.params = params

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False

    def cursor(self, cursor_factory=None):
        self.cursor_obj.factory = cursor_factory
        return self.cursor_obj

    def close(self):
        self.closed = True


class CompaniesRoutesTest(unittest.TestCase):
    def test_lists_active_companies_with_the_same_shape(self):
        cursor = FakeCursor([
            {"id": 4, "shortName": "СтройКа", "name": "ООО СтройКа", "inn": "2600000000",
             "logoUrl": "", "plan": "pro", "active": True},
        ])
        connection = FakeConnection(cursor)

        def get_current_user():
            return {"id": 1}

        app = FastAPI()
        register_companies_module(app, {
            "get_db": lambda: connection,
            "get_current_user": get_current_user,
        })
        route = next(item for item in app.routes if item.path == "/companies")
        self.assertIn("GET", route.methods)
        self.assertEqual(route.dependant.dependencies[0].call.__name__, "get_current_user")

        rows = route.endpoint(_current_user={"id": 1})

        self.assertEqual(rows, [{
            "id": 4, "shortName": "СтройКа", "name": "ООО СтройКа", "inn": "2600000000",
            "logoUrl": "", "plan": "pro", "active": True,
        }])
        self.assertIn("WHERE active=TRUE", cursor.sql)
        self.assertIs(cursor.factory, psycopg2.extras.RealDictCursor)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
