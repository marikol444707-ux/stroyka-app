"""Recorded user report, not a live attestation or execution authorization."""
PYTHON_PATH = '/opt/stroyka-qa-migrations-q7bfrs4e/venv/bin/python'
VERSIONS_PATH = '/opt/stroyka-qa-migrations-q7bfrs4e/installed-versions.json'
WHEELS_PATH = '/opt/stroyka-qa-migrations-q7bfrs4e/wheels-manifest.json'
DIRECT_PINS = {'alembic': '1.13.2', 'sqlalchemy': '2.0.31',
               'psycopg2-binary': '2.9.12', 'fastapi': '0.128.8', 'pydantic': '2.13.4'}
USER_REPORTED = {
    'pip_check': True, 'library_imports': True,
    'database_connection': False, 'migrations': False, 'restore': False,
    'evidence_source': 'user_report_not_independently_read',
}


def require_current_runtime(runtime):
    if runtime.python_path != PYTHON_PATH:
        raise ValueError('QA runtime differs from recorded installation')
    # Implementations must inspect the current installation and manifest, not
    # return the historical USER_REPORTED flag. No verifier is executed at import.
    if runtime.verify_current_installation(PYTHON_PATH, VERSIONS_PATH, WHEELS_PATH,
                                           dict(DIRECT_PINS)) is not True:
        raise ValueError('QA runtime installation requires fresh verification')
