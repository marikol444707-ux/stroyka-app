import os,unittest
from unittest.mock import patch
from . import test_email_attempts_postgres as support
from .email_attempts import EMAIL_REJECTED, EMAIL_UNCONFIRMED

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class EmailRetryPostgresTests(unittest.TestCase):
    setUpClass=classmethod(support.EmailAttemptsPostgresTests.setUpClass.__func__)
    api=support.EmailAttemptsPostgresTests.api
    sql=support.EmailAttemptsPostgresTests.sql
    quote=support.EmailAttemptsPostgresTests.quote
    queued=support.EmailAttemptsPostgresTests.queued
    state=support.EmailAttemptsPostgresTests.state
    dispatch=support.EmailAttemptsPostgresTests.dispatch

    def rejected(self):
        rid,recipient=self.queued()
        with patch.object(self.main,'_smtp_configured',return_value=True),patch.object(self.main,'_send_rfq_email',return_value={'outcome':'rejected','code':'smtp_rejected'}):
            self.dispatch(rid,recipient)
        self.assertEqual(self.state(recipient)[0],EMAIL_REJECTED)
        row=self.api('director','GET',f'/supply-requests/{rid}/recipients')[0]
        self.assertEqual(row['emailAttempts'][0]['outcome'],'rejected')
        return rid,recipient,row['emailRetryAttemptId']

    def test_retry_rejected_once_and_record_both_attempts(self):
        rid,recipient,attempt=self.rejected()
        path=f'/supply-requests/{rid}/recipients/{recipient}/retry-email'
        with patch.object(self.main,'_smtp_configured',return_value=True),patch.object(self.main,'_send_rfq_email',return_value=True) as send:
            self.api('director','POST',path,{'expectedAttemptId':attempt})
            self.api('director','POST',path,{'expectedAttemptId':attempt},expected=409)
            self.assertEqual(send.call_count,1)
        row=self.api('director','GET',f'/supply-requests/{rid}/recipients')[0]
        self.assertEqual([a['outcome'] for a in row['emailAttempts']],['accepted','rejected'])
        self.assertIsNone(row['emailRetryAttemptId'])

    def test_unknown_delivery_and_other_company_are_blocked(self):
        rid,recipient,attempt=self.rejected();path=f'/supply-requests/{rid}/recipients/{recipient}/retry-email'
        self.api('stranger','POST',path,{'expectedAttemptId':attempt},expected=403)
        self.api('supplier','POST',path,{'expectedAttemptId':attempt},expected=403)
        with patch.object(self.main,'_smtp_configured',return_value=True),patch.object(self.main,'_send_rfq_email',return_value=False) as send:
            self.api('director','POST',path,{'expectedAttemptId':attempt})
            self.api('director','POST',path,{'expectedAttemptId':attempt},expected=409)
            self.assertEqual(send.call_count,1)
        self.assertEqual(self.state(recipient)[0],EMAIL_UNCONFIRMED)

    def test_worker_restores_only_never_started_queue(self):
        rid,recipient=self.queued()
        worker=next(r.endpoint for r in self.main.app.routes if r.path=='/max/supplier-email/dispatch')
        with patch.object(self.main,'_smtp_configured',return_value=True),patch.object(self.main,'_send_rfq_email',return_value=False) as send:
            worker(limit=5,_bot={});worker(limit=5,_bot={})
            self.assertEqual(send.call_count,1)
        self.assertEqual(self.state(recipient)[0],EMAIL_UNCONFIRMED)

    def test_worker_ignores_archived_project_without_burning_attempt(self):
        rid,recipient=self.queued()
        worker=next(r.endpoint for r in self.main.app.routes if r.path=='/max/supplier-email/dispatch')
        self.sql('UPDATE projects SET archived=TRUE WHERE company_id=2 AND name=%s',(self.fixture['project'],))
        try:
            with patch.object(self.main,'_send_rfq_email') as send:
                self.assertEqual(worker(limit=5,_bot={})['checked'],0)
                send.assert_not_called()
            self.assertEqual(self.sql('SELECT count(*) FROM supplier_email_attempts WHERE recipient_id=%s',(recipient,)),[(0,)])
        finally:
            self.sql('UPDATE projects SET archived=FALSE WHERE company_id=2 AND name=%s',(self.fixture['project'],))
            self.sql('UPDATE supply_request_recipients SET visible_to_supplier=FALSE WHERE id=%s',(recipient,))
