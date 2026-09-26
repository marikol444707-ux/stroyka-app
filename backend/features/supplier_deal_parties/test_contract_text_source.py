import hashlib
import io
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from .contract_text_source import read_contract_text


class ContractTextSourceTest(unittest.TestCase):
    def setUp(self):
        self.row = {'company_id': 12, 'project_id': None, 'context': 'supplier-contract',
                    'original_name': 'contract.txt', 'storage_key': None,
                    'file_url': '/uploads/company-12-common-supplier-contract/x.txt'}
        self.stream = io.BytesIO(b'text')
        self.deps = {'s3_prefixes': ('uploads',), 's3_urls_for_key': lambda key: (),
                     's3_enabled': lambda: False,
                     'open_local_file': lambda url: (self.stream, 4)}

    def assert_error(self, status):
        with self.assertRaises(HTTPException) as caught:
            read_contract_text(self.row, self.deps)
        self.assertEqual(caught.exception.status_code, status)

    def test_utf8_bom_is_removed_for_text_but_preserved_in_content_hash(self):
        content = b'\xef\xbb\xbftext'
        self.stream = io.BytesIO(content)
        self.deps['open_local_file'] = lambda url: (self.stream, len(content))
        text, digest = read_contract_text(self.row, self.deps)
        self.assertEqual(text, 'text')
        self.assertEqual(digest, hashlib.sha256(content).hexdigest())
        self.assertTrue(self.stream.closed)

    def test_unexpected_size_is_rejected_and_stream_closed(self):
        self.deps['open_local_file'] = lambda url: (self.stream, 10)
        self.assert_error(409)
        self.assertTrue(self.stream.closed)

    def test_underreported_oversized_stream_is_rejected(self):
        self.stream = io.BytesIO(b'x' * 256001)
        self.assert_error(413)
        self.assertTrue(self.stream.closed)

    def test_empty_binary_and_disguised_pdf_are_rejected(self):
        for content in (b'', b'\x00data', b'%PDF-1.7', b'\xff'):
            with self.subTest(content=content):
                self.stream = io.BytesIO(content)
                self.deps['open_local_file'] = lambda url: (self.stream, len(content))
                self.assert_error(422)
                self.assertTrue(self.stream.closed)

    def test_read_failure_is_sanitized_and_closed(self):
        class BrokenStream(io.BytesIO):
            def read(self, size):
                raise OSError('private storage details')
        self.stream = BrokenStream()
        with self.assertRaises(HTTPException) as caught:
            read_contract_text(self.row, self.deps)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn('private storage', caught.exception.detail)
        self.assertTrue(self.stream.closed)

    def test_open_failure_is_sanitized(self):
        def fail(url):
            raise OSError('private storage details')
        self.deps['open_local_file'] = fail
        self.assert_error(503)

    def test_elapsed_read_budget_is_checked_and_closes_stream(self):
        with patch('backend.features.supplier_deal_parties.contract_text_source.time.monotonic', side_effect=[0, 11]):
            self.assert_error(504)
        self.assertTrue(self.stream.closed)

    def test_s3_reads_validated_key_not_url(self):
        key = 'uploads/company-12-common-supplier-contract/x.txt'
        self.row.update(storage_key=key, file_url='https://storage.invalid/bucket/' + key)
        self.deps.update(s3_enabled=lambda: True, s3_urls_for_key=lambda value: (self.row['file_url'],))
        keys = []
        def open_s3(value):
            keys.append(value)
            return self.stream, 4
        self.deps['open_s3_object'] = open_s3
        self.assertEqual(read_contract_text(self.row, self.deps)[0], 'text')
        self.assertEqual(keys, [key])
        self.assertTrue(self.stream.closed)

    def test_disabled_s3_does_not_fall_back_to_local_or_public_url(self):
        self.row.update(storage_key='uploads/company-12-common-supplier-contract/x.txt', file_url='https://storage.invalid/x')
        self.deps['s3_urls_for_key'] = lambda key: (self.row['file_url'],)
        self.assert_error(503)
        self.assertFalse(self.stream.closed)
