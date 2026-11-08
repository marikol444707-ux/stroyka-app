"""Opt-in regressions against the already running, disposable master audit API.

No application/cluster startup, database connection, or ambient .env loading.
The temporary audit helper is deliberately imported only after fixture checks.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
RUN = os.environ.get("MASTER_CABINET_HTTP_TESTS") == "1"


def require_owned_fixture():
    marker = json.loads((ROOT / "tmp/master-audit/fixture.json").read_text())
    work = Path(marker["root"]).resolve()
    expected = {
        "root": str(work), "port": "6548", "user": "chain_test",
        "databases": ["supply_chain_test_master_audit"],
        "kind": "master-audit-local",
    }
    if (work.parent != (ROOT / "tmp").resolve()
            or not work.name.startswith("ep-") or marker != expected
            or json.loads((work / "fixture.json").read_text()) != expected):
        raise RuntimeError("Refusing an unowned or incorrectly named audit database")
    pid_lines = (work / "data/postmaster.pid").read_text().splitlines()
    if (Path(pid_lines[1]).resolve() != work / "data"
            or pid_lines[3] != "6548" or pid_lines[7].strip() != "ready"):
        raise RuntimeError("Postmaster does not match the ready audit cluster")
    pid = int(pid_lines[0])
    os.kill(pid, 0)
    process = subprocess.check_output(
        ["/bin/ps", "-p", str(pid), "-o", "uid=,command="], text=True,
    ).strip().split(maxsplit=1)
    if (int(process[0]) != os.getuid() or "postgres -D " not in process[1]
            or str(work / "data") not in process[1]):
        raise RuntimeError("Live postmaster is not owned by the audit fixture")
    # A valid marker alone cannot authorize writes to an unrelated localhost API.
    listeners = subprocess.check_output(
        ["/usr/sbin/lsof", "-nP", "-iTCP:8001", "-sTCP:LISTEN", "-t"],
        text=True,
    ).split()
    if len(set(listeners)) != 1:
        raise RuntimeError("Expected one guarded audit backend on port 8001")
    backend = subprocess.check_output(
        ["/bin/ps", "-p", listeners[0], "-o", "uid=,command="], text=True,
    ).strip().split(maxsplit=1)
    if (int(backend[0]) != os.getuid()
            or "tmp/master-audit/start_full.py" not in backend[1]):
        raise RuntimeError("Port 8001 is not the guarded audit launcher")


@unittest.skipUnless(RUN, "Set MASTER_CABINET_HTTP_TESTS=1 with the owned audit API running")
class MasterProfileHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_owned_fixture()
        spec = importlib.util.spec_from_file_location(
            "master_profile_http_api", ROOT / "tmp/master-audit/api_support.py",
        )
        helper = importlib.util.module_from_spec(spec)
        environment, exists = dict(os.environ), os.path.exists
        try:
            spec.loader.exec_module(helper)
        finally:
            os.environ.clear()
            os.environ.update(environment)
            os.path.exists = exists
        cls.request = staticmethod(helper.request)
        cls.users = helper.FIXTURE["users"]
        cls.master_id = cls.users["master"]["id"]
        for role in ("master", "director", "stranger"):
            if not cls.users[role]["email"].endswith(".invalid"):
                raise RuntimeError("Only synthetic audit identities are permitted")
        if (cls.users["master"]["company_id"] != cls.users["director"]["company_id"]
                or cls.users["master"]["company_id"] == cls.users["stranger"]["company_id"]):
            raise RuntimeError("Fixture does not provide distinct companies")

    def get_consents(self, role="director"):
        status, rows = self.request(role, "/pd-consents")
        self.assertEqual(status, 200, rows)
        self.assertIsInstance(rows, list)
        return rows

    def restore_consent(self, original):
        if original is None:
            status, body = self.request("director", f"/pd-consents/{self.master_id}", "DELETE")
        else:
            status, body = self.request("master", "/pd-consents", "POST", original)
        self.assertEqual(status, 200, body)
        restored = next((row for row in self.get_consents() if row["userId"] == self.master_id), None)
        self.assertEqual(restored, original, "Consent cleanup must restore the original record")

    def seed_consent(self, *, requires_absent=False):
        original = next((row for row in self.get_consents() if row["userId"] == self.master_id), None)
        if requires_absent and original is not None:
            self.skipTest("DELETE regression requires an absent consent to preserve existing IDs")
        self.addCleanup(self.restore_consent, original)
        payload = {"userId": self.master_id, "signedAt": "2026-11-08",
                   "scanUrl": "", "uploadedBy": "master-http-regression"}
        status, created = self.request("master", "/pd-consents", "POST", payload)
        self.assertEqual(status, 200, created)
        for key, value in payload.items():
            self.assertEqual(created[key], value)
        return created

    def test_foreign_director_cannot_list_master_profile(self):
        status, own_rows = self.request("director", "/master-profiles")
        self.assertEqual(status, 200, own_rows)
        self.assertIn(self.master_id, [row["userId"] for row in own_rows])
        status, rows = self.request("stranger", "/master-profiles")
        self.assertEqual(status, 200, rows)
        self.assertNotIn(self.master_id, [row["userId"] for row in rows])

    def test_foreign_director_cannot_read_master_profile_by_id(self):
        for role in ("master", "director"):
            status, body = self.request(role, f"/master-profile/{self.master_id}")
            self.assertEqual(status, 200, body)
            self.assertEqual(body["userId"], self.master_id)
        status, body = self.request("stranger", f"/master-profile/{self.master_id}")
        self.assertIn(status, (403, 404), body)

    def test_foreign_director_cannot_write_master_profile(self):
        status, original = self.request("master", f"/master-profile/{self.master_id}")
        self.assertEqual(status, 200, original)
        payload = {key: value for key, value in original.items()
                   if key not in ("id", "profileCompleted")}
        if not original.get("profileCompleted") or any(value is None for value in payload.values()):
            # This launcher-created profile may contain SQL NULLs, which its POST
            # model cannot restore. Establish an authorized synthetic baseline.
            payload = {key: "" if value is None else value for key, value in payload.items()}
            status, original = self.request("master", "/master-profile", "POST", payload)
            self.assertEqual(status, 200, original)

        def restore():
            status, body = self.request("master", "/master-profile", "POST", payload)
            self.assertEqual(status, 200, body)
            self.assertEqual(body, original)

        self.addCleanup(restore)
        status, body = self.request("stranger", "/master-profile", "POST",
                                    {**payload, "fullName": "Forbidden foreign edit"})
        with self.subTest("foreign write rejected"):
            self.assertIn(status, (403, 404), body)
        status, current = self.request("master", f"/master-profile/{self.master_id}")
        self.assertEqual(status, 200, current)
        self.assertEqual(current, original, "Rejected foreign writes must not alter the profile")

    def test_master_can_read_own_posted_consent_without_leaking_to_foreign_company(self):
        created = self.seed_consent()
        with self.subTest("self can read the consent just posted"):
            rows = self.get_consents("master")
            self.assertIn(created, rows)
            self.assertTrue(all(row["userId"] == self.master_id for row in rows))
        with self.subTest("same-company director can read it"):
            self.assertIn(created, self.get_consents("director"))
        with self.subTest("foreign director cannot read it"):
            self.assertNotIn(self.master_id, [row["userId"] for row in self.get_consents("stranger")])

    def test_foreign_director_cannot_overwrite_master_consent(self):
        created = self.seed_consent()
        status, body = self.request("stranger", "/pd-consents", "POST",
                                    {**created, "uploadedBy": "Forbidden foreign edit"})
        with self.subTest("foreign write rejected"):
            self.assertIn(status, (403, 404), body)
        self.assertIn(created, self.get_consents(), "Foreign write must leave consent unchanged")

    def test_foreign_director_cannot_delete_master_consent(self):
        created = self.seed_consent(requires_absent=True)
        status, body = self.request("stranger", f"/pd-consents/{self.master_id}", "DELETE")
        with self.subTest("foreign deletion rejected"):
            self.assertIn(status, (403, 404), body)
        self.assertIn(created, self.get_consents(), "Foreign deletion must leave consent unchanged")


if __name__ == "__main__":
    unittest.main()
