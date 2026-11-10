import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ops.hermes_max.poll_cursor import PollCursor
from ops.hermes_max.patch_adapter import patched


class PollCursorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "gateway" / "cursor.json"
        self.cursor = PollCursor(self.path, "test-bot")

    def test_restart_retains_marker_and_private_permissions(self):
        self.assertEqual(self.cursor.load(), 0)
        self.cursor.save(72242)
        self.assertEqual(PollCursor(self.path, "test-bot").load(), 72242)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_another_bot_cannot_acknowledge_this_cursor(self):
        self.cursor.save(42)
        with self.assertRaises(ValueError):
            PollCursor(self.path, "another-bot").load()

    def test_corrupt_cursor_does_not_silently_reset(self):
        self.cursor.save(42)
        self.path.write_text("broken")
        with self.assertRaises(ValueError):
            self.cursor.load()

    def test_invalid_remote_marker_does_not_replace_valid_cursor(self):
        self.cursor.save(42)
        for marker in (True, -1, 1.5, "43", None):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                self.cursor.save(marker)
        self.assertEqual(self.cursor.load(), 42)

    def test_failed_replace_preserves_previous_cursor(self):
        self.cursor.save(42)
        with patch("ops.hermes_max.poll_cursor.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.cursor.save(43)
        self.assertEqual(self.cursor.load(), 42)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_missing_identity_rejected(self):
        with self.assertRaises(ValueError):
            PollCursor(self.path, "")

    def test_unknown_adapter_rejected(self):
        with self.assertRaises(ValueError):
            patched(b"unreviewed adapter")


if __name__ == "__main__":
    unittest.main()
