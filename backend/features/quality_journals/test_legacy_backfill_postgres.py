"""Real legacy backfill regression; requires a fresh isolated fixture database."""
import os
import unittest


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Requires an explicitly provisioned empty PostgreSQL database')
class LegacyBackfillPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        cls.main, _, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)

    def check_history(self, function_name, table, quantity_column, filtered):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                # All mutations are rolled back, including legacy runtime DDL.
                for source in ('supply_deliveries', 'warehouse_invoices', 'materials',
                               'warehouse_history', 'material_inspection_journal', 'cable_journal'):
                    cur.execute('DELETE FROM ' + source)
                expected = []
                for project, kind, quantity in (
                    ('Backfill A', 'приход', 2),
                    ('Backfill A', 'приход: поставка', 3),
                    ('Backfill B', 'приход', 4),
                    ('Backfill A', 'расход', 5),
                    ('Backfill A', 'приход', 0),
                    ('Backfill A', 'приход', -1),
                    ('Основной склад', 'приход', 6),
                    ('', 'приход', 7),
                ):
                    cur.execute('''INSERT INTO warehouse_history
                        (material,quantity,unit,date,project,type,issued_by,work_package)
                        VALUES (%s,%s,'м','2026-09-16',%s,%s,'Regression','Основная')
                        RETURNING id''', ('ВВГнг 3х2,5', quantity, project, kind))
                    history_id = cur.fetchone()[0]
                    if (project in ('Backfill A', 'Backfill B') and quantity > 0
                            and kind.startswith('приход')
                            and (not filtered or project == 'Backfill A')):
                        expected.append((history_id, project, quantity))
                backfill = getattr(self.main, function_name)
                projects = ['Backfill A'] if filtered else None
                self.assertEqual(backfill(cur, projects), len(expected))
                query = ('SELECT warehouse_history_id,project_name,' + quantity_column
                         + ' FROM ' + table + ' ORDER BY warehouse_history_id')
                cur.execute(query)
                self.assertEqual(cur.fetchall(), expected)
                self.assertEqual(backfill(cur, projects), 0)
                cur.execute(query)
                self.assertEqual(cur.fetchall(), expected)
        finally:
            conn.rollback()
            conn.close()

    def test_inspection_filtered_history(self):
        self.check_history('_backfill_material_inspection_journal',
                           'material_inspection_journal', 'quantity', True)

    def test_inspection_unfiltered_history(self):
        self.check_history('_backfill_material_inspection_journal',
                           'material_inspection_journal', 'quantity', False)

    def test_cable_filtered_history(self):
        self.check_history('_backfill_cable_journal', 'cable_journal', 'length_received', True)

    def test_cable_unfiltered_history(self):
        self.check_history('_backfill_cable_journal', 'cable_journal', 'length_received', False)

    def check_custom_units(self, stock_backfill):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                project = 'Custom unit regression'
                units = ('уп 100м', 'уп 50 шт', 'уп 100 шт')
                inspected_quantity = 1 if stock_backfill else 2
                for unit in units:
                    args = dict(project=project, material_name='Regression material',
                                qty=inspected_quantity, unit=unit, source_type='project_stock')
                    self.assertTrue(self.main._ensure_material_inspection_row(cur, **args))
                    if stock_backfill:
                        cur.execute('''INSERT INTO materials(name,quantity,unit,project,work_package)
                            VALUES ('Regression material',2,%s,%s,'Основная')''', (unit, project))
                    else:
                        self.assertFalse(self.main._ensure_material_inspection_row(cur, **args))
                if stock_backfill:
                    self.assertEqual(self.main._backfill_material_inspection_journal(cur, [project]), 0)
                cur.execute('''SELECT unit,quantity FROM material_inspection_journal
                    WHERE project_name=%s ORDER BY unit''', (project,))
                self.assertEqual(cur.fetchall(), sorted((unit, inspected_quantity) for unit in units))
        finally:
            conn.rollback()
            conn.close()

    def test_custom_unit_ensure_is_idempotent(self):
        self.check_custom_units(False)

    def test_custom_unit_stock_backfill_is_idempotent(self):
        self.check_custom_units(True)
