"""Read-only HTTP admission check; never installs or repairs a schema."""
from fastapi import HTTPException

from .reads import require_schema


_TABLES = ('supplier_payment_allocation_groups', 'supplier_payment_receipt_relations',
           'supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows')
REQUIRED_TRIGGERS = tuple(
    (table, trigger) for table in _TABLES
    for trigger in ('allocation_immutable', 'allocation_no_truncate',
                    'allocation_insert', 'allocation_complete')
) + (
    ('supplier_payment_allocation_revisions', 'a_allocation_namespace'),
    ('supplier_payment_documents', 'a_allocation_mode'),
    ('supplier_payment_operations', 'a_allocation_mode'),
    ('supplier_payment_operations', 'a_allocation_namespace'),
    ('supplier_payment_impacts', 'a_allocation_mode'),
    ('supplier_payment_attachments', 'a_allocation_mode'),
    ('supplier_payment_attachments', 'a_allocation_namespace'),
    ('supplier_payment_request_cancellations', 'a_allocation_namespace'),
) + tuple(
    (table, trigger) for table in ('supplier_invoices', 'warehouse_invoices', 'supply_deliveries')
    for trigger in ('a_allocation_physical', 'allocation_physical_no_truncate')
) + tuple(
    (table, 'supplier_payment_no_truncate') for table in (
        'supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts')
) + (
    ('supplier_payment_attachments', 'supplier_payment_attachment_no_truncate'),
)


def require_allocation_schema(cur):
    """After current authority, before replay/write; not an online migration lock.

0021 admission also depends on the existing payment/package/cancellation guards.
Runtime registration and deployment quiescence remain separate release gates.
"""
    require_schema(cur, {}, require_cancellations=True)
    cur.execute('''SELECT NOT EXISTS (
        SELECT 1 FROM unnest(%s::text[],%s::text[]) required(table_name,trigger_name)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_trigger t
            WHERE t.tgrelid=to_regclass('public.' || required.table_name)
              AND t.tgname=required.trigger_name AND t.tgenabled IN ('O','A')
        )) AS ready''',
        ([pair[0] for pair in REQUIRED_TRIGGERS], [pair[1] for pair in REQUIRED_TRIGGERS]))
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Схема распределения оплат не подготовлена')
