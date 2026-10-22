#!/usr/bin/env python3
"""Build or install one pinned release, without reset, pull or implicit DB targets."""
import argparse
import ast
from contextlib import contextmanager
import fcntl
import glob
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = '0100_packaging_history_guard'
INTERMEDIATE_REVISION = '0101_manual_brigade_origins'
CANDIDATE_REVISION = '0102_job_candidates'
TARGET_REVISION = '0103_platform_company_features'


def run(args, *, cwd=None, env=None, capture=False):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def git(root, *args):
    return run(['git', '-C', root, *args], capture=True)


def clean_tracked(root):
    return not git(root, 'diff', '--name-only') and not git(root, 'diff', '--cached', '--name-only')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def pack(args):
    root = args.app_root.resolve()
    require(not git(root, 'status', '--porcelain'), 'Commit all changes before packaging')
    target = git(root, 'rev-parse', 'HEAD')
    base = git(root, 'rev-parse', args.base + '^{commit}')
    run(['git', '-C', root, 'merge-base', '--is-ancestor', base, target])
    commits = [{'sha': line[:40], 'subject': line[41:]} for line in git(root, 'log', '--reverse',
               '--format=%H %s', base + '..' + target).splitlines()]
    require(commits, 'There are no commits after the selected baseline')
    revisions = {}
    for file in (root / 'migrations/versions').glob('*.py'):
        constants = {}
        for node in ast.parse(file.read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for name in node.targets:
                    if isinstance(name, ast.Name):
                        constants[name.id] = node.value.value
        if constants.get('revision'):
            revisions[constants['revision']] = constants.get('down_revision')
    heads = set(revisions) - set(revisions.values())
    require(heads == {TARGET_REVISION}
            and revisions.get(INTERMEDIATE_REVISION) == BASE_REVISION
            and revisions[CANDIDATE_REVISION] == INTERMEDIATE_REVISION
            and revisions[TARGET_REVISION] == CANDIDATE_REVISION,
            'Unexpected migration graph; review this release tooling before packaging')
    tracked = git(root, 'ls-files', '-z').split('\0')
    require(not any(Path(name).name == '.env' or name.endswith(('.key', '.pem'))
                    for name in tracked if name), 'Do not package tracked credentials')
    destination = args.output.resolve()
    require(not destination.exists(), 'Output already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stroyka-release-package-') as work:
        package = Path(work) / ('stroyka-unified-' + target[:12])
        package.mkdir()
        run(['git', '-C', root, 'bundle', 'create', package / 'release.bundle', base + '..HEAD'])
        run(['git', '-C', root, 'bundle', 'verify', package / 'release.bundle'])
        for source, name in [(root / 'scripts/unified_release.py', 'install.py'),
                             (root / 'scripts/release_database_check.py', 'release_database_check.py'),
                             (root / 'docs/deployment-retention.md', 'deployment-retention.md'),
                             (root / 'tasks/unified-release-review.md', 'VERIFICATION.ru.md'),
                             (root / 'docs/unified-release.md', 'README.ru.md')]:
            shutil.copyfile(source, package / name)
        manifest = {'formatVersion': 1, 'base': base, 'head': target, 'commits': commits,
                    'databaseBase': BASE_REVISION, 'databaseHead': TARGET_REVISION,
                    'files': {file.name: sha256(file) for file in sorted(package.iterdir())}}
        (package / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
        with tarfile.open(destination, 'w:gz') as archive:
            archive.add(package, arcname=package.name)
    checksum = sha256(destination)
    destination.with_name(destination.name + '.sha256').write_text(f'{checksum}  {destination.name}\n')
    print(json.dumps({'artifact': str(destination), 'sha256': checksum, 'head': target,
                      'commitsAfterBase': len(commits), 'base': base}, indent=2))


def load_package(path):
    manifest = json.loads((path / 'release.json').read_text())
    require(manifest.get('formatVersion') == 1, 'Unsupported package format')
    for field in ('head', 'base'):
        require(re.fullmatch('[0-9a-f]{40}', manifest.get(field, '')), 'Invalid release SHA')
    require(manifest.get('databaseBase') == BASE_REVISION and manifest.get('databaseHead') == TARGET_REVISION,
            'Unexpected release migration target')
    require(set(manifest['files']) == {'release.bundle', 'install.py', 'release_database_check.py',
                                     'deployment-retention.md', 'VERIFICATION.ru.md', 'README.ru.md'},
            'Unexpected package file list')
    for name, expected in manifest['files'].items():
        file = path / name
        require(not file.is_symlink() and sha256(file) == expected, 'Package checksum mismatch: ' + name)
    return manifest


def systemd_environment_file(path):
    """Read systemd.exec EnvironmentFile syntax, never shell-source its contents.

    States follow systemd's parse_env_file_internal: quotes only start in
    pre-value state, quoted values may span lines, and $/backticks stay literal.
    """
    text = path.read_bytes().decode('utf-8')
    require('\0' not in text, 'NUL byte in service EnvironmentFile')
    state, key, value, trailing = 'key_start', [], [], None
    values = {}
    whitespace = ' \t\r\n'

    def save():
        name = ''.join(key).rstrip(whitespace)
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', name):
            values[name] = ''.join(value[:trailing] if state == 'value' and trailing is not None else value)

    for char in text:
        if state == 'key_start':
            if char in '#;':
                state = 'comment'
            elif char not in whitespace:
                key, value, trailing = [char], [], None
                state = 'key'
        elif state == 'comment':
            if char == '\n':
                state = 'key_start'
        elif state == 'key':
            if char == '\n':
                state = 'key_start'
            elif char == '=':
                state = 'value_start'
            else:
                key.append(char)
        elif state in ('value_start', 'value'):
            if char == '\n':
                save()
                state = 'key_start'
            elif char == '\\':
                state, trailing = 'escape', None
            elif state == 'value_start' and char in "'\"":
                state = 'single' if char == "'" else 'double'
            elif state == 'value_start' and char in whitespace:
                continue
            else:
                if char not in whitespace:
                    trailing = None
                elif trailing is None:
                    trailing = len(value)
                value.append(char)
                state = 'value'
        elif state == 'escape':
            if char != '\n':
                value.append(char)
            state = 'value'
        elif state == 'single':
            if char == "'":
                state = 'value_start'
            else:
                value.append(char)
        elif state == 'double':
            if char == '"':
                state = 'value_start'
            elif char == '\\':
                state = 'double_escape'
            else:
                value.append(char)
        elif state == 'double_escape':
            if char in '\\`"$':
                value.append(char)
            elif char != '\n':
                value.extend(('\\', char))
            state = 'double'
    if state not in ('key_start', 'key', 'comment'):
        save()
    return values


def systemd_property(unit, interface, name, signature):
    # D-Bus JSON preserves exact strings and array order, unlike systemctl's
    # human-readable/C-escaped rendering of Environment and EnvironmentFiles.
    payload = json.loads(run(['busctl', '--system', '--json=short', 'get-property',
                             'org.freedesktop.systemd1', unit, interface, name], capture=True))
    require(payload.get('type') == signature and isinstance(payload.get('data'), list),
            'Unexpected systemd property format: ' + name)
    return payload['data']


def runtime_environment(root, service):
    require(shutil.which('busctl'), 'busctl is required to read exact systemd service configuration')
    if '.' not in service:
        service += '.service'
    unit = json.loads(run(['busctl', '--system', '--json=short', 'call', 'org.freedesktop.systemd1',
                          '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                          'GetUnit', 's', service], capture=True))
    require(unit.get('type') == 'o' and len(unit.get('data', [])) == 1,
            'Cannot resolve systemd service')
    unit_path = unit['data'][0]
    interface = 'org.freedesktop.systemd1.Service'
    # Keep process execution settings; root's DB/feature/auth variables must
    # never select a different database or enable a feature for the release.
    env = {key: value for key, value in os.environ.items()
           if key in {'PATH', 'HOME', 'LANG', 'LANGUAGE', 'TZ', 'TMPDIR'} or key.startswith('LC_')}
    passed = systemd_property(unit_path, interface, 'PassEnvironment', 'as')
    if passed:
        manager = systemd_property('/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                                   'Environment', 'as')
        for entry in manager:
            name, separator, value = entry.partition('=')
            if separator and name in passed:
                env[name] = value
    for entry in systemd_property(unit_path, interface, 'Environment', 'as'):
        name, separator, value = entry.partition('=')
        if separator:
            env[name] = value
    for pattern, optional in systemd_property(unit_path, interface, 'EnvironmentFiles', 'a(sb)'):
        require(isinstance(pattern, str) and pattern.startswith('/') and isinstance(optional, bool),
                'Invalid systemd EnvironmentFile definition')
        paths = sorted(glob.glob(pattern), key=os.fsencode) if glob.has_magic(pattern) else [pattern]
        require(paths or optional, 'Required service EnvironmentFile pattern has no matches')
        for path in paths:
            try:
                env.update(systemd_environment_file(Path(path)))
            except (OSError, UnicodeError):
                require(optional, 'Cannot read required service EnvironmentFile')
    for entry in systemd_property(unit_path, interface, 'UnsetEnvironment', 'as'):
        name, separator, value = entry.partition('=')
        if not separator or env.get(name) == value:
            env.pop(name, None)
    # Match backend.config.load_env_file: existing runtime values win; this
    # fallback is optional when the service already supplies explicit settings.
    env_file = root / 'backend/.env'
    for raw in env_file.read_text().splitlines() if env_file.is_file() else []:
        line = raw.strip()
        if line and not line.startswith('#') and '=' in line:
            name, value = line.split('=', 1)
            env.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    return env


def frontend_service_environment(env):
    # Only feature settings enter resolver argv; credentials stay in memory.
    return shlex.join(f'{name}={value}' for name, value in sorted(env.items())
                      if name.startswith(('WAREHOUSE_', 'OWNED_DISTRIBUTION_', 'INTERCOMPANY_WAREHOUSE_',
                                          'SUPPLIER_', 'WORK_', 'PARTICIPANT_', 'ASSIGNMENT_DAILY_DRAFT_'))
                      and name.endswith(('_ENABLED', '_COMPANY_IDS')))


def database_module(package):
    spec = importlib.util.spec_from_file_location('release_database_check', package / 'release_database_check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def health(base, head):
    with urlopen(Request(base.rstrip('/') + '/health', headers={'Cache-Control': 'no-cache'}), timeout=10) as response:
        payload = json.load(response)
    require(payload.get('ok') is True and payload.get('db', {}).get('ok') is True
            and payload.get('version') == head[:12], 'Runtime SHA or database health mismatch')


def manifest_files(build):
    manifest = json.loads((build / 'asset-manifest.json').read_text())
    selected = set(manifest.get('files', {}).values()) | set(manifest.get('entrypoints', []))
    paths = []
    for name in selected:
        require(isinstance(name, str) and not urlsplit(name).scheme and not name.startswith('//'),
                'Manifest contains a remote asset')
        relative = Path(name.lstrip('/'))
        require(relative.parts and '..' not in relative.parts, 'Invalid manifest asset path')
        require(not any((build / Path(*relative.parts[:index])).is_symlink()
                        for index in range(1, len(relative.parts) + 1)), 'Symlink in manifest asset path')
        file = build / relative
        require(file.is_file() and not file.is_symlink(), 'Manifest asset missing or symlinked')
        paths.append(relative)
    require(paths, 'Empty frontend manifest')
    return paths


def backup_frontend(build, destination):
    selected = set(manifest_files(build))
    selected |= {file.relative_to(build) for file in build.rglob('*')
                 if file.is_file() and file.relative_to(build).parts[0] != 'static'}
    destination.mkdir()
    for relative in selected:
        source = build / relative
        require(not source.is_symlink(), 'Frontend backup contains a symlink')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def database_backup(module, env, destination):
    config = module.connection_settings(env)
    child = dict(env, PGHOST=config['host'], PGPORT=str(config['port']), PGUSER=config['user'],
                 PGDATABASE=config['dbname'], PGPASSWORD=config['password'])
    run(['pg_dump', '--format=custom', '--file', destination], env=child)
    require(destination.stat().st_size > 0, 'Database backup is empty')
    # Validate that the dump can be read. A restore rehearsal is a separate check.
    run(['pg_restore', '--list', destination], env=child, capture=True)


def document_worker_probe(root, env):
    # Exercise the existing isolated worker, without database or business records.
    probe = '''
import io, zipfile
from backend.features.supplier_deal_parties.contract_document import extract_document_text
data = io.BytesIO()
with zipfile.ZipFile(data, 'w') as archive:
    archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Проверка выпуска</w:t></w:r></w:p></w:body></w:document>')
assert extract_document_text(data.getvalue(), '.docx') == 'Проверка выпуска'
'''
    run([os.sys.executable, '-c', probe], cwd=root, env=env)


def preflight(args, package, manifest, env):
    root = args.app_root.resolve()
    require(git(root, 'branch', '--show-current') == 'main', 'Installed checkout must be on main')
    require(clean_tracked(root),
            'Tracked server files have local changes; nothing will be reset')
    current = git(root, 'rev-parse', 'HEAD')
    known = {manifest['base']} | {entry['sha'] for entry in manifest['commits']}
    require(current in known, 'Installed SHA is outside this package; merge/review server changes first')
    run(['git', '-C', root, 'bundle', 'verify', package / 'release.bundle'])
    require(git(root, 'bundle', 'list-heads', package / 'release.bundle') == manifest['head'] + ' HEAD',
            'Bundle head differs from release manifest')
    public = urlsplit(args.public_url)
    require(public.scheme == 'https' and public.hostname and not public.username and not public.query
            and not public.fragment and public.path in ('', '/'), 'Use the exact HTTPS site origin')
    run(['systemctl', 'is-active', '--quiet', args.service])
    run(['systemctl', 'is-active', '--quiet', 'nginx'])
    run(['nginx', '-t'])
    health('http://127.0.0.1:8001', current)
    health(args.public_url, current)
    manifest_files(root / 'build')
    module = database_module(package)
    report = module.inspect_database(env)
    require(report['status'] == 'ready', 'Database preflight blocked: ' + ', '.join(report['blockers']))
    document_worker_probe(root, env)
    return current, module, report


@contextmanager
def deployment_lock(path):
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def install(args):
    package = Path(__file__).resolve().parent
    manifest = load_package(package)
    root = args.app_root.resolve()
    env = runtime_environment(root, args.service)
    if args.action == 'db-check':
        report = database_module(package).inspect_database(env)
        print(json.dumps(report, indent=2))
        require(report['status'] == 'ready', 'Database preflight is blocked; see the report above')
        return
    if args.action == 'check':
        current, _module, report = preflight(args, package, manifest, env)
        print(json.dumps({'status': 'ready', 'current': current, 'target': manifest['head'],
                          'database': report, 'changesMade': False}, indent=2))
        return
    require(re.fullmatch('[0-9a-f]{40}', args.expect_current or ''), '--expect-current requires the full checked SHA')
    with deployment_lock(Path('/var/lock/stroyka-deploy.lock')):
        current, module, report = preflight(args, package, manifest, env)
        require(current == args.expect_current, 'Installed SHA changed after review')
        require(current != manifest['head'], 'Target is already installed; do not repeat a release')
        for program in ('pg_dump', 'pg_restore', 'npm', 'rsync'):
            require(shutil.which(program), 'Required program missing: ' + program)
        require(hasattr(tarfile, 'data_filter'), 'Update Python for safe tar extraction before installing')
        run([os.sys.executable, '-c', 'import alembic, psycopg2, sqlalchemy'], env=env)
        stage = Path(tempfile.mkdtemp(prefix='stroyka-unified-', dir='/root'))
        stage.chmod(0o700)
        (stage / 'commit-before.txt').write_text(current + '\n')
        (stage / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (stage / 'database-before.json').write_text(json.dumps(report, indent=2) + '\n')
        worker_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'stroyka-agent-job-worker.service']).returncode == 0
        switched = migrated = services_stopped = False
        try:
            database_backup(module, env, stage / 'database-before.dump')
            backup_frontend(root / 'build', stage / 'frontend-before')
            run(['git', '-C', root, 'fetch', '--no-tags', str(package / 'release.bundle'),
                 'HEAD:refs/stroyka/releases/' + manifest['head']])
            run(['git', '-C', root, 'merge-base', '--is-ancestor', current, manifest['head']])
            source = stage / 'source'
            source.mkdir()
            archive = stage / 'source.tar'
            run(['git', '-C', root, 'archive', '--format=tar', '--output', archive, manifest['head']])
            with tarfile.open(archive) as tree:
                tree.extractall(source, filter='data')
            archive.unlink()
            service_env = frontend_service_environment(env)
            build_env = run(['bash', source / 'scripts/resolve-frontend-build-env.sh', service_env, ''],
                            cwd=source, env=env, capture=True)
            frontend_env = dict(env, BUILD_PATH=str(stage / 'frontend'))
            frontend_env.update(item.split('=', 1) for item in build_env.splitlines() if item)
            run(['npm', 'ci'], cwd=source, env=env)
            run(['npm', 'run', 'build'], cwd=source, env=frontend_env)
            subprocess.run([os.sys.executable, str(source / 'scripts/verify-frontend-feature-build.py'),
                            str(stage / 'frontend')], cwd=source, env=env, input=build_env + '\n', text=True, check=True)
            manifest_files(stage / 'frontend')
            # Install only after backup and build pass. No reset, clean, pull or flags edit.
            require(git(root, 'rev-parse', 'HEAD') == current, 'Installed code changed during the build')
            require(clean_tracked(root), 'Tracked files changed during the build; preserve and review them')
            services_stopped = True
            if worker_active:
                run(['systemctl', 'stop', 'stroyka-agent-job-worker.service'])
            run(['systemctl', 'stop', args.service])
            run(['git', '-C', root, 'merge', '--ff-only', manifest['head']])
            switched = True
            require(clean_tracked(root), 'Installed working tree differs from the pinned release')
            migration_env = dict(env, PGOPTIONS='-c lock_timeout=5000 -c statement_timeout=60000')
            run([os.sys.executable, '-m', 'alembic', 'upgrade', TARGET_REVISION], cwd=root, env=migration_env)
            migrated = True
            after = module.inspect_database(env, require_target=True)
            require(after['status'] == 'ready', 'Post-migration schema check failed')
            (stage / 'database-after.json').write_text(json.dumps(after, indent=2) + '\n')
            run([os.sys.executable, '-c', 'import backend.main'], cwd=root, env=env)
            run(['systemctl', 'restart', args.service])
            if worker_active:
                run(['systemctl', 'restart', 'stroyka-agent-job-worker.service'])
                run(['systemctl', 'is-active', '--quiet', 'stroyka-agent-job-worker.service'])
            run(['bash', root / 'scripts/publish-frontend.sh', stage / 'frontend', root / 'build'], cwd=root, env=env)
            for attempt in range(30):
                try:
                    health('http://127.0.0.1:8001', manifest['head'])
                    health(args.public_url, manifest['head'])
                    break
                except Exception:
                    if attempt == 29:
                        raise
                    time.sleep(1)
            for relative in manifest_files(stage / 'frontend') + [Path('asset-manifest.json'), Path('index.html')]:
                require(sha256(stage / 'frontend' / relative) == sha256(root / 'build' / relative),
                        'Published frontend hash mismatch')
            request = Request(args.public_url.rstrip('/') + '/asset-manifest.json', headers={'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=15) as response:
                require(json.load(response) == json.loads((root / 'build/asset-manifest.json').read_text()),
                        'Public frontend manifest differs')
            public_manifest = json.loads((root / 'build/asset-manifest.json').read_text())
            for entry in public_manifest.get('entrypoints', []):
                request = Request(args.public_url.rstrip('/') + '/' + entry.lstrip('/'),
                                  headers={'Cache-Control': 'no-cache'})
                with urlopen(request, timeout=20) as response:
                    require(hashlib.sha256(response.read()).hexdigest() == sha256(root / 'build' / entry.lstrip('/')),
                            'Public frontend entrypoint hash mismatch')
            evidence = {'head': manifest['head'], 'before': current, 'status': 'installed_awaiting_browser',
                        'checks': {'backend': True, 'database': True, 'frontend': True, 'browser': False}}
            require(git(root, 'rev-parse', 'HEAD') == manifest['head'] and clean_tracked(root),
                    'Installed code changed during release verification')
            (stage / 'installed.json').write_text(json.dumps(evidence, indent=2) + '\n')
            # Keep only rollback material until real authenticated browser acceptance.
            shutil.rmtree(source)
            shutil.rmtree(stage / 'frontend')
            print(json.dumps({**evidence, 'backup': str(stage), 'complete': False}, indent=2))
        except BaseException:
            failure = {'head': manifest['head'], 'before': current, 'codeSwitched': switched,
                       'migrationCommandSucceeded': migrated, 'status': 'failed', 'automaticDowngrade': False}
            (stage / 'failed.json').write_text(json.dumps(failure, indent=2) + '\n')
            if services_stopped and not switched:
                # No code or schema changed; bring the original processes back.
                subprocess.run(['systemctl', 'start', args.service])
                if worker_active:
                    subprocess.run(['systemctl', 'start', 'stroyka-agent-job-worker.service'])
            print('STOP: release incomplete; rollback material retained at ' + str(stage), file=os.sys.stderr)
            print('Do not downgrade the database or blindly restore old access code; inspect the failure.', file=os.sys.stderr)
            raise


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    build = commands.add_parser('pack')
    build.add_argument('--app-root', type=Path, default=ROOT)
    build.add_argument('--base', required=True)
    build.add_argument('--output', required=True, type=Path)
    for action in ('check', 'apply'):
        command = commands.add_parser(action)
        command.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
        command.add_argument('--service', default='stroyka')
        command.add_argument('--public-url', required=True)
        command.add_argument('--expect-current')
    database = commands.add_parser('db-check')
    database.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    database.add_argument('--service', default='stroyka')
    args = parser.parse_args()
    try:
        pack(args) if args.action == 'pack' else install(args)
    except Exception as error:
        # DB/client errors may contain credentials. Persist no raw exception text.
        if isinstance(error, ValueError):
            print('STOP: ' + str(error), file=os.sys.stderr)
        else:
            print('STOP: command failed (' + type(error).__name__ + '); inspect server logs locally.', file=os.sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
