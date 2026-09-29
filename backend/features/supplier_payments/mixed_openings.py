"""Internal mixed opening writer; no HTTP activation until cash consumers support scope."""
from uuid import UUID
from fastapi import HTTPException
from .commands import positive_id, command_fingerprint
from .reads import transaction
from .statuses import payment_status_eligible
from .mixed_opening_review import lock_authorized_pair
from .mixed_scope_evidence import load_current_review, require_schema as require_review_schema
from .openings import _result, require_schema as require_opening_schema


def normalize(body):
    if not isinstance(body, dict) or set(body) != {'requestId','invoiceId','reviewId','reason'}:
        raise HTTPException(422, 'Нужны UUID, счёт, сохранённая сверка и основание')
    try:
        request_id = str(UUID(body['requestId']))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Некорректный UUID подтверждения') from None
    reason = body['reason']
    if not isinstance(reason,str) or not 1 <= len(reason.strip()) <= 1000:
        raise HTTPException(422, 'Укажите основание подтверждения')
    return dict(requestId=request_id, invoiceId=positive_id(body['invoiceId']),
                reviewId=positive_id(body['reviewId'], maximum=9223372036854775807), reason=reason.strip())


def require_schema(cur):
    require_opening_schema(cur)
    require_review_schema(cur)
    cur.execute("""SELECT to_regclass('public.supplier_mixed_opening_bindings') IS NOT NULL
        AND NOT EXISTS(SELECT 1 FROM (VALUES ('supplier_mixed_binding_insert'),
            ('supplier_mixed_binding_immutable'),('supplier_mixed_binding_no_truncate'),
            ('supplier_mixed_binding_complete')) required(name)
            WHERE NOT EXISTS(SELECT 1 FROM pg_trigger
                WHERE tgrelid=to_regclass('public.supplier_mixed_opening_bindings')
                AND tgname=required.name AND tgenabled IN ('O','A'))) AS ready""")
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Схема подтверждения смешанных накладных не подготовлена')


def confirm(get_db, authorize_write, actor_id, company_id, body):
    command = normalize(body)
    positive_id(actor_id); positive_id(company_id)
    fingerprint = command_fingerprint(company_id, actor_id, dict(command, kind='mixed-opening'))
    with transaction(dict(get_db=get_db, authorize_read=authorize_write), company_id) as cur:
        invoice, warehouse, _, payer, actor = lock_authorized_pair(
            cur, authorize_write, actor_id, company_id, command['invoiceId'])
        require_schema(cur)
        cur.execute('SELECT * FROM supplier_opening_confirmations WHERE company_id=%s AND request_id=%s',
                    (company_id, command['requestId']))
        previous = cur.fetchone()
        if previous:
            cur.execute("""SELECT r.package_scope,r.invoice_snapshot,d.payer_company_id FROM supplier_mixed_opening_bindings b
                JOIN supplier_mixed_scope_reviews r ON r.id=b.review_id
                JOIN supplier_payment_documents d ON d.id=b.invoice_record_id AND d.company_id=b.company_id
                WHERE b.confirmation_id=%s AND b.company_id=%s AND b.review_id=%s
                    AND r.invoice_id=%s AND r.warehouse_id=%s""",
                (previous['id'],company_id,command['reviewId'],invoice['id'],warehouse['id']))
            saved = cur.fetchone()
            if not saved:
                raise HTTPException(409, 'Связь подтверждения со сверкой требует проверки')
            for package in saved['package_scope']['requiredPackages']:
                authorize_write(cur,actor_id,company_id,saved['invoice_snapshot']['project_name'],
                                package,payer_company_id=saved['payer_company_id'])
            if previous['fingerprint'] != fingerprint:
                raise HTTPException(409, 'UUID подтверждения уже использован с другими данными')
            return _result(cur,previous)
        if not payment_status_eligible('invoice',invoice) or not payment_status_eligible('warehouse',warehouse):
            raise HTTPException(409,'Документ не утверждён к оплате или требует сверки')
        current = load_current_review(cur,authorize_write,actor_id,company_id,invoice['id'],command['reviewId'])
        if not isinstance(actor,dict) or not isinstance(actor.get('name'),str) or not actor['name'].strip():
            raise HTTPException(403,'Не определён сотрудник подтверждения')
        cur.execute("""SELECT nextval('supplier_payment_documents_id_seq') AS invoice,
            nextval('supplier_payment_documents_id_seq') AS warehouse,
            nextval('supplier_opening_confirmations_id_seq') AS confirmation""")
        ids=cur.fetchone()
        cur.execute("""INSERT INTO supplier_mixed_opening_bindings
            (review_id,company_id,invoice_record_id,warehouse_record_id,confirmation_id)
            VALUES(%s,%s,%s,%s,%s)""",
            (command['reviewId'],company_id,ids['invoice'],ids['warehouse'],ids['confirmation']))
        # Both records describe one debt. Preserve money from PostgreSQL numeric
        # columns rather than decoding/re-encoding monetary JSON snapshots.
        for kind, source in (('invoice',invoice),('warehouse',warehouse)):
            cur.execute("""INSERT INTO supplier_payment_documents
                (id,company_id,document_kind,document_id,payer_company_id,supplier_id,
                 project_name,work_package,amount,opening_paid)
                SELECT %s,company_id,%s,%s,%s,supplier_id,project_name,work_package,amount,paid_amount
                FROM supplier_invoices WHERE id=%s AND company_id=%s""",
                (ids[kind],kind,source['id'],payer,invoice['id'],company_id))
        cur.execute("""INSERT INTO supplier_opening_confirmations
            (id,company_id,request_id,fingerprint,document_record_id,warehouse_record_id,
             actor_id,actor_name,reason,source_snapshot,warehouse_snapshot,reviewed_hash)
            SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,invoice_snapshot,warehouse_snapshot,%s
            FROM supplier_mixed_scope_reviews WHERE id=%s AND company_id=%s RETURNING *""",
            (ids['confirmation'],company_id,command['requestId'],fingerprint,ids['invoice'],ids['warehouse'],
             actor_id,actor['name'],command['reason'],current['evidenceHash'],command['reviewId'],company_id))
        result = _result(cur,cur.fetchone())
        cur.connection.commit()
        return result
