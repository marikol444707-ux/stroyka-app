"""Add privacy-minimal daily page-view aggregates for the public site."""

from alembic import op


revision = "0107_public_site_analytics"
down_revision = "0106_site_lead_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public_site_page_views (
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            view_date DATE NOT NULL,
            page_path VARCHAR(80) NOT NULL,
            utm_source VARCHAR(80) NOT NULL DEFAULT '',
            utm_medium VARCHAR(80) NOT NULL DEFAULT '',
            utm_campaign VARCHAR(120) NOT NULL DEFAULT '',
            view_count BIGINT NOT NULL DEFAULT 0 CHECK (view_count >= 0),
            PRIMARY KEY (company_id, view_date, page_path, utm_source, utm_medium, utm_campaign)
        )
    """)
    op.execute("""
        CREATE INDEX idx_public_site_page_views_company_date
        ON public_site_page_views (company_id, view_date DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public_site_page_views")
