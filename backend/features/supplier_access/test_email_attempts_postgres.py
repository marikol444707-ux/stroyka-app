"""Real recipient claims and HTTP RFQ; SMTP alone is synthetic."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

from backend.features.supplier_access import test_postgres_chain as chain
from backend.features.supplier_offers import test_response_postgres as response
from backend.features.supplier_access.email_attempts import EMAIL_QUEUED, EMAIL_UNCONFIRMED


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class EmailAttemptsPostgresTests(unittest.TestCase):
    setUpClass = classmethod(response.SupplierResponsePostgresTests.setUpClass.__func__)
    api = chain.PostgresSupplyChainTests.api
    sql = chain.PostgresSupplyChainTests.sql
    quote = response.SupplierResponsePostgresTests.quote

    def queued(self):
        # Leave the normal RFQ fixture on its non-deliverable address.
        self.sql("UPDATE suppliers SET email='synthetic@test.local' WHERE id=%s", (self.fixture['supplierId'],))
        offer, _, _ = self.quote()
        rid = offer['requestId']
        recipient = self.sql('SELECT id FROM supply_request_recipients WHERE request_id=%s', (rid,))[0][0]
        self.sql("UPDATE suppliers SET email='synthetic@example.com' WHERE id=%s", (self.fixture['supplierId'],))
        self.sql('UPDATE supply_request_recipients SET email_notification_status=%s WHERE id=%s', (EMAIL_QUEUED, recipient))
        return rid, recipient

    def state(self, recipient):
        return self.sql('SELECT email_notification_status,email_sent_at FROM supply_request_recipients WHERE id=%s', (recipient,))[0]

    def dispatch(self, rid, recipient, company=2):
        self.main._dispatch_supply_recipient_email(rid, company, recipient)

    def test_concurrent_workers_claim_before_smtp_and_send_once(self):
        rid, recipient = self.queued()
        entered, release = threading.Event(), threading.Event()
        def send(*_args):
            self.assertEqual(self.state(recipient), (EMAIL_UNCONFIRMED, None))
            entered.set()
            self.assertTrue(release.wait(10))
            return True
        with patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email', side_effect=send) as smtp:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.dispatch, rid, recipient)
                self.assertTrue(entered.wait(10))
                second = pool.submit(self.dispatch, rid, recipient)
                try:
                    second.result(timeout=10)
                finally:
                    release.set()
                first.result(timeout=10)
            self.dispatch(rid, recipient)
            self.assertEqual(smtp.call_count, 1)
        self.assertEqual(self.state(recipient)[0], 'Отправлено')
        self.assertIsNotNone(self.state(recipient)[1])

    def test_ambiguous_result_and_exception_never_resend_on_rfq_repeat(self):
        for outcome in (False, RuntimeError('lost acknowledgement')):
            rid, recipient = self.queued()
            smtp = Mock(side_effect=outcome) if isinstance(outcome, Exception) else Mock(return_value=outcome)
            with patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email', smtp):
                self.dispatch(rid, recipient)
                self.dispatch(rid, recipient)
                self.api('director', 'POST', f'/supply-requests/{rid}/request-kp', {'supplierIds': [self.fixture['supplierId']]})
            self.assertEqual(smtp.call_count, 1)
            self.assertEqual(self.state(recipient), (EMAIL_UNCONFIRMED, None))

    def test_database_commit_failure_before_or_after_smtp_cannot_duplicate(self):
        real_get_db = self.main.get_db
        class FailedCommit:
            def __init__(self, connection):
                self.connection = connection
            def __getattr__(self, name):
                return getattr(self.connection, name)
            @property
            def autocommit(self):
                return self.connection.autocommit
            @autocommit.setter
            def autocommit(self, value):
                self.connection.autocommit = value
            def commit(self):
                raise RuntimeError('synthetic database commit failure')
        for failure_at, expected_calls, expected_status in ((1, 0, EMAIL_QUEUED), (2, 1, EMAIL_UNCONFIRMED)):
            rid, recipient = self.queued()
            opened = []
            def connection():
                conn = real_get_db()
                opened.append(conn)
                return FailedCommit(conn) if len(opened) == failure_at else conn
            with patch.object(self.main, 'get_db', side_effect=connection), patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email', return_value=True) as smtp:
                self.dispatch(rid, recipient)
                self.assertEqual(smtp.call_count, expected_calls)
            self.assertEqual(self.state(recipient), (expected_status, None))
            if failure_at == 2:
                with patch.object(self.main, '_send_email') as smtp:
                    self.dispatch(rid, recipient)
                    smtp.assert_not_called()

    def test_live_scope_and_visibility_prevent_transmission(self):
        rid, recipient = self.queued()
        with patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email') as smtp:
            self.dispatch(rid, recipient, company=3)
            self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE id=%s', (recipient,))
            self.dispatch(rid, recipient)
            self.sql('UPDATE supply_request_recipients SET visible_to_supplier=TRUE WHERE id=%s', (recipient,))
            uid = self.fixture['users']['supplier']['id']
            self.sql('UPDATE users SET active=FALSE WHERE id=%s', (uid,))
            self.dispatch(rid, recipient)
            self.sql('UPDATE users SET active=TRUE WHERE id=%s', (uid,))
            self.sql("UPDATE supplier_offers SET status='Отозвано' WHERE request_id=%s", (rid,))
            self.dispatch(rid, recipient)
            smtp.assert_not_called()
        self.assertEqual(self.state(recipient), (EMAIL_QUEUED, None))

    def test_http_rfq_persists_before_smtp_and_refresh_reports_result(self):
        rid, recipient = self.queued()
        def send(*_args):
            self.assertEqual(self.sql('SELECT status FROM supply_requests WHERE id=%s', (rid,)), [('КП запрошены',)])
            self.assertEqual(self.state(recipient), (EMAIL_UNCONFIRMED, None))
            return True
        with patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email', side_effect=send) as smtp:
            result = self.api('director', 'POST', f'/supply-requests/{rid}/request-kp', {'supplierIds': [self.fixture['supplierId']]})
            self.assertEqual(result['notifications'][0]['emailStatus'], EMAIL_QUEUED)
            self.assertEqual(smtp.call_count, 1)
        refreshed = self.api('director', 'GET', f'/supply-requests/{rid}/recipients')[0]
        self.assertEqual(refreshed['emailNotificationStatus'], 'Отправлено')
        self.assertIsNotNone(refreshed['emailSentAt'])

    def test_deactivation_during_recipient_lock_wait_prevents_smtp(self):
        rid,recipient=self.queued()
        actor_id=self.fixture['users']['supplier']['id']
        held=self.main.get_db();held.autocommit=False
        cur=held.cursor();cur.execute('SELECT id FROM supply_request_recipients WHERE id=%s FOR UPDATE',(recipient,))
        try:
            with patch.object(self.main,'_smtp_configured',return_value=True),patch.object(self.main,'_send_email',return_value=True) as smtp:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    task=pool.submit(self.dispatch,rid,recipient)
                    try:
                        deadline=time.monotonic()+10
                        while time.monotonic()<deadline:
                            waiting=self.sql("SELECT query FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock'")
                            if any('SELECT id FROM supply_request_recipients' in query for (query,) in waiting):break
                            time.sleep(.025)
                        else:self.fail('worker did not reach recipient lock checkpoint')
                        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(actor_id,))
                    finally:held.commit()
                    task.result(timeout=10)
                smtp.assert_not_called()
        finally:
            held.rollback();cur.close();held.close()
            self.sql('UPDATE users SET active=TRUE WHERE id=%s',(actor_id,))
