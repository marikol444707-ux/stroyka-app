"""Save-time evidence: real local SQL, synthetic bytes, no external services."""
import hashlib
import json
import os
import unittest

import psycopg2

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from .contract_recognition import register_contract_recognition
from .contracts import ContractReview, register_supplier_contracts_module
from .test_contracts import payload
from . import test_contract_recognition as recognition_fixture


def selection(digest='a' * 64):
    return {'sourceContentHash': digest, 'acceptedFields': [{'side': 'buyer', 'field': 'fullName'}]}


class ProvenanceInputTest(unittest.TestCase):
    def test_additive_optional_selection(self):
        review = ContractReview(**payload(), recognitionReview=selection())
        self.assertEqual(review.recognitionReview.acceptedFields[0].field, 'fullName')
        self.assertIsNone(ContractReview(**payload()).recognitionReview)

    def test_rejects_spoofed_author_quotes_inn_duplicate_and_unbounded_fields(self):
        for change in ({'reviewedBy': 'Other'}, {'quote': 'Invented'}, {'sourceContentHash': 'no'},
                       {'acceptedFields': []}, {'acceptedFields': [{'side': 'buyer', 'field': 'inn'}]},
                       {'acceptedFields': [{'side': 'foreign', 'field': 'rs'}]},
                       {'acceptedFields': selection()['acceptedFields'] * 2},
                       {'acceptedFields': selection()['acceptedFields'] * 40}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ContractReview(**payload(), recognitionReview={**selection(), **change})


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS') == '1', 'local PostgreSQL opt-in')
class ProvenancePostgresTest(unittest.TestCase):
    setUp_parties = recognition_fixture.RecognitionPostgresTest.setUp_parties
    put = recognition_fixture.RecognitionPostgresTest.put

    def setUp(self):
        recognition_fixture.RecognitionPostgresTest.setUp(self)
        app = FastAPI()
        register_supplier_contracts_module(app, self.deps)
        # Match production startup: the storage-backed service is registered later.
        self.deps['recognize_contract'] = register_contract_recognition(app, {**self.deps, **self.storage})
        self.client = TestClient(app)

    def save(self, **changes):
        data = {**payload(), 'buyer': {'fullName': 'ООО «Заказчик»', 'inn': '7701234567'},
                'recognitionReview': selection(hashlib.sha256(self.content).hexdigest()), **changes}
        return self.client.post('/supplier-offers/40/contracts', json=data)

    def assert_no_save(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM supplier_contract_versions')
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute('SELECT retained_at FROM file_ownership WHERE id=31')
            self.assertIsNone(cur.fetchone()[0])

    def test_verified_evidence_is_saved_and_returned_in_history(self):
        response = self.save()
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        audit = saved['snapshot']['recognitionReview']
        self.assertEqual(audit['sourceContentHash'], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(audit['sourceFileId'], 31)
        self.assertEqual(audit['acceptedFields'][0]['value'], 'ООО «Заказчик»')
        self.assertIn('ООО «Заказчик»', audit['acceptedFields'][0]['quote'])
        self.assertEqual(saved['reviewedBy'], 'Анна')
        self.assertTrue(saved['reviewedAt'])
        encoded = json.dumps(saved['snapshot'], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        self.assertEqual(saved['snapshotHash'], hashlib.sha256(encoded.encode()).hexdigest())
        history = self.client.get('/supplier-offers/40/contracts').json()['items']
        self.assertEqual(history, [saved])
        self.assertNotIn('/uploads/', response.text)
        self.assertEqual(self.save().status_code, 409)
        with self.conn.cursor() as cur:
            cur.execute('SELECT reviewed_by_id,retained_at IS NOT NULL FROM supplier_contract_versions v '
                        'JOIN file_ownership f ON f.id=v.source_file_id')
            self.assertEqual(cur.fetchone(), (8, True))

    def test_wrong_hash_or_edited_value_leave_no_partial_save(self):
        self.assertEqual(self.save(recognitionReview=selection()).status_code, 409)
        self.assertEqual(self.save(buyer=payload()['buyer']).status_code, 409)
        self.assert_no_save()

    def test_disabled_service_rejects_evidence_but_preserves_manual_flow(self):
        del self.deps['recognize_contract']
        self.assertEqual(self.save().status_code, 503)
        self.assert_no_save()
        self.assertEqual(self.save(recognitionReview=None).status_code, 200)
        self.assertEqual(self.opened, [])

    def test_revoked_payer_access_during_read_rolls_back(self):
        def revoke():
            with self.conn.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE company_id=99')
        self.during_read = revoke
        self.assertEqual(self.save().status_code, 403)
        self.assert_no_save()

    def test_supplier_payer_only_and_cross_account_cannot_save_evidence(self):
        original = self.user.copy()
        for changes in ({'role': 'поставщик'}, {'id': 9, 'companyId': 99},
                        {'companyId': 101, 'platformAccountId': 8}):
            with self.subTest(changes=changes):
                self.user = {**original, **changes}
                self.assertEqual(self.save().status_code, 403)
                self.assert_no_save()
        self.assertEqual(self.opened, [])

    def test_foreign_source_and_stale_versions_never_read_file(self):
        for changes, status in (({'sourceFileId': 32}, 403), ({'sourceFileId': 33}, 403),
                                ({'partyVersion': 2}, 409), ({'expectedVersion': 1}, 409)):
            with self.subTest(changes=changes):
                self.assertEqual(self.save(**changes).status_code, status)
                self.assert_no_save()
        self.assertEqual(self.opened, [])

    def test_file_metadata_changed_after_recognition_is_rechecked_under_lock(self):
        recognize = self.deps['recognize_contract']

        def change_after_read(*args):
            result = recognize(*args)
            with self.conn.cursor() as cur:
                cur.execute("UPDATE file_ownership SET file_url='/uploads/company-12-common-supplier-contract/new.txt' WHERE id=31")
            return result

        self.deps['recognize_contract'] = change_after_read
        self.assertEqual(self.save().status_code, 409)
        self.assert_no_save()

    def test_access_revoked_after_recognition_is_rechecked_before_insert(self):
        recognize = self.deps['recognize_contract']

        def revoke_after_read(*args):
            result = recognize(*args)
            with self.conn.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE company_id=99')
            return result

        self.deps['recognize_contract'] = revoke_after_read
        self.assertEqual(self.save().status_code, 403)
        self.assert_no_save()

    def test_manual_flow_has_no_claim_of_recognition(self):
        saved = self.save(recognitionReview=None)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertNotIn('recognitionReview', saved.json()['snapshot'])
        self.assertEqual(self.opened, [])

    def test_missing_field_cannot_be_claimed_as_recognized(self):
        selected = selection(hashlib.sha256(self.content).hexdigest())
        selected['acceptedFields'] = [{'side': 'buyer', 'field': 'email'}]
        self.assertEqual(self.save(recognitionReview=selected).status_code, 409)
        self.assert_no_save()

    def test_accepted_fields_are_distinct_between_buyer_and_payer(self):
        selected = selection(hashlib.sha256(self.content).hexdigest())
        selected['acceptedFields'].append({'side': 'payer', 'field': 'fullName'})
        response = self.save(recognitionReview=selected, payer={'fullName': 'ООО «Плательщик»', 'inn': '7707654321'})
        self.assertEqual(response.status_code, 200, response.text)
        fields = response.json()['snapshot']['recognitionReview']['acceptedFields']
        self.assertEqual([(f['side'], f['value']) for f in fields],
                         [('buyer', 'ООО «Заказчик»'), ('payer', 'ООО «Плательщик»')])

    def test_pdf_preview_to_saved_evidence_uses_the_same_byte_hash(self):
        from .test_contract_pdf import synthetic_pdf
        self.content = synthetic_pdf()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET original_name='contract.pdf' WHERE id=31")
        preview = self.client.post('/supplier-offers/40/contract-recognition', json={
            'sourceFileId': 31, 'partyVersion': 1, 'expectedVersion': 0})
        self.assertEqual(preview.status_code, 200, preview.text)
        proposed = preview.json()
        saved = self.save(recognitionReview=selection(proposed['sourceContentHash']))
        self.assertEqual(saved.status_code, 200, saved.text)
        field = saved.json()['snapshot']['recognitionReview']['acceptedFields'][0]
        self.assertEqual({k: field[k] for k in ('value', 'line', 'quote')},
                         proposed['parties']['buyer']['fields']['fullName'])

    def test_same_length_content_change_since_preview_is_detected(self):
        original_hash = hashlib.sha256(self.content).hexdigest()
        self.content = self.content.replace(b'40702810000000000001', b'40702810000000000009')
        self.assertEqual(self.save(recognitionReview=selection(original_hash)).status_code, 409)
        self.assert_no_save()

    def test_retention_failure_rolls_back_contract_and_evidence_together(self):
        with self.conn.cursor() as cur:
            cur.execute('ALTER TABLE file_ownership ADD CONSTRAINT simulate_retention_failure '
                        'CHECK (retained_at IS NULL)')
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.save()
        self.assert_no_save()
