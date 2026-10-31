"""Track inactivity for leads originating from the public website.

Revision ID: 0007_public_site_lead_retention
Revises: 0006_user_company_staff_links
"""

from alembic import op


revision = "0007_public_site_lead_retention"
down_revision = "0006_user_company_staff_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS public_site_origin BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS privacy_last_activity_at TIMESTAMPTZ")
    op.execute("UPDATE crm_leads SET privacy_last_activity_at=NOW() WHERE privacy_last_activity_at IS NULL")
    op.execute("""
        CREATE OR REPLACE FUNCTION touch_crm_lead_privacy_activity() RETURNS trigger AS $$
        BEGIN
            IF TG_TABLE_NAME = 'crm_leads' THEN
                IF OLD IS DISTINCT FROM NEW THEN
                    NEW.privacy_last_activity_at := NOW();
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                UPDATE crm_leads SET privacy_last_activity_at=NOW() WHERE id=OLD.lead_id;
                RETURN OLD;
            END IF;
            UPDATE crm_leads SET privacy_last_activity_at=NOW() WHERE id=NEW.lead_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_crm_leads_privacy_activity ON crm_leads;
        CREATE TRIGGER trg_crm_leads_privacy_activity
        BEFORE UPDATE ON crm_leads FOR EACH ROW EXECUTE FUNCTION touch_crm_lead_privacy_activity()
    """)
    for table in ("crm_lead_documents", "crm_lead_tasks"):
        op.execute(f"""
            DROP TRIGGER IF EXISTS trg_{table}_privacy_activity ON {table};
            CREATE TRIGGER trg_{table}_privacy_activity
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION touch_crm_lead_privacy_activity()
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_crm_leads_privacy_activity ON crm_leads")
    for table in ("crm_lead_documents", "crm_lead_tasks"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_privacy_activity ON {table}")
    op.execute("DROP FUNCTION IF EXISTS touch_crm_lead_privacy_activity()")
    op.execute("ALTER TABLE crm_leads DROP COLUMN IF EXISTS privacy_last_activity_at")
    op.execute("ALTER TABLE crm_leads DROP COLUMN IF EXISTS public_site_origin")
