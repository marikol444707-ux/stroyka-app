"""Company owners for tools, tool history and inventory.

The columns are added for new records. A legacy row is not given a company
from its project name or from the name of the person who created it. History
copies the owner already stored on its tool, and an inventory line copies the
owner already stored on its inventory card. Anything else stays unowned, so
company users cannot see it.
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
