import ast
import importlib
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import MagicMock, Mock, patch

from backend.features.supplier_access import test_postgres_chain_support as fixture


def _references_test_support(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] + [getattr(node, "module", "") or ""]
        elif isinstance(node, ast.Call):
            # Include aliased dynamic imports and keyword arguments, without importing code.
            args = node.args + [keyword.value for keyword in node.keywords]
            names = [arg.value for arg in args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        else:
            continue
        if any("test_postgres_chain_support" in name.split(".") for name in names):
            return True
    return False


class PostgresChainFixtureGuardTests(unittest.TestCase):
    def test_runtime_import_guard_covers_static_relative_and_dynamic_imports(self):
        for source in ("import backend.features.supplier_access.test_postgres_chain_support as support",
                       "from backend.features.supplier_access import test_postgres_chain_support as support",
                       "from .test_postgres_chain_support import build_fixture",
                       "from . import test_postgres_chain_support",
                       "importlib.import_module('backend.features.supplier_access.test_postgres_chain_support')",
                       "__import__('backend.features.supplier_access.test_postgres_chain_support')",
                       "load(name='.test_postgres_chain_support')"):
            with self.subTest(source=source):
                self.assertTrue(_references_test_support(source))
        self.assertFalse(_references_test_support("# test_postgres_chain_support\nvalue = 'ordinary'"))

    def test_support_module_is_test_only_and_never_imported_by_runtime(self):
        support = Path(fixture.__file__).resolve()
        self.assertEqual(support.name, "test_postgres_chain_support.py")
        for path in support.parents[2].rglob("*.py"):
            if path.name.startswith("test_") or "__pycache__" in path.parts:
                continue
            with self.subTest(path=str(path)):
                self.assertFalse(_references_test_support(path.read_text(encoding="utf-8")))

    def settings(self, **overrides):
        return {
            "SUPPLY_CHAIN_RUN_POSTGRES": "1",
            "SUPPLY_CHAIN_TEST_DB_HOST": "/tmp/isolated-postgres",
            "SUPPLY_CHAIN_TEST_DB_PORT": "55439",
            "SUPPLY_CHAIN_TEST_DB_NAME": "supply_chain_test_example",
            **overrides,
        }

    def test_import_never_connects_or_loads_application(self):
        with patch("psycopg2.connect") as connect, patch("os.chdir") as chdir:
            importlib.reload(fixture)
        connect.assert_not_called()
        chdir.assert_not_called()

    def test_missing_opt_in_fails_before_any_connection(self):
        with patch.dict(os.environ, {}, clear=True), patch("psycopg2.connect") as connect:
            with self.assertRaisesRegex(RuntimeError, "SUPPLY_CHAIN_RUN_POSTGRES"):
                fixture.build_fixture()
        connect.assert_not_called()

    def test_unsafe_or_missing_explicit_database_settings_fail_before_connect(self):
        for overrides in ({"SUPPLY_CHAIN_TEST_DB_NAME": "stroyka"},
                          {"SUPPLY_CHAIN_TEST_DB_NAME": "supply_chain_test_"},
                          {"SUPPLY_CHAIN_TEST_DB_HOST": "localhost"},
                          {"SUPPLY_CHAIN_TEST_DB_HOST": ""},
                          {"SUPPLY_CHAIN_TEST_DB_PORT": ""},
                          {"SUPPLY_CHAIN_TEST_DB_PORT": "bad"},
                          {"SUPPLY_CHAIN_TEST_DB_PORT": "65536"}):
            with self.subTest(overrides=overrides), patch.dict(
                os.environ, self.settings(**overrides), clear=True,
            ), patch("psycopg2.connect") as connect:
                with self.assertRaises(RuntimeError):
                    fixture.build_fixture()
                connect.assert_not_called()

    def test_settings_ignore_inherited_production_database_and_credentials(self):
        settings = fixture.connection_settings(self.settings(
            DB_HOST="production.invalid", DB_NAME="stroyka", DB_USER="admin",
            DB_PASSWORD="do-not-use", PGPASSWORD="do-not-use", DATABASE_URL="do-not-use",
        ))
        self.assertEqual(settings, {
            "host": "/tmp/isolated-postgres", "port": "55439",
            "dbname": "supply_chain_test_example", "user": "chain_test", "password": "",
        })

    def test_connection_guard_rejects_other_targets_and_libpq_overrides(self):
        settings = fixture.connection_settings(self.settings())
        connect = Mock()
        guarded = fixture.guarded_connector(settings, connect)
        for overrides in ({"dbname": "stroyka"}, {"host": "localhost"},
                          {"user": "admin"}, {"password": "secret"},
                          {"hostaddr": "127.0.0.1"}, {"service": "production"}):
            with self.subTest(overrides=overrides), self.assertRaises(RuntimeError):
                guarded(**{**settings, **overrides})
        with self.assertRaises(RuntimeError):
            guarded("dbname=stroyka")
        connect.assert_not_called()
        guarded(**settings)
        connect.assert_called_once_with(**settings)

    def test_wrong_server_identity_or_nonempty_schema_is_rejected(self):
        settings = fixture.connection_settings(self.settings())
        identity = (settings["dbname"], "chain_test", None, None)
        for rows in ([("stroyka", "chain_test", None, None)],
                     [(settings["dbname"], "other_user", None, None)],
                     [(settings["dbname"], "chain_test", "127.0.0.1", 55439)],
                     [identity, (True,)]):
            connection = MagicMock()
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = rows
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                fixture._assert_empty_database(connection, settings)

    def test_failed_connect_uses_no_ambient_credentials_and_restores_process(self):
        previous_connect = socket.socket.connect
        environ = self.settings(DB_PASSWORD="ambient-password", PGPASSWORD="ambient-password")
        def unavailable_database(**_kwargs):
            self.assertFalse(os.path.exists(os.environ["PGPASSFILE"]))
            self.assertTrue(os.path.isdir(os.path.dirname(os.environ["PGPASSFILE"])))
            self.assertEqual(os.environ["DB_PASSWORD"], "")
            self.assertNotIn("PGPASSWORD", os.environ)
            raise RuntimeError("isolated DB unavailable")
        with patch.dict(os.environ, environ, clear=True), patch(
            "psycopg2.connect", side_effect=unavailable_database,
        ):
            with self.assertRaisesRegex(RuntimeError, "isolated DB unavailable"):
                fixture.build_fixture()
            self.assertEqual(dict(os.environ), environ)
        self.assertIs(socket.socket.connect, previous_connect)


if __name__ == "__main__":
    unittest.main()
