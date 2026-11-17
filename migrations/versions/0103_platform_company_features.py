"""Add company-scoped platform feature subscriptions for JEV opportunities."""

from alembic import op


revision = "0103_platform_company_features"
down_revision = "0102_job_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.platform_company_features (
            id BIGSERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
            feature_code VARCHAR(60) NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            monthly_fee NUMERIC(12,2) NOT NULL DEFAULT 0,
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            changed_by VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_platform_company_features_company_code UNIQUE(company_id, feature_code),
            CONSTRAINT chk_platform_company_features_code CHECK (feature_code IN ('jev_procurement')),
            CONSTRAINT chk_platform_company_features_fee CHECK (
                monthly_fee >= 0
                AND monthly_fee NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
            )
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_platform_company_features_enabled
        ON public.platform_company_features(feature_code, enabled, company_id)
    """)
    # Preserve the already configured single-company JEV intake during rollout.
    op.execute("""
        INSERT INTO public.platform_company_features
            (company_id, feature_code, enabled, monthly_fee, settings, changed_by)
        SELECT id, 'jev_procurement', TRUE, 0, '{"region":"Ставропольский край"}'::jsonb, 'migration'
        FROM public.companies WHERE id=1
        ON CONFLICT (company_id, feature_code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.platform_company_features")
