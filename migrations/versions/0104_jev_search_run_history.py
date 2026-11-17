"""Persist company-scoped JEV search outcomes."""

from alembic import op


revision = "0104_jev_search_run_history"
down_revision = "0103_platform_company_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.crm_job_candidate_search_runs (
            id BIGSERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
            run_id UUID NOT NULL,
            region VARCHAR(255) NOT NULL DEFAULT '',
            received_count INTEGER NOT NULL DEFAULT 0 CHECK (received_count >= 0),
            created_count INTEGER NOT NULL DEFAULT 0 CHECK (created_count >= 0),
            updated_count INTEGER NOT NULL DEFAULT 0 CHECK (updated_count >= 0),
            sources_checked INTEGER NOT NULL DEFAULT 0 CHECK (sources_checked >= 0),
            sources_unavailable INTEGER NOT NULL DEFAULT 0 CHECK (sources_unavailable >= 0),
            sources JSONB NOT NULL DEFAULT '[]'::jsonb,
            finished_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_crm_job_candidate_search_runs_company_run UNIQUE(company_id, run_id),
            CONSTRAINT chk_crm_job_candidate_search_runs_sources_array CHECK (jsonb_typeof(sources)='array')
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_crm_job_candidate_search_runs_company_finished
        ON public.crm_job_candidate_search_runs(company_id, finished_at DESC, id DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.crm_job_candidate_search_runs")
