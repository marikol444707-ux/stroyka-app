"""Bounded, read-only legacy alias report; no implicit DB configuration loading."""
import psycopg2.extras

from .readiness import build_alias_readiness


REQUIRED_COLUMNS = {
    'projects': {'id', 'company_id', 'name', 'archived'},
    'material_aliases': {'id', 'project_name', 'alias_name', 'canonical_name',
                         'canonical_unit', 'active'},
}


def collect_alias_readiness(cur, *, row_limit=50000, preview_limit=100):
    if type(row_limit) is not int or not 1 <= row_limit <= 100000:
        raise ValueError('row_limit must be between 1 and 100000')
    if type(preview_limit) is not int or not 0 <= preview_limit <= 1000:
        raise ValueError('preview_limit must be between 0 and 1000')
    base = {'ok': True, 'dryRun': True, 'writesAttempted': 0,
            'automaticAssignments': 0, 'readyForCutover': False, 'scanComplete': False}
    cur.execute("""SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=ANY(%s)""", (sorted(REQUIRED_COLUMNS),))
    present = {(r['table_name'], r['column_name']) for r in cur.fetchall()}
    missing = sorted(table + '.' + col for table, cols in REQUIRED_COLUMNS.items()
                     for col in cols if (table, col) not in present)
    if missing:
        return dict(base, schemaReady=False, missingColumns=missing, reasonCode='schema_not_ready')
    cur.execute('SELECT id,company_id,name,archived FROM public.projects ORDER BY id LIMIT %s', (row_limit + 1,))
    projects = [dict(row) for row in cur.fetchall()]
    if len(projects) > row_limit:
        return dict(base, schemaReady=True, reasonCode='project_scan_limit_exceeded')
    cur.execute('''SELECT id,project_name,alias_name,canonical_name,canonical_unit,active
        FROM public.material_aliases ORDER BY id LIMIT %s''', (row_limit + 1,))
    aliases = [dict(row) for row in cur.fetchall()]
    if len(aliases) > row_limit:
        return dict(base, schemaReady=True, reasonCode='alias_scan_limit_exceeded')
    return dict(build_alias_readiness(projects, aliases, preview_limit=preview_limit),
                schemaReady=True, missingColumns=[], scanComplete=True)


def run_alias_readiness(get_db, *, row_limit=50000, preview_limit=100):
    """Factory must return a dedicated fresh connection; always roll back and close.

    Caller explicitly chooses and authorizes the database. No main/config import,
    migration, runtime DDL, filesystem output or network destination is inferred.
    """
    conn, cur = get_db(), None
    try:
        conn.set_session(readonly=True, autocommit=False, isolation_level='REPEATABLE READ')
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SET LOCAL lock_timeout='3s'")
        result = collect_alias_readiness(cur, row_limit=row_limit, preview_limit=preview_limit)
        conn.rollback()
        return dict(result, readOnlyTransaction=True, rolledBack=True)
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()
