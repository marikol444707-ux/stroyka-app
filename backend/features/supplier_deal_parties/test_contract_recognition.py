"""Real local authorization/SQL with synthetic protected storage bytes."""
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from . import test_contract_postgres as fixtures
from .contract_recognition import register_contract_recognition
from .test_contract_extraction import TEXT
from ..document_access.service import open_document_local_file


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS') == '1', 'local PostgreSQL opt-in')
class RecognitionPostgresTest(unittest.TestCase):
    setUp_parties = fixtures.ContractPostgresTest.setUp_parties
    put = fixtures.ContractPostgresTest.put

    def setUp(self):
        fixtures.ContractPostgresTest.setUp(self)
        with self.conn.cursor() as cur:
            cur.execute('''ALTER TABLE file_ownership ADD COLUMN file_url TEXT,
                ADD COLUMN storage_key TEXT, ADD COLUMN context TEXT DEFAULT 'supplier-contract',
                ADD COLUMN original_name TEXT DEFAULT 'contract.txt' ''')
            cur.execute("UPDATE file_ownership SET file_url='/uploads/company-12-common-supplier-contract/contract.txt'")
        self.opened = []
        self.content = TEXT.encode('utf-8')
        self.during_read = lambda: None

        def open_local(file_url):
            self.during_read()
            stream = io.BytesIO(self.content)
            self.opened.append((file_url, stream))
            return stream, len(self.content)

        self.storage = {'open_local_file': open_local, 'open_s3_object': None,
                        's3_enabled': lambda: False, 's3_urls_for_key': lambda key: (), 's3_prefixes': ('uploads',)}
        app = FastAPI()
        register_contract_recognition(app, {**self.deps, **self.storage})
        self.recognition = TestClient(app)

    def analyze(self, headers=None, **changes):
        return self.recognition.post('/supplier-offers/40/contract-recognition', headers=headers,
                                     json={'sourceFileId': 31, 'partyVersion': 1, 'expectedVersion': 0, **changes})

    def test_protected_text_to_three_parties_without_persistence(self):
        response = self.analyze()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['sourceFileId'], 31)
        self.assertEqual(data['sourceContentHash'], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(data['companyId'], 12)
        self.assertEqual(data['parties']['supplier']['fields']['inn']['value'], '7709876543')
        self.assertNotIn('file_url', response.text)
        self.assertNotIn('/uploads/', response.text)
        self.assertEqual(response.headers['cache-control'], 'private, no-store')
        self.assertTrue(self.opened[0][1].closed)
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_versions')
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute('SELECT retained_at FROM file_ownership WHERE id=31')
            self.assertIsNone(cur.fetchone()[0])

    def test_foreign_missing_deleting_and_wrong_project_files_never_open(self):
        for file_id in (32, 33, 34, 999):
            with self.subTest(file_id=file_id):
                self.assertEqual(self.analyze(sourceFileId=file_id).status_code, 403)
        self.assertEqual(self.opened, [])

    def test_supplier_cannot_recognize_customer_documents(self):
        self.user['role'] = 'поставщик'
        self.assertEqual(self.analyze().status_code, 403)
        self.assertEqual(self.opened, [])

    def test_lost_payer_access_blocks_before_storage(self):
        with self.conn.cursor() as cur:
            cur.execute('UPDATE user_company_roles SET active=FALSE WHERE company_id=99')
        self.assertEqual(self.analyze().status_code, 403)
        self.assertEqual(self.opened, [])

    def test_stale_versions_rejected_before_storage(self):
        self.assertEqual(self.analyze(partyVersion=2).status_code, 409)
        self.assertEqual(self.analyze(expectedVersion=1).status_code, 409)
        self.assertEqual(self.opened, [])

    def test_client_cannot_supply_text_url_or_expected_inn(self):
        for extra in ({'text': TEXT}, {'fileUrl': 'https://example.invalid'}, {'buyerInn': '7701234567'}, {'sourceFileId': True}):
            self.assertEqual(self.analyze(**extra).status_code, 422)
        self.assertEqual(self.opened, [])

    def test_storage_pointer_must_match_owner_even_when_row_matches(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET file_url='/uploads/company-99-common-supplier-contract/x.txt' WHERE id=31")
        self.assertEqual(self.analyze().status_code, 409)
        self.assertEqual(self.opened, [])

    def test_image_is_explicitly_unsupported_not_empty_success(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET original_name='contract.png' WHERE id=31")
        self.assertEqual(self.analyze().status_code, 415)
        self.assertEqual(self.opened, [])

    def test_pdf_to_three_party_suggestions_through_authorized_route(self):
        from .test_contract_pdf import synthetic_pdf
        self.content = synthetic_pdf()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET original_name='contract.pdf' WHERE id=31")
        response = self.analyze()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['parties']['payer']['fields']['inn']['value'], '7707654321')
        self.assertEqual(response.json()['sourceContentHash'], hashlib.sha256(self.content).hexdigest())
        self.assertTrue(self.opened[0][1].closed)

    def test_unauthorized_pdf_does_not_start_parser(self):
        from unittest.mock import patch
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET original_name='contract.pdf' WHERE id=32")
        with patch('backend.features.supplier_deal_parties.contract_text_source.extract_pdf_text') as parser:
            self.assertEqual(self.analyze(sourceFileId=32).status_code, 403)
            parser.assert_not_called()

    def test_oversized_or_invalid_text_is_not_truncated(self):
        for content, status in [(b'x' * 64001, 413), (b'x' * 256001, 413), (b'\xff\x00', 422)]:
            self.content = content
            self.assertEqual(self.analyze().status_code, status)
            self.assertTrue(self.opened[-1][1].closed)

    def test_selected_company_header_cannot_cross_offer_owner(self):
        self.assertEqual(self.analyze(headers={'X-Company-Id': '99'}).status_code, 409)
        self.assertEqual(self.opened, [])

    def test_revoked_payer_membership_during_read_withholds_result(self):
        def revoke():
            with self.conn.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE company_id=99')
        self.during_read = revoke
        self.assertEqual(self.analyze().status_code, 403)
        self.assertTrue(self.opened[0][1].closed)

    def test_changed_profile_during_read_withholds_result(self):
        def change():
            with self.conn.cursor() as cur:
                cur.execute("UPDATE company_requisites SET inn='7701111111' WHERE company_id=12")
        self.during_read = change
        self.assertEqual(self.analyze().status_code, 409)

    def test_file_deletion_during_read_withholds_result(self):
        def delete():
            with self.conn.cursor() as cur:
                cur.execute("UPDATE file_ownership SET deletion_status='deleting' WHERE id=31")
        self.during_read = delete
        self.assertEqual(self.analyze().status_code, 403)

    def test_matching_project_source_is_allowed(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET file_url='/uploads/company-12-project-44-supplier-contract/x.txt' WHERE id=35")
        self.assertEqual(self.analyze(sourceFileId=35).status_code, 200)

    def test_real_protected_local_file_to_recognition_response(self):
        with tempfile.TemporaryDirectory(prefix='contract-recognition-test-') as directory:
            file = Path(directory) / 'company-12-common-supplier-contract' / 'contract.txt'
            file.parent.mkdir()
            file.write_bytes(self.content)
            app = FastAPI()
            register_contract_recognition(app, {**self.deps, **self.storage,
                'open_local_file': lambda url: open_document_local_file(directory, url, 256000)})
            response = TestClient(app).post('/supplier-offers/40/contract-recognition',
                json={'sourceFileId': 31, 'partyVersion': 1, 'expectedVersion': 0})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['parties']['buyer']['fields']['fullName']['value'], 'ООО «Заказчик»')
