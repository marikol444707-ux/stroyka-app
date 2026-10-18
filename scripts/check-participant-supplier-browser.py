#!/usr/bin/env python3
"""Opt-in browser check of the built app, real FastAPI and an empty socket-only PG.

Requires Playwright, Chromium, backend dependencies, a build with participant
support/history merge enabled, and the existing SUPPLY_CHAIN_* test settings.
Never accepts a remote URL, production DSN or existing nonempty database.
"""
import argparse
import base64
import hashlib
import hmac
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REASON = 'Проверены юридическое лицо и исходные документы'


def totp(secret):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((int.from_bytes(digest[offset:offset+4], 'big') & 0x7fffffff) % 1000000).zfill(6)


def browser_check(state, artifacts, chromium):
    from playwright.sync_api import sync_playwright, expect

    def login(page, actor):
        page.goto('http://localhost:8001/app')
        if actor == 'stranger':
            # Authenticate the other buyer for exact API probes without starting
            # unrelated business screens outside this supplier fixture's schema.
            status = page.evaluate("""async x => {
                const options=body=>({method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
                const first=await fetch('/login',options({email:x.email,password:x.password}));
                if(!first.ok) return first.status;
                const data=await first.json();
                if(!data.twoFactorRequired) throw Error('Expected buyer 2FA');
                const verified=await fetch('/login/2fa/verify',options({challengeToken:data.challengeToken,code:x.code}));
                return verified.status;
            }""", {'email': state['users'][actor]['email'], 'password': state['password'],
                    'code': totp(state['users'][actor]['secret'])})
            assert status == 200, 'Other buyer authentication failed'
            return
        page.locator('input[type=email]').fill(state['users'][actor]['email'])
        page.locator('input[type=password]').fill(state['password'])
        page.get_by_role('button', name='Войти в систему').click()
        if actor != 'supplier':
            page.get_by_placeholder('123456').fill(totp(state['users'][actor]['secret']))
            page.get_by_role('button', name='Подтвердить вход').click()
        if actor == 'admin':
            page.get_by_role('button', name='Аккаунты/компании', exact=False).wait_for()
        elif actor == 'supplier':
            page.get_by_role('navigation', name='Кабинет поставщика').wait_for()

    def read_invoices(page, foreign=False):
        return page.evaluate("""async foreign => {
            const r=await fetch('/supplier-invoices', foreign ? {headers:{'X-Company-Id':'3','X-Company-Mode':'company'}} : {});
            if(!r.ok) throw Error('Invoice read '+r.status); return r.json();
        }""", foreign)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium, headless=True, args=['--no-sandbox'])
        try:
            for size, width, height in [('mobile', 390, 844), ('desktop', 1280, 900)]:
                row = state['scenarios'][size]
                contexts = [browser.new_context(viewport={'width': width, 'height': height}) for _ in range(3)]
                errors, server_errors = [], []
                try:
                    for context in contexts:
                        context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname
                            in ('localhost', '127.0.0.1') else route.abort())
                    admin, supplier, foreign = [context.new_page() for context in contexts]
                    for page in (admin, supplier, foreign):
                        page.set_default_timeout(15000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('response', lambda response: server_errors.append(urlsplit(response.url).path)
                            if response.status >= 500 else None)
                    login(supplier, 'supplier')
                    assert row['invoice'] not in [item['id'] for item in read_invoices(supplier)]
                    login(admin, 'admin')
                    admin.get_by_role('button', name='Аккаунты/компании', exact=False).click()
                    admin.get_by_role('button', name='Участники и доступ').nth(1).click()
                    registry = admin.get_by_role('region', name='Участники и доступ: SUPPLY CHAIN company 2', exact=True)
                    receipt = registry.locator('li').filter(has=admin.get_by_text('BROWSER '+size+' receipt', exact=True))
                    receipt.get_by_role('button', name='Объединить дубли').click()
                    panel = admin.get_by_role('region', name='Объединение дубля', exact=True)
                    panel.get_by_role('textbox', name='Название или ИНН основной карточки').fill('BROWSER '+size+' cabinet')
                    panel.get_by_role('button', name='Найти основную карточку').click()
                    panel.get_by_role('button', name='BROWSER '+size+' cabinet', exact=False).click()
                    panel.get_by_role('button', name='Проверить последствия').click()
                    panel.get_by_role('checkbox').check()
                    panel.get_by_role('textbox', name='Основание объединения').fill('ИНН сверили по исходному документу кабинета')
                    panel.get_by_role('button', name='Заполнить пропущенный ИНН').click()
                    expect(panel.get_by_role('status')).to_contain_text('ИНН сохранён')
                    assert row['invoice'] not in [item['id'] for item in read_invoices(supplier)]
                    panel.get_by_role('button', name='Проверить последствия').click()
                    panel.get_by_role('button', name='Проверить доступ к истории').click()
                    dialog = admin.get_by_role('dialog')
                    with admin.expect_response(lambda response: response.url.endswith('/history-merge-plans')) as pending:
                        dialog.get_by_role('button', name='Проверить последствия').click()
                    plan = pending.value.json()
                    assert plan['newAccess']['invoices'] == [row['invoice']]
                    dialog.get_by_role('checkbox').check()
                    dialog.get_by_role('textbox', name='Основание объединения').fill(REASON)
                    dialog.screenshot(path=str(artifacts / (size+'-plan.png')))
                    dialog.get_by_role('button', name='Подтвердить объединение').click()
                    expect(dialog.get_by_role('status')).to_contain_text('Карточки объединены')
                    replay = admin.evaluate("""async x => {
                        const r=await fetch('/system/companies/2/participants/'+x.source+'/history-merge-plans/'+x.plan+'/confirm',
                            {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,reason:x.reason})});
                        return {status:r.status,body:await r.json()};
                    }""", {'source': row['source'], 'plan': plan['id'], 'reason': REASON})
                    assert replay['status'] == 200 and replay['body']['planId'] == plan['id']
                    dialog.get_by_role('button', name='Закрыть', exact=True).click()
                    expect(admin.get_by_role('region', name='Объединение дубля', exact=True)).to_have_count(0)
                    expect(receipt.get_by_role('button', name='Открыть основную карточку')).to_be_visible()
                    supplier.reload()
                    supplier.get_by_role('button', name='Документы', exact=False).click()
                    expect(supplier.get_by_text('Счёт № —', exact=True).first).to_be_visible()
                    assert row['invoice'] in [item['id'] for item in read_invoices(supplier)]
                    login(foreign, 'stranger')
                    assert row['invoice'] not in [item['id'] for item in read_invoices(foreign, True)]
                    denied = foreign.evaluate("""async x => {
                        const r=await fetch('/system/companies/2/participants/'+x.source+'/history-merge-plans',
                            {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targetSupplierId:x.target})});
                        return r.status;
                    }""", row)
                    assert denied == 403, 'Another buyer obtained an administrative operation'
                    assert not errors, errors
                    assert not server_errors, server_errors
                    print(size+': real login/2FA, INN without history, explicit merge, replay and other-company isolation passed', flush=True)
                finally:
                    for context in contexts:
                        context.close()
        finally:
            browser.close()


def main():
    import os
    from backend.features.supplier_access.test_postgres_chain_support import connection_settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build')
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    args = parser.parse_args()
    connection_settings(os.environ)
    build = args.build.resolve()
    if not (build / 'index.html').is_file():
        parser.error('Build the frontend first')
    flags = 'REACT_APP_PARTICIPANT_SUPPORT_ENABLED=1\nREACT_APP_PARTICIPANT_HISTORY_MERGE_ENABLED=1\n'
    subprocess.run([sys.executable, str(ROOT / 'scripts/verify-frontend-feature-build.py'), str(build)],
                   input=flags, text=True, check=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 8001))  # Refuse to use an existing service.
    artifacts = Path(tempfile.mkdtemp(prefix='stroyka-supplier-browser-'))
    print('Artifacts: '+str(artifacts), flush=True)
    with (artifacts / 'server.log').open('w', encoding='utf-8') as log:
        child = subprocess.Popen([sys.executable, str(ROOT / 'scripts/participant_supplier_browser_fixture.py'),
            '--build', str(build), '--artifacts', str(artifacts)], cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 45
            while True:
                if child.poll() is not None:
                    raise RuntimeError('Fixture failed; inspect server.log')
                try:
                    with urlopen('http://localhost:8001/app', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError('Fixture startup timeout')
                    time.sleep(.2)
            state = json.loads((artifacts / 'state.json').read_text(encoding='utf-8'))
            browser_check(state, artifacts, args.chromium)
        finally:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            (artifacts / 'state.json').unlink(missing_ok=True)
    results = json.loads((artifacts / 'database-results.json').read_text(encoding='utf-8'))
    assert all(all(checks.values()) for checks in results.values()), results
    print('Database: original invoice rows preserved; exact owner/canonical link and one audit per command', flush=True)


if __name__ == '__main__':
    main()
