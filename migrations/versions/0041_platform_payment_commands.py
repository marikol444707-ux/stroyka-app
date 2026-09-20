"""Replay-safe manual platform payments; historical rows are left unchanged."""
from alembic import op

revision = '0041_platform_payment_commands'
down_revision = '0040_customer_record_owners'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
ALTER TABLE company_payments ADD COLUMN command_id UUID;
ALTER TABLE company_payments ADD COLUMN command_fingerprint VARCHAR(64);
ALTER TABLE company_payments ADD CONSTRAINT company_payment_command_pair CHECK (
    (command_id IS NULL AND command_fingerprint IS NULL) OR
    (command_id IS NOT NULL AND command_fingerprint IS NOT NULL AND command_fingerprint ~ '^[0-9a-f]{64}$')
);
CREATE UNIQUE INDEX company_payment_command_uidx ON company_payments(command_id)
    WHERE command_id IS NOT NULL;
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM company_payments WHERE command_id IS NOT NULL)
        THEN RAISE EXCEPTION 'Payment command history must be preserved'; END IF; END $$;
        DROP INDEX company_payment_command_uidx;
        ALTER TABLE company_payments DROP CONSTRAINT company_payment_command_pair;
        ALTER TABLE company_payments DROP COLUMN command_fingerprint;
        ALTER TABLE company_payments DROP COLUMN command_id;""")
