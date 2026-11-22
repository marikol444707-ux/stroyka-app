"""Stop new rows from landing in company 1 by default.

A row that already has a company keeps it. A row without one is given to the
only operating company, or to the one project whose name matches exactly.
A person's name is not used. When two companies already have projects, a row
that still cannot be tied to one of them stays unowned and hidden.
"""
import json

from alembic import op

from backend.features.explicit_company.company_backfill import (
    DROP_DEFAULTS_SQL,
    apply_backfill,
    dbapi_cursor,
)

revision = "0123_explicit_company_owner"
down_revision = "0122_field_record_owners"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DROP_DEFAULTS_SQL)
    cursor = dbapi_cursor(op.get_bind())
    try:
        plan = apply_backfill(cursor, write=True)
    finally:
        cursor.close()
    print("EXPLICIT_COMPANY_OWNER_BACKFILL " + json.dumps({
        "write": True,
        "applied": plan["applied"],
        "legacyCompanyId": plan["legacyCompanyId"],
        "counts": plan["counts"],
    }, ensure_ascii=False))


def downgrade():
    raise RuntimeError("Explicit company ownership must not be discarded")
