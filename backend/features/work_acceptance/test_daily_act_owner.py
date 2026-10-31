"""Pure unit checks of daily-act command parameters; no database or HTTP."""
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock
from .daily_acts import sync_daily


class DailyActOwnerTests(TestCase):
    def setUp(self):
        self.work = dict(room_name='Room', company_id=2, project='Object',
                         work_package='Package', date='2026-10-31', master_id=7, master_name='Worker')
        self.project = dict(id=11, companyId=2)
        self.rows = [dict(id=23, execution_total='12.30', photo_url='')]

    def run_sync(self, acts=(), rows=None):
        cur = Mock()
        cur.fetchall.side_effect = [list(acts), self.rows if rows is None else rows]
        sync_daily(cur, self.work, self.project, {'Подписан'})
        return cur.execute.call_args_list

    def test_new_act_preserves_exact_owner_and_work_amount(self):
        calls = self.run_sync()
        query, scope = calls[0].args
        self.assertIn('company_id=%s AND project_id=%s AND project=%s', query)
        self.assertEqual(scope, (2, 11, 'Object', 'Package', '2026-10-31', '2026-10-31', 7))
        sql, values = calls[-1].args
        self.assertIn('INSERT INTO interim_acts(company_id,project_id,master_id', sql)
        self.assertEqual(values[:8], (2, 11, 7, 'Worker', 'Object', 'Package', '2026-10-31', '2026-10-31'))
        self.assertEqual(values[8:], (Decimal('12.30'), '[23]', '[]'))
        self.assertEqual(sql.count('%s'), len(values))

    def test_existing_owned_draft_is_updated_instead_of_duplicate(self):
        calls = self.run_sync([dict(id=31, status='Новый')])
        self.assertTrue(calls[-1].args[0].startswith('UPDATE interim_acts'))
        self.assertEqual(calls[-1].args[1], (Decimal('12.30'), '[23]', '[]', 31))
        self.assertEqual(calls[1].args[1][-1], 31)

    def test_signed_act_is_not_rewritten(self):
        calls = self.run_sync([dict(id=30, status='Подписан')])
        self.assertTrue(calls[-1].args[0].startswith('INSERT INTO interim_acts'))
        self.assertEqual(calls[1].args[1][-1], 0)

    def test_no_eligible_work_does_not_write_or_backfill_legacy_owner(self):
        calls = self.run_sync(rows=[])
        self.assertEqual(len(calls), 2)

    def test_same_name_different_project_is_a_distinct_draft_scope(self):
        first = self.run_sync()[0].args[1]
        self.project = dict(id=12, companyId=2)
        second = self.run_sync()[0].args[1]
        self.assertEqual(first[:1] + first[2:], second[:1] + second[2:])
        self.assertNotEqual(first[1], second[1])
