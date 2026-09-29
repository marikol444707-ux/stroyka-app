"""Existing receipt allocations remain valid after the settlement migration."""
from . import test_receipt_exceptions_migration_postgres as legacy
from .test_cancellations_postgres import migration


class SettlementMigrationCompatibilityTests(legacy.ExceptionMigrationCompatibilityTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0055_supplier_settlements.py')
        finally:
            conn.close()
