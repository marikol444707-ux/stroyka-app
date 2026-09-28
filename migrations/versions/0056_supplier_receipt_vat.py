"""Immutable declared line VAT and exact cumulative VAT on accepted receipts."""
from alembic import op

revision = '0056_supplier_receipt_vat'
down_revision = '0055_supplier_settlements'
branch_labels = None
depends_on = None


def _replace(signature, old, new):
    # Fail the migration rather than patching an unexpected production function.
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    op.execute(f"""DO $patch$ DECLARE body TEXT; BEGIN
        SELECT pg_get_functiondef({quote(signature)}::regprocedure) INTO body;
        IF strpos(body,{quote(old)})=0 THEN RAISE EXCEPTION 'Unexpected VAT migration source'; END IF;
        EXECUTE replace(body,{quote(old)},{quote(new)});
    END $patch$""")


FUNCTIONS = ('supplier_invoice_line_insert()', 'supplier_invoice_line_complete()',
             'supplier_allocation_receipt(bigint,integer,integer,numeric)',
             'supplier_receipt_line_validate()', 'supplier_receipt_line_complete()',
             'supplier_receipt_exception_validate()')


def upgrade():
    op.execute('CREATE TABLE supplier_vat_guard_versions(name TEXT PRIMARY KEY,definition TEXT NOT NULL)')
    for name in FUNCTIONS:
        op.execute(f"INSERT INTO supplier_vat_guard_versions VALUES('{name}',pg_get_functiondef('{name}'::regprocedure))")
    for table in ('supplier_invoice_lines','supplier_receipt_line_proofs'):
        op.execute(f'''ALTER TABLE {table} ADD COLUMN vat_amount NUMERIC NOT NULL DEFAULT 0
            CHECK(vat_amount>=0 AND vat_amount<=amount AND vat_amount=trunc(vat_amount,2))''')
    _replace('supplier_invoice_line_insert()',
             'COALESCE(i.vat_amount,0)<>0 OR NEW.amount IS DISTINCT FROM i.amount::NUMERIC',
             'COALESCE(i.vat_amount,0)<0 OR COALESCE(i.vat_amount,0)>i.amount OR NEW.amount IS DISTINCT FROM i.amount::NUMERIC')
    _replace('supplier_invoice_line_complete()',
             "IF h.row_count<>(SELECT count(*) FROM public.supplier_invoice_lines WHERE spec_id=h.id)",
             "IF COALESCE(i.vat_amount,0) IS DISTINCT FROM (SELECT sum(vat_amount) FROM public.supplier_invoice_lines WHERE spec_id=h.id) OR h.row_count<>(SELECT count(*) FROM public.supplier_invoice_lines WHERE spec_id=h.id)")
    _replace('supplier_allocation_receipt(bigint,integer,integer,numeric)',
             'OR w.total_base IS DISTINCT FROM expected OR w.total_with_vat IS DISTINCT FROM expected\n            OR w.total_vat IS DISTINCT FROM 0::NUMERIC',
             '''OR w.total_base+w.total_vat IS DISTINCT FROM expected OR w.total_with_vat IS DISTINCT FROM expected
            OR w.total_vat IS NULL OR w.total_vat<0 OR w.total_vat>expected
            OR (w.total_vat<>0 AND NOT EXISTS(SELECT 1 FROM supplier_invoice_line_specs s WHERE s.invoice_id=invoice.id AND s.company_id=cid))''')
    _replace('supplier_receipt_line_validate()',
             'IF used_qty+NEW.quantity>l.quantity OR used_amount+NEW.amount>l.amount THEN',
             '''IF NEW.vat_amount IS DISTINCT FROM round(l.vat_amount*(used_amount+NEW.amount)/l.amount,2)-round(l.vat_amount*used_amount/l.amount,2)
            OR NEW.vat_amount IS DISTINCT FROM (snap->'warehouse'->>'total_vat')::NUMERIC THEN
            RAISE EXCEPTION 'Receipt VAT does not match invoice line' USING ERRCODE='23514'; END IF;
        IF used_qty+NEW.quantity>l.quantity OR used_amount+NEW.amount>l.amount THEN''')
    _replace('supplier_receipt_line_complete()',
             """IF EXISTS(SELECT 1 FROM public.supplier_receipt_line_proofs p
            JOIN public.supplier_payment_receipt_relations r ON r.id=p.receipt_relation_id WHERE r.group_id=gid)""",
             """IF (EXISTS(SELECT 1 FROM supplier_payment_allocation_groups g
                JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
                JOIN supplier_invoices i ON i.id=d.document_id AND d.document_kind='invoice'
                WHERE g.id=gid AND i.vat_amount>0) OR EXISTS(SELECT 1 FROM public.supplier_receipt_line_proofs p
            JOIN public.supplier_payment_receipt_relations r ON r.id=p.receipt_relation_id WHERE r.group_id=gid))""")
    _replace('supplier_receipt_exception_validate()',
             'OR w.total_base IS DISTINCT FROM w.total_with_vat OR w.total_vat IS DISTINCT FROM 0::NUMERIC',
             '''OR w.total_base+w.total_vat IS DISTINCT FROM w.total_with_vat
                OR w.total_vat IS DISTINCT FROM round(l.vat_amount*w.total_with_vat/l.amount,2)''')


def downgrade():
    op.execute('LOCK TABLE supplier_invoice_lines,supplier_receipt_line_proofs IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_invoice_lines WHERE vat_amount<>0)
        OR EXISTS(SELECT 1 FROM supplier_receipt_line_proofs WHERE vat_amount<>0) THEN
        RAISE EXCEPTION 'Cannot discard VAT evidence'; END IF; END $$""")
    op.execute('DO $$ DECLARE r RECORD; BEGIN FOR r IN SELECT definition FROM supplier_vat_guard_versions LOOP EXECUTE r.definition; END LOOP; END $$')
    for table in ('supplier_invoice_lines','supplier_receipt_line_proofs'):
        op.execute(f'ALTER TABLE {table} DROP COLUMN vat_amount')
    op.execute('DROP TABLE supplier_vat_guard_versions')
