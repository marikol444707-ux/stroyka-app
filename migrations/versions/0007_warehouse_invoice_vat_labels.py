"""Repair legacy boolean VAT columns without inventing a tax rate.

Revision ID: 0007_warehouse_vat_labels
Revises: 0006_user_company_staff_links

Existing TEXT/VARCHAR columns, including their defaults, are left unchanged.
Only boolean flags are translated: false -> "Без НДС", true -> "С НДС";
NULL remains NULL. Amounts and other invoice fields are not changed.

Downgrade deliberately preserves the label schema: the prior application also
writes labels, and converting back to boolean would discard business values.
"""

from alembic import op


revision = "0007_warehouse_vat_labels"
down_revision = "0006_user_company_staff_links"
branch_labels = None
depends_on = None


_REPAIR_BOOLEAN_VAT = """
DO $warehouse_invoice_vat_labels$
DECLARE
    vat_type OID;
BEGIN
    SELECT atttypid INTO vat_type
      FROM pg_catalog.pg_attribute
     WHERE attrelid=to_regclass('public.warehouse_invoices')
       AND attname='vat' AND attnum > 0 AND NOT attisdropped;

    IF vat_type='pg_catalog.bool'::regtype THEN
        ALTER TABLE public.warehouse_invoices ALTER COLUMN vat DROP DEFAULT;
        ALTER TABLE public.warehouse_invoices ALTER COLUMN vat TYPE TEXT
            USING CASE
                WHEN vat IS TRUE THEN 'С НДС'
                WHEN vat IS FALSE THEN 'Без НДС'
                ELSE NULL
            END;
        ALTER TABLE public.warehouse_invoices ALTER COLUMN vat SET DEFAULT 'Без НДС';
    ELSIF vat_type IN ('pg_catalog.text'::regtype, 'pg_catalog.varchar'::regtype) THEN
        NULL;
    ELSE
        RAISE EXCEPTION 'Unsupported or missing public.warehouse_invoices.vat type: %',
            vat_type::regtype;
    END IF;
END $warehouse_invoice_vat_labels$
"""


def upgrade() -> None:
    op.execute(_REPAIR_BOOLEAN_VAT)


def downgrade() -> None:
    # A previous TEXT/VARCHAR column is indistinguishable from one repaired here.
    # Preserve labels/rates and keep older label-writing application code usable.
    pass
