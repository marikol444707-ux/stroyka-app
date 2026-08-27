import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = PROJECT_ROOT / "deploy.sh"


class DeployMigrationTests(unittest.TestCase):
    def test_deploy_checks_migration_dependencies_before_build(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        dependency_gate = "import alembic, psycopg2, sqlalchemy"
        frontend_build = 'BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build'

        self.assertIn(dependency_gate, deploy)
        self.assertLess(
            deploy.index(dependency_gate),
            deploy.index(frontend_build),
        )

    def test_deploy_migrates_after_build_and_before_restart(self):
        deploy = DEPLOY_PATH.read_text(encoding="utf-8")

        frontend_build = 'BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build'
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


if __name__ == "__main__":
    unittest.main()
