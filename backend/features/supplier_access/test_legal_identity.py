"""Legal formatting never creates identity from unrelated text."""
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from .legal_identity import canonical_legal, legal_sql, legal_lock_keys, lock_legal_keys, SEPARATORS
from . import profile


class LegalIdentityTests(unittest.TestCase):
    def test_only_explicit_formatting_separators_are_ignored(self):
        for separator in SEPARATORS:
            self.assertEqual(canonical_legal(separator.join('2312254452'), (10, 12)), '2312254452')
        self.assertEqual(canonical_legal('123456789012', (10, 12)), '123456789012')
        self.assertEqual(canonical_legal('1234567890123', (13, 15)), '1234567890123')
        for value in ('INN2312254452', '23/12254452', '23.12254452', '２３１２２５４４５２',
                      '231225445', '23122544521', '2312254452123', '23\u200b12254452'):
            self.assertIsNone(canonical_legal(value, (10, 12)), value)
        for value in (None, '', ' - \t'):
            self.assertEqual(canonical_legal(value, (10, 12)), '')

    def test_lock_keys_include_old_raw_and_canonical_in_one_order(self):
        values = [('inn', '23-1225 4452'), ('ogrn', '1234567890123'), ('inn', '2312254452')]
        self.assertEqual(legal_lock_keys(values), ['1234567890123', '23-1225 4452', '2312254452'])
        cursor = Mock()
        lock_legal_keys(cursor, values)
        self.assertEqual([call.args[1][0] for call in cursor.execute.call_args_list],
                         ['supplier-legal:' + key for key in legal_lock_keys(values)])

    def test_sql_does_not_strip_arbitrary_nondigits(self):
        sql = legal_sql('s.inn', (10, 12))
        self.assertIn('translate(COALESCE(s.inn', sql)
        self.assertIn("~ '^([0-9]{10}|[0-9]{12})$'", sql)
        self.assertIn('ELSE NULL', sql)
        self.assertIn('\\013', sql)
        with self.assertRaises(ValueError):
            legal_sql('inn; DROP TABLE suppliers', (10, 12))


class ProfileIdentityTests(unittest.TestCase):
    def record(self, inn='', ogrn='', version='v1'):
        return {'fields': {**{key: '' for key in profile.FIELDS}, 'inn': inn, 'ogrn': ogrn}, 'version': version}

    def test_identity_locks_precede_row_and_leader_locks(self):
        events = []
        cursor = Mock()
        cursor.fetchone.return_value = None
        before = self.record()
        def load(cur, sid, lock=False):
            events.append('row-lock' if lock else 'read')
            return before
        with patch.object(profile, 'load', side_effect=load), \
             patch.object(profile, 'lock_legal_keys', side_effect=lambda *args: events.append('legal-lock')):
            profile.update(cursor, 7, {'inn': '23-1225 4452'}, authorize_write=lambda: events.append('leader-lock'))
        self.assertEqual(events[:4], ['read', 'legal-lock', 'row-lock', 'leader-lock'])
        self.assertIn(('2312254452', 7), [call.args[1] for call in cursor.execute.call_args_list])
        self.assertEqual(cursor.execute.call_args.args[1], ['2312254452', 7])

    def test_conflicting_cabinet_and_changed_identity_do_not_write(self):
        cursor = Mock()
        cursor.fetchone.return_value = {'exists': 1}
        with patch.object(profile, 'load', return_value=self.record()), patch.object(profile, 'lock_legal_keys'):
            with self.assertRaises(HTTPException) as error:
                profile.update(cursor, 7, {'inn': '2312254452'})
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any(call.args[0].startswith('UPDATE') for call in cursor.execute.call_args_list))
        cursor.reset_mock()
        with patch.object(profile, 'load', side_effect=[self.record(), self.record('1234567890')]), \
             patch.object(profile, 'lock_legal_keys'):
            with self.assertRaises(HTTPException) as error:
                profile.update(cursor, 7, {'phone': 'new'})
        self.assertEqual(error.exception.status_code, 409)
        cursor.execute.assert_not_called()

    def test_malformed_identity_rejected_before_database(self):
        cursor = Mock()
        with self.assertRaises(HTTPException) as error:
            profile.update(cursor, 7, {'inn': 'INN2312254452'})
        self.assertEqual(error.exception.status_code, 422)
        cursor.execute.assert_not_called()
