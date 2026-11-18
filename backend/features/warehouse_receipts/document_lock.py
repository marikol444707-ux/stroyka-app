"""One transaction lock per legal physical document, across receipt entry points."""
import hashlib
import json
from .duplicate_guard import normalize_invoice_date, normalize_invoice_number


def lock_physical_document(cur, company_id, document):
    identity = [str(company_id), str(document.get('supplierInn') or '').strip(),
                str(document.get('buyerInn') or '').strip(),
                normalize_invoice_number(document.get('waybillNumber')),
                normalize_invoice_date(document.get('waybillDate'))]
    key = 'physical-receipt-document:' + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (key,))
