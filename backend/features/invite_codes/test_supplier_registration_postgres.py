"""Real signup and buyer isolation on disposable, network-disabled PostgreSQL."""
import importlib
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
import time

from backend.features.supplier_access import test_postgres_chain as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class SupplierRegistrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.PostgresSupplyChainTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                from types import SimpleNamespace
                from backend.features.audit_ownership.migration import _ensure_schema as audit_schema
                from backend.features.api_error_ownership.migration import _ensure_schema as error_schema
                audit_schema(cur)
                error_schema(cur)
                catalog = importlib.import_module('migrations.versions.0022_supplier_company_catalog')
                with patch.object(catalog, 'op', SimpleNamespace(execute=cur.execute)):
                    catalog.upgrade()
                cur.execute(importlib.import_module('migrations.versions.0035_supplier_team_policy').SCHEMA_SQL)
                cur.execute(importlib.import_module('migrations.versions.0036_supplier_invite_company').SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    api = support.PostgresSupplyChainTests.api
    sql = support.PostgresSupplyChainTests.sql

    def invite(self):
        return self.api('director', 'POST', '/invite-codes', {
            'role': 'поставщик', 'presetName': 'INVITE ' + secrets.token_hex(8), 'expiresInDays': 1,
        }, **{'X-Company-Id': '2', 'X-Company-Mode': 'company'})

    def registration(self, invite, **extra):
        name = 'INVITE ' + secrets.token_hex(8)
        return dict(code=invite['code'], name=name, companyName=name,
                    email=secrets.token_hex(8) + '@local.invalid', password=secrets.token_urlsafe(25), **extra)

    def test_signup_catalog_and_no_workforce_membership(self):
        invite = self.invite()
        payload = self.registration(invite, companyId=3, platformAccountId=999)
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        user_id, company_id, account_id = self.sql('SELECT id,company_id,platform_account_id FROM users WHERE email=%s', (payload['email'],))[0]
        self.assertIsNone(company_id)
        self.assertIsNone(account_id)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM user_company_roles WHERE user_id=%s', (user_id,)), [(0,)])
        supplier_id = self.sql('SELECT id FROM suppliers WHERE user_id=%s', (user_id,))[0][0]
        self.assertEqual(self.sql('SELECT company_id FROM company_supplier_links WHERE supplier_id=%s', (supplier_id,)), [(2,)])
        buyer = self.api('director', 'GET', '/suppliers', **{'X-Company-Id': '2'})
        self.assertIn(supplier_id, [r['id'] for r in buyer])
        self.assertNotIn(supplier_id, [r['id'] for r in self.api('stranger', 'GET', '/suppliers', **{'X-Company-Id': '3'})])
        self.assertEqual(next(r for r in buyer if r['id'] == supplier_id)['email'], payload['email'])
        again = self.client.post('/register', json=self.registration(invite))
        self.assertEqual(again.status_code, 400)
        self.client.cookies.clear()

    def test_cross_company_creation_listing_and_delete(self):
        invite = self.invite()
        for body, status in (({'companyId': 3}, 409), ({'platformAccountId': 999}, 403)):
            self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', **body},
                     expected=status, **{'X-Company-Id': '2', 'X-Company-Mode': 'company'})
        self.api('director', 'POST', '/invite-codes', {'role': 'поставщик'},
                 expected=403, **{'X-Company-Id': '3', 'X-Company-Mode': 'company'})
        self.assertNotIn(invite['id'], [r['id'] for r in self.api('stranger', 'GET', '/invite-codes', **{'X-Company-Id': '3'})])
        self.api('stranger', 'DELETE', '/invite-codes/' + str(invite['id']), expected=403, **{'X-Company-Id': '3'})
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
        self.api('director', 'DELETE', '/invite-codes/' + str(invite['id']), **{'X-Company-Id': '2'})
        self.assertEqual(self.sql('SELECT invite_id FROM supplier_invite_companies WHERE invite_id=%s', (invite['id'],)), [])

    def test_expired_and_inactive_company_leave_no_partial_signup(self):
        for inactive in (False, True):
            invite = self.invite()
            payload = self.registration(invite)
            if inactive:
                self.sql('UPDATE companies SET active=FALSE WHERE id=2')
            else:
                self.sql("UPDATE invite_codes SET expires_at=NOW()-INTERVAL '1 day' WHERE id=%s", (invite['id'],))
            try:
                response = self.client.post('/register', json=payload)
                self.assertEqual(response.status_code, 409 if inactive else 400, response.text)
                self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
                self.assertEqual(self.sql('SELECT id FROM suppliers WHERE email=%s', (payload['email'],)), [])
                self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
            finally:
                self.sql('UPDATE companies SET active=TRUE WHERE id=2')

    def test_existing_identity_is_not_claimed(self):
        invite = self.invite()
        payload = self.registration(invite)
        payload['inn'] = '7701234567'
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])

    def test_invite_claims_only_unregistered_own_catalog_card(self):
        sid = self.sql("INSERT INTO suppliers(name,inn) VALUES('Unregistered invoice card','7799887766') RETURNING id")[0][0]
        self.sql("INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id,profile) VALUES(2,%s,1,'{\"notes\":\"Keep invoice history\"}')", (sid,))
        invite = self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', 'supplierId': sid}, **{'X-Company-Id': '2'})
        second = self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', 'supplierId': sid}, **{'X-Company-Id': '2'})
        payload = self.registration(invite, inn='7799887766')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.sql('SELECT id FROM suppliers WHERE inn=%s', ('7799887766',)), [(sid,)])
        self.assertEqual(self.sql('SELECT s.id FROM suppliers s JOIN users u ON u.id=s.user_id WHERE u.email=%s', (payload['email'],)), [(sid,)])
        self.assertEqual(self.sql("SELECT profile->>'notes' FROM company_supplier_links WHERE supplier_id=%s", (sid,)), [('Keep invoice history',)])
        self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', 'supplierId': sid}, expected=409, **{'X-Company-Id': '2'})
        again = self.client.post('/register', json=self.registration(second))
        self.assertEqual(again.status_code, 409, again.text)
        self.client.cookies.clear()

    def test_invite_rejects_foreign_and_shared_unclaimed_card(self):
        sid = self.sql("INSERT INTO suppliers(name) VALUES('Foreign invoice card') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)', (sid,))
        self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', 'supplierId': sid}, expected=404, **{'X-Company-Id': '2'})
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(2,%s,1)', (sid,))
        self.api('director', 'POST', '/invite-codes', {'role': 'поставщик', 'supplierId': sid}, expected=409, **{'X-Company-Id': '2'})

    def test_delete_during_signup_finishes_without_deadlock(self):
        from backend.features.invite_codes import supplier_relationship
        invite = self.invite()
        payload = self.registration(invite)
        reached, proceed = Event(), Event()
        original = supplier_relationship.link_registered_supplier

        def pause_with_invite_locked(*args):
            reached.set()
            self.assertTrue(proceed.wait(10))
            return original(*args)

        with patch.object(supplier_relationship, 'link_registered_supplier', pause_with_invite_locked):
            with ThreadPoolExecutor(max_workers=2) as pool:
                signup = pool.submit(self.client.post, '/register', json=payload)
                self.assertTrue(reached.wait(10))
                deletion = pool.submit(self.api, 'director', 'DELETE', '/invite-codes/' + str(invite['id']),
                                       **{'X-Company-Id': '2'})
                time.sleep(.2)
                proceed.set()
                self.assertEqual(signup.result(timeout=20).status_code, 200)
                self.assertTrue(deletion.result(timeout=20)['ok'])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM company_supplier_links l JOIN suppliers s ON s.id=l.supplier_id WHERE s.email=%s',
                                  (payload['email'],)), [(1,)])
        self.client.cookies.clear()
