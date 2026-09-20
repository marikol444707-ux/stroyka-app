#!/usr/bin/env python3
"""Delete completed deployment staging only after verifying the running release."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path('/var/www/stroyka-app')

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()

def referenced(path):
    needle = str(path).encode()
    for base in ('/etc/systemd/system', '/usr/lib/systemd/system', '/lib/systemd/system', '/etc/nginx', '/etc/cron.d', '/var/spool/cron'):
        for file in Path(base).rglob('*'):
            if file.is_file() and needle in file.read_bytes():
                return True
    for proc in Path('/proc').glob('[0-9]*'):
        for file in [proc/'cwd', proc/'exe', *list((proc/'fd').glob('*'))]:
            try:
                target = os.readlink(file)
                if target == str(path) or target.startswith(str(path)+'/'):
                    return True
            except OSError:
                pass
        try:
            if needle in (proc/'cmdline').read_bytes():
                return True
        except OSError:
            pass
    return False

def verification_passed(path, head):
    try:
        evidence = json.loads((path/'verified.json').read_text())
        return (evidence.get('head') == head and
                all(evidence.get('checks', {}).get(key) is True
                    for key in ('backend', 'database', 'frontend', 'browser')))
    except (OSError, ValueError, AttributeError):
        return False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--all-completed', action='store_true')
    args = parser.parse_args()
    if not args.all_completed:
        parser.error('--all-completed is required')
    with open('/var/lock/stroyka-deploy.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'applied':False,'reason':'deployment_in_progress'}))
            return
        head = git('rev-parse', 'HEAD')
        with urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5) as response:
            health = json.load(response)
        assert health.get('ok') and health.get('db', {}).get('ok') and health.get('version') == head[:12]
        selected, skipped = [], []
        for path in sorted(Path('/root').glob('stroyka-*')):
            marker = path/'deployed.json'
            if not path.is_dir() or path.is_symlink() or not marker.is_file():
                continue
            report = json.loads(marker.read_text())
            sha = report.get('head', '')
            if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
                skipped.append(str(path)); continue
            if not verification_passed(path, sha):
                skipped.append(str(path)); continue
            ancestor = subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', sha, head], capture_output=True)
            if ancestor.returncode or referenced(path):
                skipped.append(str(path)); continue
            selected.append((path, {**report, 'verification':json.loads((path/'verified.json').read_text())}))
        # Keep only small deployment receipts, never DB/env/frontend copies.
        if args.apply:
            receipts = Path('/var/log/stroyka-release-receipts')
            receipts.mkdir(mode=0o700, exist_ok=True)
            for path, report in selected:
                (receipts/(path.name+'.json')).write_text(json.dumps(report, indent=2)+'\n')
                shutil.rmtree(path)
        print(json.dumps({'head':head, 'applied':args.apply, 'selected':[str(p) for p,_ in selected], 'skipped':skipped}))

if __name__ == '__main__':
    main()
