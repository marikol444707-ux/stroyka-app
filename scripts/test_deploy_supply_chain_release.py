#!/usr/bin/env python3
"""Offline safety contracts; never execute deploy, migration, or database tools."""

import builtins
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock


RUNNER = Path(__file__).with_name("deploy-supply-chain-release.sh")
BEFORE = "20cf455afd2690d99b560cf02257faf0a82744fc"
TARGET = "65ce327917253d3c565d729dc288a0937f16ec29"
CI_RUN = "34064031567"
MIGRATION = "0007_warehouse_invoice_vat_labels.py"
REVISION = "0007_warehouse_vat_labels"


class SupplyChainDeploymentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RUNNER.is_file(), "deployment runner must exist")
        self.source = RUNNER.read_text(encoding="utf-8")
        self.code = "\n".join(line for line in self.source.splitlines()
                              if not line.lstrip().startswith("#")).replace("\\\n", " ")

    def position(self, expression):
        found = re.search(expression, self.code, re.M)
        self.assertIsNotNone(found, "missing safety operation: " + expression)
        return found.start()

    def execute_embedded(self, tag, modules):
        block = re.search(r"<<'" + tag + r"'[^\n]*\n(.*?)\n" + tag, self.source, re.S)
        self.assertIsNotNone(block, tag)
        def isolated_import(name, *_args, **_kwargs):
            self.assertIn(name, modules, "unapproved embedded import")
            return modules[name]
        exec(block.group(1), {"__builtins__": dict(vars(builtins), __import__=isolated_import)})

    def render(self, source):
        with tempfile.TemporaryDirectory(prefix="supply-render-test-") as directory:
            original, output = Path(directory) / "deploy.sh", Path(directory) / "reviewed.sh"
            original.write_text(source, encoding="utf-8")
            self.execute_embedded("RENDER_PY", {
                "pathlib": SimpleNamespace(Path={"deploy.sh": original, str(output): output}.__getitem__),
                "sys": SimpleNamespace(argv=["render", str(output)]),
            })
            return output.read_text(encoding="utf-8")

    def preflight(self, ci_updates=None, proof_updates=None, count=1):
        ci = dict(id=int(CI_RUN), head_sha=TARGET, head_branch="main", event="push",
                  path=".github/workflows/ci.yml", status="completed", conclusion="success",
                  repository={"full_name": "marikol444707-ux/stroyka-app"})
        proof = dict(migration=REVISION, warehouseRows=53, warehouseDataUnchanged=True,
                     vatSchemaUnchanged=True,
                     rowsSha256="5a1478de6c19603b3611153e86bc9607e6a9a7e084d2b37ddb130f60f58802c6")
        ci.update(ci_updates or {})
        proof.update(proof_updates or {})
        with tempfile.TemporaryDirectory(prefix="supply-preflight-test-") as directory:
            evidence = Path(directory)
            (evidence / "rehearsal.log").write_text("migration output\n" + (json.dumps(proof) + "\n") * count)
            http = SimpleNamespace(Request=Mock(return_value="pinned-request"),
                                   urlopen=Mock(return_value=io.StringIO(json.dumps(ci))))
            with redirect_stdout(io.StringIO()) as output:
                self.execute_embedded("PREFLIGHT_PY", {
                    "json": json, "urllib.request": SimpleNamespace(request=http),
                    "pathlib": SimpleNamespace(Path={"evidence": evidence}.__getitem__),
                    "sys": SimpleNamespace(argv=["preflight", CI_RUN, TARGET, "evidence"]),
                })
            http.Request.assert_called_once_with(
                "https://api.github.com/repos/marikol444707-ux/stroyka-app/actions/runs/" + CI_RUN,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "stroyka-release-check"})
            http.urlopen.assert_called_once_with("pinned-request", timeout=20)
            return output.getvalue()

    def test_preflight_accepts_exact_successful_ci_and_reviewed_evidence(self):
        self.assertEqual(self.preflight(), "PINNED_CI_AND_REHEARSAL_OK\n")

    def test_preflight_rejects_each_mismatched_ci_identity_or_result(self):
        for key, value in (("id", 1), ("head_sha", BEFORE), ("head_branch", "other"),
                           ("event", "pull_request"), ("path", ".github/workflows/other.yml"),
                           ("repository", {"full_name": "other/stroyka-app"}),
                           ("status", "in_progress"), ("conclusion", "failure")):
            with self.subTest(key=key), self.assertRaisesRegex(SystemExit, "CI is not successful"):
                self.preflight(ci_updates={key: value})

    def test_preflight_rejects_changed_or_missing_or_duplicate_proof(self):
        for key, value in (("migration", "0008_unreviewed"), ("warehouseRows", 54),
                           ("warehouseDataUnchanged", False), ("vatSchemaUnchanged", False),
                           ("rowsSha256", "0" * 64), ("extra", "unreviewed")):
            with self.subTest(key=key), self.assertRaisesRegex(SystemExit, "evidence does not match"):
                self.preflight(proof_updates={key: value})
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaisesRegex(SystemExit, "evidence does not match"):
                self.preflight(count=count)

    def database_env(self, address, database="stroyka", port="5432"):
        config = dict(dbname="stroyka", host="localhost", port="5432", user="app", password="fake")
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        def select_identity(query):
            self.assertTrue(query.startswith("SELECT current_database(), current_setting('port'), "))
            if "host(inet_server_addr())" in query.replace(" ", ""):
                host = address
            elif "inet_server_addr()::text" in query:
                host = None if address is None else address + ("/128" if ":" in address else "/32")
            else:
                self.fail("unexpected server identity query")
            cursor.fetchone.return_value = (database, port, host)
        cursor.execute.side_effect = select_identity
        connect = Mock(return_value=conn)
        artifact = SimpleNamespace(write_text=Mock())
        environment = {"PGHOSTADDR": "wrong", "PGPASSWORD": "wrong"}
        paths = {"/proc/1234/environ": SimpleNamespace(read_bytes=lambda: b""),
                 "migration-env.json": artifact}
        def execute():
            with redirect_stdout(io.StringIO()) as output:
                self.execute_embedded("DB_ENV_PY", {
                    "json": json, "os": SimpleNamespace(environ=environment),
                    "sys": SimpleNamespace(argv=["db-env", "1234", "migration-env.json"]),
                    "pathlib": SimpleNamespace(Path=paths.__getitem__),
                    "psycopg2": SimpleNamespace(connect=connect),
                    "backend.db": SimpleNamespace(DB_CONFIG=config),
                })
            return output.getvalue()
        return SimpleNamespace(run=execute, conn=conn, connect=connect, config=config,
                               artifact=artifact, environment=environment)

    def test_db_env_accepts_loopback_ipv4_ipv6_and_unix_socket(self):
        for address in ("127.0.0.1", "::1", None):
            with self.subTest(address=address):
                case = self.database_env(address)
                self.assertEqual(case.run(), "MIGRATION_DATABASE_ENV_VERIFIED\n")
                case.connect.assert_called_once_with(**case.config, connect_timeout=5)
                case.conn.set_session.assert_called_once_with(readonly=True)
                case.conn.rollback.assert_called_once_with()
                case.conn.close.assert_called_once_with()
                case.artifact.write_text.assert_called_once()
                self.assertEqual(json.loads(case.artifact.write_text.call_args.args[0]), {
                    "DB_NAME": "stroyka", "DB_HOST": "localhost", "DB_PORT": "5432",
                    "DB_USER": "app", "DB_PASSWORD": "fake",
                })
                self.assertEqual(case.environment, {"PGPASSFILE": "/dev/null", "PGCONNECT_TIMEOUT": "5"})

    def test_db_env_rejects_wrong_identity_and_closes_without_env_artifact(self):
        cases = (("127.0.0.1", "other", "5432"), ("127.0.0.1", "stroyka", "5433"),
                 ("192.0.2.1", "stroyka", "5432"), ("2001:db8::1", "stroyka", "5432"))
        for address, database, port in cases:
            with self.subTest(address=address, database=database, port=port):
                case = self.database_env(address, database, port)
                with self.assertRaisesRegex(SystemExit, "not the reviewed local server"):
                    case.run()
                case.conn.set_session.assert_called_once_with(readonly=True)
                case.conn.rollback.assert_called_once_with()
                case.conn.close.assert_called_once_with()
                case.artifact.write_text.assert_not_called()

    def test_shell_syntax_without_executing_the_runner(self):
        result = subprocess.run(["/bin/bash", "-n", str(RUNNER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_and_successful_ci_identifiers_are_pinned(self):
        for value in (BEFORE, TARGET, CI_RUN):
            self.assertRegex(self.code, rf"(?m)^(?:readonly )?\w+=[\"']?{value}[\"']?$")
            self.assertNotRegex(self.code, rf"\$\{{[^}}]*{value}[^}}]*\}}")

    def test_root_lock_and_private_backup_defaults_are_fail_closed(self):
        self.assertRegex(self.code, r"set\s+-[^\n]*e[^\n]*u[^\n]*pipefail")
        self.assertRegex(self.code, r"(?:EUID|id\s+-u)")
        self.assertRegex(self.code, r"umask\s+0?077")
        self.assertRegex(self.code, r"flock\s+-n\s+")
        self.assertRegex(self.code, r"mktemp\s+-d\s+/root/")

    def test_main_exact_head_and_clean_index_are_checked(self):
        self.assertRegex(self.code, r"git[^\n]*rev-parse\s+HEAD")
        self.assertRegex(self.code, r"git[^\n]*branch\s+--show-current")
        self.assertIn("main", self.code)
        self.assertRegex(self.code, r"git[^\n]*diff\s+--quiet")
        self.assertRegex(self.code, r"git[^\n]*diff\s+--cached\s+--quiet")
        self.assertIn("0006_user_company_staff_links", self.code)

    def test_target_must_be_available_and_only_reviewed_migration_can_change(self):
        self.assertRegex(self.code, r"git[^\n]*(?:cat-file|rev-parse\s+--verify)")
        self.assertRegex(self.code, r"git[^\n]*merge-base\s+--is-ancestor")
        self.assertRegex(self.code, r"git[^\n]*diff\s+--name-only[^\n]*--\s+migrations")
        self.assertIn("migrations/versions/" + MIGRATION, self.code)
        self.assertRegex(self.code, r"git diff --quiet[^\n]*--[^\n]*alembic\.ini")

    def test_rehearsal_evidence_is_pinned_and_validated_before_merge(self):
        self.assertIn("/root/stroyka-supply-rehearsal-0W76EnqI", self.code)
        self.assertIn("warehouseDataUnchanged", self.code)
        self.assertIn("vatSchemaUnchanged", self.code)
        self.assertIn("warehouseRows", self.code)
        self.assertIn("53", self.code)
        self.assertIn("rowsSha256", self.code)
        self.assertLess(self.position(r"warehouseDataUnchanged"),
                        self.position(r"git\s+merge\s+--ff-only"))

    def test_rehearsal_migration_blob_must_match_final_candidate(self):
        self.assertIn('MIGRATION="migrations/versions/' + MIGRATION + '"', self.code)
        self.assertIn('test "$(git rev-parse "$REHEARSED:$MIGRATION")" = '
                      '"$(git rev-parse "$TARGET:$MIGRATION")"', self.code)

    def test_fresh_database_code_frontend_and_env_backups_precede_merge(self):
        merge = self.position(r"git\s+merge\s+--ff-only")
        for operation in (r"pg_dump\b", r"git\s+archive\b",
                          r"cp\s+-[^\n]*\bbuild\b", r"cp\s+-[^\n]*backend/\.env"):
            self.assertLess(self.position(operation), merge)
        self.assertRegex(self.code, r"pg_dump\b[^\n]*>\s*\"")
        self.assertRegex(self.code, r"pg_restore\s+--list\b[^\n]*<\s*\"")

    def test_upgrade_is_exactly_reviewed_0007_never_moving_head(self):
        original = RUNNER.parent.parent.joinpath("deploy.sh").read_text(encoding="utf-8")
        rendered = self.render(original)
        expected = original.replace("git reset --hard HEAD\n", "").replace("git pull --ff-only\n", "")
        pinned = 'python3 -m alembic -c "$APP_ROOT/alembic.ini" upgrade ' + REVISION
        expected = expected.replace("python3 -m alembic upgrade head\n", pinned + "\n")
        self.assertEqual(rendered, expected)
        self.assertIn("bash scripts/prod-smoke-check.sh", rendered)
        self.assertIn(pinned, rendered)
        self.assertNotRegex(rendered, r"git (?:reset|pull)\b|alembic (?:downgrade|upgrade head)\b")

    def test_render_missing_or_duplicate_reviewed_lines_fails_closed(self):
        original = RUNNER.parent.parent.joinpath("deploy.sh").read_text(encoding="utf-8")
        for line in ("git reset --hard HEAD\n", "git pull --ff-only\n", "python3 -m alembic upgrade head\n"):
            for count in (0, 2):
                with self.subTest(line=line, count=count), self.assertRaises(SystemExit):
                    self.render(original.replace(line, line * count))

    def test_no_executable_reset_pull_database_restore_or_drop(self):
        self.assertNotRegex(self.code, r"(?m)^\s*git\b[^\n]*\s(?:reset|pull)(?:\s|$)")
        restores = re.findall(r"(?m)^\s*(?:\w+\s+)*pg_restore\b[^\n]*", self.code)
        self.assertTrue(restores, "backup archive listing is required")
        self.assertTrue(all("--list" in line for line in restores), restores)
        self.assertNotRegex(self.code, r"(?m)^\s*(?:sudo\s+)?dropdb\b")
        self.assertNotRegex(self.code, r"(?i)\bDROP\s+DATABASE\b")
        self.assertNotRegex(self.code, r"(?m)^\s*(?:source|\.)\s+[^\n]*\.env\b")

    def test_child_runs_in_own_process_group_and_is_stopped_before_rollback(self):
        self.assertRegex(self.code, r"\bsetsid\s+")
        self.assertRegex(self.code, r"kill\s+-(?:TERM|KILL)[^\n]*--\s+[\"']?-\$")
        self.assertRegex(self.code, r"\bwait\s+[\"']?\$")
        self.assertLess(self.position(r"kill\s+-(?:TERM|KILL)"),
                        self.position(r"git\s+switch\s+--detach"))

    def test_application_rollback_pins_previous_checkout_and_checks_health(self):
        self.assertRegex(self.code, r"git\s+switch\s+--detach\s+\"\$BEFORE\"")
        self.assertIn("asset-manifest.json", self.code)
        self.assertRegex(self.code, r"(?:ROLLED_BACK|rollback|rolled back)")
        self.assertRegex(self.code, r"(?:check_health|health_check|/health)")

    def test_production_smoke_is_explicitly_business_read_only(self):
        self.assertIn("SMOKE_BUSINESS_READ_ONLY=1", self.code)
        self.assertNotRegex(self.code, r"SUPPLY_CHAIN_RUN_POSTGRES=1")
        self.assertNotRegex(self.code, r"(?:python\S*\s+-m\s+pytest|build_fixture\(|_seed\()")

    def test_launch_freezes_database_cleans_libpq_and_keeps_readonly_smoke(self):
        frozen = dict(DB_NAME="stroyka", DB_HOST="localhost", DB_PORT="5432", DB_USER="app", DB_PASSWORD="fake")
        inherited = dict.fromkeys([*frozen, "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGOPTIONS"], "wrong")
        inherited.update(PATH="/usr/bin:/bin", SMOKE_BUSINESS_READ_ONLY="1", ALEMBIC_CONFIG="/tmp/other.ini")
        launch = SimpleNamespace(environ=inherited, execvpe=Mock())
        self.execute_embedded("LAUNCH_PY", {
            "json": json, "os": launch, "sys": SimpleNamespace(argv=["launch", "frozen.json", "reviewed.sh"]),
            "pathlib": SimpleNamespace(Path={"frozen.json": SimpleNamespace(read_text=lambda **_: json.dumps(frozen))}.__getitem__),
        })
        launch.execvpe.assert_called_once_with("bash", ["bash", "reviewed.sh"], {
            "PATH": "/usr/bin:/bin", "SMOKE_BUSINESS_READ_ONLY": "1", **frozen,
            "PGPASSFILE": "/dev/null", "PGCONNECT_TIMEOUT": "5",
            "ALEMBIC_CONFIG": "/var/www/stroyka-app/alembic.ini",
        })

    def test_post_deploy_checks_cover_revision_health_and_frontend_manifest(self):
        self.assertIn(REVISION, self.code)
        self.assertRegex(self.code, r"(?:/health|healthz)")
        self.assertIn("asset-manifest.json", self.code)
        self.assertRegex(self.code, r"(?:json\.load|json\.loads)")
        self.assertGreaterEqual(len(re.findall(r"git[^\n]*rev-parse\s+HEAD", self.code)), 2)


if __name__ == "__main__":
    unittest.main()
