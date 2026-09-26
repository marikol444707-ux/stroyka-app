import unittest
from backend.security.redact import redact_dict


class RedactTest(unittest.TestCase):
    def test_redacts_sensitive_keys(self):
        src = {
            "password": "supersecret",
            "token": "abcd1234",
            "normal": "keepme",
            "nested": {"api_key": "sk-zzz"},
            "list": ["ok", {"secret": "x"}],
        }
        out = redact_dict(src)
        self.assertNotEqual(out["password"], "supersecret")
        self.assertTrue("[redacted]" in str(out["token"]) or "[redacted]" in out["token"])
        self.assertEqual(out["normal"], "keepme")
        self.assertNotEqual(out["nested"].get("api_key"), "sk-zzz")
        self.assertNotEqual(out["list"][1].get("secret"), "x")


if __name__ == "__main__":
    unittest.main()
