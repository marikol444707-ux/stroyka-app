import tempfile
from pathlib import Path
import unittest

from .service import app_version


SHA = "1234567890abcdef1234567890abcdef12345678"


class RuntimeVersionTest(unittest.TestCase):
    def root(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_prefers_explicit_release_identity(self):
        self.assertEqual(app_version(self.root(), {"APP_VERSION": SHA}), SHA[:12])

    def test_reads_loose_and_detached_heads(self):
        root = self.root(); (root / ".git/refs/heads").mkdir(parents=True)
        (root / ".git/HEAD").write_text("ref: refs/heads/main\n")
        (root / ".git/refs/heads/main").write_text(SHA + "\n")
        self.assertEqual(app_version(root, {}), SHA[:12])
        (root / ".git/HEAD").write_text(SHA + "\n")
        self.assertEqual(app_version(root, {}), SHA[:12])

    def test_reads_packed_ref_from_worktree_common_directory(self):
        root = self.root(); common = root / "repo/.git"; worktree = common / "worktrees/release"
        worktree.mkdir(parents=True)
        (root / ".git").write_text("gitdir: repo/.git/worktrees/release\n")
        (worktree / "HEAD").write_text("ref: refs/heads/main\n")
        (worktree / "commondir").write_text("../..\n")
        (common / "packed-refs").write_text(f"# pack-refs\n{SHA} refs/heads/main\n")
        self.assertEqual(app_version(root, {}), SHA[:12])

    def test_fails_closed_for_missing_or_unsafe_ref(self):
        root = self.root(); (root / ".git").mkdir()
        (root / ".git/HEAD").write_text("ref: refs/../secret\n")
        self.assertEqual(app_version(root, {}), "unknown")
