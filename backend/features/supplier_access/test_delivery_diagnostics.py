import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.features.supplier_access.delivery_diagnostics import (
    attach_recipient_delivery_diagnostics,
)
from backend.features.supplier_access.supply_request_workflow import (
    SupplyRequestWorkflowViolation,
    supply_request_approval_block_reason,
    validate_rfq_dispatch_request,
)


class RfqApprovalTests(unittest.TestCase):
    def test_each_missing_approval_blocks_dispatch(self):
        for prorab, director in ((None, None), (None, 'now'), ('now', None)):
            with self.subTest(prorab=prorab, director=director):
                request = dict(status='Утверждена', prorab_confirmed_at=prorab,
                               director_approved_at=director)
                self.assertTrue(supply_request_approval_block_reason(request))
                with self.assertRaises(SupplyRequestWorkflowViolation) as raised:
                    validate_rfq_dispatch_request(request)
                self.assertEqual(raised.exception.status_code, 409)

    def test_dispatch_requires_valid_status_even_with_approvals(self):
        for status in ('Новая', 'Отменена', 'Поставлено'):
            with self.subTest(status=status):
                with self.assertRaises(SupplyRequestWorkflowViolation):
                    validate_rfq_dispatch_request(dict(status=status,
                        prorab_confirmed_at='now', director_approved_at='now'))
        for status in ('Утверждена', 'КП запрошены'):
            validate_rfq_dispatch_request(dict(status=status,
                prorab_confirmed_at='now', director_approved_at='now'))


class DeliveryDiagnosticsTests(unittest.TestCase):
    def test_deleted_supplier_is_distinguished_from_an_unlinked_account(self):
        source = Path(__file__).resolve().parents[2] / 'main.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == '_supplier_visibility_for_scope')
        namespace = {'_normalize_supplier_ids': lambda ids: ids}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        cur = Mock()
        cur.fetchall.return_value = []
        result = namespace['_supplier_visibility_for_scope'](cur, [42])
        self.assertFalse(result['visible'])
        self.assertIsNone(result['user_id'])
        self.assertIn('Карточка поставщика не найдена', result['reason'])
        cur.execute.assert_called_once()

    def test_approval_does_not_misrepresent_account_link_or_acknowledgement(self):
        cur = Mock()
        rows = [{'id': 1, 'visibleToSupplier': True}]
        result = attach_recipient_delivery_diagnostics(cur,
            {'id': 2, 'company_id': 1, 'director_approved_at': 'now'}, rows)
        self.assertTrue(result[0]['visibleToSupplier'])
        self.assertFalse(result[0]['approvalComplete'])
        self.assertIn('прораб', result[0]['approvalBlockReason'])
        self.assertIsNone(result[0]['actualMaxQueueStatus'])
        cur.execute.assert_not_called()

    def test_outbox_is_read_in_company_request_recipient_scope(self):
        cur = Mock()
        cur.fetchone.return_value = {'table_name': 'messenger_outbox'}
        cur.fetchall.return_value = [{'recipient_id': 1, 'status': 'failed'}]
        rows = [{'id': 1, 'maxOutboxId': 4, 'maxNotificationStatus': 'В очереди MAX'},
                {'id': 2, 'maxOutboxId': 5, 'maxNotificationStatus': 'В очереди MAX'}]
        req = {'id': 8, 'company_id': 3, 'prorab_confirmed_at': 'now',
               'director_approved_at': 'now'}
        result = attach_recipient_delivery_diagnostics(cur, req, rows)
        self.assertEqual(result[0]['actualMaxQueueStatus'], 'failed')
        self.assertEqual(result[1]['actualMaxQueueStatus'], 'unknown')
        self.assertTrue(result[0]['approvalComplete'])
        sql, params = cur.execute.call_args.args
        for clause in ('o.company_id=r.company_id', 'o.entity_id=r.request_id',
                       "o.provider='max'", "o.event_type='supplier_kp_requested'",
                       'o.user_id=r.supplier_user_id'):
            self.assertIn(clause, sql)
        self.assertEqual(params, (8, 3, [1, 2]))
        self.assertEqual(cur.execute.call_count, 2)

    def test_missing_outbox_table_is_unknown_without_schema_writes(self):
        cur = Mock()
        cur.fetchone.return_value = {'table_name': None}
        result = attach_recipient_delivery_diagnostics(cur,
            {'id': 1, 'company_id': 1}, [{'id': 2, 'maxOutboxId': 99}])
        self.assertEqual(result[0]['actualMaxQueueStatus'], 'unknown')
        cur.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
