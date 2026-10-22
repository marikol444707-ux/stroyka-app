#!/usr/bin/env python3
"""Read-only readiness check for the unified 0100 -> 0102 release.

Never imports backend.main or initializes application tables. Connection values
come from the caller's runtime environment; reports contain no DSN or row data.
"""
import os

BASE_REVISION = '0100_packaging_history_guard'
MANUAL_REVISION = '0101_manual_brigade_origins'
TARGET_REVISION = '0102_job_candidates'
REQUIRED_COLUMNS = {
    'companies': {'id'}, 'users': {'id'},
    'projects': {'id', 'company_id'},
    'staff': {'id', 'company_id', 'company_scope_verified'},
    'user_company_roles': {'id', 'user_id', 'company_id', 'staff_id', 'active', 'role'},
    'brigade_contracts': {'id', 'company_id', 'project_id', 'contractor_id', 'work_package',
                         'status', 'party_snapshot_json', 'party_snapshot_hash'},
    'brigade_contract_items': {'id', 'contract_id', 'source_estimate_version_id'},
    'estimates': {'id', 'company_id'}, 'estimate_versions': {'id', 'estimate_id'},
    'suppliers': {'id'}, 'company_supplier_links': {'id', 'company_id', 'supplier_id'},
    'material_packaging_rules': {'id', 'supplier_id'},
}
ORIGIN_COLUMNS = {'contract_id', 'company_id', 'project_id', 'request_id',
                  'command_hash', 'created_by', 'created_at'}


def connection_settings(environ=None):
    values = os.environ if environ is None else environ
    # Require explicit target settings instead of backend.db's development defaults.
    required = ('DB_NAME', 'DB_USER', 'DB_HOST')
    if any(not values.get(name) for name in required):
        raise ValueError('EXPLICIT_DATABASE_SETTINGS_REQUIRED')
    return dict(dbname=values['DB_NAME'], user=values['DB_USER'], host=values['DB_HOST'],
                password=values.get('DB_PASSWORD', ''), port=values.get('DB_PORT', '5432'),
                connect_timeout=5, application_name='stroyka-release-readonly')


def inspect_connection(conn, *, require_target=False):
    blockers, checks = [], {}
    conn.set_session(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SET LOCAL lock_timeout='2s'")
            cur.execute('SHOW transaction_read_only')
            if cur.fetchone()[0] != 'on':
                raise ValueError('READ_ONLY_TRANSACTION_REQUIRED')
            cur.execute("SELECT current_setting('server_version_num')::int, pg_is_in_recovery()")
            version, replica = cur.fetchone()
            checks['postgresVersionNumber'] = version
            if version < 120000 or replica:
                blockers.append('UNSUPPORTED_OR_READ_REPLICA_DATABASE')
            cur.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public'")
            columns = {}
            for table, column in cur.fetchall():
                columns.setdefault(table, set()).add(column)
            if 'alembic_version' not in columns:
                blockers.append('ALEMBIC_VERSION_MISSING')
                revisions = []
            else:
                cur.execute('SELECT version_num FROM public.alembic_version ORDER BY version_num')
                revisions = [row[0] for row in cur.fetchall()]
            checks['revisions'] = revisions
            accepted = [TARGET_REVISION] if require_target else [BASE_REVISION, MANUAL_REVISION, TARGET_REVISION]
            if len(revisions) != 1 or revisions[0] not in accepted:
                blockers.append('UNEXPECTED_DATABASE_REVISION')
            missing = {table: sorted(required - columns.get(table, set()))
                       for table, required in REQUIRED_COLUMNS.items() if required - columns.get(table, set())}
            if missing:
                checks['missingColumns'] = missing
                blockers.append('REQUIRED_SCHEMA_MISSING')
            cur.execute("""SELECT t.tgname,t.tgenabled,c.relname FROM pg_catalog.pg_trigger t
                JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND NOT t.tgisinternal
                  AND t.tgname=ANY(%s)""", (['material_packaging_history_writer_guard',
                    'manual_brigade_origin_guard', 'manual_brigade_identity_guard'],))
            triggers = {name: (enabled, table) for name, enabled, table in cur.fetchall()}
            if triggers.get('material_packaging_history_writer_guard') != ('A', 'material_packaging_rules'):
                blockers.append('PACKAGING_GUARD_MISSING_OR_DISABLED')
            if revisions == [BASE_REVISION]:
                cur.execute("""SELECT count(*) FROM pg_catalog.pg_proc p
                    JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
                    WHERE n.nspname='public' AND p.proname=ANY(%s)""",
                            (['guard_manual_brigade_origin', 'guard_manual_brigade_identity'],))
                if 'manual_brigade_contract_origins' in columns or cur.fetchone()[0] or any(
                        name.startswith('manual_brigade_') for name in triggers):
                    blockers.append('UNVERSIONED_MANUAL_SCHEMA_PRESENT')
            elif revisions in ([MANUAL_REVISION], [TARGET_REVISION]):
                if ORIGIN_COLUMNS - columns.get('manual_brigade_contract_origins', set()):
                    blockers.append('MANUAL_ORIGIN_SCHEMA_MISSING')
                for name, table in [('manual_brigade_origin_guard', 'manual_brigade_contract_origins'),
                                    ('manual_brigade_identity_guard', 'brigade_contracts')]:
                    if triggers.get(name) not in [('O', table), ('A', table)]:
                        blockers.append('MANUAL_GUARD_MISSING_OR_DISABLED')
                if not missing and ORIGIN_COLUMNS <= columns.get('manual_brigade_contract_origins', set()):
                    cur.execute("""SELECT count(*),count(*) FILTER (WHERE c.id IS NULL OR p.id IS NULL
                        OR c.company_id IS DISTINCT FROM o.company_id
                        OR c.project_id IS DISTINCT FROM o.project_id
                        OR p.company_id IS DISTINCT FROM o.company_id OR c.contractor_id IS NOT NULL)
                        FROM public.manual_brigade_contract_origins o
                        LEFT JOIN public.brigade_contracts c ON c.id=o.contract_id
                        LEFT JOIN public.projects p ON p.id=o.project_id""")
                    count, invalid = cur.fetchone()
                    checks['manualOriginCount'], checks['invalidManualOrigins'] = count, invalid
                    if invalid:
                        blockers.append('MANUAL_ORIGIN_SCOPE_INVALID')
                    cur.execute("""SELECT contype,convalidated FROM pg_catalog.pg_constraint
                        WHERE conrelid='public.manual_brigade_contract_origins'::regclass""")
                    constraints = cur.fetchall()
                    if (any(not valid for _kind, valid in constraints)
                            or sum(kind == 'f' for kind, _valid in constraints) != 4
                            or sum(kind == 'p' for kind, _valid in constraints) != 1
                            or sum(kind == 'u' for kind, _valid in constraints) != 1
                            or sum(kind == 'c' for kind, _valid in constraints) != 1):
                        blockers.append('MANUAL_CONSTRAINTS_INCOMPLETE')
            if revisions == [TARGET_REVISION]:
                candidate_columns = {'id','company_id','source','identity_key','url','title','description','status','created_at','updated_at'}
                if candidate_columns - columns.get('crm_job_candidates', set()):
                    blockers.append('JOB_CANDIDATE_SCHEMA_MISSING')
                else:
                    cur.execute("""SELECT count(*) FROM pg_catalog.pg_constraint
                        WHERE conrelid='public.crm_job_candidates'::regclass AND contype='u'""")
                    if cur.fetchone()[0] < 2:
                        blockers.append('JOB_CANDIDATE_DEDUPE_CONSTRAINTS_MISSING')
            if not missing:
                cur.execute('SELECT count(*) FROM public.brigade_contracts WHERE contractor_id IS NULL')
                checks['unlinkedContractsForSeparateReview'] = cur.fetchone()[0]
                cur.execute("""SELECT pg_has_role(current_user,c.relowner,'USAGE')
                    AND has_schema_privilege(current_user,'public','CREATE')
                    FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relname='brigade_contracts'""")
                if not cur.fetchone()[0]:
                    blockers.append('MIGRATION_OWNERSHIP_REQUIRED')
        return {'status': 'blocked' if blockers else 'ready', 'readOnly': True,
                'blockers': sorted(set(blockers)), 'checks': checks,
                'pendingMigrations': ([MANUAL_REVISION, TARGET_REVISION] if revisions == [BASE_REVISION]
                                      else [TARGET_REVISION] if revisions == [MANUAL_REVISION] else [])}
    finally:
        conn.rollback()


def inspect_database(environ=None, *, require_target=False):
    import psycopg2
    conn = psycopg2.connect(**connection_settings(environ))
    try:
        return inspect_connection(conn, require_target=require_target)
    finally:
        conn.close()
