"""Enforce supplier transaction keys for packaging SQL writers; retain all rows."""
from types import SimpleNamespace

from alembic import op
from backend.features.material_packaging.history_lock_schema import GUARD_SQL, DROP_GUARD_SQL
from backend.features.material_packaging.schema import ensure_packaging_schema

revision = '0100_packaging_history_guard'
down_revision = '0099_supplier_corrections'
branch_labels = None
depends_on = None


def upgrade():
    # Packaging tables were previously lazy-bootstrapped by their first API use.
    ensure_packaging_schema(SimpleNamespace(execute=op.execute))
    op.execute('LOCK TABLE public.material_packaging_rules IN SHARE ROW EXCLUSIVE MODE')
    op.execute(GUARD_SQL)


def downgrade():
    # Removing this guard must never remove or rewrite business history.
    op.execute('LOCK TABLE public.material_packaging_rules IN SHARE ROW EXCLUSIVE MODE')
    op.execute(DROP_GUARD_SQL)
