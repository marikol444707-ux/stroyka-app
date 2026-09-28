"""Existing HTTP settlements on the complete 0055–0059 schema chain."""
from .test_settlements_postgres import SettlementTests
from .test_cancellations_postgres import migration


class RefundSchemaCompatibilityTests(SettlementTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                for name in ('0056_supplier_receipt_vat.py', '0057_supplier_opening_confirmations.py',
                             '0058_supplier_paired_openings.py','0059_supplier_refund_allocations.py'):
                    migration(cur,name)
        finally: conn.close()
