import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.jev_telegram import classify, digest, export_messages, render_html, load_json, write_private
from scripts.jev_telegram_collect import collect


class TelegramTest(unittest.TestCase):
    def test_customer_request_and_advert(self):
        self.assertEqual(classify('Нужна бригада на отделку квартиры'), 'order')
        self.assertEqual(classify('Ищу мастера: ремонт ванной'), 'order')
        self.assertEqual(classify('Выполняем ремонт квартир. Ищем заказы'), 'services')
        self.assertEqual(classify('Требуется работа, отделочник со стажем'), 'services')
        self.assertEqual(classify('Продам штукатурку после ремонта'), 'materials')
        self.assertEqual(classify('Ремонт квартиры 60 м2'), 'review')
        self.assertEqual(classify('Продам телефон'), 'irrelevant')

    def test_export_entities_and_no_unsafe_links(self):
        rows = export_messages({'name': 'Тест', 'messages': [
            {'id': 4, 'type': 'message', 'date': '2026-10-19T10:00:00',
             'text': ['Нужен ', {'type': 'bold', 'text': 'маляр'}]},
            {'id': 5, 'type': 'service', 'text': 'ремонт'}]}, 'example_channel')
        self.assertEqual(rows[0]['text'], 'Нужен маляр')
        self.assertEqual(rows[0]['url'], 'https://t.me/example_channel/4')
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            export_messages({'messages': []}, 'javascript:alert(1)')

    def test_duplicates_preserve_originals_and_html_is_escaped(self):
        rows = [{'id': 1, 'source': 'a', 'date': '2026-10-19',
                 'text': 'Нужен маляр <script>alert(1)</script>', 'url': 'https://t.me/testa/1'},
                {'id': 2, 'source': 'b', 'date': '2026-10-19',
                 'text': 'НУЖЕН  МАЛЯР <script>alert(1)</script>', 'url': 'javascript:alert(1)'}]
        result = digest(rows)
        self.assertEqual(len(result['orders']), 1)
        self.assertEqual(len(result['orders'][0]['originals']), 2)
        html = render_html(result)
        self.assertNotIn('<script>', html)
        self.assertNotIn('href="javascript:', html)

    def test_input_limits(self):
        with self.assertRaises(ValueError):
            export_messages({'messages': 'not a list'}, 'example_channel')

    def test_private_files_limits_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            write_private(path, '{"ok":true}')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_json(path, private=True), {'ok': True})
            with self.assertRaises(ValueError): load_json(path, limit=2)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(OSError): load_json(link)
            os.chmod(path, 0o644)
            with self.assertRaises(ValueError): load_json(path, private=True)

    def test_floodwait_discards_incomplete_source_batch(self):
        class Wait(Exception): seconds = 120
        class Client:
            async def is_user_authorized(self): return True
            def iter_messages(self, source, **kwargs):
                async def messages():
                    yield SimpleNamespace(id=11, message='Нужен маляр', date=None)
                    raise Wait('do not expose server response')
                return messages()
        result, cursors = asyncio.run(collect(Client(), [{'id': -100111}], {'-100111': 10}))
        self.assertEqual(cursors, {'-100111': 10})
        self.assertEqual(result['orders'], [])
        self.assertEqual(result['sources'][0]['retry_after'], 120)
        self.assertNotIn('do not expose', json.dumps(result))

    def test_initial_fetch_is_bounded_and_private_dialog_rejected(self):
        class Client:
            async def is_user_authorized(self): return True
            def iter_messages(self, source, **kwargs):
                self.kwargs = kwargs
                async def messages():
                    if False: yield None
                return messages()
        client = Client()
        asyncio.run(collect(client, [{'id': -100111}], {}, 100))
        self.assertIn('offset_date', client.kwargs)
        self.assertEqual(client.kwargs['limit'], 100)
        with self.assertRaises(ValueError):
            asyncio.run(collect(client, [{'id': 12345}], {}, 100))

    def test_collection_partial_failure_and_oldest_first(self):
        class Client:
            async def is_user_authorized(self): return True
            def iter_messages(self, source, **kwargs):
                async def messages():
                    if source == -100222:
                        raise RuntimeError('sensitive server error')
                    self.kwargs = kwargs
                    for n in (11, 12):
                        yield SimpleNamespace(id=n, message='Нужен маляр', date=None)
                return messages()
        client = Client()
        result, cursors = asyncio.run(collect(client, [
            {'id': -100111, 'label': 'A'}, {'id': -100222, 'label': 'B'}], {'-100111': 10}, 2))
        self.assertEqual(cursors, {'-100111': 12})
        self.assertEqual(result['sources'][1]['status'], 'source_failed')
        self.assertEqual(client.kwargs, {'min_id': 10, 'reverse': True, 'limit': 2})
        self.assertEqual(len(result['orders']), 1)

    def test_no_sources_or_login_does_not_collect(self):
        class Client:
            async def is_user_authorized(self): return False
        with self.assertRaises(ValueError):
            asyncio.run(collect(Client(), [], {}, 10))
        result, cursors = asyncio.run(collect(Client(), [{'id': -100111, 'label': 'A'}], {}, 10))
        self.assertEqual(result['status'], 'not_authorized')
        self.assertEqual(cursors, {})


if __name__ == '__main__':
    unittest.main()
