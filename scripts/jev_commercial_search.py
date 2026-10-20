"""Bounded public B2B-Center search. Unknown procedure regimes stay unconfirmed."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

HOST = 'www.b2b-center.ru'
BASE = 'https://' + HOST + '/app/next/market-search'
IMAGE = 'sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d'
MSK = timezone(timedelta(hours=3))
TERMS = ('Ставрополь', 'Ставропольский край', 'Невинномысск', 'Пятигорск', 'Кисловодск',
         'Ессентуки', 'Минеральные Воды', 'Михайловск', 'Будённовск', 'Георгиевск',
         'Железноводск', 'Лермонтов')
WORK = re.compile(r'строительн|строительств|отделоч|электромонтаж|фундамент|благоустрой|'
                  r'ремонт\w*\s+(?:помещен|здан|офис|кровл|фасад|магаз|объект)|'
                  r'монтаж\w*\s+.{0,35}(?:сет|систем|кабель|вентиляц)', re.I)
GOODS_ONLY = re.compile(r'\b(?:поставк\w*|приобретен\w*|закупк\w*)\b', re.I)
WORK_ACTION = re.compile(r'\b(?:выполнени\w*\s+работ|строительств\w*|ремонт\w*\s+(?:помещен|здан|офис|кровл|фасад|магаз|объект)|отделоч\w*\s+работ|монтаж\w*\s+(?:работ|сет|систем|кабель|вентиляц)|благоустройств\w*)', re.I)
EQUIPMENT_REPAIR = re.compile(r'ремонт\w*\s+(?:оборудован|двигател|транспорт|станк|насос|датчик|преобразоват|тс\b|котельного\s+оборудован)', re.I)
REGION = re.compile(r'Ставропольск\w*\s+кра|Ставропол|Невинномысск|Пятигорск|Кисловодск|Ессентук|Минеральные\s+Воды|Михайловск|Буд[её]нновск', re.I)
EXCLUDED_LAW = re.compile(r'\b(?:44|223)\s*[-‑–]?\s*ФЗ\b|615\s*[-‑–]?\s*ПП', re.I)


def search_url(term):
    if not isinstance(term, str) or not 1 <= len(term) <= 64: raise ValueError('Invalid search term')
    # Parameters observed after submitting the public form, not protected filters.
    return BASE + '?' + urlencode(dict(q=term, company_type='2', include_firm_tree='false',
                                       sort='date_desc', trade='buy', show='actual'))


def tender_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != HOST or parsed.query or
        not re.fullmatch(r'/(?:app/market-next|market)/[a-zA-Z0-9_-]+/tender-[0-9]+/', parsed.path)):
        raise ValueError('Unexpected procedure URL')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def search_checks(observed, term):
    parsed = urlsplit(observed.get('url', ''))
    params = parse_qs(parsed.query)
    tabs = observed.get('selected', [])
    actual = next((re.search(r'^Актуально\s*•\s*([\d\s]+)$', x) for x in tabs if x.startswith('Актуально')), None)
    count = int(re.sub(r'\s', '', actual.group(1))) if actual else None
    highlights = observed.get('highlights', [])
    return {
        'public_search_url': parsed.scheme == 'https' and parsed.netloc == HOST and parsed.path.rstrip('/') == '/app/next/market-search',
        'query_in_url': params.get('q') == [term],
        'buy_mode_in_url': params.get('trade') == ['buy'] and params.get('show') == ['actual'],
        'rendered_query': observed.get('query') == term,
        'procurement_tab': 'Объявления о закупках' in tabs,
        'active_results_tab': count is not None,
        'rows_match_count': (bool(observed.get('rows')) if count else not observed.get('rows')) if count is not None else False,
        'query_highlighted': all(any(word.casefold() in value.casefold() for value in highlights)
                                 for word in term.split()) if observed.get('rows') else True,
    }


def verify_search(observed, term):
    return all(search_checks(observed, term).values())


def assess(row, now):
    result = dict(row, decision='review', reasons=[])
    try:
        result['url'] = tender_url(row['url'])
        if not result['url'].endswith('/tender-' + str(row['id']) + '/'):
            raise ValueError('Procedure identity mismatch')
    except (KeyError, ValueError):
        return dict(result, decision='excluded', reasons=['invalid_source'])
    if not WORK.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['not_construction_work'])
    if GOODS_ONLY.search(row.get('title', '')) and not WORK_ACTION.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['goods_purchase_not_work'])
    if EQUIPMENT_REPAIR.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['equipment_repair_not_building_work'])
    place = row.get('place', row.get('region', ''))
    if not REGION.search(place):
        if REGION.search(row.get('title', '')):
            result['reasons'].append('place_conflict_needs_review')
        elif place:
            return dict(result, decision='excluded', reasons=['other_region'])
        else: result['reasons'].append('work_location_unknown')
    try:
        found = re.search(r'\b\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}\b', row.get('deadline', ''))
        deadline = datetime.strptime(found.group(), '%d.%m.%Y %H:%M').replace(tzinfo=MSK)
        if deadline <= now: return dict(result, decision='excluded', reasons=['deadline_expired'])
        result['deadline_msk'] = deadline.isoformat()
    except (AttributeError, ValueError): result['reasons'].append('deadline_unknown')
    regime = row.get('regime', '')
    if EXCLUDED_LAW.search(regime): return dict(result, decision='excluded', reasons=['regulated_procurement'])
    if not re.fullmatch(r'коммерческ(?:ая|ие)(?:\s+закупк[аи])?', regime.strip(), re.I):
        result['reasons'].append('procurement_regime_unknown')
    if not result['reasons']: result['decision'] = 'confirmed'
    return result


def build_report(rows, sources, now=None):
    now = now or datetime.now(timezone.utc)
    unique = {}
    for row in rows:
        key = str(row.get('id', ''))
        if key: unique.setdefault(key, row)
    assessed = [assess(row, now) for row in unique.values()]
    excluded = {}
    for row in assessed:
        if row['decision'] == 'excluded':
            reason = row['reasons'][0] if row['reasons'] else 'other'
            excluded[reason] = excluded.get(reason, 0) + 1
    return {'generated_at': now.isoformat(), 'region': 'Ставропольский край', 'source': 'B2B-Center',
            'coverage': 'Первые страницы поиска по 12 городам и региону; неполный охват населённых пунктов, площадок и страниц',
            'sources': sources, 'confirmed': [x for x in assessed if x['decision'] == 'confirmed'],
            'review': [x for x in assessed if x['decision'] == 'review'],
            'excluded': excluded,
            'ok': bool(sources) and all(x.get('ok') for x in sources), 'model_calls': 0}


OBSERVE = r'''(()=>{const main=document.querySelector('main');const tabs=[...new Set([...document.querySelectorAll('[role="tab"],.cds-tab-v2')])];return {
url:location.href,title:document.title,query:main?.querySelector('input[name="q"]')?.value,
page_state:main?.innerText.slice(0,700)??document.body?.innerText.slice(0,700)??'',
all_tabs:tabs.slice(0,8).map(e=>e.innerText.trim()),
selected:tabs.filter(e=>e.getAttribute('aria-selected')==='true'||e.classList.contains('cds-tab-v2--selected')).map(e=>e.innerText.trim()),
highlights:[...main?.querySelectorAll('mark')??[]].map(e=>e.innerText),
rows:[...main?.querySelectorAll('.panel-procedure__card')??[]].slice(0,20).map(e=>({
id:e.querySelector('.panel-procedure__number-link')?.innerText.replace(/\D/g,''),
url:e.querySelector('.panel-procedure__number-link')?.href,
title:e.querySelector('.panel-procedure__dscr-main')?.innerText.slice(0,1500),
organizer:e.querySelector('.panel-procedure__dscr-branch')?.innerText.slice(0,300),
deadline:e.querySelector('.panel-procedure__dscr-date')?.innerText.slice(0,150),
price:e.querySelector('.panel-procedure__details-item-sum')?.innerText.slice(0,300),
region:e.querySelector('.panel-procedure__details-item-region')?.innerText.slice(0,300)})).filter(e=>e.id&&e.title)};})()'''


async def worker():
    import os
    from urllib.request import urlopen
    import websockets
    scratch = tempfile.mkdtemp(prefix='commercial-')
    chrome = subprocess.Popen(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox',
        '--disable-dev-shm-usage', '--remote-debugging-port=9229', '--user-data-dir='+scratch+'/chrome', 'about:blank'],
        env={'HOME': scratch, 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = []
        for _ in range(30):
            try:
                with urlopen('http://127.0.0.1:9229/json/list', timeout=1) as response:
                    targets = [x for x in json.load(response) if x.get('type') == 'page']
                if targets: break
            except OSError: pass
            await asyncio.sleep(.2)
        if not targets: raise RuntimeError('Browser not ready')
        endpoint = targets[0]['webSocketDebuggerUrl']
        if not endpoint.startswith('ws://127.0.0.1:9229/devtools/page/'): raise ValueError('Unexpected browser endpoint')
        rows, sources = [], []
        async with websockets.connect(endpoint, max_size=2*1024*1024) as socket:
            sequence = 0
            async def call(method, params):
                nonlocal sequence
                sequence += 1
                current = sequence
                await socket.send(json.dumps(dict(id=current, method=method, params=params)))
                while True:
                    reply = json.loads(await asyncio.wait_for(socket.recv(), 8))
                    if reply.get('id') == current:
                        if 'error' in reply: raise RuntimeError('Browser command failed')
                        return reply.get('result', {})
            for term in TERMS:
                await call('Page.navigate', {'url': search_url(term)})
                observed, previous, stable = {}, None, 0
                end = time.monotonic() + 12
                while time.monotonic() < end:
                    await asyncio.sleep(.6)
                    response = await call('Runtime.evaluate', {'expression': OBSERVE, 'returnByValue': True})
                    if 'exceptionDetails' in response:
                        observed = {'url': search_url(term), 'query': None, 'selected': [],
                                    'highlights': [], 'rows': [], 'evaluation_failed': True}
                        break
                    observed = response.get('result', {}).get('value') or {}
                    ready = verify_search(observed, term)
                    signature = json.dumps(observed, sort_keys=True)
                    stable = stable + 1 if ready and signature == previous else 0
                    previous = signature
                    if stable >= 2: break
                verified = stable >= 2
                source = {'query': term, 'ok': verified, 'url': observed.get('url', search_url(term)),
                          'status': 'observed_first_page' if verified else 'search_not_verified',
                          'rows': len(observed.get('rows', [])) if verified else 0}
                if not verified:
                    checks = search_checks(observed, term)
                    source.update({'observed_query': observed.get('query'),
                                   'page_title': observed.get('title', '')[:160],
                                   'page_state': observed.get('page_state', ''),
                                   'visible_tabs': observed.get('all_tabs', []),
                                   'active_tabs': observed.get('selected', [])[:3],
                                   'failed_checks': [name for name, passed in checks.items() if not passed],
                                   'evaluation_failed': observed.get('evaluation_failed', False)})
                sources.append(source)
                if not verified:
                    break
                if verified:
                    for row in observed.get('rows', []):
                        try: row['url'] = tender_url(row['url'])
                        except (KeyError, ValueError): continue
                        rows.append(row)
        return build_report(rows, sources)
    finally:
        chrome.terminate()
        try: chrome.wait(timeout=5)
        except subprocess.TimeoutExpired: chrome.kill(); chrome.wait(timeout=5)


def probe():
    name = 'stroyka-commercial-' + uuid4().hex
    command = ['docker', 'run', '--rm', '--name', name, '--user', '10001:10001', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--memory', '1g', '--pids-limit', '256', '--read-only',
               '--tmpfs', '/tmp:rw,nosuid,nodev,size=384m', '--network', 'bridge',
               '--mount', 'type=bind,src='+str(Path(__file__).resolve())+',dst=/commercial.py,readonly',
               '--entrypoint', 'python3', IMAGE, '/commercial.py', '--worker']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or (result.returncode and data.get('ok')):
            raise ValueError('Invalid runner response')
        return data
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)


def render(report):
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Строительные закупки — коммерческий поиск</title><style>body{font:16px system-ui;max-width:850px;margin:24px auto;padding:0 16px;background:#f4f6fa;color:#253047}article{background:white;padding:18px;margin:12px 0;border-radius:12px}p,a{overflow-wrap:anywhere}</style>',
             '<h1>Коммерческие закупки: поиск кандидатов</h1><p>'+esc(report['coverage'])+'</p>',
             '<p>Непроверенный правовой режим не означает коммерческую закупку. Место и условия требуют сверки в оригинале.</p>']
    for key, label in (('confirmed', 'Подтверждённые по полям источника'), ('review', 'Нужно проверить')):
        parts.append('<h2>{}: {}</h2>'.format(label, len(report[key])))
        for row in report[key]:
            parts.append('<article><h3>'+esc(row.get('title', ''))+'</h3>')
            for field, title in (('organizer','Заказчик'),('region','Регион в выдаче'),('deadline','Подача до (МСК)'),('price','Цена')):
                parts.append('<p><b>{}:</b> {}</p>'.format(title, esc(row.get(field) or 'Не указано')))
            parts.append('<p>Причины проверки: '+esc(', '.join(row['reasons']))+'</p>')
            parts.append('<a rel="noreferrer" href="'+esc(tender_url(row['url']))+'">Открыть оригинал</a></article>')
    for source in report['sources']:
        parts.append('<p>{}: {} · строк {}</p>'.format(esc(source['query']),esc(source['status']), source['rows']))
    return ''.join(parts)+'</html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--output', help='Private report directory outside repository')
    args = parser.parse_args()
    report = asyncio.run(worker()) if args.worker else probe()
    if args.output:
        try: from .jev_telegram import private_directory, write_private
        except ImportError: from jev_telegram import private_directory, write_private
        folder = private_directory(args.output)
        write_private(folder/'report.json', json.dumps(report, ensure_ascii=False, indent=2))
        write_private(folder/'report.html', render(report))
    return report


if __name__ == '__main__':
    try: result = main()
    except Exception as exc: result = {'ok': False, 'status': 'commercial_search_failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get('ok') else 1)
