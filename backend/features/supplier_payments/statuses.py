"""Shared financial eligibility; no engine/policy dependency cycle."""

INVOICE_PAYMENT_STATUSES = frozenset(('Утверждён', 'Частично оплачен', 'Оплачен'))
WAREHOUSE_PAYMENT_STATUSES = frozenset(('К оплате', 'Частично оплачена', 'Оплачена'))


def payment_status_eligible(kind, row):
    if kind == 'invoice':
        return row['status'] in INVOICE_PAYMENT_STATUSES
    if kind == 'warehouse':
        return (row['status'] not in ('Аннулирована', 'Аннулирован')
                and row['accounting_status'] in WAREHOUSE_PAYMENT_STATUSES)
    return False
