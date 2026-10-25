#!/usr/bin/env python3
"""Install one reviewed invoice-only patch without moving HEAD or changing data.

Default: read-only plan. apply builds the production-base frontend in isolation,
backs up current source/public assets, and restores them on failure. Browser
verification remains pending; no deployed.json/verified.json is manufactured.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

BASE = '57023611c6090c1bdf63a107a28eefadd1afb492'
MAIN_BEFORE = '2b71e5c5eb6c312a7f54e0fe8f8a6cdc49a8c3d55bbc2dcc6ab433029c86cfcf'
ADAPTER_BEFORE = 'feecf33d555cc60cae0f8edc63d5d491cbc4a12f5bb89e197cc1ecb5fe1bc533'
FILES = (
    'backend/main.py',
    'backend/features/invoice_scan/__init__.py',
    'backend/features/invoice_scan/validation.py',
    'src/components/ScanInvoiceModal.jsx',
    'src/components/ScannedInvoiceFormModal.jsx',
    'src/components/AppWorkflowModals.jsx',
    'src/components/warehouse/WarehouseInvoiceAttachments.jsx',
    'src/components/warehouse/WarehouseInvoicesParts.jsx',
    'src/features/warehouse/warehouseCrudActions.js',
    'src/utils/invoiceScanValidation.js',
    'src/utils/invoiceSpreadsheet.js',
    'src/components/AiAssistantDrawer.jsx',
    'src/components/AiAssistantDrawer.css',
)
ADAPTER = 'backend/features/model_gateway/yandex_adapter.py'


class Stop(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], check=check, capture_output=True).stdout


def safe_path(root, name):
    path = root / name
    require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'invalid_path')
    require(not any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent), 'symlink_path_refused')
    return path


def load_helper(root, name):
    path = safe_path(root, 'scripts/' + name + '.py')
    require(path.read_bytes() == git(root, 'show', 'HEAD:scripts/' + name + '.py'), 'release_helper_changed')
    spec = importlib.util.spec_from_file_location('_invoice_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(root, release, expected_head, adapter_backup):
    require(expected_head == BASE and git(root, 'rev-parse', 'HEAD').decode().strip() == BASE, 'installed_head_mismatch')
    require(re.fullmatch('[0-9a-f]{40}', release or '') is not None, 'full_release_sha_required')
    require(subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', BASE, release], capture_output=True).returncode == 0, 'release_not_based_on_reviewed_production')
    require(not git(root, 'diff', '--cached', '--name-only').strip(), 'staged_changes_refused')
    dirty = set(git(root, 'diff', '--name-only').decode().splitlines())
    require(dirty <= {'backend/main.py', ADAPTER}, 'unreviewed_local_changes')
    require(sha(safe_path(root, ADAPTER).read_bytes()) == ADAPTER_BEFORE, 'adapter_changed_since_review')
    changes = {}
    for name in FILES:
        path = safe_path(root, name)
        tracked = subprocess.run(['git', '-C', str(root), 'cat-file', '-e', 'HEAD:' + name], capture_output=True).returncode == 0
        expected = git(root, 'show', 'HEAD:' + name) if tracked else None
        before = path.read_bytes() if path.exists() else None
        if name == 'backend/main.py':
            require(before is not None and sha(before) == MAIN_BEFORE, 'main_changed_since_pdf_repair')
        else:
            require(before == expected, 'source_changed_or_new_file_exists:' + name)
        after = git(root, 'show', release + ':' + name)
        require(after != before, 'release_file_unchanged:' + name)
        if name.endswith('.py'):
            compile(after, name, 'exec')
        changes[name] = {'before': before, 'after': after}
    return changes


def write_atomic(path, content, attributes=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if attributes is None:
        attributes = ((stat.S_IMODE(path.stat().st_mode), path.stat().st_uid, path.stat().st_gid)
                      if path.exists() else (0o644, os.getuid(), os.getgid()))
    fd, temporary = tempfile.mkstemp(prefix='.invoice-update-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, attributes[0])
        os.chown(temporary, attributes[1], attributes[2])
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def backup_sources(root, stage, changes):
    rows = {}
    for name, change in changes.items():
        path = safe_path(root, name)
        attributes = [stat.S_IMODE(path.stat().st_mode), path.stat().st_uid, path.stat().st_gid] if path.exists() else None
        if change['before'] is not None:
            target = stage / 'source-before' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(change['before'])
        rows[name] = {'beforeHash': sha(change['before']) if change['before'] is not None else None,
                      'afterHash': sha(change['after']), 'attributes': attributes}
    return rows


def restore_sources(root, stage, metadata):
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == metadata['head'], 'head_changed_restore_refused')
    require(set(metadata['files']) == set(FILES), 'backup_file_list_mismatch')
    for name, info in metadata['files'].items():
        path = safe_path(root, name)
        current = sha(path.read_bytes()) if path.exists() else None
        require(current in (info['beforeHash'], info['afterHash']), 'later_source_change_restore_refused:' + name)
        if info['beforeHash'] is not None:
            require(sha((stage / 'source-before' / name).read_bytes()) == info['beforeHash'], 'backup_source_corrupt')
    for name, info in metadata['files'].items():
        path = safe_path(root, name)
        if info['beforeHash'] is None:
            if path.exists():
                path.unlink()
        else:
            write_atomic(path, (stage / 'source-before' / name).read_bytes(), info['attributes'])


def extract_source(root, stage):
    source = stage / 'source'
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(git(root, 'archive', BASE))) as archive:
        for member in archive.getmembers():
            require(not member.issym() and not member.islnk() and not member.name.startswith('/') and '..' not in Path(member.name).parts,
                    'unsupported_archive_member')
        archive.extractall(source, filter='data')
    return source


def build_frontend(root, stage, changes, helper):
    source = extract_source(root, stage)
    for name, change in changes.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(change['after'])
    env = helper.runtime_environment(root, 'stroyka')
    flags = helper.run(['bash', source / 'scripts/resolve-frontend-build-env.sh', helper.frontend_service_environment(env), ''], cwd=source, env=env, capture=True)
    frontend_env = dict(env, BUILD_PATH=str(stage / 'frontend'), GENERATE_SOURCEMAP='false')
    frontend_env.update(entry.split('=', 1) for entry in flags.splitlines() if entry)
    helper.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=source, env=env)
    helper.run(['npm', 'run', 'build'], cwd=source, env=frontend_env)
    subprocess.run([os.sys.executable, str(source / 'scripts/verify-frontend-feature-build.py'), str(stage / 'frontend')],
                   cwd=source, env=env, input=flags + '\n', text=True, check=True)
    helper.manifest_files(stage / 'frontend')
    return env


def publish(root, source):
    subprocess.run(['bash', str(root / 'scripts/publish-frontend.sh'), str(source), str(root / 'build')], check=True)


def restart():
    subprocess.run(['systemctl', 'restart', 'stroyka'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'stroyka'], check=True)


def healthy(helper):
    for attempt in range(15):
        try:
            helper.health('http://127.0.0.1:8001', BASE)
            helper.health('https://stroyka26.pro', BASE)
            return
        except Exception:
            if attempt == 14:
                raise Stop('backend_or_database_health_failed')
            time.sleep(2)


def restore(root, stage, helper):
    metadata = json.loads((stage / 'patch.json').read_text())
    require(metadata['appRoot'] == str(root) and metadata['head'] == BASE, 'backup_target_mismatch')
    # Check everything before restoring any file.
    if metadata.get('frontendPublishing'):
        manifest = sha((root / 'build/asset-manifest.json').read_bytes())
        require(manifest in {metadata['frontendBefore'], metadata['frontendAfter']}, 'later_frontend_change_restore_refused')
    restore_sources(root, stage, metadata)
    if metadata.get('frontendPublishing'):
        publish(root, stage / 'frontend-before')
    restart()
    healthy(helper)
    return {'state': 'restored', 'backup': str(stage)}


def apply(root, release, expected_head, adapter_backup, backup_root):
    changes = plan(root, release, expected_head, adapter_backup)
    helper = load_helper(root, 'unified_release')
    healthy(helper)
    require(shutil.disk_usage(backup_root).free > 3 * 1024**3, 'need_3_gib_free_for_isolated_build')
    stage = Path(tempfile.mkdtemp(prefix='stroyka-invoice-update-', dir=backup_root))
    stage.chmod(0o700)
    shutil.copy2(__file__, stage / 'install_invoice_recovery.py')
    print(json.dumps({'state': 'building_before_installation', 'stage': str(stage)}), flush=True)
    env = build_frontend(root, stage, changes, helper)
    # Recheck files/HEAD after the long build, before the first app mutation.
    plan(root, release, expected_head, adapter_backup)
    checker = load_helper(root, 'release_database_check')
    database = checker.inspect_database(env)
    require(database.get('status') == 'ready', 'read_only_database_preflight_blocked')
    (stage / 'database-readonly.json').write_text(json.dumps(database, indent=2))
    helper.backup_frontend(root / 'build', stage / 'frontend-before')
    metadata = {'appRoot': str(root), 'head': BASE, 'release': release,
                'files': backup_sources(root, stage, changes), 'frontendPublishing': False,
                'frontendBefore': sha((root / 'build/asset-manifest.json').read_bytes()),
                'frontendAfter': sha((stage / 'frontend/asset-manifest.json').read_bytes())}
    record = stage / 'patch.json'
    record.write_text(json.dumps(metadata, indent=2))
    try:
        for name, change in changes.items():
            write_atomic(safe_path(root, name), change['after'])
        restart()
        healthy(helper)
        metadata['frontendPublishing'] = True
        record.write_text(json.dumps(metadata, indent=2))
        publish(root, stage / 'frontend')
        helper.manifest_files(root / 'build')
        for relative in helper.manifest_files(stage / 'frontend'):
            require(sha((root / 'build' / relative).read_bytes()) == sha((stage / 'frontend' / relative).read_bytes()), 'frontend_file_hash_mismatch')
        require(sha((root / 'build/index.html').read_bytes()) == sha((stage / 'frontend/index.html').read_bytes()), 'frontend_index_hash_mismatch')
        healthy(helper)
    except Exception:
        restore(root, stage, helper)
        raise Stop('installation_failed_restored_previous_version')
    report = {'state': 'installed_awaiting_browser', 'head': BASE, 'release': release, 'backup': str(stage),
              'checks': {'backend': True, 'database': True, 'frontend': True, 'browser': False}, 'complete': False,
              'restoreCommand': 'python3 ' + str(stage / 'install_invoice_recovery.py') + ' restore --backup ' + str(stage)}
    (stage / 'installed-awaiting-browser.json').write_text(json.dumps(report, indent=2))
    # The isolated source/npm tree is disposable; keep just rollback and checks.
    shutil.rmtree(stage / 'source')
    shutil.rmtree(stage / 'frontend')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'apply', 'restore'], nargs='?', default='plan')
    parser.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    parser.add_argument('--release')
    parser.add_argument('--expect-head')
    parser.add_argument('--adapter-backup', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--backup-root', type=Path, default=Path('/root'))
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    root = args.app_root.resolve()
    try:
        with open('/var/lock/stroyka-deploy.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == 'restore':
                require(args.backup is not None, 'backup_required')
                result = restore(root, args.backup.resolve(), load_helper(root, 'unified_release'))
            elif args.action == 'apply':
                result = apply(root, args.release, args.expect_head, args.adapter_backup, args.backup_root.resolve())
            else:
                changes = plan(root, args.release, args.expect_head, args.adapter_backup)
                result = {'state': 'ready', 'files': list(changes), 'changesMade': False}
        print(json.dumps(result))
    except Stop as error:
        print(json.dumps({'error': str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'error': 'invoice_update_failed_keep_stage_for_review'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
