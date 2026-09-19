"""Two buyer companies can notify the same supplier without sharing email state."""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from unittest.mock import patch

from backend.features.supplier_access import test_email_attempts_postgres as support
from backend.features.supplier_access.email_attempts import EMAIL_QUEUED, EMAIL_UNCONFIRMED


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'Requires isolated PostgreSQL')
class EmailTenantIsolationPostgresTests(unittest.TestCase):
    setUpClass = classmethod(support.EmailAttemptsPostgresTests.setUpClass.__func__)
    api = support.EmailAttemptsPostgresTests.api
    sql = support.EmailAttemptsPostgresTests.sql
    quote = support.EmailAttemptsPostgresTests.quote
    queued = support.EmailAttemptsPostgresTests.queued
    dispatch = support.EmailAttemptsPostgresTests.dispatch
    state = support.EmailAttemptsPostgresTests.state

    def test_shared_supplier_independent_content_state_and_authorization(self):
        request_a, recipient_a = self.queued()
        self.sql("UPDATE supply_requests SET notes='PRIVATE COMPANY A' WHERE id=%s", (request_a,))
        project_b = 'PRIVATE COMPANY B OBJECT'
        self.sql("INSERT INTO projects(name,company_id,status,archived) VALUES (%s,3,'В работе',FALSE)", (project_b,))
        # Explicit synthetic seed of the second approved workflow. The preceding
        # fixture already created A via the real HTTP approval/RFQ endpoints.
        request_b = self.sql('''INSERT INTO supply_requests
            (company_id,project,status,prorab_confirmed_at,director_approved_at,
             material_name,quantity,unit,notes,work_package)
            SELECT 3,%s,status,prorab_confirmed_at,director_approved_at,
                   material_name,quantity,unit,'PRIVATE COMPANY B',work_package
            FROM supply_requests WHERE id=%s RETURNING id''', (project_b, request_a))[0][0]
        self.sql('''INSERT INTO supplier_offers(request_id,company_id,supplier_id,status)
            SELECT %s,3,supplier_id,status FROM supplier_offers WHERE request_id=%s''', (request_b, request_a))
        recipient_b = self.sql('''INSERT INTO supply_request_recipients
            (company_id,request_id,supplier_id,target_supplier_id,supplier_user_id,
             visible_to_supplier,email_notification_status)
            SELECT 3,%s,supplier_id,target_supplier_id,supplier_user_id,TRUE,%s
            FROM supply_request_recipients WHERE id=%s RETURNING id''',
            (request_b, EMAIL_QUEUED, recipient_a))[0][0]
        captured = []
        def send(address, subject, body):
            captured.append((address, subject, body))
            return 'PRIVATE COMPANY A' in body
        with patch.object(self.main, '_smtp_configured', return_value=True), patch.object(self.main, '_send_email', side_effect=send):
            # Cross-company and cross-request combinations cannot claim anything.
            self.dispatch(request_a, recipient_a, company=3)
            self.dispatch(request_b, recipient_b, company=2)
            self.dispatch(request_a, recipient_b, company=2)
            self.dispatch(request_b, recipient_a, company=3)
            self.assertEqual(captured, [])
            self.api('stranger', 'POST', f'/supply-requests/{request_a}/request-kp', {'supplierIds': [self.fixture['supplierId']]}, expected=403)
            self.api('director', 'POST', f'/supply-requests/{request_b}/request-kp', {'supplierIds': [self.fixture['supplierId']]}, expected=403)
            self.assertEqual(captured, [])
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(self.dispatch, request_a, recipient_a, 2)
                b = pool.submit(self.dispatch, request_b, recipient_b, 3)
                a.result(timeout=10)
                b.result(timeout=10)
            self.dispatch(request_a, recipient_a, 2)
            self.dispatch(request_b, recipient_b, 3)
        self.assertEqual(len(captured), 2)
        self.assertEqual({row[0] for row in captured}, {'synthetic@example.com'})
        messages = {subject: body for _, subject, body in captured}
        body_a = messages['Запрос КП №' + str(request_a)]
        body_b = messages['Запрос КП №' + str(request_b)]
        self.assertIn('PRIVATE COMPANY A', body_a)
        self.assertNotIn('PRIVATE COMPANY B', body_a)
        self.assertIn('PRIVATE COMPANY B', body_b)
        self.assertNotIn('PRIVATE COMPANY A', body_b)
        self.assertIn('supplyRequestId=' + str(request_a), body_a)
        self.assertIn('supplyRequestId=' + str(request_b), body_b)
        self.assertEqual(self.state(recipient_a)[0], 'Отправлено')
        self.assertIsNotNone(self.state(recipient_a)[1])
        self.assertEqual(self.state(recipient_b), (EMAIL_UNCONFIRMED, None))
        self.api('stranger', 'GET', f'/supply-requests/{request_a}/recipients', expected=403)
        self.api('director', 'GET', f'/supply-requests/{request_b}/recipients', expected=403)
