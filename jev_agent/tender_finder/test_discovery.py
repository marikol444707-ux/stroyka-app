import json
import errno
import subprocess
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from .audit_bridge import REVIEWED_RUNTIME
from .cli_result import decode_eis_result
from .contract import REGION, validate_v2_request
from .discovery import discover, verify_installed_runtime, RuntimeMismatch, WRAPPER_SHA256
from .state import Scope

SCOPE = Scope(37,'fixture-owner')


def request(**changes):
    return validate_v2_request({'version':2,'request_id':'search-fixture-001',
        'region':REGION,'sources':['eis','commercial'],'topics':['кровля'],
        'legal_regimes':['44-ФЗ','commercial'],'commercial_sources':['B2B-Center'], **changes})


def eis(query='кровля', **changes):
    value={'ok':True,'status':'keyword_search_observed','query':query,
        'url':'https://zakupki.gov.ru/epz/order/extendedsearch/results.html?'+urlencode({
            'searchString':query,'deliveryPlaceGAR':REGION,'fz44':'on','af':'on'}),
        'notice_links_observed':1,
        'notice_links':['https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=123456789'],
        'search_execution_verified':True,'delivery_region_filter_verified':True,
        'active_only_filter_verified':True,'law':'44-ФЗ','delivery_region':REGION,'model_calls':0}
    value.update(changes)
    return json.dumps(value).encode()


def commercial(**changes):
    value={'ok':True,'sources':[{'provider':'B2B-Center','ok':True}],
           'confirmed':[],'review':[],'model_calls':0}
    value.update(changes)
    return json.dumps(value).encode()


class EISDecoderTests(unittest.TestCase):
    def test_truncated_registry_links_remain_partial(self):
        value=decode_eis_result(eis(notice_links_observed=12),0,query='кровля')
        self.assertEqual(value.status,'partial')
        self.assertEqual(value.code,'eis_listing_truncated')
    def test_verified_registry_discovery_is_not_a_card_with_invented_price_or_deadline(self):
        value=decode_eis_result(eis(),0,query='кровля')
        self.assertEqual(value.status,'completed')
        self.assertNotIn('price',value.report)
        self.assertNotIn('deadline',value.report)

    def test_empty_must_be_verified_and_distinct_from_unavailable(self):
        raw=eis(status='keyword_search_empty',notice_links=[],notice_links_observed=0)
        self.assertEqual(decode_eis_result(raw,0,query='кровля').status,'completed')
        raw=eis(status='keyword_search_empty',notice_links=[],notice_links_observed=0,active_only_filter_verified=False)
        self.assertEqual(decode_eis_result(raw,0,query='кровля').status,'failed')
        failure=decode_eis_result(b'{"ok":false,"status":"busy"}',1,query='кровля')
        self.assertEqual(failure.code,'cli_busy')

    def test_wrong_query_scope_or_exit_never_looks_successful(self):
        for raw,code,query in ((eis(),1,'кровля'),(eis(),0,'ремонт'),
                               (eis(delivery_region_filter_verified=False),0,'кровля'),
                               (eis(law='223-ФЗ'),0,'кровля')):
            with self.subTest(raw=raw):
                self.assertNotEqual(decode_eis_result(raw,code,query=query).status,'completed')

    def test_spoofed_links_and_unknown_counts_are_rejected(self):
        for changes in ({'notice_links':['https://zakupki.gov.ru.evil.example/common-info.html?regNumber=1']},
                        {'notice_links':['https://u:p@zakupki.gov.ru/common-info.html?regNumber=1']},
                        {'notice_links_observed':True},
                        {'notice_links':['https://zakupki.gov.ru/common-info.html?regNumber=1&regNumber=2']}):
            with self.subTest(changes=changes):
                self.assertEqual(decode_eis_result(eis(**changes),0,query='кровля').status,'failed')


class DiscoveryTests(unittest.TestCase):
    def test_output_limit_is_reported_distinctly_and_other_source_continues(self):
        result=discover(request(),SCOPE,invoke=Mock(side_effect=[OSError(errno.EFBIG,'PRIVATE'),(commercial(),0)]),verify_runtime=Mock())
        self.assertEqual(result['outputs'][0]['code'],'cli_output_limit')
        self.assertEqual(result['status'],'partial')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_missing_requested_commercial_provider_cannot_look_completed(self):
        result=discover(request(sources=['commercial'],commercial_sources=['B2B-Center','Росэлторг'],legal_regimes=['commercial']),
                        SCOPE,invoke=Mock(return_value=(commercial(),0)),verify_runtime=Mock())
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['outputs'][0]['sources_not_reported'],['Росэлторг'])

    def test_unexpected_provider_is_not_silently_treated_as_selected_provider(self):
        raw=commercial(sources=[{'provider':'B2B-Center-IMPOSTOR','ok':True}])
        result=discover(request(sources=['commercial'],legal_regimes=['commercial']),SCOPE,
                        invoke=Mock(return_value=(raw,0)),verify_runtime=Mock())
        self.assertEqual(result['status'],'partial')
        self.assertTrue(result['outputs'][0]['unexpected_source_labels'])
    def test_actual_profile_and_sequential_eis_call_are_passed_to_bound_invoker(self):
        calls=[]
        def invoke(call,timeout):
            calls.append(call)
            if call.source=='eis':
                self.assertEqual(timeout,100)
                return eis(query=call.query),0
            self.assertEqual(timeout,330)
            self.assertEqual(json.loads(call.stdin)['companyId'],37)
            return commercial(),0
        gate=Mock()
        result=discover(request(),SCOPE,invoke=invoke,verify_runtime=gate)
        self.assertEqual([call.source for call in calls],['eis','commercial'])
        self.assertEqual(gate.call_count,2)
        self.assertEqual(result['status'],'completed')
        self.assertFalse(result['card_acceptance_complete'])
        self.assertFalse(result['telegram_delivery_verified'])

    def test_source_timeout_does_not_skip_other_source_or_expose_exception(self):
        invoker=Mock(side_effect=[subprocess.TimeoutExpired('PRIVATE',100), (commercial(),0)])
        result=discover(request(),SCOPE,invoke=invoker,verify_runtime=Mock())
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['outputs'][0]['code'],'cli_timeout')
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(invoker.call_count,2)

    def test_commercial_nonzero_partial_is_retained_after_eis_failure(self):
        partial=commercial(ok=False,review=[{'id':'synthetic-1'}])
        result=discover(request(),SCOPE,invoke=Mock(side_effect=[(b'{"ok":false,"status":"busy"}',1),(partial,1)]),verify_runtime=Mock())
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['outputs'][1]['report']['review'][0]['id'],'synthetic-1')

    def test_unsupported_eis_regime_is_reported_without_search(self):
        invoker=Mock();gate=Mock()
        result=discover(request(sources=['eis'],commercial_sources=[],legal_regimes=['223-ФЗ']),SCOPE,invoke=invoker,verify_runtime=gate)
        invoker.assert_not_called();gate.assert_not_called()
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['unsupported_regimes'],[{'source':'eis','regime':'223-ФЗ'}])

    def test_changed_release_stops_before_next_source(self):
        gate=Mock(side_effect=[None,RuntimeMismatch('reviewed_runtime_required')])
        invoker=Mock(side_effect=lambda call,timeout:(eis(query=call.query),0))
        with self.assertRaises(RuntimeMismatch):
            discover(request(),SCOPE,invoke=invoker,verify_runtime=gate)
        self.assertEqual(invoker.call_count,1)

    def test_gate_checks_all_three_modules_and_wrapper_and_rejects_any_mismatch(self):
        expected=[{'sha256':value[0]} for value in REVIEWED_RUNTIME.values()]
        with patch('jev_agent.tender_finder.discovery.runtime_source',side_effect=[*expected,{'sha256':WRAPPER_SHA256,'code':'SyntaxError'}]) as reader:
            verify_installed_runtime()
            self.assertEqual(reader.call_count,4)
        for evidence in ({'sha256':'0'*64},{'code':'UNTRUSTED_SOURCE_PERMISSIONS'},{'exists':False}):
            with self.subTest(evidence=evidence),patch('jev_agent.tender_finder.discovery.runtime_source',return_value=evidence),self.assertRaises(RuntimeMismatch):
                verify_installed_runtime()


if __name__=='__main__':unittest.main()
