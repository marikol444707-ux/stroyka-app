import ast
import getpass
import io
import json
import importlib.util
import inspect
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg2.extensions import TRANSACTION_STATUS_IDLE, parse_dsn
from psycopg2.extras import RealDictCursor

import backend.features.estimate_revision_impact.supply_warehouse_audit as supply_audit
import backend.features.estimate_revision_impact.baseline as baseline_audit
import backend.features.warehouse_recommendation_preview.runtime_access as runtime_access
import backend.features.warehouse_recommendation_preview.runtime_budget as runtime_budget
import backend.features.warehouse_recommendation_preview.runtime_contract as runtime_contract
import backend.features.human_approved_actions.action_kernel as human_action_kernel
from backend.features.estimate_revision_impact.contract import (
    MAX_CANONICAL_SOURCE_BYTES,
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.combined_contract import (
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)
from backend.features.estimate_revision_impact.resource_limits import (
    MAX_COLLECTOR_VARIABLE_BYTES,
    MAX_JSON_QUERY_BYTES,
    MAX_NUMERIC_FIELD_BYTES,
    MAX_TEXT_FIELD_BYTES,
    _BOUNDED_ACCEPTED,
    _BOUNDED_CARDINALITY,
    _BOUNDED_OVERFLOW,
    _VariableByteBudget,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    MAX_DOMAIN_ROWS,
    MAX_SOURCE_JSON_BYTES,
    run_supply_warehouse_impact_audit,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
)
from backend.features.warehouse_recommendation_preview.content_contract import (
    _validate_current_warehouse_anomaly_report,
)
from backend.features.warehouse_recommendation_preview.test_content_preview import (
    _real_a7_case,
)
from backend.features.assignment_daily_drafts.snapshot import (
    AssignmentDailySnapshotRequest,
    run_assignment_daily_snapshot,
)
from backend.features.assignment_daily_drafts.runtime_preview import (
    run_authorized_assignment_daily_snapshot,
)
from backend.features.assignment_daily_drafts.runtime_routes import (
    register_assignment_daily_draft_preview_routes,
)
from backend.features.accounting_exception_checks.ownership_inventory import (
    run_accounting_ownership_inventory,
)
from backend.features.accounting_exception_checks.ownership_backfill import (
    run_accounting_ownership_backfill,
)
from backend.features.accounting_exception_checks.ownership_remediation import (
    build_accounting_ownership_remediation_request,
)
from backend.features.accounting_exception_checks.ownership_remediation_runner import (
    run_accounting_ownership_remediation,
)
from backend.features.accounting_exception_checks.schema_contract import (
    build_accounting_ownership_schema_plan,
    run_accounting_ownership_schema,
)
from backend.features.human_approved_actions.schema_contract import (
    APPLY_CONFIRMATION as HUMAN_ACTION_SCHEMA_CONFIRMATION,
    HumanActionSchemaMigrationError,
    _collect_catalog as collect_human_action_schema_catalog,
    build_human_action_schema_plan,
    run_human_action_schema_migration,
)
from backend.features.accounting_exception_checks.snapshot import (
    run_accounting_exception_snapshot,
)
from backend.features.accounting_exception_checks.runtime_access import (
    run_authorized_accounting_exception_snapshot,
)
from backend.features.accounting_exception_checks.runtime_routes import (
    register_accounting_exception_check_routes,
)
from backend.features.accountable_payments.routes import (
    register_accountable_payments_module,
)
from backend.features.expense_reports.routes import (
    register_expense_reports_module,
)
from backend.features.expenses.routes import register_expenses_module
from backend.features.own_expenses.routes import register_own_expenses_module
from backend.features.salary_payments.routes import (
    register_salary_payments_module,
)
from backend.features.staff.routes import register_staff_module
from backend.features.company_context.service import (
    effective_company_actors,
    resolve_request_company_context,
)


RUN_POSTGRES = os.getenv("A93_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_DSN = os.getenv("A93_TEST_DATABASE_DSN", "")
TEST_CLUSTER_ROOT = os.getenv("A93_TEST_CLUSTER_ROOT", "")
TEST_SOCKET_DIR = os.getenv("A93_TEST_SOCKET_DIR", "")
TEST_DATABASE_USER = os.getenv("A93_TEST_DATABASE_USER", "")
TEST_CAPABILITY = os.getenv("A93_TEST_CAPABILITY", "")
TEST_CAPABILITY_FD = os.getenv("A93_TEST_CAPABILITY_FD", "")

if RUN_POSTGRES and not all((
    TEST_DATABASE_DSN,
    TEST_CLUSTER_ROOT,
    TEST_SOCKET_DIR,
    TEST_DATABASE_USER,
    TEST_CAPABILITY,
    TEST_CAPABILITY_FD,
)):
    raise RuntimeError(
        "A9.3 PostgreSQL opt-in requires every launcher-owned value"
    )

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_PATH = PROJECT_ROOT / "scripts" / "run_a93_postgres_tests.py"
TEST_MODULE = (
    "backend.features.estimate_revision_impact."
    "test_resource_limits_postgres"
)

_CONTEXT_VARIABLES = (
    "project_name",
    "base_work_package",
    "base_sections_json",
)
_REQUEST_VARIABLES = (
    "request_project",
    "request_work_package",
    "request_status",
    "items_json",
)
_DELIVERY_VARIABLES = (
    "delivery_project",
    "delivery_work_package",
    "material_name",
    "unit",
    "received_quantity",
)


def _json_string_bytes(size):
    if type(size) is not int or size < 2:
        raise AssertionError("invalid JSON fixture size")
    value = '"' + ("a" * (size - 2)) + '"'
    if len(value.encode("utf-8")) != size:
        raise AssertionError("JSON fixture byte size mismatch")
    return value


def _request_json_bytes(size):
    prefix = '{"estimateId":51,"pad":"'
    suffix = '"}'
    padding = size - len((prefix + suffix).encode("utf-8"))
    if padding < 0:
        raise AssertionError("request JSON fixture is too small")
    value = prefix + ("a" * padding) + suffix
    if len(value.encode("utf-8")) != size:
        raise AssertionError("request JSON fixture byte size mismatch")
    return value


class _RecordingCursor:
    def __init__(self, cursor, observation):
        self._cursor = cursor
        self._observation = observation
        self._call_index = None

    def execute(self, sql, params=None):
        self._call_index = len(self._observation["calls"])
        self._observation["calls"].append((sql, tuple(params or ())))
        return self._cursor.execute(sql, params)

    def fetchall(self):
        rows = self._cursor.fetchall()
        copied = [dict(row) if isinstance(row, dict) else tuple(row) for row in rows]
        self._observation["fetched"].append((self._call_index, copied))
        return copied

    def close(self):
        return self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _ObservedConnection:
    def __init__(self, connection, *, before_close=None):
        self._connection = connection
        self._before_close = before_close
        self.observation = {
            "calls": [],
            "fetched": [],
            "sessions": [],
            "commits": 0,
            "rollbacks": 0,
            "closed": False,
        }

    def set_session(self, **kwargs):
        self.observation["sessions"].append(dict(kwargs))
        return self._connection.set_session(**kwargs)

    @property
    def autocommit(self):
        return self._connection.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._connection.autocommit = value

    def cursor(self, *args, **kwargs):
        return _RecordingCursor(
            self._connection.cursor(*args, **kwargs),
            self.observation,
        )

    def commit(self):
        self.observation["commits"] += 1
        return self._connection.commit()

    def rollback(self):
        self.observation["rollbacks"] += 1
        return self._connection.rollback()

    def close(self):
        self.observation["closed"] = True
        if self._before_close is not None:
            self._before_close(self._connection)
        return self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


class A93PostgresLauncherContractTests(unittest.TestCase):
    @staticmethod
    def _launcher_module():
        spec = importlib.util.spec_from_file_location(
            "a93_postgres_test_launcher",
            LAUNCHER_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_launcher_is_local_test_only_and_owns_its_database(self):
        launcher = self._launcher_module()
        self.assertTrue(LAUNCHER_PATH.is_file())
        source = LAUNCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.assertIn('mkdtemp(', source)
        self.assertEqual(
            launcher.TEMP_ROOT,
            Path(tempfile.gettempdir()).resolve(),
        )
        self.assertIn('dir=str(TEMP_ROOT)', source)
        self.assertNotIn('dir="/private/tmp"', source)
        self.assertIn("listen_addresses=''", source)
        self.assertIn("A93_RUN_POSTGRES_INTEGRATION", source)
        self.assertNotIn("argparse", source)
        self.assertNotIn("localhost", source)
        self.assertNotIn("docker", source.lower())
        self.assertFalse(any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                alias.name.split(".")[0] in {
                    "requests", "urllib", "http", "socketserver",
                }
                for alias in node.names
            )
            for node in ast.walk(tree)
        ))

    def test_launcher_accepts_the_installed_postgresql_15_version_format(self):
        launcher = self._launcher_module()
        installed = {
            name: "/usr/local/opt/postgresql@15/bin/" + name
            for name in launcher.POSTGRES_PROGRAMS
        }
        completed = mock.Mock(
            returncode=0,
            stdout="postgres (PostgreSQL) 15.17 (Homebrew)\n",
        )

        with mock.patch.object(
            launcher.shutil,
            "which",
            side_effect=lambda name: installed[name],
        ), mock.patch.object(
            launcher.subprocess,
            "run",
            return_value=completed,
        ):
            self.assertEqual(
                launcher._postgres_programs(),
                {
                    name: str(Path(path).resolve())
                    for name, path in installed.items()
                },
            )

    def test_launcher_checks_psycopg2_before_creating_a_cluster(self):
        launcher = self._launcher_module()
        unavailable = mock.Mock(returncode=1)

        with mock.patch.object(
            launcher.subprocess,
            "run",
            return_value=unavailable,
        ):
            self.assertFalse(launcher._python_driver_available({}))

        source = LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("_python_driver_available(environment)"),
            source.index("tempfile.mkdtemp("),
        )

    def test_launcher_strips_inherited_database_configuration(self):
        launcher = self._launcher_module()
        inherited = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/private/tmp/a93-home",
            "PGHOST": "foreign.example",
            "PGDATABASE": "production",
            "DATABASE_URL": "postgresql://foreign.example/production",
            "A7_TEST_DATABASE_URL": "postgresql://foreign.example/a7",
            "DB_HOST": "foreign.example",
        }

        with mock.patch.dict(launcher.os.environ, inherited, clear=True):
            environment = launcher._subprocess_environment()

        self.assertEqual(
            environment,
            {
                "HOME": "/private/tmp/a93-home",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
        )

    def test_launcher_retries_server_stop_with_immediate_mode(self):
        launcher = self._launcher_module()
        failed_fast = subprocess.CalledProcessError(1, ["pg_ctl"])

        with mock.patch.object(
            launcher,
            "_run",
            side_effect=(failed_fast, None),
        ) as run:
            self.assertTrue(launcher._stop_server(
                "/private/a93/pg_ctl",
                Path("/private/tmp/stroyka-a93-pg-test/data"),
                {},
            ))

        self.assertEqual(run.call_count, 2)
        self.assertIn("fast", run.call_args_list[0].args[0])
        self.assertIn("immediate", run.call_args_list[1].args[0])

    def test_launcher_never_removes_a_fixture_until_server_death_is_proven(self):
        launcher = self._launcher_module()
        root = Path("/private/tmp/stroyka-a93-pg-test")
        data = root / "data"
        socket_dir = root / "socket"

        with mock.patch.object(
            launcher.shutil,
            "rmtree",
        ) as remove:
            self.assertFalse(launcher._remove_fixture_root(
                root,
                data,
                socket_dir,
                original_identity=(1, 2, os.getuid(), 0o700),
                death_confirmed=False,
            ))

        remove.assert_not_called()

    def test_server_death_requires_stopped_status_and_recorded_pid_exit(self):
        launcher = self._launcher_module()
        data = Path("/private/tmp/stroyka-a93-pg-test/data")
        socket_dir = Path("/private/tmp/stroyka-a93-pg-test/socket")

        with mock.patch.object(
            launcher,
            "_pg_ctl_reports_stopped",
            return_value=False,
        ), mock.patch.object(
            launcher,
            "_process_is_gone",
            return_value=True,
        ):
            self.assertFalse(launcher._server_is_dead(
                data,
                socket_dir,
                pid=123,
                pg_ctl="/private/a93/pg_ctl",
                environment={},
            ))

        with mock.patch.object(
            launcher,
            "_pg_ctl_reports_stopped",
            return_value=True,
        ), mock.patch.object(
            launcher,
            "_process_is_gone",
            return_value=False,
        ):
            self.assertFalse(launcher._server_is_dead(
                data,
                socket_dir,
                pid=123,
                pg_ctl="/private/a93/pg_ctl",
                environment={},
            ))

    def test_root_inode_must_match_before_fixture_removal(self):
        launcher = self._launcher_module()
        root = Path("/private/tmp/stroyka-a93-pg-test")
        data = root / "data"
        socket_dir = root / "socket"
        original = (1, 2, os.getuid(), 0o700)
        replacement = (1, 3, os.getuid(), 0o700)

        with mock.patch.object(
            launcher,
            "_server_is_dead",
            return_value=True,
        ), mock.patch.object(
            launcher,
            "_directory_identity",
            return_value=replacement,
        ), mock.patch.object(
            launcher.shutil,
            "rmtree",
        ) as remove:
            self.assertFalse(launcher._remove_fixture_root(
                root,
                data,
                socket_dir,
                original_identity=original,
                death_confirmed=True,
            ))

        remove.assert_not_called()

    def test_root_creation_is_inside_the_outer_cleanup_boundary(self):
        source = LAUNCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        mkdtemp_call = next(
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "mkdtemp"
        )
        protected = any(
            isinstance(node, ast.Try)
            and any(
                nested is mkdtemp_call
                for statement in node.body
                for nested in ast.walk(statement)
            )
            and node.finalbody
            for node in ast.walk(main)
        )

        self.assertTrue(protected)

    def test_interrupted_subprocess_is_terminated_as_an_owned_group(self):
        launcher = self._launcher_module()
        process = mock.Mock(pid=4321)
        process.poll.side_effect = (None, None, None, 0)
        process.wait.side_effect = (
            subprocess.TimeoutExpired(["child"], 5),
            0,
        )

        with mock.patch.object(launcher.os, "killpg") as kill_group:
            self.assertTrue(launcher._terminate_process_group(process))

        self.assertEqual(
            kill_group.call_args_list,
            [
                mock.call(4321, signal.SIGTERM),
                mock.call(4321, signal.SIGKILL),
            ],
        )

    def test_unreaped_owned_process_permanently_blocks_root_removal(self):
        launcher = self._launcher_module()
        process = mock.Mock(pid=9876)
        process.wait.side_effect = subprocess.TimeoutExpired(["child"], 1)

        with mock.patch.object(
            launcher.subprocess,
            "Popen",
            return_value=process,
        ), mock.patch.object(
            launcher,
            "_terminate_process_group",
            return_value=False,
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                launcher._run(
                    ["child"],
                    environment={},
                    timeout=1,
                )

        self.assertEqual(launcher._OWNED_PROCESS_GROUPS, {9876})
        with mock.patch.object(launcher.shutil, "rmtree") as remove:
            self.assertFalse(launcher._remove_fixture_root(
                Path("/private/tmp/stroyka-a93-pg-test"),
                Path("/private/tmp/stroyka-a93-pg-test/data"),
                Path("/private/tmp/stroyka-a93-pg-test/socket"),
                original_identity=(1, 2, os.getuid(), 0o700),
                death_confirmed=True,
            ))
        remove.assert_not_called()

    def test_unreaped_process_blocks_every_destructive_cleanup_phase(self):
        launcher = self._launcher_module()
        launcher._OWNED_PROCESS_GROUPS.add(9876)
        with mock.patch.object(
            launcher,
            "_fixture_paths_match",
            return_value=True,
        ) as matches:
            self.assertFalse(launcher._cleanup_paths_are_safe(
                Path("/private/tmp/stroyka-a93-pg-test"),
                Path("/private/tmp/stroyka-a93-pg-test/data"),
                Path("/private/tmp/stroyka-a93-pg-test/socket"),
                root_identity=(1, 2, os.getuid(), 0o700),
                data_identity=(1, 3, os.getuid(), 0o700),
                socket_identity=(1, 4, os.getuid(), 0o700),
            ))
        matches.assert_not_called()

    def test_partial_root_state_is_preserved_without_cleanup_exception(self):
        launcher = self._launcher_module()
        self.assertFalse(launcher._remove_fixture_root(
            Path("/private/tmp/stroyka-a93-pg-test"),
            None,
            None,
            original_identity=(1, 2, os.getuid(), 0o700),
            death_confirmed=True,
        ))

    def test_prerequisite_probe_failures_are_plain_unavailability(self):
        launcher = self._launcher_module()
        installed = {
            name: "/usr/local/opt/postgresql@15/bin/" + name
            for name in launcher.POSTGRES_PROGRAMS
        }
        timeout = subprocess.TimeoutExpired(["postgres", "--version"], 10)

        with mock.patch.object(
            launcher.shutil,
            "which",
            side_effect=lambda name: installed[name],
        ), mock.patch.object(
            launcher.subprocess,
            "run",
            side_effect=timeout,
        ):
            self.assertIsNone(launcher._postgres_programs())

        with mock.patch.object(
            launcher.subprocess,
            "run",
            side_effect=OSError("missing driver interpreter"),
        ):
            self.assertFalse(launcher._python_driver_available({}))

    def test_partial_opt_in_is_an_import_error_instead_of_a_skip(self):
        environment = dict(os.environ)
        for key in tuple(environment):
            if key.startswith("A93_TEST_") or key == "A93_RUN_POSTGRES_INTEGRATION":
                environment.pop(key)
        environment["A93_RUN_POSTGRES_INTEGRATION"] = "1"

        completed = subprocess.run(
            [sys.executable, "-c", "import " + TEST_MODULE],
            cwd=str(PROJECT_ROOT),
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "opt-in requires every launcher-owned value",
            completed.stderr,
        )

    def test_forged_full_opt_in_cannot_reach_psycopg_connect(self):
        root = Path(tempfile.mkdtemp(
            prefix="stroyka-a93-pg-forged_contract_",
            dir=str(Path(tempfile.gettempdir()).resolve()),
        )).resolve()
        os.chmod(root, 0o700)
        data_dir = root / "data"
        socket_dir = root / "socket"
        data_dir.mkdir(mode=0o700)
        socket_dir.mkdir(mode=0o700)
        marker_path = root / "launcher.capability"
        marker_fd = os.open(
            marker_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(marker_fd, b"b" * 64)
        finally:
            os.close(marker_fd)
        capability_fd = os.open(marker_path, os.O_RDONLY)
        environment = dict(os.environ)
        for key in tuple(environment):
            if key.startswith("A93_TEST_") or key.startswith("PG"):
                environment.pop(key)
        database_name = "a93_0123456789abcdef"
        database_user = getpass.getuser()
        environment.update({
            "A93_RUN_POSTGRES_INTEGRATION": "1",
            "A93_TEST_CLUSTER_ROOT": str(root),
            "A93_TEST_SOCKET_DIR": str(socket_dir),
            "A93_TEST_DATABASE_USER": database_user,
            "A93_TEST_CAPABILITY": "a" * 64,
            "A93_TEST_CAPABILITY_FD": str(capability_fd),
            "A93_TEST_DATABASE_DSN": (
                "dbname=" + database_name
                + " user=" + database_user
                + " host=" + str(socket_dir)
                + " port=55432 connect_timeout=5"
            ),
            "PGDATABASE": database_name,
            "PGHOST": str(socket_dir),
            "PGPORT": "55432",
            "PGUSER": database_user,
        })
        probe = (
            "from unittest import mock\n"
            "import " + TEST_MODULE + " as module\n"
            "with mock.patch.object(module.psycopg2, 'connect') as connect:\n"
            "    try:\n"
            "        module.A93ResourceLimitsPostgresTests.setUpClass()\n"
            "    except RuntimeError as exc:\n"
            "        if str(exc) != "
            "'A9.3 PostgreSQL capability marker is invalid':\n"
            "            raise\n"
            "    else:\n"
            "        raise SystemExit('capability guard accepted forgery')\n"
            "    if connect.called:\n"
            "        raise SystemExit('connect reached')\n"
        )

        try:
            completed = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=str(PROJECT_ROOT),
                env=environment,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                pass_fds=(capability_fd,),
            )
        finally:
            os.close(capability_fd)
            shutil.rmtree(root)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("connect reached", completed.stderr)
        self.assertNotIn("capability guard accepted forgery", completed.stderr)

    def test_main_wires_drop_stop_death_and_inode_bound_removal(self):
        launcher = self._launcher_module()
        programs = {
            name: "/private/a93/bin/" + name
            for name in launcher.POSTGRES_PROGRAMS
        }

        for child_exit, death_confirmed, expected_exit in (
            (0, True, 0),
            (0, False, 1),
            (1, True, 1),
        ):
            with self.subTest(
                child_exit=child_exit,
                death_confirmed=death_confirmed,
            ):
                events = []
                roots = []

                def fake_run(command, **_kwargs):
                    program = Path(command[0]).name
                    if program == "initdb":
                        data_dir = Path(command[command.index("--pgdata") + 1])
                        data_dir.mkdir(mode=0o700)
                        roots.append(data_dir.parent)
                        events.append("initdb")
                    elif program == "pg_ctl" and "start" in command:
                        data_dir = Path(command[command.index("--pgdata") + 1])
                        (data_dir / "postmaster.pid").write_text(
                            "424242\n",
                            encoding="ascii",
                        )
                        events.append("start")
                    elif program == "createdb":
                        events.append("createdb")
                    elif program == "dropdb":
                        events.append("dropdb")
                    elif command[:3] == [
                        sys.executable,
                        "-m",
                        "unittest",
                    ]:
                        events.append("tests")
                        return subprocess.CompletedProcess(command, child_exit)
                    return subprocess.CompletedProcess(command, 0)

                def fake_stop(*_args, **_kwargs):
                    events.append("stop")
                    return True

                def fake_death(*_args, **_kwargs):
                    events.append("death")
                    return death_confirmed

                original_remove = launcher._remove_fixture_root

                def observed_remove(*args, **kwargs):
                    events.append("remove")
                    return original_remove(*args, **kwargs)

                with mock.patch.object(
                    launcher,
                    "_postgres_programs",
                    return_value=programs,
                ), mock.patch.object(
                    launcher,
                    "_python_driver_available",
                    return_value=True,
                ), mock.patch.object(
                    launcher,
                    "_run",
                    side_effect=fake_run,
                ), mock.patch.object(
                    launcher,
                    "_stop_server",
                    side_effect=fake_stop,
                ), mock.patch.object(
                    launcher,
                    "_server_is_dead",
                    side_effect=fake_death,
                ), mock.patch.object(
                    launcher,
                    "_remove_fixture_root",
                    side_effect=observed_remove,
                ), mock.patch.object(
                    launcher.getpass,
                    "getuser",
                    return_value="a93_test_user",
                ), mock.patch.object(
                    launcher.secrets,
                    "token_hex",
                    side_effect=("1" * 16, "2" * 64),
                ), mock.patch.object(
                    launcher.sys,
                    "stderr",
                    new_callable=io.StringIO,
                ):
                    exit_code = launcher.main()

                self.assertEqual(exit_code, expected_exit)
                self.assertEqual(
                    events[-4:],
                    ["dropdb", "stop", "death", "remove"],
                )
                self.assertEqual(len(roots), 1)
                if death_confirmed:
                    self.assertFalse(roots[0].exists())
                else:
                    self.assertTrue(roots[0].exists())
                    shutil.rmtree(roots[0])


@unittest.skipUnless(
    RUN_POSTGRES
    and TEST_DATABASE_DSN
    and TEST_CLUSTER_ROOT
    and TEST_SOCKET_DIR,
    "run through scripts/run_a93_postgres_tests.py",
)
class A93ResourceLimitsPostgresTests(unittest.TestCase):
    TABLES = (
        "platform_accounts",
        "companies",
        "users",
        "user_sessions",
        "user_company_roles",
        "projects",
        "estimates",
        "estimate_versions",
        "brigade_contracts",
        "brigade_payments",
        "project_payments",
        "brigade_contract_items",
        "work_journal",
        "estimate_reconciliations",
        "supply_requests",
        "supply_deliveries",
        "estimate_row_supply_allocations",
        "supplier_invoices",
        "warehouse_invoices",
        "warehouse_history",
        "warehouse_receipt_lots",
        "warehouse_movements",
        "warehouse_lot_movements",
        "agent_jobs",
        "audit_log",
        "staff",
        "accountable_payments",
        "accountable_expenses",
        "expense_reports",
        "salary_payments",
        "own_expenses",
        "expenses",
    )

    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_DSN)
        database_name = configured.get("dbname", "")
        socket_dir = configured.get("host", "")
        raw_root = Path(TEST_CLUSTER_ROOT)
        raw_socket = Path(TEST_SOCKET_DIR)

        if not re.fullmatch(r"a93_[0-9a-f]{16}", database_name):
            raise RuntimeError(
                "A9.3 PostgreSQL tests require an exact disposable database"
            )
        if (
            set(configured) != {
                "connect_timeout", "dbname", "host", "port", "user",
            }
            or configured.get("connect_timeout") != "5"
            or configured.get("port") != "55432"
            or configured.get("user") != TEST_DATABASE_USER
            or not re.fullmatch(r"[0-9a-f]{64}", TEST_CAPABILITY)
        ):
            raise RuntimeError(
                "A9.3 PostgreSQL connection contract is not launcher-owned"
            )
        if (
            not raw_root.is_absolute()
            or raw_root.parent != Path(tempfile.gettempdir()).resolve()
            or not re.fullmatch(
                r"stroyka-a93-pg-[A-Za-z0-9_]+",
                raw_root.name,
            )
            or raw_socket != raw_root / "socket"
            or socket_dir != str(raw_socket)
        ):
            raise RuntimeError(
                "A9.3 PostgreSQL tests require the launcher-owned socket"
            )

        raw_data = raw_root / "data"
        raw_marker = raw_root / "launcher.capability"
        for directory in (raw_root, raw_data, raw_socket):
            metadata = os.lstat(directory)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise RuntimeError("disposable fixture path is not private")
        marker_metadata = os.lstat(raw_marker)
        try:
            capability_fd = int(TEST_CAPABILITY_FD)
        except (TypeError, ValueError):
            raise RuntimeError(
                "A9.3 PostgreSQL capability descriptor is invalid"
            ) from None
        if capability_fd < 0 or str(capability_fd) != TEST_CAPABILITY_FD:
            raise RuntimeError(
                "A9.3 PostgreSQL capability descriptor is invalid"
            )
        descriptor_metadata = os.fstat(capability_fd)
        if (
            not stat.S_ISREG(marker_metadata.st_mode)
            or stat.S_ISLNK(marker_metadata.st_mode)
            or marker_metadata.st_uid != os.getuid()
            or stat.S_IMODE(marker_metadata.st_mode) != 0o600
            or marker_metadata.st_size != 64
            or (
                marker_metadata.st_dev,
                marker_metadata.st_ino,
            ) != (
                descriptor_metadata.st_dev,
                descriptor_metadata.st_ino,
            )
            or os.pread(capability_fd, 64, 0).decode("ascii")
            != TEST_CAPABILITY
        ):
            raise RuntimeError(
                "A9.3 PostgreSQL capability marker is invalid"
            )
        postgres_environment = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("PG")
        }
        if postgres_environment != {
            "PGDATABASE": database_name,
            "PGHOST": str(raw_socket),
            "PGPORT": "55432",
            "PGUSER": TEST_DATABASE_USER,
        }:
            raise RuntimeError(
                "A9.3 PostgreSQL inherited environment is invalid"
            )

        expected_root = raw_root.resolve()
        expected_socket = raw_socket.resolve()

        cls.connection = psycopg2.connect(
            dbname=database_name,
            user=TEST_DATABASE_USER,
            host=str(expected_socket),
            port=55432,
            connect_timeout=5,
        )
        cls.connection.autocommit = True
        with cls.connection.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.current_database(),"
                "pg_catalog.inet_server_addr(),"
                "pg_catalog.current_setting('data_directory'),"
                "pg_catalog.current_setting('unix_socket_directories'),"
                "pg_catalog.current_setting('client_encoding'),"
                "pg_catalog.current_setting('server_encoding'),"
                "pg_catalog.current_setting('listen_addresses'),"
                "CURRENT_USER,"
                "(SELECT pg_catalog.pg_get_userbyid(database.datdba) "
                "FROM pg_catalog.pg_database database "
                "WHERE database.datname=pg_catalog.current_database()),"
                "(SELECT pg_catalog.pg_get_userbyid(namespace.nspowner) "
                "FROM pg_catalog.pg_namespace namespace "
                "WHERE namespace.nspname='public'),"
                "pg_catalog.has_schema_privilege('public','CREATE,USAGE'),"
                "(SELECT pg_catalog.array_agg(database.datname "
                "ORDER BY database.datname) "
                "FROM pg_catalog.pg_database database "
                "WHERE NOT database.datistemplate)"
            )
            (
                current_database,
                server_address,
                data_directory,
                socket_directories,
                client_encoding,
                server_encoding,
                listen_addresses,
                current_user,
                database_owner,
                public_schema_owner,
                public_schema_access,
                database_inventory,
            ) = cur.fetchone()

        if current_database != database_name:
            raise RuntimeError("disposable database identity changed")
        if server_address is not None:
            raise RuntimeError("disposable PostgreSQL unexpectedly uses TCP")
        if listen_addresses != "":
            raise RuntimeError("disposable PostgreSQL has a TCP listener")
        if Path(data_directory).resolve().parent != expected_root:
            raise RuntimeError("PostgreSQL data directory escaped fixture root")
        if Path(socket_directories).resolve() != expected_socket:
            raise RuntimeError("PostgreSQL socket directory changed")
        if client_encoding != "UTF8":
            raise RuntimeError("PostgreSQL client encoding is not UTF8")
        if server_encoding != "UTF8":
            raise RuntimeError("PostgreSQL server encoding is not UTF8")
        if current_user != database_owner:
            raise RuntimeError("disposable database ownership changed")
        if public_schema_owner != "pg_database_owner":
            raise RuntimeError("disposable public schema ownership changed")
        if public_schema_access is not True:
            raise RuntimeError("disposable public schema access changed")
        if database_inventory != [database_name, "postgres"]:
            raise RuntimeError("disposable cluster database inventory changed")
        for directory in (expected_root, Path(data_directory), expected_socket):
            metadata = os.lstat(directory)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise RuntimeError("disposable fixture path is not private")

        cls.database_name = database_name
        cls.data_directory = Path(data_directory).resolve()
        cls.socket_directory = Path(socket_directories).resolve()
        cls._create_fixture_schema()

    @classmethod
    def _create_fixture_schema(cls):
        statements = (
            """CREATE TABLE public.platform_accounts (
                   id INTEGER PRIMARY KEY,
                   active BOOLEAN,
                   status TEXT
               )""",
            """CREATE TABLE public.companies (
                   id INTEGER PRIMARY KEY,
                   platform_account_id INTEGER,
                   name TEXT,
                   short_name TEXT,
                   active BOOLEAN
               )""",
            """CREATE TABLE public.users (
                   id INTEGER PRIMARY KEY,
                   name TEXT,
                   email TEXT,
                   password TEXT,
                   role TEXT,
                   project_id INTEGER,
                   project_name TEXT,
                   assigned_projects JSONB DEFAULT '[]'::jsonb,
                   assigned_packages JSONB DEFAULT '[]'::jsonb,
                   company_id INTEGER,
                   active BOOLEAN,
                   two_factor_enabled BOOLEAN,
                   failed_login_count INTEGER DEFAULT 0,
                   locked_until TIMESTAMP
               )""",
            """CREATE TABLE public.user_sessions (
                   id INTEGER PRIMARY KEY,
                   user_id INTEGER,
                   session_hash TEXT,
                   revoked_at TIMESTAMP,
                   expires_at TIMESTAMP,
                   two_factor_passed BOOLEAN
               )""",
            """CREATE TABLE public.user_company_roles (
                   id INTEGER PRIMARY KEY,
                   user_id INTEGER,
                   platform_account_id INTEGER,
                   company_id INTEGER,
                   role TEXT,
                   assigned_projects TEXT,
                   assigned_packages TEXT,
                   active BOOLEAN,
                   is_default BOOLEAN,
                   updated_at TIMESTAMP DEFAULT NOW()
               )""",
            """CREATE TABLE public.projects (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   name TEXT
               )""",
            """CREATE TABLE public.estimates (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   project_id INTEGER,
                   version TEXT,
                   sections_json TEXT,
                   status TEXT,
                   is_template BOOLEAN,
                   smeta_type TEXT,
                   work_package TEXT
               )""",
            """CREATE TABLE public.estimate_versions (
                   id INTEGER PRIMARY KEY,
                   estimate_id INTEGER,
                   sections_json TEXT
               )""",
            """CREATE TABLE public.brigade_contracts (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   project_id INTEGER,
                   work_package TEXT,
                   status TEXT
               )""",
            """CREATE TABLE public.brigade_payments (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   contract_id INTEGER,
                   project_payment_id INTEGER,
                   amount NUMERIC
               )""",
            """CREATE TABLE public.project_payments (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   company_scope_verified BOOLEAN NOT NULL DEFAULT FALSE,
                   project_name TEXT,
                   amount NUMERIC
               )""",
            """CREATE TABLE public.brigade_contract_items (
                   id INTEGER PRIMARY KEY,
                   contract_id INTEGER,
                   work_package TEXT,
                   quantity NUMERIC,
                   status TEXT,
                   source_type TEXT,
                   source_estimate_version_id INTEGER,
                   source_section_index INTEGER,
                   source_item_index INTEGER,
                   source_item_key TEXT
               )""",
            """CREATE TABLE public.work_journal (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   master_id INTEGER,
                   master_name TEXT,
                   project TEXT,
                   description TEXT,
                   unit TEXT,
                   quantity NUMERIC,
                   date TEXT,
                   status TEXT,
                   work_package TEXT
               )""",
            """CREATE TABLE public.estimate_reconciliations (
                   id INTEGER PRIMARY KEY,
                   base_estimate_id INTEGER,
                   next_estimate_id INTEGER,
                   status TEXT,
                   smeta_type TEXT,
                   work_package TEXT
               )""",
            """CREATE TABLE public.supply_requests (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   project TEXT,
                   status TEXT,
                   work_package TEXT,
                   items_json TEXT
               )""",
            """CREATE TABLE public.supply_deliveries (
                   id INTEGER PRIMARY KEY,
                   request_id INTEGER,
                   company_id INTEGER,
                   project TEXT,
                   work_package TEXT,
                   material_name TEXT,
                   unit TEXT,
                   received_quantity NUMERIC
               )""",
            """CREATE TABLE public.estimate_row_supply_allocations (
                   id INTEGER PRIMARY KEY,
                   request_id INTEGER,
                   request_item_index INTEGER,
                   company_id INTEGER,
                   source_estimate_id INTEGER,
                   source_section_index INTEGER,
                   source_item_index INTEGER,
                   allocation_quantity NUMERIC
               )""",
            """CREATE TABLE public.supplier_invoices (
                   id INTEGER PRIMARY KEY,
                   request_id INTEGER,
                   company_id INTEGER,
                   project_name TEXT,
                   amount NUMERIC,
                   paid_amount NUMERIC,
                   warehouse_invoice_id INTEGER
               )""",
            """CREATE TABLE public.warehouse_invoices (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   supply_request_id INTEGER,
                   supply_delivery_id INTEGER,
                   supplier_invoice_id INTEGER,
                   project TEXT,
                   items TEXT
               )""",
            """CREATE TABLE public.warehouse_history (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   work_package TEXT,
                   source_invoice_id INTEGER,
                   source_invoice_line_index INTEGER
               )""",
            """CREATE TABLE public.warehouse_receipt_lots (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   project_id INTEGER,
                   warehouse_invoice_id INTEGER,
                   invoice_line_index INTEGER
               )""",
            """CREATE TABLE public.warehouse_movements (
                   id INTEGER PRIMARY KEY,
                   company_id INTEGER,
                   work_package TEXT,
                   source_invoice_id INTEGER,
                   source_invoice_line_index INTEGER
               )""",
            """CREATE TABLE public.warehouse_lot_movements (
                   id INTEGER PRIMARY KEY,
                   lot_id INTEGER,
                   company_id INTEGER,
                   warehouse_movement_id INTEGER
               )""",
            """CREATE TABLE public.agent_jobs (
                   id BIGINT PRIMARY KEY,
                   owner_scope TEXT,
                   company_id INTEGER,
                   project_id INTEGER,
                   project_scope_id INTEGER,
                   requested_by_user_id INTEGER,
                   requested_by_role TEXT,
                   job_type TEXT,
                   idempotency_key TEXT,
                   correlation_id TEXT,
                   payload_json JSONB,
                   result_json JSONB,
                   status TEXT,
                   priority INTEGER,
                   attempts INTEGER,
                   max_attempts INTEGER,
                   locked_at TIMESTAMP,
                   locked_by TEXT,
                   lease_token TEXT,
                   lease_expires_at TIMESTAMP,
                   heartbeat_at TIMESTAMP,
                   started_at TIMESTAMP,
                   completed_at TIMESTAMP,
                   last_error TEXT
               )""",
            """CREATE TABLE public.audit_log (
                   id SERIAL PRIMARY KEY,
                   user_id INTEGER,
                   user_name TEXT,
                   user_role TEXT,
                   action TEXT,
                   entity_type TEXT,
                   entity_id INTEGER,
                   description TEXT,
                   project_name TEXT,
                   ip TEXT,
                   owner_scope TEXT,
                   company_id INTEGER,
                   project_id INTEGER,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )""",
            """CREATE TABLE public.staff (
                   id SERIAL PRIMARY KEY,
                   company_id INTEGER DEFAULT 1,
                   name TEXT,
                   role TEXT,
                   phone TEXT,
                   salary DOUBLE PRECISION DEFAULT 0,
                   project TEXT,
                   pay_type TEXT,
                   last_name TEXT,
                   first_name TEXT,
                   middle_name TEXT,
                   birth_date DATE,
                   citizenship TEXT,
                   address TEXT,
                   photo_url TEXT,
                   email_work TEXT,
                   email_personal TEXT,
                   phone_extra TEXT,
                   passport_series TEXT,
                   passport_number TEXT,
                   passport_issued_by TEXT,
                   passport_issued_date DATE,
                   inn TEXT,
                   snils TEXT,
                   specialization TEXT,
                   category TEXT,
                   employment_type TEXT,
                   hired_date DATE,
                   fired_date DATE,
                   status TEXT,
                   brigade TEXT,
                   bank_account TEXT,
                   bank_name TEXT,
                   bank_bik TEXT,
                   bank_corr TEXT,
                   ogrnip TEXT,
                   card_number TEXT,
                   signature_url TEXT,
                   notes TEXT
               )""",
            """CREATE TABLE public.staff_documents (
                   id SERIAL PRIMARY KEY,
                   staff_id INTEGER NOT NULL,
                   doc_type TEXT NOT NULL,
                   title TEXT,
                   file_url TEXT,
                   status TEXT,
                   signed_at DATE,
                   expires_at DATE,
                   notes TEXT,
                   created_by TEXT,
                   created_at TIMESTAMP DEFAULT NOW()
               )""",
            """CREATE TABLE public.accountable_payments (
                   id SERIAL PRIMARY KEY,
                   project_name TEXT,
                   given_to TEXT,
                   given_to_id INTEGER,
                   amount NUMERIC(14,2) DEFAULT 0,
                   spent_amount NUMERIC(14,2) DEFAULT 0,
                   payment_method TEXT,
                   purpose TEXT,
                   date TEXT,
                   added_by TEXT,
                   status TEXT
               )""",
            """CREATE TABLE public.accountable_expenses (
                   id SERIAL PRIMARY KEY,
                   payment_id INTEGER,
                   project_name TEXT,
                   amount NUMERIC(14,2) DEFAULT 0,
                   description TEXT,
                   photo_url TEXT,
                   date TEXT,
                   added_by TEXT
               )""",
            """CREATE TABLE public.expense_reports (
                   id SERIAL PRIMARY KEY,
                   employee_id INTEGER,
                   employee_name TEXT,
                   project_name TEXT,
                   report_type TEXT DEFAULT 'Авансовый отчёт',
                   purpose TEXT,
                   total_amount NUMERIC(14,2) DEFAULT 0,
                   issued_amount NUMERIC(14,2) DEFAULT 0,
                   spent_amount NUMERIC(14,2) DEFAULT 0,
                   balance NUMERIC(14,2) DEFAULT 0,
                   items_json TEXT,
                   photo_url TEXT,
                   date_from DATE,
                   date_to DATE,
                   status TEXT DEFAULT 'На утверждении',
                   approved_by TEXT,
                   approved_at DATE,
                   created_at TIMESTAMP DEFAULT NOW()
               )""",
            """CREATE TABLE public.salary_payments (
                   id SERIAL PRIMARY KEY,
                   staff_id INTEGER,
                   staff_name TEXT,
                   month TEXT,
                   amount NUMERIC(14,2) DEFAULT 0,
                   paid_by TEXT,
                   paid_date TEXT,
                   note TEXT,
                   created_at TIMESTAMP DEFAULT NOW()
               )""",
            """CREATE TABLE public.own_expenses (
                   id SERIAL PRIMARY KEY,
                   project_name TEXT,
                   employee_name TEXT,
                   employee_id INTEGER,
                   amount NUMERIC(14,2),
                   description TEXT,
                   photo_url TEXT,
                   date TEXT,
                   category TEXT,
                   status TEXT DEFAULT 'Ожидает',
                   approved_by TEXT,
                   telegram_id TEXT,
                   telegram_chat_id TEXT,
                   expense_id INTEGER
               )""",
            """CREATE TABLE public.expenses (
                   id SERIAL PRIMARY KEY,
                   project TEXT,
                   category TEXT,
                   own_expense_id INTEGER,
                   amount NUMERIC(14,2),
                   note TEXT,
                   date TEXT,
                   added_by TEXT,
                   source TEXT,
                   photo_url TEXT
               )""",
        )
        with cls.connection.cursor() as cur:
            for statement in statements:
                cur.execute(statement)

    @classmethod
    def tearDownClass(cls):
        connection = getattr(cls, "connection", None)
        if connection is not None:
            with connection.cursor() as cur:
                cur.execute(
                    "DROP TABLE IF EXISTS public.human_action_events CASCADE"
                )
                cur.execute(
                    "DROP TABLE IF EXISTS public.human_action_proposals CASCADE"
                )
                cur.execute(
                    "DROP FUNCTION IF EXISTS public."
                    "reject_human_action_ledger_mutation()"
                )
                for table in reversed(cls.TABLES):
                    cur.execute("DROP TABLE public." + table)
            connection.close()

    def setUp(self):
        self.source = self._reset_normal_fixture()

    def _reset_normal_fixture(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "TRUNCATE "
                + ",".join("public." + table for table in self.TABLES)
            )
        return self._seed_normal_fixture()

    def _seed_normal_fixture(self):
        base_sections = [{
            "name": "Private section",
            "items": [{
                "itemType": "material",
                "name": "Private material",
                "unit": "кг",
                "quantity": "10",
                "estimateItemKey": "base-material",
            }],
        }]
        target_sections = [{"name": "Работы", "items": []}]
        request_items = [{
            "sourceType": "estimate_material_control",
            "materialName": "Private material",
            "unit": "кг",
            "quantity": "10",
            "workPackage": "Основная",
            "estimateLineage": {
                "version": 2,
                "companyId": 4,
                "projectId": 17,
                "projectName": "Private project",
                "workPackage": "Основная",
                "validated": True,
                "sources": [{
                    "estimateId": 51,
                    "sectionIndex": 0,
                    "itemIndex": 0,
                    "materialName": "Private material",
                    "unit": "кг",
                    "validated": True,
                }],
            },
        }]
        invoice_items = [{
            "name": "Private material",
            "unit": "кг",
            "quantity": "3",
        }]
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (17,4,'Private project')"
            )
            cur.execute(
                """INSERT INTO public.estimates
                     (id,company_id,project_id,version,sections_json,status,
                      is_template,smeta_type,work_package)
                   VALUES
                     (51,4,17,'v1.0',%s,'Черновик',FALSE,
                      'Заказчик','Основная'),
                     (52,4,17,'v2.0',%s,'Активная',FALSE,
                      'Заказчик','Основная')""",
                (
                    json.dumps(base_sections, ensure_ascii=False),
                    json.dumps(target_sections, ensure_ascii=False),
                ),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,
                      smeta_type,work_package)
                   VALUES (91,51,52,'Черновик','Заказчик','Основная')"""
            )
            cur.execute(
                """INSERT INTO public.supply_requests
                     (id,company_id,project,status,work_package,items_json)
                   VALUES (61,4,'Private project','Новая','Основная',%s)""",
                (json.dumps(request_items, ensure_ascii=False),),
            )
            cur.execute(
                """INSERT INTO public.supply_deliveries
                     (id,request_id,company_id,project,work_package,
                      material_name,unit,received_quantity)
                   VALUES (71,61,4,'Private project','Основная',
                           'Private material','кг',3)"""
            )
            cur.execute(
                """INSERT INTO public.estimate_row_supply_allocations
                     (id,request_id,request_item_index,company_id,
                      source_estimate_id,source_section_index,
                      source_item_index,allocation_quantity)
                   VALUES (81,61,0,4,51,0,0,2)"""
            )
            cur.execute(
                """INSERT INTO public.supplier_invoices
                     (id,request_id,company_id) VALUES (91,61,4)"""
            )
            cur.execute(
                """INSERT INTO public.warehouse_invoices
                     (id,company_id,supply_request_id,supply_delivery_id,
                      supplier_invoice_id,project,items)
                   VALUES (101,4,61,71,91,'Private project',%s)""",
                (json.dumps(invoice_items, ensure_ascii=False),),
            )
            cur.execute(
                """INSERT INTO public.warehouse_history
                     (id,company_id,work_package,source_invoice_id,
                      source_invoice_line_index)
                   VALUES (111,4,'Основная',101,0)"""
            )
            cur.execute(
                """INSERT INTO public.warehouse_receipt_lots
                     (id,company_id,project_id,warehouse_invoice_id,
                      invoice_line_index)
                   VALUES (121,4,17,101,0)"""
            )
            cur.execute(
                """INSERT INTO public.warehouse_movements
                     (id,company_id,work_package,source_invoice_id,
                      source_invoice_line_index)
                   VALUES (131,4,'Основная',101,0)"""
            )
            cur.execute(
                """INSERT INTO public.warehouse_lot_movements
                     (id,lot_id,company_id,warehouse_movement_id)
                   VALUES (141,121,4,131)"""
            )
        return build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=target_sections,
        )

    @staticmethod
    def _runtime_claims(
        *, session_hash="a" * 64, project_id=17, job_id=123,
    ):
        return runtime_contract._parse_warehouse_anomaly_runtime_claims(
            {
                "authenticationKind": "cookie_session",
                "sessionHash": session_hash,
            },
            company_mode="company",
            company_id="4",
            body={
                "projectId": project_id,
                "jobId": job_id,
                "selected": {
                    "subjectKind": "warehouseInvoice",
                    "subjectId": 456,
                    "anomalyCode": "warehouse_invoice_project_mismatch",
                },
            },
        )

    def _reset_runtime_auth_fixture(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "TRUNCATE public.user_sessions,public.user_company_roles,"
                "public.users,public.companies,public.platform_accounts"
            )
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (7,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_sessions "
                "(id,user_id,session_hash,revoked_at,expires_at,"
                "two_factor_passed) VALUES "
                "(8,7,%s,NULL,clock_timestamp()+interval '1 hour',TRUE)",
                ("a" * 64,),
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active) "
                "VALUES (9,7,1,4,'директор',TRUE)"
            )

    @staticmethod
    def _runtime_artifact_values():
        report = {
            **combined(),
            "readOnlyTransaction": True,
            "rolledBack": True,
        }
        report["evidenceSha256"] = calculate_evidence_sha256(report)
        source = report["source"]
        payload = {
            "schemaVersion": 1,
            "eventType": "estimate.version_activated",
            "companyId": source["companyId"],
            "projectId": source["projectId"],
            "estimateId": source["estimateId"],
            "sourceRevision": source["sourceRevision"],
        }
        plan = build_estimate_revision_impact_job_plan(
            source_from_job_payload(payload),
        )
        return payload, report, plan

    def _insert_runtime_job(self, **overrides):
        payload, result, plan = self._runtime_artifact_values()
        row = {
            "id": 123,
            "owner_scope": "company",
            "company_id": 4,
            "project_id": 17,
            "project_scope_id": 17,
            "requested_by_user_id": None,
            "requested_by_role": "system",
            "job_type": plan.job_type,
            "idempotency_key": plan.idempotency_key,
            "correlation_id": plan.correlation_id,
            "payload_json": payload,
            "result_json": result,
            "status": "succeeded",
            "priority": plan.priority,
            "attempts": 1,
            "max_attempts": plan.max_attempts,
            "locked_at": None,
            "locked_by": None,
            "lease_token": None,
            "lease_expires_at": None,
            "heartbeat_at": None,
            "started_at": "2026-08-21 00:00:00",
            "completed_at": "2026-08-21 00:01:00",
            "last_error": "",
        }
        row.update(overrides)
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO public.agent_jobs (
                       id,owner_scope,company_id,project_id,project_scope_id,
                       requested_by_user_id,requested_by_role,job_type,
                       idempotency_key,correlation_id,payload_json,result_json,
                       status,priority,attempts,max_attempts,locked_at,locked_by,
                       lease_token,lease_expires_at,heartbeat_at,started_at,
                       completed_at,last_error
                   ) VALUES (
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                   )""",
                (
                    row["id"], row["owner_scope"], row["company_id"],
                    row["project_id"], row["project_scope_id"],
                    row["requested_by_user_id"], row["requested_by_role"],
                    row["job_type"], row["idempotency_key"],
                    row["correlation_id"],
                    json.dumps(
                        row["payload_json"], ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    json.dumps(
                        row["result_json"], ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    row["status"], row["priority"], row["attempts"],
                    row["max_attempts"], row["locked_at"], row["locked_by"],
                    row["lease_token"], row["lease_expires_at"],
                    row["heartbeat_at"], row["started_at"],
                    row["completed_at"], row["last_error"],
                ),
            )
        return row

    @classmethod
    def _new_connection(cls):
        return psycopg2.connect(
            dbname=cls.database_name,
            user=TEST_DATABASE_USER,
            host=str(cls.socket_directory),
            port=55432,
            connect_timeout=5,
        )

    def _snapshot(self):
        result = {}
        with self.connection.cursor() as cur:
            for table in self.TABLES:
                cur.execute(
                    "SELECT pg_catalog.row_to_json(row_value)::text "
                    "FROM (SELECT * FROM public."
                    + table
                    + " ORDER BY id) AS row_value"
                )
                result[table] = [row[0] for row in cur.fetchall()]
        return result

    def _run_private(self, operation):
        observed = _ObservedConnection(self._new_connection())
        observed.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = observed.cursor(cursor_factory=RealDictCursor)
        try:
            result = operation(cur)
        finally:
            observed.rollback()
            cur.close()
            observed.close()
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        return result, observed

    def _last_raw_rows(self, observed):
        call_index, rows = observed.observation["fetched"][-1]
        self.assertEqual(
            call_index,
            len(observed.observation["calls"]) - 1,
        )
        return rows

    def _run_public(self):
        observed = _ObservedConnection(self._new_connection())
        report = run_supply_warehouse_impact_audit(
            lambda: observed,
            self.source,
        )
        return report, observed

    def _assert_current_report(self, report):
        current = {
            key: value
            for key, value in report.items()
            if key not in {"readOnlyTransaction", "rolledBack"}
        }
        self.assertEqual(
            _validate_current_warehouse_anomaly_report(
                current,
                self.source,
            ),
            current,
        )

    def test_launcher_created_only_the_guarded_utf8_unix_socket_database(self):
        self.assertRegex(self.database_name, r"^a93_[0-9a-f]{16}$")
        self.assertEqual(self.data_directory.name, "data")
        self.assertEqual(self.socket_directory.name, "socket")

    def test_real_guarded_runtime_rolls_back_to_idle_before_close(self):
        before = self._snapshot()
        observed_connections = []
        close_observation = {}

        def before_close(real_connection):
            close_observation["transaction_status"] = (
                real_connection.get_transaction_status()
            )
            with self.connection.cursor() as observer:
                observer.execute(
                    "SELECT state,xact_start "
                    "FROM pg_catalog.pg_stat_activity WHERE pid=%s",
                    (real_connection.get_backend_pid(),),
                )
                close_observation["activity"] = observer.fetchall()

        def connect(**kwargs):
            observed = _ObservedConnection(
                psycopg2.connect(**kwargs),
                before_close=before_close,
            )
            observed_connections.append(observed)
            return observed

        lease = runtime_budget.acquire_warehouse_anomaly_runtime_slot()
        result = None
        backend_pid = None
        try:
            opened = runtime_budget.open_warehouse_anomaly_read_connection(
                {
                    "dbname": self.database_name,
                    "user": TEST_DATABASE_USER,
                    "password": "",
                    "host": str(self.socket_directory),
                    "port": "55432",
                },
                lease,
                connect=connect,
            )
            backend_pid = opened.get_backend_pid()

            def read(guarded_cursor):
                guarded_cursor.execute(
                    "SELECT pg_catalog.pg_backend_pid() AS backend_pid,"
                    "pg_catalog.current_setting(%s) AS isolation_level,"
                    "pg_catalog.current_setting(%s) AS read_only,"
                    "pg_catalog.current_setting(%s) AS statement_timeout,"
                    "pg_catalog.current_setting(%s) AS lock_timeout,"
                    "pg_catalog.current_setting(%s) AS idle_timeout,"
                    "pg_catalog.current_setting(%s) AS search_path",
                    (
                        "transaction_isolation",
                        "transaction_read_only",
                        "statement_timeout",
                        "lock_timeout",
                        "idle_in_transaction_session_timeout",
                        "search_path",
                    ),
                )
                rows = guarded_cursor.fetchall()
                self.assertEqual(len(rows), 1)
                return rows[0]

            result = runtime_budget.run_warehouse_anomaly_read_transaction(
                opened, lease, read,
            )
        finally:
            lease.release()

        self.assertEqual(len(observed_connections), 1)
        observed = observed_connections[0]
        self.assertEqual(result, {
            "backend_pid": backend_pid,
            "isolation_level": "repeatable read",
            "read_only": "on",
            "statement_timeout": "5s",
            "lock_timeout": "1s",
            "idle_timeout": "10s",
            "search_path": "pg_catalog, public",
        })
        self.assertEqual(observed.observation["sessions"], [])
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 0)
        self.assertTrue(observed.observation["closed"])
        calls = observed.observation["calls"]
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0], (runtime_budget._BEGIN_SQL, ()))
        self.assertEqual(calls[1], (
            runtime_budget._SETTINGS_SQL,
            runtime_budget._SETTINGS_PARAMS,
        ))
        self.assertTrue(
            " ".join(calls[2][0].split()).upper().startswith("SELECT ")
        )
        self.assertEqual(calls[3], (runtime_budget._ROLLBACK_SQL, ()))
        self.assertEqual(
            close_observation["transaction_status"],
            TRANSACTION_STATUS_IDLE,
        )
        self.assertEqual(close_observation["activity"], [("idle", None)])
        with self.connection.cursor() as observer:
            observer.execute(
                "SELECT pg_catalog.count(*) "
                "FROM pg_catalog.pg_stat_activity WHERE pid=%s",
                (backend_pid,),
            )
            self.assertEqual(observer.fetchone(), (0,))
        self.assertEqual(self._snapshot(), before)

    def test_real_live_authorization_uses_the_production_sql(self):
        self._reset_runtime_auth_fixture()
        claims = self._runtime_claims()
        result, observed = self._run_private(
            lambda cur: runtime_access._authorize_warehouse_anomaly_runtime_access(
                cur,
                claims,
            )
        )
        self.assertIs(result, claims)
        self.assertEqual(len(observed.observation["calls"]), 1)

        invalid_actor_mutations = (
            ("revoked", "UPDATE public.user_sessions SET revoked_at=NOW()"),
            (
                "expired",
                "UPDATE public.user_sessions "
                "SET expires_at=clock_timestamp()-interval '1 second'",
            ),
            (
                "session-2fa",
                "UPDATE public.user_sessions SET two_factor_passed=FALSE",
            ),
            ("user-active", "UPDATE public.users SET active=FALSE"),
            (
                "user-2fa",
                "UPDATE public.users SET two_factor_enabled=FALSE",
            ),
            (
                "role",
                "UPDATE public.user_company_roles SET role='зам_директора'",
            ),
            (
                "membership-active",
                "UPDATE public.user_company_roles SET active=FALSE",
            ),
            ("company-active", "UPDATE public.companies SET active=FALSE"),
            (
                "account-binding",
                "UPDATE public.user_company_roles SET platform_account_id=2",
            ),
            (
                "account-active",
                "UPDATE public.platform_accounts SET active=FALSE",
            ),
            (
                "account-status",
                "UPDATE public.platform_accounts SET status='suspended'",
            ),
            (
                "ambiguous-membership",
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active) "
                "VALUES (10,7,1,4,'директор',TRUE)",
            ),
        )
        for label, mutation in invalid_actor_mutations:
            self._reset_runtime_auth_fixture()
            with self.connection.cursor() as cur:
                cur.execute(mutation)
            with self.subTest(label=label):
                with self.assertRaises(ValueError) as raised:
                    self._run_private(
                        lambda cur: (
                            runtime_access
                            ._authorize_warehouse_anomaly_runtime_access(
                                cur,
                                claims,
                            )
                        )
                    )
                self.assertEqual(
                    raised.exception.code,
                    "warehouse_anomaly_runtime_authentication_required",
                )

        self._reset_runtime_auth_fixture()
        with self.assertRaises(ValueError) as raised:
            self._run_private(
                lambda cur: (
                    runtime_access._authorize_warehouse_anomaly_runtime_access(
                        cur,
                        self._runtime_claims(project_id=999),
                    )
                )
            )
        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_runtime_resource_not_found",
        )

    def test_real_auth_and_artifact_resolve_on_one_caller_cursor(self):
        self._reset_runtime_auth_fixture()
        stored = self._insert_runtime_job()
        claims = self._runtime_claims()

        def operation(cur):
            authorized = (
                runtime_access._authorize_warehouse_anomaly_runtime_access(
                    cur,
                    claims,
                )
            )
            artifact = runtime_access._resolve_warehouse_anomaly_runtime_artifact(
                cur,
                authorized,
            )
            return artifact

        artifact, observed = self._run_private(operation)

        self.assertEqual(len(observed.observation["calls"]), 2)
        self.assertIn(
            "FROM public.user_sessions",
            observed.observation["calls"][0][0],
        )
        self.assertIn(
            "FROM public.agent_jobs",
            observed.observation["calls"][1][0],
        )
        self.assertEqual(
            artifact["combinedReport"],
            stored["result_json"],
        )
        self.assertEqual(artifact["selected"]["subjectId"], 456)

    def test_real_artifact_case_accepts_128k_and_nulls_both_json_at_plus_one(self):
        claims = self._runtime_claims()
        empty_json_bytes = len('{"pad": ""}'.encode("utf-8"))
        exact_payload = {
            "pad": "a" * (128 * 1024 - empty_json_bytes),
        }
        self._insert_runtime_job(payload_json=exact_payload, result_json={})
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT octet_length(convert_to(payload_json::text,'UTF8')) "
                "FROM public.agent_jobs WHERE id=123"
            )
            self.assertEqual(cur.fetchone(), (128 * 1024,))
        with self.connection.cursor(cursor_factory=RealDictCursor) as raw:
            observation = {"calls": [], "fetched": []}
            recording = _RecordingCursor(raw, observation)
            row = runtime_access._read_warehouse_anomaly_runtime_artifact(
                recording,
                claims,
            )
        self.assertEqual(row["payload_bytes"], 128 * 1024)
        self.assertIs(type(row["payload_json"]), dict)

        with self.connection.cursor() as cur:
            cur.execute("TRUNCATE public.agent_jobs")
        oversized_payload = {
            "pad": "a" * (128 * 1024 + 1 - empty_json_bytes),
        }
        self._insert_runtime_job(payload_json=oversized_payload, result_json={})
        with self.connection.cursor(cursor_factory=RealDictCursor) as raw:
            observation = {"calls": [], "fetched": []}
            recording = _RecordingCursor(raw, observation)
            with self.assertRaises(ValueError) as raised:
                runtime_access._read_warehouse_anomaly_runtime_artifact(
                    recording,
                    claims,
                )
        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_runtime_artifact_invalid",
        )
        fetched = observation["fetched"][-1][1]
        self.assertEqual(len(fetched), 1)
        self.assertIsNone(fetched[0]["payload_json"])
        self.assertIsNone(fetched[0]["result_json"])
        self.assertEqual(fetched[0]["payload_bytes"], 128 * 1024 + 1)
        self.assertIs(fetched[0]["payload_limit_exceeded"], True)

    def test_real_artifact_projects_no_raw_terminal_text(self):
        marker = "PRIVATE-LAST-ERROR-MARKER-"
        self._insert_runtime_job(last_error=marker + "x" * 200000)
        with self.connection.cursor(cursor_factory=RealDictCursor) as raw:
            observation = {"calls": [], "fetched": []}
            recording = _RecordingCursor(raw, observation)
            with self.assertRaises(ValueError) as raised:
                runtime_access._read_warehouse_anomaly_runtime_artifact(
                    recording,
                    self._runtime_claims(),
                )
        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_runtime_artifact_invalid",
        )
        fetched = observation["fetched"][-1][1][0]
        self.assertNotIn("last_error", fetched)
        self.assertNotIn("locked_by", fetched)
        self.assertNotIn("lease_token", fetched)
        self.assertNotIn(marker, repr(fetched))
        self.assertIs(fetched["last_error_empty"], False)

    def test_real_delivery_loader_executes_the_production_sql(self):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            state, rows, overflow_fields = supply_audit._load_deliveries(
                cur,
                [61],
                _VariableByteBudget(),
            )

        self.assertEqual(state, _BOUNDED_ACCEPTED)
        self.assertEqual([row["delivery_id"] for row in rows], [71])
        self.assertEqual(overflow_fields, ())

    def test_real_utf8_boundary_and_mixed_query_wide_case_nulling(self):
        exact = "я" * (MAX_TEXT_FIELD_BYTES // 2)
        oversized = exact + "a"
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.supply_deliveries SET project=%s WHERE id=71",
                (exact,),
            )
        exact_budget = _VariableByteBudget()
        before = exact_budget.remaining_bytes
        (state, rows, overflow), observed = self._run_private(
            lambda cur: supply_audit._load_deliveries(
                cur,
                [61],
                exact_budget,
            )
        )
        raw = self._last_raw_rows(observed)
        self.assertEqual(state, _BOUNDED_ACCEPTED)
        self.assertEqual(rows[0]["delivery_project"], exact)
        self.assertEqual(raw[0]["field_delivery_project_bytes"], 1024)
        self.assertEqual(overflow, ())
        self.assertEqual(
            before - exact_budget.remaining_bytes,
            raw[0]["query_variable_bytes"],
        )

        with self.connection.cursor() as cur:
            cur.execute("TRUNCATE public.supply_deliveries")
            cur.executemany(
                """INSERT INTO public.supply_deliveries
                     (id,request_id,company_id,project,work_package,
                      material_name,unit,received_quantity)
                   VALUES (%s,61,4,%s,'Основная','marker','кг',3)""",
                ((71, "small-secret-marker"), (72, oversized)),
            )
        overflow_budget = _VariableByteBudget()
        before = overflow_budget.remaining_bytes
        (state, rows, overflow), observed = self._run_private(
            lambda cur: supply_audit._load_deliveries(
                cur,
                [61],
                overflow_budget,
            )
        )
        raw = self._last_raw_rows(observed)
        self.assertEqual(state, _BOUNDED_OVERFLOW)
        self.assertEqual(overflow, ("delivery_project",))
        self.assertEqual(overflow_budget.remaining_bytes, before)
        self.assertEqual([row["delivery_id"] for row in rows], [71, 72])
        for row in raw:
            self.assertTrue(all(row[field] is None for field in _DELIVERY_VARIABLES))
        serialized = json.dumps(raw, ensure_ascii=False)
        self.assertNotIn("small-secret-marker", serialized)
        self.assertNotIn(oversized, serialized)

    def test_real_ordered_limit_precedes_window_and_cardinality_wins(self):
        oversized = ("я" * (MAX_TEXT_FIELD_BYTES // 2)) + "a"
        with self.connection.cursor() as cur:
            cur.execute("TRUNCATE public.supply_deliveries")
            cur.executemany(
                """INSERT INTO public.supply_deliveries
                     (id,request_id,company_id,project,work_package,
                      material_name,unit,received_quantity)
                   VALUES (%s,61,4,%s,'Основная','Private material','кг',3)""",
                [
                    (row_id, oversized if row_id == 102 else "x")
                    for row_id in range(1, 103)
                ],
            )

        for poison_id, expected_overflow in (
            (102, ()),
            (101, ("delivery_project",)),
        ):
            with self.subTest(poison_id=poison_id):
                with self.connection.cursor() as cur:
                    cur.execute(
                        "UPDATE public.supply_deliveries SET project='x'"
                    )
                    cur.execute(
                        "UPDATE public.supply_deliveries SET project=%s "
                        "WHERE id=%s",
                        (oversized, poison_id),
                    )
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (state, rows, overflow), observed = self._run_private(
                    lambda cur: supply_audit._load_deliveries(
                        cur,
                        [61],
                        budget,
                    )
                )
                raw = self._last_raw_rows(observed)
                self.assertEqual(state, _BOUNDED_CARDINALITY)
                self.assertEqual([row["delivery_id"] for row in rows], list(
                    range(1, MAX_DOMAIN_ROWS + 2)
                ))
                self.assertEqual(overflow, expected_overflow)
                self.assertEqual(budget.remaining_bytes, before)
                for row in raw:
                    self.assertTrue(row["cardinality_limit_exceeded"])
                    self.assertFalse(row["payload_limit_exceeded"])
                    self.assertTrue(all(
                        row[field] is None
                        for field in _DELIVERY_VARIABLES
                    ))

    def test_prepared_production_gate_rechecks_bytes_after_row_growth(self):
        connection = self._new_connection()
        connection.autocommit = True
        observation = {"calls": [], "fetched": []}
        real_cursor = connection.cursor(cursor_factory=RealDictCursor)
        recording = _RecordingCursor(real_cursor, observation)
        prepared_name = "a93_delivery_gate"
        try:
            state, _rows, _overflow = supply_audit._load_deliveries(
                recording,
                [61],
                _VariableByteBudget(),
            )
            self.assertEqual(state, _BOUNDED_ACCEPTED)
            production_sql, production_params = observation["calls"][0]
            prepared_sql = real_cursor.mogrify(
                production_sql,
                production_params,
            ).decode("utf-8")
            real_cursor.execute(
                "PREPARE " + prepared_name + " AS " + prepared_sql
            )
            oversized = ("я" * (MAX_TEXT_FIELD_BYTES // 2)) + "a"
            with self.connection.cursor() as cur:
                cur.execute(
                    "UPDATE public.supply_deliveries SET project=%s WHERE id=71",
                    (oversized,),
                )
            real_cursor.execute("EXECUTE " + prepared_name)
            raw = [dict(row) for row in real_cursor.fetchall()]
        finally:
            try:
                real_cursor.execute("DEALLOCATE " + prepared_name)
            except psycopg2.Error:
                pass
            real_cursor.close()
            connection.close()

        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["field_delivery_project_bytes"], 1025)
        self.assertTrue(raw[0]["payload_limit_exceeded"])
        self.assertFalse(raw[0]["cardinality_limit_exceeded"])
        self.assertTrue(all(
            raw[0][field] is None for field in _DELIVERY_VARIABLES
        ))
        self.assertNotIn(oversized, json.dumps(raw, ensure_ascii=False))

    def test_real_emitted_null_and_fallback_utf8_accounting(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.estimates SET status=NULL,smeta_type=NULL,"
                "work_package=NULL WHERE id=52"
            )
        (_report, observed) = self._run_private(
            lambda cur: baseline_audit._collect_baseline_audit(
                cur,
                self.source,
                _VariableByteBudget(),
            )
        )
        target = self._last_raw_rows(observed)[0]
        self.assertEqual(target["status"], "Черновик")
        self.assertEqual(target["field_status_bytes"], 16)
        self.assertEqual(target["smeta_type"], "Заказчик")
        self.assertEqual(target["field_smeta_type_bytes"], 16)
        self.assertIsNone(target["work_package"])
        self.assertEqual(target["field_work_package_bytes"], 0)

        self.source = self._reset_normal_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.estimates SET smeta_type=NULL "
                "WHERE id IN (51,52)"
            )
            cur.execute(
                "UPDATE public.estimate_reconciliations "
                "SET smeta_type=NULL WHERE id=91"
            )
        (_report, observed) = self._run_private(
            lambda cur: baseline_audit._collect_baseline_audit(
                cur,
                self.source,
                _VariableByteBudget(),
            )
        )
        reconciliation = self._last_raw_rows(observed)[0]
        for value_key, byte_key in (
            (
                "reconciliation_smeta_type",
                "field_reconciliation_smeta_type_bytes",
            ),
            ("base_smeta_type", "field_base_smeta_type_bytes"),
            ("next_smeta_type", "field_next_smeta_type_bytes"),
        ):
            self.assertEqual(reconciliation[value_key], "Заказчик")
            self.assertEqual(reconciliation[byte_key], 16)

        self.source = self._reset_normal_fixture()
        with self.connection.cursor() as cur:
            cur.execute("UPDATE public.projects SET name=NULL WHERE id=17")
            cur.execute(
                "UPDATE public.estimates SET work_package=NULL,"
                "sections_json=NULL WHERE id=51"
            )
        (result, observed) = self._run_private(
            lambda cur: supply_audit._load_context(
                cur,
                {"companyId": 4, "projectId": 17, "baseEstimateId": 51},
                _VariableByteBudget(),
            )
        )
        state, rows, overflow = result
        context_row = self._last_raw_rows(observed)[0]
        self.assertEqual(state, _BOUNDED_ACCEPTED)
        self.assertEqual(overflow, ())
        self.assertIsNone(context_row["project_name"])
        self.assertEqual(context_row["field_project_name_bytes"], 0)
        self.assertEqual(context_row["base_work_package"], "Основная")
        self.assertEqual(context_row["field_base_work_package_bytes"], 16)
        self.assertIsNone(context_row["base_sections_json"])
        self.assertEqual(context_row["field_base_sections_json_bytes"], 0)
        self.assertFalse(any(key.startswith("field_") for key in rows[0]))

        self.source = self._reset_normal_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.supply_requests SET status=NULL,"
                "work_package=NULL WHERE id=61"
            )
        (result, observed) = self._run_private(
            lambda cur: supply_audit._load_requests(
                cur,
                {
                    "companyId": 4,
                    "projectName": "Private project",
                    "workPackage": "Основная",
                    "baseEstimateId": 51,
                },
                _VariableByteBudget(),
            )
        )
        state, rows, overflow = result
        request = self._last_raw_rows(observed)[0]
        self.assertEqual(state, _BOUNDED_ACCEPTED)
        self.assertEqual(overflow, ())
        self.assertEqual(request["request_status"], "")
        self.assertEqual(request["field_request_status_bytes"], 0)
        self.assertEqual(request["request_work_package"], "Основная")
        self.assertEqual(request["field_request_work_package_bytes"], 16)
        self.assertFalse(any(key.startswith("field_") for key in rows[0]))

        self.source = self._reset_normal_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.supply_deliveries SET project=NULL,"
                "work_package='',material_name=NULL,unit=NULL,"
                "received_quantity=NULL WHERE id=71"
            )
            cur.execute(
                "UPDATE public.estimate_row_supply_allocations "
                "SET allocation_quantity=NULL WHERE id=81"
            )
            cur.execute(
                "UPDATE public.warehouse_invoices SET project=NULL,items=NULL "
                "WHERE id=101"
            )
            cur.execute(
                "UPDATE public.warehouse_history SET work_package='' "
                "WHERE id=111"
            )
            cur.execute(
                "UPDATE public.warehouse_movements SET work_package=NULL "
                "WHERE id=131"
            )
        downstream = (
            (
                supply_audit._load_deliveries,
                ([61],),
                {
                    "delivery_project": (None, 0),
                    "delivery_work_package": ("Основная", 16),
                    "material_name": (None, 0),
                    "unit": (None, 0),
                    "received_quantity": (None, 0),
                },
            ),
            (
                supply_audit._load_allocations,
                ([61],),
                {"allocation_quantity": (None, 0)},
            ),
            (
                supply_audit._load_warehouse_invoices,
                ([61],),
                {"invoice_project": (None, 0), "items": (None, 0)},
            ),
            (
                supply_audit._load_history,
                ([101],),
                {"history_work_package": ("Основная", 16)},
            ),
            (
                supply_audit._load_movements,
                ([101],),
                {"movement_work_package": ("Основная", 16)},
            ),
        )
        for loader, arguments, expected in downstream:
            with self.subTest(loader=loader.__name__):
                (result, observed) = self._run_private(
                    lambda cur, loader=loader, arguments=arguments: loader(
                        cur,
                        *arguments,
                        _VariableByteBudget(),
                    )
                )
                state, rows, overflow = result
                raw = self._last_raw_rows(observed)[0]
                self.assertEqual(state, _BOUNDED_ACCEPTED)
                self.assertEqual(overflow, ())
                for field, (value, byte_count) in expected.items():
                    self.assertEqual(raw[field], value)
                    self.assertEqual(
                        raw["field_" + field + "_bytes"],
                        byte_count,
                    )
                self.assertFalse(any(
                    key.startswith("field_")
                    for key in rows[0]
                ))

    def test_real_numeric_text_accepts_64_bytes_and_rejects_65(self):
        exact = "1" + ("0" * (MAX_NUMERIC_FIELD_BYTES - 1))
        oversized = exact + "0"
        cases = (
            (
                "delivery",
                "UPDATE public.supply_deliveries "
                "SET received_quantity=%s WHERE id=71",
                supply_audit._load_deliveries,
                [61],
                "received_quantity",
                _DELIVERY_VARIABLES,
            ),
            (
                "allocation",
                "UPDATE public.estimate_row_supply_allocations "
                "SET allocation_quantity=%s WHERE id=81",
                supply_audit._load_allocations,
                [61],
                "allocation_quantity",
                ("allocation_quantity",),
            ),
        )
        for (
            label,
            update_sql,
            loader,
            parent_ids,
            field,
            variable_fields,
        ) in cases:
            with self.subTest(group=label, boundary="inclusive"):
                with self.connection.cursor() as cur:
                    cur.execute(update_sql, (exact,))
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (result, observed) = self._run_private(
                    lambda cur, loader=loader, parent_ids=parent_ids: loader(
                        cur,
                        parent_ids,
                        budget,
                    )
                )
                state, rows, overflow = result
                raw = self._last_raw_rows(observed)[0]
                self.assertEqual(state, _BOUNDED_ACCEPTED)
                self.assertEqual(rows[0][field], exact)
                self.assertEqual(raw["field_" + field + "_bytes"], 64)
                self.assertEqual(overflow, ())
                self.assertEqual(
                    before - budget.remaining_bytes,
                    raw["query_variable_bytes"],
                )

            with self.subTest(group=label, boundary="max_plus_one"):
                with self.connection.cursor() as cur:
                    cur.execute(update_sql, (oversized,))
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (result, observed) = self._run_private(
                    lambda cur, loader=loader, parent_ids=parent_ids: loader(
                        cur,
                        parent_ids,
                        budget,
                    )
                )
                state, _rows, overflow = result
                raw = self._last_raw_rows(observed)[0]
                self.assertEqual(state, _BOUNDED_OVERFLOW)
                self.assertEqual(overflow, (field,))
                self.assertEqual(budget.remaining_bytes, before)
                self.assertEqual(raw["field_" + field + "_bytes"], 65)
                self.assertTrue(all(
                    raw[name] is None for name in variable_fields
                ))

    def test_real_json_field_and_query_aggregate_boundaries(self):
        context_source = {
            "companyId": 4,
            "projectId": 17,
            "baseEstimateId": 51,
        }
        for size, expected_state in (
            (MAX_CANONICAL_SOURCE_BYTES, _BOUNDED_ACCEPTED),
            (MAX_CANONICAL_SOURCE_BYTES + 1, _BOUNDED_OVERFLOW),
        ):
            with self.subTest(group="context", size=size):
                value = _json_string_bytes(size)
                with self.connection.cursor() as cur:
                    cur.execute(
                        "UPDATE public.estimates SET sections_json=%s "
                        "WHERE id=51",
                        (value,),
                    )
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (result, observed) = self._run_private(
                    lambda cur: supply_audit._load_context(
                        cur,
                        context_source,
                        budget,
                    )
                )
                state, rows, overflow = result
                raw = self._last_raw_rows(observed)[0]
                self.assertEqual(state, expected_state)
                self.assertEqual(
                    raw["field_base_sections_json_bytes"],
                    size,
                )
                if expected_state == _BOUNDED_ACCEPTED:
                    self.assertEqual(rows[0]["base_sections_json"], value)
                    self.assertEqual(overflow, ())
                    self.assertLess(budget.remaining_bytes, before)
                else:
                    self.assertEqual(overflow, ("base_sections_json",))
                    self.assertEqual(budget.remaining_bytes, before)
                    self.assertTrue(all(
                        raw[field] is None for field in _CONTEXT_VARIABLES
                    ))

        self.source = self._reset_normal_fixture()
        for size, expected_state in (
            (MAX_SOURCE_JSON_BYTES, _BOUNDED_ACCEPTED),
            (MAX_SOURCE_JSON_BYTES + 1, _BOUNDED_OVERFLOW),
        ):
            with self.subTest(group="warehouse_invoice", size=size):
                value = _json_string_bytes(size)
                with self.connection.cursor() as cur:
                    cur.execute(
                        "UPDATE public.warehouse_invoices SET items=%s "
                        "WHERE id=101",
                        (value,),
                    )
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (result, observed) = self._run_private(
                    lambda cur: supply_audit._load_warehouse_invoices(
                        cur,
                        [61],
                        budget,
                    )
                )
                state, rows, overflow = result
                raw = self._last_raw_rows(observed)[0]
                self.assertEqual(state, expected_state)
                self.assertEqual(raw["field_items_bytes"], size)
                if expected_state == _BOUNDED_ACCEPTED:
                    self.assertEqual(rows[0]["items"], value)
                    self.assertEqual(overflow, ())
                    self.assertLess(budget.remaining_bytes, before)
                else:
                    self.assertEqual(overflow, ("items",))
                    self.assertEqual(budget.remaining_bytes, before)
                    self.assertIsNone(raw["invoice_project"])
                    self.assertIsNone(raw["items"])

        base_size, remainder = divmod(
            MAX_JSON_QUERY_BYTES,
            MAX_DOMAIN_ROWS,
        )
        exact_sizes = [
            base_size + (1 if index < remainder else 0)
            for index in range(MAX_DOMAIN_ROWS)
        ]
        request_context = {
            "companyId": 4,
            "projectName": "Private project",
            "workPackage": "Основная",
            "baseEstimateId": 51,
        }
        for total, sizes, expected_state in (
            (
                MAX_JSON_QUERY_BYTES,
                exact_sizes,
                _BOUNDED_ACCEPTED,
            ),
            (
                MAX_JSON_QUERY_BYTES + 1,
                [exact_sizes[0] + 1] + exact_sizes[1:],
                _BOUNDED_OVERFLOW,
            ),
        ):
            with self.subTest(group="request_aggregate", total=total):
                with self.connection.cursor() as cur:
                    cur.execute("TRUNCATE public.supply_requests")
                    cur.executemany(
                        """INSERT INTO public.supply_requests
                             (id,company_id,project,status,work_package,
                              items_json)
                           VALUES (%s,4,'Private project','Новая',
                                   'Основная',%s)""",
                        [
                            (1000 + index, _request_json_bytes(size))
                            for index, size in enumerate(sizes)
                        ],
                    )
                budget = _VariableByteBudget()
                before = budget.remaining_bytes
                (result, observed) = self._run_private(
                    lambda cur: supply_audit._load_requests(
                        cur,
                        request_context,
                        budget,
                    )
                )
                state, rows, overflow = result
                raw = self._last_raw_rows(observed)
                self.assertEqual(len(raw), MAX_DOMAIN_ROWS)
                self.assertEqual(state, expected_state)
                self.assertEqual(raw[0]["query_json_bytes"], total)
                self.assertEqual(overflow, ())
                if expected_state == _BOUNDED_ACCEPTED:
                    self.assertEqual(len(rows), MAX_DOMAIN_ROWS)
                    self.assertLess(budget.remaining_bytes, before)
                else:
                    self.assertEqual(budget.remaining_bytes, before)
                    for row in raw:
                        self.assertTrue(all(
                            row[field] is None
                            for field in _REQUEST_VARIABLES
                        ))

    def test_real_shared_cumulative_budget_is_inclusive_and_atomic(self):
        with self.connection.cursor() as cur:
            cur.execute("UPDATE public.projects SET name='P' WHERE id=17")
            cur.execute(
                "UPDATE public.estimates SET work_package=NULL,"
                "sections_json=NULL WHERE id=51"
            )
            cur.execute(
                "UPDATE public.supply_deliveries SET project='я',"
                "work_package=NULL,material_name=NULL,unit=NULL,"
                "received_quantity=NULL WHERE id=71"
            )
        context_source = {
            "companyId": 4,
            "projectId": 17,
            "baseEstimateId": 51,
        }

        exact_budget = _VariableByteBudget()
        exact_budget.consume(MAX_COLLECTOR_VARIABLE_BYTES - 35)

        def exact_operation(cur):
            context_result = supply_audit._load_context(
                cur,
                context_source,
                exact_budget,
            )
            self.assertEqual(exact_budget.remaining_bytes, 18)
            delivery_result = supply_audit._load_deliveries(
                cur,
                [61],
                exact_budget,
            )
            return context_result, delivery_result

        ((context_result, delivery_result), observed) = self._run_private(
            exact_operation
        )
        self.assertEqual(context_result[0], _BOUNDED_ACCEPTED)
        self.assertEqual(delivery_result[0], _BOUNDED_ACCEPTED)
        self.assertEqual(exact_budget.remaining_bytes, 0)
        raw_batches = [rows for _index, rows in observed.observation["fetched"]]
        self.assertEqual(raw_batches[0][0]["query_variable_bytes"], 17)
        self.assertEqual(raw_batches[1][0]["query_variable_bytes"], 18)

        overflow_budget = _VariableByteBudget()
        overflow_budget.consume(MAX_COLLECTOR_VARIABLE_BYTES - 34)

        def overflow_operation(cur):
            context_result = supply_audit._load_context(
                cur,
                context_source,
                overflow_budget,
            )
            self.assertEqual(overflow_budget.remaining_bytes, 17)
            delivery_result = supply_audit._load_deliveries(
                cur,
                [61],
                overflow_budget,
            )
            return context_result, delivery_result

        ((context_result, delivery_result), observed) = self._run_private(
            overflow_operation
        )
        self.assertEqual(context_result[0], _BOUNDED_ACCEPTED)
        self.assertEqual(delivery_result[0], _BOUNDED_OVERFLOW)
        self.assertEqual(delivery_result[2], ())
        self.assertEqual(overflow_budget.remaining_bytes, 17)
        raw = self._last_raw_rows(observed)[0]
        self.assertEqual(raw["query_variable_bytes"], 18)
        self.assertTrue(all(
            raw[field] is None for field in _DELIVERY_VARIABLES
        ))

    def test_real_public_overflow_paths_stop_at_exact_query_boundaries(self):
        def target_overflow():
            with self.connection.cursor() as cur:
                cur.execute(
                    "UPDATE public.estimates SET sections_json=%s WHERE id=52",
                    (_json_string_bytes(MAX_CANONICAL_SOURCE_BYTES + 1),),
                )

        def request_overflow():
            base_size, remainder = divmod(
                MAX_JSON_QUERY_BYTES,
                MAX_DOMAIN_ROWS,
            )
            sizes = [
                base_size + (1 if index < remainder else 0)
                for index in range(MAX_DOMAIN_ROWS)
            ]
            sizes[0] += 1
            with self.connection.cursor() as cur:
                cur.execute("TRUNCATE public.supply_requests")
                cur.executemany(
                    """INSERT INTO public.supply_requests
                         (id,company_id,project,status,work_package,items_json)
                       VALUES (%s,4,'Private project','Новая','Основная',%s)""",
                    [
                        (1000 + index, _request_json_bytes(size))
                        for index, size in enumerate(sizes)
                    ],
                )

        def delivery_overflow():
            with self.connection.cursor() as cur:
                cur.execute(
                    "UPDATE public.supply_deliveries "
                    "SET received_quantity=%s WHERE id=71",
                    ("1" + ("0" * MAX_NUMERIC_FIELD_BYTES),),
                )

        cases = (
            (
                "target",
                target_overflow,
                2,
                "impact_estimate_snapshot_too_large",
                "baseline",
                (
                    "version",
                    "sections_json",
                    "status",
                    "smeta_type",
                    "work_package",
                ),
            ),
            (
                "request",
                request_overflow,
                6,
                "supply_request_scan_limit_exceeded",
                "projection",
                _REQUEST_VARIABLES,
            ),
            (
                "delivery",
                delivery_overflow,
                7,
                "supply_warehouse_scan_limit_exceeded",
                "projection",
                _DELIVERY_VARIABLES,
            ),
        )
        for (
            label,
            arrange,
            expected_calls,
            reason,
            reason_location,
            variable_fields,
        ) in cases:
            with self.subTest(path=label):
                self.source = self._reset_normal_fixture()
                arrange()
                before = self._snapshot()
                report, observed = self._run_public()
                self.assertEqual(
                    len(observed.observation["calls"]),
                    expected_calls,
                )
                self.assertEqual(observed.observation["commits"], 0)
                self.assertEqual(observed.observation["rollbacks"], 1)
                self.assertEqual(self._snapshot(), before)
                if reason_location == "baseline":
                    self.assertEqual(report["reasonCounts"], {reason: 1})
                    self.assertEqual(
                        report["supplyWarehouseImpact"]["state"],
                        "not_collected",
                    )
                else:
                    projection = report["supplyWarehouseImpact"]
                    self.assertEqual(projection["reasonCounts"], {reason: 1})
                    self.assertEqual(projection["state"], "incomplete")
                raw = self._last_raw_rows(observed)
                for row in raw:
                    self.assertTrue(all(
                        row[field] is None for field in variable_fields
                    ))
                self._assert_current_report(report)

    def test_public_collector_uses_14_read_only_selects_and_changes_nothing(self):
        self.assertEqual(
            str(inspect.signature(
                supply_audit.collect_supply_warehouse_impact_audit
            )),
            "(cur, source)",
        )
        self.assertEqual(supply_audit.__all__, [
            "MAX_DOMAIN_ROWS",
            "SUPPLY_WAREHOUSE_REQUIRED_COLUMNS",
            "collect_supply_warehouse_impact_audit",
            "run_supply_warehouse_impact_audit",
        ])
        before = self._snapshot()
        observed = _ObservedConnection(self._new_connection())

        report = run_supply_warehouse_impact_audit(
            lambda: observed,
            self.source,
        )

        self.assertEqual(observed.observation["sessions"], [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        calls = observed.observation["calls"]
        self.assertEqual(len(calls), 14)
        expected_markers = (
            "pg_catalog.pg_attribute",
            "public.estimates",
            "public.estimate_reconciliations",
            "pg_catalog.pg_attribute",
            "public.projects",
            "public.supply_requests",
            "public.supply_deliveries",
            "public.estimate_row_supply_allocations",
            "public.supplier_invoices",
            "public.warehouse_invoices",
            "public.warehouse_history",
            "public.warehouse_receipt_lots",
            "public.warehouse_movements",
            "public.warehouse_lot_movements",
        )
        for (sql, _params), marker in zip(calls, expected_markers):
            normalized = " ".join(sql.split())
            self.assertTrue(normalized.upper().startswith("SELECT "))
            self.assertIn(marker, normalized)
            self.assertNotIn(";", normalized)

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(self._snapshot(), before)
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        for private_fragment in (
            '"field_',
            '"query_json_bytes"',
            '"query_text_bytes"',
            '"query_variable_bytes"',
            '"payload_limit_exceeded"',
            '"cardinality_limit_exceeded"',
        ):
            self.assertNotIn(private_fragment, serialized)
        current = {
            key: value
            for key, value in report.items()
            if key not in {"readOnlyTransaction", "rolledBack"}
        }
        validated = _validate_current_warehouse_anomaly_report(
            current,
            self.source,
        )
        self.assertEqual(validated, current)

    def _seed_assignment_daily_snapshot_fixture(self, *, oversized_daily=False):
        sections = [{
            "name": "Кабельные системы",
            "items": [{
                "name": "Монтаж кабеля",
                "unit": "м",
                "quantity": "10",
                "itemType": "work",
                "priceWork": 100,
                "priceMaterial": 0,
                "estimateItemKey": "work-1",
            }],
        }]
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.estimates SET sections_json=%s "
                "WHERE id=52 AND company_id=4 AND project_id=17",
                (json.dumps(sections, ensure_ascii=False),),
            )
            cur.execute(
                "INSERT INTO public.estimate_versions"
                "(id,estimate_id,sections_json) VALUES (401,52,%s)",
                (json.dumps(sections, ensure_ascii=False, separators=(",", ":")),),
            )
            cur.execute(
                "INSERT INTO public.brigade_contracts"
                "(id,company_id,project_id,work_package,status) "
                "VALUES (501,4,17,'Основная','Активен')"
            )
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                     (id,contract_id,work_package,quantity,status,source_type,
                      source_estimate_version_id,source_section_index,
                      source_item_index,source_item_key)
                   VALUES (601,501,'Основная',4,'Не начато','estimate',
                           401,0,0,'work-1')"""
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (18,5,'Private project')"
            )
            cur.execute(
                """INSERT INTO public.work_journal
                     (id,company_id,master_id,master_name,project,description,
                      unit,quantity,date,status,work_package)
                   VALUES
                     (701,4,31,'Иван Петров','Private project',%s,'м',2.5,
                      '2026-08-21','Подтверждено','Основная'),
                     (702,5,99,'PRIVATE FOREIGN','Private project',
                      'PRIVATE FOREIGN','м',99,'2026-08-21',
                      'Подтверждено','Основная')""",
                (("☃" * 1366) if oversized_daily else "Монтаж кабеля",),
            )

    def _run_assignment_daily_snapshot(self):
        observed = _ObservedConnection(self._new_connection())
        result = run_assignment_daily_snapshot(
            lambda: observed,
            AssignmentDailySnapshotRequest(
                4, 17, "2026-08-21", 52, 401, "Основная",
            ),
        )
        return result, observed

    def _assignment_daily_route_client(self):
        observed_connections = []

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def build_authentication(
            _request,
            authorization=None,
            csrf_token=None,
            *,
            require_csrf=True,
        ):
            if (
                authorization is not None
                or csrf_token != "csrf"
                or require_csrf is not True
            ):
                raise ValueError("invalid test authentication")
            return {
                "authenticationKind": "cookie_session",
                "sessionHash": "a" * 64,
            }

        app = FastAPI()
        register_assignment_daily_draft_preview_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "get_db": get_db,
            "build_cookie_session_authentication": build_authentication,
            "run_authorized_assignment_daily_snapshot": (
                run_authorized_assignment_daily_snapshot
            ),
        })
        return TestClient(app), observed_connections

    @staticmethod
    def _assignment_daily_route_headers():
        return {
            "Content-Type": "application/json",
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-CSRF-Token": "csrf",
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }

    @staticmethod
    def _assignment_daily_route_body():
        return {
            "projectId": 17,
            "date": "2026-08-21",
            "estimateId": 52,
            "estimateVersionId": 401,
            "workPackage": "Основная",
        }

    def test_real_assignment_daily_snapshot_is_tenant_bound_and_rolled_back(self):
        self._seed_assignment_daily_snapshot_fixture()
        before = self._snapshot()

        result, observed = self._run_assignment_daily_snapshot()

        self.assertEqual(result.state, "ready")
        self.assertEqual(result.review_codes, ())
        self.assertEqual(
            result.assignment_draft.items[0].available_quantity,
            "6",
        )
        self.assertIsNone(result.assignment_draft.items[0].assignee)
        self.assertEqual(len(result.daily_work_draft.items), 1)
        self.assertEqual(
            result.daily_work_draft.items[0].responsible_name,
            "Иван Петров",
        )
        self.assertNotIn("PRIVATE FOREIGN", repr(result))
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(observed.observation["sessions"], [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(len(observed.observation["calls"]), 4)
        for sql, _params in observed.observation["calls"]:
            normalized = " ".join(sql.split()).upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE ", "ALTER "):
                self.assertNotIn(mutation, normalized)
        self.assertEqual(self._snapshot(), before)

    def test_real_daily_utf8_overflow_is_case_nulled_before_python(self):
        self._seed_assignment_daily_snapshot_fixture(oversized_daily=True)
        before = self._snapshot()

        result, observed = self._run_assignment_daily_snapshot()

        self.assertEqual(result.state, "review_required")
        self.assertIn("daily_work_source_invalid", result.review_codes)
        self.assertEqual(result.daily_work_draft.items, ())
        self.assertNotIn("☃", repr(result))
        _call_index, raw_rows = observed.observation["fetched"][-1]
        self.assertEqual(len(raw_rows), 1)
        for field in (
            "description", "unit", "quantity", "master_name", "work_package",
        ):
            self.assertIsNone(raw_rows[0][field])
        self.assertGreater(raw_rows[0]["field_description_bytes"], 4096)
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertEqual(self._snapshot(), before)

    def test_real_assignment_daily_http_preview_authorizes_and_rolls_back(self):
        self._reset_runtime_auth_fixture()
        self._seed_assignment_daily_snapshot_fixture()
        before = self._snapshot()
        client, observed_connections = self._assignment_daily_route_client()

        response = client.post(
            "/assignment-daily-draft-previews",
            headers=self._assignment_daily_route_headers(),
            json=self._assignment_daily_route_body(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        value = response.json()
        self.assertEqual(value["state"], "ready")
        self.assertEqual(value["companyId"], 4)
        self.assertEqual(value["projectId"], 17)
        self.assertIs(value["previewOnly"], True)
        self.assertIs(value["applyAllowed"], False)
        self.assertEqual(value["writesAttempted"], 0)
        self.assertNotIn("PRIVATE FOREIGN", response.text)

        self.assertEqual(len(observed_connections), 1)
        observed = observed_connections[0]
        self.assertEqual(len(observed.observation["calls"]), 5)
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(self._snapshot(), before)

    def test_real_assignment_daily_http_rejects_other_role_before_business_reads(self):
        self._reset_runtime_auth_fixture()
        self._seed_assignment_daily_snapshot_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.user_company_roles SET role='прораб' "
                "WHERE company_id=4"
            )
        before = self._snapshot()
        client, observed_connections = self._assignment_daily_route_client()

        response = client.post(
            "/assignment-daily-draft-previews",
            headers=self._assignment_daily_route_headers(),
            json=self._assignment_daily_route_body(),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            "detail": "assignment_daily_preview_not_found",
        })
        self.assertEqual(len(observed_connections), 1)
        observed = observed_connections[0]
        self.assertEqual(len(observed.observation["calls"]), 2)
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(self._snapshot(), before)

    def test_accounting_exception_snapshot_is_one_company_read_only_and_detached(self):
        plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "TRUNCATE public.brigade_payments,public.project_payments,"
                "public.brigade_contracts,public.supplier_invoices,"
                "public.warehouse_invoices,public.accountable_expenses,"
                "public.accountable_payments,public.expense_reports,"
                "public.salary_payments,public.staff,public.own_expenses,"
                "public.expenses"
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (117,5,'Private project')"
            )
            cur.execute(
                "INSERT INTO public.brigade_contracts"
                "(id,company_id,project_id,status) VALUES "
                "(10,4,17,'active'),(110,5,117,'active'),"
                "(210,4,117,'quarantined-parent')"
            )
            cur.execute(
                "INSERT INTO public.project_payments"
                "(id,company_id,company_scope_verified,project_name,amount) "
                "VALUES (12,4,TRUE,'Private project',10.25),"
                "(112,5,TRUE,'Private project',999),"
                "(212,4,FALSE,'Private project',999)"
            )
            cur.execute(
                "INSERT INTO public.brigade_payments"
                "(id,company_id,contract_id,project_payment_id,amount) VALUES "
                "(11,4,10,12,10.25),(111,5,110,112,999),"
                "(211,4,210,212,999)"
            )
            cur.execute(
                "INSERT INTO public.supplier_invoices"
                "(id,company_id,project_name,amount,paid_amount,"
                "warehouse_invoice_id) VALUES "
                "(20,4,'Private project',100,100.01,21),"
                "(120,5,'Private project',1,999,121)"
            )
            cur.execute(
                "INSERT INTO public.warehouse_invoices"
                "(id,company_id,project,supplier_invoice_id) VALUES "
                "(21,4,'Private project',20),"
                "(121,5,'Private project',120)"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments"
                "(id,company_id,project_id,company_scope_verified,"
                "amount,spent_amount) VALUES "
                "(30,4,17,TRUE,100,40),(130,5,117,TRUE,999,999),"
                "(230,4,17,FALSE,999,999)"
            )
            cur.execute(
                "INSERT INTO public.accountable_expenses"
                "(id,payment_id,company_id,project_id,"
                "company_scope_verified,amount) VALUES "
                "(31,30,4,17,TRUE,40),(131,130,5,117,TRUE,999),"
                "(231,230,4,17,FALSE,999)"
            )
            cur.execute(
                "INSERT INTO public.expense_reports"
                "(id,company_id,project_id,company_scope_verified,"
                "issued_amount,spent_amount,balance) VALUES "
                "(40,4,17,TRUE,100,40,61),"
                "(140,5,117,TRUE,999,0,0),"
                "(240,4,17,FALSE,999,0,0)"
            )
            cur.execute(
                "INSERT INTO public.staff"
                "(id,company_id,company_scope_verified,name) VALUES "
                "(50,4,TRUE,'Private staff'),"
                "(150,5,TRUE,'Foreign private staff'),"
                "(250,4,FALSE,'Quarantined private staff')"
            )
            cur.execute(
                "INSERT INTO public.salary_payments"
                "(id,company_id,company_scope_verified,staff_id,month,amount) "
                "VALUES (51,4,TRUE,50,'2026-13',1),"
                "(151,5,TRUE,150,'PRIVATE',999),"
                "(251,4,FALSE,250,'PRIVATE',999)"
            )
            cur.execute(
                "INSERT INTO public.own_expenses"
                "(id,company_id,project_id,company_scope_verified,"
                "expense_id,amount) VALUES "
                "(60,4,17,TRUE,61,1),(160,5,117,TRUE,161,999),"
                "(260,4,17,FALSE,261,999)"
            )
            cur.execute(
                "INSERT INTO public.expenses"
                "(id,company_id,project_id,company_scope_verified,"
                "own_expense_id,amount) VALUES "
                "(61,4,17,TRUE,60,1),(161,5,117,TRUE,160,999),"
                "(261,4,17,FALSE,260,999)"
            )

        before = self._snapshot()
        observed = _ObservedConnection(self._new_connection())
        report = run_accounting_exception_snapshot(lambda: observed, 4)
        after = self._snapshot()

        self.assertEqual(before, after)
        self.assertEqual(report["state"], "review_required")
        self.assertEqual(set(report["sourceCounts"].values()), {1})
        self.assertEqual(
            {finding["reasonCode"] for finding in report["findings"]},
            {
                "accounting_supplier_invoice_overpaid",
                "accounting_expense_report_balance_mismatch",
                "accounting_salary_month_invalid",
            },
        )
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(len(observed.observation["calls"]), 13)
        self.assertEqual(len(observed.observation["fetched"]), 12)
        self.assertEqual(
            observed.observation["sessions"],
            [{
                "readonly": True,
                "autocommit": False,
                "isolation_level": "REPEATABLE READ",
            }],
        )
        forbidden = {
            "purpose", "note", "notes", "photo_url", "items_json",
            "bank_account", "employee_name", "staff_name",
        }
        for _call_index, rows in observed.observation["fetched"]:
            for row in rows:
                self.assertTrue(forbidden.isdisjoint(row))

    def test_accounting_exception_snapshot_real_numeric_and_row_boundaries(self):
        plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )
        finally:
            schema_connection.close()

        source_tables = (
            "brigade_payments,project_payments,brigade_contracts,"
            "supplier_invoices,warehouse_invoices,accountable_expenses,"
            "accountable_payments,expense_reports,salary_payments,staff,"
            "own_expenses,expenses"
        )
        numeric_64 = "9" * 64
        with self.connection.cursor() as cur:
            cur.execute("TRUNCATE public." + source_tables.replace(",", ",public."))
            cur.execute(
                "INSERT INTO public.brigade_contracts"
                "(id,company_id,project_id,status) VALUES (10,4,17,'active')"
            )
            cur.execute(
                "INSERT INTO public.project_payments"
                "(id,company_id,company_scope_verified,project_name,amount) "
                "VALUES (12,4,TRUE,'Private project',%s)",
                (numeric_64,),
            )
            cur.execute(
                "INSERT INTO public.brigade_payments"
                "(id,company_id,contract_id,project_payment_id,amount) "
                "VALUES (11,4,10,12,%s)",
                (numeric_64,),
            )

        before = self._snapshot()
        accepted_connection = _ObservedConnection(self._new_connection())
        accepted = run_accounting_exception_snapshot(
            lambda: accepted_connection, 4
        )
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(accepted["state"], "clear")
        self.assertEqual(len(accepted_connection.observation["calls"]), 13)
        accepted_payment = accepted_connection.observation["fetched"][1][1][0]
        self.assertEqual(accepted_payment["amount"], numeric_64)
        self.assertEqual(accepted_payment["field_amount_bytes"], 64)
        self.assertFalse(accepted_payment["payload_limit_exceeded"])

        numeric_65 = "1" + ("0" * 64)
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.brigade_payments SET amount=%s WHERE id=11",
                (numeric_65,),
            )
        before = self._snapshot()
        overflow_connection = _ObservedConnection(self._new_connection())
        overflow = run_accounting_exception_snapshot(
            lambda: overflow_connection, 4
        )
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(overflow["state"], "incomplete")
        self.assertEqual(overflow["findings"], [])
        self.assertEqual(len(overflow_connection.observation["calls"]), 3)
        overflow_payment = overflow_connection.observation["fetched"][1][1][0]
        self.assertIsNone(overflow_payment["amount"])
        self.assertEqual(overflow_payment["field_amount_bytes"], 65)
        self.assertTrue(overflow_payment["payload_limit_exceeded"])

        with self.connection.cursor() as cur:
            cur.execute("TRUNCATE public." + source_tables.replace(",", ",public."))
            cur.execute(
                "INSERT INTO public.staff"
                "(id,company_id,company_scope_verified,name) "
                "SELECT 1000+value,4,TRUE,'bounded' "
                "FROM pg_catalog.generate_series(1,1001) AS value"
            )
        before = self._snapshot()
        cardinality_connection = _ObservedConnection(self._new_connection())
        cardinality = run_accounting_exception_snapshot(
            lambda: cardinality_connection, 4
        )
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(cardinality["state"], "incomplete")
        self.assertEqual(cardinality["findings"], [])
        self.assertEqual(len(cardinality_connection.observation["calls"]), 10)
        raw_staff = cardinality_connection.observation["fetched"][-1][1]
        self.assertEqual(len(raw_staff), 1001)
        self.assertTrue(all(
            row["cardinality_limit_exceeded"] is True for row in raw_staff
        ))
        self.assertTrue(all(
            row["payload_limit_exceeded"] is False for row in raw_staff
        ))

    def _accounting_exception_route_client(self):
        observed_connections = []

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def build_authentication(
            _request,
            authorization=None,
            csrf_token=None,
            *,
            require_csrf=True,
        ):
            if (
                authorization is not None
                or csrf_token is not None
                or require_csrf is not False
            ):
                raise ValueError("invalid test authentication")
            return {
                "authenticationKind": "cookie_session",
                "sessionHash": "a" * 64,
            }

        app = FastAPI()
        register_accounting_exception_check_routes(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "get_db": get_db,
            "finance_roles": (
                "директор", "зам_директора", "бухгалтер",
            ),
            "build_cookie_session_authentication": build_authentication,
            "run_authorized_accounting_exception_snapshot": (
                run_authorized_accounting_exception_snapshot
            ),
        })
        return TestClient(app), observed_connections

    @staticmethod
    def _accounting_exception_route_headers():
        return {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }

    def _seed_accounting_exception_route_fixture(self):
        plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )
        finally:
            schema_connection.close()
        self._reset_runtime_auth_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.user_company_roles SET role='бухгалтер' "
                "WHERE company_id=4"
            )
            cur.execute(
                "TRUNCATE public.brigade_payments,public.project_payments,"
                "public.brigade_contracts,public.supplier_invoices,"
                "public.warehouse_invoices,public.accountable_expenses,"
                "public.accountable_payments,public.expense_reports,"
                "public.salary_payments,public.staff,public.own_expenses,"
                "public.expenses"
            )
            cur.execute(
                "INSERT INTO public.staff"
                "(id,company_id,company_scope_verified,name) VALUES "
                "(50,4,TRUE,'Local staff'),"
                "(150,5,TRUE,'PRIVATE FOREIGN STAFF')"
            )
            cur.execute(
                "INSERT INTO public.salary_payments"
                "(id,company_id,company_scope_verified,staff_id,month,amount) "
                "VALUES (51,4,TRUE,50,'2026-13',1),"
                "(151,5,TRUE,150,'PRIVATE',999)"
            )

    def test_real_accounting_exception_http_authorizes_one_company_and_rolls_back(self):
        self._seed_accounting_exception_route_fixture()
        before = self._snapshot()
        client, observed_connections = self._accounting_exception_route_client()

        response = client.get(
            "/accounting-exception-checks",
            headers=self._accounting_exception_route_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"], "no-store, max-age=0",
        )
        value = response.json()
        self.assertEqual(value["companyId"], 4)
        self.assertEqual(value["state"], "review_required")
        self.assertEqual(value["findingCount"], 1)
        self.assertEqual(
            value["findings"][0]["reasonCode"],
            "accounting_salary_month_invalid",
        )
        self.assertNotIn("PRIVATE", response.text)

        self.assertEqual(len(observed_connections), 1)
        observed = observed_connections[0]
        self.assertEqual(len(observed.observation["calls"]), 15)
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(observed.observation["sessions"], [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        expected_markers = (
            "pg_catalog.set_config",
            "public.user_sessions",
            "public.user_company_roles",
            "public.brigade_contracts",
            "public.brigade_payments",
            "public.project_payments",
            "public.supplier_invoices",
            "public.warehouse_invoices",
            "public.accountable_payments",
            "public.accountable_expenses",
            "public.expense_reports",
            "public.staff",
            "public.salary_payments",
            "public.own_expenses",
            "public.expenses",
        )
        for (sql, _params), marker in zip(
            observed.observation["calls"], expected_markers,
        ):
            normalized = " ".join(sql.split())
            self.assertTrue(normalized.upper().startswith("SELECT "))
            self.assertIn(marker, normalized)
            for mutation in ("INSERT ", "UPDATE ", "DELETE ", "ALTER "):
                self.assertNotIn(mutation, normalized.upper())
        self.assertNotIn("PRIVATE", repr(observed.observation["fetched"]))
        self.assertEqual(self._snapshot(), before)

    def test_real_accounting_exception_http_rejects_other_role_before_business_reads(self):
        self._seed_accounting_exception_route_fixture()
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.user_company_roles SET role='прораб' "
                "WHERE company_id=4"
            )
        before = self._snapshot()
        client, observed_connections = self._accounting_exception_route_client()

        response = client.get(
            "/accounting-exception-checks",
            headers=self._accounting_exception_route_headers(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {
            "detail": "accounting_exception_review_request_forbidden",
        })
        self.assertEqual(len(observed_connections), 1)
        observed = observed_connections[0]
        self.assertEqual(len(observed.observation["calls"]), 3)
        self.assertEqual(observed.observation["commits"], 0)
        self.assertEqual(observed.observation["rollbacks"], 1)
        self.assertTrue(observed.observation["closed"])
        self.assertEqual(self._snapshot(), before)

    def test_accounting_ownership_schema_is_idempotent_and_preserves_business_rows(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (19,4,'Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.staff(id,company_id,name,project) "
                "VALUES (100,4,'PRIVATE STAFF','Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,project_name,given_to_id,amount,spent_amount,purpose) "
                "VALUES (200,'Exact accounting',100,100,20,'PRIVATE PURPOSE')"
            )
            cur.execute(
                "INSERT INTO public.accountable_expenses "
                "(id,payment_id,project_name,amount,description) "
                "VALUES (300,200,'Exact accounting',20,'PRIVATE DESCRIPTION')"
            )
            cur.execute(
                "INSERT INTO public.expense_reports "
                "(id,employee_id,project_name,total_amount,issued_amount,"
                "spent_amount,balance,purpose) VALUES "
                "(400,100,'Exact accounting',20,100,20,80,'PRIVATE REPORT')"
            )
            cur.execute(
                "INSERT INTO public.salary_payments(id,staff_id,amount,note) "
                "VALUES (500,100,50,'PRIVATE SALARY')"
            )
            cur.execute(
                "INSERT INTO public.own_expenses "
                "(id,project_name,employee_id,amount,description,expense_id) "
                "VALUES (600,'Exact accounting',999,10,'PRIVATE OWN',700)"
            )
            cur.execute(
                "INSERT INTO public.expenses "
                "(id,project,own_expense_id,amount,note) "
                "VALUES (700,'Exact accounting',600,10,'PRIVATE MANUAL')"
            )

        business_columns = {
            "staff": "id,company_id,name,project",
            "accountable_payments": (
                "id,project_name,given_to_id,amount,spent_amount,purpose"
            ),
            "accountable_expenses": (
                "id,payment_id,project_name,amount,description"
            ),
            "expense_reports": (
                "id,employee_id,project_name,total_amount,issued_amount,"
                "spent_amount,balance,purpose"
            ),
            "salary_payments": "id,staff_id,amount,note",
            "own_expenses": (
                "id,project_name,employee_id,amount,description,expense_id"
            ),
            "expenses": "id,project,own_expense_id,amount,note",
        }

        def business_snapshot():
            result = {}
            with self.connection.cursor() as cur:
                for table, columns in business_columns.items():
                    cur.execute(
                        "SELECT pg_catalog.row_to_json(row_value)::text FROM "
                        f"(SELECT {columns} FROM public.{table} ORDER BY id) "
                        "AS row_value"
                    )
                    result[table] = [row[0] for row in cur.fetchall()]
            return result

        before = business_snapshot()
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT table_name,column_name FROM information_schema.columns "
                "WHERE table_schema='public' "
                "AND column_name IN ('company_scope_verified','project_id') "
                "AND table_name=ANY(%s) ORDER BY table_name,column_name",
                (list(business_columns),),
            )
            schema_before_dry_run = cur.fetchall()

        dry_connection = self._new_connection()
        try:
            dry_report = run_accounting_ownership_schema(dry_connection)
        finally:
            dry_connection.close()
        self.assertTrue(dry_report["dryRun"])
        self.assertEqual(dry_report["writesAttempted"], 0)
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT table_name,column_name FROM information_schema.columns "
                "WHERE table_schema='public' "
                "AND column_name IN ('company_scope_verified','project_id') "
                "AND table_name=ANY(%s) ORDER BY table_name,column_name",
                (list(business_columns),),
            )
            self.assertEqual(cur.fetchall(), schema_before_dry_run)

        plan = build_accounting_ownership_schema_plan()
        reports = []
        for _attempt in range(2):
            apply_connection = self._new_connection()
            try:
                reports.append(run_accounting_ownership_schema(
                    apply_connection,
                    apply=True,
                    expected_change_count=plan["changeCount"],
                    expected_plan_sha256=plan["planSha256"],
                ))
            finally:
                apply_connection.close()

        self.assertTrue(all(report["schemaReady"] for report in reports))
        self.assertEqual(business_snapshot(), before)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            for table in business_columns:
                cur.execute(
                    f"SELECT company_scope_verified FROM public.{table} "
                    "ORDER BY id"
                )
                self.assertTrue(all(
                    row["company_scope_verified"] is False
                    for row in cur.fetchall()
                ))

    def test_accounting_ownership_constraints_and_inventory_fail_closed(self):
        plan = build_accounting_ownership_schema_plan()
        apply_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                apply_connection,
                apply=True,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )
        finally:
            apply_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (19,4,'Exact accounting'),(20,5,'Duplicate scope'),"
                "(21,4,'Duplicate scope')"
            )
            cur.execute(
                "INSERT INTO public.staff(id,company_id,name,project) VALUES "
                "(100,4,'PRIVATE STAFF','Exact accounting'),"
                "(101,4,'PRIVATE AMBIGUOUS','Duplicate scope'),"
                "(102,5,'PRIVATE CONFLICT','Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,project_name,given_to_id,amount,spent_amount,purpose) "
                "VALUES "
                "(200,'Exact accounting',100,100,20,'PRIVATE'),"
                "(201,'Exact accounting',999,100,20,'PRIVATE ORPHAN'),"
                "(202,'Exact accounting',102,100,20,'PRIVATE CONFLICT')"
            )
            cur.execute(
                "INSERT INTO public.accountable_expenses "
                "(id,payment_id,project_name,amount,description) "
                "VALUES (300,200,'Exact accounting',20,'PRIVATE')"
            )
            cur.execute(
                "INSERT INTO public.expense_reports "
                "(id,employee_id,project_name,total_amount,issued_amount,"
                "spent_amount,balance,purpose) VALUES "
                "(400,100,'Exact accounting',20,100,20,80,'PRIVATE')"
            )
            cur.execute(
                "INSERT INTO public.salary_payments(id,staff_id,amount,note) "
                "VALUES (500,100,50,'PRIVATE')"
            )
            cur.execute(
                "INSERT INTO public.own_expenses "
                "(id,project_name,employee_id,amount,description,expense_id) "
                "VALUES (600,'Exact accounting',999,10,'PRIVATE',700)"
            )
            cur.execute(
                "INSERT INTO public.expenses "
                "(id,project,own_expense_id,amount,note) "
                "VALUES (700,'Exact accounting',600,10,'PRIVATE')"
            )

        inventory_connection = self._new_connection()
        try:
            inventory = run_accounting_ownership_inventory(inventory_connection)
        finally:
            inventory_connection.close()
        self.assertEqual(
            inventory["summary"],
            {"provable": 7, "ambiguous": 1, "orphaned": 1, "conflicting": 2},
        )
        self.assertNotIn("PRIVATE", repr(inventory))

        constraint_connection = self._new_connection()
        try:
            with constraint_connection.cursor() as cur:
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    cur.execute(
                        "UPDATE public.staff SET company_id=NULL,"
                        "company_scope_verified=TRUE WHERE id=100"
                    )
                constraint_connection.rollback()
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    cur.execute(
                        "UPDATE public.accountable_payments SET company_id=4,"
                        "project_id=19,amount='NaN'::numeric,"
                        "company_scope_verified=TRUE WHERE id=200"
                    )
                constraint_connection.rollback()
                cur.execute(
                    "UPDATE public.own_expenses SET company_id=4,"
                    "project_id=NULL,company_scope_verified=TRUE WHERE id=600"
                )
                constraint_connection.rollback()
        finally:
            constraint_connection.close()

    def test_accounting_ownership_backfill_updates_only_provable_rows_and_is_idempotent(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(19,4,'Exact accounting'),(20,4,'Duplicate scope'),"
                "(21,5,'Duplicate scope')"
            )
            cur.execute(
                "INSERT INTO public.staff(id,company_id,name,project) VALUES "
                "(100,4,'PRIVATE STAFF','Exact accounting'),"
                "(101,4,'PRIVATE QUARANTINE','Duplicate scope')"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,project_name,given_to_id,amount,spent_amount,purpose) "
                "VALUES (200,'Exact accounting',100,100,20,'PRIVATE PAYMENT')"
            )
            cur.execute(
                "INSERT INTO public.accountable_expenses "
                "(id,payment_id,project_name,amount,description) "
                "VALUES (300,200,'Exact accounting',20,'PRIVATE EXPENSE')"
            )
            cur.execute(
                "INSERT INTO public.expense_reports "
                "(id,employee_id,project_name,total_amount,issued_amount,"
                "spent_amount,balance,purpose) VALUES "
                "(400,100,'Exact accounting',20,100,20,80,'PRIVATE REPORT')"
            )
            cur.execute(
                "INSERT INTO public.salary_payments(id,staff_id,amount,note) "
                "VALUES (500,100,50,'PRIVATE SALARY')"
            )
            cur.execute(
                "INSERT INTO public.own_expenses "
                "(id,project_name,employee_id,amount,description,expense_id) "
                "VALUES (600,'Exact accounting',999,10,'PRIVATE OWN',700)"
            )
            cur.execute(
                "INSERT INTO public.expenses "
                "(id,project,own_expense_id,amount,note) "
                "VALUES (700,'Exact accounting',600,10,'PRIVATE MANUAL')"
            )

        dry_connection = self._new_connection()
        try:
            dry = run_accounting_ownership_backfill(dry_connection)
        finally:
            dry_connection.close()
        self.assertEqual(dry["readyCount"], 7)
        self.assertEqual(dry["quarantinedCount"], 1)
        self.assertEqual(dry["conflictingCount"], 0)
        self.assertEqual(dry["writesAttempted"], 0)

        apply_connection = self._new_connection()
        try:
            applied = run_accounting_ownership_backfill(
                apply_connection,
                apply=True,
                expected_ready_count=dry["readyCount"],
                expected_plan_sha256=dry["planSha256"],
            )
        finally:
            apply_connection.close()
        self.assertEqual(applied["updated"], 7)
        self.assertTrue(applied["complete"])

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            for table, record_id in (
                ("staff", 100),
                ("accountable_payments", 200),
                ("accountable_expenses", 300),
                ("expense_reports", 400),
                ("salary_payments", 500),
                ("own_expenses", 600),
                ("expenses", 700),
            ):
                project_column = (
                    "NULL::integer AS project_id"
                    if table in ("staff", "salary_payments")
                    else "project_id"
                )
                cur.execute(
                    f"SELECT company_id,{project_column},company_scope_verified "
                    f"FROM public.{table} WHERE id=%s",
                    (record_id,),
                )
                row = cur.fetchone()
                self.assertEqual(row["company_id"], 4)
                if table not in ("staff", "salary_payments"):
                    self.assertEqual(row["project_id"], 19)
                self.assertIs(row["company_scope_verified"], True)
            cur.execute(
                "SELECT company_id,company_scope_verified,name FROM public.staff "
                "WHERE id=101"
            )
            quarantined = cur.fetchone()
            self.assertEqual(quarantined["company_id"], 4)
            self.assertIs(quarantined["company_scope_verified"], False)
            self.assertEqual(quarantined["name"], "PRIVATE QUARANTINE")
            cur.execute(
                "SELECT purpose FROM public.accountable_payments WHERE id=200"
            )
            self.assertEqual(cur.fetchone()["purpose"], "PRIVATE PAYMENT")

        second_dry_connection = self._new_connection()
        try:
            second_dry = run_accounting_ownership_backfill(second_dry_connection)
        finally:
            second_dry_connection.close()
        self.assertEqual(second_dry["readyCount"], 0)
        self.assertEqual(second_dry["verifiedCount"], 7)
        self.assertEqual(second_dry["quarantinedCount"], 1)

        second_apply_connection = self._new_connection()
        try:
            second_apply = run_accounting_ownership_backfill(
                second_apply_connection,
                apply=True,
                expected_ready_count=0,
                expected_plan_sha256=second_dry["planSha256"],
            )
        finally:
            second_apply_connection.close()
        self.assertEqual(second_apply["updated"], 0)
        self.assertTrue(second_apply["complete"])

    def test_accounting_ownership_backfill_rolls_back_all_rows_on_nonfinite_money(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (19,4,'Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.staff(id,company_id,name,project) "
                "VALUES (100,4,'PRIVATE STAFF','Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,project_name,given_to_id,amount,spent_amount,purpose) "
                "VALUES (200,'Exact accounting',100,'NaN'::numeric,20,'PRIVATE')"
            )

        dry_connection = self._new_connection()
        try:
            dry = run_accounting_ownership_backfill(dry_connection)
        finally:
            dry_connection.close()
        self.assertEqual(dry["readyCount"], 2)

        apply_connection = self._new_connection()
        try:
            with self.assertRaises(psycopg2.errors.CheckViolation):
                run_accounting_ownership_backfill(
                    apply_connection,
                    apply=True,
                    expected_ready_count=dry["readyCount"],
                    expected_plan_sha256=dry["planSha256"],
                )
        finally:
            apply_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT company_scope_verified FROM public.staff WHERE id=100"
            )
            self.assertIs(cur.fetchone()[0], False)
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified "
                "FROM public.accountable_payments WHERE id=200"
            )
            self.assertEqual(cur.fetchone(), (None, None, False))

    def test_accountable_http_routes_enforce_verified_company_ownership(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (31,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active,is_default) "
                "VALUES (32,31,1,4,'директор',TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(19,4,'Exact accounting'),(20,5,'Foreign accounting')"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,project,company_scope_verified) VALUES "
                "(100,4,'Exact staff','Exact accounting',TRUE),"
                "(101,5,'Foreign staff','Foreign accounting',TRUE),"
                "(102,4,'Quarantined staff','Exact accounting',FALSE)"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,company_id,project_id,company_scope_verified,project_name,"
                "given_to,given_to_id,amount,spent_amount,purpose,added_by) VALUES "
                "(200,4,19,TRUE,'Exact accounting','Exact staff',100,100,20,"
                "'VISIBLE','Server actor'),"
                "(201,4,19,FALSE,'Exact accounting','Quarantined staff',102,"
                "100,0,'PRIVATE QUARANTINED','Legacy actor'),"
                "(202,5,20,TRUE,'Foreign accounting','Foreign staff',101,100,"
                "0,'PRIVATE FOREIGN','Foreign actor')"
            )
            cur.execute(
                "INSERT INTO public.accountable_expenses "
                "(id,payment_id,company_id,project_id,company_scope_verified,"
                "project_name,description,amount,added_by) VALUES "
                "(300,200,4,19,TRUE,'Exact accounting','VISIBLE EXPENSE',20,"
                "'Server actor'),"
                "(301,200,4,19,FALSE,'Exact accounting','PRIVATE QUARANTINED',"
                "20,'Legacy actor'),"
                "(302,202,5,20,TRUE,'Foreign accounting','PRIVATE FOREIGN',20,"
                "'Foreign actor')"
            )

        observed_connections = []

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def resolve_context(cur, user, requested_company_id, action_mode, **headers):
            return resolve_request_company_context(
                cur,
                user,
                requested_company_id,
                action_mode,
                **headers,
            )

        app = FastAPI()
        register_accountable_payments_module(app, {
            "get_db": get_db,
            "get_current_user": lambda: {
                "id": 31,
                "name": "Accounting director",
                "role": "директор",
            },
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": effective_company_actors,
            "finance_roles": ("директор", "бухгалтер"),
        })
        client = TestClient(app)
        headers = {"X-Company-Id": "4", "X-Company-Mode": "company"}

        payment_list = client.get("/accountable-payments", headers=headers)
        expense_list = client.get("/accountable-expenses", headers=headers)
        rejected_project = client.post(
            "/accountable-payments",
            headers=headers,
            json={"projectId": 20, "givenToId": 100, "amount": 50},
        )
        created_payment = client.post(
            "/accountable-payments",
            headers=headers,
            json={
                "projectId": 19,
                "givenToId": 100,
                "amount": 50,
                "projectName": "CLIENT FORGED",
                "givenTo": "CLIENT FORGED",
                "addedBy": "CLIENT FORGED",
            },
        )
        created_expense = client.post(
            "/accountable-expenses",
            headers=headers,
            json={
                "paymentId": 200,
                "amount": 30,
                "description": "Real receipt",
                "projectName": "CLIENT FORGED",
                "addedBy": "CLIENT FORGED",
            },
        )

        self.assertEqual(payment_list.status_code, 200)
        self.assertEqual([row["id"] for row in payment_list.json()], [200])
        self.assertEqual(expense_list.status_code, 200)
        self.assertEqual([row["id"] for row in expense_list.json()], [300])
        self.assertEqual(rejected_project.status_code, 404)
        self.assertEqual(created_payment.status_code, 200)
        self.assertEqual(created_expense.status_code, 200)
        self.assertNotIn("PRIVATE", payment_list.text + expense_list.text)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,"
                "project_name,given_to,given_to_id,added_by "
                "FROM public.accountable_payments "
                "WHERE id=%s",
                (created_payment.json()["id"],),
            )
            stored_payment = dict(cur.fetchone())
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,"
                "project_name,added_by FROM public.accountable_expenses "
                "WHERE description='Real receipt'"
            )
            stored_expense = dict(cur.fetchone())
            cur.execute(
                "SELECT spent_amount FROM public.accountable_payments "
                "WHERE id=200"
            )
            spent_amount = cur.fetchone()["spent_amount"]
        self.assertEqual(stored_payment, {
            "company_id": 4,
            "project_id": 19,
            "company_scope_verified": True,
            "project_name": "Exact accounting",
            "given_to": "Exact staff",
            "given_to_id": 100,
            "added_by": "Accounting director",
        })
        self.assertEqual(stored_expense, {
            "company_id": 4,
            "project_id": 19,
            "company_scope_verified": True,
            "project_name": "Exact accounting",
            "added_by": "Accounting director",
        })
        self.assertEqual(float(spent_amount), 50.0)
        self.assertEqual(len(observed_connections), 5)
        self.assertEqual(observed_connections[2].observation["commits"], 0)
        self.assertEqual(observed_connections[2].observation["rollbacks"], 1)
        self.assertEqual(observed_connections[3].observation["commits"], 1)
        self.assertEqual(observed_connections[4].observation["commits"], 1)
        self.assertTrue(all(
            observed.observation["closed"] for observed in observed_connections
        ))

    def test_expense_report_http_routes_enforce_verified_company_ownership(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (31,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active,is_default) "
                "VALUES (32,31,1,4,'директор',TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(19,4,'Одинаковый объект'),(20,5,'Одинаковый объект')"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,project,company_scope_verified) VALUES "
                "(100,4,'Точный сотрудник','Одинаковый объект',TRUE),"
                "(101,5,'Чужой сотрудник','Одинаковый объект',TRUE),"
                "(102,4,'Карантинный сотрудник','Одинаковый объект',FALSE)"
            )
            cur.execute(
                "INSERT INTO public.expense_reports "
                "(id,company_id,project_id,company_scope_verified,employee_id,"
                "employee_name,project_name,purpose,total_amount,issued_amount,"
                "spent_amount,balance,items_json,status) VALUES "
                "(400,4,19,TRUE,100,'Точный сотрудник','Одинаковый объект',"
                "'VISIBLE',1000,1000,300,700,'[]','На утверждении'),"
                "(401,4,19,FALSE,102,'Карантинный сотрудник','Одинаковый объект',"
                "'PRIVATE QUARANTINED',1000,1000,0,1000,'[]','На утверждении'),"
                "(402,5,20,TRUE,101,'Чужой сотрудник','Одинаковый объект',"
                "'PRIVATE FOREIGN',1000,1000,0,1000,'[]','На утверждении')"
            )

        observed_connections = []

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def resolve_context(cur, user, requested_company_id, action_mode, **headers):
            return resolve_request_company_context(
                cur, user, requested_company_id, action_mode, **headers,
            )

        app = FastAPI()
        register_expense_reports_module(app, {
            "get_db": get_db,
            "get_current_user": lambda: {
                "id": 31,
                "name": "Accounting director",
                "role": "директор",
            },
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": effective_company_actors,
            "finance_roles": ("директор", "бухгалтер"),
        })
        client = TestClient(app)
        headers = {"X-Company-Id": "4", "X-Company-Mode": "company"}

        listed = client.get(
            "/expense-reports",
            headers=headers,
            params={"project_name": "Одинаковый объект"},
        )
        rejected_project = client.post(
            "/expense-reports",
            headers=headers,
            json={"projectId": 20, "employeeId": 100, "issuedAmount": 500},
        )
        created = client.post(
            "/expense-reports",
            headers=headers,
            json={
                "projectId": 19,
                "employeeId": 100,
                "employeeName": "CLIENT FORGED",
                "projectName": "CLIENT FORGED",
                "issuedAmount": 500,
                "spentAmount": 125,
                "balance": -999,
                "purpose": "Real report",
            },
        )
        approved = client.put(
            "/expense-reports/400",
            headers=headers,
            json={
                "status": "Утверждён",
                "approvedBy": "CLIENT FORGED",
                "approvedAt": "2000-01-01",
            },
        )
        cancelled = client.delete("/expense-reports/400", headers=headers)
        quarantined = client.put(
            "/expense-reports/401",
            headers=headers,
            json={"status": "Утверждён"},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.json()], [400])
        self.assertNotIn("PRIVATE", listed.text)
        self.assertEqual(rejected_project.status_code, 404)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(quarantined.status_code, 404)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,employee_id,"
                "employee_name,project_name,issued_amount,spent_amount,balance "
                "FROM public.expense_reports WHERE id=%s",
                (created.json()["id"],),
            )
            stored = dict(cur.fetchone())
            cur.execute(
                "SELECT status,approved_by,purpose FROM public.expense_reports "
                "WHERE id=400"
            )
            cancelled_row = dict(cur.fetchone())
        self.assertEqual(stored["company_id"], 4)
        self.assertEqual(stored["project_id"], 19)
        self.assertIs(stored["company_scope_verified"], True)
        self.assertEqual(stored["employee_id"], 100)
        self.assertEqual(stored["employee_name"], "Точный сотрудник")
        self.assertEqual(stored["project_name"], "Одинаковый объект")
        self.assertEqual(float(stored["issued_amount"]), 500.0)
        self.assertEqual(float(stored["spent_amount"]), 125.0)
        self.assertEqual(float(stored["balance"]), 375.0)
        self.assertEqual(cancelled_row["status"], "Аннулирован")
        self.assertEqual(cancelled_row["approved_by"], "Accounting director")
        self.assertNotIn("CLIENT FORGED", repr(stored) + repr(cancelled_row))
        self.assertEqual(len(observed_connections), 6)
        self.assertEqual(observed_connections[1].observation["commits"], 0)
        self.assertEqual(observed_connections[1].observation["rollbacks"], 1)
        self.assertEqual(observed_connections[2].observation["commits"], 1)
        self.assertEqual(observed_connections[3].observation["commits"], 1)
        self.assertEqual(observed_connections[4].observation["commits"], 1)
        self.assertEqual(observed_connections[5].observation["commits"], 0)
        self.assertEqual(observed_connections[5].observation["rollbacks"], 1)
        self.assertTrue(all(
            observed.observation["closed"] for observed in observed_connections
        ))

    def test_salary_payment_http_routes_enforce_verified_company_ownership(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (31,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active,is_default) "
                "VALUES (32,31,1,4,'директор',TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,project,company_scope_verified) VALUES "
                "(100,4,'Точный сотрудник','Private project',TRUE),"
                "(101,5,'Чужой сотрудник','Private project',TRUE),"
                "(102,4,'Карантинный сотрудник','Private project',FALSE)"
            )
            cur.execute(
                "INSERT INTO public.salary_payments "
                "(id,company_id,company_scope_verified,staff_id,staff_name,"
                "month,amount,paid_by,paid_date,note) VALUES "
                "(500,4,TRUE,100,'Точный сотрудник','2026-07',1000,'Сервер',"
                "'2026-08-22','VISIBLE'),"
                "(501,4,FALSE,102,'Карантинный сотрудник','2026-07',1000,"
                "'Legacy','2026-08-22','PRIVATE QUARANTINED'),"
                "(502,5,TRUE,101,'Чужой сотрудник','2026-07',1000,'Foreign',"
                "'2026-08-22','PRIVATE FOREIGN')"
            )

        observed_connections = []

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def resolve_context(cur, user, requested_company_id, action_mode, **headers):
            return resolve_request_company_context(
                cur, user, requested_company_id, action_mode, **headers,
            )

        app = FastAPI()
        register_salary_payments_module(app, {
            "get_db": get_db,
            "get_current_user": lambda: {
                "id": 31,
                "name": "Accounting director",
                "role": "директор",
            },
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": effective_company_actors,
            "finance_roles": ("директор", "бухгалтер"),
        })
        client = TestClient(app)
        headers = {"X-Company-Id": "4", "X-Company-Mode": "company"}

        listed = client.get("/salary-payments", headers=headers)
        rejected_staff = client.post(
            "/salary-payments",
            headers=headers,
            json={"staffId": 101, "month": "2026-07", "amount": 500},
        )
        created = client.post(
            "/salary-payments",
            headers=headers,
            json={
                "staffId": 100,
                "staffName": "CLIENT FORGED",
                "month": "2026-08",
                "amount": 500,
                "paidBy": "CLIENT FORGED",
                "paidDate": "2000-01-01",
            },
        )
        deleted = client.delete("/salary-payments/500", headers=headers)
        quarantined = client.delete("/salary-payments/501", headers=headers)

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.json()], [500])
        self.assertNotIn("PRIVATE", listed.text)
        self.assertEqual(rejected_staff.status_code, 404)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(quarantined.status_code, 404)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,company_scope_verified,staff_id,staff_name,"
                "month,amount,paid_by,paid_date FROM public.salary_payments "
                "WHERE id=%s",
                (created.json()["id"],),
            )
            stored = dict(cur.fetchone())
            cur.execute("SELECT COUNT(*) AS count FROM public.salary_payments WHERE id=500")
            deleted_count = cur.fetchone()["count"]
        self.assertEqual(stored["company_id"], 4)
        self.assertIs(stored["company_scope_verified"], True)
        self.assertEqual(stored["staff_id"], 100)
        self.assertEqual(stored["staff_name"], "Точный сотрудник")
        self.assertEqual(stored["month"], "2026-08")
        self.assertEqual(float(stored["amount"]), 500.0)
        self.assertEqual(stored["paid_by"], "Accounting director")
        self.assertNotEqual(stored["paid_date"], "2000-01-01")
        self.assertEqual(deleted_count, 0)
        self.assertNotIn("CLIENT FORGED", repr(stored))
        self.assertEqual(len(observed_connections), 5)
        self.assertEqual(observed_connections[1].observation["commits"], 0)
        self.assertEqual(observed_connections[1].observation["rollbacks"], 1)
        self.assertEqual(observed_connections[2].observation["commits"], 1)
        self.assertEqual(observed_connections[3].observation["commits"], 1)
        self.assertEqual(observed_connections[4].observation["commits"], 0)
        self.assertEqual(observed_connections[4].observation["rollbacks"], 1)
        self.assertTrue(all(
            observed.observation["closed"] for observed in observed_connections
        ))

    def test_staff_http_routes_enforce_verified_company_ownership(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,name,email,role,company_id,active,"
                "two_factor_enabled) VALUES "
                "(31,'Director','director@example.test','директор',4,TRUE,TRUE),"
                "(41,'Shared','shared@example.test','мастер',4,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active,is_default) "
                "VALUES (32,31,1,4,'директор',TRUE,TRUE),"
                "(42,41,1,4,'мастер',TRUE,TRUE),"
                "(43,41,1,5,'мастер',TRUE,FALSE)"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,role,project,email_work,company_scope_verified) "
                "VALUES (100,4,'Visible','мастер','','',TRUE),"
                "(101,5,'PRIVATE FOREIGN','мастер','','',TRUE),"
                "(102,4,'PRIVATE QUARANTINED','мастер','','',FALSE),"
                "(103,4,'Shared member','мастер','','shared@example.test',TRUE)"
            )
            cur.execute(
                "INSERT INTO public.staff_documents(id,staff_id,doc_type,title) "
                "VALUES (800,100,'другое','VISIBLE DOCUMENT'),"
                "(801,101,'другое','PRIVATE FOREIGN DOCUMENT')"
            )

        observed_connections = []
        current_user = {"id": 31, "name": "Request name", "role": "директор"}

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def resolve_context(cur, user, requested_company_id, action_mode, **headers):
            return resolve_request_company_context(
                cur, user, requested_company_id, action_mode, **headers,
            )

        def require_roles(*_roles):
            return lambda: current_user

        app = FastAPI()
        register_staff_module(app, {
            "get_db": get_db,
            "get_current_user": lambda: current_user,
            "require_roles": require_roles,
            "staff_view_roles": ("директор", "прораб"),
            "staff_manage_roles": ("директор",),
            "staff_full_view_roles": ("директор", "бухгалтер"),
            "user_project_names": lambda actor: actor.get("assignedProjects") or [],
            "safe_project_list": lambda value: value if isinstance(value, list) else [],
            "prepare_user_access_scope": lambda cur, role, project, projects, packages: (
                projects, packages,
            ),
            "date_or_none": lambda value: value or None,
            "log_audit": lambda *_args: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": effective_company_actors,
        })
        client = TestClient(app)
        headers = {"X-Company-Id": "4", "X-Company-Mode": "company"}

        listed = client.get("/staff", headers=headers)
        created = client.post(
            "/staff", headers=headers,
            json={"name": "Created", "role": "мастер"},
        )
        updated = client.put(
            "/staff/100", headers=headers,
            json={"name": "Updated", "role": "мастер"},
        )
        foreign_update = client.put(
            "/staff/101", headers=headers,
            json={"name": "Forged", "role": "мастер"},
        )
        foreign_profile = client.get("/staff/102/profile", headers=headers)
        document_created = client.post(
            "/staff/100/documents", headers=headers,
            json={"title": "Created document", "createdBy": "CLIENT FORGED"},
        )
        foreign_document = client.post(
            "/staff/101/documents", headers=headers,
            json={"title": "Forged"},
        )
        foreign_document_delete = client.delete(
            "/staff-documents/801", headers=headers,
        )
        document_deleted = client.delete("/staff-documents/800", headers=headers)
        fired = client.delete("/staff/103", headers=headers)

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.json()], [100, 103])
        self.assertNotIn("PRIVATE", listed.text)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(foreign_update.status_code, 404)
        self.assertEqual(foreign_profile.status_code, 404)
        self.assertEqual(document_created.status_code, 200)
        self.assertEqual(foreign_document.status_code, 404)
        self.assertEqual(foreign_document_delete.status_code, 404)
        self.assertEqual(document_deleted.status_code, 200)
        self.assertEqual(fired.status_code, 200)
        self.assertEqual(fired.json()["disabledUsers"], 1)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,company_scope_verified,name FROM public.staff "
                "WHERE id=%s",
                (created.json()["id"],),
            )
            stored_staff = dict(cur.fetchone())
            cur.execute(
                "SELECT created_by FROM public.staff_documents WHERE id=%s",
                (document_created.json()["id"],),
            )
            stored_document = dict(cur.fetchone())
            cur.execute(
                "SELECT company_id,active FROM public.user_company_roles "
                "WHERE user_id=41 ORDER BY company_id"
            )
            memberships = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT active FROM public.users WHERE id=41")
            shared_user_active = cur.fetchone()["active"]
            cur.execute(
                "SELECT COUNT(*) AS count FROM public.staff_documents WHERE id=800"
            )
            deleted_document_count = cur.fetchone()["count"]

        self.assertEqual(stored_staff, {
            "company_id": 4,
            "company_scope_verified": True,
            "name": "Created",
        })
        self.assertEqual(stored_document["created_by"], "Request name")
        self.assertNotEqual(stored_document["created_by"], "CLIENT FORGED")
        self.assertEqual(memberships, [
            {"company_id": 4, "active": False},
            {"company_id": 5, "active": True},
        ])
        self.assertIs(shared_user_active, True)
        self.assertEqual(deleted_document_count, 0)
        self.assertTrue(all(
            observed.observation["closed"] for observed in observed_connections
        ))

    def test_manual_and_own_expense_routes_preserve_exact_company_ownership(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE),(5,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,name,email,role,company_id,active,"
                "two_factor_enabled) VALUES "
                "(31,'Director','director@example.test','директор',4,TRUE,TRUE),"
                "(41,'Worker','worker@example.test','мастер',4,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active,is_default) "
                "VALUES (32,31,1,4,'директор',TRUE,TRUE),"
                "(42,41,1,4,'мастер',TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(19,4,'Shared project'),(20,5,'Shared project')"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,role,project,email_work,company_scope_verified) "
                "VALUES (100,4,'Director staff','директор','Shared project',"
                "'director@example.test',TRUE),"
                "(103,4,'Worker staff','мастер','Shared project',"
                "'worker@example.test',TRUE),"
                "(101,5,'PRIVATE FOREIGN','мастер','Shared project',"
                "'foreign@example.test',TRUE)"
            )
            cur.execute(
                "INSERT INTO public.own_expenses "
                "(id,company_id,project_id,company_scope_verified,project_name,"
                "employee_name,employee_id,description,amount,status) VALUES "
                "(600,4,19,TRUE,'Shared project','Worker staff',103,'VISIBLE',10,'Ожидает'),"
                "(601,4,19,TRUE,'Shared project','Director staff',100,'OTHER',20,'Ожидает'),"
                "(602,5,20,TRUE,'Shared project','PRIVATE FOREIGN',101,'PRIVATE FOREIGN',30,'Ожидает'),"
                "(603,4,19,FALSE,'Shared project','Worker staff',103,'PRIVATE QUARANTINED',40,'Ожидает')"
            )
            cur.execute(
                "INSERT INTO public.expenses "
                "(id,company_id,project_id,company_scope_verified,project,category,amount,note,source) VALUES "
                "(700,4,19,TRUE,'Shared project','other',10,'VISIBLE','manual'),"
                "(701,5,20,TRUE,'Shared project','other',20,'PRIVATE FOREIGN','manual'),"
                "(702,4,19,FALSE,'Shared project','other',30,'PRIVATE QUARANTINED','manual')"
            )

        observed_connections = []
        current_user = {
            "id": 31,
            "name": "Accounting director",
            "email": "director@example.test",
            "role": "директор",
        }

        def get_db():
            observed = _ObservedConnection(self._new_connection())
            observed_connections.append(observed)
            return observed

        def resolve_context(cur, user, requested_company_id, action_mode, **headers):
            return resolve_request_company_context(
                cur, user, requested_company_id, action_mode, **headers,
            )

        def require_roles(*_roles):
            return lambda: current_user

        shared_deps = {
            "get_db": get_db,
            "get_current_user": lambda: current_user,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": effective_company_actors,
        }
        app = FastAPI()
        register_expenses_module(app, {
            **shared_deps,
            "finance_roles": ("директор", "бухгалтер"),
        })
        register_own_expenses_module(app, {
            **shared_deps,
            "require_roles": require_roles,
            "own_expense_roles": ("директор", "бухгалтер", "мастер"),
            "own_expense_review_roles": ("директор", "бухгалтер"),
            "finance_roles": ("директор", "бухгалтер"),
            "leadership_roles": ("директор",),
            "worker_execution_roles": ("мастер",),
            "warehouse_roles": ("кладовщик",),
            "own_expense_no_project_category": "personal_no_project",
            "require_project_access": lambda *_args: None,
            "user_project_names": lambda actor: actor.get("assignedProjects") or [actor.get("projectName")],
            "safe_project_list": lambda value: value if isinstance(value, list) else [],
            "safe_float": lambda value, default=None: float(value) if value not in (None, "") else default,
            "supply_work_package": lambda value=None: value or "Основная",
            "create_warehouse_invoice_record": lambda *_args: {"ok": True},
        })
        client = TestClient(app)
        headers = {"X-Company-Id": "4", "X-Company-Mode": "company"}

        manual_list = client.get("/expenses", headers=headers)
        foreign_manual = client.post(
            "/expenses", headers=headers,
            json={"projectId": 20, "amount": 50},
        )
        created_manual = client.post(
            "/expenses", headers=headers,
            json={
                "projectId": 19,
                "project": "CLIENT FORGED",
                "amount": 50,
                "addedBy": "CLIENT FORGED",
            },
        )

        current_user.update({
            "id": 41,
            "name": "Worker account",
            "email": "worker@example.test",
            "role": "мастер",
        })
        own_list = client.get("/own-expenses", headers=headers)
        created_own = client.post(
            "/own-expenses", headers=headers,
            json={
                "projectId": 19,
                "projectName": "CLIENT FORGED",
                "employeeId": 100,
                "employeeName": "CLIENT FORGED",
                "description": "Worker receipt",
                "amount": 75,
            },
        )

        current_user.update({
            "id": 31,
            "name": "Accounting director",
            "email": "director@example.test",
            "role": "директор",
        })
        approved = client.put(
            f"/own-expenses/{created_own.json()['id']}",
            headers=headers,
            json={"status": "Возмещено", "approvedBy": "CLIENT FORGED"},
        )
        quarantined = client.put(
            "/own-expenses/603", headers=headers, json={"status": "Возмещено"},
        )
        deleted = client.delete("/own-expenses/600", headers=headers)

        self.assertEqual([row["id"] for row in manual_list.json()], [700])
        self.assertNotIn("PRIVATE", manual_list.text)
        self.assertEqual(foreign_manual.status_code, 404)
        self.assertEqual(created_manual.status_code, 200)
        self.assertEqual([row["id"] for row in own_list.json()], [600])
        self.assertNotIn("PRIVATE", own_list.text)
        self.assertEqual(created_own.status_code, 200)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(quarantined.status_code, 404)
        self.assertEqual(deleted.status_code, 200)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,project,added_by "
                "FROM public.expenses WHERE id=%s",
                (created_manual.json()["id"],),
            )
            stored_manual = dict(cur.fetchone())
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,project_name,"
                "employee_id,employee_name,status,approved_by,expense_id "
                "FROM public.own_expenses WHERE id=%s",
                (created_own.json()["id"],),
            )
            stored_own = dict(cur.fetchone())
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,project,"
                "own_expense_id,source FROM public.expenses WHERE id=%s",
                (created_own.json()["expenseId"],),
            )
            stored_mirror = dict(cur.fetchone())
            cur.execute("SELECT COUNT(*) AS count FROM public.own_expenses WHERE id=600")
            deleted_count = cur.fetchone()["count"]

        self.assertEqual(stored_manual, {
            "company_id": 4,
            "project_id": 19,
            "company_scope_verified": True,
            "project": "Shared project",
            "added_by": "Accounting director",
        })
        self.assertEqual(stored_own["company_id"], 4)
        self.assertEqual(stored_own["project_id"], 19)
        self.assertIs(stored_own["company_scope_verified"], True)
        self.assertEqual(stored_own["project_name"], "Shared project")
        self.assertEqual(stored_own["employee_id"], 103)
        self.assertEqual(stored_own["employee_name"], "Worker staff")
        self.assertEqual(stored_own["status"], "Возмещено")
        self.assertEqual(stored_own["approved_by"], "Accounting director")
        self.assertEqual(stored_mirror, {
            "company_id": 4,
            "project_id": 19,
            "company_scope_verified": True,
            "project": "Shared project",
            "own_expense_id": created_own.json()["id"],
            "source": "own_expense",
        })
        self.assertEqual(stored_own["expense_id"], created_own.json()["expenseId"])
        self.assertEqual(deleted_count, 0)
        self.assertNotIn("CLIENT FORGED", repr(stored_manual) + repr(stored_own))
        self.assertTrue(all(
            observed.observation["closed"] for observed in observed_connections
        ))

    def test_accounting_ownership_remediation_is_exact_audited_and_atomic(self):
        schema_plan = build_accounting_ownership_schema_plan()
        schema_connection = self._new_connection()
        try:
            run_accounting_ownership_schema(
                schema_connection,
                apply=True,
                expected_change_count=schema_plan["changeCount"],
                expected_plan_sha256=schema_plan["planSha256"],
            )
        finally:
            schema_connection.close()

        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.companies(id,platform_account_id,active) "
                "VALUES (4,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (31,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active) "
                "VALUES (32,31,1,4,'бухгалтер',TRUE)"
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (19,4,'Exact accounting')"
            )
            cur.execute(
                "INSERT INTO public.staff "
                "(id,company_id,name,project,company_scope_verified) "
                "VALUES (100,4,'PRIVATE STAFF','Exact accounting',TRUE)"
            )
            cur.execute(
                "INSERT INTO public.accountable_payments "
                "(id,project_name,given_to_id,amount,spent_amount,purpose) "
                "VALUES "
                "(200,'Exact accounting',100,100,20,'PRIVATE PAYMENT'),"
                "(201,'Exact accounting',100,200,30,'PRIVATE ROLLBACK')"
            )

        request = build_accounting_ownership_remediation_request(
            source="accountable_payments",
            record_id=200,
            company_id=4,
            project_id=19,
            operator_user_id=31,
        )
        dry_connection = self._new_connection()
        try:
            dry = run_accounting_ownership_remediation(
                dry_connection, request
            )
        finally:
            dry_connection.close()
        self.assertEqual(dry["state"], "ready")
        self.assertTrue(dry["rolledBack"])

        apply_connection = self._new_connection()
        try:
            applied = run_accounting_ownership_remediation(
                apply_connection,
                request,
                apply=True,
                expected_evidence_sha256=dry["evidenceSha256"],
            )
        finally:
            apply_connection.close()
        self.assertEqual(applied["state"], "already_verified")
        self.assertEqual(applied["writesAttempted"], 1)
        self.assertEqual(applied["auditWritesAttempted"], 1)
        self.assertIs(type(applied["auditEventId"]), int)

        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified,purpose "
                "FROM public.accountable_payments WHERE id=200"
            )
            stored = cur.fetchone()
            self.assertEqual(stored["company_id"], 4)
            self.assertEqual(stored["project_id"], 19)
            self.assertIs(stored["company_scope_verified"], True)
            self.assertEqual(stored["purpose"], "PRIVATE PAYMENT")
            cur.execute(
                "SELECT user_id,user_name,user_role,action,entity_type,"
                "entity_id,owner_scope,company_id,project_id,description "
                "FROM public.audit_log ORDER BY id"
            )
            audit_rows = cur.fetchall()
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(dict(audit_rows[0]), {
            "user_id": 31,
            "user_name": "system",
            "user_role": "migration",
            "action": "accounting_ownership_remediated",
            "entity_type": "accountable_payments",
            "entity_id": 200,
            "owner_scope": "company",
            "company_id": 4,
            "project_id": 19,
            "description": "exact-id ownership remediation",
        })
        self.assertNotIn("PRIVATE", repr(audit_rows))

        second_dry_connection = self._new_connection()
        try:
            second_dry = run_accounting_ownership_remediation(
                second_dry_connection, request
            )
        finally:
            second_dry_connection.close()
        self.assertEqual(second_dry["state"], "already_verified")

        second_apply_connection = self._new_connection()
        try:
            second_apply = run_accounting_ownership_remediation(
                second_apply_connection,
                request,
                apply=True,
                expected_evidence_sha256=second_dry["evidenceSha256"],
            )
        finally:
            second_apply_connection.close()
        self.assertEqual(second_apply["writesAttempted"], 0)
        self.assertEqual(second_apply["auditWritesAttempted"], 0)
        with self.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.audit_log")
            self.assertEqual(cur.fetchone()[0], 1)

        rollback_request = build_accounting_ownership_remediation_request(
            source="accountable_payments",
            record_id=201,
            company_id=4,
            project_id=19,
            operator_user_id=31,
        )
        rollback_dry_connection = self._new_connection()
        try:
            rollback_dry = run_accounting_ownership_remediation(
                rollback_dry_connection, rollback_request
            )
        finally:
            rollback_dry_connection.close()
        with self.connection.cursor() as cur:
            cur.execute(
                "ALTER TABLE public.audit_log ADD CONSTRAINT "
                "ck_test_reject_accounting_201 CHECK "
                "(entity_id <> 201 OR action <> "
                "'accounting_ownership_remediated')"
            )
        try:
            rollback_connection = self._new_connection()
            try:
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    run_accounting_ownership_remediation(
                        rollback_connection,
                        rollback_request,
                        apply=True,
                        expected_evidence_sha256=(
                            rollback_dry["evidenceSha256"]
                        ),
                    )
            finally:
                rollback_connection.close()
        finally:
            with self.connection.cursor() as cur:
                cur.execute(
                    "ALTER TABLE public.audit_log DROP CONSTRAINT "
                    "ck_test_reject_accounting_201"
                )
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT company_id,project_id,company_scope_verified "
                "FROM public.accountable_payments WHERE id=201"
            )
            self.assertEqual(cur.fetchone(), (None, None, False))
            cur.execute("SELECT COUNT(*) FROM public.audit_log")
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute(
                "UPDATE public.user_company_roles SET active=FALSE "
                "WHERE id=32"
            )
        inactive_operator_connection = self._new_connection()
        try:
            with self.assertRaisesRegex(
                RuntimeError, "accounting_remediation_owner_invalid"
            ):
                run_accounting_ownership_remediation(
                    inactive_operator_connection, rollback_request
                )
        finally:
            inactive_operator_connection.close()

    def _human_action_ledger_counts(self):
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.human_action_proposals "
                "WHERE company_id=4 AND project_id=17"
            )
            proposals = cur.fetchone()[0]
            cur.execute(
                "SELECT event_kind,COUNT(*) "
                "FROM public.human_action_events "
                "WHERE company_id=4 AND project_id=17 "
                "GROUP BY event_kind ORDER BY event_kind"
            )
            events = dict(cur.fetchall())
            cur.execute(
                "SELECT COUNT(*) FROM public.audit_log "
                "WHERE company_id=4 AND project_id=17 "
                "AND action='warehouse_anomaly_review_acknowledged' "
                "AND entity_type='human_action_proposal'"
            )
            audit = cur.fetchone()[0]
        return {"proposals": proposals, "events": events, "audit": audit}

    def _prove_human_action_kernel_lifecycle(self):
        stored, selection, _result_sets = _real_a7_case()
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO public.platform_accounts(id,active,status) "
                "VALUES (1,TRUE,'active')"
            )
            cur.execute(
                "INSERT INTO public.companies"
                "(id,platform_account_id,active) VALUES (4,1,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.users(id,active,two_factor_enabled) "
                "VALUES (7,TRUE,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.user_sessions "
                "(id,user_id,session_hash,revoked_at,expires_at,"
                "two_factor_passed) VALUES "
                "(8,7,%s,NULL,clock_timestamp()+interval '1 hour',TRUE)",
                ("a" * 64,),
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,platform_account_id,company_id,role,active) "
                "VALUES (9,7,1,4,'директор',TRUE)"
            )
            cur.execute(
                "UPDATE public.warehouse_invoices "
                "SET project='Other project' WHERE id=101"
            )
        self._insert_runtime_job(result_json=stored)

        authentication = {
            "authenticationKind": "cookie_session",
            "sessionHash": "a" * 64,
        }
        body = {
            "projectId": 17,
            "jobId": 123,
            "selected": selection,
        }
        preview_claims = runtime_contract._parse_warehouse_anomaly_runtime_claims(
            authentication,
            company_mode="company",
            company_id="4",
            body=body,
        )
        preview_connection = self._new_connection()
        preview_cur = None
        try:
            preview_connection.set_session(
                readonly=True,
                autocommit=False,
                isolation_level="REPEATABLE READ",
            )
            preview_cur = preview_connection.cursor(
                cursor_factory=RealDictCursor,
            )
            human_action_kernel._configure_transaction(preview_cur)
            preview = human_action_kernel._rebuild_current_preview(
                preview_cur, preview_claims,
            )
        finally:
            preview_connection.rollback()
            if preview_cur is not None:
                preview_cur.close()
            preview_connection.close()
        self.assertEqual(preview["state"], "preview_ready")
        self.assertEqual(
            {
                key: preview["candidate"][key]
                for key in ("subjectKind", "subjectId", "anomalyCode")
            },
            selection,
        )
        protected_before = {
            table: rows
            for table, rows in self._snapshot().items()
            if table != "audit_log"
        }

        proposal = human_action_kernel.create_review_acknowledgement_proposal(
            self._new_connection,
            authentication,
            company_mode="company",
            company_id="4",
            body=body,
        )
        self.assertEqual(proposal["state"], "proposed")
        self.assertEqual(proposal["sourceJobId"], 123)
        self.assertFalse(proposal["idempotent"])
        repeated_proposal = (
            human_action_kernel.create_review_acknowledgement_proposal(
                self._new_connection,
                authentication,
                company_mode="company",
                company_id="4",
                body=body,
            )
        )
        self.assertEqual(repeated_proposal["proposalId"], proposal["proposalId"])
        self.assertTrue(repeated_proposal["idempotent"])
        self.assertEqual(self._human_action_ledger_counts(), {
            "proposals": 1,
            "events": {"proposed": 1},
            "audit": 0,
        })

        decision = {
            "proposalId": proposal["proposalId"],
            "proposalSha256": proposal["proposalSha256"],
            "decision": "approve",
        }
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.warehouse_invoices "
                "SET project='Private project' WHERE id=101"
            )
        stale_counts = self._human_action_ledger_counts()
        with self.assertRaises(human_action_kernel.HumanActionKernelError) as raised:
            human_action_kernel.decide_review_acknowledgement(
                self._new_connection,
                authentication,
                decision,
                company_mode="company",
                company_id="4",
            )
        self.assertEqual(
            raised.exception.args,
            ("human_action_kernel_source_stale",),
        )
        self.assertEqual(self._human_action_ledger_counts(), stale_counts)
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE public.warehouse_invoices "
                "SET project='Other project' WHERE id=101"
            )

        applied = human_action_kernel.decide_review_acknowledgement(
            self._new_connection,
            authentication,
            decision,
            company_mode="company",
            company_id="4",
        )
        self.assertEqual(applied["state"], "applied")
        self.assertEqual(applied["writesAttempted"], 3)
        self.assertFalse(applied["idempotent"])
        applied_replay = human_action_kernel.decide_review_acknowledgement(
            self._new_connection,
            authentication,
            decision,
            company_mode="company",
            company_id="4",
        )
        self.assertEqual(applied_replay["eventId"], applied["eventId"])
        self.assertEqual(applied_replay["auditEventId"], applied["auditEventId"])
        self.assertTrue(applied_replay["idempotent"])
        self.assertEqual(applied_replay["writesAttempted"], 0)

        rejected_proposal = (
            human_action_kernel.create_review_acknowledgement_proposal(
                self._new_connection,
                authentication,
                company_mode="company",
                company_id="4",
                body=body,
            )
        )
        rejected_decision = {
            "proposalId": rejected_proposal["proposalId"],
            "proposalSha256": rejected_proposal["proposalSha256"],
            "decision": "reject",
        }
        rejected = human_action_kernel.decide_review_acknowledgement(
            self._new_connection,
            authentication,
            rejected_decision,
            company_mode="company",
            company_id="4",
        )
        self.assertEqual(rejected["state"], "rejected")
        self.assertIsNone(rejected["auditEventId"])
        rejected_replay = human_action_kernel.decide_review_acknowledgement(
            self._new_connection,
            authentication,
            rejected_decision,
            company_mode="company",
            company_id="4",
        )
        self.assertEqual(rejected_replay["eventId"], rejected["eventId"])
        self.assertTrue(rejected_replay["idempotent"])

        concurrent_proposal = (
            human_action_kernel.create_review_acknowledgement_proposal(
                self._new_connection,
                authentication,
                company_mode="company",
                company_id="4",
                body=body,
            )
        )
        concurrent_payload = {
            "proposalId": concurrent_proposal["proposalId"],
            "proposalSha256": concurrent_proposal["proposalSha256"],
            "decision": "approve",
        }
        original_read_proposal = human_action_kernel._read_proposal
        decision_barrier = threading.Barrier(2)

        def coordinated_read(cur, payload, company_id):
            decision_barrier.wait(timeout=10)
            return original_read_proposal(cur, payload, company_id)

        def concurrent_decisions():
            try:
                return (
                    "receipt",
                    human_action_kernel.decide_review_acknowledgement(
                        self._new_connection,
                        authentication,
                        concurrent_payload,
                        company_mode="company",
                        company_id="4",
                    ),
                )
            except human_action_kernel.HumanActionKernelError as error:
                return ("error", error.code)

        with mock.patch.object(
            human_action_kernel,
            "_read_proposal",
            side_effect=coordinated_read,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                race_results = list(executor.map(
                    lambda _index: concurrent_decisions(), range(2),
                ))

        race_receipts = [
            result[1] for result in race_results if result[0] == "receipt"
        ]
        race_errors = [
            result[1] for result in race_results if result[0] == "error"
        ]
        self.assertEqual(sum(
            receipt["state"] == "applied" and not receipt["idempotent"]
            for receipt in race_receipts
        ), 1)
        self.assertTrue(all(
            receipt["state"] == "applied" for receipt in race_receipts
        ))
        self.assertTrue(all(
            code == "human_action_kernel_write_conflict"
            for code in race_errors
        ))
        self.assertEqual(len(race_receipts) + len(race_errors), 2)

        race_replay = human_action_kernel.decide_review_acknowledgement(
            self._new_connection,
            authentication,
            concurrent_payload,
            company_mode="company",
            company_id="4",
        )
        self.assertTrue(race_replay["idempotent"])
        self.assertEqual(race_replay["writesAttempted"], 0)
        self.assertEqual(self._human_action_ledger_counts(), {
            "proposals": 3,
            "events": {
                "applied": 2,
                "approved": 2,
                "proposed": 3,
                "rejected": 1,
            },
            "audit": 2,
        })
        history = human_action_kernel.list_review_acknowledgement_history(
            self._new_connection,
            authentication,
            company_mode="company",
            company_id="4",
            project_id=17,
            before_event_id=None,
            limit=100,
        )
        self.assertEqual(history["humanActionHistoryVersion"], 1)
        self.assertEqual(history["companyId"], 4)
        self.assertEqual(history["projectId"], 17)
        self.assertIsNone(history["nextBeforeId"])
        self.assertEqual(len(history["items"]), 8)
        history_ids = [item["eventId"] for item in history["items"]]
        self.assertEqual(history_ids, sorted(history_ids, reverse=True))
        history_kinds = [item["eventKind"] for item in history["items"]]
        self.assertEqual(history_kinds.count("proposed"), 3)
        self.assertEqual(history_kinds.count("approved"), 2)
        self.assertEqual(history_kinds.count("applied"), 2)
        self.assertEqual(history_kinds.count("rejected"), 1)
        self.assertEqual(
            {item["proposalId"] for item in history["items"]},
            {
                proposal["proposalId"],
                rejected_proposal["proposalId"],
                concurrent_proposal["proposalId"],
            },
        )
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT entity_id,COUNT(*) FROM public.audit_log "
                "WHERE company_id=4 AND project_id=17 "
                "AND action='warehouse_anomaly_review_acknowledged' "
                "AND entity_type='human_action_proposal' "
                "GROUP BY entity_id ORDER BY entity_id"
            )
            self.assertEqual(cur.fetchall(), [
                (proposal["proposalId"], 1),
                (concurrent_proposal["proposalId"], 1),
            ])

        protected_after = {
            table: rows
            for table, rows in self._snapshot().items()
            if table != "audit_log"
        }
        self.assertEqual(protected_after, protected_before)

    def test_zz_human_action_schema_is_guarded_append_only_and_idempotent(self):
        before = self._snapshot()
        probe_connection = self._new_connection()
        try:
            with probe_connection.cursor(cursor_factory=RealDictCursor) as cur:
                initial_catalog = collect_human_action_schema_catalog(cur)
            probe_connection.rollback()
        finally:
            probe_connection.close()
        initial_plan = build_human_action_schema_plan(initial_catalog)
        self.assertTrue(initial_plan["readyForApply"], initial_plan)
        dry_connection = self._new_connection()
        try:
            dry = run_human_action_schema_migration(dry_connection)
        finally:
            dry_connection.close()
        self.assertTrue(dry["dryRun"])
        self.assertTrue(dry["readyForApply"])
        self.assertEqual(dry["changeCount"], 12)
        self.assertEqual(dry["writesAttempted"], 0)
        self.assertEqual(self._snapshot(), before)

        invalid_connection = self._new_connection()
        try:
            with self.assertRaisesRegex(
                HumanActionSchemaMigrationError,
                "human_action_schema_apply_guard_mismatch",
            ):
                run_human_action_schema_migration(
                    invalid_connection,
                    apply=True,
                    confirm=HUMAN_ACTION_SCHEMA_CONFIRMATION,
                    expected_change_count=dry["changeCount"],
                    expected_plan_sha256="0" * 64,
                )
        finally:
            invalid_connection.close()
        self.assertEqual(self._snapshot(), before)

        apply_connection = self._new_connection()
        try:
            applied = run_human_action_schema_migration(
                apply_connection,
                apply=True,
                confirm=HUMAN_ACTION_SCHEMA_CONFIRMATION,
                expected_change_count=dry["changeCount"],
                expected_plan_sha256=dry["planSha256"],
            )
        finally:
            apply_connection.close()
        self.assertTrue(applied["committed"])
        self.assertEqual(applied["writesAttempted"], 12)
        self.assertEqual(self._snapshot(), before)

        repeat_connection = self._new_connection()
        try:
            repeat = run_human_action_schema_migration(repeat_connection)
        finally:
            repeat_connection.close()
        self.assertTrue(repeat["complete"])
        self.assertEqual(repeat["changeCount"], 0)
        self.assertEqual(repeat["writesAttempted"], 0)

        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.uq_hae_decision")
            cur.execute(
                "CREATE UNIQUE INDEX uq_hae_decision "
                "ON public.human_action_events (proposal_id) "
                "WHERE event_kind='approved'"
            )
        drift_connection = self._new_connection()
        try:
            drift = run_human_action_schema_migration(drift_connection)
        finally:
            drift_connection.close()
        self.assertFalse(drift["ok"])
        self.assertEqual(drift["blockers"], ["human_action_schema_drift"])
        self.assertEqual(drift["changes"], [])
        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.uq_hae_decision")
            cur.execute(
                "CREATE UNIQUE INDEX uq_hae_decision "
                "ON public.human_action_events (proposal_id) "
                "WHERE event_kind IN ('approved','rejected')"
            )
            cur.execute(
                "ALTER TABLE public.human_action_proposals "
                "ENABLE ROW LEVEL SECURITY"
            )
        rls_connection = self._new_connection()
        try:
            rls_drift = run_human_action_schema_migration(rls_connection)
        finally:
            rls_connection.close()
        self.assertFalse(rls_drift["ok"])
        self.assertEqual(
            rls_drift["blockers"], ["human_action_schema_drift"]
        )
        with self.connection.cursor() as cur:
            cur.execute(
                "ALTER TABLE public.human_action_proposals "
                "DISABLE ROW LEVEL SECURITY"
            )

        self._prove_human_action_kernel_lifecycle()

        with self.connection.cursor() as cur:
            company_id = 9900
            project_id = 9903
            user_id = 9901
            membership_id = 9902
            source_job_id = 9904
            cur.execute(
                "INSERT INTO public.companies(id,name,active) "
                "VALUES (%s,'A12 fixture',TRUE)",
                (company_id,),
            )
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) "
                "VALUES (%s,%s,'A12 fixture')",
                (project_id, company_id),
            )
            cur.execute(
                "INSERT INTO public.users(id,company_id,role,active) "
                "VALUES (%s,%s,'директор',TRUE)",
                (user_id, company_id),
            )
            cur.execute(
                "INSERT INTO public.user_company_roles "
                "(id,user_id,company_id,role,active) "
                "VALUES (%s,%s,%s,'директор',TRUE)",
                (membership_id, user_id, company_id),
            )
            cur.execute(
                "INSERT INTO public.agent_jobs "
                "(id,company_id,project_id) VALUES (%s,%s,%s)",
                (source_job_id, company_id, project_id),
            )
            cur.execute(
                "INSERT INTO public.human_action_proposals ("
                "contract_version,action_kind,effect_kind,company_id,project_id,"
                "source_job_id,subject_kind,subject_id,anomaly_code,source_content_version,"
                "source_content_sha256,proposer_user_id,proposer_membership_id,"
                "created_at,expires_at,idempotency_key,proposal_sha256) VALUES ("
                "1,'warehouse_anomaly_review_acknowledged','audit_only',%s,%s,%s,"
                "'warehouseInvoice',61,'warehouse_invoice_project_mismatch',1,"
                "%s,%s,%s,statement_timestamp(),statement_timestamp()+INTERVAL '15 minutes',"
                "%s,%s) RETURNING id,created_at,expires_at",
                (
                    company_id, project_id, source_job_id, "1" * 64,
                    user_id, membership_id,
                    "human-action:v1:" + "2" * 64, "3" * 64,
                ),
            )
            proposal_id, created_at, expires_at = cur.fetchone()
            event_values = (
                proposal_id, "3" * 64, company_id, project_id, user_id,
                membership_id, user_id, membership_id, created_at, expires_at,
            )
            cur.execute(
                "INSERT INTO public.human_action_events ("
                "contract_version,event_kind,proposal_id,proposal_sha256,"
                "action_kind,company_id,project_id,subject_kind,subject_id,"
                "proposer_user_id,proposer_membership_id,actor_user_id,"
                "actor_membership_id,proposal_created_at,proposal_expires_at,"
                "occurred_at,event_sha256) VALUES ("
                "1,'proposed',%s,%s,'warehouse_anomaly_review_acknowledged',"
                "%s,%s,'warehouseInvoice',61,%s,%s,%s,%s,%s,%s,"
                "clock_timestamp(),%s)",
                (*event_values, "4" * 64),
            )

        with self.assertRaises(psycopg2.Error):
            with self.connection.cursor() as cur:
                cur.execute(
                    "UPDATE public.human_action_proposals "
                    "SET subject_id=62 WHERE id=%s",
                    (proposal_id,),
                )
        with self.assertRaises(psycopg2.Error):
            with self.connection.cursor() as cur:
                cur.execute("TRUNCATE public.human_action_events")

        with self.connection.cursor() as cur:
            decision_sql = (
                "INSERT INTO public.human_action_events ("
                "contract_version,event_kind,proposal_id,proposal_sha256,"
                "action_kind,company_id,project_id,subject_kind,subject_id,"
                "proposer_user_id,proposer_membership_id,actor_user_id,"
                "actor_membership_id,proposal_created_at,proposal_expires_at,"
                "occurred_at,event_sha256) VALUES ("
                "1,%s,%s,%s,'warehouse_anomaly_review_acknowledged',%s,%s,"
                "'warehouseInvoice',61,%s,%s,%s,%s,%s,%s,clock_timestamp(),%s)"
            )
            cur.execute(
                decision_sql,
                ("approved", *event_values, "5" * 64),
            )
            with self.assertRaises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    decision_sql,
                    ("rejected", *event_values, "6" * 64),
                )
            cur.execute(
                decision_sql,
                ("applied", *event_values, "7" * 64),
            )
            with self.assertRaises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    decision_sql,
                    ("applied", *event_values, "8" * 64),
                )


def load_tests(loader, _tests, _pattern):
    suite = loader.suiteClass()
    suite.addTests(loader.loadTestsFromTestCase(
        A93PostgresLauncherContractTests
    ))
    if RUN_POSTGRES:
        suite.addTests(loader.loadTestsFromTestCase(
            A93ResourceLimitsPostgresTests
        ))
    return suite


if __name__ == "__main__":
    unittest.main()
