"""Transit request contract; no database or application bootstrap."""
from unittest import TestCase
from uuid import uuid4
import os
from unittest.mock import patch
from pydantic import ValidationError
from .models import TransferInput, TransferReceiptInput
from .test_membership import boundary, membership
from . import transfers


class TransferContractTests(TestCase):
    def payload(self, **extra):
        return dict(companyId=2, requestId=str(uuid4()), reason='Actual receipt', **extra)

    def test_zero_receipt_is_valid_discrepancy(self):
        value = TransferReceiptInput(**self.payload(quantity='0', expectedQuantity='2'))
        self.assertEqual(value.quantity, 0)

    def test_invalid_receipt_quantities(self):
        for quantity, expected in [('-1','2'), ('2','1'), ('0','0'), ('NaN','2'), ('1.0000001','2')]:
            with self.subTest(quantity=quantity, expected=expected), self.assertRaises(ValidationError):
                TransferReceiptInput(**self.payload(quantity=quantity, expectedQuantity=expected))

    def test_dispatch_requires_exact_allocation_and_no_actor_binding(self):
        value = TransferInput(**self.payload(allocationId=2**32, toProjectId=2, quantity='1'))
        self.assertEqual(value.allocationId, 2**32)
        with self.assertRaises(ValidationError):
            TransferInput(**self.payload(allocationId=1, toProjectId=2, quantity='1', receiverId=3))

    def test_transfer_commands_refresh_membership_and_never_bind_actor(self):
        for role in ('кладовщик','снабженец'):
            for change in ({},dict(active=False),dict(readOnly=True),dict(role='бухгалтер'),dict(membershipId=999)):
                for receiving in (False,True):
                    with self.subTest(role=role,change=change,receiving=receiving), boundary(
                            membership(role=role),refreshed=membership(**dict(dict(role=role),**change))) as case:
                        os.environ['WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED']='1'
                        command = 'receive' if receiving else 'dispatch'
                        payload = self.payload(quantity='1',**(dict(expectedQuantity='1') if receiving else dict(allocationId=1,toProjectId=2)))
                        path = '/warehouse-distributions/transfers'+('/1/receipts' if receiving else '')
                        with patch.object(transfers,command,return_value=dict(ok=True,requestId=payload['requestId'],item={})) as writer:
                            response = case.client.post(path,json=payload)
                            self.assertEqual(response.status_code,403 if change else 200,response.text)
                            self.assertEqual(case.resolver.call_count,2)
                            if change:
                                writer.assert_not_called()
                                case.conn.commit.assert_not_called()
                            else:
                                self.assertEqual(writer.call_args.args[-1]['role'],role)

    def test_transfer_gate_is_off_by_default_and_requires_distribution(self):
        for flags in ({},dict(WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED='true'),
                      dict(WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED='1',WAREHOUSE_DISTRIBUTION_ENABLED='0')):
            with self.subTest(flags=flags),boundary() as case:
                os.environ.pop('WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED',None)
                os.environ.update(flags)
                response = case.client.post('/warehouse-distributions/transfers',json=self.payload(
                    allocationId=1,toProjectId=2,quantity='1'))
                self.assertEqual(response.status_code,404)
                case.resolver.assert_not_called()
