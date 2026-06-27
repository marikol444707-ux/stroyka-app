"""Add operational error logging tables.

Revision ID: 0002_ops_error_logging
Revises: 0001_baseline
Create Date: 2026-06-27
"""

from alembic import op


revision = "0002_ops_error_logging"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_errors (
            id SERIAL PRIMARY KEY,
            method VARCHAR(20),
            path TEXT,
            status_code INT DEFAULT 500,
            error_type VARCHAR(255),
            error_message TEXT,
            user_id INT,
            user_name VARCHAR(255),
            user_role VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_errors_created_at
        ON api_errors(created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_errors_created_at")
    op.execute("DROP TABLE IF EXISTS api_errors")
