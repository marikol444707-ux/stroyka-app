"""Bounded, credential-free browser sessions for the owner's Jev controller.

This runner never changes the QA worker's configured target or authentication.
Only the local demo and the explicitly requested public Avito search are exposed.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import urllib.request
from urllib.parse import urlencode, urlparse
from uuid import uuid4


def task_spec(request: dict) -> dict:
    operation = request.get('operation')
    if operation == 'demo' and set(request) == {'operation'}:
        return {'base': 'http://127.0.0.1:8080',
                'url': 'http://127.0.0.1:8080/selftest-page',
                'goal': 'Click Run browser self-test. Finish only when JEV_BROWSER_OK is visible. Do not type.'}
    if operation == 'avito' and set(request) <= {'operation', 'query'}:
        query = request.get('query', '')
        if isinstance(query, str) and 1 <= len(query.strip()) <= 500:
            return {'base': 'https://www.avito.ru',
                    'url': 'https://www.avito.ru/stavropolskiy_kray?' + urlencode({'q': query}),
                    'goal': 'Find five matching public listings for ' + query +
                            ' in Stavropol Krai. Keep the region. Stop when listings and prices are visible. '
                            'Do not log in, contact sellers, purchase, publish, upload, or solve security challenges.'}
    raise ValueError('Unsupported task or fields')


def demo_passed(state: dict, facts: dict) -> bool:
    return (state.get('status') == 'done'
            and facts == {'marker': 'JEV_BROWSER_OK', 'disabled': True}
            and [x.get('kind') for x in state.get('history', [])] == ['click'])


async def _probe_browser() -> None:
    import websockets
    with urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=2) as response:
        version = json.load(response)
    endpoint = version['webSocketDebuggerUrl']
    parsed = urlparse(endpoint)
    if (parsed.scheme != 'ws' or parsed.netloc != '127.0.0.1:9222'
            or not parsed.path.startswith('/devtools/browser/') or parsed.query or parsed.fragment):
        raise ValueError('Unexpected CDP endpoint')
    async with websockets.connect(endpoint, open_timeout=2, close_timeout=1, max_size=1024*1024) as ws:
        sequence = 0

        async def call(method, params=None, session=None):
            nonlocal sequence
            sequence += 1
            request_id = sequence
            message = {'id': request_id, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            await ws.send(json.dumps(message))
            while True:
                reply = json.loads(await asyncio.wait_for(ws.recv(), 2))
                if reply.get('id') == request_id:
                    if 'error' in reply:
                        raise RuntimeError('CDP probe rejected')
                    return reply.get('result', {})

        context = (await call('Target.createBrowserContext'))['browserContextId']
        try:
            target = (await call('Target.createTarget', {'url': 'about:blank', 'browserContextId': context}))['targetId']
            session = (await call('Target.attachToTarget', {'targetId': target, 'flatten': True}))['sessionId']
            await call('Emulation.setDeviceMetricsOverride',
                       {'width': 1120, 'height': 780, 'deviceScaleFactor': 1, 'mobile': False}, session)
            reply = await call('Runtime.evaluate', {'expression': '1+1', 'returnByValue': True}, session)
            if reply.get('result', {}).get('value') != 2:
                raise RuntimeError('Renderer did not respond')
        finally:
            await call('Target.disposeBrowserContext', {'browserContextId': context})


def run(request: dict) -> dict:
    if request == {'operation': 'health'}:
        asyncio.run(asyncio.wait_for(_probe_browser(), 12))
        return {'ok': True, 'browser': 'renderer_verified', 'model_calls': 0}
    spec = task_spec(request)
    # Set before importing browser-harness; it captures its name at import time.
    name = 'control-' + uuid4().hex
    os.environ['BU_NAME'] = name
    for key in ('QA_SESSION_COOKIE_NAME', 'QA_SESSION_COOKIE_VALUE', 'DEV_CONTROL_API_TOKEN',
                'JEV_WATCHER_TOKEN', 'JEV_WATCH_GITHUB_TOKEN'):
        os.environ.pop(key, None)
    from dev_control.browser_worker.network_guard import install_safe_browser
    from dev_control.browser_worker.provider import install_timeweb_provider
    from browser_harness.admin import restart_daemon
    from jev_ultrafast import Agent

    patch = None
    result = {'ok': False, 'status': 'not_completed'}
    try:
        install_safe_browser(spec['base'], read_only=True)
        patch = install_timeweb_provider()
        with Agent(spec['url'], spec['goal'], screenshots=False) as agent:
            for index, state in enumerate(agent.run(), 1):
                if index >= 20:
                    break
            result.update(status=state.get('status'), actions=len(state.get('history', [])),
                          model_calls=len(state.get('decisions', [])))
            if request['operation'] == 'demo':
                facts = agent.browser.evaluate("({marker:document.getElementById('result').textContent,disabled:document.getElementById('run-test').disabled})")
                result.update(ok=demo_passed(state, facts), verified_facts=facts)
            else:
                page = state.get('page') or {}
                result.update(status='observed_unverified', url=page.get('url'),
                              text=str(page.get('text', ''))[:6500])
    except Exception as exc:
        # Do not expose provider responses, credentials or arbitrary exception text.
        result.update(ok=False, status='failed', error_type=type(exc).__name__)
        if 'firewallPow' in str(exc):
            result['status'] = 'site_security_check_blocked'
    finally:
        if patch:
            patch.restore()
        # A stuck cleanup is bounded separately; the host never repeats a task.
        signal.alarm(20)
        try:
            restart_daemon(name=name)
            result['session_cleaned'] = True
        except Exception:
            result.update(ok=False, session_cleaned=False)
        finally:
            signal.alarm(0)
    return result


def main():
    def expired(*_):
        raise TimeoutError('task budget exhausted')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(65)
    try:
        request = json.loads(sys.stdin.buffer.read(8193))
        result = run(request)
    except Exception as exc:
        result = {'ok': False, 'status': 'failed', 'error_type': type(exc).__name__}
    finally:
        signal.alarm(0)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
