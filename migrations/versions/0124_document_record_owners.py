"""Store a document version's company from its hidden-work act.

A project document or letter that does not already store a company stays
blank. A name is not ownership. A version copies the company already saved
on its hidden-work act.
"""
import json

from alembic import op

from backend.features.document_owners.company_backfill import (
    ADD_COLUMNS_SQL,
    apply_document_owners,
    dbapi_cursor,
)

revision = "0124_document_record_owners"
down_revision = "0123_explicit_company_owner"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(ADD_COLUMNS_SQL)
    cursor = dbapi_cursor(op.get_bind())
    try:
        plan = apply_document_owners(cursor, write=True)
    finally:
        cursor.close()
    print("DOCUMENT_RECORD_OWNER_BACKFILL " + json.dumps({
        "write": True,
        "applied": plan["applied"],
        "legacyCompanyId": plan["legacyCompanyId"],
        "counts": plan["counts"],
    }, ensure_ascii=False))


def downgrade():
    raise RuntimeError("Document company ownership must not be discarded")
