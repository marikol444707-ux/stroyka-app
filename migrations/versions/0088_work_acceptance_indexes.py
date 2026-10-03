"""Add company-leading indexes to the work-acceptance ownership chain."""

from alembic import op


revision = "0088_work_acceptance_indexes"
down_revision = "0087_work_material_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS work_acceptance_review_owner
        ON public.work_acceptance_reviews(company_id,project_id,journal_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_rework_link_owner
        ON public.work_rework_links(company_id,journal_id,review_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_rework_submission_owner
        ON public.work_rework_submissions(company_id,journal_id,operation_id)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.work_rework_submission_owner")
    op.execute("DROP INDEX IF EXISTS public.work_rework_link_owner")
    op.execute("DROP INDEX IF EXISTS public.work_acceptance_review_owner")
