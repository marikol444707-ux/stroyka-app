"""Proof of read-only transaction behavior on a fresh guarded local database."""
import os
import unittest
from unittest.mock import patch

import psycopg2

from . import test_postgres_support as support
from backend.features.material_aliases.readiness_report import run_alias_readiness


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Explicit fresh isolated PostgreSQL opt-in required')
class AliasReadinessPostgresTests(unittest.TestCase):
    sql = support.AliasPostgresFixture.sql

    @classmethod
    def setUpClass(cls):
        support.AliasPostgresFixture.setUpClass.__func__(cls)

    def test_real_legacy_schema_classifies_collision_without_mutation(self):
        name = 'Synthetic alias collision'
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,2),(%s,3)', (name, name))
        self.sql("""INSERT INTO material_aliases(project_name,alias_name,canonical_name,active)
            VALUES(%s,'Synthetic brand','Synthetic material',TRUE)""", (name,))
        before = self.sql('SELECT * FROM material_aliases ORDER BY id')
        result = run_alias_readiness(self.main.get_db)
        self.assertTrue(result['schemaReady'] and result['scanComplete'])
        self.assertEqual(result['reasonCounts']['cross_company_name_collision'], 1)
        self.assertFalse(result['readyForCutover'])
        self.assertEqual(self.sql('SELECT * FROM material_aliases ORDER BY id'), before)

    def test_postgres_rejects_accidental_writes_in_collector(self):
        before = self.sql('SELECT * FROM material_aliases ORDER BY id')
        def attempted_write(cur, **kwargs):
            cur.execute("INSERT INTO material_aliases(alias_name,canonical_name) VALUES('must not persist','test')")
        with patch('backend.features.material_aliases.readiness_report.collect_alias_readiness', attempted_write):
            with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
                run_alias_readiness(self.main.get_db)
        self.assertEqual(self.sql('SELECT * FROM material_aliases ORDER BY id'), before)

    def test_postgres_confirms_read_only_repeatable_read(self):
        def probe(cur, **kwargs):
            cur.execute('SHOW transaction_read_only')
            self.assertEqual(cur.fetchone()['transaction_read_only'], 'on')
            cur.execute('SHOW transaction_isolation')
            self.assertEqual(cur.fetchone()['transaction_isolation'], 'repeatable read')
            return {'ok': True}
        with patch('backend.features.material_aliases.readiness_report.collect_alias_readiness', probe):
            self.assertTrue(run_alias_readiness(self.main.get_db)['rolledBack'])
