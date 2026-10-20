import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.jev_telegram import digest, write_private
from scripts.jev_telegram_history import save_batch, read_cursors


class HistoryTest(unittest.TestCase):
    def batch(self, text='Нужен маляр, 50 м², цена 1000 ₽', channel='testa', number=1):
        return digest([{'text': text, 'source': channel, 'id': number,
                        'date': '2026-10-20T12:00:00+03:00',
                        'url': 'https://t.me/{}/{}'.format(channel, number)}])

    def test_reposts_across_runs_preserve_links_without_new_order(self):
        with tempfile.TemporaryDirectory() as folder:
            first = save_batch(folder, self.batch(), {'a': 1})
            self.assertEqual(first['new_orders'], 1)
            second = save_batch(folder, self.batch(channel='testb'), {'a': 1, 'b': 1})
            report = json.loads(Path(second['json']).read_text())
            self.assertEqual(second['new_orders'], 0)
            self.assertEqual(second['orders'], 1)
            self.assertEqual(len(report['orders'][0]['originals']), 2)
            self.assertFalse(report['orders'][0]['is_new'])
            self.assertEqual(read_cursors(folder), {'a': 1, 'b': 1})
            self.assertTrue(Path(first['report']).exists())

    def test_real_export_cli_remembers_previous_run(self):
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / 'input.json'
            export.write_text(json.dumps({'messages': [{'id': 1, 'type': 'message',
                'date': '2026-10-20T10:00:00', 'text': 'Нужен маляр, квартира 60 м²'}]}))
            command = [sys.executable, str(Path(__file__).with_name('jev_telegram.py')),
                       '--export', str(export), '--source', 'testa', '--output', str(Path(folder) / 'state')]
            first = json.loads(subprocess.check_output(command, text=True))
            second = json.loads(subprocess.check_output(command, text=True))
            self.assertEqual(first['new_orders'], 1)
            self.assertEqual(second['new_orders'], 0)
            self.assertEqual(second['orders'], 1)
            self.assertIn('Уже встречалось', Path(second['report']).read_text())

    def test_replay_and_changed_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            save_batch(folder, self.batch(), {})
            replay = save_batch(folder, self.batch(), {})
            report = json.loads(Path(replay['json']).read_text())
            self.assertEqual(len(report['orders'][0]['originals']), 1)
            changed = save_batch(folder, self.batch(text='Нужен маляр, 50 м², цена 2000 ₽', number=2), {})
            self.assertEqual(changed['orders'], 2)
            self.assertEqual(changed['new_orders'], 1)

    def test_report_failure_rolls_back_history_and_cursor(self):
        with tempfile.TemporaryDirectory() as folder:
            save_batch(folder, self.batch(), {'a': 1})
            before = set(Path(folder).glob('digest-*'))
            def fail_html(path, text):
                if path.suffix == '.html': raise OSError('disk full')
                write_private(path, text)
            with patch('scripts.jev_telegram_history.write_private', side_effect=fail_html):
                with self.assertRaises(OSError):
                    save_batch(folder, self.batch(channel='testb'), {'a': 2})
            self.assertEqual(read_cursors(folder), {'a': 1})
            self.assertEqual(set(Path(folder).glob('digest-*')), before)
            retry = save_batch(folder, self.batch(channel='testb'), {'a': 2})
            report = json.loads(Path(retry['json']).read_text())
            self.assertEqual(len(report['orders'][0]['originals']), 2)

    def test_retention_and_private_state_isolation(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            save_batch(a, self.batch(), {}, now=now)
            empty = save_batch(b, digest([]), {}, now=now)
            self.assertEqual(empty['orders'], 0)
            self.assertEqual((Path(a) / 'history.sqlite3').stat().st_mode & 0o777, 0o600)
            expired = save_batch(a, digest([]), {}, now=now + timedelta(days=31))
            self.assertEqual(expired['orders'], 0)

    def test_legacy_checkpoint_and_capacity_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cursor.json'
            path.write_text('{"a": 7}')
            path.chmod(0o600)
            self.assertEqual(read_cursors(folder), {'a': 7})
            with patch('scripts.jev_telegram_history.MAX_CARDS', 0):
                with self.assertRaises(ValueError): save_batch(folder, self.batch(), {'a': 8})
            self.assertEqual(read_cursors(folder), {'a': 7})

    def test_successful_first_save_preserves_legacy_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cursor.json'
            path.write_text('{"a": 7}')
            path.chmod(0o600)
            save_batch(folder, self.batch(), {})
            self.assertEqual(read_cursors(folder), {'a': 7})

    def test_normalization_contacts_and_stale_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            save_batch(folder, self.batch(text='Нужен маляр, звонить 111'), {'a': 3})
            duplicate = save_batch(folder, self.batch(text='НУЖЕН   маляр, звонить 111', number=2), {'a': 3})
            self.assertEqual(duplicate['new_orders'], 0)
            changed = save_batch(folder, self.batch(text='Нужен маляр, звонить 222', number=3), {'a': 4})
            self.assertEqual(changed['orders'], 2)
            with self.assertRaises(ValueError): save_batch(folder, self.batch(), {'a': 2})
            self.assertEqual(read_cursors(folder), {'a': 4})


if __name__ == '__main__': unittest.main()
