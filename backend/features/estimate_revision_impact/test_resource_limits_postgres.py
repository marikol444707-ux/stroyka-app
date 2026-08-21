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
import unittest
from pathlib import Path
from unittest import mock

import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_IDLE, parse_dsn
from psycopg2.extras import RealDictCursor

import backend.features.estimate_revision_impact.supply_warehouse_audit as supply_audit
import backend.features.estimate_revision_impact.baseline as baseline_audit
import backend.features.warehouse_recommendation_preview.runtime_access as runtime_access
import backend.features.warehouse_recommendation_preview.runtime_budget as runtime_budget
import backend.features.warehouse_recommendation_preview.runtime_contract as runtime_contract
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
        self.assertTrue(LAUNCHER_PATH.is_file())
        source = LAUNCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.assertIn('mkdtemp(', source)
        self.assertIn('dir="/private/tmp"', source)
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
            dir="/private/tmp",
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
            or raw_root.parent != Path("/private/tmp")
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
                   active BOOLEAN
               )""",
            """CREATE TABLE public.users (
                   id INTEGER PRIMARY KEY,
                   active BOOLEAN,
                   two_factor_enabled BOOLEAN
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
                   active BOOLEAN
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
                   company_id INTEGER
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
                   id BIGINT,
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
        )
        with cls.connection.cursor() as cur:
            for statement in statements:
                cur.execute(statement)

    @classmethod
    def tearDownClass(cls):
        connection = getattr(cls, "connection", None)
        if connection is not None:
            with connection.cursor() as cur:
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
