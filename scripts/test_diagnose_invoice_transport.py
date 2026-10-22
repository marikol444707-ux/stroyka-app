import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import diagnose_invoice_transport as diagnostic


class SyntheticInvoiceTransportTest(unittest.TestCase):
    def test_matrix_distinguishes_pdf_rejection_and_never_prints_model_output(self):
        calls = []
        class BadRequestError(RuntimeError):
            status_code = 400
            body = {'detail': 'Unsupported InputFile for folder secret-folder, key private-key'}
        def create(**values):
            calls.append(values)
            if any(part['type'] == 'input_file' for part in values['input'][0]['content']):
                raise BadRequestError('private SDK exception and request headers')
            return SimpleNamespace(output_text='DO NOT PRINT MODEL OUTPUT')
        result = diagnostic.probe('private-key', 'secret-folder',
            client=SimpleNamespace(responses=SimpleNamespace(create=create)),
            parts_factory=lambda: ('data:image/png;base64,YWJj', 'data:application/pdf;base64,YWJj'))
        self.assertEqual([item['result'] for item in result['cases']], ['accepted', 'accepted', 'rejected'])
        self.assertEqual(result['cases'][-1]['httpStatus'], 400)
        self.assertIn('Unsupported InputFile', result['cases'][-1]['syntheticErrorDetail'])
        self.assertNotIn('private-key', json.dumps(result))
        self.assertNotIn('secret-folder', json.dumps(result))
        self.assertNotIn('DO NOT PRINT MODEL OUTPUT', json.dumps(result))
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call['max_output_tokens'] == 12000 and call['timeout'] == 20.0 for call in calls))
        self.assertTrue(all(call['model'] == calls[0]['model'] for call in calls))
        self.assertFalse(result['databaseAccess'])
        self.assertFalse(result['warehouseWrites'])

    def test_error_redaction_covers_credentials_and_synthetic_data(self):
        error = SimpleNamespace(status_code=400, body={'detail': 'private-key weird"folder',
            'input': 'data:image/png;base64,' + 'A' * 2000, 'auth': 'Bearer additional-secret'})
        result = diagnostic.safe_synthetic_error(error, ('private-key', 'weird"folder'))
        rendered = json.dumps(result)
        for value in ('private-key', 'weird', 'additional-secret', 'AAAA', 'data:image'):
            self.assertNotIn(value, rendered)
        self.assertLessEqual(len(result['syntheticErrorDetail']), 1200)

    def test_default_mode_never_reads_runtime_or_calls_the_model(self):
        output = io.StringIO()
        with patch('sys.argv', ['diagnostic']), patch.object(diagnostic, 'probe') as probe, contextlib.redirect_stdout(output):
            self.assertEqual(diagnostic.main(), 0)
        probe.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['state'], 'not_run')

    def test_missing_credentials_make_no_client_call(self):
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: self.fail('model called')))
        self.assertEqual(diagnostic.probe('', '', client=client)['error'], 'model_credentials_missing')

    def test_inputs_are_actual_synthetic_png_and_pdf(self):
        import base64
        png, pdf = diagnostic.synthetic_parts()
        self.assertTrue(base64.b64decode(png.split(',', 1)[1]).startswith(b'\x89PNG'))
        self.assertTrue(base64.b64decode(pdf.split(',', 1)[1]).startswith(b'%PDF'))

    def test_schema_does_not_accept_arbitrary_exception_string(self):
        error = ValueError('SECRET RAW SDK ERROR')
        result = diagnostic.safe_synthetic_error(error, ())
        self.assertEqual(result['syntheticErrorDetail'], 'no_structured_error_body')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_parent_uses_exact_runtime_environment_and_uvicorn_interpreter(self):
        output = io.StringIO()
        env = {'YANDEX_API_KEY': 'private-key', 'YANDEX_FOLDER_ID': 'secret-folder'}
        child = SimpleNamespace(stdout=json.dumps({'syntheticOnly': True, 'cases': []}), returncode=0)
        root = Path('/workspace/stroyka-app')
        with patch('sys.argv', ['probe', '--probe', '--app-root', str(root)]), \
             patch.object(diagnostic.os, 'chdir'), \
             patch('scripts.unified_release.runtime_environment', return_value=env) as runtime, \
             patch.object(Path, 'read_text', return_value='#!/usr/local/bin/python3\n'), \
             patch.object(diagnostic.subprocess, 'run', return_value=child) as run, \
             contextlib.redirect_stdout(output):
            self.assertEqual(diagnostic.main(), 0)
        runtime.assert_called_once_with(root, 'stroyka')
        self.assertEqual(run.call_args.args[0][0], '/usr/local/bin/python3')
        self.assertIn('--runtime-env', run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs['env'], env)
        self.assertEqual(run.call_args.kwargs['cwd'], root)
        self.assertNotIn('private-key', output.getvalue())

    def test_parent_does_not_forward_failed_child_stderr_or_unstructured_output(self):
        child = SimpleNamespace(stdout='private child output', stderr='private SDK headers', returncode=1)
        output = io.StringIO()
        with patch('sys.argv', ['probe', '--probe', '--app-root', '/workspace/stroyka-app']), \
             patch.object(diagnostic.os, 'chdir'), \
             patch('scripts.unified_release.runtime_environment', return_value={}), \
             patch.object(Path, 'read_text', return_value='#!/usr/local/bin/python3\n'), \
             patch.object(diagnostic.subprocess, 'run', return_value=child), \
             contextlib.redirect_stdout(output):
            self.assertEqual(diagnostic.main(), 2)
        self.assertNotIn('private', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error'], 'synthetic_probe_unavailable')


if __name__ == '__main__':
    unittest.main()
