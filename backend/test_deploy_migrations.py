import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = PROJECT_ROOT / "deploy.sh"
FRONTEND_ENV_PATH = PROJECT_ROOT / "scripts" / "resolve-frontend-build-env.sh"


class DeployMigrationTests(unittest.TestCase):
    def test_deploy_checks_migration_dependencies_before_build(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        dependency_gate = "import alembic, psycopg2, sqlalchemy"
        frontend_build = (
            'env "${FRONTEND_BUILD_ENV[@]}" '
            'BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build'
        )

        self.assertIn(dependency_gate, deploy)
        self.assertLess(
            deploy.index(dependency_gate),
            deploy.index(frontend_build),
        )

    def test_deploy_migrates_after_build_and_before_restart(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        frontend_build = (
            'env "${FRONTEND_BUILD_ENV[@]}" '
            'BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build'
        )
        migration = "python3 -m alembic upgrade head"
        restart = "systemctl restart stroyka"

        self.assertIn(migration, deploy)
        self.assertIn("lock_timeout=5000", deploy)
        self.assertIn("statement_timeout=60000", deploy)
        self.assertLess(deploy.index(frontend_build), deploy.index(migration))
        self.assertLess(deploy.index(migration), deploy.index(restart))
        self.assertNotIn("alembic stamp", deploy)

    def test_active_agent_worker_restarts_after_backend_and_before_smoke(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        backend_restart = "systemctl restart stroyka"
        worker_restart = 'systemctl restart "$AGENT_JOB_WORKER_UNIT"'
        smoke = "bash scripts/prod-smoke-check.sh"

        self.assertIn(worker_restart, deploy)
        self.assertLess(deploy.index(backend_restart), deploy.index(worker_restart))
        self.assertLess(deploy.index(worker_restart), deploy.index(smoke))

    def test_deploy_preserves_enabled_a10_canary_in_frontend_build(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        resolver = "bash scripts/resolve-frontend-build-env.sh"
        frontend_build = (
            'env "${FRONTEND_BUILD_ENV[@]}" '
            'BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build'
        )

        self.assertIn(resolver, deploy)
        self.assertIn(frontend_build, deploy)
        self.assertLess(deploy.index(resolver), deploy.index(frontend_build))

    def test_frontend_env_resolver_copies_only_valid_enabled_a10_flags(self):
        result = subprocess.run(
            [
                "bash",
                str(FRONTEND_ENV_PATH),
                (
                    "OTHER=value "
                    '"ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true" '
                    '"ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=1,2"'
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED=true",
            "REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS=1,2",
        ])

    def test_frontend_env_resolver_keeps_a10_off_when_backend_is_off(self):
        result = subprocess.run(
            [
                "bash",
                str(FRONTEND_ENV_PATH),
                "ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=1",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_frontend_env_resolver_fails_closed_on_invalid_enabled_allowlist(self):
        for company_ids in ("", "01", "1,1", "1, 2", "9007199254740992"):
            with self.subTest(company_ids=company_ids):
                result = subprocess.run(
                    [
                        "bash",
                        str(FRONTEND_ENV_PATH),
                        (
                            "ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true "
                            f"ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS={company_ids}"
                        ),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
