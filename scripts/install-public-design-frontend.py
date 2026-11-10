#!/usr/bin/env python3
"""Publish a reviewed frontend-only commit over an exact, clean production base."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import urlopen, Request


def run(*args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/var/www/stroyka-app')
    os.chdir(root)
    spec = importlib.util.spec_from_file_location('release', root / 'scripts/unified_release.py')
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with release.deployment_lock(Path('/var/lock/stroyka-deploy.lock')):
        require(run('git', 'rev-parse', 'HEAD') == args.base, 'Production base changed')
        require(not run('git', 'diff', '--name-only') and not run('git', 'diff', '--cached', '--name-only'), 'Tracked server edits exist')
        require(run('git', 'rev-parse', args.target + '^') == args.base, 'Expected one reviewed frontend commit')
        changed = run('git', 'diff', '--name-only', args.base, args.target).splitlines()
        allowed = ('public/', 'src/features/public-site/', 'src/components/PublicSitePage.', 'scripts/', 'docs/')
        require(all(name.startswith(allowed) for name in changed), 'Unexpected release scope')
        build = args.build.resolve()
        release.manifest_files(build)
        require(json.loads((build / 'frontend-release.json').read_text())['commit'] == args.target, 'Build commit mismatch')
        # Exact production modes must survive the redesign, including flags not
        # covered by the shared feature resolver.
        def modes(path):
            return sorted(re.findall(r'<meta name="stroyka-[^>]+', path.read_text()))
        require(modes(build / 'index.html') == modes(root / 'build/index.html'), 'Production feature metadata differs')
        backup = Path(tempfile.mkdtemp(prefix='stroyka-public-design-', dir='/root'))
        os.chmod(backup, 0o700)
        release.backup_frontend(root / 'build', backup / 'frontend')
        (backup / 'release.json').write_text(json.dumps({'before': args.base, 'target': args.target}, indent=2))
        print('Backup:', backup, flush=True)
        subprocess.run(['git', 'merge', '--ff-only', args.target], check=True)
        try:
            subprocess.run(['bash', str(root / 'scripts/publish-frontend.sh'), str(build), str(root / 'build')], check=True)
            for path in ['index.html', 'asset-manifest.json', 'frontend-release.json']:
                url = 'https://stroyka26.pro/' + ('' if path == 'index.html' else path) + '?release=' + args.target
                with urlopen(Request(url, headers={'Cache-Control': 'no-cache'}), timeout=30) as response:
                    data = response.read()
                require(hashlib.sha256(data).digest() == hashlib.sha256((build / path).read_bytes()).digest(), 'Published file mismatch: ' + path)
            with urlopen('https://stroyka26.pro/health', timeout=20) as response:
                health = json.load(response)
            require(health.get('ok') and health.get('db', {}).get('ok'), 'Backend health failed')
        except Exception:
            subprocess.run(['bash', str(root / 'scripts/publish-frontend.sh'), str(backup / 'frontend'), str(root / 'build')], check=True)
            if run('git', 'rev-parse', 'HEAD') == args.target and not run('git', 'diff', '--name-only') and not run('git', 'diff', '--cached', '--name-only'):
                subprocess.run(['git', 'reset', '--keep', args.base], check=True)
            raise
        print(json.dumps({'status': 'published_awaiting_browser', 'frontendCommit': args.target, 'backup': str(backup), 'backendRestarted': False, 'databaseChanged': False}))


if __name__ == '__main__':
    main()
