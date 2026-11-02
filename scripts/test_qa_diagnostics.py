"""Local tempfiles and mocked subprocess only; no DB, network or app imports."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from scripts.qa_diagnostics import (Diagnostics, DiagnosticError, LoggedDriver,
    classify, child_entry, child_failure, MARKER)
from scripts.qa_install import LocalDriver, command, execute
from scripts.test_qa_install import manifest

SECRET = 'PASSWORD_DSN_PRIVATE_SENTINEL'


class DiagnosticsTests(unittest.TestCase):
    def test_all_child_failure_classes_redacted_and_not_retried(self):
        cases = [(subprocess.CalledProcessError(19, [SECRET], stderr=SECRET), 'child_failed'),
                 (subprocess.TimeoutExpired([SECRET], 9, stderr=SECRET), 'timeout'),
                 (FileNotFoundError(SECRET), 'executable_missing'),
                 (PermissionError(SECRET), 'permission_denied'),
                 (RuntimeError(SECRET), 'unexpected_error')]
        for error, category in cases:
            with self.subTest(category=category), patch('scripts.qa_install.subprocess.run', side_effect=error) as run:
                with self.assertRaises(DiagnosticError) as caught:
                    LocalDriver().run([SECRET], env={'password': SECRET})
                self.assertEqual(run.call_count, 1)
                self.assertEqual(caught.exception.details['category'], category)
                self.assertNotIn(SECRET, str(caught.exception))
                if category == 'timeout':
                    self.assertTrue(caught.exception.details['uncertain_outcome'])

    def test_database_envelope_whitelist_and_auth_no_retry(self):
        stderr = MARKER + json.dumps({'category': 'database_error', 'sqlstate': '28P01',
                                    'message': SECRET, 'uncertain_outcome': False})
        error = subprocess.CalledProcessError(1, [SECRET], stderr=stderr)
        with patch('scripts.qa_install.subprocess.run', side_effect=error) as run:
            with self.assertRaises(DiagnosticError) as caught:
                LocalDriver().database_preflight(manifest())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(caught.exception.details['sqlstate'], '28P01')
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertNotIn('sqlstate', child_failure(error, database=False))
        for raw in (SECRET, MARKER + '{bad', MARKER + json.dumps({'sqlstate': SECRET, 'category': SECRET}),
                    MARKER + '[]', MARKER + json.dumps({'category': []})):
            error.stderr = raw
            self.assertNotIn(SECRET, json.dumps(child_failure(error, database=True)))

    def test_child_never_emits_traceback_or_private_error(self):
        class DatabaseFailure(Exception):
            pgcode = '42501'
        for error in (DatabaseFailure(SECRET), ImportError(SECRET), RuntimeError(SECRET)):
            output = io.StringIO()
            run = MagicMock(side_effect=error)
            with contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
                child_entry(run, {}, {})
            self.assertNotIn(SECRET, output.getvalue())
            self.assertNotIn('Traceback', output.getvalue())
            parsed = json.loads(output.getvalue().removeprefix(MARKER))
            self.assertEqual(parsed['category'], classify(error)['category'])
            self.assertEqual(run.call_count, 1)

    def test_journal_precedes_subprocess_with_stage_and_child_number(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            d = Diagnostics(parent=folder)
            driver = LocalDriver()
            proxy = LoggedDriver(driver, d)
            def child(*args, **kwargs):
                events = [json.loads(x) for x in (d.directory/'events.jsonl').read_text().splitlines()]
                self.assertEqual(events[0]['status'], 'created')
                self.assertEqual(events[-1]['status'], 'child_start')
                self.assertEqual(events[-1]['stage'], 'deliver_target')
                raise subprocess.TimeoutExpired([SECRET], 9, stderr=SECRET)
            with patch.object(driver, 'deliver_target', side_effect=lambda m: driver.run(['git', SECRET])), patch('scripts.qa_install.subprocess.run', side_effect=child):
                with self.assertRaises(DiagnosticError):
                    proxy.deliver_target(manifest())
            self.assertTrue(d.uncertain)
            d.close()
            text = (d.directory/'events.jsonl').read_text()
            self.assertNotIn(SECRET, text)
            self.assertIn('"child_index": 1', text)
            self.assertIn(str(d.directory/'events.jsonl'), output.getvalue())

    def test_cleanup_failure_does_not_mask_original_and_both_recorded(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            d = Diagnostics(parent=folder)
            driver = MagicMock()
            driver.preflight.side_effect = ValueError(SECRET)
            driver.discard_preparation.side_effect = PermissionError(SECRET)
            with self.assertRaises(DiagnosticError) as caught:
                execute(manifest(), LoggedDriver(driver, d), MagicMock())
            self.assertEqual(caught.exception.stage, 'preflight')
            self.assertEqual(caught.exception.details['category'], 'validation_failed')
            driver.stop.assert_not_called()
            d.close()
            events = [json.loads(x) for x in (d.directory/'events.jsonl').read_text().splitlines()]
            failures = [x for x in events if x['status'] == 'failure']
            self.assertEqual([x['category'] for x in failures], ['validation_failed', 'permission_denied'])
            self.assertNotIn(SECRET, str(events))

    def test_dryrun_creates_no_diagnostics_or_driver(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'manifest.json'
            path.write_text(json.dumps(manifest()))
            with patch('scripts.qa_diagnostics.Diagnostics') as diag, patch('scripts.qa_install.LocalDriver') as driver, contextlib.redirect_stdout(io.StringIO()):
                command(SimpleNamespace(manifest=path, execute=False))
            diag.assert_not_called()
            driver.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_cli_preserves_safe_fields(self):
        from scripts.unified_release import main
        error = DiagnosticError('preflight', {'category':'database_error', 'sqlstate':'28P01', 'exit_code':1})
        with patch('sys.argv', ['release', 'qa-install', '--manifest', '/unused']), patch('scripts.qa_install.command', side_effect=error), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(), 1)
        self.assertIn('28P01', output.getvalue())
        self.assertIn('preflight', output.getvalue())

    def test_owned_paths_are_narrow_and_journal_failure_stops_before_child(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            d = Diagnostics(parent=folder)
            d.resource('host_staging', '/opt/stroyka-qa-prebuild-abc123')
            with self.assertRaises(ValueError):
                d.resource('host_staging', '/etc/' + SECRET)
            driver = LocalDriver()
            driver.diagnostics = d
            with patch.object(d.journal, 'record', side_effect=OSError(SECRET)), patch('scripts.qa_install.subprocess.run') as run:
                with self.assertRaises(OSError):
                    driver.run(['git'])
            run.assert_not_called()
            d.close()

    def test_timeout_retains_owned_staging_without_cleanup_subprocess(self):
        from scripts.qa_frontend_stage import FrontendStage
        driver = MagicMock()
        driver.diagnostics.uncertain = True
        stage = FrontendStage(driver)
        stage.host = Path('/opt/stroyka-qa-prebuild-synthetic')
        stage.container_path = '/tmp/stroyka-qa-prebuild.abcdefghij'
        stage.cleanup_safe = True
        with contextlib.redirect_stdout(io.StringIO()), patch('scripts.qa_frontend_stage.shutil.rmtree') as remove:
            stage.discard_unaccepted()
        driver.run.assert_not_called()
        remove.assert_not_called()
        self.assertIsNotNone(stage.host)

    def test_log_disk_failure_does_not_mask_primary(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            d = Diagnostics(parent=folder)
            driver = MagicMock()
            primary = DiagnosticError('preflight', {'category':'database_error', 'sqlstate':'28P01'})
            def fail(*args):
                d.journal.record = MagicMock(side_effect=OSError(SECRET))
                raise primary
            driver.preflight.side_effect = fail
            with self.assertRaises(DiagnosticError) as caught:
                execute(manifest(), LoggedDriver(driver, d), MagicMock())
            self.assertIs(caught.exception, primary)
            d.close()

    def test_created_event_precedes_first_preparation_failure(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            d = Diagnostics(parent=folder)
            driver = MagicMock()
            driver.deliver_target.side_effect = PermissionError(SECRET)
            with self.assertRaises(DiagnosticError):
                execute(manifest(), LoggedDriver(driver, d), MagicMock())
            driver.preflight.assert_not_called()
            d.close()
            events = [json.loads(x) for x in (d.directory/'events.jsonl').read_text().splitlines()]
            self.assertEqual([e['status'] for e in events], ['created', 'start', 'failure'])
