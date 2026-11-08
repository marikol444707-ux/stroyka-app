"""Canonical invitation regression on disposable PostgreSQL and real HTTP.

Only run through scripts/run_supplier_catalog_postgres_tests.py. Registration,
company-scoped merge, authorization, transactions and SQL are not mocked.
"""
import json
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from .test_supplier_registration_postgres import SupplierRegistrationPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MergedInvitationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)

    sql = Base.sql
    api = Base.api
    registration = Base.registration

    def setUp(self):
        self.client.cookies.clear()

    def inn(self):
        return '76' + str(secrets.randbelow(10**8)).zfill(8)

    def card(self, inn=None, company=2, name=None):
        sid = self.sql('INSERT INTO suppliers(name,inn,bank) VALUES(%s,%s,%s) RETURNING id',
                       (name or 'Invitation regression ' + secrets.token_hex(8), inn, 'Original bank'))[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(%s,%s,1)',
                 (company, sid))
        return sid

    def invite(self, sid=None):
        return self.api('director', 'POST', '/invite-codes',
                        {'role': 'поставщик', 'supplierId': sid, 'expiresInDays': 1},
                        **{'X-Company-Id': '2'})

    def merge(self, source, target):
        headers = {'X-Company-Id': '2'}
        review = self.api('director', 'POST', f'/suppliers/{target}/merge-preview',
                          {'sourceId': source, 'companyId': 2}, **headers)
        return self.api('director', 'POST', f'/suppliers/{target}/merge',
                        {**review, 'sourceId': source, 'companyId': 2, 'confirmed': True,
                         'expectedReview': review['reviewVersion']}, **headers)

    def assert_refused(self, invite, payload, status=409):
        before = self.sql('SELECT row_to_json(s)::text FROM suppliers s ORDER BY id')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, status, response.json().get('detail', f'Unexpected HTTP {response.status_code}'))
        self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
        self.assertEqual(self.sql('SELECT row_to_json(s)::text FROM suppliers s ORDER BY id'), before)

    def assert_claimed(self, payload, source, target, before_count):
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.json().get('detail', f'Unexpected HTTP {response.status_code}'))
        owner = self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],))[0][0]
        self.assertEqual(self.sql('SELECT id,user_id FROM suppliers WHERE id=ANY(%s) ORDER BY id',
                                  ([source, target],)), [(sid, owner) for sid in sorted({source, target})])
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers'), before_count)
        self.assertEqual(self.sql('SELECT company_id,platform_account_id FROM users WHERE id=%s', (owner,)),
                         [(None, None)])
        self.assertEqual(self.sql('SELECT user_id FROM user_company_roles WHERE user_id=%s', (owner,)), [])

    def test_invitation_issued_before_explicit_merge_claims_original_history_without_rewriting_it(self):
        inn = self.inn()
        source, target = self.card(inn), self.card(inn)
        invite = self.invite(source)
        invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            amount,paid_amount,status,paid_note) VALUES(2,%s,%s,200,50,'На утверждении','Original payment') RETURNING id''',
            (source, self.fixture['project']))[0][0]
        snapshot = {'version': 1, 'supplier': {'name': 'Frozen supplier', 'inn': inn, 'bank': 'Frozen bank'}}
        offer = self.sql('INSERT INTO supplier_offers(company_id,supplier_id,party_snapshot_json) VALUES(2,%s,%s::jsonb) RETURNING id',
                         (source, json.dumps(snapshot)))[0][0]
        before_invoice = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        before_offer = self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s', (offer,))
        self.merge(source, target)
        payload = self.registration(invite, inn=inn)
        self.assert_claimed(payload, source, target, self.sql('SELECT count(*) FROM suppliers'))
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)), before_invoice)
        self.assertEqual(self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s', (offer,)), before_offer)
        self.assertEqual(self.sql('SELECT bank FROM suppliers WHERE id=ANY(%s)', ([source, target],)),
                         [('Original bank',), ('Original bank',)])
        own = self.client.get('/supplier-invoices')
        self.assertEqual(own.status_code, 200, own.text)
        self.assertIn(invoice, [row['id'] for row in own.json()])
        self.assertIn(invoice, [row['id'] for row in self.api('director', 'GET', '/supplier-invoices', **{'X-Company-Id': '2'})])
        for actor in ('stranger', 'stranger_supplier'):
            self.assertNotIn(invoice, [row['id'] for row in self.api(actor, 'GET', '/supplier-invoices')])

    def test_new_invitation_from_merged_source_targets_the_canonical_card(self):
        inn = self.inn()
        source, target = self.card(inn), self.card(inn)
        self.merge(source, target)
        invite = self.invite(source)
        self.assertEqual(invite['supplier_id'], target)
        self.assert_claimed(self.registration(invite, inn=inn), source, target,
                            self.sql('SELECT count(*) FROM suppliers'))

    def test_generic_invitation_matches_formatted_key_on_merged_source_without_new_supplier(self):
        inn = self.inn()
        formatted = inn[:2] + '\u00a0-' + inn[2:]
        source, target = self.card(formatted), self.card()
        self.merge(source, target)
        invite = self.invite()
        self.assert_claimed(self.registration(invite, inn=inn), source, target,
                            self.sql('SELECT count(*) FROM suppliers'))
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (source,)), [(formatted,)])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [(inn,)])

    def test_targeted_invitation_accepts_same_formatted_identity_and_preserves_original(self):
        inn = self.inn()
        formatted = inn[:3] + ' - ' + inn[3:]
        sid = self.card(formatted)
        invite = self.invite(sid)
        self.assert_claimed(self.registration(invite, inn=inn), sid, sid,
                            self.sql('SELECT count(*) FROM suppliers'))
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (sid,)), [(formatted,)])

    def test_foreign_cyclic_missing_and_malformed_merge_targets_refuse_atomically(self):
        for mode in ('foreign', 'cycle', 'missing', 'string', 'chain'):
            with self.subTest(mode=mode):
                inn = self.inn()
                source, target = self.card(inn), self.card(inn, company=3 if mode == 'foreign' else 2)
                invite = self.invite(source)
                target_value = str(target) if mode == 'string' else 999999999 if mode == 'missing' else target
                self.sql('UPDATE company_supplier_links SET profile=%s::jsonb WHERE company_id=2 AND supplier_id=%s',
                         (json.dumps({'mergedIntoSupplierId': target_value}), source))
                if mode in ('cycle', 'chain'):
                    final = source if mode == 'cycle' else self.card(inn)
                    self.sql('UPDATE company_supplier_links SET profile=%s::jsonb WHERE company_id=2 AND supplier_id=%s',
                             (json.dumps({'mergedIntoSupplierId': final}), target))
                self.assert_refused(invite, self.registration(invite, inn=inn))

    def test_ambiguous_generic_invitation_does_not_choose_one_card(self):
        inn = self.inn()
        self.card(inn)
        self.card(inn)
        invite = self.invite()
        self.assert_refused(invite, self.registration(invite, inn=inn))

    def test_targeted_invitation_cannot_claim_populated_identity_of_registered_cabinet(self):
        sid = self.card('7701234567')
        invite = self.invite(sid)
        self.assert_refused(invite, self.registration(invite, inn='7701234567'))

    def test_foreign_document_added_after_invitation_prevents_claim(self):
        inn = self.inn()
        source, target = self.card(inn), self.card(inn)
        invite = self.invite(source)
        self.merge(source, target)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(3,%s,300,100)', (source,))
        self.assert_refused(invite, self.registration(invite, inn=inn))

    def test_malformed_explicit_legal_keys_never_become_a_registered_identity(self):
        inn = self.inn()
        for key, value in [('inn', 'ИНН ' + inn), ('inn', inn[:3] + '/' + inn[3:]),
                           ('inn', '７７０１２３４５６７'), ('ogrn', '1234567890123x')]:
            with self.subTest(key=key, value=value):
                invite = self.invite()
                self.assert_refused(invite, self.registration(invite, **{key: value}), status=422)

    def test_two_old_invitations_for_one_merged_group_create_one_account(self):
        from fastapi.testclient import TestClient
        inn = self.inn()
        source, target = self.card(inn), self.card(inn)
        first, second = self.invite(source), self.invite(target)
        self.merge(source, target)
        payloads = [self.registration(invite, inn=inn) for invite in (first, second)]
        before = self.sql('SELECT count(*) FROM suppliers')
        ready = Barrier(2)

        def signup(payload):
            with TestClient(self.main.app) as client:
                ready.wait(timeout=10)
                return client.post('/register', json=payload)

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(signup, payloads))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409],
                         [(r.status_code, r.json().get('detail', 'no error detail')) for r in responses])
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers'), before)
        owners = self.sql('SELECT DISTINCT user_id FROM suppliers WHERE id=ANY(%s)', ([source, target],))
        self.assertEqual(len(owners), 1)
        self.assertIsNotNone(owners[0][0])
        self.assertEqual(self.sql('SELECT count(*) FROM users WHERE email=ANY(%s)',
                                  ([p['email'] for p in payloads],)), [(1,)])
        for invite, payload, response in zip((first, second), payloads, responses):
            self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)),
                             [(response.status_code == 200,)])
            if response.status_code == 409:
                self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])

    def test_blank_canonical_target_does_not_hide_registered_identity_on_source(self):
        source, target = self.card('7701234567'), self.card()
        invite = self.invite(source)
        self.merge(source, target)
        self.assert_refused(invite, self.registration(invite))

    def test_blank_canonical_target_with_conflicting_source_identities_requires_review(self):
        first, second, target = self.card(self.inn()), self.card(self.inn()), self.card()
        invite = self.invite(target)
        self.merge(first, target)
        self.merge(second, target)
        self.assert_refused(invite, self.registration(invite))

    def test_name_containing_legal_number_alone_never_claims_catalog_history(self):
        inn = self.inn()
        sid = self.card(inn)
        invite = self.invite()
        payload = self.registration(invite)
        payload['companyName'] = 'Another name ИНН ' + inn
        response = self.client.post('/register', json=payload)
        self.assertIn(response.status_code, (200, 409), response.json().get('detail', f'Unexpected HTTP {response.status_code}'))
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (sid,)), [(None,)])
        if response.status_code == 409:
            self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
            self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])

    def test_ocr_supplier_alias_fields_cannot_override_explicit_registration_identity(self):
        inn = self.inn()
        sid = self.card(inn)
        invite = self.invite(sid)
        payload = self.registration(invite, inn=inn, supplierInn='7701234567', supplier_inn='7809876543',
                                    supplierName='Misleading OCR supplier name')
        self.assert_claimed(payload, sid, sid, self.sql('SELECT count(*) FROM suppliers'))
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (sid,)), [(inn,)])
        self.assertEqual(self.sql('SELECT inn,alias_name,source FROM supplier_aliases WHERE supplier_id=%s', (sid,)),
                         [(inn, payload['companyName'], 'supplier_invite')])
        self.assertEqual(self.sql('SELECT id FROM supplier_aliases WHERE supplier_id=%s AND inn=ANY(%s)',
                                  (sid, ['7701234567', '7809876543'])), [])

    def test_registration_and_profile_change_cannot_claim_same_identity_concurrently(self):
        from fastapi.testclient import TestClient
        inn = self.inn()
        provisional = self.card(inn)
        invite = self.invite(provisional)
        payload = self.registration(invite, inn=inn)
        current_id = self.fixture['supplierId']
        path = f'/suppliers/{current_id}/requisites'
        before = self.api('supplier', 'GET', path)
        old = self.sql('SELECT inn,ogrn,phone FROM suppliers WHERE id=%s', (current_id,))[0]
        self.addCleanup(self.sql, 'UPDATE suppliers SET inn=%s,ogrn=%s,phone=%s WHERE id=%s', (*old, current_id))
        token = self.main.create_auth_token(self.fixture['users']['supplier'], two_factor_passed=True)
        ready = Barrier(2)

        def signup():
            with TestClient(self.main.app) as client:
                ready.wait(timeout=10)
                return client.post('/register', json=payload)

        def change():
            with TestClient(self.main.app) as client:
                ready.wait(timeout=10)
                return client.put(path, json={'inn': inn, 'phone': 'Concurrent profile draft',
                                              'expectedProfileVersion': before['version']},
                                  headers={'Authorization': 'Bearer ' + token})

        with ThreadPoolExecutor(max_workers=2) as pool:
            signup_future, profile_future = pool.submit(signup), pool.submit(change)
            registered, changed = signup_future.result(timeout=20), profile_future.result(timeout=20)
        self.assertEqual(sorted([registered.status_code, changed.status_code]), [200, 409],
                         [(r.status_code, r.json().get('detail', 'no error detail')) for r in (registered, changed)])
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers WHERE inn=%s AND user_id IS NOT NULL', (inn,)), [(1,)])
        if registered.status_code == 409:
            self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
            self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
            self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (provisional,)), [(None,)])
        else:
            self.assertEqual(self.api('supplier', 'GET', path), before)
