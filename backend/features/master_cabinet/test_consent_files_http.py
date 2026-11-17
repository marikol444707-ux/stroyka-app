"""Personal consent attachment isolation on the guarded disposable HTTP fixture."""
import base64
import unittest

from backend.features.master_cabinet import test_profile_http as profile_http


@unittest.skipUnless(profile_http.RUN, 'Requires the owned local audit API')
class ConsentFileHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_http.MasterProfileHttpTests.setUpClass.__func__(cls)

    def setUp(self):
        status, rows = self.request('master', '/pd-consents')
        self.assertEqual(status, 200, rows)
        original = next((row for row in rows if row['userId'] == self.master_id), None)
        self.addCleanup(self.restore_consent, original)
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII='
        )
        boundary = 'master-consent-http-fixture-boundary'
        multipart = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="context"\r\n\r\npd-consents\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-consent.png"\r\n'
            'Content-Type: image/png\r\n\r\n'
        ).encode() + png + f'\r\n--{boundary}--\r\n'.encode()
        status, uploaded = self.request(
            'master', '/upload-photo', 'POST', raw=multipart,
            content_type=f'multipart/form-data; boundary={boundary}',
        )
        self.assertEqual(status, 200, uploaded)
        self.content = uploaded['url']
        self.assertRegex(self.content, r'^/tenant-files/[1-9][0-9]*/content$')
        consent = {'userId': self.master_id, 'signedAt': '2026-11-08',
                   'scanUrl': self.content, 'uploadedBy': 'synthetic-consent-http-test'}
        status, saved = self.request('master', '/pd-consents', 'POST', consent)
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved['scanUrl'], self.content)

    def restore_consent(self, original):
        if original is None:
            status, body = self.request('director', f'/pd-consents/{self.master_id}', 'DELETE')
        else:
            status, body = self.request('master', '/pd-consents', 'POST', original)
        self.assertEqual(status, 200, body)
        status, rows = self.request('master', '/pd-consents')
        self.assertEqual(status, 200, rows)
        self.assertEqual(next((row for row in rows if row['userId'] == self.master_id), None), original)
        # Keep the synthetic upload until fixture teardown; never delete originals.

    def test_other_workers_cannot_download_or_read_metadata_of_master_consent(self):
        content = self.content
        self.assertRegex(content, r'^/tenant-files/[1-9][0-9]*/content$')
        for path in [content, content.removesuffix('/content')]:
            for role in ['master', 'director']:
                with self.subTest(path=path, role=role):
                    self.assertEqual(self.request(role, path)[0], 200)
            for role in ['peer', 'unassigned', 'foreman', 'accountant', 'stranger']:
                with self.subTest(path=path, role=role):
                    self.assertIn(self.request(role, path)[0], (403, 404, 409))
