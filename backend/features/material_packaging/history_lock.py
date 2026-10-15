"""First writer slice; merge retains its table locks until DB enforcement exists."""

PACKAGING_HISTORY_NAMESPACE = 94101


def lock_supplier_history_writer(cur, supplier_id):
    if supplier_id is not None:
        cur.execute('SELECT pg_advisory_xact_lock_shared(%s, %s)',
                    (PACKAGING_HISTORY_NAMESPACE, supplier_id))
