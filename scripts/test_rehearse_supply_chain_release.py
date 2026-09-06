#!/usr/bin/env python3
"""Offline safety contracts for the backup/disposable-database rehearsal.

Run: python3 scripts/test_rehearse_supply_chain_release.py
These tests never execute the runner, access a database, or contact production.
The shell is parsed with ``bash -n`` only. Embedded validation is tested with
local fakes, never with application/database modules.
"""

import ast
import builtins
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
import unittest


RUNNER = Path(__file__).with_name("rehearse-supply-chain-release.sh")
BEFORE = "20cf455afd2690d99b560cf02257faf0a82744fc"
TARGET = "4b935a5163ac602eee590adec02defba4222ef27"


class RehearsalSafetyContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RUNNER.is_file(), "the rehearsal runner must exist")
        self.source = RUNNER.read_text(encoding="utf-8")
        # Comments cannot satisfy a positive command-presence assertion.
        self.code = "\n".join(
            line for line in self.source.splitlines()
            if not line.lstrip().startswith("#")
        ).replace("\\\n", " ")

    def test_shell_syntax_is_valid_without_execution(self):
        result = subprocess.run(
            ["/bin/bash", "-n", str(RUNNER)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_identifiers_are_pinned_not_environment_defaults(self):
        for revision in (BEFORE, TARGET):
            self.assertRegex(self.code, rf"(?m)^\w+=[\"']?{revision}[\"']?$")
            self.assertNotRegex(self.code, rf"\$\{{[^}}]*{revision}[^}}]*\}}")

    def test_fail_closed_root_lock_and_private_file_defaults(self):
        self.assertRegex(self.code, r"set\s+-[^\n]*e[^\n]*u[^\n]*pipefail")
        self.assertRegex(self.code, r"(?:EUID|id\s+-u)")
        self.assertRegex(self.code, r"umask\s+0?077")
        self.assertRegex(self.code, r"flock\s+-n\s+")
        self.assertRegex(self.code, r"mktemp\s+-d\s+")

    def test_live_checkout_has_revision_branch_and_both_dirty_guards(self):
        self.assertRegex(self.code, r"git[^\n]*rev-parse\s+HEAD")
        self.assertRegex(self.code, r"git[^\n]*(?:branch\s+--show-current|symbolic-ref)")
        self.assertIn("main", self.code)
        self.assertRegex(self.code, r"git[^\n]*diff\s+--quiet")
        self.assertRegex(self.code, r"git[^\n]*diff\s+--cached\s+--quiet")

    def test_candidate_is_checked_locally_without_fetch_checkout_or_merge(self):
        self.assertRegex(self.code, r"git[^\n]*(?:cat-file|rev-parse\s+--verify)")
        self.assertRegex(self.code, r"git[^\n]*archive")
        self.assertNotRegex(
            self.code,
            r"(?m)^\s*(?:\w+=\S+\s+)*git\b[^\n]*\b"
            r"(?:fetch|pull|push|checkout|switch|merge|reset|clean)(?:\s|$)",
        )

    def test_no_service_mutation_cleanup_or_application_side_effect_runner(self):
        self.assertRegex(self.code, r"systemctl\s+is-active")
        self.assertNotRegex(
            self.code,
            r"\bsystemctl\s+(?:restart|start|stop|reload|enable|disable)\b",
        )
        self.assertNotRegex(self.code, r"(?m)^\s*(?:sudo\s+)?(?:rm|dropdb|npm|npx)\s")
        self.assertNotRegex(self.code, r"(?m)^\s*(?:bash\s+)?[^\n ]*deploy[^\n ]*\.sh\b")
        self.assertNotRegex(self.code, r"(?im)\bDROP\s+DATABASE\b")
        self.assertNotRegex(self.code, r"(?m)^\s*(?:source|\.)\s+[^\n]*\.env\b")

    def test_production_database_preconditions_are_read_only(self):
        self.assertIn("0006_user_company_staff_links", self.code)
        self.assertIn("column_name='vat'", self.code)
        self.assertRegex(self.code, r"(?:READ\s+ONLY|default_transaction_read_only|readonly=True)")
        self.assertRegex(self.code, r"(?:information_schema\.columns|pg_attribute)")

    def test_backup_is_streamed_and_checked_before_clone_restore(self):
        self.assertRegex(self.code, r"pg_dump\b[^\n]*>\s*\"")
        self.assertRegex(self.code, r"pg_restore\s+--list\b[^\n]*<\s*\"")
        self.assertRegex(self.code, r"pg_restore\b[^\n]*--(?:dbname|db)\b")
        self.assertIn(".env", self.code)
        self.assertIn("build", self.code)
        self.assertLess(self.code.index("pg_restore --list"), self.code.index("createdb"))

    def test_unique_clone_revokes_public_access_before_restoring_data(self):
        self.assertIn("stroyka_supply_rehearsal_", self.code)
        self.assertIn("$$", self.code)
        self.assertRegex(self.code, r"REVOKE\s+CONNECT\s+ON\s+DATABASE")
        self.assertIn("FROM PUBLIC", self.code)
        create = self.code.index("createdb")
        revoke = self.code.index("REVOKE CONNECT ON DATABASE")
        restore = re.search(r"pg_restore\b[^\n]*--(?:dbname|db)\b", self.code)
        self.assertIsNotNone(restore)
        self.assertLess(create, revoke)
        self.assertLess(revoke, restore.start())

    def test_clone_python_runs_as_postgres_with_all_database_settings_isolated(self):
        self.assertRegex(self.code, r"runuser\s+-u\s+postgres\s+--\s+env\s+-i\b")
        for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            self.assertRegex(self.code, rf"\b{name}=")
        self.assertRegex(self.code, r"chown\s+[^\n]*postgres")

    def test_actual_alembic_cli_and_fingerprint_checks_are_present(self):
        self.assertRegex(self.code, r"[\"']-m[\"']\s*,\s*[\"']alembic[\"']")
        self.assertRegex(
            self.code,
            r"[\"']upgrade[\"']\s*,\s*[\"'](?:head|0007_warehouse_vat_labels)[\"']",
        )
        self.assertIn("hashlib.sha256()", self.code)
        self.assertIn("before != after", self.code)
        self.assertGreaterEqual(len(re.findall(r"snapshot\s*\(", self.code)), 3)

    def test_production_checkout_revision_and_health_are_checked_after_rehearsal(self):
        self.assertGreaterEqual(len(re.findall(r"git[^\n]*rev-parse\s+HEAD", self.code)), 2)
        self.assertRegex(self.code, r"(?:healthz|/health)")
        # A postcondition must be explicitly tied to retaining the live revision.
        self.assertRegex(self.code, r"(?i)(?:unchanged|remain|still|postcheck)")


CLONE = "stroyka_supply_rehearsal_20260907123456_1234"
SCHEMA = ("text", "'Без НДС'::text", "YES", None, None, None)
CONFIG = dict(dbname=CLONE, user="postgres", password="",
              host="/var/run/postgresql", port="5432")


class FakeDatabase:
    """Only the rehearsal's read-only fingerprint queries are accepted."""

    def __init__(self):
        self.states = [
            dict(revision="0006_user_company_staff_links", schema=SCHEMA,
                 count=2, rows=b'{"id":1,"vat":"12%"}\n{"id":2,"vat":null}\n'),
            dict(revision="0007_warehouse_vat_labels", schema=SCHEMA,
                 count=2, rows=b'{"id":1,"vat":"12%"}\n{"id":2,"vat":null}\n'),
        ]
        self.connections = []

    def connect(self, **settings):
        if settings != dict(CONFIG, connect_timeout=5):
            raise AssertionError("unexpected database connection settings")
        if len(self.connections) >= len(self.states):
            raise AssertionError("unexpected extra database connection")
        conn = FakeConnection(self.states[len(self.connections)])
        self.connections.append(conn)
        return conn


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.readonly = False
        self.closed = False
        self.rolled_back = False

    def set_session(self, **settings):
        if settings != dict(readonly=True, isolation_level="REPEATABLE READ"):
            raise AssertionError("snapshot must be repeatable-read and read-only")
        self.readonly = True

    def cursor(self):
        if not self.readonly:
            raise AssertionError("cursor created before read-only transaction")
        return FakeCursor(self.state)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query):
        if query.startswith("SELECT current_database(), current_user,"):
            self.result = self.state.get("identity", (CLONE, "postgres", None, "5432"))
        elif query.startswith("SET LOCAL TIME ZONE 'UTC';"):
            self.result = None
        elif query == "SELECT version_num FROM public.alembic_version":
            self.result = [(self.state["revision"],)]
        elif (query.startswith("SELECT data_type, column_default, is_nullable,")
              and "FROM information_schema.columns" in query):
            self.result = self.state["schema"]
        elif query == "SELECT count(*) FROM public.warehouse_invoices":
            self.result = (self.state["count"],)
        else:
            raise AssertionError("unexpected SQL in local fake: " + query)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result

    def copy_expert(self, query, sink):
        if query != ("COPY (SELECT to_jsonb(w)::text FROM public.warehouse_invoices "
                     "w ORDER BY id) TO STDOUT"):
            raise AssertionError("unexpected copy statement")
        sink.write(self.state["rows"])


class FakeAlembic:
    def __init__(self):
        self.heads = "0007_warehouse_vat_labels (head)\n"
        self.upgrades = []

    def check_output(self, command, **settings):
        if command != ["/isolated/python3", "-m", "alembic", "heads"]:
            raise AssertionError("unexpected CLI inspection")
        if settings != {"text": True}:
            raise AssertionError("unexpected CLI inspection settings")
        return self.heads

    def run(self, command, **settings):
        if command != ["/isolated/python3", "-m", "alembic", "upgrade",
                       "0007_warehouse_vat_labels"]:
            raise AssertionError("unexpected migration command")
        if settings != {"check": True, "timeout": 90}:
            raise AssertionError("migration must be checked and bounded")
        self.upgrades.append(command)


class EmbeddedRehearsalTests(unittest.TestCase):
    def setUp(self):
        source = RUNNER.read_text(encoding="utf-8")
        match = re.search(r"<<'REHEARSAL_PY'\n(.*?)\nREHEARSAL_PY", source, re.S)
        self.assertIsNotNone(match, "expected embedded rehearsal Python")
        parsed = ast.parse(match.group(1))
        # Never execute imports, module-level statements, or the __main__ guard.
        functions = [node for node in parsed.body if isinstance(node, ast.FunctionDef)]
        self.database = FakeDatabase()
        self.alembic = FakeAlembic()
        self.config = dict(CONFIG)

        def isolated_import(name, *_args, **_kwargs):
            if name == "backend.db":
                return SimpleNamespace(DB_CONFIG=self.config)
            if name == "psycopg2":
                return self.database
            raise AssertionError("embedded code attempted an unexpected import: " + name)

        # Exclude file/process/network facilities even if a future edit uses them.
        allowed = ("__build_class__", "RuntimeError", "dict", "isinstance", "len",
                   "print", "str", "tuple", "ValueError")
        safe_builtins = {name: getattr(builtins, name) for name in allowed}
        safe_builtins["__import__"] = isolated_import
        self.namespace = {
            "__builtins__": safe_builtins, "__name__": "isolated_rehearsal_test",
            "hashlib": hashlib, "json": json, "re": re,
            "sys": SimpleNamespace(argv=["rehearsal", CLONE], executable="/isolated/python3"),
            "subprocess": self.alembic,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "<rehearsal>", "exec"),
             self.namespace)

    def run_main(self):
        with redirect_stdout(io.StringIO()) as output:
            self.namespace["main"]()
        return output.getvalue()

    def test_name_accepts_only_unique_bounded_disposable_identifiers(self):
        prefix = "stroyka_supply_rehearsal_20260907123456_"
        for name in (CLONE, prefix + "9" * (63 - len(prefix))):
            with self.subTest(name=name):
                self.namespace["validate_database_name"](name)

    def test_name_rejects_production_unsafe_and_noncanonical_identifiers(self):
        invalid = ("stroyka", "postgres", "template0", "", CLONE + "\n",
                   CLONE + ";DROP DATABASE stroyka", CLONE.replace("1234", "../1234"),
                   "stroyka_supply_rehearsal_1_1", CLONE.replace("20260907123456", "202609071234567"),
                   "stroyka_supply_rehearsal_20260907123456_" + "9" * 64)
        for name in invalid:
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    self.namespace["validate_database_name"](name)

    def test_wrong_configuration_stops_before_database_and_alembic(self):
        for key, value in (("dbname", "stroyka"), ("user", "stroyka"),
                           ("password", "inherited-secret"), ("host", "127.0.0.1"),
                           ("port", "5433")):
            with self.subTest(key=key):
                self.config.clear()
                self.config.update(CONFIG, **{key: value})
                with self.assertRaisesRegex(RuntimeError, "configuration"):
                    self.run_main()
                self.assertEqual(self.database.connections, [])
                self.assertEqual(self.alembic.upgrades, [])

    def test_wrong_database_identity_stops_before_alembic(self):
        self.database.states[0]["identity"] = ("stroyka", "postgres", None, "5432")
        with self.assertRaisesRegex(RuntimeError, "unexpected database/server"):
            self.run_main()
        self.assertEqual(self.alembic.upgrades, [])
        self.assertTrue(self.database.connections[0].closed)

    def test_old_revision_or_schema_mismatch_stops_before_alembic(self):
        for key, value in (("revision", "0005_previous"),
                           ("schema", ("numeric", None, "YES", None, None, None))):
            with self.subTest(key=key):
                self.database = FakeDatabase()
                self.database.states[0][key] = value
                with self.assertRaises(RuntimeError):
                    self.run_main()
                self.assertEqual(self.alembic.upgrades, [])

    def test_unexpected_migration_head_stops_before_upgrade(self):
        self.alembic.heads = "0008_unreviewed (head)\n"
        with self.assertRaisesRegex(RuntimeError, "migration head"):
            self.run_main()
        self.assertEqual(self.alembic.upgrades, [])

    def test_changed_rows_count_schema_or_revision_rejects_rehearsal(self):
        for key, value in (("rows", b'{"id":1,"vat":"20%"}\n'),
                           ("count", 3), ("schema", SCHEMA[:-1] + ("different",)),
                           ("revision", "0006_user_company_staff_links")):
            with self.subTest(key=key):
                self.database = FakeDatabase()
                self.database.states[1][key] = value
                with self.assertRaisesRegex(RuntimeError, "changed invoice data/schema"):
                    self.run_main()

    def test_success_requires_upgrade_and_exact_unchanged_snapshot(self):
        result = json.loads(self.run_main())
        self.assertEqual(result["migration"], "0007_warehouse_vat_labels")
        self.assertTrue(result["warehouseDataUnchanged"])
        self.assertTrue(result["vatSchemaUnchanged"])
        self.assertEqual(result["warehouseRows"], 2)
        self.assertEqual(result["rowsSha256"], hashlib.sha256(self.database.states[0]["rows"]).hexdigest())
        self.assertEqual(len(self.alembic.upgrades), 1)
        self.assertEqual(len(self.database.connections), 2)
        self.assertTrue(all(conn.readonly and conn.rolled_back and conn.closed
                            for conn in self.database.connections))


if __name__ == "__main__":
    unittest.main()
