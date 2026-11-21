"""Company owners for tools, tool history and inventory.

An unambiguous project name is copied from projects. A blank project can use
the creator when that person's active memberships all belong to one company.
A name shared by two companies, an unknown name, or a creator from another
company stays NULL. Company users cannot see those rows.
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
        "ambiguousNames": plan["ambiguousNames"],
        "counts": plan["counts"],
    }, ensure_ascii=False))
    op.execute(CONSTRAINTS_SQL)


def downgrade():
    raise RuntimeError("Verified tool and inventory ownership must not be discarded")
