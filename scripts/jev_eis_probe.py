"""Read-only EIS browser access probe; not an autonomous procurement search.

The CA is trusted only inside this short-lived, credential-free browser container.
"""
import hashlib
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urljoin, urlparse, parse_qs
from uuid import uuid4

URL = 'https://zakupki.gov.ru/epz/order/extendedsearch/results.html'
IMAGE = 'sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d'
CA_SHA256 = 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'

class Registry(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ''
        self.search = False
        self.query = None
        self.notices = set()
        self.text = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'style'}: self.hidden_depth += 1
        if tag == 'title': self.in_title = True
        if tag == 'input' and attrs.get('name') == 'searchString':
            self.search = True
            self.query = attrs.get('value', '')
        if tag == 'a':
            link = urljoin(URL, attrs.get('href', ''))
            parsed = urlparse(link)
            if (parsed.scheme == 'https' and parsed.netloc == 'zakupki.gov.ru'
                    and parsed.path.endswith('/common-info.html') and 'regNumber=' in parsed.query):
                self.notices.add(link)

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in {'script', 'style'}: self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data):
        if self.in_title: self.title += data
        if not self.hidden_depth: self.text.append(data)


def classify(html, *, url=URL, query=None, visible_text=None):
    page = Registry()
    page.feed(html)
    registry = page.title.strip() == 'Закупки' and page.search
    query_ok = (query is not None and page.query == query
                and urlparse(url).scheme == 'https' and urlparse(url).netloc == 'zakupki.gov.ru'
                and urlparse(url).path == urlparse(URL).path
                and parse_qs(urlparse(url).query).get('searchString') == [query])
    visible_text = ' '.join((' '.join(page.text) if visible_text is None else visible_text).split())
    empty = (not page.notices and 'Поиск не дал результатов' in visible_text
             and bool(re.search(r'\b0 записей\b', visible_text)))
    ready = registry and (bool(page.notices) or (empty and query_ok))
    if query is not None: ready = ready and query_ok
    status = 'registry_not_verified'
    if ready:
        status = ('keyword_search_empty' if empty else 'keyword_search_observed') if query_ok else 'search_registry_accessible'
    if 'ERR_CERT_' in html: status, ready = 'tls_failed', False
    return {'ok': ready, 'status': status, 'title': page.title.strip()[:150],
            'url': url, 'notice_links_observed': len(page.notices),
            'notice_links': sorted(page.notices)[:10],
            'query': query, 'search_execution_verified': bool(ready and query_ok),
            'region_verified': False, 'model_calls': 0}


def verify_ca(path):
    import ssl
    der = ssl.PEM_cert_to_DER_cert(path.read_text())
    if hashlib.sha256(der).hexdigest() != CA_SHA256:
        raise ValueError('Unexpected EIS CA fingerprint')


async def search_browser(tmp, env, query):
    """Submit the observed GET form; never synthesize undocumented query filters."""
    import asyncio
    import urllib.request
    import websockets
    chrome = subprocess.Popen(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox',
        '--disable-dev-shm-usage', '--remote-debugging-port=9229',
        '--user-data-dir='+tmp+'/chrome', 'about:blank'], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = []
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:9229/json/list', timeout=1) as response:
                    targets = [x for x in json.load(response) if x.get('type') == 'page']
                if targets: break
            except OSError:
                pass
            await asyncio.sleep(.2)
        if not targets: return {'ok': False, 'status': 'browser_not_ready'}
        endpoint = targets[0]['webSocketDebuggerUrl']
        if not endpoint.startswith('ws://127.0.0.1:9229/devtools/page/'):
            raise ValueError('Unexpected browser endpoint')
        async with websockets.connect(endpoint, max_size=3*1024*1024) as ws:
            sequence = 0

            async def call(method, params):
                nonlocal sequence
                sequence += 1
                request_id = sequence
                await ws.send(json.dumps({'id': request_id, 'method': method, 'params': params}))
                while True:
                    reply = json.loads(await asyncio.wait_for(ws.recv(), 12))
                    if reply.get('id') == request_id:
                        if 'error' in reply: raise RuntimeError('Browser command rejected')
                        return reply.get('result', {})

            async def evaluate(expression):
                reply = await call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
                if 'exceptionDetails' in reply: raise RuntimeError('Page evaluation failed')
                return reply.get('result', {}).get('value')

            await call('Page.navigate', {'url': URL})
            for _ in range(20):
                if await evaluate('!!document.querySelector("#quickSearchForm_header input[name=searchString]")'):
                    break
                await asyncio.sleep(.5)
            # Both form action and method must be observed and agree with the public registry.
            script = ('(()=>{const f=document.querySelector("#quickSearchForm_header");'
                'const i=f?.querySelector("input[name=searchString]");'
                'if(!i||f.method.toLowerCase()!=="get"||f.action!=='+json.dumps(URL)+')return false;'
                'i.value='+json.dumps(query)+';i.dispatchEvent(new Event("input",{bubbles:true}));'
                'i.dispatchEvent(new Event("change",{bubbles:true}));f.requestSubmit();return true})()')
            if await evaluate(script) is not True:
                return {'ok': False, 'status': 'search_form_not_verified'}
            for _ in range(30):
                await asyncio.sleep(.5)
                observation = await evaluate('({url:location.href,html:document.documentElement.outerHTML,text:document.body.innerText})')
                if observation:
                    result = classify(observation['html'], url=observation['url'], query=query, visible_text=observation['text'])
                    if result['ok']: return result
            return {'ok': False, 'status': 'search_result_not_verified',
                    'search_execution_verified': False}
    finally:
        chrome.terminate()
        try: chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
            chrome.wait(timeout=5)


def worker(query=None):
    ca = Path('/cert/root.pem')
    verify_ca(ca)
    # The outer disposable container owns its tmpfs. Do not race Chrome's
    # descendants by deleting its profile while returning a verified result.
    # Docker --rm / the host's finally block remove all scratch after PID 1 exits.
    tmp = tempfile.mkdtemp(prefix='eis-browser-')
    env = {'HOME': tmp, 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    db = Path(tmp) / '.pki/nssdb'
    db.mkdir(parents=True)
    for args in (['certutil', '-N', '-d', 'sql:'+str(db), '--empty-password'],
                 ['certutil', '-A', '-d', 'sql:'+str(db), '-n', 'EIS Russian Trusted Root',
                  '-t', 'C,,', '-i', str(ca)]):
        subprocess.run(args, env=env, check=True, capture_output=True, timeout=5)
    if query is not None:
        import asyncio
        return asyncio.run(search_browser(tmp, env, query))
    result = subprocess.run(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox',
        '--disable-dev-shm-usage', '--user-data-dir='+tmp+'/chrome', '--dump-dom', URL],
        env=env, timeout=40, capture_output=True, text=True)
    if result.returncode: return {'ok': False, 'status': 'browser_failed'}
    return classify(result.stdout)


def probe(query=None):
    if query is not None and (not isinstance(query, str) or not 1 <= len(query.strip()) <= 200):
        raise ValueError('Invalid search query')
    repo = Path(__file__).resolve().parent.parent
    ca = repo / 'dev_control/certificates/russian-trusted-root.pem'
    verify_ca(ca)
    name = 'stroyka-eis-probe-' + uuid4().hex
    args = ['docker', 'run', '--rm', '--name', name, '--network', 'bridge',
            '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '1g', '--pids-limit', '256', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=384m',
            '--mount', 'type=bind,src='+str(ca)+',dst=/cert/root.pem,readonly',
            '--mount', 'type=bind,src='+str(Path(__file__).resolve())+',dst=/probe.py,readonly',
            '--entrypoint', 'python3', IMAGE, '/probe.py', '--worker']
    if query is not None: args.extend(['--query', query])
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=75)
        try:
            outcome = json.loads(result.stdout)
        except (ValueError, TypeError):
            return {'ok': False, 'status': 'runner_failed', 'exit_code': result.returncode}
        if not isinstance(outcome, dict) or not isinstance(outcome.get('ok'), bool):
            return {'ok': False, 'status': 'invalid_runner_response'}
        if result.returncode and outcome['ok']:
            return {'ok': False, 'status': 'runner_failed', 'exit_code': result.returncode}
        return outcome
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--query')
    options = parser.parse_args()
    try:
        result = worker(options.query) if options.worker else probe(options.query)
    except subprocess.TimeoutExpired:
        result = {'ok': False, 'status': 'browser_timeout'}
    except Exception as exc:
        result = {'ok': False, 'status': 'probe_failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get('ok') else 1)
