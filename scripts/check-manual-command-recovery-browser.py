#!/usr/bin/env python3
"""Opt-in Chromium check: real forms/storage, simulated lost API response.

Requires installed node_modules, Python Playwright and Chromium. Does not start
the app backend, access a database, accept a remote URL or validate deployment.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def check(server, artifacts, chromium):
    from playwright.sync_api import sync_playwright, expect

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium, headless=True, args=['--no-sandbox'])
        try:
            for width, height in ((390, 844), (1280, 900)):
                for kind in ('contract', 'assignment'):
                    context = browser.new_context(viewport={'width': width, 'height': height})
                    try:
                        context.route('**/*', lambda route: route.continue_()
                                      if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
                        page = context.new_page()
                        page.set_default_timeout(10000)
                        page.on('dialog', lambda dialog: dialog.accept())
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(f'http://127.0.0.1:{server.server_port}/index.html?{kind}')
                        if kind == 'contract':
                            page.get_by_placeholder('Название / ФИО *').fill('Исходная бригада')
                            page.get_by_role('button', name='Создать договор', exact=True).click()
                        else:
                            page.get_by_role('combobox', name='Исполнитель', exact=True).select_option('__manual__')
                            page.get_by_placeholder('Название бригады', exact=True).fill('Исходная бригада')
                            if width < 600:
                                for _step in range(2):
                                    page.get_by_role('button', name='Далее', exact=True).click()
                            page.get_by_role('button', name='Выдать в работу', exact=True).click()
                        expect(page.get_by_role('alert')).to_contain_text('Проверьте соединение')
                        original = page.evaluate("JSON.parse(localStorage.getItem('qa-server')).bodies[0]")
                        page.reload()
                        panel = page.get_by_role('region', name='Сохранённая отправка бригады')
                        expect(panel).to_contain_text('Исходная бригада')
                        page.screenshot(path=str(artifacts / f'{width}-{kind}-restored.png'))
                        panel.get_by_role('button', name='Повторить сохранённую отправку').click()
                        expect(page.get_by_role('status')).to_have_text('Восстановление завершено')
                        state = page.evaluate("JSON.parse(localStorage.getItem('qa-server'))")
                        assert state['bodies'] == [original, original], 'The retry changed the original body'
                        assert page.evaluate("Object.keys(sessionStorage).filter(k=>k.startsWith('stroyka:manual-brigade-command:')).length") == 0
                        assert not errors, errors
                        print(f'PASS {width} {kind}: reload, exact body/UUID, receipt and storage cleanup', flush=True)
                    finally:
                        context.close()
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default=shutil.which('chromium'))
    parser.add_argument('--artifacts', type=Path)
    args = parser.parse_args()
    if not args.chromium:
        parser.error('Chromium not found; pass --chromium')
    artifacts = args.artifacts or Path(tempfile.mkdtemp(prefix='stroyka-manual-recovery-artifacts-'))
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stroyka-manual-recovery-build-') as build:
        subprocess.run(['node', str(ROOT / 'scripts/manual-command-recovery-browser/build.cjs'), build],
                       cwd=ROOT, check=True)
        (Path(build) / 'index.html').write_text(
            '<!doctype html><html lang="ru"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="icon" href="data:,"><title>Manual recovery fixture</title>'
            '<div id="root"></div><script src="bundle.js"></script></html>', encoding='utf-8')
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=build))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            check(server, artifacts.resolve(), args.chromium)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    print(f'4 browser scenarios passed; screenshots: {artifacts.resolve()}')


if __name__ == '__main__':
    main()
