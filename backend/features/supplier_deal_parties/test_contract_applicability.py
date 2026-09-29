import datetime as dt
import unittest
from unittest.mock import Mock
from pydantic import ValidationError
from .contract_applicability import ContractApplicability, eligible_applicability, offer_project


class ApplicabilityTests(unittest.TestCase):
    def test_dates_inclusive_and_unknown_not_eligible(self):
        value={'scope':'company','term':'fixed','startsOn':'2026-09-01','endsOn':'2026-09-30'}
        for day,expected in [('2026-08-31',False),('2026-09-01',True),('2026-09-30',True),('2026-10-01',False)]:
            self.assertEqual(eligible_applicability({'applicability':value},today=dt.date.fromisoformat(day)),expected)
        self.assertFalse(eligible_applicability({}))
        self.assertFalse(eligible_applicability({'applicability':{}}))

    def test_open_ended_and_exact_project(self):
        value={'scope':'project','projectId':44,'term':'open_ended','startsOn':'2020-01-01'}
        self.assertTrue(eligible_applicability({'applicability':value},44))
        self.assertFalse(eligible_applicability({'applicability':value},45))
        self.assertFalse(eligible_applicability({'applicability':value}))

    def test_incoherent_conditions_rejected(self):
        value={'scope':'company','term':'open_ended','startsOn':'2026-09-01'}
        for change in ({'scope':'project'},{'projectId':44},{'term':'fixed'},
                       {'endsOn':'2026-09-02'},{'term':'fixed','endsOn':'2026-08-01'}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ContractApplicability(**{**value,**change})

    def test_ambiguous_project_is_not_selected(self):
        cur=Mock();offer={'company_id':1,'project':'Object'}
        for rows in ([],[{'id':1,'name':'Object'},{'id':2,'name':'Object'}]):
            cur.fetchall.return_value=rows
            self.assertIsNone(offer_project(cur,offer))
        cur.fetchall.return_value=[{'id':1,'name':'Object'}]
        self.assertEqual(offer_project(cur,offer)['id'],1)
        self.assertEqual(cur.execute.call_args.args[1],(1,'Object'))
