"""Offline security tests for the one-time Jev seccomp diagnostic builder."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_jev_qa_unshare_probe as probe


def example_default():
    return {
        "defaultAction": "SCMP_ACT_ERRNO", "defaultErrnoRet": 1,
        "architectures": ["SCMP_ARCH_X86_64"],
        "syscalls": [
            {"names": ["read", "write"], "action": "SCMP_ACT_ALLOW"},
            {"names": ["unshare", "setns"], "action": "SCMP_ACT_ALLOW",
             "includes": {"caps": ["CAP_SYS_ADMIN"]}},
            {"names": ["clone3"], "action": "SCMP_ACT_ERRNO",
             "errnoRet": 38, "excludes": {"caps": ["CAP_SYS_ADMIN"]}},
        ],
    }


class SeccompProbeTest(unittest.TestCase):
    def test_exactly_two_unshare_flag_combinations_and_no_broad_allow(self):
        original = example_default()
        result = probe.make_probe_profile(original)
        self.assertEqual(original, example_default())
        appended = result["syscalls"][len(original["syscalls"]):]
        self.assertEqual(len(appended), 2)
        self.assertEqual(
            [e["args"][0]["value"] for e in appended],
            [0x10000000, 0x30000000],
        )
        for e in appended:
            self.assertEqual(e["names"], ["unshare"])
            self.assertEqual(e["action"], "SCMP_ACT_ALLOW")
            self.assertEqual(e["args"][0]["op"], "SCMP_CMP_EQ")
        self.assertEqual(result["defaultAction"], "SCMP_ACT_ERRNO")
        self.assertNotIn("SCMP_ACT_ALLOW", [result["defaultAction"]])

    def test_rejects_malformed_or_overpermissive_upstream(self):
        for edit in (
            lambda x: x.update(defaultAction="SCMP_ACT_ALLOW"),
            lambda x: x.update(defaultErrnoRet=0),
            lambda x: x.pop("syscalls"),
            lambda x: x["syscalls"].append({"names": ["unshare"], "action": "SCMP_ACT_ALLOW"}),
            lambda x: x["syscalls"].pop(1),
            lambda x: x["syscalls"].pop(2),
        ):
            value = example_default()
            edit(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.make_probe_profile(value)

    def test_refuses_unreviewed_upstream_blob(self):
        with self.assertRaisesRegex(ValueError, "SHA"):
            probe.verified_source(b'{"defaultAction":"SCMP_ACT_ALLOW"}')

    def test_pinned_blob_validation_and_no_overwrite(self):
        upstream = (json.dumps(example_default()) + "\n").encode("utf-8")
        digest = hashlib.sha1(("blob " + str(len(upstream)) + "\0").encode() + upstream).hexdigest()

        class ReadResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, count):
                assert count == probe.MAX_SOURCE_BYTES + 1
                return upstream

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            probe, "PINNED_GIT_BLOB_SHA1", digest,
        ), patch.object(
            probe, "urlopen", return_value=ReadResponse(),
        ):
            filename = Path(tmp) / "unshare-test.json"
            self.assertEqual(probe.create_profile(filename), filename)
            result = json.loads(filename.read_text())
            self.assertEqual(result["syscalls"][-1]["args"][0]["value"], 0x30000000)
            self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                probe.create_profile(filename)


if __name__ == "__main__":
    unittest.main()
