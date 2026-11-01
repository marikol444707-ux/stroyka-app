"""No SQL execution: pure text and inert module checks."""
import unittest
from backend.bootstrap_schema import (LEGACY_STEPS, LEGACY_SCHEMA_BATCH,
    SCHEMA_STATEMENTS, SEED_STATEMENTS, REPAIR_STATEMENTS)
from scripts.qa_sql_inventory import split_statements, leading_keyword


class InventoryTests(unittest.TestCase):
    def test_lossless_statement_boundaries(self):
        self.assertEqual(split_statements(LEGACY_SCHEMA_BATCH), [s for k, s in LEGACY_STEPS])
        self.assertEqual((len(SCHEMA_STATEMENTS), len(SEED_STATEMENTS), len(REPAIR_STATEMENTS)), (735, 2, 24))

    def test_complex_statements_reviewed(self):
        for index in (109, 241, 349, 377):
            kind, sql = LEGACY_STEPS[index]
            self.assertEqual(kind, 'schema')
            self.assertEqual(leading_keyword(sql), 'DO')
            self.assertIn('ADD CONSTRAINT', sql)
        for index in (180, 183, 242, 381, 567):
            self.assertEqual(LEGACY_STEPS[index][0], 'repair')
        self.assertTrue(all('VALUES (1,' in s for s in SEED_STATEMENTS))
        self.assertIn('FROM users u', LEGACY_STEPS[242][1])

    def test_dml_never_in_schema_category(self):
        self.assertTrue(all(leading_keyword(s) in ('CREATE', 'ALTER', 'DO') for s in SCHEMA_STATEMENTS))
        self.assertTrue(all(leading_keyword(s) in ('UPDATE', 'SELECT', 'INSERT', 'WITH') for s in REPAIR_STATEMENTS))

    def test_quotes_comments_and_dollar_bodies(self):
        sql = "-- x;\nSELECT 'a;''b'; DO $tag$ BEGIN PERFORM 1; END $tag$; /* a /* ; */ b */ SELECT \"x;y\";\n"
        parts = split_statements(sql)
        self.assertEqual(len(parts), 3)
        self.assertEqual(''.join(parts), sql)

    def test_unreviewed_lexical_forms_rejected(self):
        for sql in ("SELECT 'x", 'SELECT 1', 'DO $$x;', '/* x', "SELECT E'a\\b';"):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                split_statements(sql)


if __name__ == '__main__':
    unittest.main()
