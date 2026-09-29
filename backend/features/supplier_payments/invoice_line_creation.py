"""New-invoice-only snapshot helpers; no authority, connections, DDL or commit.

The existing invoice creation route owns authority, source locks and transaction.
Database birth evidence rejects use on old invoices, including updated old rows.
These helpers do not register receipts or authorize partial shipment consumption.
"""
import os
from decimal import Decimal
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
    taxable = os.getenv('SUPPLIER_VAT_RECEIPTS_ENABLED') == '1' and offer['vat_included'] is True
    try:
        if taxable and ('vatAmount' not in data or data['vatAmount'] in ('',None)):
            raise ValueError('Укажите НДС явно, включая нулевую сумму')
        spec = build_invoice_line_spec(offer['items_json'], offer['items_kp_json'],
            invoice_amount=amount, offer_amount=offer['exact_offer_total'],
            vat_amount=0 if taxable else vat, vat_included=False if taxable else offer['vat_included'], work_package=invoice_package)
        if taxable:
            from .receipt_tax import invoice_tax_lines
            supplied = data.get('lineTaxes')
            if supplied is None and len(spec['lines'])==1:
                supplied=[dict(sourceOfferPosition=spec['lines'][0]['sourceOfferPosition'],vatAmount=vat)]
            if not isinstance(supplied,list) or len(supplied)!=len(spec['lines']):
                raise ValueError('Нужен НДС каждой строки')
            indexed={}
            for row in supplied:
                position=row.get('sourceOfferPosition') if isinstance(row,dict) else None
                if type(position) is not int or position in indexed or 'vatAmount' not in row:
                    raise ValueError('Не определена строка НДС')
                indexed[position]=row['vatAmount']
            if set(indexed)!={line['sourceOfferPosition'] for line in spec['lines']}:
                raise ValueError('Не совпали строки НДС')
            taxes=invoice_tax_lines([dict(lineNo=line['lineNo'],amount=line['amount'],
                vatAmount=indexed[line['sourceOfferPosition']]) for line in spec['lines']],
                invoice_amount=spec['amount'],invoice_vat_amount=vat)
            for line,tax in zip(spec['lines'],taxes):
                line['vatAmount']=tax['vatAmount']
            spec['vatAmount']=format(sum(Decimal(t['vatAmount']) for t in taxes),'.2f')
    except ValueError:
        raise HTTPException(409, 'Товарные строки счёта требуют сверки: нужны точные количества, '
                            'цены, суммы и НДС по каждой позиции без неоднозначных совпадений') from None
    source = dict(requestItemsJson=offer['items_json'], offerItemsJson=offer['items_kp_json'],
                  offerTotal=offer['exact_offer_total'], invoiceAmount=spec['amount'],
                  vatAmount=spec.get('vatAmount','0.00'), vatIncluded=taxable)
    if taxable:
        source['lineTaxes']=[dict(sourceOfferPosition=line['sourceOfferPosition'],vatAmount=line['vatAmount']) for line in spec['lines']]
    return spec, source


def save_invoice_line_spec(cur, invoice_id, company_id, spec, source):
    """Append validated server-derived lines before the creating invoice commits."""
    if cur.connection.autocommit:
        raise RuntimeError('Invoice specification requires a caller-owned transaction')
    if 'vatAmount' in spec:
        from .receipt_vat_runtime import require_vat_schema
        require_vat_schema(cur)
    cur.execute('''INSERT INTO supplier_invoice_line_specs
        (company_id,invoice_id,row_count,amount,source_payload)
        VALUES(%s,%s,%s,%s,%s) RETURNING id''',
        (company_id, invoice_id, len(spec['lines']), spec['amount'], Json(source)))
    spec_id = cur.fetchone()['id']
    for line in spec['lines']:
        tax_column=',vat_amount' if 'vatAmount' in line else ''
        tax_value=(line['vatAmount'],) if tax_column else ()
        cur.execute('''INSERT INTO supplier_invoice_lines
            (spec_id,company_id,line_no,source_request_position,source_offer_position,
             material_name,unit,work_package,quantity,unit_price,amount''' + tax_column + ''')
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s''' + (',%s' if tax_column else '') + ')',
            (spec_id, company_id, line['lineNo'], line['sourceRequestPosition'], line['sourceOfferPosition'],
             line['materialName'], line['unit'], line['workPackage'], line['quantity'],
             line['unitPrice'], line['amount']) + tax_value)
    return spec_id


def verify_existing_invoice_tax(cur, invoice_id, company_id, data):
    """A repeat must not silently accept different taxes for a sealed invoice."""
    cur.execute("SELECT to_regclass('supplier_vat_guard_versions') AS ready")
    if not cur.fetchone()['ready']:
        return
    cur.execute('''SELECT l.source_offer_position,l.line_no,l.amount,l.vat_amount,s.source_payload
        FROM supplier_invoice_lines l JOIN supplier_invoice_line_specs s ON s.id=l.spec_id
        WHERE s.invoice_id=%s AND s.company_id=%s ORDER BY l.line_no''',(invoice_id,company_id))
    rows=cur.fetchall()
    if not rows or not rows[0]['source_payload'].get('vatIncluded'):
        return
    supplied=data.get('lineTaxes')
    if supplied is None and len(rows)==1:
        supplied=[dict(sourceOfferPosition=rows[0]['source_offer_position'],vatAmount=data.get('vatAmount',0))]
    try:
        from .invoice_line_spec import _number
        if not isinstance(supplied,list) or len(supplied)!=len(rows):
            raise ValueError()
        actual={}
        for row in supplied:
            position=row.get('sourceOfferPosition')
            if type(position) is not int or position in actual:
                raise ValueError()
            actual[position]=_number(row['vatAmount'],'0.01',zero=True)
        expected={row['source_offer_position']:row['vat_amount'] for row in rows}
        if actual!=expected or _number(data.get('vatAmount',0),'0.01',zero=True)!=sum(expected.values()):
            raise ValueError()
    except (ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(409,'Счёт уже сохранён с другим НДС по строкам; повтор не изменяет документ') from None
