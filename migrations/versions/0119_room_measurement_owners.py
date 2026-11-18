"""Company and project owners for rooms and measurements.

Unambiguous project names are copied from projects. A name shared by more than
one project, or a name that matches nothing, stays NULL. Company users cannot
see those rows; platform staff can read them and cannot claim them here.
"""
import json

from alembic import op

from backend.features.room_ownership.backfill import (
    ADD_COLUMNS_SQL,
    CONSTRAINTS_SQL,
    apply_backfill,
    dbapi_cursor,
)

revision = "0119_room_measurement_owners"
down_revision = "0118_main_server_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(ADD_COLUMNS_SQL)
    cursor = dbapi_cursor(op.get_bind())
    try:
        plan = apply_backfill(cursor, write=True)
    finally:
        cursor.close()
    print("ROOM_OWNERSHIP_BACKFILL " + json.dumps({
        "write": True,
        "applied": plan["applied"],
        "ambiguousNames": plan["ambiguousNames"],
        "counts": plan["counts"],
    }, ensure_ascii=False))
    op.execute(CONSTRAINTS_SQL)


def downgrade():
    raise RuntimeError("Verified room and measurement ownership must not be discarded")
