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


class ImageDetailRepairTest(unittest.TestCase):
    def test_mixed_scan_reproduces_detail_rejection_then_preserves_files_and_succeeds(self):
        original = SOURCE.replace(', "detail": "auto"', '')
        instrumented = diagnostic.instrument(original)
        calls = []
        class BadRequestError(RuntimeError):
            status_code = 400
            body = {'message': 'detail is required'}
        def create(**values):
            calls.append(values)
            images = [part for part in values['input'][0]['content'] if part['type'] == 'input_image']
            if any(part.get('detail') != 'auto' for part in images):
                raise BadRequestError('private document must not appear')
            return SimpleNamespace(output_text='{"items":[{"name":"Synthetic cement","quantity":2}]}')
        def generate(source):
            namespace = {'__name__': 'invoice_repair_test'}
            exec(source, namespace)
            adapter = namespace['build_yandex_model_adapter'](
                api_key='test-key', folder_id='folder-1', telemetry_sink=lambda **_: None,
                client_factory=lambda **_: SimpleNamespace(responses=SimpleNamespace(create=create)))
            part = namespace['ModelInputPart']
            request = namespace['build_model_request'](
                capability='invoice_scan', instructions='Read synthetic invoice',
                input_parts=(part('text', 'Synthetic invoice'),
                             part('image_data_url', 'data:image/png;base64,YWJj'),
                             part('image_data_url', 'data:image/jpeg;base64,ZGVm'),
                             part('file_data_url', 'data:application/pdf;base64,YWJj', 'invoice.pdf')),
                temperature=.1, max_output_tokens=12000, deadline_seconds=120)
            return adapter.generate(request)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(Exception) as raised:
            generate(instrumented)
        self.assertEqual(raised.exception.code, 'model_gateway_provider_failed')
        event = ast.literal_eval(output.getvalue().split(diagnostic.MARKER + ' ', 1)[1])
        self.assertEqual((event['httpStatus'], event['mentions'], event['images'], event['files']),
                         (400, ['detail'], 2, 1))
        result = generate(diagnostic.add_image_detail(instrumented))
        self.assertEqual(json.loads(result.output_text)['items'][0]['quantity'], 2)
        before = calls[0]['input'][0]['content']
        after = calls[1]['input'][0]['content']
        self.assertEqual([part for part in before if part['type'] != 'input_image'],
                         [part for part in after if part['type'] != 'input_image'])
        for old, new in zip(before, after):
            self.assertEqual(new, dict(old, detail='auto') if old['type'] == 'input_image' else old)
        for key in ('model', 'temperature', 'instructions', 'max_output_tokens'):
            self.assertEqual(calls[0][key], calls[1][key])

    def test_unknown_or_already_repaired_builder_is_refused(self):
        with self.assertRaises(diagnostic.Stop):
            diagnostic.add_image_detail('def unrelated(): pass\n')
        once = diagnostic.add_image_detail(SOURCE.replace(', "detail": "auto"', ''))
        with self.assertRaises(diagnostic.Stop):
            diagnostic.add_image_detail(once)


class ImageDetailRepairFilesystemTest(DiagnosticFilesystemTest):
    def prepare_diagnostic(self):
        self.target.write_text(SOURCE.replace(', "detail": "auto"', ''))
        self.git('add', '.')
        self.git('-c', 'user.name=Tests', '-c', 'user.email=tests@example.invalid',
                 'commit', '--allow-empty', '-qm', 'Missing image detail fixture')
        self.head = self.git('rev-parse', 'HEAD')
        result = self.install()
        self.diagnostic_backup = Path(result['backup'])
        self.instrumented = self.target.read_bytes()
        self.operations.clear()

    def repair(self, operate=None):
        return diagnostic.repair_image_detail(self.root, self.head, self.diagnostic_backup,
                                              self.backups, operate=operate or self.operate)

    def test_repair_plan_changes_nothing(self):
        self.prepare_diagnostic()
        meta, before, after = diagnostic.repair_plan(self.root, self.head, self.diagnostic_backup)
        self.assertEqual(before, self.instrumented)
        self.assertEqual(after, diagnostic.add_image_detail(before.decode()).encode())
        self.assertEqual(meta['head'], self.head)
        self.assertEqual(self.target.read_bytes(), self.instrumented)
        self.assertEqual(len(list(self.backups.iterdir())), 1)
        self.assertEqual(self.operations, [])

    def test_repair_retains_diagnostics_and_can_restore_in_two_exact_steps(self):
        self.prepare_diagnostic()
        result = self.repair()
        self.assertEqual(result['state'], 'image_detail_repaired_awaiting_scan')
        self.assertIn(diagnostic.MARKER, self.target.read_text())
        self.assertIn('"detail": "auto"', self.target.read_text())
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.head)
        diagnostic.restore(self.root, Path(result['backup']), operate=self.operate)
        self.assertEqual(self.target.read_bytes(), self.instrumented)
        diagnostic.restore(self.root, self.diagnostic_backup, operate=self.operate)
        self.assertEqual(self.target.read_text(), SOURCE.replace(', "detail": "auto"', ''))
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_repair_rejects_wrong_head_or_later_edit_before_mutations(self):
        self.prepare_diagnostic()
        with self.assertRaisesRegex(diagnostic.Stop, 'installed_head_mismatch'):
            diagnostic.repair_image_detail(self.root, '00000000', self.diagnostic_backup,
                                           self.backups, operate=self.operate)
        edited = self.instrumented + b'\n# other operator edit\n'
        self.target.write_bytes(edited)
        with self.assertRaisesRegex(diagnostic.Stop, 'adapter_changed_repair_refused'):
            self.repair()
        self.assertEqual(self.target.read_bytes(), edited)
        self.assertEqual(len(list(self.backups.iterdir())), 1)
        self.assertEqual(self.operations, [])

    def test_failed_repair_restart_restores_the_exact_diagnostic_source(self):
        self.prepare_diagnostic()
        attempts = []
        def operate(service, action):
            if action == 'restart':
                attempts.append(action)
                if len(attempts) == 1:
                    raise RuntimeError('fake restart failure')
        with self.assertRaisesRegex(diagnostic.Stop, 'original_restored'):
            self.repair(operate)
        self.assertEqual(self.target.read_bytes(), self.instrumented)
        self.assertEqual(len(attempts), 2)

    def test_missing_or_corrupted_backup_is_refused(self):
        self.prepare_diagnostic()
        with self.assertRaisesRegex(diagnostic.Stop, 'diagnostic_backup_required'):
            diagnostic.repair_plan(self.root, self.head, None)
        (self.diagnostic_backup / 'source.py').write_text('corrupted')
        with self.assertRaisesRegex(diagnostic.Stop, 'backup_hash_mismatch'):
            self.repair()
        self.assertEqual(self.target.read_bytes(), self.instrumented)
        self.assertEqual(self.operations, [])


if __name__ == '__main__':
    unittest.main()
