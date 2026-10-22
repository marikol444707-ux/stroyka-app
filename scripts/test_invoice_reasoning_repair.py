import ast
import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import invoice_provider_status_patch as operator
from scripts.test_invoice_provider_status_patch import DiagnosticFilesystemTest, SOURCE


def before_reasoning(source):
    tree = ast.parse(source)
    removals = [item for node in ast.walk(tree) if isinstance(node,ast.Call)
                and ast.unparse(node.func)=='self._client.responses.create'
                for item in node.keywords if item.arg is None]
    lines = source.splitlines(keepends=True)
    for node in sorted(removals,key=lambda value:value.lineno,reverse=True):
        del lines[node.lineno-1:node.end_lineno]
    return ''.join(lines)

BEFORE = before_reasoning(SOURCE)


class InvoiceReasoningBehaviorTest(unittest.TestCase):
    def generate(self, source, capability='invoice_scan', alternate_model=False):
        namespace = {'__name__':'reasoning_repair_test'}
        exec(source,namespace)
        if alternate_model:
            routes = dict(namespace['YANDEX_CAPABILITY_MODELS'])
            routes['invoice_scan'] = ('yandexgpt-5.1/latest',)
            namespace['YANDEX_CAPABILITY_MODELS'] = routes
        calls=[]
        def create(**values):
            calls.append(values)
            if capability=='invoice_scan' and not alternate_model and values.get('reasoning')!={'effort':'none'}:
                return SimpleNamespace(output_text='',status='incomplete',
                    incomplete_details=SimpleNamespace(reason='max_output_tokens'),output=[{'type':'reasoning'}])
            return SimpleNamespace(output_text='{"items":[{"name":"Synthetic cement","quantity":2}]}',status='completed')
        adapter = namespace['build_yandex_model_adapter'](api_key='key',folder_id='folder-1',clock=lambda:1.,
            client_factory=lambda **_:SimpleNamespace(responses=SimpleNamespace(create=create)),telemetry_sink=lambda **_:None)
        request = namespace['build_model_request'](capability=capability,instructions='Synthetic invoice',
            **({'input_parts':(namespace['ModelInputPart']('image_data_url','data:image/png;base64,YWJj'),)}
               if capability=='invoice_scan' else {'input_text':'Synthetic text'}),
            temperature=.1,max_output_tokens=12000 if capability=='invoice_scan' else 1000,deadline_seconds=20)
        try:
            result = adapter.generate(request).output_text
        except namespace['ModelGatewayError'] as error:
            result = error.code
        return result,calls

    def test_budget_exhaustion_before_and_complete_invoice_after_scoped_reasoning_control(self):
        before,old_calls = self.generate(BEFORE)
        after,new_calls = self.generate(operator.disable_invoice_reasoning(BEFORE))
        self.assertEqual(before,'model_gateway_empty_output')
        self.assertEqual(json.loads(after)['items'][0]['quantity'],2)
        expected = dict(old_calls[0],reasoning={'effort':'none'})
        self.assertEqual(new_calls,[expected])
        self.assertEqual(new_calls[0]['max_output_tokens'],12000)

    def test_other_qwen_and_yandex_capabilities_keep_their_existing_arguments(self):
        for capability in ('ai_chat_json','estimate_chat'):
            _,calls = self.generate(operator.disable_invoice_reasoning(BEFORE),capability)
            self.assertNotIn('reasoning',calls[0])
        _,calls = self.generate(operator.disable_invoice_reasoning(BEFORE),alternate_model=True)
        self.assertNotIn('reasoning',calls[0])

    def test_hotfix_and_repository_adapter_are_identical_in_ast(self):
        self.assertEqual(ast.dump(ast.parse(operator.disable_invoice_reasoning(BEFORE)),include_attributes=False),
                         ast.dump(ast.parse(SOURCE),include_attributes=False))
        with self.assertRaises(operator.Stop):
            operator.disable_invoice_reasoning(operator.disable_invoice_reasoning(BEFORE))

    def run_probe(self,response=None,reject=False):
        calls=[]
        class BadRequestError(RuntimeError):
            status_code=400
        def create(**values):
            calls.append(values)
            if reject:
                raise BadRequestError('PRIVATE SDK BODY')
            return response
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        fake_sdk = SimpleNamespace(OpenAI=lambda **_:client)
        output = io.StringIO()
        with patch.dict('sys.modules',{'openai':fake_sdk}), \
             patch.dict(os.environ,{'YANDEX_API_KEY':'PRIVATE-KEY','YANDEX_FOLDER_ID':'PRIVATE-FOLDER'}), \
             contextlib.redirect_stdout(output):
            exec(operator.REASONING_PROBE,{'__name__':'synthetic_reasoning_probe_test'})
        self.assertNotIn('PRIVATE',output.getvalue())
        return json.loads(output.getvalue()),calls

    def test_synthetic_preflight_uses_documented_parameter_and_never_prints_output(self):
        result,calls = self.run_probe(SimpleNamespace(output_text='PRIVATE MODEL OUTPUT',status='completed'))
        self.assertTrue(result['ok'])
        self.assertEqual(calls[0]['reasoning'],{'effort':'none'})
        self.assertEqual(calls[0]['max_output_tokens'],12000)
        self.assertFalse(result['warehouseWrites'])

    def test_rejected_parameter_or_partial_output_does_not_pass_preflight(self):
        result,_ = self.run_probe(reject=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['providerHttpStatus'],400)
        result,_ = self.run_probe(SimpleNamespace(output_text='PRIVATE PARTIAL',status='incomplete'))
        self.assertFalse(result['ok'])


class ReasoningRepairFilesystemTest(DiagnosticFilesystemTest):
    def prepare(self):
        self.target.write_text(BEFORE)
        (self.root/'backend/main.py').write_text('pdf_fix_is_unchanged = True\n')
        self.git('add','.')
        self.git('-c','user.name=Tests','-c','user.email=tests@example.invalid',
                 'commit','--allow-empty','-qm','Invoice adapter before reasoning fix')
        self.head = self.git('rev-parse','HEAD')
        known = Path(self.install()['backup'])
        self.known = Path(operator.observe_responses(self.root,self.head,known,self.backups,
                                                    operate=self.operate)['backup'])
        self.before = self.target.read_bytes()
        self.operations.clear()

    def repair(self,prober=None,operate=None):
        return operator.repair_invoice_reasoning(self.root,self.head,self.known,self.backups,
            operate=operate or self.operate,prober=prober or (lambda *_:{'ok':True}))

    def test_install_keeps_diagnostics_main_head_and_independent_rollback(self):
        self.prepare()
        main = (self.root/'backend/main.py').read_bytes()
        def preflight(root,service):
            self.assertEqual(self.target.read_bytes(),self.before)
            self.assertEqual(self.operations,[])
            return {'ok':True}
        result = self.repair(prober=preflight)
        self.assertEqual(result['state'],'invoice_reasoning_repaired_awaiting_scan')
        self.assertEqual(result['syntheticProbe'],'passed')
        self.assertIn(operator.RESPONSE_MARKER,self.target.read_text())
        self.assertEqual(self.git('rev-parse','HEAD'),self.head)
        self.assertEqual((self.root/'backend/main.py').read_bytes(),main)
        operator.restore(self.root,Path(result['backup']),operate=self.operate)
        self.assertEqual(self.target.read_bytes(),self.before)

    def test_rejected_preflight_leaves_no_new_backup_or_service_operation(self):
        self.prepare()
        backups = list(self.backups.iterdir())
        with self.assertRaisesRegex(operator.Stop,'reasoning_probe_rejected_no_changes'):
            self.repair(prober=lambda *_:{'ok':False})
        self.assertEqual(self.operations,[])
        self.assertEqual(self.target.read_bytes(),self.before)
        self.assertEqual(list(self.backups.iterdir()),backups)

    def test_wrong_release_or_new_edit_prevents_preflight(self):
        self.prepare()
        probe = Mock(side_effect=AssertionError('probe must not run'))
        with self.assertRaisesRegex(operator.Stop,'installed_head_mismatch'):
            operator.repair_invoice_reasoning(self.root,'00000000',self.known,self.backups,
                operate=self.operate,prober=probe)
        self.target.write_bytes(self.before+b'\n# unrelated change\n')
        with self.assertRaisesRegex(operator.Stop,'adapter_changed_reasoning_repair_refused'):
            self.repair(prober=probe)
        probe.assert_not_called()

    def test_failed_restart_restores_preceding_adapter_exactly(self):
        self.prepare()
        attempts=[]
        def operate(service,action):
            if action=='restart':
                attempts.append(action)
                if len(attempts)==1:
                    raise RuntimeError('fake restart failure')
        with self.assertRaisesRegex(operator.Stop,'original_restored'):
            self.repair(operate=operate)
        self.assertEqual(self.target.read_bytes(),self.before)
        self.assertEqual(len(attempts),2)

    def test_cli_dispatches_explicit_repair_mode_with_expected_arguments(self):
        output=io.StringIO()
        with patch('sys.argv',['tool','--repair-invoice-reasoning','--app-root',str(self.root),
                    '--expect-head',self.head,'--diagnostic-backup',str(self.backups)]), \
             patch.object(operator,'repair_invoice_reasoning',return_value={'state':'test'}) as repair, \
             contextlib.redirect_stdout(output):
            self.assertEqual(operator.main(),0)
        self.assertEqual(repair.call_args.args[:3],(self.root,self.head,self.backups))


if __name__=='__main__':
    unittest.main()
