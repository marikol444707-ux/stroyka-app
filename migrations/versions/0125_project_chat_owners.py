"""Store the company on project chat rows that name one project.

A chat that already has a company keeps it. A name that matches exactly one
owned project receives that company. A shared name stays blank.
"""
import json

from alembic import op

from backend.features.explicit_company.company_backfill import dbapi_cursor
from backend.features.project_chat.company_backfill import plan_chat_owners

revision = "0125_project_chat_owners"
down_revision = "0124_document_record_owners"
branch_labels = None
depends_on = None

ADD_COLUMN_SQL = """
ALTER TABLE project_chat ADD COLUMN IF NOT EXISTS company_id INTEGER;
"""


def upgrade():
    op.execute(ADD_COLUMN_SQL)
    plan = {"assignments": [], "unknown": 0, "alreadyOwned": 0}
    cursor = dbapi_cursor(op.get_bind())
    try:
        cursor.execute("SELECT id, company_id, name FROM projects ORDER BY id")
        projects = []
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                projects.append(row)
            else:
                projects.append({"id": row[0], "company_id": row[1], "name": row[2]})
        cursor.execute("SELECT id, company_id, project_name FROM project_chat ORDER BY id")
        messages = []
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                messages.append(row)
            else:
                messages.append({"id": row[0], "company_id": row[1], "project_name": row[2]})
        plan = plan_chat_owners(projects, messages)
        for item in plan["assignments"]:
            cursor.execute(
                "UPDATE project_chat SET company_id=%s WHERE id=%s AND company_id IS NULL",
                (item["company_id"], item["id"]),
            )
    finally:
        cursor.close()
    print("PROJECT_CHAT_OWNER_BACKFILL " + json.dumps({
        "applied": len(plan["assignments"]),
        "unknown": plan["unknown"],
        "alreadyOwned": plan["alreadyOwned"],
    }, ensure_ascii=False))


def downgrade():
    raise RuntimeError("Project chat company ownership must not be discarded")
