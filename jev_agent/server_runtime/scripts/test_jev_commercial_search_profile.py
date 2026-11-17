import importlib.util
import json
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import patch
import unittest


SCRIPT = Path(__file__).with_name('jev_commercial_search.py')
SPEC = importlib.util.spec_from_file_location('jev_commercial_search_profile_subject', SCRIPT)
jev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jev)


class CompanyProfileTests(unittest.TestCase):
    def test_search_report_has_uuid_for_safe_retries_of_same_report(self):
        from uuid import UUID

        report = jev.build_report([], [{
            'provider': 'B2B-Center', 'query': 'ремонт', 'ok': True,
            'status': 'observed_first_page', 'rows': 0,
        }])

        UUID(report['run_id'])
        self.assertEqual(report['sources'][0]['rows'], 0)

    def test_normalizes_company_profile_and_removes_duplicates(self):
        profile = jev.normalize_company_profile({
            'companyId': 23,
            'region': 'Ставропольский край',
            'searchTerms': ['  школа  ', 'школа', 'кровля'],
            'sourceProviders': ['B2B-Center', 'B2B-Center', 'Росэлторг'],
        })

        self.assertEqual(profile, {
            'companyId': 23,
            'region': 'Ставропольский край',
            'searchTerms': ['школа', 'кровля'],
            'sourceProviders': ['B2B-Center', 'Росэлторг'],
        })

    def test_legacy_unprofiled_search_remains_available(self):
        self.assertIsNone(jev.normalize_company_profile(None))

    def test_rejects_invalid_company_region_terms_and_sources(self):
        valid = {'companyId': 23, 'region': 'Ставропольский край',
                 'searchTerms': [], 'sourceProviders': ['B2B-Center']}
        invalid_profiles = (
            {**valid, 'companyId': True},
            {**valid, 'region': 'Москва'},
            {**valid, 'searchTerms': ['x']},
            {**valid, 'searchTerms': ['x' * 81]},
            {**valid, 'searchTerms': ['школа'] * 21},
            {**valid, 'sourceProviders': []},
            {**valid, 'sourceProviders': ['ЕИС']},
        )
        for profile in invalid_profiles:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                jev.normalize_company_profile(profile)

    def test_query_terms_respect_each_providers_length_limit(self):
        custom = ['ремонт кровли', 'x' * 70]
        self.assertEqual(jev.terms_for_source(custom, ('default',), 64), ('ремонт кровли',))
        self.assertEqual(jev.terms_for_source(custom, ('default',), 80), tuple(custom))
        self.assertEqual(jev.terms_for_source(['x' * 70], ('default',), 64), ('default',))

    def test_profile_is_mounted_read_only_with_private_file_permissions(self):
        profile = {'companyId': 23, 'region': 'Ставропольский край',
                   'searchTerms': ['школа'], 'sourceProviders': ['B2B-Center']}
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            if command[0] == 'docker' and command[1] == 'run':
                mount = next(item for item in command if 'dst=/profile.json' in item)
                profile_path = mount.split('src=', 1)[1].split(',dst=', 1)[0]
                self.assertEqual(json.loads(Path(profile_path).read_text()), profile)
                metadata = Path(profile_path).stat()
                self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o400)
                self.assertIn('--profile-file', command)
                self.assertEqual(kwargs['timeout'], 300)
                return SimpleNamespace(returncode=0, stdout='{"ok":true,"sources":[],"confirmed":[],"review":[]}', stderr='')
            return SimpleNamespace(returncode=0, stdout='', stderr='')

        with patch.object(jev.subprocess, 'run', side_effect=fake_run), \
                patch.object(jev.os, 'chown') as chown:
            result = jev.probe(profile)
        self.assertTrue(result['ok'])
        self.assertEqual([call[0][1] for call in calls], ['run', 'rm'])
        chown_args = chown.call_args.args
        self.assertEqual(chown_args[1:], (10001, 10001))
        self.assertEqual(Path(chown_args[0]).name, 'profile.json')


if __name__ == '__main__':
    unittest.main()
