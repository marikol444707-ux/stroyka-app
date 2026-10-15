"""Read-only guard diagnostic; does not pin DDL or enable weaker merge locks."""
from .history_lock_schema import GUARD_BODY


def packaging_guard_ready(cur):
    """Require the exact row trigger/function contract, without repairing it.

    A positive result describes this catalog snapshot only. A future merge caller
    must separately prevent concurrent guard DDL before relying on this result.
    """
    cur.execute(
        """SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
            JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
            JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE t.tgrelid=to_regclass('public.material_packaging_rules')
              AND c.relkind='r' AND NOT c.relispartition
              AND EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid
                          AND a.attname='supplier_id' AND a.atttypid='pg_catalog.int4'::regtype
                          AND a.attnum>0 AND NOT a.attisdropped)
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i
                              WHERE i.inhrelid=c.oid OR i.inhparent=c.oid)
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger other
                              WHERE other.tgrelid=c.oid AND NOT other.tgisinternal AND other.oid<>t.oid)
              AND t.tgname='material_packaging_history_writer_guard'
              AND t.tgenabled='A' AND t.tgtype=31 AND NOT t.tgisinternal
              AND t.tgnargs=0 AND t.tgqual IS NULL AND t.tgattr=''::int2vector
              AND t.tgconstraint=0 AND NOT t.tgdeferrable AND NOT t.tginitdeferred
              AND n.nspname='public' AND p.proname='material_packaging_history_writer_guard'
              AND p.prokind='f' AND p.pronargs=0 AND p.proargtypes=''::oidvector
              AND p.prorettype='pg_catalog.trigger'::regtype AND NOT p.proretset
              AND l.lanname='plpgsql' AND NOT p.prosecdef AND NOT p.proisstrict
              AND NOT p.proleakproof AND p.provolatile='v' AND p.proparallel='u'
              AND p.procost=100
              AND p.proconfig=ARRAY['search_path=pg_catalog']::text[]
              AND p.prosrc=%s
        ) AS ready""", (GUARD_BODY,),
    )
    row = cur.fetchone()
    return bool(row['ready'] if isinstance(row, dict) else row[0])
