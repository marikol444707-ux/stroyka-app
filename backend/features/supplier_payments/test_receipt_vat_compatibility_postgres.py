"""Legacy allocation invariants must survive the VAT schema upgrade."""
from . import test_settlement_compatibility_postgres as legacy
from .test_cancellations_postgres import migration


class VatMigrationCompatibilityTests(legacy.SettlementMigrationCompatibilityTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0056_supplier_receipt_vat.py')
        finally: conn.close()
