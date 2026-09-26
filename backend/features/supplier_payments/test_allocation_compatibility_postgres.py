"""Run the existing financial engine regressions with allocation schema present.

No allocation groups are registered here: installing the additive schema must
not require existing invoice/warehouse workflows to adopt the new mode.
"""
from . import test_engine_postgres as engine_tests
from . import test_cancellations_postgres as migration_tests


class AllocationCompatibilityTests(engine_tests.LedgerTests):
    def seed_warehouse(self):
        warehouse = super().seed_warehouse()
        # 0019 already requires an explicit item package; the older fixture
        # used NULL items. Do not weaken the production package validator.
        self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                 ('[{"workPackage":""}]', warehouse))
        return warehouse

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                # The old engine fixture predates these persisted provenance
                # columns; supply the current synthetic shape, not runtime DDL.
                cur.execute('ALTER TABLE supply_deliveries ADD COLUMN IF NOT EXISTS source_supplier_invoice_id INTEGER')
                for table in ('supplier_invoices', 'supply_deliveries'):
                    cur.execute('ALTER TABLE ' + table + ' ADD COLUMN IF NOT EXISTS contract_version_id INTEGER')
                for filename in ('0046_supplier_payment_attachments.py',
                                 '0047_supplier_payment_packages.py',
                                 '0048_supplier_payment_cancellations.py',
                                 '0049_supplier_payment_allocations.py'):
                    migration_tests.migration(cur, filename)
        finally:
            conn.close()
