"""Internal bound-mixed cash adapter; not mounted on public payment routes."""
from fastapi import HTTPException
from .commands import positive_id
from .documents import _snapshot, _require
from .mixed_opening_review import lock_authorized_pair
from .mixed_openings import require_schema
from .policy import validate_new_payment
from .reads import require_schema as require_ledger_schema


def bound_evidence(cur, company_id, warehouse_id):
    require_ledger_schema(cur, {})
    require_schema(cur)
    cur.execute("""SELECT r.package_scope,r.invoice_snapshot->>'project_name' AS project,
        r.invoice_snapshot->>'work_package' AS anchor,d.payer_company_id,
        r.invoice_id,r.warehouse_id,
        (to_jsonb(i)-ARRAY['paid_amount','status','paid_by','paid_at'])
            =(r.invoice_snapshot-ARRAY['paid_amount','status','paid_by','paid_at'])
        AND (to_jsonb(w)-ARRAY['paid_amount','accounting_status','status','paid_by','paid_at'])
            =(r.warehouse_snapshot-ARRAY['paid_amount','accounting_status','status','paid_by','paid_at'])
        AND r.package_scope=supplier_mixed_package_scope(w.items::text,i.work_package) AS unchanged
        FROM supplier_mixed_opening_bindings b
        JOIN supplier_mixed_scope_reviews r ON r.id=b.review_id AND r.company_id=b.company_id
        JOIN supplier_payment_documents d ON d.id=b.invoice_record_id AND d.company_id=b.company_id
        JOIN supplier_payment_documents wd ON wd.id=b.warehouse_record_id AND wd.company_id=b.company_id
        JOIN supplier_opening_confirmations c ON c.id=b.confirmation_id AND c.company_id=b.company_id
            AND c.document_record_id=d.id AND c.warehouse_record_id=wd.id
        JOIN supplier_invoices i ON i.id=r.invoice_id AND i.company_id=b.company_id
        JOIN warehouse_invoices w ON w.id=r.warehouse_id AND w.company_id=b.company_id
        WHERE b.company_id=%s AND r.warehouse_id=%s""",(company_id,warehouse_id))
    evidence=cur.fetchone()
    if not evidence:
        raise HTTPException(409,'Нет подтверждённого начального остатка смешанной накладной')
    return evidence


def bound_snapshot(kind, row, payer, *, cur):
    if kind == 'invoice':
        return _snapshot(kind,row,payer,cur=cur)
    evidence=bound_evidence(cur,row['company_id'],row['id'])
    _require(evidence['unchanged'] and evidence['payer_company_id']==payer)
    return _snapshot(kind,row,payer,cur=cur,validated_package=evidence['anchor'])


def build_resolver(authorize):
    if not callable(authorize):
        raise TypeError('Server financial authority required')

    def resolve(cur, actor_id, company_id, command):
        if command['documentKind']!='invoice' or command['kind'] not in ('payment','reversal'):
            raise HTTPException(409,'Для смешанной накладной поддерживаются доплата и сторно по счёту')
        invoice_id=positive_id(command['documentId'])
        invoice,warehouse,_,payer,actor=lock_authorized_pair(cur,authorize,actor_id,company_id,invoice_id)
        evidence=bound_evidence(cur,company_id,warehouse['id'])
        for package in evidence['package_scope']['requiredPackages']:
            authorize(cur,actor_id,company_id,evidence['project'],package,
                      payer_company_id=evidence['payer_company_id'])
        _require(evidence['unchanged'] and evidence['invoice_id']==invoice_id
                 and evidence['payer_company_id']==payer)
        _require(isinstance(actor,dict) and isinstance(actor.get('name'),str) and bool(actor['name'].strip()))
        documents=[bound_snapshot('invoice',invoice,payer,cur=cur),
                   bound_snapshot('warehouse',warehouse,payer,cur=cur)]
        _require(documents[0]['amount']==documents[1]['amount'])
        return dict(actorName=actor['name'],documents=documents)
    return resolve


def validate_new(cur, context, command, signed_amount):
    if command['kind'] not in ('payment','reversal'):
        raise HTTPException(409,'Недопустимая операция смешанной накладной')
    return validate_new_payment(cur,context,command,signed_amount,snapshot_document=bound_snapshot)
