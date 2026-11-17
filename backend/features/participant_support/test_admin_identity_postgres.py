"""Admin legal identity changes use exact tenant provenance and canonical locks."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from .test_duplicate_merge_postgres import AdminDuplicateMergePostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AdminIdentityPostgresTests(unittest.TestCase):
    sql, api, seed = Base.sql, Base.api, Base.seed
    duplicate_review, complete_inn = Base.duplicate_review, Base.complete_inn

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)

    def setUp(self):
        flags = patch.dict(os.environ, PARTICIPANT_HISTORY_MERGE_ENABLED='1')
        flags.start()
        self.addCleanup(flags.stop)

    def cards(self):
        source, target = self.seed(), self.seed(owned=True)
        inn = f'76{source:08d}'
        return source, target, inn

    def distinct_cabinet(self):
        sid = self.seed(owned=True)
        uid = self.sql("INSERT INTO users(name,email,password,role,active) VALUES(%s,%s,'unused','поставщик',TRUE) RETURNING id",
                       ('Synthetic distinct owner', f'identity-{sid}@local.invalid'))[0][0]
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s', (uid, sid))
        return sid

    def snapshot(self, ids):
        return {table: self.sql('SELECT to_jsonb(t) FROM '+table+' t WHERE '+column+'=ANY(%s) ORDER BY id', (ids,))
                for table, column in (('suppliers', 'id'), ('company_supplier_links', 'supplier_id'),
                                      ('supplier_invoices', 'supplier_id'))}

    def audit_count(self, target):
        return self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_missing_inn_completed' AND entity_id=%s", (target,))

    def connection_review(self, source):
        return self.api('admin', 'GET', f'/system/companies/2/participants/{source}/connection-preview')

    def test_formatted_existing_cabinet_blocks_without_disclosure_or_mutation(self):
        source, target, inn = self.cards()
        other = self.distinct_cabinet()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        formatted = inn[:2]+' - '+inn[2:]
        self.sql("UPDATE suppliers SET inn=%s,name='Private competitor name' WHERE id=%s", (formatted, other))
        before = self.snapshot([source, target, other])
        review = self.duplicate_review(source, target)
        self.complete_inn(source, review, expected=409)
        self.assertFalse(review['canCompleteInn'])
        self.assertEqual(review['innCompletionBlocker'], 'С этим ИНН уже есть другой кабинет. Нужна проверка реквизитов')
        self.assertNotIn('Private competitor name', str(review))
        self.assertEqual(self.snapshot([source, target, other]), before)
        self.assertEqual(self.audit_count(target), [(0,)])

    def test_formatted_source_completes_only_target_preserving_invoice_and_access(self):
        source, target, inn = self.cards()
        formatted = inn[:3]+'\u00a0-'+inn[3:]
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (formatted, source))
        invoice = self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount,paid_note) VALUES(2,%s,500,123,'Original payment') RETURNING id", (source,))[0][0]
        before = self.snapshot([source, target])
        review = self.duplicate_review(source, target)
        result = self.complete_inn(source, review)
        self.assertEqual(review['sourceInn'], inn)
        self.assertEqual(result['inn'], inn)
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [(inn,)])
        after = self.snapshot([source, target])
        self.assertEqual(after['supplier_invoices'], before['supplier_invoices'])
        self.assertEqual(after['company_supplier_links'], before['company_supplier_links'])
        self.assertEqual(after['suppliers'][0], before['suppliers'][0])
        self.assertNotIn(invoice, [row['id'] for row in self.api('supplier', 'GET', '/supplier-invoices')])
        self.assertEqual(self.audit_count(target), [(1,)])
        self.complete_inn(source, review, expected=409)
        next_step = self.connection_review(source)
        self.assertEqual(next_step['scenario'], 'merge_cards')
        self.assertEqual(next_step['cabinet']['supplierId'], target)
        self.assertFalse(next_step['canApply'])
        self.assertIn('HISTORICAL_ACCESS_REVIEW_REQUIRED', [b['code'] for b in next_step['blockers']])

    def test_malformed_source_cannot_complete_or_mutate(self):
        for value in ('ИНН 7612345678', '7612345678x', '７６１２３４５６７８'):
            with self.subTest(value=value):
                source, target, _ = self.cards()
                self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (value, source))
                before = self.snapshot([source, target])
                self.duplicate_review(source, target, expected=409)
                self.assertEqual(self.snapshot([source, target]), before)
                self.assertEqual(self.audit_count(target), [(0,)])

    def test_changed_source_invalidates_review_without_replacing_target(self):
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        review = self.duplicate_review(source, target)
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', ('78'+inn[2:], source))
        before = self.snapshot([source, target])
        self.complete_inn(source, review, expected=409)
        self.assertEqual(self.snapshot([source, target]), before)
        self.assertEqual(self.audit_count(target), [(0,)])

    def test_completion_requires_company_account_and_admin_authority(self):
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        review = self.duplicate_review(source, target)
        body = dict(targetSupplierId=target, expectedReview=review['reviewVersion'], confirmed=True,
                    reason='Synthetic explicit original document review')
        before = self.snapshot([source, target])
        self.api('director', 'POST', f'/system/companies/2/participants/{source}/duplicate-complete-inn', body, expected=403)
        self.api('admin', 'POST', f'/system/companies/3/participants/{source}/duplicate-complete-inn', body, expected=404)
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(99,'Synthetic foreign account','pro','active')")
        self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(99,'Synthetic foreign company',99,TRUE,'pro')")
        self.api('admin', 'POST', f'/system/companies/99/participants/{source}/duplicate-complete-inn', body, expected=404)
        self.assertEqual(self.snapshot([source, target]), before)
        self.assertEqual(self.audit_count(target), [(0,)])

    def test_connection_diagnosis_matches_formatted_source_without_granting_history(self):
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn[:2]+'-'+inn[2:], source))
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, target))
        before = self.snapshot([source, target])
        review = self.connection_review(source)
        self.assertEqual(review['scenario'], 'merge_cards')
        self.assertEqual(review['cabinet']['supplierId'], target)
        self.assertFalse(review['canApply'])
        self.assertIn('HISTORICAL_ACCESS_REVIEW_REQUIRED', [b['code'] for b in review['blockers']])
        self.assertNotIn('LEGAL_IDENTITY_CONFLICT', [b['code'] for b in review['blockers']])
        self.assertEqual(self.snapshot([source, target]), before)

    def test_connection_diagnosis_matches_formatted_cabinet(self):
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn[:2]+' -'+inn[2:], target))
        review = self.connection_review(source)
        self.assertEqual(review['scenario'], 'merge_cards')
        self.assertEqual(review['cabinet']['supplierId'], target)
        self.assertNotIn('LEGAL_IDENTITY_CONFLICT', [b['code'] for b in review['blockers']])
        self.assertFalse(review['canApply'])

    def test_malformed_secondary_ogrn_is_not_ignored_when_inn_matches(self):
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=ANY(%s)', (inn, [source, target]))
        self.sql("UPDATE suppliers SET ogrn='invalid-1234567890123' WHERE id=%s", (source,))
        review = self.connection_review(source)
        self.assertTrue({'LEGAL_IDENTITY_CONFLICT', 'LEGAL_IDENTITY_REQUIRED'} & {b['code'] for b in review['blockers']})
        self.assertFalse(review['canApply'])

    def test_profile_and_completion_share_canonical_lock_and_only_one_identity_wins(self):
        from fastapi.testclient import TestClient
        from ..supplier_access import profile
        source, target, inn = self.cards()
        competitor = self.distinct_cabinet()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn[:2]+' -'+inn[2:], source))
        review = self.duplicate_review(source, target)
        locked, release = Event(), Event()
        holder = []
        real_load = profile.load
        def paused_load(cur, supplier_id, lock=False):
            result = real_load(cur, supplier_id, lock)
            if supplier_id == competitor and lock:
                cur.execute('SELECT pg_backend_pid() AS pid')
                holder.append(cur.fetchone()['pid'])
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic profile lock release timed out')
            return result
        token = self.main.create_auth_token(self.fixture['users']['admin'], two_factor_passed=True)
        def request(kind):
            with TestClient(self.main.app) as client:
                headers = {'Authorization': 'Bearer '+token}
                if kind == 'profile':
                    result = client.put(f'/suppliers/{competitor}/requisites', json={'inn': inn}, headers=headers)
                else:
                    result = client.post(f'/system/companies/2/participants/{source}/duplicate-complete-inn',
                        json=dict(targetSupplierId=target, expectedReview=review['reviewVersion'], confirmed=True,
                                  reason='Synthetic confirmed source document'), headers=headers)
                return result.status_code
        blocked = False
        with patch.object(profile, 'load', side_effect=paused_load), ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(request, 'profile')
            try:
                self.assertTrue(locked.wait(5), 'Profile must hold its canonical key before completion starts')
                completion = pool.submit(request, 'complete')
                deadline = time.monotonic()+4
                while time.monotonic() < deadline:
                    blocked = bool(self.sql('SELECT 1 FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid))', (holder[0],)))
                    if blocked or completion.done():
                        break
                    release.wait(.02)
            finally:
                release.set()
            statuses = [writer.result(timeout=10), completion.result(timeout=10)]
        self.assertTrue(blocked, 'Admin completion must wait on the same canonical key as profile')
        self.assertEqual(statuses, [200, 409])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [(None,)])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (competitor,)), [(inn,)])
        self.assertEqual(self.audit_count(target), [(0,)])

    def test_registration_waits_for_completion_and_cannot_create_another_owner(self):
        from fastapi.testclient import TestClient
        from . import duplicate_merge
        source, target, inn = self.cards()
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn[:2]+' -'+inn[2:], source))
        review = self.duplicate_review(source, target)
        invite = self.api('stranger', 'POST', '/invite-codes',
                          dict(role='поставщик', expiresInDays=1), **{'X-Company-Id': '3'})
        email = f'competing-registration-{source}@local.invalid'
        payload = dict(code=invite['code'], name='Synthetic competing registration',
                       companyName='Synthetic competing registration', inn=inn,
                       email=email, password='Synthetic-local-only!2026')
        token = self.main.create_auth_token(self.fixture['users']['admin'], two_factor_passed=True)
        locked, release = Event(), Event()
        holder = []
        real_preview = duplicate_merge.checked_preview
        def paused_preview(cur, user, company_id, source_id, target_id):
            result = real_preview(cur, user, company_id, source_id, target_id)
            if source_id == source and target_id == target:
                cur.execute('SELECT pg_backend_pid() AS pid')
                holder.append(cur.fetchone()['pid'])
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic completion release timed out')
            return result
        def request(kind):
            with TestClient(self.main.app) as client:
                if kind == 'registration':
                    result = client.post('/register', json=payload)
                else:
                    result = client.post(f'/system/companies/2/participants/{source}/duplicate-complete-inn',
                        json=dict(targetSupplierId=target, expectedReview=review['reviewVersion'], confirmed=True,
                                  reason='Synthetic confirmed source document'),
                        headers={'Authorization': 'Bearer '+token})
                return result.status_code
        blocked = False
        with patch.object(duplicate_merge, 'checked_preview', side_effect=paused_preview), ThreadPoolExecutor(max_workers=2) as pool:
            completion = pool.submit(request, 'complete')
            try:
                self.assertTrue(locked.wait(5), 'Completion must lock identity before registration starts')
                registration = pool.submit(request, 'registration')
                deadline = time.monotonic()+4
                while time.monotonic() < deadline:
                    blocked = bool(self.sql('SELECT 1 FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid))', (holder[0],)))
                    if blocked or registration.done():
                        break
                    release.wait(.02)
            finally:
                release.set()
            statuses = [completion.result(timeout=10), registration.result(timeout=10)]
        self.assertTrue(blocked, 'Registration must wait on the canonical key held by completion')
        self.assertEqual(statuses, [200, 409])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [(inn,)])
        self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (email,)), [])
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])
        self.assertEqual(self.audit_count(target), [(1,)])
