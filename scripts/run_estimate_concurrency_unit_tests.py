#!/usr/bin/env python3
"""Run affected estimate unit contracts with database/config imports blocked.

Unlike the PostgreSQL fixture launcher, this runner cannot open any database.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BOOTSTRAP = '''
import sys, types, psycopg2
def forbidden_database(*args, **kwargs):
    raise AssertionError("Database connections are forbidden in estimate unit tests")
psycopg2.connect = forbidden_database
for name in ("backend.db", "db"):
    module = types.ModuleType(name)
    module.get_db = forbidden_database
    module.DB_CONFIG = {}
    sys.modules[name] = module
for name in ("backend.config", "config"):
    sys.modules[name] = types.ModuleType(name)
'''

MODULES = (
    'backend.features.estimate_access.test_service',
    'backend.features.estimate_versions.test_routes',
    'backend.features.estimate_versions.test_automatic_snapshot_wiring',
    'backend.features.estimate_changes.test_service',
    'backend.features.estimate_changes.test_routes',
    'backend.features.estimate_changes.test_include_routes',
    'backend.features.estimate_changes.test_mutation_routes',
    'backend.features.estimate_deletion.test_service',
    'backend.features.material_control_ownership.test_estimate_api_contract',
    'backend.features.customer_cabinet.test_estimates',
    'backend.features.hidden_works_detection.test_local_route_cutover',
    'backend.features.hidden_works_detection.test_model_gateway_cutover',
    'backend.features.estimate_revision_impact.test_handoff',
)


def main():
    if len(sys.argv) != 1:
        raise SystemExit('This runner accepts no connection or module arguments.')
    exec(BOOTSTRAP, {})
    original_run = subprocess.run

    def guarded_run(command, *args, **kwargs):
        allowed_imports = {
            'from features.estimate_revision_impact.handoff import estimate_revision_impact_enabled',
            'from features.estimate_access.service import estimate_visibility_filter',
            'from features.estimate_versions.routes import register_estimate_versions_module',
            'from features.estimate_changes.routes import register_estimate_changes_module',
        }
        if len(command) != 3 or list(command[:2]) != [sys.executable, '-c'] or command[2] not in allowed_imports:
            raise AssertionError('Unexpected subprocess in guarded estimate unit tests')
        command = [command[0], command[1], BOOTSTRAP + '\n' + command[2]]
        env = {key: value for key, value in kwargs.get('env', os.environ).items()
               if not key.startswith(('PG', 'DB_', 'DATABASE_', 'PYTHONPYCACHEPREFIX'))}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        return original_run(command, *args, **dict(kwargs, env=env))

    subprocess.run = guarded_run
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        subprocess.run = original_run
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
