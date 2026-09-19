"""Actual session/HTTP/company authority and transactions on synthetic PostgreSQL."""
import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch

from . import test_postgres_chain as baseline


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CompanyDirectoryPostgresTests(unittest.TestCase):
    api = baseline.PostgresSupplyChainTests.api
    sql = baseline.PostgresSupplyChainTests.sql

    @classmethod
    def setUpClass(cls):
        from .test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)
        conn = cls.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM company_supplier_links')
                cur.execute("INSERT INTO suppliers(name,inn) VALUES('Legacy catalog','7709990000') RETURNING id")
                cls.legacy_supplier = cur.fetchone()[0]
                cur.execute("INSERT INTO company_supplier_links(company_id,supplier_id,local_category) VALUES(2,%s,'Legacy')", (cls.legacy_supplier,))
                adapter = types.ModuleType('alembic')
                adapter.op = types.SimpleNamespace(execute=cur.execute)
                with patch.dict(sys.modules, {'alembic': adapter}):
                    migration = importlib.import_module('migrations.versions.0022_supplier_company_catalog')
                    with patch.object(migration, 'op', adapter.op):
                        migration.upgrade()
                cls.migration = migration
        finally:
            conn.close()

    def body(self, suffix):
        return {'name': 'Каталог ' + suffix, 'inn': '770000' + suffix.zfill(4),
                'category': 'Компания А', 'rating': 2, 'notes': 'Только А',
                'contractNumber': 'PRIVATE-A', 'phone': '+70000000001'}

    def create(self, suffix):
        return self.api('director', 'POST', '/suppliers', self.body(suffix), **{'X-Company-Id': '2'})

    def test_two_companies_share_identity_but_never_commercial_fields(self):
        first = self.create('1')
        second = self.api('stranger', 'POST', '/suppliers', {
            **self.body('1'), 'name': 'Чужая попытка переименования', 'rating': 5,
            'category': 'Компания Б', 'notes': 'Только Б', 'contractNumber': 'PRIVATE-B',
        }, **{'X-Company-Id': '3'})
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(second['name'], first['name'])
        for actor, company, notes in (('director', 2, 'Только А'), ('stranger', 3, 'Только Б')):
            rows = self.api(actor, 'GET', '/suppliers', **{'X-Company-Id': str(company)})
            row = next(r for r in rows if r['id'] == first['id'])
            self.assertEqual(row['notes'], notes)
            self.assertEqual(row['companyId'], company)
        self.assertEqual(self.sql('SELECT notes,contract_number,user_id FROM suppliers WHERE id=%s', (first['id'],)), [(None, None, None)])

    def test_update_is_versioned_and_local(self):
        first = self.create('2')
        path = f"/suppliers/{first['id']}"
        changed = self.api('director', 'PUT', path, {'rating': 4, 'notes': 'Новая заметка', 'relationshipVersion': 1})
        self.assertEqual(changed['relationshipVersion'], 2)
        self.api('director', 'PUT', path, {'rating': 1, 'relationshipVersion': 1}, expected=409)
        self.api('stranger', 'PUT', path, {'rating': 1, 'relationshipVersion': 2}, expected=404)
        self.api('director', 'PUT', path, {'name': 'Подмена', 'relationshipVersion': 2}, expected=409)
        self.api('director', 'PUT', path + '/requisites', {'inn': '7709999999'}, expected=403)
        self.api('director', 'DELETE', path, expected=403)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM audit_log WHERE entity_type=%s AND entity_id=%s',
                                 ('company_supplier_link', first['companySupplierLinkId'])), [(2,)])

    def test_wrong_headers_roles_and_revoked_membership_fail_closed(self):
        self.api('director', 'GET', '/suppliers', expected=403, **{'X-Company-Id': '3'})
        self.api('director', 'GET', '/suppliers', expected=400, **{'X-Company-Mode': 'all_companies'})
        self.api('foreman', 'POST', '/suppliers', self.body('3'), expected=403)
        actor = self.fixture['users']['director']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (actor,))
        try:
            self.api('director', 'POST', '/suppliers', self.body('3'), expected=403)
            self.api('director', 'GET', '/suppliers', expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (actor,))

    def test_missing_schema_blocks_without_repair(self):
        self.sql('ALTER TABLE company_supplier_links RENAME COLUMN profile TO hidden_profile')
        try:
            self.api('director', 'GET', '/suppliers', expected=503)
            self.api('director', 'POST', '/suppliers', self.body('4'), expected=503)
        finally:
            self.sql('ALTER TABLE company_supplier_links RENAME COLUMN hidden_profile TO profile')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM suppliers WHERE inn=%s', (self.body('4')['inn'],)), [(0,)])

    def test_legacy_bootstrap_is_explicit_atomic_version_safe_and_replayable(self):
        import psycopg2.extras
        from .catalog_bootstrap import make_plan, apply_plan, digest
        legacy_statuses = ('На проверке', 'Нужно уточнение')
        ids = [self.sql("INSERT INTO suppliers(name,notes,contract_number,status) VALUES(%s,%s,%s,%s) RETURNING id",
                        ('Legacy no INN ' + str(i), 'Only company A', 'A-' + str(i), status))[0][0]
               for i, status in enumerate(legacy_statuses)]
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                plan = make_plan(cur, 2, ids)
                checksum = digest(plan)
                conn.rollback()
                self.assertNotIn('Only company A', str(plan))
                cur.execute('UPDATE suppliers SET inn=%s WHERE id=%s', ('7701234000', ids[0]))
                conn.commit()
                with self.assertRaisesRegex(ValueError, 'changed after review'):
                    apply_plan(cur, plan, checksum)
                conn.rollback()
                cur.execute('UPDATE suppliers SET inn=NULL WHERE id=%s', (ids[0],))
                conn.commit()
                with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                    apply_plan(cur, plan, 'wrong')
                conn.rollback()
                cur.execute('UPDATE suppliers SET notes=%s WHERE id=%s', ('Changed after review', ids[1]))
                conn.commit()
                with self.assertRaisesRegex(ValueError, 'changed after review'):
                    apply_plan(cur, plan, checksum)
                conn.rollback()
                self.assertEqual(self.sql('SELECT count(*) FROM company_supplier_links WHERE supplier_id=ANY(%s)', (ids,)), [(0,)])
                cur.execute('UPDATE suppliers SET notes=%s WHERE id=%s', ('Only company A', ids[1]))
                conn.commit()
                self.assertEqual(apply_plan(cur, plan, checksum)['created'], ids)
                conn.commit()
                self.assertEqual(apply_plan(cur, plan, checksum)['alreadyApplied'], ids)
                conn.commit()
                self.assertEqual(self.sql('SELECT company_id,profile->>\'notes\' FROM company_supplier_links WHERE supplier_id=ANY(%s)', (ids,)), [(2, 'Only company A')] * 2)
                self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_catalog_bootstrap'"), [(2,)])
                self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE supplier_id=ANY(%s) ORDER BY supplier_id', (ids,)), [(status,) for status in legacy_statuses])
                for sid, status in zip(ids, legacy_statuses):
                    updated = self.api('director', 'PUT', f'/suppliers/{sid}', {'notes': 'Only company A', 'relationshipVersion': 1})
                    self.assertEqual(updated['status'], status)
                cur.execute('UPDATE company_supplier_links SET contract_number=%s,version=version+1 WHERE supplier_id=%s', ('New company contract', ids[0]))
                conn.commit()
                with self.assertRaisesRegex(ValueError, 'must not be overwritten'):
                    apply_plan(cur, plan, checksum)
                conn.rollback()
        finally:
            conn.close()

    def test_audit_failure_rolls_back_global_identity_and_relationship(self):
        self.sql("ALTER TABLE audit_log ADD CONSTRAINT synthetic_audit_failure CHECK(action<>'supplier_relationship_created') NOT VALID")
        try:
            with self.assertRaises(Exception):
                self.create('5')
        finally:
            self.sql('ALTER TABLE audit_log DROP CONSTRAINT synthetic_audit_failure')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM suppliers WHERE inn=%s', (self.body('5')['inn'],)), [(0,)])

    def test_exact_legal_identity_never_links_by_name_or_email(self):
        first = self.create('6')
        second = self.api('director', 'POST', '/suppliers', {**self.body('7'), 'name': first['name'], 'email': 'same@example.test'})
        self.assertNotEqual(first['id'], second['id'])
        self.api('director', 'POST', '/suppliers', self.body('6'), expected=409)

    def test_supplier_cannot_read_company_notes_or_change_customer_directory(self):
        sid = self.fixture['supplierId']
        self.sql("UPDATE suppliers SET notes='PRIVATE-LEGACY',contract_number='SECRET',rating=1 WHERE id=%s", (sid,))
        rows = self.api('supplier', 'GET', '/suppliers')
        self.assertTrue(rows)
        self.assertTrue(all('notes' not in r and 'contract_number' not in r and 'rating' not in r for r in rows))
        self.api('supplier', 'POST', '/suppliers', self.body('8'), expected=403)
        self.api('supplier', 'PUT', f'/suppliers/{sid}/requisites', {'notes': 'Overwrite', 'contractNumber': 'Other'}, expected=422)
        self.assertEqual(self.sql('SELECT notes,contract_number FROM suppliers WHERE id=%s', (sid,)), [('PRIVATE-LEGACY', 'SECRET')])
        self.api('supplier', 'PUT', f'/suppliers/{sid}/requisites', {'specialization': 'Public description'})
        own_rows = self.api('director', 'GET', '/suppliers')
        self.assertTrue(all(row['specialization'] != 'Public description' for row in own_rows))
        self.api('stranger_supplier', 'PUT', f'/suppliers/{sid}/requisites', {'phone': '+7'}, expected=403)

    def test_name_or_email_does_not_grant_supplier_identity(self):
        name = self.sql('SELECT name FROM suppliers WHERE id=%s', (self.fixture['supplierId'],))[0][0]
        actor = self.sql("INSERT INTO users(name,email,password,role,active) VALUES(%s,'unbound@example.invalid','unused','поставщик',TRUE) RETURNING id", (name,))[0][0]
        self.fixture['users']['unbound'] = {'id': actor, 'name': name, 'email': 'unbound@example.invalid', 'role': 'поставщик'}
        self.assertEqual(self.api('unbound', 'GET', '/suppliers'), [])
        self.assertEqual(self.api('unbound', 'GET', '/supplier-offers'), [])

    def test_registration_invite_never_claims_existing_global_supplier(self):
        sid = self.fixture['supplierId']
        before = self.sql('SELECT user_id FROM suppliers WHERE id=%s', (sid,))
        self.sql("INSERT INTO invite_codes(code,role,supplier_id,created_by,company_id,platform_account_id) VALUES('CATALOG-NO-TAKEOVER','поставщик',%s,'Synthetic',2,1)", (sid,))
        response = self.client.post('/register', json={'code': 'CATALOG-NO-TAKEOVER', 'name': 'Attacker',
            'email': 'new-supplier@example.invalid', 'password': 'Synthetic-only-Password123!'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (sid,)), before)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE email='new-supplier@example.invalid'"), [(0,)])

    def test_new_supplier_registration_creates_only_its_own_identity_and_no_customer_membership(self):
        self.sql("INSERT INTO invite_codes(code,role,created_by,company_id,platform_account_id) VALUES('CATALOG-NEW-SUPPLIER','поставщик','Synthetic',2,1)")
        response = self.client.post('/register', json={'code': 'CATALOG-NEW-SUPPLIER', 'name': 'New supplier',
            'companyName': 'New independent supplier', 'inn': '7722223333',
            'email': 'new-independent@example.invalid', 'password': 'Synthetic-only-Password123!'})
        self.assertEqual(response.status_code, 200)
        rows = self.sql("SELECT u.id,u.company_id,u.platform_account_id,s.id FROM users u JOIN suppliers s ON s.user_id=u.id WHERE u.email='new-independent@example.invalid'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1:3], (None, None))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM user_company_roles WHERE user_id=%s', (rows[0][0],)), [(0,)])

    def test_legacy_link_uses_proven_company_account_and_can_be_updated(self):
        rows = self.api('director', 'GET', '/suppliers')
        legacy = next(row for row in rows if row['id'] == self.legacy_supplier)
        self.assertEqual(legacy['category'], 'Legacy')
        self.api('director', 'PUT', f'/suppliers/{self.legacy_supplier}', {'notes': 'Migrated', 'relationshipVersion': 1})
        self.assertEqual(self.sql('SELECT COUNT(*) FROM suppliers WHERE inn=%s', ('7709990000',)), [(1,)])

    def test_ogrn_only_creation_and_mismatched_ownership_migration_fail_closed(self):
        created = self.api('director', 'POST', '/suppliers', {'name': 'ОГРН', 'ogrn': '1162375052839'})
        self.assertEqual(created['ogrn'], '1162375052839')
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, patch.object(self.migration, 'op', types.SimpleNamespace(execute=cur.execute)):
                self.migration.downgrade()
                cur.execute('UPDATE company_supplier_links SET platform_account_id=999 WHERE supplier_id=%s', (created['id'],))
                with self.assertRaisesRegex(Exception, 'ownership requires reconciliation'):
                    self.migration.upgrade()
        finally:
            conn.rollback(); conn.close()
        self.assertIn(created['id'], [row['id'] for row in self.api('director', 'GET', '/suppliers')])

    def test_dispatch_rechecks_link_and_never_expands_unselected_aliases(self):
        f = self.fixture
        sid = f['supplierId']
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', ('7701234567', sid))
        link = self.api('director', 'POST', '/suppliers', {'name': 'Existing', 'inn': '7701234567'})
        item = {key: f[key] for key in ('materialName', 'quantity', 'unit', 'workPackage')}
        request = self.api('director', 'POST', '/supply-requests', {
            'companyId': 2, 'project': f['project'], 'workPackage': f['workPackage'], 'items': [item]})
        path = f"/supply-requests/{request['id']}"
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        candidates = self.api('director', 'GET', path + '/suggest-suppliers')
        self.assertIn(sid, [row['id'] for row in candidates['suppliers']])
        self.api('stranger', 'GET', path + '/suggest-suppliers', expected=403)
        self.api('director', 'GET', path + '/compare-kp', expected=409, **{'X-Company-Id': '3'})
        for version, status in enumerate(('Неактивный', 'На проверке', 'Нужно уточнение'), start=1):
            self.api('director', 'PUT', f'/suppliers/{sid}', {'status': status, 'relationshipVersion': version})
            self.api('director', 'POST', path + '/request-kp', {'supplierIds': [sid]}, expected=409)
            candidates = self.api('director', 'GET', path + '/suggest-suppliers')
            self.assertNotIn(sid, [row['id'] for row in candidates['suppliers']])
            self.assertEqual(self.sql('SELECT COUNT(*) FROM supplier_offers WHERE request_id=%s', (request['id'],)), [(0,)])
        self.api('director', 'PUT', f'/suppliers/{sid}', {'status': 'Активный', 'relationshipVersion': 4})
        with patch.object(self.main, 'supplier_group_scope_ids', return_value=[sid, 999999]), \
             patch.object(self.main, 'supplier_offer_targets_for_groups', side_effect=AssertionError('Implicit alias dispatch')):
            result = self.api('director', 'POST', path + '/request-kp', {'supplierIds': [sid], 'aiRecommendedIds': [sid]})
        self.assertEqual(result['supplierIds'], [sid])
        self.assertEqual(self.sql('SELECT supplier_id,ai_recommended FROM supplier_offers WHERE request_id=%s',
                                 (request['id'],)), [(sid, False)])

    def test_delivery_and_claim_disclosure_require_visible_coherent_addressing(self):
        f = self.fixture
        request_id = self.sql('''INSERT INTO supply_requests(company_id,project,material_name,quantity,unit,work_package,
            status,prorab_confirmed_at,director_approved_at) VALUES(2,%s,'Synthetic',1,'шт',%s,'КП запрошены',NOW(),NOW()) RETURNING id''',
            (f['project'], f['workPackage']))[0][0]
        offer_id = self.sql("INSERT INTO supplier_offers(company_id,request_id,supplier_id,status) VALUES(2,%s,%s,'Утверждено') RETURNING id",
                            (request_id, f['supplierId']))[0][0]
        recipient_id = self.sql('''INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,
            supplier_user_id,supplier_group_ids,visible_to_supplier) VALUES(2,%s,%s,%s,%s,%s,TRUE) RETURNING id''',
            (request_id, f['supplierId'], f['supplierId'], f['users']['supplier']['id'], [f['supplierId']]))[0][0]
        delivery_id = self.sql('''INSERT INTO supply_deliveries(company_id,request_id,offer_id,supplier_id,project,
            material_name,planned_quantity,unit,work_package) VALUES(2,%s,%s,%s,%s,'Synthetic',1,'шт',%s) RETURNING id''',
            (request_id, offer_id, f['supplierId'], f['project'], f['workPackage']))[0][0]
        claim_id = self.sql('''INSERT INTO supply_claims(delivery_id,request_id,offer_id,supplier_id,project,material_name,work_package)
            VALUES(%s,%s,%s,%s,%s,'Synthetic',%s) RETURNING id''',
            (delivery_id, request_id, offer_id, f['supplierId'], f['project'], f['workPackage']))[0][0]
        self.assertIn(delivery_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-deliveries')])
        self.assertIn(claim_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-claims')])
        self.api('supplier', 'PUT', f'/supply-claims/{claim_id}', {'resolution': 'Reply'}, expected=409)
        self.api('supplier', 'PUT', f'/supply-claims/{claim_id}', {'status': 'Закрыта'}, expected=409)
        self.api('stranger', 'PUT', f'/supply-claims/{claim_id}', {'resolution': 'Foreign'}, expected=409)
        self.api('stranger', 'PUT', f'/supply-deliveries/{delivery_id}/receive', {'receivedQuantity': 1}, expected=403)
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE id=%s', (recipient_id,))
        self.assertNotIn(delivery_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-deliveries')])
        self.assertNotIn(claim_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-claims')])
        self.api('supplier', 'PUT', f'/supply-claims/{claim_id}', {'resolution': 'Hidden'}, expected=403)
        self.assertEqual(self.sql('SELECT resolution FROM supply_claims WHERE id=%s', (claim_id,)), [(None,)])
        self.sql('UPDATE supply_request_recipients SET visible_to_supplier=TRUE WHERE id=%s', (recipient_id,))
        self.sql('UPDATE supply_deliveries SET company_id=3 WHERE id=%s', (delivery_id,))
        self.assertNotIn(delivery_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-deliveries')])
        self.assertNotIn(claim_id, [r['id'] for r in self.api('supplier', 'GET', '/supply-claims')])

    def test_delivery_check_revalidates_identity_membership_and_snapshot_after_model_latency(self):
        f = self.fixture
        uid = f['users']['director']['id']
        rid = self.sql("INSERT INTO supply_requests(company_id,project,material_name,quantity) VALUES(2,%s,'Synthetic',1) RETURNING id", (f['project'],))[0][0]
        oid = self.sql('INSERT INTO supplier_offers(company_id,request_id,supplier_id) VALUES(2,%s,%s) RETURNING id', (rid, f['supplierId']))[0][0]
        did = self.sql('''INSERT INTO supply_deliveries(company_id,request_id,offer_id,supplier_id,project,
            material_name,planned_quantity,unit,work_package) VALUES(2,%s,%s,%s,%s,'Synthetic',1,'шт',%s) RETURNING id''',
            (rid, oid, f['supplierId'], f['project'], f['workPackage']))[0][0]
        path = f'/supply-deliveries/{did}/ai-check'
        with patch.object(self.main, 'generate_supply_delivery_check', return_value='Synthetic result'):
            result = self.api('director', 'POST', path, {'documentText': 'Synthetic document'})
        self.assertEqual(result['result'], 'Synthetic result')
        self.sql('UPDATE supply_deliveries SET ai_check_result=NULL WHERE id=%s', (did,))
        cases = [
            ('UPDATE users SET active=FALSE WHERE id=%s', (uid,), 'UPDATE users SET active=TRUE WHERE id=%s', (uid,), 403),
            ('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (uid,),
             'UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (uid,), 403),
            ('UPDATE supply_deliveries SET planned_quantity=2 WHERE id=%s', (did,),
             'UPDATE supply_deliveries SET planned_quantity=1 WHERE id=%s', (did,), 409),
            ('UPDATE supplier_offers SET company_id=3 WHERE id=%s', (oid,),
             'UPDATE supplier_offers SET company_id=2 WHERE id=%s', (oid,), 409),
        ]
        for change, args, restore, restore_args, status in cases:
            with self.subTest(change=change):
                def delayed_model(*_args, **_kwargs):
                    self.sql(change, args)
                    return 'Must not persist'
                try:
                    with patch.object(self.main, 'generate_supply_delivery_check', side_effect=delayed_model) as model:
                        self.api('director', 'POST', path, {'documentText': 'Synthetic document'}, expected=status)
                    self.assertEqual(model.call_count, 1)
                    self.assertEqual(self.sql('SELECT ai_check_result FROM supply_deliveries WHERE id=%s', (did,)), [(None,)])
                finally:
                    self.sql(restore, restore_args)
        token = 'synthetic-delivery-check-session'
        session_id = self.sql('''INSERT INTO user_sessions(user_id,session_hash,expires_at,two_factor_passed)
            VALUES(%s,%s,NOW()+INTERVAL '1 hour',TRUE) RETURNING id''', (uid, self.main._session_token_hash(token)))[0][0]
        def revoke_session(*_args, **_kwargs):
            self.sql('UPDATE user_sessions SET revoked_at=NOW() WHERE id=%s', (session_id,))
            return 'Must not persist'
        with patch.object(self.main, 'generate_supply_delivery_check', side_effect=revoke_session):
            response = self.client.post(path, json={'documentText': 'Synthetic document'},
                cookies={self.main.AUTH_SESSION_COOKIE_NAME: token},
                headers={'X-CSRF-Token': self.main._create_csrf_token(token)})
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(self.sql('SELECT ai_check_result FROM supply_deliveries WHERE id=%s', (did,)), [(None,)])

    def test_supplier_archive_keeps_each_customers_documents_private_and_archives_without_deletion(self):
        sid = self.fixture['supplierId']
        own = self.api('director', 'POST', '/supplier-documents', {'supplierId': sid, 'title': 'Customer A contract'})
        other = self.api('stranger', 'POST', '/supplier-documents', {'supplierId': sid, 'title': 'Customer B contract'})
        personal = self.sql("INSERT INTO supplier_documents(supplier_id,title,notes) VALUES(%s,'Personal document','Own notes') RETURNING id", (sid,))[0][0]
        visible = [r['id'] for r in self.api('supplier', 'GET', '/supplier-documents')]
        self.assertIn(personal, visible)
        self.assertNotIn(own['id'], visible)
        self.assertNotIn(other['id'], visible)
        self.assertIn(own['id'], [r['id'] for r in self.api('director', 'GET', '/supplier-documents')])
        self.assertNotIn(other['id'], [r['id'] for r in self.api('director', 'GET', '/supplier-documents')])
        self.assertNotIn(own['id'], [r['id'] for r in self.api('stranger', 'GET', '/supplier-documents')])
        self.api('stranger', 'DELETE', f"/supplier-documents/{own['id']}", expected=403)
        self.api('director', 'DELETE', f"/supplier-documents/{own['id']}")
        self.assertNotIn(own['id'], [r['id'] for r in self.api('director', 'GET', '/supplier-documents')])
        self.assertEqual(self.sql('SELECT company_id,archived_at IS NOT NULL FROM supplier_documents WHERE id=%s', (own['id'],)), [(2, True)])
