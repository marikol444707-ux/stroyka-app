import unittest

from fastapi import Depends, FastAPI, HTTPException

from backend.features.material_price_history.routes import register_material_price_history_module


ROLES = ("директор", "зам_директора", "снабженец", "кладовщик", "бухгалтер")


def get_current_user():
    return {}


def require_roles(*roles):
    allowed = set(roles)

    def _dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return user

    return _dep


class FakeCursor:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.batches.pop(0)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_obj

    def close(self):
        self.closed = True


def build(cursor=None):
    app = FastAPI()
    connection = FakeConnection(cursor or FakeCursor([[], []]))
    calls = []

    def get_db():
        calls.append("db")
        return connection

    register_material_price_history_module(app, {
        "get_db": get_db,
        "require_roles": require_roles,
        "material_price_history_roles": ROLES,
    })
    route = next(item for item in app.routes if item.path == "/material-price-history")
    return route, connection, calls


class MaterialPriceHistoryRoutesTest(unittest.TestCase):
    def test_keeps_get_and_price_roles(self):
        route, _connection, _calls = build()
        self.assertIn("GET", route.methods)
        dependency = route.dependant.dependencies[0]
        self.assertEqual(dependency.call.__name__, "_dep")
        self.assertEqual(dependency.call.__closure__[0].cell_contents, set(ROLES))
        nested = dependency.dependencies[0]
        self.assertEqual(nested.call.__name__, "get_current_user")

    def test_blank_material_skips_the_database(self):
        route, _connection, calls = build()
        self.assertEqual(
            route.endpoint(material="  ", _current_user={"role": "снабженец"}),
            {"history": [], "catalog": [], "stats": None},
        )
        self.assertEqual(calls, [])

    def test_history_and_catalog_keep_the_response_shape(self):
        cursor = FakeCursor([
            [("Кабель", 10, "м", 2, "Объект", "2026-01-01", "Поставщик")],
            [("Кабель", "Каталог", 12, "м", 5, True)],
        ])
        route, connection, _calls = build(cursor)
        result = route.endpoint(material=" Кабель ", _current_user={"role": "снабженец"})
        self.assertEqual(result["history"], [{
            "materialName": "Кабель", "price": 10.0, "unit": "м", "quantity": 2.0,
            "project": "Объект", "date": "2026-01-01", "supplierName": "Поставщик",
        }])
        self.assertEqual(result["catalog"], [{
            "materialName": "Кабель", "supplierName": "Каталог", "price": 12.0,
            "unit": "м", "deliveryDays": 5, "inStock": True,
        }])
        self.assertEqual(result["stats"], {"min": 10.0, "max": 12.0, "avg": 11.0, "count": 2})
        self.assertIn("FROM supply_history", cursor.calls[0][0])
        self.assertIn("FROM supplier_catalog", cursor.calls[1][0])
        self.assertEqual(cursor.calls[0][1], ("%Кабель%",))
        self.assertEqual(cursor.calls[1][1], ("%Кабель%",))
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
