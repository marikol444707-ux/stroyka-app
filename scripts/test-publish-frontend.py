#!/usr/bin/env python3
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = ROOT / "scripts" / "publish-frontend.sh"


class PublishFrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="stroyka-publish-test-")
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "release"
        self.target = self.root / "live"
        (self.source / "static" / "js").mkdir(parents=True)
        (self.source / "static" / "css").mkdir(parents=True)
        (self.target / "static" / "js").mkdir(parents=True)
        self.old_index = "<html><script src='/static/js/old.js'></script></html>"
        self.new_index = "<html><script src='/static/js/new.js'></script></html>"
        (self.source / "index.html").write_text(self.new_index, encoding="utf-8")
        (self.source / "asset-manifest.json").write_text('{"main":"new.js"}', encoding="utf-8")
        (self.source / "static" / "js" / "new.js").write_text("new", encoding="utf-8")
        (self.source / "static" / "css" / "new.css").write_text("new", encoding="utf-8")
        (self.target / "index.html").write_text(self.old_index, encoding="utf-8")
        (self.target / "stale-root-file.html").write_text("stale", encoding="utf-8")
        (self.target / "static" / "js" / "old.js").write_text("old", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _slow_rsync(self):
        real_rsync = shutil.which("rsync")
        self.assertIsNotNone(real_rsync, "rsync is required for the publisher test")
        wrapper = self.root / "slow-rsync"
        wrapper.write_text(
            "#!/bin/sh\nsleep 0.15\nexec " + shlex.quote(real_rsync) + ' "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        return wrapper

    def test_keeps_old_index_available_until_atomic_swap(self):
        env = dict(os.environ)
        env["RSYNC_BIN"] = str(self._slow_rsync())
        process = subprocess.Popen(
            ["bash", str(PUBLISH_SCRIPT), str(self.source), str(self.target)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        observed_indexes = []
        while process.poll() is None:
            try:
                observed_indexes.append((self.target / "index.html").read_text(encoding="utf-8"))
            except FileNotFoundError:
                observed_indexes.append(None)
            time.sleep(0.005)
        stdout, stderr = process.communicate()

        self.assertEqual(process.returncode, 0, msg=stdout + stderr)
        self.assertGreater(len(observed_indexes), 10)
        self.assertNotIn(None, observed_indexes)
        self.assertTrue(set(observed_indexes).issubset({self.old_index, self.new_index}))
        self.assertEqual((self.target / "index.html").read_text(encoding="utf-8"), self.new_index)
        self.assertFalse((self.target / "stale-root-file.html").exists())
        self.assertTrue((self.target / "static" / "js" / "old.js").exists())
        self.assertTrue((self.target / "static" / "js" / "new.js").exists())
        self.assertTrue((self.target / "static" / "css" / "new.css").exists())
        self.assertEqual(
            (self.target / "asset-manifest.json").read_text(encoding="utf-8"),
            '{"main":"new.js"}',
        )

    def test_rejects_incomplete_release_without_touching_live_files(self):
        (self.source / "index.html").unlink()

        result = subprocess.run(
            ["bash", str(PUBLISH_SCRIPT), str(self.source), str(self.target)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / "index.html").read_text(encoding="utf-8"), self.old_index)
        self.assertTrue((self.target / "stale-root-file.html").exists())
        self.assertTrue((self.target / "static" / "js" / "old.js").exists())

    def test_rejects_nonempty_target_that_is_not_a_frontend_build(self):
        unsafe_target = self.root / "repository"
        unsafe_target.mkdir()
        marker = unsafe_target / "package.json"
        marker.write_text('{"private":true}', encoding="utf-8")

        result = subprocess.run(
            ["bash", str(PUBLISH_SCRIPT), str(self.source), str(unsafe_target)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(marker.exists())
        self.assertFalse((unsafe_target / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
