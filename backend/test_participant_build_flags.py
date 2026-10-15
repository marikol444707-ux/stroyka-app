"""Participant rollout settings must reach and match the published interface."""
import importlib.util
import json
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

    def build(self, modes=('1','0'), source='Участники и доступ participant-tickets'):
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
                    root = self.build(('1','1'), source='Участники и доступ participant-tickets /support-access')
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
        verifier.verify(self.build(('1','1'),source='Участники и доступ participant-tickets /support-access'),
                        '\n'.join('REACT_APP_'+name+'=1' for name in NAMES))
        verifier.verify(self.build(('0','0'),source='legacy'), '\n'.join('REACT_APP_'+name+'=0' for name in NAMES))
        with self.assertRaises(ValueError):
            verifier.verify(self.build(), 'REACT_APP_'+NAMES[0]+'=0')

    def test_html_template_exposes_both_build_modes(self):
        template = (ROOT/'public/index.html').read_text()
        for name, metadata in zip(NAMES,METADATA):
            self.assertIn(f'<meta name="{metadata}" content="%REACT_APP_{name}%"', template)
