import ast
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from scripts import invoice_provider_status_patch as diagnostic

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / diagnostic.TARGET).read_text()


class DiagnosticInstrumentationTest(unittest.TestCase):
    def run_adapter(self, source, capability='invoice_scan', logging_failure=False):
        namespace = {'__name__': 'invoice_diagnostic_test_adapter'}
        exec(diagnostic.instrument(source), namespace)
        class BadRequestError(RuntimeError):
            status_code = 400
            body = {'message': 'Invalid image_url, private API key, private invoice'}
        calls = []
        def create(**values):
            calls.append(values)
            raise BadRequestError('private SDK error and headers')
        adapter = namespace['build_yandex_model_adapter'](
            api_key='private-key', folder_id='private-folder',
            client_factory=lambda **_: SimpleNamespace(responses=SimpleNamespace(create=create)),
            telemetry_sink=lambda **_: None)
        request = namespace['build_model_request'](
            capability=capability, instructions='private instructions',
            **({'input_parts': (namespace['ModelInputPart']('image_data_url', 'data:image/png;base64,YWJj'),)}
               if capability == 'invoice_scan' else {'input_text': 'private input'}),
            temperature=.1, max_output_tokens=12000 if capability == 'invoice_scan' else 1000, deadline_seconds=20)
        output = io.StringIO()
        if logging_failure:
            def bad_print(*args, **kwargs):
                raise OSError('private output error')
            namespace['print'] = bad_print
        with contextlib.redirect_stdout(output), self.assertRaises(namespace['ModelGatewayError']) as error:
            adapter.generate(request)
        self.assertEqual(error.exception.code, 'model_gateway_provider_failed')
        self.assertNotIn('private', output.getvalue())
        return output.getvalue(), calls

    def test_records_actual_http_status_without_document_or_exception_contents(self):
        output, calls = self.run_adapter(SOURCE)
        self.assertIn(diagnostic.MARKER, output)
        record = ast.literal_eval(output.split(diagnostic.MARKER + ' ', 1)[1])
        self.assertEqual(record, {'stage': 'provider', 'httpStatus': 400, 'exceptionType': 'BadRequestError',
                                 'mentions': ['image_url'], 'images': 1, 'files': 0})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['max_output_tokens'], 12000)

    def test_supports_the_old_unbound_exception_handler(self):
        tree = ast.parse(SOURCE)
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name == 'YandexModelAdapter':
                method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'generate')
                for node in ast.walk(method):
                    if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                        node.name = None
                        node.body = [ast.Continue()]
        output, _ = self.run_adapter(ast.unparse(ast.fix_missing_locations(tree)) + '\n')
        self.assertIn("'httpStatus': 400", output)

    def test_other_capabilities_do_not_emit_invoice_diagnostics(self):
        output, _ = self.run_adapter(SOURCE, 'estimate_chat')
        self.assertEqual(output, '')

    def test_diagnostic_output_failure_does_not_change_the_gateway_error(self):
        self.run_adapter(SOURCE, logging_failure=True)

    def test_local_adapter_exception_is_reported_and_rethrown_unchanged(self):
        namespace = {'__name__': 'invoice_diagnostic_test_adapter'}
        exec(diagnostic.instrument(SOURCE), namespace)
        class Response:
            @property
            def output_text(self):
                raise TypeError('private response failure')
        adapter = namespace['build_yandex_model_adapter'](
            api_key='private-key', folder_id='private-folder',
            client_factory=lambda **_: SimpleNamespace(responses=SimpleNamespace(create=lambda **_: Response())),
            telemetry_sink=lambda **_: None)
        request = namespace['build_model_request'](capability='invoice_scan', instructions='private input',
            input_parts=(namespace['ModelInputPart']('image_data_url','data:image/png;base64,YWJj'),),
            temperature=.1,max_output_tokens=12000,deadline_seconds=20)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(TypeError, 'private response failure'):
            adapter.generate(request)
        record = ast.literal_eval(output.getvalue().split(diagnostic.MARKER + ' ', 1)[1])
        self.assertEqual(record['stage'], 'adapter')
        self.assertEqual(record['exceptionType'], 'TypeError')
        self.assertIsNone(record['httpStatus'])
        self.assertNotIn('private', output.getvalue())

    def test_duplicate_or_unknown_instrumentation_is_refused(self):
        with self.assertRaises(diagnostic.Stop):
            diagnostic.instrument(diagnostic.instrument(SOURCE))
        with self.assertRaises(diagnostic.Stop):
            diagnostic.instrument('class Unrelated: pass\n')


class DiagnosticFilesystemTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root = base / 'app'
        self.backups = base / 'backups'
        self.backups.mkdir()
        self.target = self.root / diagnostic.TARGET
        self.target.parent.mkdir(parents=True)
        self.target.write_text(SOURCE)
        self.target.chmod(0o640)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Invoice diagnostic tests', '-c', 'user.email=tests@example.invalid',
                 'commit', '-qm', 'Original adapter fixture')
        self.head = self.git('rev-parse', 'HEAD')
        self.operations = []

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()

    def operate(self, service, action):
        self.operations.append((service, action))

    def install(self, **kwargs):
        return diagnostic.apply(self.root, self.head[:8], self.backups, operate=kwargs.get('operate', self.operate))

    def test_plan_is_read_only(self):
        meta, before, after = diagnostic.plan(self.root)
        self.assertEqual(meta['head'], self.head)
        self.assertEqual(before, SOURCE.encode())
        self.assertNotEqual(before, after)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertEqual(self.operations, [])

    def test_apply_and_restore_preserve_original_bytes_and_file_mode(self):
        result = self.install()
        self.assertIn(diagnostic.MARKER, self.target.read_text())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        backup = Path(result['backup'])
        self.assertEqual((backup / 'source.py').read_text(), SOURCE)
        self.assertEqual((backup / 'invoice_status_tool.py').read_text(), (ROOT / 'scripts/invoice_provider_status_patch.py').read_text())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        diagnostic.restore(self.root, backup, operate=self.operate)
        self.assertEqual(self.target.read_text(), SOURCE)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.operations, [('stroyka', 'check'), ('stroyka', 'restart'), ('stroyka', 'restart')])
        self.assertTrue(backup.exists())

    def test_wrong_release_or_local_changes_prevent_all_mutations(self):
        with self.assertRaises(diagnostic.Stop):
            diagnostic.apply(self.root, '00000000', self.backups, operate=self.operate)
        self.target.write_text(SOURCE + '\n# Unrelated user edit\n')
        with self.assertRaises(diagnostic.Stop):
            self.install()
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertEqual(self.operations, [])

    def test_restart_failure_restores_the_original(self):
        restarted = []
        def operate(service, action):
            if action == 'restart':
                restarted.append(True)
                if len(restarted) == 1:
                    raise RuntimeError('service failure')
        with self.assertRaisesRegex(diagnostic.Stop, 'original_restored'):
            self.install(operate=operate)
        self.assertEqual(self.target.read_text(), SOURCE)
        self.assertEqual(len(restarted), 2)

    def test_restore_does_not_overwrite_later_user_edits(self):
        result = self.install()
        edited = self.target.read_text() + '\n# Later user edit\n'
        self.target.write_text(edited)
        with self.assertRaisesRegex(diagnostic.Stop, 'adapter_changed_restore_refused'):
            diagnostic.restore(self.root, Path(result['backup']), operate=self.operate)
        self.assertEqual(self.target.read_text(), edited)

    def test_changed_head_prevents_restore(self):
        result = self.install()
        (self.root / 'note.txt').write_text('Other deployment')
        self.git('add', 'note.txt')
        self.git('-c', 'user.name=Tests', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'Other deployment')
        with self.assertRaisesRegex(diagnostic.Stop, 'head_changed_restore_refused'):
            diagnostic.restore(self.root, Path(result['backup']), operate=self.operate)

    def test_single_command_delivery_can_apply_and_restore_with_a_fake_service(self):
        binaries = Path(self.temporary.name) / 'bin'
        binaries.mkdir()
        fake = binaries / 'systemctl'
        fake.write_text('#!/bin/sh\nexit 0\n')
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
        command = shlex.split(diagnostic.delivery_command(self.head[:8]))
        command[0] = sys.executable
        command.extend(['--app-root', str(self.root), '--backup-root', str(self.backups)])
        result = subprocess.run(command, env=env, check=True, capture_output=True, text=True)
        installed = json.loads(result.stdout)
        self.assertEqual(installed['state'], 'diagnostic_installed_awaiting_scan')
        self.assertIn(diagnostic.MARKER, self.target.read_text())
        restore_command = shlex.split(installed['restoreCommand'])
        restore_command[0] = sys.executable
        restored = subprocess.run(restore_command, env=env, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(restored.stdout)['state'], 'source_restored')
        self.assertEqual(self.target.read_text(), SOURCE)


if __name__ == '__main__':
    unittest.main()
