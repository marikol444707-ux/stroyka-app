"""Manual demo: upstream Jev chooses on Timeweb; an isolated local MCP executes.

Only a built-in fixture is supported. No user browser profile or arbitrary URL.
"""
import json
import os
import re
import select
import shlex
import signal
import subprocess
import tempfile
import time
from urllib.parse import quote


REMOTE_CODE = '''import json,sys
from dev_control.browser_worker.provider import install_timeweb_provider
from jev_ultrafast.model import choose
request=json.loads(sys.stdin.buffer.read(65537))
if set(request)!={'page','history'}: raise ValueError('Unsupported request')
patch=install_timeweb_provider()
try:
 result=choose(request['page'],
  'Нажми «Проверить связь». Заверши, только когда виден результат JEV_LOCAL_OK.',
  request['history'])
 print(json.dumps({'choice':result['choice'],'operation':result['operation']}))
finally: patch.restore()
'''


def observed_page(snapshot):
    refs = re.findall(r'^\s*- button "Проверить связь" \[ref=([^\]]+)\](?!.*\[disabled\])',
                      snapshot, re.M)
    if len(refs) > 1:
        raise ValueError('Ambiguous fixture button')
    return {'url': 'about:blank', 'title': 'Jev local connection', 'text': snapshot[:10000],
            'actions': [{'id': ref, 'node': index, 'kind': 'click', 'role': 'button',
                         'label': 'Проверить связь'} for index, ref in enumerate(refs, 1)]}


def validate_choice(decision, page):
    choice = decision.get('choice')
    if choice not in {'DONE', 'BLOCKED', *(a['id'] for a in page['actions'])}:
        raise ValueError('Jev selected an unobserved action')
    return choice


def verified_done(choice, snapshot, clicks):
    return (choice == 'DONE' and len(clicks) == 1
            and bool(re.search(r'^\s*- paragraph(?: \[ref=[^\]]+\])?: JEV_LOCAL_OK\s*$',
                               snapshot, re.M)))


def remote_choose(page, history):
    command = 'sudo -n docker exec -i stroyka-jev-control python3 -c ' + shlex.quote(REMOTE_CODE)
    payload = json.dumps({'page': page, 'history': history}, ensure_ascii=False)
    if len(payload.encode()) > 64000:
        raise ValueError('Observation exceeds budget')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                             'stroyka-dev-agent', command], input=payload, text=True,
                            capture_output=True, timeout=45)
    if result.returncode:
        # Provider/SSH stderr may contain sensitive details; never print it.
        raise RuntimeError('Remote Jev decision failed')
    decision = json.loads(result.stdout)
    validate_choice(decision, page)
    return decision


class LocalBrowser:
    """A bounded stdio MCP connection owning just its temporary browser."""

    def __enter__(self):
        self.buffer, self.sequence = b'', 0
        self.directory = tempfile.TemporaryDirectory(prefix='jev-local-browser-')
        self.process = subprocess.Popen(
            ['/usr/local/bin/npx', '-y', '@playwright/mcp@0.0.83', '--browser', 'chrome',
             '--isolated', '--timeout-navigation', '15000', '--output-dir', self.directory.name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={k: v for k, v in os.environ.items()
                 if k in {'PATH', 'HOME', 'TMPDIR', 'LANG', 'DISPLAY', 'SHELL'}})
        try:
            self.rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                                   'clientInfo': {'name': 'jev-local-demo', 'version': '1'}})
            self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + '\n').encode())
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            while b'\n' in self.buffer:
                raw, self.buffer = self.buffer.split(b'\n', 1)
                reply = json.loads(raw)
                if reply.get('method') == 'roots/list' and 'id' in reply:
                    self.send({'jsonrpc': '2.0', 'id': reply['id'], 'result': {'roots': []}})
                if reply.get('id') == request_id:
                    if 'error' in reply:
                        raise RuntimeError('MCP request rejected')
                    return reply['result']
            ready, _, _ = select.select([self.process.stdout], [], [], 0.2)
            if ready:
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('MCP disconnected')
                self.buffer += chunk
                if len(self.buffer) > 8 * 1024 * 1024:
                    raise RuntimeError('MCP response exceeds budget')
        raise TimeoutError('MCP response timed out')

    def call(self, name, arguments):
        result = self.rpc('tools/call', {'name': name, 'arguments': arguments})
        if result.get('isError'):
            raise RuntimeError('Browser tool failed: ' + name)
        return '\n'.join(x.get('text', '') for x in result.get('content', [])
                         if x.get('type') == 'text')

    def snapshot(self):
        text = self.call('browser_snapshot', {})
        match = re.search(r'```yaml\n(.*?)\n```', text, re.S)
        if not match:
            raise ValueError('MCP returned no inline snapshot')
        return match.group(1)

    def __exit__(self, *_):
        try:
            if self.process.poll() is None:
                self.call('browser_close', {})
        finally:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            self.directory.cleanup()


def demo():
    html = ('<html><head><meta charset="utf-8"><title>Jev local connection</title></head>'
            '<body><button onclick="this.disabled=true;document.querySelector(\'p\').textContent='
            '\'JEV_LOCAL_OK\'">Проверить связь</button><p>Waiting</p></body></html>')
    history, clicks, decisions = [], [], []
    with LocalBrowser() as browser:
        browser.call('browser_navigate', {'url': 'data:text/html,' + quote(html, safe='')})
        for _ in range(3):
            snapshot = browser.snapshot()
            page = observed_page(snapshot)
            decision = remote_choose(page, history)
            choice = validate_choice(decision, page)
            decisions.append(choice)
            if choice in {'DONE', 'BLOCKED'}:
                return {'ok': verified_done(choice, snapshot, clicks), 'status': choice,
                        'model_calls': len(decisions), 'clicks': len(clicks),
                        'local_browser': True, 'provider_key_copied': False}
            if clicks:
                raise ValueError('Repeated click refused')
            browser.call('browser_click', {'target': choice})
            clicks.append(choice)
            history.append({'action': 'Проверить связь', 'kind': 'click', 'page_changed': True})
    return {'ok': False, 'status': 'step_budget_exhausted'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['demo'])
    parser.parse_args()
    try:
        result = demo()
    except Exception as exc:
        result = {'ok': False, 'status': 'failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
