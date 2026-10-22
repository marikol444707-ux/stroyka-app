import ast
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest

from scripts import invoice_provider_status_patch as operator
from scripts.test_invoice_provider_status_patch import DiagnosticFilesystemTest, SOURCE


class InvoiceResponseDiagnosticTest(unittest.TestCase):
    def generate(self, response, capability='invoice_scan', broken_logging=False):
        namespace = {'__name__':'response_diagnostic_test'}
        exec(operator.instrument_responses(operator.instrument(SOURCE)), namespace)
        calls = []
        def create(**values):
            calls.append(values)
            return response
        adapter = namespace['build_yandex_model_adapter'](api_key='PRIVATE-KEY',folder_id='PRIVATE-FOLDER',
            client_factory=lambda **_:SimpleNamespace(responses=SimpleNamespace(create=create)),
            telemetry_sink=lambda **_:None)
        request = namespace['build_model_request'](capability=capability,instructions='PRIVATE-INVOICE-INSTRUCTIONS',
            **({'input_parts':(namespace['ModelInputPart']('image_data_url','data:image/png;base64,YWJj'),)}
               if capability=='invoice_scan' else {'input_text':'PRIVATE-INPUT'}),
            temperature=.1,max_output_tokens=12000 if capability=='invoice_scan' else 1000,deadline_seconds=20)
        if broken_logging:
            def bad_print(*args,**kwargs):
                raise OSError('PRIVATE-OUTPUT-ERROR')
            namespace['print'] = bad_print
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            try:
                result = adapter.generate(request)
                outcome = result.output_text
            except namespace['ModelGatewayError'] as error:
                outcome = error.code
        events = [ast.literal_eval(line.split(operator.RESPONSE_MARKER+' ',1)[1])
                  for line in output.getvalue().splitlines() if operator.RESPONSE_MARKER+' ' in line]
        self.assertNotIn('PRIVATE',output.getvalue())
        self.assertEqual(len(calls),1)
        return outcome, events, calls

    def test_reasoning_budget_exhaustion_is_visible_without_reasoning_contents(self):
        response = SimpleNamespace(output_text='',status='incomplete',
            incomplete_details={'reason':'max_output_tokens'},
            output=[{'type':'reasoning','summary':[{'text':'PRIVATE-REASONING'}]}],
            usage={'input_tokens':500,'output_tokens':12000,'output_tokens_details':{'reasoning_tokens':12000}})
        outcome,events,calls = self.generate(response)
        self.assertEqual(outcome,'model_gateway_empty_output')
        self.assertEqual(events[0]['status'],'incomplete')
        self.assertEqual(events[0]['incompleteReason'],'max_output_tokens')
        self.assertEqual(events[0]['outputTypes'],{'reasoning':1})
        self.assertEqual(events[0]['reasoningTokens'],12000)
        self.assertEqual(events[0]['outputTextChars'],0)
        self.assertEqual(calls[0]['max_output_tokens'],12000)
        self.assertEqual(events[0]['files'],0)

    def test_structured_text_is_counted_but_never_copied_or_promoted_to_result(self):
        response = SimpleNamespace(output_text='',status='completed',
            output=[SimpleNamespace(type='message',content=[
                SimpleNamespace(type='output_text',text='PRIVATE-TEXT'),
                {'type':'refusal','refusal':'PRIVATE-REFUSAL'},
                {'type':'PRIVATE-TYPE','text':'PRIVATE-OTHER'}])])
        outcome,events,_ = self.generate(response)
        self.assertEqual(outcome,'model_gateway_empty_output')
        self.assertEqual(events[0]['contentTypes'],{'output_text':1,'refusal':1,'other':1})
        self.assertEqual(events[0]['messageTextChars'],len('PRIVATE-TEXT'))

    def test_successful_result_and_request_are_unchanged(self):
        outcome,events,calls = self.generate(SimpleNamespace(output_text='PRIVATE-SUCCESS',status='completed',output=[]))
        self.assertEqual(outcome,'PRIVATE-SUCCESS')
        self.assertEqual(events[0]['outputTextChars'],len(outcome))
        self.assertEqual(calls[0]['temperature'],.1)
        self.assertEqual(calls[0]['input'][0]['content'][0]['image_url'],'data:image/png;base64,YWJj')

    def test_unknown_metadata_and_unbounded_tokens_do_not_escape(self):
        _,events,_ = self.generate(SimpleNamespace(output_text='',status='PRIVATE-STATUS',
            incomplete_details={'reason':'PRIVATE-REASON'},output=[{'type':['PRIVATE-TYPE']}],
            usage={'input_tokens':True,'output_tokens':10000001,'output_tokens_details':{'reasoning_tokens':'PRIVATE'}}))
        self.assertEqual(events[0]['status'],'other')
        self.assertIsNone(events[0]['incompleteReason'])
        self.assertIsNone(events[0]['inputTokens'])
        self.assertIsNone(events[0]['outputTokens'])
        self.assertEqual(events[0]['outputTypes'],{'other':1})

    def test_logging_failure_does_not_change_empty_output(self):
        outcome,events,_ = self.generate(SimpleNamespace(output_text=''),broken_logging=True)
        self.assertEqual(outcome,'model_gateway_empty_output')
        self.assertEqual(events,[])

    def test_other_capabilities_do_not_emit_response_diagnostics(self):
        _,events,_ = self.generate(SimpleNamespace(output_text='PRIVATE-ANSWER'),'estimate_chat')
        self.assertEqual(events,[])

    def test_unknown_or_duplicate_response_reader_is_refused(self):
        with self.assertRaises(operator.Stop):
            operator.instrument_responses('class Other: pass\n')
        once = operator.instrument_responses(SOURCE)
        with self.assertRaises(operator.Stop):
            operator.instrument_responses(once)


class ResponseDiagnosticFilesystemTest(DiagnosticFilesystemTest):
    def prepare(self):
        self.known = Path(self.install()['backup'])
        self.before = self.target.read_bytes()
        self.operations.clear()

    def test_install_and_restore_exact_bytes_without_changing_head(self):
        self.prepare()
        result = operator.observe_responses(self.root,self.head,self.known,self.backups,operate=self.operate)
        self.assertEqual(result['state'],'response_diagnostic_installed_awaiting_scan')
        self.assertIn(operator.RESPONSE_MARKER,self.target.read_text())
        self.assertEqual(self.git('rev-parse','HEAD'),self.head)
        operator.restore(self.root,Path(result['backup']),operate=self.operate)
        self.assertEqual(self.target.read_bytes(),self.before)

    def test_unknown_release_and_later_changes_are_refused(self):
        self.prepare()
        with self.assertRaisesRegex(operator.Stop,'installed_head_mismatch'):
            operator.observe_responses(self.root,'00000000',self.known,self.backups,operate=self.operate)
        self.target.write_bytes(self.before+b'\n# another operator change\n')
        with self.assertRaisesRegex(operator.Stop,'adapter_changed_response_diagnostic_refused'):
            operator.observe_responses(self.root,self.head,self.known,self.backups,operate=self.operate)
        self.assertEqual(self.operations,[])

    def test_failed_restart_restores_previous_diagnostic(self):
        self.prepare()
        attempts=[]
        def operate(service,action):
            if action=='restart':
                attempts.append(action)
                if len(attempts)==1:
                    raise RuntimeError('fake failure')
        with self.assertRaisesRegex(operator.Stop,'original_restored'):
            operator.observe_responses(self.root,self.head,self.known,self.backups,operate=operate)
        self.assertEqual(self.target.read_bytes(),self.before)
        self.assertEqual(len(attempts),2)


if __name__=='__main__':
    unittest.main()
