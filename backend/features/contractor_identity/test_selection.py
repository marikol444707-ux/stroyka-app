"""Explicit selections never fall back to legacy numeric/name matching."""
import unittest

from fastapi import HTTPException

from ..brigade_access.service import resolve_brigade_contractor_user
from ..brigade_access.test_service import SequencedCursor


class TypedContractorSelectionTests(unittest.TestCase):
    def test_staff_number_selects_its_linked_user_even_when_a_user_has_that_number(self):
        cur=SequencedCursor(one=[(23,)],many=[[(41,)]])
        self.assertEqual(resolve_brigade_contractor_user(cur,4,23,'Other name',
            contractor_ref={'type':'staff','id':23}),41)
        self.assertNotIn('LOWER', ' '.join(sql for sql,_ in cur.calls))

    def test_user_namespace_never_looks_up_staff_with_the_same_id(self):
        cur=SequencedCursor(many=[[(23,)]])
        self.assertEqual(resolve_brigade_contractor_user(cur,4,23,'Changed display name',
            contractor_ref={'type':'user','id':23}),23)
        self.assertEqual(len(cur.calls),1)

    def test_missing_or_ambiguous_staff_links_do_not_guess_by_name_or_email(self):
        for matches in ([], [(41,),(42,)]):
            with self.subTest(matches=matches), self.assertRaises(HTTPException) as raised:
                resolve_brigade_contractor_user(SequencedCursor(one=[(23,)],many=[matches]),4,23,'Иван',
                    contractor_ref={'type':'staff','id':23})
            self.assertEqual(raised.exception.status_code,409)

    def test_invalid_reference_cannot_downgrade_to_the_legacy_resolver(self):
        for reference in (None,{},[],{'type':'contractor','id':23},{'type':'user','id':True},
                          {'type':'staff','id':1.5},{'type':'user','id':0},
                          {'type':'user','id':23,'companyId':3}):
            cur=SequencedCursor(many=[[(23,)]])
            with self.subTest(reference=reference), self.assertRaises(HTTPException) as raised:
                resolve_brigade_contractor_user(cur,4,23,'Иван',contractor_ref=reference)
            self.assertEqual(raised.exception.status_code,400)
            self.assertEqual(cur.calls,[])

    def test_conflicting_legacy_id_is_rejected_before_reading_any_identity(self):
        cur=SequencedCursor()
        with self.assertRaises(HTTPException) as raised:
            resolve_brigade_contractor_user(cur,4,41,'Иван',contractor_ref={'type':'staff','id':23})
        self.assertEqual(raised.exception.status_code,400)
        self.assertEqual(cur.calls,[])
