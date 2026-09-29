import copy
import unittest

from .reviewed_plan import build_reviewed_alias_plan, legacy_alias_fingerprint


class ReviewedPlanTests(unittest.TestCase):
    def setUp(self):
        self.source = {'id': 9, 'active': True, 'project_name': 'Школа',
                       'alias_name': 'Марка', 'canonical_name': 'Цемент', 'canonical_unit': 'кг'}
        self.projects = [{'id': 7, 'company_id': 2, 'name': 'Школа'},
                         {'id': 8, 'company_id': 3, 'name': 'Школа'}]
        self.decision = {'aliasId': 9, 'sourceFingerprint': legacy_alias_fingerprint(self.source),
                         'companyId': 2, 'projectId': 7, 'reviewedById': 11,
                         'evidenceRef': 'review/9'}

    def plan(self, decisions=None, existing=()):
        return build_reviewed_alias_plan(2, [self.source], self.projects,
                                        [self.decision] if decisions is None else decisions, existing)

    def test_confirmed_plan_is_read_only_and_redacted(self):
        before = copy.deepcopy((self.source, self.projects, self.decision))
        result = self.plan()
        self.assertEqual(result['reviewedCount'], 1)
        self.assertEqual(result['writesAttempted'], 0)
        self.assertFalse(result['readyForCutover'])
        self.assertNotIn('Цемент', str(result))
        self.assertEqual(before, (self.source, self.projects, self.decision))

    def test_no_inference_from_even_unique_name(self):
        self.projects = self.projects[:1]
        self.assertEqual(self.plan([])['issues'][0]['reasonCode'], 'missing_review')

    def test_boolean_and_float_ids_cannot_alias_integer_keys(self):
        self.source['id'] = 1
        self.decision['sourceFingerprint'] = legacy_alias_fingerprint(self.source)
        for malformed in (True, 1.0, '1'):
            with self.subTest(alias_id=malformed):
                self.decision['aliasId'] = malformed
                result = self.plan()
                self.assertEqual(result['reviewedCount'], 0)
                self.assertIn('invalid_review_id', [issue['reasonCode'] for issue in result['issues']])

    def test_stale_source(self):
        self.source['canonical_unit'] = 'т'
        self.assertEqual(self.plan()['issues'][0]['reasonCode'], 'stale_source')

    def test_foreign_project_or_company_rejected(self):
        self.decision['projectId'] = 8
        self.assertEqual(self.plan()['reviewedCount'], 0)
        self.decision.update(projectId=7, companyId=3)
        self.assertEqual(self.plan()['reviewedCount'], 0)

    def test_duplicate_review_rejected(self):
        self.assertEqual(self.plan([self.decision, self.decision])['issues'][0]['reasonCode'], 'duplicate_review')

    def test_proof_and_reviewer_required(self):
        self.decision['evidenceRef'] = ''
        self.assertEqual(self.plan()['reviewedCount'], 0)
        self.decision.update(evidenceRef='review/9', reviewedById=True)
        self.assertEqual(self.plan()['reviewedCount'], 0)

    def test_existing_normalized_key_is_never_overwritten(self):
        existing = [{'company_id': 2, 'project_id': 7, 'alias_name': 'Марка.', 'active': True}]
        self.assertEqual(self.plan(existing=existing)['issues'][0]['reasonCode'], 'existing_owned_key')

    def test_unknown_and_inactive_sources_rejected(self):
        self.decision['aliasId'] = 999
        self.assertEqual(self.plan()['reviewedCount'], 0)
        self.decision['aliasId'] = 9
        self.source['active'] = False
        self.assertEqual(self.plan()['reviewedCount'], 0)

    def test_common_scope_requires_explicit_null(self):
        del self.decision['projectId']
        self.assertEqual(self.plan()['reviewedCount'], 0)
        self.decision['projectId'] = None
        self.assertEqual(self.plan()['reviewedCount'], 1)

    def test_two_sources_cannot_claim_one_key(self):
        second = {**self.source, 'id': 10}
        review = {**self.decision, 'aliasId': 10, 'sourceFingerprint': legacy_alias_fingerprint(second)}
        result = build_reviewed_alias_plan(2, [self.source, second], self.projects, [self.decision, review], [])
        self.assertEqual(result['reviewedCount'], 0)
        self.assertTrue(all(i['reasonCode'] == 'duplicate_target_key' for i in result['issues']))
