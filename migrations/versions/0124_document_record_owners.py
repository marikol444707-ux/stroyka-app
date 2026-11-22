"""Store the owner company on blank registry documents.

A document that already has a company keeps it. A blank project document or
letter is filled only when one project owns that name, or when the install
has one operating company and exactly one project. A version takes the
company already stored on its hidden-work act. A person's name is not used.
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
