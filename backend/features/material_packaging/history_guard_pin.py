"""Pin the exact packaging guard until commit; no weaker merge mode is enabled."""
from psycopg2 import errors

from .history_guard_readiness import packaging_guard_ready


def try_pin_packaging_guard(cur):
    """Return False for an unavailable guard; retain successful locks until commit.

    ALTER of the already canonical COST value pins the pg_proc tuple against
    concurrent CREATE OR REPLACE/ALTER. The function body and properties stay the
    same. The table lock also pins trigger DDL/TRUNCATE. This intentionally writes
    one catalog tuple, so only a READ COMMITTED write transaction may call it.
    """
    if cur.connection.autocommit:
        raise ValueError('Packaging guard pin requires an explicit transaction')
    cur.execute('SHOW transaction_isolation')
    row = cur.fetchone()
    isolation = row['transaction_isolation'] if isinstance(row, dict) else row[0]
    if isolation != 'read committed':
        return False

    cur.execute('SAVEPOINT packaging_history_guard_pin')
    try:
        cur.execute('LOCK TABLE public.material_packaging_rules IN ROW EXCLUSIVE MODE')
        pinned = packaging_guard_ready(cur)
        if pinned:
            # Readiness requires COST 100 already. Do not rewrite code, rights,
            # search_path, ownership, or a caller's noncanonical cost setting.
            cur.execute('ALTER FUNCTION public.material_packaging_history_writer_guard() COST 100')
            pinned = packaging_guard_ready(cur)
    except Exception as exc:
        cur.execute('ROLLBACK TO SAVEPOINT packaging_history_guard_pin')
        cur.execute('RELEASE SAVEPOINT packaging_history_guard_pin')
        if isinstance(exc, (errors.InsufficientPrivilege, errors.UndefinedTable, errors.UndefinedFunction)):
            return False
        # PostgreSQL catalog DDL uses XX000 for this specific concurrent-update
        # race rather than SerializationFailure. Do not hide other internal errors.
        if isinstance(exc, errors.InternalError_) and exc.diag.message_primary == 'tuple concurrently updated':
            return False
        raise

    if not pinned:
        cur.execute('ROLLBACK TO SAVEPOINT packaging_history_guard_pin')
    cur.execute('RELEASE SAVEPOINT packaging_history_guard_pin')
    return pinned
