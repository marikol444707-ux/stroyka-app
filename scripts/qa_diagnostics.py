"""Private, allowlisted QA diagnostics. No work or application imports at import time."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

STAGES = frozenset(('deliver_target', 'preflight', 'prepare_frontend', 'verify_frontend',
    'record_maintenance_intent', 'accept_preparation', 'discard_preparation', 'stop',
    'prepare_database', 'switch', 'frontend', 'start_and_check', 'confirmation'))
CATEGORIES = frozenset(('child_failed', 'timeout', 'executable_missing', 'permission_denied',
    'dependency_missing', 'validation_failed', 'interrupted', 'unexpected_error', 'database_error'))
SQLSTATES = frozenset(('28000', '28P01', '42501', '3D000', '08000', '08001', '08003',
    '08004', '08006', '08007', '08P01', '53300', '53400', '57014', '57P01', '55P03',
    '42P01', '42703', '23505', '23503', '40001', '40P01'))
MARKER = 'QA_SAFE_ERROR:'


def classify(error):
    category = 'unexpected_error'
    for cls, name in ((subprocess.TimeoutExpired, 'timeout'),
                      (subprocess.CalledProcessError, 'child_failed'),
                      (FileNotFoundError, 'executable_missing'),
                      (PermissionError, 'permission_denied'),
                      (ImportError, 'dependency_missing'),
                      (ValueError, 'validation_failed'),
                      (KeyboardInterrupt, 'interrupted'), (InterruptedError, 'interrupted')):
        if isinstance(error, cls):
            category = name
            break
    result = {'category': category, 'uncertain_outcome': category in ('timeout', 'interrupted', 'child_failed')}
    if isinstance(error, subprocess.CalledProcessError):
        result['exit_code'] = error.returncode if type(error.returncode) is int else None
    original = getattr(error, 'orig', error)
    state = getattr(original, 'pgcode', None)
    if isinstance(state, str) and state in SQLSTATES:
        result.update(category='database_error', sqlstate=state)
    return result


def child_entry(run, payload, environment):
    """Only this fixed envelope crosses the child boundary, never a traceback."""
    import sys
    try:
        print(json.dumps(run(payload, environment)))
    except BaseException as error:
        print(MARKER + json.dumps(classify(error)), file=sys.stderr)
        raise SystemExit(1) from None


def child_failure(error, database=False):
    result = classify(error)
    if database and isinstance(error, subprocess.CalledProcessError):
        raw = error.stderr
        if isinstance(raw, bytes):
            raw = raw.decode('ascii', errors='replace')
        if isinstance(raw, str) and len(raw) < 1024 and raw.startswith(MARKER):
            try:
                parsed = json.loads(raw[len(MARKER):])
                if parsed.get('category') in CATEGORIES:
                    result['category'] = parsed['category']
                if parsed.get('sqlstate') in SQLSTATES:
                    result['sqlstate'] = parsed['sqlstate']
                if parsed.get('uncertain_outcome') is True:
                    result['uncertain_outcome'] = True
            except (ValueError, TypeError, AttributeError):
                pass
    return result


class DiagnosticError(ValueError):
    """String is constructed exclusively from internal enums and numeric fields."""
    def __init__(self, stage, details):
        self.stage = stage if stage in STAGES else 'preflight'
        category = details.get('category')
        self.details = {'category': category if isinstance(category, str) and category in CATEGORIES else 'unexpected_error',
                        'uncertain_outcome': details.get('uncertain_outcome') is True}
        for key in ('exit_code', 'child_index'):
            if type(details.get(key)) is int:
                self.details[key] = details[key]
        state = details.get('sqlstate')
        if isinstance(state, str) and state in SQLSTATES:
            self.details['sqlstate'] = state
        super().__init__(json.dumps({'stage': self.stage, **self.details}, sort_keys=True))


class Diagnostics:
    def __init__(self, parent='/opt'):
        from scripts.qa_maintenance import Journal
        self.directory = Path(tempfile.mkdtemp(prefix='stroyka-qa-diagnostics-', dir=parent))
        self.journal = Journal(self.directory / 'events.jsonl')
        self.stage = 'preflight'
        self.child_index = 0
        self.uncertain = False
        print('QA diagnostics journal: ' + str(self.directory / 'events.jsonl'), flush=True)
        self.event('created')

    def event(self, status, **fields):
        if status not in ('created', 'start', 'success', 'failure', 'cleanup', 'owned', 'child_start', 'child_success'):
            raise ValueError('Invalid diagnostic event')
        self.journal.record(stage=self.stage, status=status, **fields)

    def resource(self, kind, path):
        patterns = {'host_staging': r'/opt/stroyka-qa-prebuild-[A-Za-z0-9_-]+',
                    'container_staging': r'/tmp/stroyka-qa-prebuild\.[A-Za-z0-9]{10}',
                    'maintenance': r'/opt/stroyka-qa-maintenance-[A-Za-z0-9_-]+',
                    'configuration_backup': r'/opt/stroyka-qa-config-before-[A-Za-z0-9_-]+',
                    'publication': r'/var/lib/docker/volumes/stroyka-qa-frontend-work/_data/qa-publish-[A-Za-z0-9_-]+'}
        if kind not in patterns or not re.fullmatch(patterns[kind], str(path)):
            raise ValueError('Invalid owned resource')
        self.event('owned', resource=kind, path=str(path))

    def failure(self, error):
        details = error.details if isinstance(error, DiagnosticError) else classify(error)
        self.uncertain |= details.get('uncertain_outcome', False)
        self.event('failure', failure_stage=error.stage if isinstance(error, DiagnosticError) else self.stage, **details)
        return error if isinstance(error, DiagnosticError) else DiagnosticError(self.stage, details)

    def close(self):
        self.journal.close()


class LoggedDriver:
    """Stage boundaries preserve the existing executor's order and confirmation gate."""
    def __init__(self, driver, diagnostics):
        self.driver = driver
        self.diagnostics = diagnostics
        driver.diagnostics = diagnostics

    def __getattr__(self, name):
        method = getattr(self.driver, name)
        if name not in STAGES:
            return method
        def call(*args, **kwargs):
            d = self.diagnostics
            d.stage = name
            d.child_index = 0
            d.event('cleanup' if name == 'discard_preparation' else 'start',
                    uncertain_outcome=d.uncertain)
            try:
                value = method(*args, **kwargs)
            except BaseException as error:
                # Keep the underlying safe failure even if the disk stops accepting logs.
                try:
                    safe = d.failure(error)
                except Exception:
                    safe = error if isinstance(error, DiagnosticError) else DiagnosticError(name, classify(error))
                raise safe from None
            d.event('success')
            return value
        return call
