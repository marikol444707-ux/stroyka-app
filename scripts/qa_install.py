"""QA-only implementation used by unified_release. No work at import time.

Default CLI is a plan. Execution requires an exact manifest, QA-host checks,
fresh interactive confirmation, and the recorded host venv. No production mode.
"""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
from urllib.request import urlopen

from scripts.qa_host_runtime import PYTHON_PATH, DIRECT_PINS
from scripts.qa_topology import TOPOLOGY, FRONTEND_VOLUME, validate_topology

CANDIDATE = 'stroyka-qa-backend-candidate'
DB = 'stroyka-qa-db'
ROOT = Path('/opt/stroyka-jev-qa-7e89d73')
GATEWAY = 'stroyka-qa-gateway'
WRITERS = ('stroyka-qa-backend', CANDIDATE, 'stroyka-qa-frontend', GATEWAY)
TARGET = '0109_legacy_payment_requests'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_manifest(m):
    require(set(m) == {'qa_only', 'database', 'container', 'source_sha', 'target_sha',
                       'candidate_root', 'frontend_root', 'discard_test_data',
                       'maintenance_database'}, 'Unexpected QA manifest fields')
    require(m['qa_only'] is True and m['discard_test_data'] is True
            and m['maintenance_database'] == 'postgres', 'Explicit QA scope required')
    require(m['database'] == 'stroyka_qa' and m['container'] == DB
            and m['candidate_root'] == str(ROOT) and m['frontend_root'] == FRONTEND_VOLUME,
            'QA target mismatch')
    require(all(isinstance(m[k], str) and re.fullmatch('[0-9a-f]{40}', m[k])
                for k in ('source_sha', 'target_sha')), 'Exact SHAs required')
    return hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def confirmation(m):
    return 'STOP QA BACKENDS/FRONTEND/GATEWAY; SWITCH CANDIDATE AND FRONTEND; SWITCH GENERAL /api/* FROM MAIN TO CANDIDATE; PRESERVE EXACT IDENTITY CANARY; UPDATE QA STATIC ROOT; CLOSE QA CONNECTIONS VIA postgres; TERMINATE OTHER stroyka_qa SESSIONS; REPLACE stroyka_qa ON stroyka-qa-db WITH ' + m['target_sha']


def plan(m):
    return {'manifest_sha256': validate_manifest(m), 'execution': False,
            'stages': ['deliver_target_objects', 'readonly_preflight', 'isolated_frontend_build',
                       'repeat_preflight', 'fresh_confirmation', 'stop_qa_writers',
                       'exclusive_schema_and_migrations', 'switch_candidate', 'publish_frontend', 'start_candidate',
                       'check_health_and_frontend', 'open_gateway'],
            'routing_change': {'general_api': '/api/*', 'from': 'stroyka-qa-backend',
                               'to': CANDIDATE,
                               'preserve_exact_canary': '/api/users/qa-readonly-context/identity',
                               'static_root': '/srv/app/build'},
            'old_backend_remains_stopped': True, 'automatic_rollback': False}


def check_version_environment(values, target):
    configured = (values.get('APP_VERSION') or values.get('GIT_COMMIT') or '').strip()
    require(not configured or (re.fullmatch(r'[0-9a-f]{12}|[0-9a-f]{40}', configured) and configured[:12] == target[:12]),
            'Candidate version environment pins another version; no container reconfiguration is performed')


def read_config_text(path):
    # Preserve existing line endings, including the exact canary block.
    with Path(path).open('r', encoding='utf-8', newline='') as source:
        return source.read()


def routing_update(static, gateway, ports):
    from scripts.qa_routing import validate_static
    validate_static(static)
    roots = re.findall(r'(?m)^([ \t]*root\s+\*\s+)(/srv/app(?:/build)?)([ \t]*\r?)$', static)
    require(len(roots) == 1, 'Static root is ambiguous or outside reviewed QA volume')
    new_static = re.sub(r'(?m)^([ \t]*root\s+\*\s+)/srv/app(?:/build)?([ \t]*\r?)$',
                        r'\g<1>/srv/app/build\2', static)
    matches = [key.split('/')[0] for key, bindings in ports.items()
               if key.endswith('/tcp') and any(b.get('HostPort') == '8002' for b in (bindings or []))]
    require(len(matches) == 1 and matches[0].isdigit(), 'Candidate port mapping ambiguous')
    from scripts.qa_routing import adapt_dual_gateway
    new_gateway = adapt_dual_gateway(gateway, matches[0])
    return new_static, new_gateway


class LocalDriver:
    """Actual host operations; instantiated only after explicit execution selection."""
    def __init__(self):
        self.environment = None
        self.stage = None
        self.maintenance_stage = None
        self.config_updates = {}
        self.frontend_stage = None
        self.database_evidence = None
        self.frontend_environment = {}

    def run(self, args, *, cwd=None, env=None, binary=False, stdin=None):
        try:
            r = subprocess.run(args, cwd=cwd, env=env, input=stdin,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=not binary, timeout=900, check=True)
            return r.stdout
        except Exception:
            raise RuntimeError('QA command failed; no raw output disclosed') from None

    def inspect(self, name, expression):
        return json.loads(self.run(['docker', 'inspect', '--format', expression, name]))

    def git(self, *args):
        git_env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        git_env.update(GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/bin/false',
                       SSH_ASKPASS='/bin/false', GIT_OPTIONAL_LOCKS='0')
        return self.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                         '-C', str(ROOT), *args], env=git_env).strip()

    def deliver_target(self, m):
        # Git objects only: no checkout, remote-tracking ref change or force.
        require(socket.gethostname().lower().rstrip('.') in
                ('stroyka-dev-agent', 'stroyka-dev-agent.local'), 'Wrong host')
        keys = self.git('config', '--name-only', '--list').splitlines()
        require(not any(k.startswith('filter.') or (k.startswith('url.') and k.lower().endswith(('insteadof', 'pushinsteadof'))) for k in keys), 'Configured Git filters or URL rewrites require review')
        require(self.git('rev-parse', 'HEAD') == m['source_sha'] and not self.git('status', '--porcelain'),
                'Candidate changed or dirty')
        tooling = Path(__file__).resolve().parents[1]
        require(self.run(['git', '-C', str(tooling), 'rev-parse', 'HEAD']).strip() == m['target_sha'],
                'Tooling must be the exact target version')
        args = ['fetch', '--no-tags', '--no-recurse-submodules']
        if self.git('rev-parse', '--is-shallow-repository') == 'true':
            args.append('--unshallow')
        # Fixed official source; no credential configuration or unsafe protocol.
        self.git('-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
                 '-c', 'http.followRedirects=false', *args,
                 'https://github.com/marikol444707-ux/stroyka-app.git', m['target_sha'])
        require(self.git('rev-parse', 'FETCH_HEAD^{commit}') == m['target_sha'], 'Delivered target mismatch')
        require(self.git('rev-parse', 'HEAD') == m['source_sha'] and not self.git('status', '--porcelain'),
                'Delivery unexpectedly changed worktree')

    def selected_env(self, container, prefix):
        fmt = ('{{range .Config.Env}}{{if and (ge (len .) '+str(len(prefix))+
               ') (eq (slice . 0 '+str(len(prefix))+') "'+prefix+
               '")}}{{json .}}{{println}}{{end}}{{end}}')
        result = {}
        for line in self.run(['docker', 'inspect', '--format', fmt, container]).splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            key, sep, content = value.partition('=')
            require(sep and key not in result, 'Ambiguous environment configuration')
            result[key] = content
        return result

    def database_preflight(self, m):
        tooling = str(Path(__file__).resolve().parents[1])
        code = ('import sys,os,json; sys.path.insert(0,' + repr(tooling) + '); '
                'from scripts.qa_maintenance import run; '
                'print(json.dumps(run(json.load(sys.stdin),os.environ)))')
        payload = {'action': 'preflight', 'maintenance_database': m['maintenance_database'],
                   'root': str(ROOT), 'schema_root': tooling}
        return json.loads(self.run([PYTHON_PATH, '-I', '-c', code], env=self.environment,
                                  stdin=json.dumps(payload)))

    def preflight(self, m):
        tooling = str(Path(__file__).resolve().parents[1])
        require(self.run(['git', '-C', tooling, 'rev-parse', 'HEAD']).strip() == m['target_sha']
                and not self.run(['git', '-c', 'core.fsmonitor=false', '-C', tooling, 'status', '--porcelain']).strip(),
                'Tooling changed since delivery')
        require(socket.gethostname().lower().rstrip('.') in
                ('stroyka-dev-agent', 'stroyka-dev-agent.local'), 'Wrong host')
        observed = {n: {'image': self.inspect(n, '{{json .Image}}'),
                       'workdir': self.inspect(n, '{{json .Config.WorkingDir}}'),
                       'mounts': self.inspect(n, '{{json .Mounts}}')} for n in TOPOLOGY}
        validate_topology(observed)
        require(self.git('rev-parse', 'HEAD') == m['source_sha'], 'Source changed')
        require(not self.git('status', '--porcelain'), 'Candidate checkout is not clean')
        require(self.git('rev-parse', m['target_sha']+'^{commit}') == m['target_sha'],
                'Target commit unavailable locally; no fetch is performed')
        self.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor',
                  '012c9984dabd2e60ab8983f233fb2e8acf9b4703', m['target_sha']])
        from backend.bootstrap_schema import LEGACY_SCHEMA_BATCH
        target_tree = ast.parse(self.git('show', m['target_sha']+':backend/bootstrap_schema.py'))
        assignment = next(n for n in target_tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'LEGACY_STEPS' for t in n.targets))
        require(''.join(sql for _, sql in ast.literal_eval(assignment.value)) == LEGACY_SCHEMA_BATCH,
                'Target base schema differs from reviewed tooling')
        # Preserve immutable/pinned connection scope; secrets stay in memory.
        values = {}
        for key in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'):
            prefix = key + '='
            fmt = ('{{range .Config.Env}}{{if and (ge (len .) '+str(len(prefix))+
                   ') (eq (slice . 0 '+str(len(prefix))+') "'+prefix+
                   '")}}{{json .}}{{end}}{{end}}')
            value = self.inspect(CANDIDATE, fmt)
            require(isinstance(value, str) and value.startswith(prefix), 'Explicit DB configuration missing')
            values[key] = value[len(prefix):]
        require((values['DB_HOST'], values['DB_PORT'], values['DB_NAME']) ==
                (DB, '5432', 'stroyka_qa'), 'Unexpected DB mapping')
        networks = self.inspect(DB, '{{json .NetworkSettings.Networks}}')
        import ipaddress
        values['DB_HOST'] = str(ipaddress.ip_address(networks['stroyka-qa-net']['IPAddress']))
        self.environment = dict(values, PATH='/usr/bin:/bin',
            PGOPTIONS='-c lock_timeout=5000 -c statement_timeout=120000')
        # Third-party imports only. No backend/db/config/main imports.
        check = ('import importlib.metadata as m,json; pins=json.loads('+repr(json.dumps(DIRECT_PINS))+'); '
                 'assert all(m.version(k)==v for k,v in pins.items()); '
                 'import psycopg2,alembic,sqlalchemy,fastapi,pydantic')
        self.run([PYTHON_PATH, '-I', '-c', check], env=self.environment)
        # Verify known QA frontend routing before permitting any deletion.
        static = read_config_text('/tmp/stroyka-qa-static.Caddyfile')
        gateway = read_config_text('/opt/stroyka-qa-gateway/Caddyfile')
        ports = self.inspect(CANDIDATE, '{{json .NetworkSettings.Ports}}')
        new_static, new_gateway = routing_update(static, gateway, ports)
        self.config_updates = {
            '/tmp/stroyka-qa-static.Caddyfile': (static, new_static),
            '/opt/stroyka-qa-gateway/Caddyfile': (gateway, new_gateway)}
        require(all(not Path(path).is_symlink() for path in self.config_updates), 'Configuration symlink')
        versions = {}
        for key in ('APP_VERSION', 'GIT_COMMIT'):
            versions.update(self.selected_env(CANDIDATE, key + '='))
        check_version_environment(versions, m['target_sha'])
        require(not (ROOT / 'backend/.env').exists(), 'Candidate dotenv requires explicit version/config review')
        from scripts.qa_frontend_stage import build_environment
        self.frontend_environment = self.selected_env('stroyka-qa-frontend', 'REACT_APP_')
        build_environment(self.frontend_environment)
        require(not any((Path(FRONTEND_VOLUME) / name).exists() for name in
                        ('.env', '.env.local', '.env.production', '.env.production.local')),
                'Existing frontend dotenv requires explicit build-config review')
        self.database_evidence = self.database_preflight(m)
        return {'database': self.database_evidence, 'version_env': versions,
                'frontend_env': self.frontend_environment, 'topology': observed, 'running': {name: self.inspect(name, '{{json .State.Running}}')
                for name in (*WRITERS, 'stroyka-qa-static')}, 'config_sha256': {
            'static': hashlib.sha256(static.encode()).hexdigest(),
            'gateway': hashlib.sha256(gateway.encode()).hexdigest()}}

    def stop(self):
        self.run(['docker', 'stop', *WRITERS])
        require(all(self.inspect(n, '{{json .State.Running}}') is False for n in WRITERS),
                'QA writers still running')

    def switch(self, m):
        require(self.git('rev-parse', 'HEAD') == m['source_sha'] and not self.git('status', '--porcelain'),
                'Candidate changed during confirmation')
        self.git('checkout', '--detach', m['target_sha'])

    def record_maintenance_intent(self, m, evidence):
        from scripts.qa_maintenance import Journal
        self.maintenance_stage = Path(tempfile.mkdtemp(prefix='stroyka-qa-maintenance-', dir='/opt'))
        journal = Journal(self.maintenance_stage / 'intent.jsonl')
        try:
            journal.record(phase='confirmed_before_container_or_checkout_changes',
                           manifest=m, original=evidence, frontend_staging=str(self.frontend_stage.host),
                           frontend_hashes=self.frontend_stage.hashes)
        finally:
            journal.close()
        print('QA maintenance journal: ' + str(self.maintenance_stage))

    def prepare_database(self, m):
        # One child owns both connections; retain its private recovery journal.
        require(self.maintenance_stage is not None, 'Durable maintenance intent required')
        stage = self.maintenance_stage
        payload = {'confirmed_scope': 'qa_connection_gate_and_session_termination',
                   'maintenance_database': m['maintenance_database'],
                   'root': str(ROOT), 'target_root': str(Path(__file__).resolve().parents[1]),
                   'journal': str(stage / 'maintenance.jsonl'),
                   'expected_database': self.database_evidence}
        tooling = str(Path(__file__).resolve().parents[1])
        code = ('import sys,os,json; sys.path.insert(0,' + repr(tooling) + '); '
                'from scripts.qa_maintenance import run; '
                'run(json.load(sys.stdin),os.environ)')
        self.run([PYTHON_PATH, '-I', '-c', code], env=self.environment,
                 stdin=json.dumps(payload))

    def prepare_frontend(self, m):
        from scripts.qa_frontend_stage import FrontendStage
        self.frontend_stage = FrontendStage(self)
        raw = self.run(['git', '-C', str(ROOT), 'archive', m['target_sha'],
                        'src', 'public', 'package.json', 'package-lock.json', 'scripts'], binary=True)
        return self.frontend_stage.prepare(raw, self.frontend_environment)

    def verify_frontend(self):
        require(self.frontend_stage is not None, 'Frontend not prepared')
        self.frontend_stage.verify()

    def discard_preparation(self):
        if self.frontend_stage is not None:
            self.frontend_stage.discard_unaccepted()

    def accept_preparation(self):
        self.verify_frontend()
        self.frontend_stage.accepted = True

    def frontend(self, m):
        # Publication only, after acceptance and QA writer stop. No npm here.
        self.verify_frontend()
        volume = Path(FRONTEND_VOLUME)
        require(not volume.is_symlink(), 'Frontend root symlink')
        require(self.inspect('stroyka-qa-frontend', '{{json .State.Running}}') is False,
                'Frontend writer remains active')
        destination = Path(tempfile.mkdtemp(prefix='qa-publish-', dir=volume))
        shutil.copytree(self.frontend_stage.host / 'build', destination / 'build')
        from scripts.qa_frontend_stage import digest
        require(digest(destination / 'build') == self.frontend_stage.hashes, 'Published copy changed')
        published = volume / 'build'
        require(not published.is_symlink(), 'Published build symlink')
        if published.exists():
            os.replace(published, destination / 'frontend-before')
        os.replace(destination / 'build', published)
        require(digest(published) == self.frontend_stage.hashes, 'Published assets mismatch')
        self.stage = destination

    def start_and_check(self, m):
        self.run(['docker', 'start', CANDIDATE])
        for attempt in range(30):
            try:
                with urlopen('http://127.0.0.1:8002/health', timeout=5) as r:
                    value = json.load(r)
                require(value.get('ok') is True and value.get('db', {}).get('ok') is True
                        and value.get('version') == m['target_sha'][:12], 'QA health/version mismatch')
                break
            except Exception:
                if attempt == 29:
                    raise RuntimeError('QA health/version check failed') from None
                time.sleep(1)
        config_backup = Path(tempfile.mkdtemp(prefix='stroyka-qa-config-before-', dir='/opt'))
        config_backup.chmod(0o700)
        # Keep bind-mounted inodes: replace contents only after backup and exact
        # before comparison. Never print Caddy contents or certificate material.
        for i, (name, (before, after)) in enumerate(self.config_updates.items()):
            path = Path(name)
            require(not path.is_symlink() and read_config_text(path) == before, 'QA config changed')
            saved = config_backup / str(i)
            saved.write_text(before)
            saved.chmod(0o600)
        self.run(['docker', 'stop', 'stroyka-qa-static'])
        for name, (_, after) in self.config_updates.items():
            Path(name).write_text(after)
        self.run(['docker', 'start', 'stroyka-qa-static'])
        self.run(['docker', 'exec', 'stroyka-qa-static', 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile'])
        self.run(['docker', 'start', GATEWAY])
        self.run(['docker', 'exec', GATEWAY, 'caddy', 'validate', '--config', '/etc/caddy/Caddyfile'])
        require(self.inspect(GATEWAY, '{{json .State.Running}}') is True
                and self.inspect('stroyka-qa-static', '{{json .State.Running}}') is True,
                'QA routing containers not running')


def execute(m, driver, prompt, *, clock=time.monotonic):
    """No unattended confirmation; caller supplies terminal input, not a flag."""
    plan(m)
    driver.deliver_target(m)
    try:
        evidence = driver.preflight(m)
        driver.prepare_frontend(m)
        require(driver.preflight(m) == evidence, 'QA state changed during preparation')
        driver.verify_frontend()
        started = clock()
        require(prompt(confirmation(m)) == confirmation(m), 'QA confirmation mismatch')
        require(0 <= clock()-started <= 300, 'QA confirmation expired')
        require(driver.preflight(m) == evidence, 'QA state changed after confirmation')
        driver.verify_frontend()
        driver.record_maintenance_intent(m, evidence)
        driver.accept_preparation()
    except BaseException:
        driver.discard_preparation()
        raise
    try:
        driver.stop()
        driver.prepare_database(m)
        driver.switch(m)
        driver.frontend(m)
        driver.start_and_check(m)
    except BaseException:
        # No rollback claim. Best effort keeps both QA backends/gateway closed.
        try:
            driver.stop()
        except Exception:
            pass
        raise
    return {'status': 'qa_installed_pending_business_acceptance',
            'head': m['target_sha'], 'audit_complete': False, 'rollback_verified': False}


def command(args):
    m = json.loads(args.manifest.read_text())
    if not args.execute:
        print(json.dumps(plan(m), indent=2))
        return
    import sys
    require(sys.stdin.isatty(), 'QA execution requires fresh interactive terminal confirmation')
    def prompt(phrase):
        print('This replaces ONLY test data in stroyka_qa. Type exactly:\n' + phrase)
        return input('Confirmation: ').strip()
    print(json.dumps(execute(m, LocalDriver(), prompt), indent=2))
