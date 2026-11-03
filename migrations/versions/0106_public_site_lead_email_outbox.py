"""Persist public-site lead email notifications and retry delivery failures.

Revision ID: 0106_public_site_lead_email_outbox
Revises: 0105_public_site_lead_retention
"""

from alembic import op


revision = "0106_public_site_lead_email_outbox"
down_revision = "0105_public_site_lead_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public_site_lead_email_outbox (
            id BIGSERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'sending', 'sent')),
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (company_id, lead_id)
        )
    """)
    op.execute("""
        CREATE INDEX idx_public_site_lead_email_outbox_due
            ON public_site_lead_email_outbox (next_attempt_at, id)
         WHERE status IN ('pending', 'sending')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public_site_lead_email_outbox")
