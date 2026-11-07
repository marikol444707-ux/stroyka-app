"""Manual creation never reads users or guesses an identity from a display name."""
import unittest
from uuid import uuid4

from fastapi import HTTPException

from ..brigade_access.service import resolve_brigade_contractor_user
from ..brigade_access.test_service import SequencedCursor
from .manual import command_evidence


class ManualContractCommandTests(unittest.TestCase):
    def test_explicit_manual_selection_returns_no_account_without_any_lookup(self):
        cur = SequencedCursor()
        self.assertIsNone(resolve_brigade_contractor_user(cur, 2, None, 'Same name as real user',
            contractor_ref={'type':'manual','requestId':str(uuid4())}))
        self.assertEqual(cur.calls, [])

    def test_manual_selection_rejects_an_account_or_invalid_command_instead_of_legacy_matching(self):
        for reference, user_id in (({'type':'manual','requestId':str(uuid4())}, 23),
                ({'type':'manual','requestId':str(uuid4()),'id':23}, None),
                ({'type':'manual'}, None), ({'type':'manual','requestId':True}, None),
                ({'type':'manual','requestId':'not-a-uuid'}, None)):
            cur = SequencedCursor()
            with self.subTest(reference=reference), self.assertRaises(HTTPException) as raised:
                resolve_brigade_contractor_user(cur,2,user_id,'Same name',contractor_ref=reference)
            self.assertEqual(raised.exception.status_code,400)
            self.assertEqual(cur.calls,[])

    def test_replay_fingerprint_binds_actor_company_source_and_entire_payload(self):
        ref = {'type':'manual','requestId':str(uuid4())}
        args = {'company_id':2,'project_id':17,'actor_id':11,'command':'create_contract',
                'payload':{'brigadeName':'Manual','contractorRef':ref}}
        baseline = command_evidence(ref,**args)
        self.assertEqual(baseline, command_evidence(ref,**args))
        for change in ({'company_id':3},{'actor_id':12},{'project_id':18},
                       {'command':'estimate_assignment:25'}, {'payload':{'brigadeName':'Different'}}):
            self.assertNotEqual(baseline,command_evidence(ref,**{**args,**change}))
