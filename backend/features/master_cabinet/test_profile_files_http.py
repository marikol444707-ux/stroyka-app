"""Personal profile uploads stay private on the guarded disposable HTTP fixture."""

import base64
import unittest
from uuid import uuid4

from backend.features.master_cabinet import test_profile_http as profile_http


@unittest.skipUnless(profile_http.RUN, "Requires the owned local audit API")
class ProfileFileHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_http.MasterProfileHttpTests.setUpClass.__func__(cls)
        for role in ("unassigned", "peer", "foreman", "master", "director", "stranger"):
            if not cls.users[role]["email"].endswith(".invalid"):
                raise RuntimeError("Only synthetic audit identities are permitted")

    def setUp(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII="
        )
        marker = uuid4().hex
        boundary = "master-profile-http-" + marker
        multipart = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="context"\r\n\r\nworker-profile-documents\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-profile-{marker}.png"\r\n'
            'Content-Type: image/png\r\n\r\n'
        ).encode() + png + f"\r\n--{boundary}--\r\n".encode()
        status, uploaded = self.request(
            "unassigned", "/upload-photo", "POST", raw=multipart,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertEqual(status, 200, uploaded)
        self.content = uploaded["url"]
        self.assertRegex(self.content, r"^/tenant-files/[1-9][0-9]*/content$")
        self.assertEqual(uploaded["companyId"], self.users["unassigned"]["company_id"])
        self.assertEqual(uploaded["context"], "worker-profile-documents")
        # This new synthetic upload remains until fixture teardown. No originals
        # or existing profile records are changed or deleted by this test.

    def test_only_uploader_and_staff_manager_can_read_profile_file(self):
        for path in (self.content, self.content.removesuffix("/content")):
            for role in ("unassigned", "director"):
                with self.subTest(path=path, role=role):
                    status, body = self.request(role, path)
                    self.assertEqual(status, 200, body)
            for role in ("peer", "foreman", "master", "stranger"):
                with self.subTest(path=path, role=role):
                    status, _body = self.request(role, path)
                    self.assertIn(status, (403, 404, 409), "Personal files must not be shared with colleagues")


if __name__ == "__main__":
    unittest.main()
