"""Read-only validation of sealed invoice-line receipt evidence, after authority.

Legacy groups without a specification retain their zero-VAT admission. No tax
rate, invoice line or historical provenance is inferred or repaired here.
"""
from decimal import Decimal
from fastapi import HTTPException
from .receipt_tax import receipt_tax_slice


def _require(condition):
    if not condition:
        raise HTTPException(409, 'Состав, сумма или НДС приёмок требуют сверки со счётом')


def receipt_taxes(cur, invoice, relations, warehouses, deliveries):
    cur.execute("SELECT to_regclass('supplier_invoice_line_specs') IS NOT NULL AS ready")
    if not cur.fetchone()['ready']:
        _require(not invoice.get('vat_amount'))
        return {}
    cur.execute('''SELECT s.*,s.source_identity=supplier_invoice_line_identity(i) AS exact_identity
        FROM supplier_invoice_line_specs s JOIN supplier_invoices i ON i.id=s.invoice_id
        WHERE s.invoice_id=%s FOR SHARE OF s''', (invoice['id'],))
    spec = cur.fetchone()
    if not spec:
        _require(not invoice.get('vat_amount'))
        return {}
    _require(spec['company_id'] == invoice['company_id'] and spec['exact_identity'])
    cur.execute("SELECT to_regclass('supplier_receipt_line_proofs') IS NOT NULL AS ready")
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Не установлена схема связей строк приёмки')
    required = [(table, trigger) for table in ('supplier_invoice_line_specs','supplier_invoice_lines')
                for trigger in ('invoice_line_spec_insert','invoice_line_spec_immutable',
                                'invoice_line_spec_no_truncate','invoice_line_spec_complete')]
    required += [('supplier_receipt_line_proofs', trigger) for trigger in
                 ('receipt_line_validate','receipt_line_immutable','receipt_line_no_truncate','receipt_line_complete')]
    required += [('supplier_payment_receipt_relations','receipt_line_complete')]
    cur.execute('''SELECT NOT EXISTS(SELECT 1 FROM unnest(%s::text[],%s::text[]) r(table_name,trigger_name)
        WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=to_regclass('public.'||r.table_name)
            AND t.tgname=r.trigger_name AND t.tgenabled IN ('O','A'))) AS ready''',
        ([row[0] for row in required], [row[1] for row in required]))
    if not cur.fetchone()['ready']:
        raise HTTPException(503, 'Защита строк счёта и приёмок не подготовлена')
    cur.execute('''SELECT l.*,COALESCE((to_jsonb(l)->>'vat_amount')::numeric,0) AS tax
        FROM supplier_invoice_lines l WHERE spec_id=%s ORDER BY line_no FOR SHARE''', (spec['id'],))
    lines = {row['id']:row for row in cur.fetchall()}
    _require(len(lines) == spec['row_count'] and all(row['company_id'] == invoice['company_id'] for row in lines.values()))
    _require(sum(row['amount'] for row in lines.values()) == spec['amount'] == invoice['amount'])
    _require(sum(row['tax'] for row in lines.values()) == (invoice.get('vat_amount') or 0))
    cur.execute('''SELECT p.*,COALESCE((to_jsonb(p)->>'vat_amount')::numeric,0) AS tax
        FROM supplier_receipt_line_proofs p WHERE receipt_relation_id=ANY(%s::bigint[])
        ORDER BY receipt_relation_id FOR SHARE''', ([row['id'] for row in relations],))
    proofs = {row['receipt_relation_id']:row for row in cur.fetchall()}
    _require(set(proofs) == {row['id'] for row in relations})
    totals = {key:[Decimal(0),Decimal(0),Decimal(0)] for key in lines}
    taxes = {}
    for relation in relations:
        proof = proofs[relation['id']]
        line = lines.get(proof['invoice_line_id'])
        warehouse = warehouses.get(relation['warehouse_invoice_id'])
        _require(warehouse is not None and line is not None and proof['company_id'] == invoice['company_id'])
        delivery = deliveries.get(warehouse['supply_delivery_id'])
        _require(delivery is not None)
        _require((delivery['material_name'],delivery['unit'],delivery['work_package'] or '',delivery['price_per_unit'])
                 == (line['material_name'],line['unit'],line['work_package'],line['unit_price']))
        _require(proof['quantity'] == delivery['received_quantity'] and proof['quantity'] > 0
                 and proof['amount'] == relation['amount'] == proof['quantity'] * line['unit_price']
                 and proof['tax'] == warehouse['total_vat'] and 0 <= proof['tax'] <= proof['amount'])
        total = totals[line['id']]
        total[0] += proof['quantity']; total[1] += proof['amount']; total[2] += proof['tax']
        taxes[relation['id']] = proof['tax']
    for key, (quantity, amount, tax) in totals.items():
        line = lines[key]
        _require(quantity <= line['quantity'] and amount <= line['amount'])
        if amount:
            try:
                expected = receipt_tax_slice(line_amount=line['amount'],line_vat_amount=line['tax'],
                                             previous_amount='0',received_amount=amount)
            except ValueError:
                _require(False)
            _require(tax == Decimal(expected['vatAmount']))
    return taxes
