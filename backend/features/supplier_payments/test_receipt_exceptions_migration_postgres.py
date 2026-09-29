"""Existing allocation invariants must remain valid after exceptional receipt support."""
import os
import unittest
from .test_receipt_line_proofs_postgres import ReceiptProofLegacyCompatibilityTests
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1','isolated PostgreSQL opt-in')
class ExceptionMigrationCompatibilityTests(ReceiptProofLegacyCompatibilityTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0053_supplier_receipt_exceptions.py')
        finally:conn.close()

    def test_empty_exception_migration_round_trip_preserves_legacy_groups(self):
        conn=self.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0053_supplier_receipt_exceptions.py','downgrade')
                migration(cur,'0053_supplier_receipt_exceptions.py')
        finally:conn.close()

    def test_missing_acceptance_status_or_quality_never_becomes_a_payable_receipt(self):
        from unittest.mock import patch
        from psycopg2 import Error
        real_sql=self.sql
        for field in ('status','quality_status'):
            def intercepted(statement,params=()):
                if 'INSERT INTO supplier_payment_receipt_relations' in statement:
                    real_sql('UPDATE supply_deliveries SET '+field+'=NULL WHERE id=(SELECT supply_delivery_id FROM warehouse_invoices WHERE id=%s)', (params[1],))
                return real_sql(statement,params)
            with self.subTest(field=field),patch.object(self,'sql',side_effect=intercepted),self.assertRaises(Error) as error:
                self.seed_receipt('10.00')
            self.assertEqual(error.exception.pgcode,'23514')
