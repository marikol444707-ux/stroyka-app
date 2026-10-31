"""Preserve refund/credit semantics together with DATE comparison."""
from alembic import op
revision = '0105_settlement_cash_guard'
down_revision = '0104_legacy_project_owners'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE OR REPLACE FUNCTION supplier_payment_operation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE payment project_payments; original supplier_payment_operations; cash NUMERIC;
        BEGIN
        NEW.creation_xid:=pg_current_xact_id();
        IF NEW.kind='reversal' THEN
            SELECT * INTO original FROM supplier_payment_operations WHERE id=NEW.reverses_id AND company_id=NEW.company_id FOR SHARE;
            IF NOT FOUND OR original.kind NOT IN ('payment','refund','credit') OR
                (original.amount,original.payer_company_id,original.supplier_id,original.document_kind,original.document_id)
                IS DISTINCT FROM (NEW.amount,NEW.payer_company_id,NEW.supplier_id,NEW.document_kind,NEW.document_id) THEN
                RAISE EXCEPTION 'Invalid supplier operation reversal' USING ERRCODE='23514'; END IF;
        END IF;
        cash:=supplier_settlement_cash(NEW.kind,NEW.amount,original.kind);
        IF cash IS NULL THEN RAISE EXCEPTION 'Unknown settlement kind' USING ERRCODE='23514'; END IF;
        IF cash=0 THEN
            IF NEW.project_payment_id IS NOT NULL OR NEW.document_kind<>'invoice' THEN
                RAISE EXCEPTION 'Credit must not create cash' USING ERRCODE='23514'; END IF;
        ELSE
            SELECT * INTO payment FROM project_payments WHERE id=NEW.project_payment_id FOR SHARE;
            IF NOT FOUND OR (payment.company_id,payment.amount,payment.added_by,payment.date::DATE)
                IS DISTINCT FROM (NEW.company_id,cash,NEW.actor_name,NEW.payment_date) THEN
                RAISE EXCEPTION 'Supplier operation does not match cash' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END $$''')

def downgrade():
    raise RuntimeError('Do not restore a guard that rejects valid refunds')
