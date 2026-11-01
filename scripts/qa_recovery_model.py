"""Pure offline orchestration model. Never dispatches commands or callbacks.

Transitions validate hypothetical evidence, not facts about a server. Even the
terminal state is a model result, never release authorization.
"""
from dataclasses import dataclass
import re
from scripts.qa_bootstrap_plan import HOLD, recovery_gaps

STAGES = (
    ('identify', ('qa_identity', 'both_backend_versions', 'shared_storage', 'frontend_mapping')),
    ('quiesce', ('both_writers_stopped', 'workers_stopped', 'restart_prevented')),
    ('backup', ('recovery_bundle', 'restore_demonstration')),
    ('empty_schema', ('approved_scope', 'empty_schema_verified')),
    ('base_schema', ('schema_only_completed', 'no_seed_or_repairs')),
    ('migrations', ('full_graph_completed', 'revision_0109')),
    ('schema_check', ('constraints_verified', 'functions_triggers_verified')),
    ('seed', ('synthetic_owners_verified', 'default_accounts_secured', 'external_actions_disabled')),
    ('candidate', ('matching_frontend', 'candidate_checks', 'first_backend_stopped')),
    ('acceptance', ('authorized_business_acceptance', 'recovery_retained')),
)


@dataclass(frozen=True)
class ModelState:
    build_sha: str
    position: int = 0
    status: str = 'planning'
    journal: tuple = ()


def new_model(build_sha):
    if not isinstance(build_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', build_sha):
        raise ValueError('exact build SHA required')
    return ModelState(build_sha)


def advance(state, stage, evidence):
    if state.status != 'planning' or state.position >= len(STAGES):
        raise ValueError('model cannot advance')
    expected, required = STAGES[state.position]
    if stage != expected:
        raise ValueError('out-of-order or repeated stage')
    if not isinstance(evidence, dict) or evidence.get('build_sha') != state.build_sha:
        raise ValueError('evidence build mismatch')
    if any(evidence.get(key) is not True for key in required):
        raise ValueError('missing positive evidence')
    if stage == 'backup' and recovery_gaps(evidence.get('recovery')):
        raise ValueError('incomplete recovery evidence')
    # Store labels only, never configuration, credentials, SQL or caller payloads.
    journal = state.journal + ((stage, state.build_sha),)
    position = state.position + 1
    return ModelState(state.build_sha, position,
                      'model_complete_execution_held' if position == len(STAGES) else 'planning', journal)


def fail(state):
    if state.status != 'planning':
        raise ValueError('only active model can fail')
    return ModelState(state.build_sha, state.position, 'failed_execution_held', state.journal)


def recovery_plan(state):
    if state.status != 'failed_execution_held':
        raise ValueError('no failed transition')
    return {
        'execution_allowed': False, 'blocker': HOLD,
        'actions': ('keep_both_writers_stopped', 'preserve_failure_evidence_and_new_results',
                    'verify_original_bundle', 'restore_consistent_database_files_code_config',
                    'verify_old_backend_database_frontend', 'separately_authorize_reopening'),
        'automatic_downgrade': False, 'cleanup_allowed': False,
    }


def execute(*args, **kwargs):
    # Deliberately no adapter interface capable of carrying out the plan.
    raise RuntimeError(HOLD)
