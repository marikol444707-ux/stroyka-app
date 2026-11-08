"""Add concurrency revisions covering every writer of an estimate row."""
from alembic import op

revision = '0107_estimate_revisions'
down_revision = '0106_site_lead_outbox'
branch_labels = None
depends_on = None

UPGRADE_SQL = """
ALTER TABLE public.estimates ADD COLUMN revision BIGINT NOT NULL DEFAULT 1
    CHECK (revision > 0);
CREATE FUNCTION public.bump_estimate_revision() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.revision := OLD.revision + 1;
    RETURN NEW;
END;
$$;
CREATE TRIGGER estimates_revision_before_update
BEFORE UPDATE ON public.estimates
FOR EACH ROW EXECUTE FUNCTION public.bump_estimate_revision();
"""
DOWNGRADE_SQL = """
DROP TRIGGER estimates_revision_before_update ON public.estimates;
DROP FUNCTION public.bump_estimate_revision();
ALTER TABLE public.estimates DROP COLUMN revision;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
