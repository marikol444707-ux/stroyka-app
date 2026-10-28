import json
import unittest
from unittest.mock import patch

from .cli_plan import build_cli_plan, EXECUTABLE
from .contract import validate_v2_request, InvalidRequest
from .state import Scope, StorageError


def request(**changes):
    return validate_v2_request({'version':2,'request_id':'search-fixture-001',
        'region':'Ставропольский край','sources':['commercial','eis'],
        'topics':['кровля'], **changes})


class CLIPlanTests(unittest.TestCase):
    def test_commercial_selection_is_on_stdin_and_only_contains_supported_profile_fields(self):
        req=request(commercial_sources=['Росэлторг'], price_min_rub=1000000)
        plan=build_cli_plan(req,Scope(37,'fixture-owner'))
        call=next(item for item in plan.calls if item.source=='commercial')
        self.assertEqual(call.argv,(EXECUTABLE,'commercial-search','--profile-stdin'))
        data=json.loads(call.stdin)
        self.assertEqual(set(data),{'companyId','region','searchTerms','sourceProviders'})
        self.assertEqual(data['companyId'],37)
        self.assertEqual(data['sourceProviders'],['Росэлторг'])
        self.assertEqual(data['searchTerms'],req.company_profile(37)['searchTerms'])
        self.assertTrue(plan.postfilter_required)
        self.assertFalse(plan.installed_cli_verified)

    def test_eis_regimes_are_not_silently_substituted(self):
        plan=build_cli_plan(request(sources=['eis']),Scope(37,'fixture-owner'))
        self.assertEqual(set(plan.unsupported),{('eis','223-ФЗ'),('eis','615-ПП')})
        self.assertTrue(plan.calls)
        for call in plan.calls:
            self.assertEqual(call.argv[1:3],('eis-search','--query'))
            self.assertEqual(call.argv[-1],'--stavropol-open')
            self.assertIsNone(call.stdin)

    def test_eis_only_unsupported_regimes_never_launch_44_search(self):
        plan=build_cli_plan(request(sources=['eis'],legal_regimes=['223-ФЗ']),Scope(37,'fixture-owner'))
        self.assertEqual(plan.calls,())
        self.assertEqual(plan.unsupported,(('eis','223-ФЗ'),))

    def test_shell_text_is_a_single_query_argument_and_never_executed(self):
        with patch('subprocess.run') as run:
            plan=build_cli_plan(request(keywords=['ремонт; $(id)']),Scope(37,'fixture-owner'))
        run.assert_not_called()
        eis=[call for call in plan.calls if call.query=='ремонт; $(id)']
        self.assertEqual(len(eis),1)
        self.assertEqual(eis[0].argv[3],'ремонт; $(id)')

    def test_protected_company_cannot_come_from_request_and_has_no_fallback(self):
        with self.assertRaises(InvalidRequest):request(companyId=99)
        for company in (None,True,0,-1):
            with self.subTest(company=company),self.assertRaises(StorageError):
                build_cli_plan(request(),Scope(company,'fixture-owner'))

    def test_does_not_add_unrequested_sources_or_duplicate_queries(self):
        plan=build_cli_plan(request(sources=['commercial']),Scope(37,'fixture-owner'))
        self.assertEqual([call.source for call in plan.calls],['commercial'])
        plan=build_cli_plan(request(sources=['eis'],keywords=['кровля','КРОВЛЯ']),Scope(37,'fixture-owner'))
        queries=[call.query.casefold() for call in plan.calls]
        self.assertEqual(len(queries),len(set(queries)))


if __name__=='__main__':unittest.main()
