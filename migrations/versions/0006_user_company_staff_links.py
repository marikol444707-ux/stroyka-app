"""Link company memberships to their exact staff records.

Revision ID: 0006_user_company_staff_links
Revises: 0005_platform_client_contracts
Create Date: 2026-09-04
"""

from alembic import op


revision = "0006_user_company_staff_links"
down_revision = "0005_platform_client_contracts"
branch_labels = None
depends_on = None


_ADD_STAFF_LINK = """
ALTER TABLE public.user_company_roles
ADD COLUMN IF NOT EXISTS staff_id INTEGER
"""

_ADD_INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_company_id
ON public.staff (company_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_company_roles_active_staff
ON public.user_company_roles (company_id, staff_id)
WHERE staff_id IS NOT NULL AND COALESCE(active, TRUE) IS TRUE
"""

_ADD_FOREIGN_KEY = """
DO $user_company_staff_link$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_user_company_roles_company_staff'
      AND conrelid='public.user_company_roles'::regclass
) THEN
    ALTER TABLE public.user_company_roles
    ADD CONSTRAINT fk_user_company_roles_company_staff
    FOREIGN KEY (company_id, staff_id)
    REFERENCES public.staff(company_id, id);
END IF;
END $user_company_staff_link$
"""

_DOWNGRADE_GUARD = """
DO $user_company_staff_link_downgrade$ BEGIN
IF EXISTS (
    SELECT 1 FROM public.user_company_roles
    WHERE staff_id IS NOT NULL
    LIMIT 1
) THEN
    RAISE EXCEPTION 'user_company_roles.staff_id contains business links';
END IF;
END $user_company_staff_link_downgrade$
"""


def upgrade() -> None:
    op.execute(_ADD_STAFF_LINK)
    op.execute(_ADD_INDEXES)
    op.execute(_ADD_FOREIGN_KEY)


def downgrade() -> None:
    op.execute(_DOWNGRADE_GUARD)
    op.execute(
        "ALTER TABLE public.user_company_roles "
        "DROP CONSTRAINT IF EXISTS fk_user_company_roles_company_staff"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.uq_user_company_roles_active_staff"
    )
    op.execute(
        "ALTER TABLE public.user_company_roles DROP COLUMN IF EXISTS staff_id"
    )
    op.execute("DROP INDEX IF EXISTS public.uq_staff_company_id")
