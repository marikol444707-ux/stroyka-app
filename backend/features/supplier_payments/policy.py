"""Internal new-operation policy, not registered with any runtime route.

Use ONLY after build_document_resolver in the engine-owned transaction. The
resolver supplies current owner/payer authorization and retains physical locks.
Engine replay precedes this callback; the engine also owns UUID, original
reversal identity, remaining-balance bounds and atomic ledger validation.

Actual payments may be recorded on any date, including during deferral and
before acceptance. Schedule, advance and accepted amounts are NOT caps. Their
informational presentation/warnings belong outside this eligibility callback.
"""
from decimal import Decimal

from fastapi import HTTPException

from .documents import TABLES, _snapshot
from .statuses import payment_status_eligible


def validate_new_payment(cur, context, command, signed_amount):
    """Recheck live identity for both directions; approval gates payments only.

    No DDL, writes, commits, receipt queries or deadline calculations. A reversal
    can undo a bad record even if the document is now pending, held or cancelled;
    it still needs the resolver's authorization and the engine's integrity checks.
    """
    if cur.connection.autocommit:
        raise RuntimeError('Payment policy requires the engine transaction')
    kind = command.get('kind')
    if (kind not in ('payment', 'reversal') or not isinstance(signed_amount, Decimal)
            or not signed_amount.is_finite() or signed_amount == 0
            or (signed_amount > 0) != (kind == 'payment')):
        raise HTTPException(409, 'Направление операции оплаты требует сверки')
    documents = context.get('documents')
    if not isinstance(documents, list) or not 1 <= len(documents) <= 2:
        raise HTTPException(409, 'Не определены документы оплаты')
    for doc in sorted(documents, key=lambda value: (value['kind'], value['id'])):
        if doc['kind'] not in TABLES:
            raise HTTPException(409, 'Неизвестный вид документа оплаты')
        table = TABLES[doc['kind']][0]
        cur.execute(f'SELECT * FROM {table} WHERE id=%s', (doc['id'],))
        row = cur.fetchone()
        if not row:
            raise HTTPException(409, 'Документ оплаты больше не существует')
        live = _snapshot(doc['kind'], row, doc['payerCompanyId'], cur=cur)
        if any(doc.get(key) != value for key, value in live.items()):
            raise HTTPException(409, 'Реквизиты документа изменились после проверки доступа')
        if kind == 'reversal':
            continue
        if not payment_status_eligible(doc['kind'], row):
            raise HTTPException(409, 'Документ не утверждён к оплате или требует сверки')
