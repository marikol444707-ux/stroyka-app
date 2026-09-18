"""Ownership candidates are evidence for review, never authorization or backfill."""
import copy
import ast
import json
from pathlib import Path
import unittest

from backend.features.material_aliases.readiness import build_alias_readiness, _alias_key


def alias(**changes):
    return dict(id=1, project_name='School', alias_name='Brand', canonical_name='Cement',
                canonical_unit='kg', active=True, **changes)


class AliasReadinessTests(unittest.TestCase):
    def setUp(self):
        self.projects = [dict(id=10, name='School', company_id=2, archived=False)]

    def report(self, **changes):
        row = alias()
        row.update(changes)
        return build_alias_readiness(self.projects, [row])

    def test_unique_name_is_only_a_candidate_never_an_owner(self):
        result = self.report()
        self.assertEqual(result['reasonCounts'], {'candidate_requires_confirmation': 1})
        self.assertEqual(result['issues'][0]['candidateCompanyIds'], [2])
        self.assertFalse(result['readyForCutover'])
        self.assertEqual(result['automaticAssignments'], 0)

    def test_global_alias_has_no_implicit_company(self):
        result = self.report(project_name='')
        self.assertEqual(result['reasonCounts'], {'global_scope_unowned': 1})
        self.assertNotIn('candidateCompanyIds', result['issues'][0])

    def test_cross_company_name_collision(self):
        self.projects.append(dict(id=11, name='School', company_id=3, archived=False))
        self.assertEqual(self.report()['reasonCounts'], {'cross_company_name_collision': 1})

    def test_same_company_name_collision(self):
        self.projects.append(dict(id=11, name='School', company_id=2, archived=False))
        self.assertEqual(self.report()['reasonCounts'], {'same_company_name_collision': 1})

    def test_archived_project_remains_an_ambiguity_candidate(self):
        self.projects.append(dict(id=11, name='School', company_id=3, archived=True))
        self.assertIn('cross_company_name_collision', self.report()['reasonCounts'])

    def test_missing_project(self):
        self.assertIn('project_not_found', self.report(project_name='Missing')['reasonCounts'])

    def test_invalid_project_owner_does_not_become_company_one(self):
        for value in (None, 0, True, '2'):
            self.projects[0]['company_id'] = value
            self.assertIn('project_owner_invalid', self.report()['reasonCounts'])

    def test_empty_alias_or_target_is_invalid(self):
        for field in ('alias_name', 'canonical_name'):
            self.assertIn('invalid_mapping', self.report(**{field: ' '})['reasonCounts'])

    def test_inactive_rows_counted_but_not_active_blockers(self):
        result = self.report(active=False)
        self.assertEqual(result['summary']['inactiveAliases'], 1)
        self.assertEqual(result['issueCount'], 0)
        self.assertFalse(result['readyForCutover'])

    def test_conflicting_active_targets_are_flagged(self):
        first, second = alias(), alias()
        second.update(id=2, alias_name=' BRAND ', canonical_name='Concrete')
        result = build_alias_readiness(self.projects, [first, second])
        self.assertEqual(result['conflictCount'], 1)
        self.assertEqual(result['conflicts'][0]['aliasIds'], [1, 2])

    def test_inactive_conflict_is_not_counted(self):
        other = alias()
        other.update(id=2, canonical_name='Concrete', active=False)
        self.assertEqual(build_alias_readiness(self.projects, [alias(), other])['conflictCount'], 0)

    def test_summary_counts_survive_preview_limits(self):
        rows = [dict(alias(), id=i) for i in range(1, 5)]
        result = build_alias_readiness(self.projects, rows, preview_limit=1)
        self.assertEqual(result['issueCount'], 4)
        self.assertEqual(len(result['issues']), 1)
        self.assertTrue(result['issuesTruncated'])

    def test_report_excludes_names_and_personal_fields_and_does_not_mutate(self):
        rows = [dict(alias(), updated_by='Private Person', source='private note')]
        before = copy.deepcopy((self.projects, rows))
        result = build_alias_readiness(self.projects, rows)
        for secret in ('School', 'Brand', 'Cement', 'Private Person', 'private note'):
            self.assertNotIn(secret, json.dumps(result))
        self.assertEqual((self.projects, rows), before)

    def test_empty_audit_is_not_permission_to_switch_runtime(self):
        result = build_alias_readiness([], [])
        self.assertEqual(result['issueCount'], 0)
        self.assertFalse(result['readyForCutover'])

    def test_collision_normalization_matches_legacy_without_importing_runtime(self):
        path = Path(__file__).resolve().parents[2] / 'main.py'
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_norm_key_text')
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
        for value in (' Цемент (М500) ', 'A/B\\C', 'a, b; c: d', '«Brand»', 'a\tb\nC', None):
            self.assertEqual(_alias_key(value), namespace['_norm_key_text'](value))
