"""Company owners for tools, tool history and inventory.

A row that already has a company keeps it. A row without one is given to the
only operating company, or to the one project whose name matches exactly.
A person's name is not used. When two companies already have projects, a row
that still cannot be tied to one of them stays unowned and hidden.
"""
import json

from alembic import op

from backend.features.inventory_ownership.company_backfill import (
    ADD_COLUMNS_SQL,
    CONSTRAINTS_SQL,
    apply_backfill,
    dbapi_cursor,
)

revision = "0121_tool_inventory_owners"
down_revision = "0120_crm_lead_utm"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(ADD_COLUMNS_SQL)
    cursor = dbapi_cursor(op.get_bind())
    try:
        plan = apply_backfill(cursor, write=True)
    finally:
        cursor.close()
    print("TOOL_INVENTORY_OWNERSHIP_BACKFILL " + json.dumps({
        "write": True,
        "applied": plan["applied"],
        "counts": plan["counts"],
    }, ensure_ascii=False))
    op.execute(CONSTRAINTS_SQL)


def downgrade():
    raise RuntimeError("Verified tool and inventory ownership must not be discarded")
