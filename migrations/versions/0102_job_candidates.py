"""Add company-scoped intake for externally discovered construction opportunities."""

from alembic import op


revision = "0102_job_candidates"
down_revision = "0101_manual_brigade_origins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.crm_job_candidates (
            id BIGSERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
            source VARCHAR(40) NOT NULL,
            source_name VARCHAR(100) NOT NULL DEFAULT '',
            source_item_id VARCHAR(255),
            identity_key VARCHAR(600) NOT NULL,
            url TEXT NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            published_at TIMESTAMPTZ,
            region VARCHAR(255) NOT NULL DEFAULT '',
            work_types JSONB NOT NULL DEFAULT '[]'::jsonb,
            price NUMERIC(16,2),
            deadline TIMESTAMPTZ,
            evidence TEXT NOT NULL DEFAULT '',
            status VARCHAR(32) NOT NULL DEFAULT 'Нужно проверить',
            collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by VARCHAR(255) NOT NULL DEFAULT '',
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMPTZ,
            review_note TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_crm_job_candidates_identity UNIQUE(company_id, source, identity_key),
            CONSTRAINT uq_crm_job_candidates_url UNIQUE(company_id, source, url),
            CONSTRAINT chk_crm_job_candidates_source CHECK (source IN ('eis','public_web','browser_agent','manual')),
            CONSTRAINT chk_crm_job_candidates_status CHECK (status IN ('Нужно проверить','Подходит','Не подходит','Дубль')),
            CONSTRAINT chk_crm_job_candidates_price CHECK (price IS NULL OR (price >= 0 AND price NOT IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_crm_job_candidates_company_status ON public.crm_job_candidates(company_id, status, collected_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_crm_job_candidates_company_region ON public.crm_job_candidates(company_id, region)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.crm_job_candidates")
