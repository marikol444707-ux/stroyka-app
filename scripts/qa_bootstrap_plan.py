"""Offline preparation only. No executor, subprocess, application or DB imports."""
import ast
from pathlib import Path

TARGET = '0109_legacy_payment_requests'
BASE = '012c9984dabd2e60ab8983f233fb2e8acf9b4703'
HOLD = 'QA_BOOTSTRAP_EXECUTION_NOT_ACCEPTED'


def migration_order(directory):
    """Read literal revision metadata without importing migration modules."""
    parents = {}
    for path in sorted(Path(directory).glob('*.py')):
        if path.name == '__init__.py':
            continue
        metadata = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('revision', 'down_revision', 'depends_on'):
                        metadata[target.id] = ast.literal_eval(node.value)
        revision = metadata.get('revision')
        parent = metadata.get('down_revision')
        if not isinstance(revision, str) or revision in parents:
            raise ValueError('missing or duplicate revision')
        if parent is not None and not isinstance(parent, str):
            raise ValueError('branch merge requires explicit review')
        if metadata.get('depends_on') is not None:
            raise ValueError('additional dependencies require explicit review')
        parents[revision] = parent
    heads = set(parents) - {p for p in parents.values() if p is not None}
    if heads != {TARGET}:
        raise ValueError('unexpected migration heads')
    order, current = [], TARGET
    while current is not None:
        if current not in parents or current in order:
            raise ValueError('missing parent or cycle')
        order.append(current)
        current = parents[current]
    if len(order) != len(parents):
        raise ValueError('disconnected migration graph')
    return list(reversed(order))


def preparation_plan(directory):
    """A plan can never authorize execution, even with a valid graph."""
    return {
        'source_commit': BASE,
        'target_revision': TARGET,
        'migration_order': migration_order(directory),
        'execution_allowed': False,
        'blockers': [HOLD, 'BASE_SCHEMA_EXECUTION_UNACCEPTED',
                     'RESTORE_NOT_VERIFIED', 'RUNTIME_SCOPE_NOT_APPROVED'],
        'stages': ['freeze_both_writers', 'verified_recovery_bundle',
                   'approved_empty_schema', 'base_schema_without_seed_or_repairs',
                   'all_migrations_from_base', 'schema_contract_verification',
                   'approved_synthetic_seed', 'candidate_and_matching_frontend'],
        'recovery_components': ['qa_database', 'qa_uploads', 'both_backend_versions',
                                'frontend_manifest_and_assets', 'protected_runtime_configuration'],
        'first_backend': 'retain_stopped_until_startup_and_write_compatibility_accepted',
        'cleanup_allowed': False,
    }


def require_execution_allowed(*args, **kwargs):
    """No override or executor is provided by this preparatory package."""
    raise RuntimeError(HOLD)


def recovery_gaps(evidence):
    """Assess explicit evidence metadata; never perform or authorize restore.

    True must be a boolean, not a path, nonempty string or merely a dump exit code.
    This does not independently verify evidence authenticity.
    """
    required = ('both_backend_writers_stopped', 'other_writers_accounted_for',
                'database_backup_verified', 'uploads_backup_verified',
                'both_backend_versions_recorded', 'frontend_bundle_verified',
                'protected_configuration_retained', 'restore_demonstrated',
                'qa_target_identity_verified')
    if not isinstance(evidence, dict):
        return list(required)
    return [key for key in required if evidence.get(key) is not True]
