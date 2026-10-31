"""Existing-contract selection never substitutes a richer same-name contract."""
import json
import os
import unittest

from . import test_selection_postgres as support
from ..contractor_contract_parties.snapshot import snapshot_digest


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ExactContractSelectionPostgresTests(unittest.TestCase):
    sql = support.TypedContractorSelectionPostgresTests.sql
    api = support.TypedContractorSelectionPostgresTests.api
    request = support.TypedContractorSelectionPostgresTests.request
    state = support.TypedContractorSelectionPostgresTests.state
    setUp = support.TypedContractorSelectionPostgresTests.setUp

    @classmethod
    def setUpClass(cls):
        support.TypedContractorSelectionPostgresTests.setUpClass.__func__(cls)

    def create_contract(self):
        return self.api('director', 'POST', '/brigade-contracts', {
            **self.contract, 'contractorRef': {'type': 'user', 'id': self.target}})['id']

    def assignment(self, contract_id, owner=None):
        key = 'exact-contract-work-' + self.tag
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=%s', (json.dumps([
            {'name': 'Contract selection', 'items': [{'name': 'Selected work', 'type': 'work',
                'unit': 'м', 'quantity': 5, 'priceWork': 100, 'estimateItemKey': key}]}]), self.f['estimateId']))
        return {'assignee': {'contractorRef': {'type': 'contract', 'id': contract_id},
            'contractorId': self.target if owner is None else owner,
            'brigadeName': 'Untrusted renamed brigade', 'contractorType': 'Untrusted type'},
            'priceMode': 'coefficient', 'coefficient': 0.6,
            'items': [{'sectionIndex': 0, 'itemIndex': 0, 'estimateItemKey': key}]}

    def assign(self, payload, expected=200):
        return self.api('director', 'POST', f"/estimates/{self.f['estimateId']}/work-assignment", payload, expected=expected)

    def freeze(self, contract_id, owner, **changes):
        snapshot = {'schemaVersion': 1, 'customer': {'companyId': 2},
            'contractor': {'userId': owner, 'fullName': self.name},
            'project': {'id': self.f['projectId']}, 'contract': {'id': contract_id}, **changes}
        self.sql("""UPDATE brigade_contracts SET status='Подписан',party_snapshot_json=%s,
            party_snapshot_hash=%s WHERE id=%s""", (json.dumps(snapshot), snapshot_digest(snapshot), contract_id))

    def test_assignment_uses_selected_contract_despite_a_richer_duplicate_and_retries_preserve_prices(self):
        selected = self.create_contract()
        duplicate = self.sql('''INSERT INTO brigade_contracts(company_id,project_id,project_name,work_package,
            brigade_name,contractor_type,contractor_id,status,total_amount)
            SELECT company_id,project_id,project_name,work_package,brigade_name,contractor_type,
                contractor_id,status,total_amount FROM brigade_contracts WHERE id=%s RETURNING id''', (selected,))[0][0]
        self.api('director', 'POST', '/brigade-contract-items', {'contractId': duplicate,
            'name': 'Existing duplicate work', 'unit': 'м', 'quantity': 1, 'priceBrigade': 50, 'priceSmeta': 100})
        self.freeze(selected, self.target)
        before = self.sql('SELECT to_jsonb(c)-\'total_amount\' FROM brigade_contracts c WHERE id=%s', (selected,))
        other_before = self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (duplicate,))
        payload = self.assignment(selected)
        result = self.assign(payload)
        self.assertEqual(result['contractId'], selected)
        self.assertEqual(result['brigadeName'], self.name)
        self.assertFalse(result['createdContract'])
        self.assertEqual(result['inserted'], 1)
        first_items = self.sql('SELECT to_jsonb(i) FROM brigade_contract_items i WHERE contract_id=%s ORDER BY id', (selected,))
        retry = self.assign({**payload, 'coefficient': 0.9})
        self.assertEqual((retry['inserted'], retry['reused']), (0, 1))
        self.assertEqual(first_items, self.sql('SELECT to_jsonb(i) FROM brigade_contract_items i WHERE contract_id=%s ORDER BY id', (selected,)))
        self.assertEqual(before, self.sql('SELECT to_jsonb(c)-\'total_amount\' FROM brigade_contracts c WHERE id=%s', (selected,)))
        self.assertEqual(other_before, self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (duplicate,)))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM brigade_contract_items WHERE contract_id=%s', (duplicate,)), [(1,)])

    def test_wrong_company_project_package_status_and_unlinked_contract_leave_state_unchanged(self):
        selected = self.create_contract()
        payload = self.assignment(selected)
        other_project = self.sql("INSERT INTO projects(name,company_id) VALUES(%s,2) RETURNING id", ('Other '+self.tag,))[0][0]
        for field, value in (('company_id', 3), ('project_id', other_project),
                             ('work_package', 'Other package'), ('status', 'Аннулирован'), ('contractor_id', None)):
            with self.subTest(field=field):
                original = self.sql('SELECT '+field+' FROM brigade_contracts WHERE id=%s', (selected,))[0][0]
                self.sql('UPDATE brigade_contracts SET '+field+'=%s WHERE id=%s', (value, selected))
                try:
                    before = self.state()
                    self.assign(payload, expected=409)
                    self.assertEqual(before, self.state())
                finally:
                    self.sql('UPDATE brigade_contracts SET '+field+'=%s WHERE id=%s', (original, selected))
        before = self.state()
        self.assign({**payload, 'assignee': {**payload['assignee'], 'contractorId': self.collision}}, expected=400)
        self.assertEqual(before, self.state())

    def test_ambiguous_legacy_owner_requires_frozen_user_evidence_and_conflicting_snapshot_is_blocked(self):
        selected = self.create_contract()
        self.sql('UPDATE brigade_contracts SET contractor_id=%s WHERE id=%s', (self.collision, selected))
        payload = self.assignment(selected, self.collision)
        before = self.state()
        self.assign(payload, expected=409)
        self.assertEqual(before, self.state())
        self.sql("UPDATE brigade_contracts SET status='Подписан' WHERE id=%s", (selected,))
        before = self.state()
        self.assign(payload, expected=409)
        self.assertEqual(before, self.state())
        self.freeze(selected, self.collision, customer={'companyId': 3})
        before = self.state()
        self.assign(payload, expected=409)
        self.assertEqual(before, self.state())
        self.freeze(selected, self.collision)
        self.sql("UPDATE brigade_contracts SET party_snapshot_hash='invalid' WHERE id=%s", (selected,))
        before = self.state()
        self.assign(payload, expected=409)
        self.assertEqual(before, self.state())
        self.freeze(selected, self.collision)
        self.assertEqual(self.assign(payload)['contractorId'], self.collision)
        self.assertEqual(self.api('typed_target', 'GET', f'/brigade-contract-items/{selected}'), [])

    def test_reuse_endpoint_returns_exact_id_and_rechecks_revoked_membership_without_writes(self):
        selected = self.create_contract()
        self.sql('''INSERT INTO brigade_contracts(company_id,project_id,project_name,work_package,
            brigade_name,contractor_type,contractor_id,status)
            SELECT company_id,project_id,project_name,work_package,brigade_name,contractor_type,
                contractor_id,status FROM brigade_contracts WHERE id=%s''', (selected,))
        payload = {**self.contract, 'contractorRef': {'type': 'contract', 'id': selected}, 'contractorId': self.target}
        before = self.state()
        response = self.api('director', 'POST', '/brigade-contracts', payload)
        self.assertEqual((response['id'], response['contractorId'], response['reused']), (selected, self.target, True))
        self.assertEqual(before, self.state())
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s', (self.target,))
        assignment = self.assignment(selected)
        before = self.state()
        self.api('director', 'POST', '/brigade-contracts', payload, expected=409)
        self.assign(assignment, expected=409)
        self.assertEqual(before, self.state())

    def test_contract_owner_and_membership_are_pinned_until_assignment_transaction_ends(self):
        from concurrent.futures import ThreadPoolExecutor
        import psycopg2
        from .selection import resolve_selected_user
        selected = self.create_contract()
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                self.assertEqual(resolve_selected_user(cur, 2, {'type': 'contract', 'id': selected},
                    project_id=self.f['projectId'], work_package=self.f['workPackage']), self.target)
            def update(sql, args):
                other = self.main.get_db()
                other.autocommit = False
                try:
                    with other.cursor() as cur:
                        cur.execute("SET LOCAL lock_timeout='100ms'")
                        cur.execute(sql, args)
                    other.commit()
                finally:
                    other.close()
            with ThreadPoolExecutor(max_workers=1) as pool:
                for sql, args in (
                    ('UPDATE brigade_contracts SET contractor_id=%s WHERE id=%s', (self.collision, selected)),
                    ('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s', (self.target,)),
                ):
                    with self.assertRaises(psycopg2.errors.LockNotAvailable):
                        pool.submit(update, sql, args).result(timeout=3)
        finally:
            conn.rollback()
            conn.close()
