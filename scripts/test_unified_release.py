import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest


SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('unified_release', SCRIPTS / 'unified_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class UnifiedReleaseTests(unittest.TestCase):
    def test_bundle_transports_all_commits_without_a_remote_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            source = work / 'source'
            source.mkdir()
            self.git(source, 'init', '-b', 'main')
            self.git(source, 'config', 'user.email', 'test@local.invalid')
            self.git(source, 'config', 'user.name', 'Release test')
            (source / '.gitignore').write_text('.env\n')
            (source / 'app.txt').write_text('installed baseline')
            self.commit(source, 'baseline')
            base = self.git(source, 'rev-parse', 'HEAD')
            server = work / 'server'
            self.git(work, 'clone', str(source), str(server))
            (source / 'scripts').mkdir()
            (source / 'docs').mkdir()
            (source / 'tasks').mkdir()
            migrations = source / 'migrations/versions'
            migrations.mkdir(parents=True)
            (migrations / '0100.py').write_text("revision='0100_packaging_history_guard'\ndown_revision=None\n")
            (migrations / '0101.py').write_text("revision='0101_manual_brigade_origins'\ndown_revision='0100_packaging_history_guard'\n")
            for name in ('unified_release.py', 'release_database_check.py'):
                shutil.copyfile(SCRIPTS / name, source / 'scripts' / name)
            (source / 'docs/unified-release.md').write_text('Runbook')
            (source / 'docs/deployment-retention.md').write_text('Retention rules')
            (source / 'tasks/unified-release-review.md').write_text('Verification report')
            self.commit(source, 'first change')
            (source / 'app.txt').write_text('all changes installed')
            self.commit(source, 'second change')
            (source / '.env').write_text('DO_NOT_PACKAGE=this-is-not-a-real-secret\n')
            artifact = work / 'release.tar.gz'
            release.pack(SimpleNamespace(app_root=source, base=base, output=artifact))
            extracted = work / 'extracted'
            with tarfile.open(artifact) as archive:
                self.assertFalse(any('.env' == Path(member.name).name for member in archive.getmembers()))
                archive.extractall(extracted, filter='data')
            package = next(extracted.iterdir())
            manifest = release.load_package(package)
            self.assertEqual(len(manifest['commits']), 2)
            self.assertEqual(manifest['base'], base)
            self.git(server, 'bundle', 'verify', str(package / 'release.bundle'))
            self.git(server, 'fetch', str(package / 'release.bundle'), 'HEAD')
            self.git(server, 'merge', '--ff-only', 'FETCH_HEAD')
            self.assertEqual(self.git(server, 'rev-parse', 'HEAD'), manifest['head'])
            self.assertEqual((server / 'app.txt').read_text(), 'all changes installed')
            self.assertFalse((server / '.env').exists())
            self.assertTrue(release.clean_tracked(server))
            (server / 'app.txt').write_text('local server edit must survive')
            self.assertFalse(release.clean_tracked(server))
            self.git(server, 'add', 'app.txt')
            self.assertFalse(release.clean_tracked(server))
            (package / 'release.bundle').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                release.load_package(package)

    def test_frontend_backup_copies_current_assets_and_public_files_without_old_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build'
            (build / 'static/js').mkdir(parents=True)
            (build / 'static/js/current.js').write_text('current')
            (build / 'static/js/old.js').write_text('old')
            (build / 'index.html').write_text('<html>current</html>')
            (build / 'favicon.ico').write_bytes(b'icon')
            (build / 'asset-manifest.json').write_text(json.dumps({
                'files': {'main.js': '/static/js/current.js'}, 'entrypoints': ['static/js/current.js']}))
            backup = root / 'backup'
            release.backup_frontend(build, backup)
            self.assertTrue((backup / 'static/js/current.js').is_file())
            self.assertTrue((backup / 'favicon.ico').is_file())
            self.assertTrue((backup / 'index.html').is_file())
            self.assertFalse((backup / 'static/js/old.js').exists())

    def test_frontend_manifest_rejects_path_escape_and_symlinked_parents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build'
            build.mkdir()
            (root / 'outside.js').write_text('outside')
            (build / 'linked').symlink_to(root, target_is_directory=True)
            for asset in ('../outside.js', 'linked/outside.js', '//example.invalid/x.js', 'https://example.invalid/x.js'):
                with self.subTest(asset=asset):
                    (build / 'asset-manifest.json').write_text(json.dumps({'files': {'main.js': asset}}))
                    with self.assertRaises(ValueError):
                        release.manifest_files(build)

    def test_database_target_must_be_explicit_and_not_development_defaults(self):
        dbspec = importlib.util.spec_from_file_location('release_database_check', SCRIPTS / 'release_database_check.py')
        database = importlib.util.module_from_spec(dbspec)
        dbspec.loader.exec_module(database)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_DATABASE_SETTINGS_REQUIRED'):
            database.connection_settings({})
        settings = database.connection_settings({'DB_NAME': 'explicit', 'DB_HOST': '/isolated/socket', 'DB_USER': 'test'})
        self.assertEqual(settings['dbname'], 'explicit')
        self.assertEqual(settings['host'], '/isolated/socket')

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, root, message):
        self.git(root, 'add', '.')
        self.git(root, 'commit', '-m', message)


if __name__ == '__main__':
    unittest.main()
