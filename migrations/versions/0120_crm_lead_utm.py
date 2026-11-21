"""Store the first-touch website campaign on a CRM lead.

Revision ID: 0120_crm_lead_utm
Revises: 0119_room_measurement_owners

The same columns are added at startup by CRM schema ensure and by init_db,
so a process that boots before this migration still accepts the new fields.
"""

from alembic import op


revision = "0120_crm_lead_utm"
down_revision = "0119_room_measurement_owners"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS utm_source VARCHAR(120)")
    op.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS utm_medium VARCHAR(120)")
    op.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(120)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_utm_source ON crm_leads (utm_source)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_crm_leads_utm_source")
    op.execute("ALTER TABLE crm_leads DROP COLUMN IF EXISTS utm_campaign")
    op.execute("ALTER TABLE crm_leads DROP COLUMN IF EXISTS utm_medium")
    op.execute("ALTER TABLE crm_leads DROP COLUMN IF EXISTS utm_source")
