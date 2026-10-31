import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import re
import shlex
import sys


SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('unified_release', SCRIPTS / 'unified_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class UnifiedReleaseTests(unittest.TestCase):
    def test_systemd_environment_file_quotes_continuations_and_literal_shell_syntax(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'runtime.env'
            marker = Path(temporary) / 'must-not-exist'
            path.write_text('''# comment
; another comment
INVALID LINE
 A =  plain words\x20\x20
B=' single
quoted $HOME '
C="double\\\" \\$literal \\q \\
continued"
D=one\\
two\\ three\\\x20
E=interior"quotes" # literal
EMPTY=
DUPLICATE=first
DUPLICATE=last
BAD-NAME=ignored
''' + f'LITERAL=$(touch {marker})`touch {marker}`${{HOME}}\n' + 'EOF="no trailing newline"')
            values = release.systemd_environment_file(path)
            self.assertEqual(values['A'], 'plain words')
            self.assertEqual(values['B'], ' single\nquoted $HOME ')
            self.assertEqual(values['C'], 'double" $literal \\q continued')
            self.assertEqual(values['D'], 'onetwo three ')
            self.assertEqual(values['E'], 'interior"quotes" # literal')
            self.assertEqual(values['EMPTY'], '')
            self.assertEqual(values['DUPLICATE'], 'last')
            self.assertNotIn('BAD-NAME', values)
            self.assertEqual(values['EOF'], 'no trailing newline')
            self.assertIn('$(touch ', values['LITERAL'])
            self.assertIn('${HOME}', values['LITERAL'])
            self.assertFalse(marker.exists())

    def runtime_fixture(self, root, properties, ambient=None):
        unit_path = '/org/freedesktop/systemd1/unit/stroyka_2eservice'

        def bus(args, **kwargs):
            self.assertTrue(kwargs.get('capture'))
            self.assertEqual(args[:3], ['busctl', '--system', '--json=short'])
            if 'GetUnit' in args:
                self.assertEqual(args[-1], 'stroyka.service')
                return json.dumps({'type': 'o', 'data': [unit_path]})
            self.assertEqual(args[3], 'get-property')
            self.assertEqual(args[5], unit_path if args[-1] != 'Environment' or
                             args[6] != 'org.freedesktop.systemd1.Manager' else '/org/freedesktop/systemd1')
            key = 'ManagerEnvironment' if args[6] == 'org.freedesktop.systemd1.Manager' else args[-1]
            return json.dumps({'type': 'a(sb)' if key == 'EnvironmentFiles' else 'as',
                               'data': properties.get(key, [])})

        with patch.object(release, 'run', side_effect=bus), patch.object(release.shutil, 'which', return_value='/usr/bin/busctl'), \
                patch.dict(os.environ, ambient or {}, clear=True):
            return release.runtime_environment(root, 'stroyka')

    def test_runtime_environment_preserves_systemd_order_and_backend_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'backend').mkdir()
            (root / 'backend/.env').write_text('DB_NAME=fallback\nDB_USER=fallback_user\nWORK_ACCEPTANCE_ENABLED=0\nFALLBACK=yes\n')
            first = root / 'settings with spaces and \\ backslash.env'
            first.write_text('DB_NAME=first\nDB_HOST=/actual/socket\nDB_PASSWORD="literal$`;pass"\nWORK_ACCEPTANCE_ENABLED=0\n')
            second = root / 'last.env'
            second.write_text('DB_NAME=last\nWORK_ACCEPTANCE_ENABLED=1\n')
            env = self.runtime_fixture(root, {
                'PassEnvironment': ['DB_NAME', 'PASSED'],
                'ManagerEnvironment': ['DB_NAME=manager', 'PASSED=yes', 'NOT_PASSED=no'],
                'Environment': ['DB_NAME=unit', 'REMOVE=unit', 'MATCH=matching', 'KEEP=value'],
                'EnvironmentFiles': [[str(first), False], [str(root / 'optional.env'), True], [str(second), False]],
                'UnsetEnvironment': ['REMOVE', 'MATCH=matching', 'KEEP=different'],
            }, {'PATH': '/execution/path', 'DB_NAME': 'wrong_shell_db', 'DB_USER': 'wrong_shell_user',
                'PARTICIPANT_HISTORY_MERGE_ENABLED': '1', 'AUTH_SECRET': 'wrong_shell_secret'})
            self.assertEqual(env['DB_NAME'], 'last')
            self.assertEqual(env['DB_USER'], 'fallback_user')
            self.assertEqual(env['DB_HOST'], '/actual/socket')
            self.assertEqual(env['DB_PASSWORD'], 'literal$`;pass')
            self.assertEqual(env['WORK_ACCEPTANCE_ENABLED'], '1')
            self.assertEqual(env['PATH'], '/execution/path')
            self.assertEqual(env['PASSED'], 'yes')
            self.assertEqual(env['KEEP'], 'value')
            self.assertEqual(env['FALLBACK'], 'yes')
            for key in ('REMOVE', 'MATCH', 'NOT_PASSED', 'AUTH_SECRET', 'PARTICIPANT_HISTORY_MERGE_ENABLED'):
                self.assertNotIn(key, env)
            frontend = release.run(['bash', str(SCRIPTS / 'resolve-frontend-build-env.sh'),
                                    release.frontend_service_environment(env), ''], capture=True)
            self.assertIn('REACT_APP_WORK_ACCEPTANCE_ENABLED=1', frontend.splitlines())
            self.assertIn('REACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED=0', frontend.splitlines())
            self.assertNotIn('literal', release.frontend_service_environment(env))

    def test_runtime_environment_accepts_explicit_service_configuration_without_backend_env(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = self.runtime_fixture(Path(temporary), {'Environment': ['DB_NAME=service', 'DB_USER=user', 'DB_HOST=/socket']})
            self.assertEqual(env['DB_NAME'], 'service')
            self.assertEqual(env['DB_HOST'], '/socket')

    def test_runtime_environment_required_and_optional_globs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '10.env').write_text('DB_NAME=first\n')
            (root / '20.env').write_text('DB_NAME=last\n')
            env = self.runtime_fixture(root, {'EnvironmentFiles': [[str(root / '*.env'), False],
                                                                  [str(root / 'absent*.env'), True]]})
            self.assertEqual(env['DB_NAME'], 'last')
            for pattern in ('absent.env', 'absent*.env'):
                with self.subTest(pattern=pattern), self.assertRaisesRegex(ValueError, 'required|Required'):
                    self.runtime_fixture(root, {'EnvironmentFiles': [[str(root / pattern), False]]})

    def test_frontend_environment_does_not_forward_secrets_or_root_shell_flags(self):
        env = {'DB_PASSWORD': 'do-not-forward', 'AUTH_SECRET': 'do-not-forward',
               'AUTH_SECRET_ENABLED': 'do-not-forward', 'PARTICIPANT_SUPPORT_ENABLED': '1',
               'ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS': '4,5'}
        self.assertEqual(set(shlex.split(release.frontend_service_environment(env))),
                         {'PARTICIPANT_SUPPORT_ENABLED=1', 'ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=4,5'})

    def test_git_delivery_is_blocked_before_any_git_or_install_action(self):
        text = (SCRIPTS / 'install-unified-from-git.sh').read_text()
        self.assertIn('integration 0104-to-0109 requires release acceptance', text)
        self.assertLess(text.index('exit 1'), text.index('git fetch'))
        self.assertLess(text.index('exit 1'), text.index('mktemp'))

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
            (migrations / '0102.py').write_text("revision='0102_job_candidates'\ndown_revision='0101_manual_brigade_origins'\n")
            (migrations / '0103.py').write_text("revision='0103_platform_company_features'\ndown_revision='0102_job_candidates'\n")
            (migrations / '0104.py').write_text("revision='0104_jev_search_run_history'\ndown_revision='0103_platform_company_features'\n")
            parent = release.BASE_REVISION
            for i, revision in enumerate(release.PENDING_REVISIONS):
                (migrations / f'audit_{i}.py').write_text(f'revision={revision!r}\ndown_revision={parent!r}\n')
                parent = revision
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
                members = archive.getmembers()
                for member in members:
                    destination = (extracted / member.name).resolve()
                    self.assertTrue(destination == extracted.resolve() or extracted.resolve() in destination.parents)
                    self.assertFalse(member.issym() or member.islnk())
                if 'filter' in __import__('inspect').signature(archive.extractall).parameters:
                    archive.extractall(extracted, members=members, filter='data')
                else:
                    archive.extractall(extracted, members=members)
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
