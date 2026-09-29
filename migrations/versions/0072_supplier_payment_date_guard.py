"""Compare supplier payment dates using the database DATE type."""
from alembic import op


revision = '0072_payment_date_guard'
down_revision = '0071_approved_legacy_lines'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE OR REPLACE FUNCTION public.supplier_payment_operation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE payment public.project_payments; original public.supplier_payment_operations; signed_amount NUMERIC;
        BEGIN
        NEW.creation_xid := pg_current_xact_id();
        signed_amount := CASE WHEN NEW.kind='reversal' THEN -NEW.amount ELSE NEW.amount END;
        SELECT * INTO payment FROM public.project_payments WHERE id=NEW.project_payment_id FOR SHARE;
        IF NOT FOUND OR (payment.company_id,payment.amount,payment.added_by,payment.date::DATE)
            IS DISTINCT FROM (NEW.company_id,signed_amount,NEW.actor_name,NEW.payment_date) THEN
            RAISE EXCEPTION 'Supplier operation does not match project payment' USING ERRCODE='23514';
        END IF;
        IF NEW.kind='reversal' THEN
            SELECT * INTO original FROM public.supplier_payment_operations
              WHERE id=NEW.reverses_id AND company_id=NEW.company_id FOR SHARE;
            IF NOT FOUND OR original.kind<>'payment' OR
                (original.amount,original.payer_company_id,original.supplier_id,original.document_kind,original.document_id)
                IS DISTINCT FROM (NEW.amount,NEW.payer_company_id,NEW.supplier_id,NEW.document_kind,NEW.document_id) THEN
                RAISE EXCEPTION 'Invalid full supplier payment reversal' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
        END;
    $$''')


def downgrade():
    raise RuntimeError('The corrected supplier payment date guard cannot be downgraded safely')
