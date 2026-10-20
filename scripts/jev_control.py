"""Single SSH entry point; goals and credentials never enter a shell command."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

CONTAINER = 'stroyka-jev-control'
STATE_DIR = Path('/var/lib/stroyka-jev-control')
LOCK = str(STATE_DIR / 'operation.lock')


def ssh_command(operation=None):
    remote = ('sudo -n stroyka-jev commercial-search'
              if operation == 'commercial-search'
              else 'sudo -n python3 /usr/local/libexec/stroyka-jev-control/jev_control.py --server')
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o',
            'StrictHostKeyChecking=yes', 'stroyka-dev-agent',
            remote]


def recovery_decision(state: dict, *, healthy: bool, now: float):
    restarts = [x for x in state.get('restarts', []) if now - 3600 < x <= now]
    failures = 0 if healthy else min(int(state.get('failures', 0)) + 1, 3)
    restart = failures >= 3 and len(restarts) < 3
    status = 'healthy' if healthy else 'degraded'
    if restart:
        restarts.append(now)
        failures = 0
        status = 'restarting'
    elif failures >= 3:
        status = 'recovery_limit_reached'
    return {'failures': failures, 'restarts': restarts, 'status': status, 'checked_at': now}, restart


def browser_task(request: dict):
    try:
        result = subprocess.run(['docker', 'exec', '-u', 'worker', '-i', CONTAINER,
            'timeout', '100', 'python', '/app/dev_control/browser_worker/control_task.py'],
            input=json.dumps(request), text=True, capture_output=True, timeout=110)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'status': 'runner_timeout'}
    if result.returncode:
        return {'ok': False, 'status': 'runner_unavailable', 'exit_code': result.returncode}
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {'ok': False, 'status': 'invalid_runner_response'}


def server(request: dict):
    if os.geteuid() != 0:
        raise PermissionError('server entry requires root')
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(LOCK, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'ok': False, 'status': 'busy'}
        operation = request.get('operation')
        if operation == 'watchdog':
            healthy = browser_task({'operation': 'health'}).get('ok') is True
            STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
            path = STATE_DIR / 'watchdog.json'
            previous = json.loads(path.read_text()) if path.exists() else {}
            state, restart = recovery_decision(previous, healthy=healthy, now=time.time())
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(path)
            if restart:
                result = subprocess.run(['docker', 'restart', '-t', '10', CONTAINER],
                                        capture_output=True, timeout=45)
                state['restart_accepted'] = result.returncode == 0
                temporary.write_text(json.dumps(state))
                temporary.replace(path)
            return state
        if operation not in {'health', 'demo', 'avito'}:
            raise ValueError('Unsupported operation')
        result = browser_task(request)
        if operation != 'health':
            STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Last result is owner-only, never a public HTTP endpoint.
            (STATE_DIR / 'last.json').write_text(json.dumps(result, ensure_ascii=False))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', nargs='?', choices=['status', 'demo', 'avito', 'commercial-search', 'watchdog'])
    parser.add_argument('--query')
    parser.add_argument('--server', action='store_true')
    args = parser.parse_args()
    try:
        if args.server:
            request = ({'operation': 'watchdog'} if args.operation == 'watchdog'
                       else json.loads(sys.stdin.buffer.read(8193)))
            result = server(request)
        else:
            operation = args.operation or 'status'
            if operation == 'commercial-search' and args.query is not None:
                parser.error('--query is not configurable for commercial-search')
            request = {'operation': 'health' if operation == 'status' else operation}
            if operation == 'avito':
                request['query'] = args.query or 'кирпич б/у'
            response = subprocess.run(ssh_command(operation), input=json.dumps(request),
                capture_output=True, text=True, timeout=240 if operation == 'commercial-search' else 125)
            if response.returncode == 255 or not response.stdout.strip():
                result = {'ok': False, 'status': 'ssh_unavailable', 'exit_code': response.returncode}
            else:
                result = json.loads(response.stdout)
    except Exception as exc:
        result = {'ok': False, 'status': 'control_error', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('ok') or result.get('status') == 'healthy' else 1


if __name__ == '__main__':
    raise SystemExit(main())
