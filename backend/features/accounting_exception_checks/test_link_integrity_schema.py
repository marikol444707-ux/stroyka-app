import inspect
import unittest

from backend.features.accounting_exception_checks import link_integrity_schema


class AccountingLinkIntegritySchemaPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_additive_and_clears_deleted_targets(self):
        first = link_integrity_schema.build_accounting_link_integrity_schema_plan()
        second = link_integrity_schema.build_accounting_link_integrity_schema_plan()

        self.assertEqual(first, second)
        self.assertEqual(first["version"], "accounting-link-integrity-schema-v1")
        self.assertTrue(first["dryRun"])
        self.assertFalse(first["schemaReady"])
        self.assertEqual(first["changeCount"], 2)
        self.assertEqual(first["writesAttempted"], 0)
        self.assertRegex(first["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            [change["table"] for change in first["changes"]],
            ["supplier_invoices", "warehouse_invoices"],
        )

        sql = "\n".join(change["sql"] for change in first["changes"])
        self.assertIn(
            "FOREIGN KEY (warehouse_invoice_id) "
            "REFERENCES public.warehouse_invoices(id)",
            sql,
        )
        self.assertIn(
            "FOREIGN KEY (supplier_invoice_id) "
            "REFERENCES public.supplier_invoices(id)",
            sql,
        )
        self.assertEqual(sql.count("ON DELETE SET NULL"), 2)
        self.assertEqual(sql.count("DEFERRABLE INITIALLY IMMEDIATE"), 2)
        self.assertNotRegex(sql.upper(), r"\b(INSERT|UPDATE|DELETE FROM|TRUNCATE)\b")
        self.assertNotIn("DROP ", sql.upper())

    def test_contract_has_no_database_factory_registration_or_automatic_apply(self):
        source = inspect.getsource(link_integrity_schema)

        self.assertNotIn("backend.main", source)
        self.assertNotIn("get_db", source)
        self.assertNotIn("register_", source)
        self.assertNotIn("psycopg", source)
        self.assertNotIn("if __name__", source)
        self.assertNotIn("def run_", source)


if __name__ == "__main__":
    unittest.main()
