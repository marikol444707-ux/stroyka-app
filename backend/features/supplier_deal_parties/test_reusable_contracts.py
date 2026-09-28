import copy
import unittest
from unittest.mock import Mock
from fastapi import HTTPException
from .reusable_contracts import reusable_contracts


class ReusableContractsTests(unittest.TestCase):
    def setUp(self):
        self.identities = {'buyer': {'companyId': 1, 'inn': '111'},
                           'payer': {'companyId': 1, 'inn': '111'},
                           'supplier': {'supplierId': 2, 'inn': '222'}}
        self.row = dict(id=7, offer_id=8, company_id=1, version=2,
                        source_file_id=9, snapshot_hash='hash',
                        snapshot_json=copy.deepcopy(self.identities))
        self.cur = Mock()
        self.access = Mock()

    def run_rows(self, rows):
        self.cur.fetchall.return_value = rows
        return reusable_contracts(self.cur, {'id': 10, 'company_id': 1, 'supplier_id': 2},
                                  self.identities, self.access, {'id': 3}, '1', 'company')

    def test_reuses_original_and_checks_source_access(self):
        result = self.run_rows([self.row, self.row])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['sourceFileId'], 9)
        self.access.assert_called_with(self.cur, 8, {'id': 3}, 'read', '1', 'company')
        sql, params = self.cur.execute.call_args.args
        self.assertEqual(params, (1, 2, 10))
        self.assertIn('f.project_id IS NULL', sql)
        self.assertIn('newer.version>c.version', sql)

    def test_different_party_or_inn_never_reused(self):
        for side, field in [('buyer','companyId'), ('payer','companyId'),
                            ('supplier','supplierId'), ('supplier','inn')]:
            row = copy.deepcopy(self.row)
            row['snapshot_json'][side][field] = 'other'
            self.assertEqual(self.run_rows([row]), [])

    def test_source_access_denied(self):
        self.access.side_effect = HTTPException(403, 'denied')
        self.assertEqual(self.run_rows([self.row]), [])

    def test_deal_schedule_not_silently_dropped(self):
        self.row['snapshot_json']['paymentSchedule'] = {'items': [1]}
        self.assertEqual(self.run_rows([self.row]), [])

    def test_unexpected_access_error_propagates(self):
        self.access.side_effect = HTTPException(500, 'failed')
        with self.assertRaises(HTTPException):
            self.run_rows([self.row])
