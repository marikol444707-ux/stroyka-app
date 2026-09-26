"""Projection units use locked canonical contexts; authorization is tested in PG."""
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from fastapi import HTTPException


class HistoryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.cur = Mock()
        self.row = dict(document_kind='warehouse', document_id=8, payer_company_id=3,
                        project_name='Recorded project', work_package='Recorded package')

    def test_recorded_payer_denial_precedes_physical_owner_conflict_including_lookahead(self):
        from .reads import history
        def authorize(cur, actor, company, project, package, *, payer_company_id):
            if payer_company_id == 3:
                raise HTTPException(403, 'Denied recorded payer')
        for rows in ([self.row], [dict(self.row, payer_company_id=2), self.row]):
            with self.subTest(lookahead=len(rows) == 2):
                self.cur.fetchall.return_value = rows
                self.cur.fetchone.return_value = dict(company_id=9, project='Other', package='')
                with self.assertRaises(HTTPException) as error:
                    history(self.cur, dict(authorize_read=authorize), 7, 2, limit=1)
                self.assertEqual(error.exception.status_code, 403)

    def test_raw_physical_scope_denial_precedes_warehouse_package_parsing(self):
        from .reads import history
        from psycopg2.errors import CheckViolation
        self.cur.fetchall.return_value = [self.row]
        self.cur.fetchone.return_value = dict(company_id=2, project='Denied project', items='invalid')
        def execute(sql, *args):
            if 'supplier_payment_warehouse_package' in sql:
                raise CheckViolation('Malformed persisted items must not leak')
        self.cur.execute.side_effect = execute
        def authorize(cur, actor, company, project, package, *, payer_company_id):
            if project == 'Denied project':
                raise HTTPException(403, 'Denied physical project')
        with self.assertRaises(HTTPException) as error:
            history(self.cur, dict(authorize_read=authorize), 7, 2, limit=1)
        self.assertEqual(error.exception.status_code, 403)

    def test_recorded_scope_denial_precedes_corruption_on_uuid_attachment_lookup(self):
        from .reads import history
        self.cur.fetchall.return_value = []
        self.cur.fetchone.side_effect = [self.row, dict(company_id=9, project='Other', package='')]
        def authorize(cur, actor, company, project, package, *, payer_company_id):
            if project == 'Recorded project':
                raise HTTPException(403, 'Denied recorded project')
        with self.assertRaises(HTTPException) as error:
            history(self.cur, dict(authorize_read=authorize), 7, 2, limit=1, request_id='lookup')
        self.assertEqual(error.exception.status_code, 403)


class DocumentProjectionTests(unittest.TestCase):
    def setUp(self):
        self.doc = dict(kind='invoice', id=8, companyId=2, payerCompanyId=2, supplierId=3,
                        projectName='Exact project', workPackage='', amount=Decimal('200'),
                        paidAmount=Decimal('20'))
        self.context = dict(actorName='Accountant', documents=[self.doc], contract=None)
        self.cur = Mock()
        self.deps = dict(authorize_read=Mock())
        self.resolver = patch('backend.features.supplier_payments.reads.build_document_resolver',
                              return_value=Mock(return_value=self.context))
        self.resolver.start()
        self.addCleanup(self.resolver.stop)

    def test_unregistered_opening_is_not_invented(self):
        from .reads import document
        self.cur.fetchall.return_value = []
        self.cur.fetchone.return_value = {'status': 'Частично оплачен', 'accounting_status': None}
        result = document(self.cur, self.deps, 7, 2, 'invoice', 8)
        self.assertEqual(result['openingPaidAmount'], None)
        self.assertFalse(result['registered'])
        self.assertEqual((result['amount'], result['paidAmount'], result['remainingAmount']),
                         ('200.00', '20.00', '180.00'))
        self.assertEqual(result['canonicalTarget'], dict(documentKind='invoice', documentId=8))
        self.assertTrue(all(call.args[0].lstrip().upper().startswith('SELECT')
                            for call in self.cur.execute.call_args_list))

    def test_registered_balance_must_equal_opening_plus_impacts(self):
        from .reads import document
        record = dict(id=9, company_id=2, document_kind='invoice', document_id=8,
                      payer_company_id=2, supplier_id=3, project_name='Exact project',
                      work_package='', amount=Decimal('200'), opening_paid=Decimal('10'))
        self.cur.fetchall.return_value = [record]
        self.cur.fetchone.return_value = {'total': Decimal('11')}
        with self.assertRaises(HTTPException) as error:
            document(self.cur, self.deps, 7, 2, 'invoice', 8)
        self.assertEqual(error.exception.status_code, 409)

    def test_registered_owner_drift_is_not_hidden_by_company_filter(self):
        from .reads import document
        self.cur.fetchall.return_value = [dict(id=9, company_id=3, document_kind='invoice', document_id=8)]
        with self.assertRaises(HTTPException) as error:
            document(self.cur, self.deps, 7, 2, 'invoice', 8)
        self.assertEqual(error.exception.status_code, 409)
