import datetime as dt
import io
import unittest
import urllib.error

from fastapi import HTTPException

from backend.features.document_access.storage import NoRedirectHandler, delete_s3_object, open_s3_object


class FakeResponse(io.BytesIO):
    def __init__(self, content=b"png", headers=None, status=200):
        super().__init__(content)
        self.headers = headers or {
            "Content-Length": str(len(content)),
            "Content-Type": "image/png",
        }
        self.status = status


class FakeOpener:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class S3DocumentStorageTests(unittest.TestCase):
    def _open(self, opener, **overrides):
        params = {
            "key": "uploads/company-4-common-general/general/file.png",
            "endpoint_url": "https://storage.example",
            "bucket": "documents",
            "region": "ru-central1",
            "access_key": "access-key",
            "secret_key": "secret-key",
            "max_bytes": 1024,
            "opener": opener,
            "now": dt.datetime(2026, 7, 11, 9, 0, 0),
        }
        params.update(overrides)
        return open_s3_object(**params)

    def test_open_s3_object_signs_https_get_without_reading_body(self):
        response = FakeResponse(b"png-content")
        opener = FakeOpener(response)

        opened, size = self._open(opener)

        self.assertIs(opened, response)
        self.assertEqual(size, len(b"png-content"))
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 30)
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.startswith("https://storage.example/documents/"))
        self.assertTrue(request.get_header("Authorization").startswith("AWS4-HMAC-SHA256 "))
        self.assertEqual(response.tell(), 0)

    def test_open_s3_object_rejects_insecure_endpoint_before_request(self):
        opener = FakeOpener(FakeResponse())
        with self.assertRaises(HTTPException) as error:
            self._open(opener, endpoint_url="http://storage.example")
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(opener.calls, [])

    def test_redirect_handler_never_forwards_signed_request(self):
        handler = NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://other.example"))

        redirect = urllib.error.HTTPError(
            "https://storage.example/documents/file.png",
            302,
            "Found",
            {},
            None,
        )
        opener = FakeOpener(redirect)
        with self.assertRaises(HTTPException) as error:
            self._open(opener)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(len(opener.calls), 1)

    def test_oversized_or_unbounded_s3_response_is_closed(self):
        for headers in (
            {"Content-Length": "2048", "Content-Type": "image/png"},
            {"Content-Type": "image/png"},
        ):
            response = FakeResponse(headers=headers)
            with self.subTest(headers=headers), self.assertRaises(HTTPException) as error:
                self._open(FakeOpener(response))
            self.assertIn(error.exception.status_code, (413, 503))
            self.assertTrue(response.closed)

    def test_partial_or_encoded_s3_response_is_rejected_and_closed(self):
        for response in (
            FakeResponse(b"part", status=206),
            FakeResponse(b"gzip", headers={"Content-Length": "4", "Content-Encoding": "gzip"}),
        ):
            with self.subTest(status=response.status, headers=dict(response.headers)):
                with self.assertRaises(HTTPException) as error:
                    self._open(FakeOpener(response))
                self.assertEqual(error.exception.status_code, 503)
                self.assertTrue(response.closed)

    def test_delete_s3_object_uses_signed_https_delete_and_closes_response(self):
        response = FakeResponse(b"", headers={"Content-Length": "0"}, status=204)
        opener = FakeOpener(response)

        delete_s3_object(
            key="uploads/company-4-common-general/general/file.png",
            endpoint_url="https://storage.example",
            bucket="documents",
            region="ru-central1",
            access_key="access-key",
            secret_key="secret-key",
            opener=opener,
            now=dt.datetime(2026, 7, 11, 9, 0, 0),
        )

        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 30)
        self.assertEqual(request.get_method(), "DELETE")
        self.assertTrue(request.get_header("Authorization").startswith("AWS4-HMAC-SHA256 "))
        self.assertTrue(response.closed)

    def test_delete_s3_object_rejects_redirect(self):
        redirect = urllib.error.HTTPError(
            "https://storage.example/documents/file.png",
            302,
            "Found",
            {},
            None,
        )
        with self.assertRaises(HTTPException) as error:
            delete_s3_object(
                key="uploads/company-4-common-general/general/file.png",
                endpoint_url="https://storage.example",
                bucket="documents",
                region="ru-central1",
                access_key="access-key",
                secret_key="secret-key",
                opener=FakeOpener(redirect),
                now=dt.datetime(2026, 7, 11, 9, 0, 0),
            )
        self.assertEqual(error.exception.status_code, 503)

    def test_delete_s3_object_treats_missing_key_as_already_clean(self):
        missing = urllib.error.HTTPError(
            "https://storage.example/documents/file.png",
            404,
            "Not Found",
            {},
            None,
        )
        deleted = delete_s3_object(
            key="uploads/company-4-common-general/general/file.png",
            endpoint_url="https://storage.example",
            bucket="documents",
            region="ru-central1",
            access_key="access-key",
            secret_key="secret-key",
            opener=FakeOpener(missing),
            now=dt.datetime(2026, 7, 11, 9, 0, 0),
        )
        self.assertFalse(deleted)


if __name__ == "__main__":
    unittest.main()
