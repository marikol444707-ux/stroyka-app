#!/usr/bin/env python3
"""Prepare/test a private source candidate and inspect startup data read-only.

No apply mode. No app imports, production file writes, migrations, or service
actions. A successful preparation is not authorization/readiness to install.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/var/www/stroyka-app')
HOST = 'msk-1-vm-zh4n'
SERVER_HEAD = '57023611c6090c1bdf63a107a28eefadd1afb492'
MAIN_HASH = '66182cb62da7b838b3f5044a0d61465fc9c0304c4ac5dcaf4042b71dbebd6ff8'
YANDEX = 'backend/features/model_gateway/yandex_adapter.py'
YANDEX_HASH = 'feecf33d555cc60cae0f8edc63d5d491cbc4a12f5bb89e197cc1ecb5fe1bc533'
CORE = '8f5af35fa3afc2ba4093937310b37f015859eeff'
# Immutable public source only; never fetch or publish production data/config.
PAYLOADS = {'payload/check_work_hotfix_merge.py': {'revision': 'a63b85632e2f854d40c926ab1625cd0b48212b33',
                                        'sha256': 'ebd71e9e7283e05b5216719d573b971b14e3c1bba960f4495b429c40ad7e8e86',
                                        'source': 'scripts/check_work_hotfix_merge.py'},
 'payload/server-readonly-check.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                      'sha256': 'ff820ea9665de42d2ee31016cf44cead6d1f524399d3932152bf22678b6844f4',
                                      'source': 'scripts/combined_release/server-readonly-check.py'},
 'payload/unified_release.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                'sha256': '596a006e131f0419c108108e4c3b1acf7ef2735e83882129a004019a197910f4',
                                'source': 'scripts/unified_release.py'},
 'resolvers/resolve-frontend-build-env.sh': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                             'sha256': '3549c15c9c08ca662c96de95dc3c38281357e4bdf6e35318279bf38c6cc5c6ae',
                                             'source': 'scripts/resolve-frontend-build-env.sh'},
 'resolvers/resolve-material-capability-build-env.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                        'sha256': '6871cebecab5b03ca5aaefe7dafe8b2d524e07931c22dfea51bb53c0656954f3',
                                                        'source': 'scripts/resolve-material-capability-build-env.py'},
 'resolvers/resolve-participant-build-env.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                'sha256': '14b75c7e4f585feb90ab4af0a6eaa14a87da9f7811b59a3571e827a760f4cdd5',
                                                'source': 'scripts/resolve-participant-build-env.py'},
 'resolvers/resolve-supplier-build-env.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                             'sha256': 'fe91766d7cd3532e7f4bed5383051a8955b4fa7e0be50b948e3d0c6e84f31430',
                                             'source': 'scripts/resolve-supplier-build-env.py'},
 'resolvers/resolve-warehouse-build-env.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                              'sha256': '3da044de9f1374a581e813b359f91daffdf8428d0b47133e7f955d5742f19a09',
                                              'source': 'scripts/resolve-warehouse-build-env.py'},
 'resolvers/resolve-work-material-build-env.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                  'sha256': '9261bf5953c4d87fd495ebdedef73e0399042ae0ffe6ff67790547717cc58914',
                                                  'source': 'scripts/resolve-work-material-build-env.py'},
 'resolvers/verify-frontend-feature-build.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                'sha256': '0d981417ab300cf5de44d06c7ad07bac02009154f70618855d23c4e504c51d5a',
                                                'source': 'scripts/verify-frontend-feature-build.py'},
 'tests/backend/features/invoice_scan/test_supplier_identity.py': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                                   'sha256': 'bf7d2fe17a32463d243d8fa43bde612ce0e6fa165fe337c5cf393ab2a28ad67c',
                                                                   'source': 'backend/features/invoice_scan/test_supplier_identity.py'},
 'tests/src/components/ScannedInvoiceFormModal.test.jsx': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                           'sha256': 'e38295fda65a5a0879600ea18f85270b82157464d23d3b03d1dbc9214e1934f3',
                                                           'source': 'src/components/ScannedInvoiceFormModal.test.jsx'},
 'tests/src/features/work-acceptance/WorkReviewQueue.test.jsx': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                                 'sha256': 'd5f4d0fb9863c837e589cf9988afa9e9b76ecd74beb58fcc7f895e5413fde2f5',
                                                                 'source': 'src/features/work-acceptance/WorkReviewQueue.test.jsx'},
 'tests/src/utils/scannedSupplierSelection.test.js': {'revision': '8f5af35fa3afc2ba4093937310b37f015859eeff',
                                                      'sha256': '7e33f313fc10ca923c17a2e4ae115365aa3f933cfdda3d704fc2c82430a19220',
                                                      'source': 'src/utils/scannedSupplierSelection.test.js'}}
CANDIDATE_HASHES = {'backend/features/invoice_scan/supplier_identity.py': 'abf70096fa2c0a18b60d487a2a6f09bbbaece96530ed87e044666e0f8114b28a',
 'backend/main.py': 'f2c301888d0c70f198f11c8e7e5418bcd4778c7b7eae1b07d3f19c500ebc40f0',
 'src/components/AccountingPage.jsx': '9c4485a9691d6e05e79556032a48c79a708bdcf0ddc7aa6e98fc43a0bf097ed2',
 'src/components/AppWorkflowModals.jsx': '294cc42c97cba570d7b4f168a42cfa784a9b0a9c4c3dd4e4308c47b91139be32',
 'src/components/ScanInvoiceModal.jsx': 'eb3ea260b339a0df06d3b84b23efc7bab36d567a6af1eaa3b64b1f83cecc100e',
 'src/components/ScannedInvoiceFormModal.jsx': 'a13f6bc2fefb6b78a9e2aa2f291bd470db7a1ca995ee6a4a8ab563b6c1246019',
 'src/features/dashboard/DashboardPage.jsx': '0410b280e1631cdc41391dcf1e081c5b5ecf5de87cdc43dca03454ed4c29faf6',
 'src/features/work-acceptance/WorkReviewQueue.jsx': '35eab4bb226445b16a0f19e15d40e4c28cfb53f8d4f7ea2f9a1d72ef0bfd6476',
 'src/utils/scannedSupplierSelection.js': '6bdc2eb69c99eef9d51ee520f97bd64bd53db0f1821440f59b34c9329a6fe7d0'}


class Stop(RuntimeError):
    pass


def need(condition, code):
    if not condition:
        raise Stop(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean_env(stage):
    return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'HOME': str(stage / 'home'), 'TMPDIR': str(stage / 'tmp'),
            'CI': 'true', 'FORCE_COLOR': '0', 'PYTHONDONTWRITEBYTECODE': '1',
            'GIT_OPTIONAL_LOCKS': '0'}


def command(args, *, cwd=None, env=None, timeout=30):
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env,
                            capture_output=True, timeout=timeout)
    need(result.returncode == 0, 'PREPARATION_COMMAND_FAILED')
    return result.stdout


def verify_baseline():
    need(os.geteuid() == 0 and socket.gethostname().split('.')[0] == HOST, 'WRONG_HOST_OR_USER')
    need(ROOT.is_dir() and ROOT.resolve() == ROOT, 'UNEXPECTED_APP_ROOT')
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'GIT_OPTIONAL_LOCKS': '0'}
    head = command(['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', ROOT,
                    'rev-parse', 'HEAD'], env=environment).decode().strip()
    need(head == SERVER_HEAD, 'SERVER_HEAD_CHANGED')
    for path, expected in [('backend/main.py', MAIN_HASH), (YANDEX, YANDEX_HASH)]:
        need(not (ROOT / path).is_symlink() and digest((ROOT / path).read_bytes()) == expected,
             'SERVER_SOURCE_CHANGED')


def fetch_payloads(stage):
    for relative, pin in PAYLOADS.items():
        url = 'https://raw.githubusercontent.com/marikol444707-ux/stroyka-app/' + pin['revision'] + '/' + pin['source']
        with urllib.request.urlopen(url, timeout=25) as response:
            data = response.read(5 * 1024 * 1024 + 1)
        need(len(data) <= 5 * 1024 * 1024 and digest(data) == pin['sha256'], 'PINNED_PAYLOAD_CHANGED')
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(data)
        path.chmod(0o600)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def allowed_source(path, tracked):
    parts = PurePosixPath(path).parts
    if not parts or PurePosixPath(path).is_absolute() or any(p in ('.', '..', '.git', 'node_modules', 'uploads', 'build') or p.startswith('.env') for p in parts):
        return False
    if parts[0] not in ('src', 'public', 'scripts', 'backend', 'migrations'):
        return tracked and len(parts) == 1 and path in (
            'package.json', 'package-lock.json', 'jsconfig.json', 'tsconfig.json',
            'tailwind.config.js', 'postcss.config.js', '.browserslistrc')
    if any(p.startswith(('uploads.', 'uploads_', 'backup')) for p in parts):
        return False
    return tracked or Path(path).suffix in ('.py', '.js', '.jsx', '.ts', '.tsx', '.css')


def read_stage_source(root, name):
    path = root / name
    for node in (path, *path.parents):
        if node == root:
            break
        need(not node.is_symlink(), 'SOURCE_COPY_SYMLINK')
    need(path.is_file() and path.stat().st_size <= 64 * 1024 * 1024, 'SOURCE_COPY_FILE_INVALID')
    data = path.read_bytes()
    need(len(data) <= 64 * 1024 * 1024, 'SOURCE_COPY_FILE_INVALID')
    return data


def copy_source(stage, checker):
    destination = stage / 'source'
    destination.mkdir()
    before = {}
    total = 0
    for tracked, args in ((True, ['ls-files', '-z']), (False, ['ls-files', '--others', '--exclude-standard', '-z'])):
        raw = command(['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', ROOT, *args], env=clean_env(stage))
        for entry in raw.split(b'\0'):
            if not entry:
                continue
            name = entry.decode('utf-8')
            if name in before or not allowed_source(name, tracked):
                continue
            data = read_stage_source(ROOT, name)
            total += len(data)
            need(len(before) < 15000 and total <= 768 * 1024 * 1024, 'SOURCE_COPY_BUDGET_EXCEEDED')
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            before[name] = digest(data)
    # Keep originals only in this private preparation directory, not in GitHub.
    for name, pins in checker.SOURCES.items():
        current = checker.read_current(ROOT, name)
        need((digest(current) if current is not None else None) == before.get(name), 'SOURCE_CHANGED_DURING_COPY')
        base = checker.fetch_source(checker.BASE, name, pins['base'])
        incoming = checker.fetch_source(checker.TARGET, name, pins['target'])
        status, merged = checker.merge_source(current, base, incoming, python_functions=name == 'backend/main.py')
        need(merged is not None and status in ('already_present', 'applicable',
             'applicable_preserving_local_changes', 'applicable_verified_function_merge'), 'SOURCE_MERGE_CONFLICT')
        need(digest(merged) == CANDIDATE_HASHES[name], 'CANDIDATE_HASH_CHANGED')
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(merged)
    return destination, before


def verified_service_python():
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    pid = command(['/usr/bin/systemctl', 'show', 'stroyka.service', '-p', 'MainPID', '--value'], env=environment).decode().strip()
    need(pid.isdecimal() and int(pid) > 0, 'RUNNING_SERVICE_REQUIRED')
    process = Path('/proc') / pid
    need((process / 'cwd').resolve() == ROOT / 'backend', 'SERVICE_CWD_CHANGED')
    python = Path((process / 'cmdline').read_bytes().split(b'\0')[0].decode())
    if not python.is_absolute():
        python = ROOT / 'backend' / python
    executable = (process / 'exe').resolve()
    need(re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', python.name) and python.resolve() == executable
         and executable == Path('/usr/bin/python3.12').resolve(), 'SERVICE_INTERPRETER_UNVERIFIED')
    return str(python)


SNAPSHOT_ADAPTER = r'''
import hashlib,importlib.util,json,sys
from pathlib import Path
stage=Path(sys.argv[1]);root=Path('/var/www/stroyka-app')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
try:
    helper=load('readonly_runtime',stage/'payload/unified_release.py')
    probe=load('readonly_startup_probe',stage/'payload/server-readonly-check.py')
    checker=load('readonly_merge',stage/'payload/check_work_hotfix_merge.py')
    runner=probe.startup_module();plan=runner.load_plan()
    actual=checker.startup_fingerprints((root/'backend/main.py').read_bytes())
    if actual!=plan['startup_ast_hashes']:raise RuntimeError('STARTUP_GUARD_SOURCE_CHANGED')
    env=helper.runtime_environment(root,'stroyka.service')
    import psycopg2
    conn=psycopg2.connect(**runner.connection_settings(env))
    try:snapshot=runner.inspect_connection(conn,plan)
    finally:conn.close()
    units={name:probe.unit_report(name) for name in (*probe.UNITS,'cron.service')}
    pid=units['stroyka.service']['MainPID']
    result={'snapshot':snapshot,'units':units,'jobs':probe.systemd_rows('jobs'),
            'backend_listeners':probe.listeners(pid),'launch_inventory':probe.launch_inventory(units),
            'nginx_routing':probe.routing_facts(probe.output(['nginx','-T'])),
            'maintenance_boundary_proven':False,'installation_ready':False}
    storage=env.get('STORAGE_BACKEND','local').strip().lower()
    result['storage_backend']=storage if storage in ('local','s3') else 'OTHER'
    # Resolver input contains only existing feature flags/company allowlists.
    flags=helper.frontend_service_environment(env)
    (stage/'feature-resolver-input.txt').write_text(flags)
    print(json.dumps(result,ensure_ascii=False))
except Exception as error:
    code=str(error) if type(error).__name__=='CheckError' and __import__('re').fullmatch('[A-Z][A-Z0-9_]+',str(error)) else type(error).__name__
    counts=getattr(error,'counts',{})
    safe_counts={key:counts[key] for key in ('json_rows','json_total_bytes','json_max_value_bytes')
                 if type(counts) is dict and type(counts.get(key)) is int and counts[key]>=0}
    print(json.dumps({'report_complete':False,'code':code,'counts':safe_counts,'installation_ready':False}))
    sys.exit(1)
'''


PURE_TEST_ADAPTER = r'''
import pathlib,sys,types,unittest
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root))
for name,relative in [('backend','backend'),('backend.features','backend/features'),('backend.features.invoice_scan','backend/features/invoice_scan')]:
    package=types.ModuleType(name);package.__path__=[str(root/relative)];sys.modules[name]=package
    if '.' in name:
        parent,attribute=name.rsplit('.',1);setattr(sys.modules[parent],attribute,package)
suite=unittest.defaultTestLoader.loadTestsFromName('backend.features.invoice_scan.test_supplier_identity')
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('PURE_BACKEND_ACCEPTANCE tests=%s skipped=%s' % (result.testsRun,len(result.skipped)))
sys.exit(0 if result.testsRun>0 and not result.skipped and result.wasSuccessful() else 1)
'''


def logged(args, stage, name, *, cwd, env, timeout, input_data=None):
    log = stage / (name + '.log')
    started = time.monotonic()
    with log.open('xb') as output:
        result = subprocess.run(list(map(str, args)), cwd=cwd, env=env,
                                stdout=output, stderr=subprocess.STDOUT,
                                input=input_data, timeout=timeout)
    log.chmod(0o600)
    return {'passed': result.returncode == 0, 'seconds': round(time.monotonic() - started),
            'log': str(log)}


def progress(phase):
    print(json.dumps({'preparation_phase': phase, 'application_changed': False}), flush=True)


def build_capacity(stage):
    available = next((int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                      if line.startswith('MemAvailable:')), 0)
    free = shutil.disk_usage(stage).free
    need(available >= 3 * 1024**3, 'INSUFFICIENT_SPARE_MEMORY_FOR_SERVER_BUILD')
    need(free >= 3 * 1024**3, 'INSUFFICIENT_SPACE_FOR_PREPARATION')
    return {'available_memory_mib': available // 1024**2, 'free_disk_mib': free // 1024**2}


def prepare():
    verify_baseline()
    stage = Path(tempfile.mkdtemp(prefix='stroyka-work-hotfix-', dir='/root'))
    for name in ('home', 'tmp'):
        (stage / name).mkdir(mode=0o700)
    report = {'stage': str(stage), 'installation_ready': False, 'production_files_changed': False,
              'services_changed': False, 'maintenance_boundary_proven': False,
              'production_database_access': 'READ_ONLY_SNAPSHOT_ONLY',
              'upstream_core_ci': 'https://github.com/marikol444707-ux/stroyka-app/actions/runs/40503114770',
              'exact_merged_snapshot_postgres_tests': 'NOT_RUN'}
    try:
        progress('download_pinned_sources')
        fetch_payloads(stage)
        checker = load(stage / 'payload/check_work_hotfix_merge.py', 'pinned_hotfix_merge')
        source, before = copy_source(stage, checker)
        report['candidate_sha256'] = CANDIDATE_HASHES
        for path in PAYLOADS:
            if path.startswith('tests/'):
                target = source / path.removeprefix('tests/')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(stage / path, target)
            elif path.startswith('resolvers/'):
                target = source / 'scripts' / Path(path).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(stage / path, target)
        python = verified_service_python()
        progress('readonly_startup_snapshot')
        snapshot_process = subprocess.run([python, '-I', '-B', '-c', SNAPSHOT_ADAPTER, str(stage)],
                               cwd=stage, env=clean_env(stage), timeout=160, capture_output=True)
        snapshot_raw = snapshot_process.stdout
        need(len(snapshot_raw) <= 2 * 1024 * 1024, 'SNAPSHOT_REPORT_TOO_LARGE')
        report['startup'] = json.loads(snapshot_raw)
        need(snapshot_process.returncode == 0, 'READONLY_STARTUP_SNAPSHOT_FAILED')
        progress('isolated_supplier_tests')
        report['backend_tests'] = logged([python, '-I', '-B', '-c', PURE_TEST_ADAPTER, source],
                stage, 'backend-tests', cwd=source, env=clean_env(stage), timeout=90)
        need(report['backend_tests']['passed'], 'MERGED_BACKEND_TESTS_FAILED')
        environment = clean_env(stage)
        report['build_capacity'] = build_capacity(stage)
        environment['NODE_OPTIONS'] = '--max-old-space-size=1024'
        node = shutil.which('node')
        npm = shutil.which('npm')
        need(node is not None and npm is not None, 'NODE_AND_NPM_REQUIRED')
        environment['PATH'] = os.pathsep.join([str(Path(node).parent), str(Path(npm).parent), environment['PATH']])
        feature_input = (stage / 'feature-resolver-input.txt').read_text()
        flags = command(['/bin/bash', source / 'scripts/resolve-frontend-build-env.sh', feature_input, ''],
                        cwd=source, env=environment).decode()
        environment.update(line.split('=', 1) for line in flags.splitlines() if line)
        need(environment.get('REACT_APP_WORK_ACCEPTANCE_ENABLED') == '1', 'EXISTING_ACCEPTANCE_MODE_CHANGED')
        environment['BUILD_PATH'] = str(stage / 'frontend')
        progress('frontend_dependencies')
        report['npm_dependencies'] = logged([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'],
                stage, 'npm-ci', cwd=source, env=environment, timeout=480)
        need(report['npm_dependencies']['passed'], 'FRONTEND_DEPENDENCIES_FAILED')
        scripts = json.loads((source / 'package.json').read_text())['scripts']
        need(scripts.get('test') == 'react-scripts test' and scripts.get('build') == 'react-scripts build',
             'UNREVIEWED_PACKAGE_COMMANDS')
        runner = source / 'node_modules/react-scripts/bin/react-scripts.js'
        progress('merged_frontend_tests')
        tests = ['src/components/ScannedInvoiceFormModal.test.jsx',
                 'src/features/work-acceptance/WorkReviewQueue.test.jsx',
                 'src/utils/scannedSupplierSelection.test.js']
        report['frontend_tests'] = logged(['/usr/bin/nice', '-n', '10', node, runner, 'test', '--watchAll=false', '--runInBand',
                '--runTestsByPath', *tests], stage, 'frontend-tests', cwd=source, env=environment, timeout=240)
        summary = Path(report['frontend_tests']['log']).read_text(errors='replace')
        counts = re.search(r'^Tests:\s+(\d+) passed,\s+(\d+) total\s*$', summary, re.M)
        need(report['frontend_tests']['passed'] and counts and counts[1] == counts[2] and int(counts[1]) > 0,
             'FRONTEND_TESTS_FAILED_OR_SKIPPED')
        report['frontend_tests']['tests_passed'] = int(counts[1])
        progress('merged_frontend_build')
        report['frontend_build'] = logged(['/usr/bin/nice', '-n', '10', node, runner, 'build'], stage, 'frontend-build',
                cwd=source, env=environment, timeout=480)
        need(report['frontend_build']['passed'], 'MERGED_FRONTEND_BUILD_FAILED')
        report['frontend_features'] = logged([python, '-I', '-B', source / 'scripts/verify-frontend-feature-build.py',
                stage / 'frontend'], stage, 'frontend-features', cwd=source, env=environment, timeout=30,
                input_data=flags.encode())
        need(report['frontend_features']['passed'], 'BUILT_FRONTEND_FEATURES_MISMATCH')
        verify_baseline()
        need(all(digest(read_stage_source(ROOT, name)) == expected for name, expected in before.items()),
             'PRODUCTION_SOURCE_CHANGED_DURING_PREPARATION')
        report['source_stable_during_preparation'] = True
        report['preparation_complete'] = True
        report['startup_business_guards_satisfied'] = report['startup']['snapshot']['business_guards_satisfied']
        report['remaining'] = ['Current maintenance exclusion and fresh backup',
             'Review startup catalog/sequence effects', 'Explicit maintenance approval with downtime',
             'Installed authenticated browser acceptance']
    except Exception as error:
        report['preparation_complete'] = False
        report['code'] = str(error) if isinstance(error, Stop) else type(error).__name__
    (stage / 'preparation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (stage / 'source-before-sha256.json').write_text(json.dumps(locals().get('before', {}), indent=2) + '\n')
    return report


if __name__ == '__main__':
    try:
        report = prepare()
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(0 if report.get('preparation_complete') else 1)
    except Exception as error:
        print(json.dumps({'installation_ready': False, 'preparation_complete': False,
                          'code': str(error) if isinstance(error, Stop) else type(error).__name__}))
        raise SystemExit(1)
