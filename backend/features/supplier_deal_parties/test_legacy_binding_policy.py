import copy
import unittest
from fastapi import HTTPException
from .legacy_binding_policy import validate_legacy_binding


class LegacyBindingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.invoice = dict(id=161, company_id=1, supplier_id=159, offer_id=71,
            request_id=880, contract_version_id=None, warehouse_invoice_id=None,
            project_name='Лицей', work_package='Отделка', status='На утверждении',
            amount='263000.00', paid_amount='0.00')
        self.offer = dict(id=71, company_id=1, supplier_id=159, request_id=880,
            project='Лицей', work_package='Отделка', status='Утверждено')
        self.contract = dict(id=8, offer_id=71, company_id=1, reviewed_at='2026-09-28',
            reviewed_by='Директор', party_version=2, current_party_version=2)
        self.evidence = dict(ledger=False, receipts=False, deliveries=False, sealed_lines=False)

    def check(self):
        return validate_legacy_binding(self.invoice, self.offer, self.contract, self.evidence)

    def test_unpaid_unbound_invoice_preserves_input(self):
        original = copy.deepcopy(self.invoice)
        self.check()
        self.assertEqual(self.invoice, original)

    def test_each_downstream_evidence_blocks(self):
        for key in self.evidence:
            with self.subTest(key=key):
                self.evidence[key] = True
                with self.assertRaises(HTTPException): self.check()
                self.evidence[key] = False

    def test_missing_evidence_fails_closed(self):
        del self.evidence['deliveries']
        with self.assertRaises(HTTPException): self.check()

    def test_money_is_not_coerced_or_inferred(self):
        for field, values in [('paid_amount', [None, '1', '-1', 'NaN', True]),
                              ('amount', ['0', '-1', 'NaN', '1.001', True])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    old = self.invoice[field]; self.invoice[field] = value
                    with self.assertRaises(HTTPException): self.check()
                    self.invoice[field] = old

    def test_scope_changes_and_inactive_status_block(self):
        for field, value in [('company_id', 2), ('supplier_id', 160), ('offer_id', 72),
                             ('request_id', 881), ('project_name', 'Другой'),
                             ('work_package', 'Электрика'), ('status', 'Аннулирован'),
                             ('contract_version_id', 9), ('warehouse_invoice_id', 46)]:
            with self.subTest(field=field):
                old = self.invoice[field]; self.invoice[field] = value
                with self.assertRaises(HTTPException): self.check()
                self.invoice[field] = old

    def test_contract_must_be_current_reviewed_and_same_deal(self):
        for field, value in [('offer_id', 72), ('company_id', 2), ('reviewed_at', None),
                             ('reviewed_by', ''), ('current_party_version', 3)]:
            with self.subTest(field=field):
                old = self.contract[field]; self.contract[field] = value
                with self.assertRaises(HTTPException): self.check()
                self.contract[field] = old
        self.offer['status'] = 'Отклонено'
        with self.assertRaises(HTTPException): self.check()
