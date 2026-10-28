import json
import unittest

from .cli_result import MAX_RESULT_BYTES, decode_commercial_result


def report(**changes):
    value={'ok':True,'sources':[{'name':'B2B-Center','ok':True}],
           'confirmed':[{'source':'B2B-Center','id':'synthetic-1','title':'Synthetic roof work'}],
           'review':[], 'model_calls':0}
    value.update(changes)
    return json.dumps(value).encode()


class CLIResultTests(unittest.TestCase):
    def test_nonzero_partial_json_keeps_actual_candidate_evidence(self):
        result=decode_commercial_result(report(ok=False,sources=[{'name':'B2B-Center','ok':True},
                                                               {'name':'Росэлторг','ok':False}]),1)
        self.assertEqual(result.status,'partial')
        self.assertEqual(result.report['confirmed'][0]['id'],'synthetic-1')
        self.assertEqual(result.code,'cli_nonzero_exit')

    def test_completed_requires_zero_exit_and_all_sources_successful(self):
        self.assertEqual(decode_commercial_result(report(),0).status,'completed')
        self.assertEqual(decode_commercial_result(report(),1).status,'partial')
        self.assertEqual(decode_commercial_result(report(ok=False),0).status,'partial')

    def test_verified_empty_is_distinct_from_a_failed_source(self):
        self.assertEqual(decode_commercial_result(report(confirmed=[]),0).status,'completed')
        result=decode_commercial_result(report(ok=False,sources=[{'name':'B2B-Center','ok':False}],confirmed=[]),1)
        self.assertEqual(result.status,'failed')
        self.assertEqual(result.code,'cli_failed_without_verified_coverage')

    def test_parse_failure_and_oversized_output_do_not_leak_raw_error_contents(self):
        for raw,code in [(b'PRIVATE_ERROR_WITH_TOKEN','invalid_cli_json'),
                         (b'\xff','invalid_cli_json'),(b'x'*(MAX_RESULT_BYTES+1),'cli_result_too_large'),
                         (b'{"ok":true,"ok":false}','invalid_cli_json')]:
            result=decode_commercial_result(raw,1)
            self.assertEqual(result.status,'failed')
            self.assertEqual(result.code,code)
            self.assertIsNone(result.report)

    def test_arbitrary_json_and_empty_source_list_are_not_success(self):
        self.assertEqual(decode_commercial_result(b'{"ok":true}',0).status,'failed')
        self.assertEqual(decode_commercial_result(report(sources=[],confirmed=[]),0).status,'failed')

    def test_eis_format_is_not_mistaken_for_commercial_report(self):
        self.assertEqual(decode_commercial_result(b'{"ok":true,"rows":[]}',0).status,'failed')


if __name__=='__main__':
    unittest.main()
