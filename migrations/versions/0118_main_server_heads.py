"""Join the main and production-server migration branches.

Databases stamped with main's ``0102_platform_company_features`` and databases
already at the server head ``0117_invoice_template_owners`` must both reach one
head. The overlapping job-candidate and platform-feature revisions are
idempotent (``IF NOT EXISTS`` / ``ON CONFLICT DO NOTHING``), so a server
database replaying the main ids does not rebuild those tables. This revision
itself changes no schema.
"""

revision = "0118_main_server_heads"
down_revision = ("0117_invoice_template_owners", "0102_platform_company_features")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
