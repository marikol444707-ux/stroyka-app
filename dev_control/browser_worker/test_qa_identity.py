"""Offline tests for server-backed QA identity projection (no auth bypass)."""
import copy
import unittest

from dev_control.browser_worker.qa_identity import (
    QAIdentityNotEstablished,
    project_qa_user,
    verify_qa_identity_http_response,
)


def valid_response():
    return {
        "ok": True,
        "user": {
            "id": 21, "name": "QA Viewer", "email": "qa@example.test",
            "role": "прораб", "companyId": 17,
        },
        "defaultCompanyId": 17,
        "canUseAllCompanies": False,
        "companies": [{
            "source": "membership", "membershipId": 29,
            "companyId": 17, "role": "прораб",
            "active": True, "companyActive": True,
            "readOnly": False, "accountLevel": False,
        }],
    }


class QAIdentityTest(unittest.TestCase):
    def test_accepts_only_server_public_identity_and_exact_company(self):
        payload = valid_response()
        self.assertEqual(project_qa_user(payload), {
            "id": 21, "companyId": 17, "role": "прораб",
            "name": "QA Viewer", "email": "qa@example.test",
        })

    def test_requires_exact_https_qa_identity_response(self):
        args = {
            "base_url": "https://qa.example.test/app",
            "response_url": "https://qa.example.test/users/company-context",
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "payload": valid_response(),
        }
        self.assertEqual(
            verify_qa_identity_http_response(**args)["companyId"], 17
        )
        bad_cases = [
            {"response_url": "https://evil.example/users/company-context"},
            {"response_url": "http://qa.example.test/users/company-context"},
            {"response_url": "https://qa.example.test/login"},
            {"response_url": "https://qa.example.test/users/company-context?token=secret"},
            {"response_url": "https://user:pass@qa.example.test/users/company-context"},
            {"response_url": "https://qa.example.test:444/users/company-context"},
            {"status": 302},
            {"status": 401},
            {"status": 403},
            {"status": True},
            {"content_type": "text/html"},
            {"payload": {"ok": False}},
            {"base_url": "http://qa.example.test/app"},
        ]
        for changed in bad_cases:
            with self.subTest(changed=changed):
                with self.assertRaises(QAIdentityNotEstablished):
                    verify_qa_identity_http_response(**(args | changed))

    def test_rejects_unverified_or_cross_tenant_identity(self):
        def mutate(path, value):
            payload = valid_response()
            target = payload
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            return payload

        cases = [
            (("ok",), False),
            (("user", "id"), 0),
            (("user", "id"), True),
            (("user", "companyId"), 18),
            (("user", "companyId"), "17"),
            (("user", "role"), "директор"),
            (("user", "role"), ""),
            (("user", "name"), None),
            (("user", "email"), None),
            (("defaultCompanyId",), 18),
            (("canUseAllCompanies",), True),
            (("companies", 0, "companyId"), 18),
            (("companies", 0, "membershipId"), None),
            (("companies", 0, "role"), "директор"),
            (("companies", 0, "active"), False),
            (("companies", 0, "companyActive"), False),
            (("companies", 0, "source"), "platform"),
            (("companies", 0, "source"), "legacy"),
            (("companies", 0, "accountLevel"), True),
            (("companies", 0, "readOnly"), True),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                with self.assertRaisesRegex(QAIdentityNotEstablished, "AUTH_NOT_ESTABLISHED"):
                    project_qa_user(mutate(path, value))

    def test_rejects_missing_multiple_or_forged_context(self):
        for payload in (None, [], {}, {"ok": True}, valid_response() | {"companies": []},
                        valid_response() | {"companies": [valid_response()["companies"][0]] * 2}):
            with self.subTest(payload=payload):
                with self.assertRaises(QAIdentityNotEstablished):
                    project_qa_user(payload)

        for field in ("authToken", "token", "password", "session", "sessionHash"):
            payload = copy.deepcopy(valid_response())
            payload["user"][field] = "SECRET-DO-NOT-LOG"
            with self.subTest(field=field):
                with self.assertRaises(QAIdentityNotEstablished) as exc:
                    project_qa_user(payload)
                self.assertNotIn("SECRET-DO-NOT-LOG", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
