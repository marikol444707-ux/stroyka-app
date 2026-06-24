"""Baseline for the existing inline init_db schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-24
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Existing tables are still created by backend.main.init_db()."""
    pass


def downgrade() -> None:
    """The baseline is metadata-only and has no downgrade SQL."""
    pass
