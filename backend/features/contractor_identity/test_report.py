"""Legacy identity decisions cannot depend on names, contacts or numeric guesses."""
from contextlib import redirect_stdout
import io
import json
import os
import unittest
from unittest.mock import patch

from .report import classify_reference, main, positive_id, run_audit
from ..contractor_contract_parties.snapshot import snapshot_digest


def candidate():
    return dict(id=71, company_id=2, project_id=17, project_company_id=2, contractor_id=23,
                status='Черновик', user_id=23, user_active=True, membership_ids=[9],
                membership_roles=['субподрядчик'], staff_id=None, staff_user_ids=[],
                party_snapshot_json=None, party_snapshot_hash=None)


def frozen(row, **changes):
    snapshot = {'schemaVersion': 1, 'customer': {'companyId': 2}, 'contractor': {'userId': 23},
                'project': {'id': 17}, 'contract': {'id': 71}, **changes}
    return {**row, 'status': 'Подписан', 'party_snapshot_json': snapshot,
            'party_snapshot_hash': snapshot_digest(snapshot)}


class ContractorReferenceTests(unittest.TestCase):
    def test_exact_user_is_a_review_candidate_without_a_grant(self):
        self.assertEqual(classify_reference(candidate()), {
            'contractId': 71, 'status': 'review_required', 'reason': 'CANDIDATE_USER_REFERENCE',
            'reference': {'type': 'user', 'id': 23}})

    def test_same_numeric_staff_id_requires_exact_persisted_link(self):
        for links in ([], [41], [23, 41]):
            with self.subTest(links=links):
                result = classify_reference({**candidate(), 'staff_id': 23, 'staff_user_ids': links,
                    'name': 'Одинаковое имя', 'email': 'same@local.invalid'})
                self.assertEqual(result['reason'], 'AMBIGUOUS_USER_STAFF_ID')
                self.assertIsNone(result['reference'])
        row = {**candidate(), 'staff_id': 23, 'staff_user_ids': [23]}
        self.assertEqual(classify_reference(row)['reference'], {'type': 'user', 'id': 23})

    def test_staff_only_id_does_not_turn_into_its_linked_user(self):
        row = {**candidate(), 'user_id': None, 'staff_id': 23, 'staff_user_ids': [41]}
        self.assertEqual(classify_reference(row)['reason'], 'LEGACY_STAFF_REFERENCE_UNVERIFIED')
        self.assertIsNone(classify_reference(row)['reference'])

    def test_name_or_email_never_links_a_contract_without_user_id(self):
        row = {**candidate(), 'contractor_id': None, 'name': 'Мастер Иван', 'email': 'same@local.invalid'}
        self.assertEqual(classify_reference(row)['reason'], 'UNLINKED_LEGACY_CONTRACT')
        self.assertIsNone(classify_reference(row)['reference'])

    def test_revoked_or_missing_membership_is_not_replaced_with_a_legacy_company_id(self):
        row = {**candidate(), 'membership_ids': [], 'user_company_id': 2}
        self.assertEqual(classify_reference(row)['reason'], 'COMPANY_MEMBERSHIP_UNVERIFIED')

    def test_inactive_user_and_nonperformer_membership_are_blocked(self):
        self.assertEqual(classify_reference({**candidate(), 'user_active': False})['reason'], 'USER_INACTIVE')
        self.assertEqual(classify_reference({**candidate(), 'membership_roles': ['директор']})['reason'],
                         'PERFORMER_ROLE_UNVERIFIED')

    def test_foreign_or_unknown_project_never_becomes_a_candidate(self):
        for change in ({'project_company_id': 3}, {'project_company_id': None}, {'project_id': None}):
            with self.subTest(change=change):
                self.assertEqual(classify_reference({**candidate(), **change})['reason'], 'PROJECT_OWNER_UNVERIFIED')

    def test_verified_frozen_user_namespace_disambiguates_staff_collision(self):
        row = frozen({**candidate(), 'staff_id': 23, 'staff_user_ids': [41]})
        self.assertEqual(classify_reference(row)['reason'], 'FROZEN_USER_REFERENCE')
        self.assertEqual(classify_reference(row)['reference'], {'type': 'user', 'id': 23})

    def test_frozen_party_hash_and_all_owner_coordinates_are_required(self):
        for changes in ({'customer': {'companyId': 3}}, {'contractor': {'userId': 41}},
                        {'project': {'id': 18}}, {'contract': {'id': 72}},
                        {'contractor': {'userId': True}}, {'schemaVersion': 2}, {'schemaVersion': True}):
            with self.subTest(changes=changes):
                self.assertEqual(classify_reference(frozen(candidate(), **changes))['status'], 'blocked')
        row = frozen(candidate())
        row['party_snapshot_json']['contractor']['userId'] = 41
        self.assertEqual(classify_reference(row)['reason'], 'FROZEN_IDENTITY_UNVERIFIED')
        self.assertEqual(classify_reference({**candidate(), 'status': 'Подписан'})['reason'], 'SIGNED_IDENTITY_MISSING')

    def test_ids_are_strict_and_not_coerced(self):
        for value in (True, False, 0, -1, 1.5, '23', None, 2147483648):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_id(value)

    def test_failure_rolls_back_and_closes_without_exposing_driver_error(self):
        from unittest.mock import MagicMock
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError('private database error')
        with self.assertRaises(RuntimeError):
            run_audit(lambda: conn, 2)
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()
        conn.commit.assert_not_called()

    def test_cli_does_not_load_ambient_config_or_print_a_failed_dsn(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'CONTRACTOR_IDENTITY_AUDIT_DSN': 'private credential'}, clear=True), \
                patch('psycopg2.connect', side_effect=RuntimeError('private credential')), redirect_stdout(output):
            status = main(['--company-id', '2', '--read-only'])
        self.assertEqual(status, 2)
        self.assertNotIn('private', output.getvalue())
        self.assertFalse(json.loads(output.getvalue())['canApply'])


if __name__ == '__main__':
    unittest.main()
