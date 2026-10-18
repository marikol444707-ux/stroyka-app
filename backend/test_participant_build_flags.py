"""Participant rollout settings must reach and match the published interface."""
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('PARTICIPANT_SUPPORT_ENABLED', 'PARTICIPANT_SUPPORT_ACCESS_ENABLED')
METADATA = ('stroyka-participant-support', 'stroyka-participant-support-access')
spec = importlib.util.spec_from_file_location('participant_build_verify', ROOT/'scripts/verify-frontend-feature-build.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ParticipantBuildFlagsTests(unittest.TestCase):
    def resolve(self, service='', contents=''):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'backend.env'
            path.write_text(contents)
            return subprocess.run(['bash', str(ROOT/'scripts/resolve-frontend-build-env.sh'), service, str(path)],
                                  capture_output=True, text=True)

    def test_default_off_is_explicit(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in NAMES:
            self.assertIn('REACT_APP_'+name+'=0', result.stdout.splitlines())

    def test_file_enables_both_modes_without_exposing_unrelated_values(self):
        result = self.resolve(contents='PRIVATE_KEY=do-not-print\n'+'\n'.join(name+'="1"' for name in NAMES))
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in NAMES:
            self.assertIn('REACT_APP_'+name+'=1', result.stdout.splitlines())
        self.assertNotIn('do-not-print', result.stdout+result.stderr)

    def test_service_precedence_and_first_file_value_match_backend(self):
        for service, contents, expected in (
            (NAMES[0]+'=1', NAMES[0]+'=0', '1'),
            (NAMES[0]+'=0', NAMES[0]+'=1', '0'),
            ('', NAMES[0]+'=0\n'+NAMES[0]+'=1', '0'),
        ):
            with self.subTest(service=service, contents=contents):
                result = self.resolve(service, contents)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('REACT_APP_'+NAMES[0]+'='+expected, result.stdout.splitlines())

    def test_invalid_values_block_build_without_printing_them(self):
        for name in NAMES:
            result = self.resolve(name+'=private-invalid')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertNotIn('private-invalid', result.stderr)

    def test_support_access_requires_the_base_section(self):
        result = self.resolve(NAMES[1]+'=1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_assignment_enabled_path_preserves_participant_mode(self):
        result = self.resolve('ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true '
                              'ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=2 '+NAMES[0]+'=1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('REACT_APP_'+NAMES[0]+'=1', result.stdout.splitlines())

    def build(self, modes=('1','0'), source='organization-participants participant-tickets'):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root/'index.html').write_text(''.join(f'<meta name="{key}" content="{value}">' for key,value in zip(METADATA,modes)))
        (root/'main.js').write_text(source)
        (root/'asset-manifest.json').write_text(json.dumps({'files':{'main.js':'/main.js'}}))
        return root

    def test_each_mode_rejects_mismatched_missing_or_duplicate_metadata(self):
        for index, name in enumerate(NAMES):
            for value in ('0', '%REACT_APP_'+name+'%', None, 'duplicate'):
                with self.subTest(name=name, value=value):
                    root = self.build(('1','1'), source='organization-participants participant-tickets /support-access')
                    html = (root/'index.html').read_text()
                    tag = f'<meta name="{METADATA[index]}" content="1">'
                    replacement = '' if value is None else (tag+tag if value=='duplicate' else tag.replace('content="1"', f'content="{value}"'))
                    (root/'index.html').write_text(html.replace(tag,replacement))
                    with self.assertRaises(ValueError):
                        verifier.verify(root, 'REACT_APP_'+name+'=1')

    def test_enabled_modes_require_their_workflows(self):
        for name in NAMES:
            with self.subTest(name=name), self.assertRaises(ValueError):
                verifier.verify(self.build(('1','1'),source='legacy'), 'REACT_APP_'+name+'=1')

    def test_matching_enabled_and_disabled_builds_pass(self):
        verifier.verify(self.build(), 'REACT_APP_'+NAMES[0]+'=1\nREACT_APP_'+NAMES[1]+'=0')
        verifier.verify(self.build(('1','1'),source='organization-participants participant-tickets /support-access'),
                        '\n'.join('REACT_APP_'+name+'=1' for name in NAMES))
        verifier.verify(self.build(('0','0'),source='legacy'), '\n'.join('REACT_APP_'+name+'=0' for name in NAMES))
        with self.assertRaises(ValueError):
            verifier.verify(self.build(), 'REACT_APP_'+NAMES[0]+'=0')

    def test_html_template_exposes_both_build_modes(self):
        template = (ROOT/'public/index.html').read_text()
        for name, metadata in zip(NAMES,METADATA):
            self.assertIn(f'<meta name="{metadata}" content="%REACT_APP_{name}%"', template)

    def ui_names(self):
        return sorted(set().union(*(set(re.findall(r'REACT_APP_(PARTICIPANT_[A-Z_]+)', path.read_text()))
                                   for path in (ROOT/'src').rglob('*')
                                   if path.suffix in ('.js','.jsx','.ts','.tsx') and '.test.' not in path.name and '.spec.' not in path.name)))

    def test_every_participant_ui_gate_is_exported_default_off_and_has_metadata(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        flags = dict(line.split('=',1) for line in result.stdout.splitlines())
        exported = {key.removeprefix('REACT_APP_') for key in flags if key.startswith('REACT_APP_PARTICIPANT_')}
        self.assertEqual(exported, set(self.ui_names()))
        template = (ROOT/'public/index.html').read_text()
        for name in self.ui_names():
            self.assertEqual(flags['REACT_APP_'+name], '0')
            self.assertIn('content="%REACT_APP_'+name+'%"', template)

    def test_every_ui_mode_honors_service_precedence_and_rejects_invalid_values(self):
        for name in self.ui_names():
            with self.subTest(name=name):
                result = self.resolve('PARTICIPANT_SUPPORT_ENABLED=1 '+name+'=1', name+'=0')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('REACT_APP_'+name+'=1', result.stdout.splitlines())
                invalid = self.resolve(name+'=private-invalid')
                self.assertNotEqual(invalid.returncode, 0)
                self.assertEqual(invalid.stdout, '')
                self.assertNotIn('private-invalid', invalid.stderr)

    def test_every_ui_mode_is_rejected_when_build_metadata_is_missing(self):
        for name in self.ui_names():
            with self.subTest(name=name), self.assertRaises(ValueError):
                verifier.verify(self.build(('0','0'), source='legacy'), 'REACT_APP_'+name+'=1')

    def test_enabled_connections_require_supplier_and_admin_paths(self):
        root = self.build()
        with (root/'index.html').open('a') as target:
            target.write('<meta name="stroyka-participant-connections" content="1">')
        flags = 'REACT_APP_PARTICIPANT_CONNECTIONS_ENABLED=1'
        with self.assertRaises(ValueError):
            verifier.verify(root, flags)
        (root/'main.js').write_text('organization-participants participant-tickets expectedSourceVersion /supplier/connection-requests')
        verifier.verify(root, flags)

    def test_each_ui_mode_accepts_matching_metadata_and_rejects_opposite_mode(self):
        source = 'organization-participants participant-tickets expectedSourceVersion /supplier/connection-requests /history-preview /history-merge-plans /support-access'
        for name in self.ui_names():
            with self.subTest(name=name):
                root = self.build(('1','1'), source=source)
                metadata = 'stroyka-'+name.removesuffix('_ENABLED').lower().replace('_','-')
                tag = f'<meta name="{metadata}" content="1">'
                if name not in NAMES:
                    with (root/'index.html').open('a') as target: target.write(tag)
                verifier.verify(root, 'REACT_APP_'+name+'=1')
                (root/'index.html').write_text((root/'index.html').read_text().replace(tag,tag.replace('content="1"','content="0"')))
                with self.assertRaises(ValueError): verifier.verify(root, 'REACT_APP_'+name+'=1')
