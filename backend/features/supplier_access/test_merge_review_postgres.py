"""Review/confirm evidence and history boundaries on disposable PostgreSQL."""
import os
import unittest

from . import test_company_merge_postgres as base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MergeReviewPostgresTests(unittest.TestCase):
    sql = base.CompanyMergePostgresTests.sql
    api = base.CompanyMergePostgresTests.api
    seed = base.CompanyMergePostgresTests.seed
    review = base.CompanyMergePostgresTests.review

    @classmethod
    def setUpClass(cls):
        base.CompanyMergePostgresTests.setUpClass.__func__(cls)

    def body(self, review):
        return dict(companyId=2, confirmed=True, sourceId=review['sourceId'],
                    targetVersion=review['targetVersion'], sourceVersion=review['sourceVersion'],
                    expectedReview=review.get('reviewVersion', 'unbound-old-preview'))

    def confirm(self, review, *, expected=200, actor='director', body=None, **headers):
        return self.api(actor, 'POST', f"/suppliers/{review['targetId']}/merge",
                        self.body(review) if body is None else body, expected=expected, **headers)

    def snapshot(self, source, target):
        ids = [source, target]
        return dict(
            suppliers=self.sql('SELECT to_jsonb(s) FROM suppliers s WHERE id=ANY(%s) ORDER BY id', (ids,)),
            links=self.sql('SELECT to_jsonb(l) FROM company_supplier_links l WHERE supplier_id=ANY(%s) ORDER BY id', (ids,)),
            invoices=self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE supplier_id=ANY(%s) ORDER BY id', (ids,)),
            merges=self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_cards_merged'"),
        )

    def assert_stale_rejected(self, review):
        before = self.snapshot(review['sourceId'], review['targetId'])
        self.confirm(review, expected=409)
        self.assertEqual(self.snapshot(review['sourceId'], review['targetId']), before)

    def test_changed_invoice_contents_with_same_count_reject_old_review(self):
        source, target, invoice, _ = self.seed()
        review = self.review(source, target)
        self.sql('UPDATE supplier_invoices SET amount=225,paid_amount=75 WHERE id=%s', (invoice,))
        self.assertEqual(self.review(source, target)['documents'], review['documents'])
        self.assert_stale_rejected(review)
        self.assertTrue(self.confirm(self.review(source, target))['ok'])
        self.assertEqual(self.sql('SELECT supplier_id,amount,paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), [(source, 225, 75)])

    def test_inserted_invoice_rejects_old_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,80,0)', (source,))
        self.assert_stale_rejected(review)

    def test_changed_legal_identity_without_link_version_rejects_old_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        self.sql("UPDATE suppliers SET inn='7891234567' WHERE id=%s", (target,))
        self.assertEqual(self.review(source, target)['targetVersion'], review['targetVersion'])
        self.assert_stale_rejected(review)

    def test_changed_name_without_link_version_rejects_old_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        self.sql("UPDATE suppliers SET name='Renamed after review' WHERE id=%s", (source,))
        self.assert_stale_rejected(review)

    def test_changed_source_bank_without_link_version_rejects_old_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        self.sql("UPDATE suppliers SET bank='Source bank changed after review' WHERE id=%s", (source,))
        self.assert_stale_rejected(review)

    def test_changed_target_bank_without_link_version_rejects_old_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        self.sql("UPDATE suppliers SET bank='Target bank changed after review' WHERE id=%s", (target,))
        self.assert_stale_rejected(review)

    def test_old_client_without_review_evidence_is_rejected_without_mutation(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        body = self.body(review)
        del body['expectedReview']
        before = self.snapshot(source, target)
        result = self.confirm(review, body=body, expected=409)
        self.assertTrue(result.get('detail'))
        self.assertEqual(self.snapshot(source, target), before)

    def test_another_pairs_review_cannot_confirm_current_pair(self):
        source, target, _, _ = self.seed()
        other_source, other_target, _, _ = self.seed()
        first, other = self.review(source, target), self.review(other_source, other_target)
        before = self.snapshot(source, target)
        body = dict(self.body(first), expectedReview=other.get('reviewVersion', 'unbound-other-review'))
        self.confirm(first, body=body, expected=409)
        self.assertEqual(self.snapshot(source, target), before)

    def test_foreign_company_and_disallowed_role_cannot_confirm_review(self):
        source, target, _, _ = self.seed()
        review = self.review(source, target)
        before = self.snapshot(source, target)
        self.confirm(review, body=dict(self.body(review), companyId=3),
                     actor='stranger', expected=404, **{'X-Company-Id': '3'})
        for actor in ('stranger', 'foreman'):
            self.confirm(review, actor=actor, expected=403, **{'X-Company-Id': '2'})
        self.assertEqual(self.snapshot(source, target), before)

    def test_current_review_preserves_original_history_and_replay_changes_nothing(self):
        source, target, invoice, _ = self.seed()
        before = self.snapshot(source, target)
        review = self.review(source, target)
        self.assertTrue(self.confirm(review)['ok'])
        after = self.snapshot(source, target)
        self.assertEqual(after['suppliers'], before['suppliers'])
        self.assertEqual(after['invoices'], before['invoices'])
        self.assertEqual(self.sql('SELECT supplier_id,amount,paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), [(source, 200, 50)])
        rows = self.api('director', 'GET', '/suppliers', **{'X-Company-Id': '2'})
        for sid in (source, target):
            row = next(row for row in rows if row['id'] == sid)
            self.assertEqual(row['canonicalSupplierId'], target)
            self.assertEqual(row['relatedSupplierIds'], [source, target])
        self.confirm(review, expected=409)
        self.assertEqual(self.snapshot(source, target), after)
        self.assertIsInstance(review.get('reviewVersion'), str)
        self.assertTrue(review['reviewVersion'])

    def test_two_concurrent_confirmations_produce_one_merge_and_preserve_history(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from fastapi.testclient import TestClient

        source, target, _, _ = self.seed()
        review = self.review(source, target)
        before = self.snapshot(source, target)
        token = self.main.create_auth_token(self.fixture['users']['director'], two_factor_passed=True)
        barrier = Barrier(2)

        def submit():
            with TestClient(self.main.app) as client:
                barrier.wait(timeout=10)
                return client.post(f'/suppliers/{target}/merge', json=self.body(review), headers={
                    'Authorization': 'Bearer ' + token, 'X-Company-Id': '2',
                })

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            responses = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409],
                         [response.text for response in responses])
        after = self.snapshot(source, target)
        self.assertEqual(after['suppliers'], before['suppliers'])
        self.assertEqual(after['invoices'], before['invoices'])
        self.assertEqual(after['merges'][0][0], before['merges'][0][0] + 1)

    def test_reviewed_document_update_waits_until_confirmation_commits(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from time import monotonic
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from . import company_merge

        source, target, invoice, _ = self.seed()
        review = self.review(source, target)
        token = self.main.create_auth_token(self.fixture['users']['director'], two_factor_passed=True)
        reviewed, release_confirm, writer_ready = Event(), Event(), Event()
        writer_state = {}
        original_preview = company_merge.preview_for_pair

        def pause_after_review(*args, **kwargs):
            result = original_preview(*args, **kwargs)
            reviewed.set()
            if not release_confirm.wait(timeout=10):
                raise RuntimeError('Test did not release merge confirmation')
            return result

        def submit():
            with TestClient(self.main.app) as client:
                return client.post(f'/suppliers/{target}/merge', json=self.body(review), headers={
                    'Authorization': 'Bearer ' + token, 'X-Company-Id': '2',
                })

        def update_invoice():
            conn = self.main.get_db()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='10s'")
                    cur.execute('SELECT pg_backend_pid()')
                    writer_state['pid'] = cur.fetchone()[0]
                    writer_ready.set()
                    cur.execute('UPDATE supplier_invoices SET amount=225 WHERE id=%s', (invoice,))
                conn.commit()
            finally:
                conn.close()

        with patch.object(company_merge, 'preview_for_pair', side_effect=pause_after_review):
            with ThreadPoolExecutor(max_workers=2) as pool:
                confirm = pool.submit(submit)
                try:
                    self.assertTrue(reviewed.wait(timeout=10))
                    writer = pool.submit(update_invoice)
                    self.assertTrue(writer_ready.wait(timeout=5))
                    deadline, blocked = monotonic() + 5, False
                    while monotonic() < deadline and not writer.done():
                        blocked = bool(self.sql('SELECT pg_blocking_pids(%s)', (writer_state['pid'],))[0][0])
                        if blocked:
                            break
                        release_confirm.wait(timeout=.01)
                    self.assertTrue(blocked, 'Document writer must be blocked by the confirmed review transaction')
                    self.assertFalse(writer.done())
                finally:
                    release_confirm.set()
                response = confirm.result(timeout=15)
                self.assertEqual(response.status_code, 200, response.text)
                writer.result(timeout=15)
        self.assertEqual(self.sql('SELECT supplier_id,amount,paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), [(source, 225, 50)])
