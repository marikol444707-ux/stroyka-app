"""Profile legal identity regressions through authenticated HTTP and real SQL.

Run only via run_supplier_catalog_postgres_tests.py on its disposable database.
The fixtures disable external services and create synthetic suppliers/companies.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from backend.features.supplier_team import test_customer_team_postgres as support


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Requires isolated PostgreSQL')
class SupplierIdentityRegressionPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.CustomerTeamPostgresTests.setUpClass.__func__(cls)

    api = support.CustomerTeamPostgresTests.api
    sql = support.CustomerTeamPostgresTests.sql
    quote = support.CustomerTeamPostgresTests.quote

    def setUp(self):
        support.CustomerTeamPostgresTests.setUp(self)
        self.supplier_id = self.fixture['supplierId']
        self.other_id = self.sql('SELECT id FROM suppliers WHERE user_id=%s',
                                (self.fixture['users']['stranger_supplier']['id'],))[0][0]
        rows = self.sql('SELECT id,inn,ogrn,phone,bank FROM suppliers WHERE id IN (%s,%s)',
                        (self.supplier_id, self.other_id))
        self.addCleanup(self.restore_profiles, rows)

    def restore_profiles(self, rows):
        for sid, inn, ogrn, phone, bank in rows:
            self.sql('UPDATE suppliers SET inn=%s,ogrn=%s,phone=%s,bank=%s WHERE id=%s',
                     (inn, ogrn, phone, bank, sid))

    def path(self, sid=None):
        return f'/suppliers/{self.supplier_id if sid is None else sid}/requisites'

    def put(self, actor, sid, data):
        token = self.main.create_auth_token(self.fixture['users'][actor], two_factor_passed=True)
        return self.client.put(self.path(sid), json=data,
                               headers={'Authorization': 'Bearer ' + token})

    def test_formatted_legal_keys_are_saved_canonically_and_survive_reload(self):
        before = self.api('supplier', 'GET', self.path())
        saved = self.api('supplier', 'PUT', self.path(), {
            'inn': '74\u00a0-12345678', 'ogrn': '12345 - 67890123',
            'expectedProfileVersion': before['version'],
        })
        self.assertEqual(saved['fields']['inn'], '7412345678')
        self.assertEqual(saved['fields']['ogrn'], '1234567890123')
        self.assertEqual(self.api('supplier', 'GET', self.path())['fields'], saved['fields'])
        self.assertEqual(self.sql('SELECT inn,ogrn FROM suppliers WHERE id=%s',
                                  (self.supplier_id,)), [('7412345678', '1234567890123')])

    def test_malformed_identity_rejects_entire_update_without_losing_profile(self):
        for key, value in [('inn', 'ИНН 7412345678'), ('inn', '74/12345678'),
                           ('inn', '７４１２３４５６７８'), ('inn', '74123456789'),
                           ('ogrn', '12345678901234'), ('ogrn', '1234567890123x')]:
            with self.subTest(key=key, value=value):
                before = self.api('supplier', 'GET', self.path())
                response = self.put('supplier', self.supplier_id, {
                    key: value, 'phone': 'Must never persist',
                    'expectedProfileVersion': before['version'],
                })
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.api('supplier', 'GET', self.path()), before)

    def test_registered_cabinet_inn_collision_rejects_whole_update(self):
        self.sql("UPDATE suppliers SET inn='75 - 12345678' WHERE id=%s", (self.other_id,))
        before = self.api('supplier', 'GET', self.path())
        other = self.api('stranger_supplier', 'GET', self.path(self.other_id))
        response = self.put('supplier', self.supplier_id, {
            'inn': '7512345678', 'bank': 'Must never persist',
            'expectedProfileVersion': before['version'],
        })
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn('кабинет', response.json()['detail'])
        self.assertEqual(response.json()['code'], 'supplier_identity_conflict')
        self.assertEqual(self.api('supplier', 'GET', self.path()), before)
        self.assertEqual(self.api('stranger_supplier', 'GET', self.path(self.other_id)), other)

    def test_registered_cabinet_ogrn_collision_rejects_whole_update(self):
        self.sql("UPDATE suppliers SET ogrn='12345\u00a067890123' WHERE id=%s", (self.other_id,))
        before = self.api('supplier', 'GET', self.path())
        response = self.put('supplier', self.supplier_id, {
            'ogrn': '1234567890123', 'phone': 'Must never persist',
            'expectedProfileVersion': before['version'],
        })
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.api('supplier', 'GET', self.path()), before)

    def test_concurrent_cabinets_claiming_same_unused_inn_have_one_winner(self):
        from backend.features.supplier_access import profile
        actors = [('supplier', self.supplier_id), ('stranger_supplier', self.other_id)]
        before = {actor: self.api(actor, 'GET', self.path(sid)) for actor, sid in actors}
        # Synchronize HTTP requests at the public update boundary, retaining all
        # real SQL, authorization, transactions and lock acquisition underneath.
        entered = Barrier(2)
        original = profile.update

        def together(*args, **kwargs):
            entered.wait(timeout=10)
            return original(*args, **kwargs)

        def claim(pair):
            actor, sid = pair
            response = self.put(actor, sid, {
                'inn': '7612345678', 'phone': 'New identity ' + actor,
                'expectedProfileVersion': before[actor]['version'],
            })
            return actor, sid, response

        with patch.object(profile, 'update', together), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, actors))
        self.assertEqual(sorted(r.status_code for _, _, r in results), [200, 409],
                         [(actor, r.status_code, r.text) for actor, _, r in results])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM suppliers WHERE inn='7612345678'"), [(1,)])
        for actor, sid, response in results:
            after = self.api(actor, 'GET', self.path(sid))
            if response.status_code == 409:
                self.assertEqual(after, before[actor])
            else:
                self.assertEqual(after['fields']['inn'], '7612345678')
                self.assertEqual(after['fields']['phone'], 'New identity ' + actor)

    def test_forbidden_roles_do_not_modify_or_disclose_profile(self):
        before = self.api('supplier', 'GET', self.path())
        for actor in ('manager', 'stranger_supplier', 'director'):
            with self.subTest(actor=actor):
                response = self.put(actor, self.supplier_id, {'inn': '7712345678'})
                self.assertEqual(response.status_code, 403, response.text)
                self.api(actor, 'GET', self.path(), expected=403)
        self.assertEqual(self.api('supplier', 'GET', self.path()), before)

    def test_profile_change_preserves_published_party_snapshot_and_relationships(self):
        offer, path, body = self.quote()
        saved = self.api('supplier', 'PUT', path, body)
        links = self.sql('SELECT row_to_json(l)::text FROM company_supplier_links l ORDER BY id')
        self.api('supplier', 'PUT', self.path(), {'inn': '7812345678', 'phone': 'Current contact'})
        buyer_offer = next(row for row in self.api('director', 'GET', '/supplier-offers')
                           if row['id'] == offer['id'])
        supplier_offer = next(row for row in self.api('supplier', 'GET', '/supplier-offers')
                              if row['id'] == offer['id'])
        self.assertEqual(buyer_offer['partySnapshot'], saved['partySnapshot'])
        self.assertEqual(supplier_offer['partySnapshot'], saved['partySnapshot'])
        self.assertEqual(self.sql('SELECT row_to_json(l)::text FROM company_supplier_links l ORDER BY id'), links)
        self.assertNotIn(offer['id'], [row['id'] for row in self.api('stranger', 'GET', '/supplier-offers')])
        self.assertNotIn(offer['id'], [row['id'] for row in self.api('stranger_supplier', 'GET', '/supplier-offers')])
