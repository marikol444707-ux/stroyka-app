"""Automatic draft selection through three real authenticated write routes.

Uses the existing guarded, fresh socket-only PostgreSQL fixture by delegation.
Explicit contract selection and manual request replay are intentionally separate.
"""
import json
import os
import unittest

from ..contractor_identity import test_selection_postgres as support
from ..contractor_identity import test_contract_selection_postgres as exact_support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DraftSelectionRoutesPostgresTests(unittest.TestCase):
    sql = support.TypedContractorSelectionPostgresTests.sql
    api = support.TypedContractorSelectionPostgresTests.api
    request = support.TypedContractorSelectionPostgresTests.request
    state = support.TypedContractorSelectionPostgresTests.state
    freeze = exact_support.ExactContractSelectionPostgresTests.freeze

    @classmethod
    def setUpClass(cls):
        support.TypedContractorSelectionPostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        support.TypedContractorSelectionPostgresTests.setUp(self)
        self.key = 'automatic-draft-work-' + self.tag
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s', (json.dumps([
            {'name': 'Automatic draft section', 'items': [
                {'name': 'New automatic work', 'type': 'work', 'unit': 'м',
                 'quantity': 5, 'priceWork': 100, 'estimateItemKey': self.key}]}]), self.f['estimateId']))

    def create(self):
        return self.api('director', 'POST', '/brigade-contracts', {
            **self.contract, 'contractorRef': {'type': 'user', 'id': self.target}})['id']

    def signed(self):
        selected = self.create()
        self.api('director', 'POST', '/brigade-contract-items', {
            'contractId': selected, 'name': 'Signed original work', 'unit': 'м',
            'quantity': 2, 'priceBrigade': 13, 'priceSmeta': 100})
        self.freeze(selected, self.target)
        return selected

    def contract_state(self, contract_id):
        return (self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (contract_id,)),
                self.sql('SELECT to_jsonb(i) FROM brigade_contract_items i WHERE contract_id=%s ORDER BY id',
                         (contract_id,)))

    def invoke(self, route, *, expected=200):
        if route == 'create':
            result = self.api('director', 'POST', '/brigade-contracts', {
                **self.contract, 'contractorRef': {'type': 'user', 'id': self.target}}, expected=expected)
            return result['id'] if expected == 200 else result
        coordinate = {'sectionIndex': 0, 'itemIndex': 0, 'estimateItemKey': self.key}
        if route == 'assignment':
            result = self.api('director', 'POST', f"/estimates/{self.f['estimateId']}/work-assignment", {
                'assignee': {'brigadeName': self.name, 'contractorId': self.target,
                             'contractorRef': {'type': 'user', 'id': self.target}},
                'priceMode': 'coefficient', 'coefficient': 0.6, 'items': [coordinate]}, expected=expected)
            return result['contractId'] if expected == 200 else result
        if route == 'distribution':
            result = self.api('director', 'POST', f"/estimates/{self.f['estimateId']}/distribute", {
                'defaultCoefficient': 0.6, 'assignments': [{**coordinate,
                    'brigadeName': self.name, 'contractorId': self.target,
                    'workPackage': self.f['workPackage']}]}, expected=expected)
            return result['createdContracts'][0]['id'] if expected == 200 else result
        raise AssertionError('Unknown route')

    def assert_signed_unchanged_and_draft_reused(self, route):
        signed = self.signed()
        before = self.contract_state(signed)
        draft = self.invoke(route)
        self.assertNotEqual(draft, signed)
        self.assertEqual(self.contract_state(signed), before)
        self.assertEqual(self.sql('SELECT status,contractor_id,company_id,project_id FROM brigade_contracts WHERE id=%s',
                                 (draft,)), [('Черновик', self.target, 2, self.f['projectId'])])
        created_state = self.contract_state(draft)
        self.assertEqual(self.invoke(route), draft)
        self.assertEqual(self.contract_state(draft), created_state)
        self.assertEqual(self.contract_state(signed), before)
        self.assertEqual(self.sql('''SELECT count(*) FROM brigade_contracts
            WHERE company_id=2 AND project_id=%s AND contractor_id=%s''',
            (self.f['projectId'], self.target)), [(2,)])
        expected_items = 0 if route == 'create' else 1
        self.assertEqual(self.sql('SELECT count(*) FROM brigade_contract_items WHERE contract_id=%s',
                                 (draft,)), [(expected_items,)])

    def assert_ambiguous_drafts_roll_back(self, route):
        draft = self.create()
        self.sql('''INSERT INTO brigade_contracts(company_id,project_id,project_name,work_package,
            brigade_name,contractor_type,contractor_id,status,total_amount)
            SELECT company_id,project_id,project_name,work_package,brigade_name,contractor_type,
                contractor_id,status,total_amount FROM brigade_contracts WHERE id=%s''', (draft,))
        before = self.state()
        self.invoke(route, expected=409)
        # Includes both contracts/items and earlier snapshot/version writes from
        # assignment/distribution, plus membership grants and source estimate.
        self.assertEqual(self.state(), before)

    def test_contract_create_ignores_signed_and_reuses_new_draft(self):
        self.assert_signed_unchanged_and_draft_reused('create')

    def test_assignment_ignores_signed_and_reuses_new_draft(self):
        self.assert_signed_unchanged_and_draft_reused('assignment')

    def test_distribution_ignores_signed_and_reuses_new_draft(self):
        self.assert_signed_unchanged_and_draft_reused('distribution')

    def test_contract_create_ambiguous_drafts_409_without_writes(self):
        self.assert_ambiguous_drafts_roll_back('create')

    def test_assignment_ambiguous_drafts_409_rolls_back_snapshot(self):
        self.assert_ambiguous_drafts_roll_back('assignment')

    def test_distribution_ambiguous_drafts_409_rolls_back_snapshot(self):
        self.assert_ambiguous_drafts_roll_back('distribution')
