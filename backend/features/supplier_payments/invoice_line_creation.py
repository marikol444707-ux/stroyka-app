"""New-invoice-only snapshot helpers; no authority, connections, DDL or commit.

The existing invoice creation route owns authority, source locks and transaction.
Database birth evidence rejects use on old invoices, including updated old rows.
These helpers do not register receipts or authorize partial shipment consumption.
"""
from fastapi import HTTPException
from psycopg2.extras import Json

from .invoice_line_spec import build_invoice_line_spec


def require_invoice_line_schema(cur):
    """Read-only admission, not runtime migration or an online-DDL interlock."""
    guards = [('supplier_invoices', name) for name in (
        'invoice_line_spec_birth', 'invoice_line_spec_physical', 'invoice_line_spec_no_truncate')]
    guards += [(table, name) for table in ('supplier_invoice_line_specs', 'supplier_invoice_lines')
               for name in ('invoice_line_spec_insert', 'invoice_line_spec_complete',
                            'invoice_line_spec_immutable', 'invoice_line_spec_no_truncate')]
    cur.execute('''SELECT NOT EXISTS (
        SELECT 1 FROM unnest(%s::text[],%s::text[]) required(table_name,trigger_name)
        WHERE NOT EXISTS (SELECT 1 FROM pg_trigger t
            WHERE t.tgrelid=to_regclass('public.' || required.table_name)
              AND t.tgname=required.trigger_name AND t.tgenabled IN ('O','A'))
        ) AS ready''', ([table for table, _ in guards], [name for _, name in guards]))
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Схема товарных строк счёта не подготовлена')


def prepare_invoice_line_spec(offer, data, invoice_package):
    """Validate locked request/KP sources; an explicit invalid amount is not absent."""
    amount = data['amount'] if 'amount' in data else offer['exact_offer_total']
    vat = data['vatAmount'] if 'vatAmount' in data else 0
    try:
        spec = build_invoice_line_spec(offer['items_json'], offer['items_kp_json'],
            invoice_amount=amount, offer_amount=offer['exact_offer_total'],
            vat_amount=vat, vat_included=offer['vat_included'], work_package=invoice_package)
    except ValueError:
        raise HTTPException(409, 'Товарные строки счёта требуют сверки: нужны точные количества, '
                            'цены и суммы без НДС и неоднозначных совпадений') from None
    source = dict(requestItemsJson=offer['items_json'], offerItemsJson=offer['items_kp_json'],
                  offerTotal=offer['exact_offer_total'], invoiceAmount=spec['amount'],
                  vatAmount='0.00', vatIncluded=False)
    return spec, source


def save_invoice_line_spec(cur, invoice_id, company_id, spec, source):
    """Append validated server-derived lines before the creating invoice commits."""
    if cur.connection.autocommit:
        raise RuntimeError('Invoice specification requires a caller-owned transaction')
    cur.execute('''INSERT INTO supplier_invoice_line_specs
        (company_id,invoice_id,row_count,amount,source_payload)
        VALUES(%s,%s,%s,%s,%s) RETURNING id''',
        (company_id, invoice_id, len(spec['lines']), spec['amount'], Json(source)))
    spec_id = cur.fetchone()['id']
    for line in spec['lines']:
        cur.execute('''INSERT INTO supplier_invoice_lines
            (spec_id,company_id,line_no,source_request_position,source_offer_position,
             material_name,unit,work_package,quantity,unit_price,amount)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (spec_id, company_id, line['lineNo'], line['sourceRequestPosition'], line['sourceOfferPosition'],
             line['materialName'], line['unit'], line['workPackage'], line['quantity'],
             line['unitPrice'], line['amount']))
    return spec_id
