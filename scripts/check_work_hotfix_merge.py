#!/usr/bin/env python3
"""Check a pinned source-only three-way merge, without modifying the app.

This is a compatibility diagnostic, not an installer. It never imports the app,
reads configuration, contacts PostgreSQL, or manages services. Temporary merge
inputs are private and removed before the report is printed.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

BASE = 'adc5f812407080c18e797b3c91d99b24340b46da'
TARGET = 'e0fd91a6341adc9d2dd27649b4b6e0d6ebbae6d7'
MAX_BYTES = 5 * 1024 * 1024
# Exact source bytes reviewed in the successful application CI. No env/data paths.
SOURCES = {'backend/main.py': {'base': '197164ec7afe3cae418c7520c938fa7fcb0c61a5eac53cdd832161033b4a0011', 'target': 'a63a1acfdbebe009f89744eab6f8b7a5642f090bb262ba34bc92ebfe824e0a62'}, 'backend/features/invoice_scan/supplier_identity.py': {'base': None, 'target': 'abf70096fa2c0a18b60d487a2a6f09bbbaece96530ed87e044666e0f8114b28a'}, 'src/components/AccountingPage.jsx': {'base': '8be128ee4ea0177ce4288483dbc0af896bb0376b30e900501e6acb4672e6be59', 'target': '9c4485a9691d6e05e79556032a48c79a708bdcf0ddc7aa6e98fc43a0bf097ed2'}, 'src/components/AppWorkflowModals.jsx': {'base': '7d498dcbe97339a9740a4e2f9c4764c6482ccacbb82ab87d2ddcc93ca0fac05d', 'target': '294cc42c97cba570d7b4f168a42cfa784a9b0a9c4c3dd4e4308c47b91139be32'}, 'src/components/ScanInvoiceModal.jsx': {'base': 'c8d41e9e4d30dc646671d27fc5428544615835dd0ec4ac71e0eec8ed49a27891', 'target': 'fa16d19b502988cb276e985f4bbd0860a40819d34727796664884a172f67f01d'}, 'src/components/ScannedInvoiceFormModal.jsx': {'base': 'eb8e267d19fa79754ed0100126834090cbf6588dafd335f8dd3f6df200603338', 'target': 'd79583df813a314c1440f5ee7d1ef233f9eb7094ef81a4fc2acc4a04d535bd78'}, 'src/features/dashboard/DashboardPage.jsx': {'base': 'ecd6db84c2ea3bdcceee93d4b2f19242c446ca6c5f92137bc4febfad87a45eca', 'target': '0410b280e1631cdc41391dcf1e081c5b5ecf5de87cdc43dca03454ed4c29faf6'}, 'src/features/work-acceptance/WorkReviewQueue.jsx': {'base': None, 'target': '35eab4bb226445b16a0f19e15d40e4c28cfb53f8d4f7ea2f9a1d72ef0bfd6476'}, 'src/utils/scannedSupplierSelection.js': {'base': None, 'target': '6bdc2eb69c99eef9d51ee520f97bd64bd53db0f1821440f59b34c9329a6fe7d0'}}


def digest(value):
    return hashlib.sha256(value).hexdigest() if value is not None else None


def read_current(root, relative):
    path = root / relative
    for node in (path, *path.parents):
        if node == root:
            break
        if node.is_symlink():
            raise ValueError('SOURCE_SYMLINK_REQUIRES_REVIEW')
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('INVALID_SOURCE_FILE')
    data = path.read_bytes()
    if len(data) > MAX_BYTES or b'\0' in data:
        raise ValueError('INVALID_SOURCE_FILE')
    return data


def fetch_source(revision, relative, expected):
    if expected is None:
        return None
    url = ('https://raw.githubusercontent.com/marikol444707-ux/stroyka-app/'
           + revision + '/' + relative)
    with urllib.request.urlopen(url, timeout=25) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or digest(data) != expected:
        raise ValueError('PINNED_SOURCE_HASH_MISMATCH')
    return data


def merge_source(current, base, incoming):
    if current == incoming:
        return 'already_present', current
    if current == base:
        return 'applicable', incoming
    if current is None or base is None:
        return 'conflict', None
    with tempfile.TemporaryDirectory(prefix='stroyka-merge-check-') as folder:
        directory = Path(folder)
        files = [directory / name for name in ('current', 'base', 'incoming')]
        for path, data in zip(files, (current, base, incoming)):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
        result = subprocess.run(
            ['/usr/bin/git', 'merge-file', '-p', '--', *map(str, files)],
            cwd=directory, capture_output=True, timeout=10,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
        )
    if result.returncode != 0:
        return ('conflict' if 0 < result.returncode < 128 else 'merge_error'), None
    return 'applicable_preserving_local_changes', result.stdout


def function_ast(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.dump(node, include_attributes=False)
    return None


def inspect(root, fetch=fetch_source):
    before = {path: read_current(root, path) for path in SOURCES}
    report = []
    init_unchanged = None
    for path, pins in SOURCES.items():
        base = fetch(BASE, path, pins['base'])
        incoming = fetch(TARGET, path, pins['target'])
        # Keep verification at this boundary too, including injected test fetchers.
        if digest(base) != pins['base'] or digest(incoming) != pins['target']:
            raise ValueError('PINNED_SOURCE_HASH_MISMATCH')
        status, merged = merge_source(before[path], base, incoming)
        if merged is not None and path.endswith('.py'):
            compile(merged, path, 'exec')  # Syntax only: no execution or imports.
        if path == 'backend/main.py' and merged is not None:
            original = function_ast(before[path], 'init_db') if before[path] else None
            init_unchanged = original is not None and original == function_ast(merged, 'init_db')
            if not init_unchanged:
                status = 'startup_code_requires_review'
        report.append({'path': path, 'status': status,
                       'current_sha256': digest(before[path]),
                       'candidate_sha256': digest(merged)})
    stable = all(read_current(root, path) == value for path, value in before.items())
    applicable = stable and all(row['status'] in (
        'already_present', 'applicable', 'applicable_preserving_local_changes') for row in report)
    return {'read_only_app': True, 'report_complete': True,
            'application_files_changed': False, 'services_changed': False,
            'database_accessed': False, 'source_stable_during_check': stable,
            'text_merge_applicable': applicable, 'init_db_code_unchanged': init_unchanged,
            'startup_data_gate': 'NOT_EVALUATED', 'maintenance_quiescence': 'NOT_ESTABLISHED',
            'merged_application_tests': 'NOT_RUN', 'installation_ready': False,
            'files': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path('/var/www/stroyka-app'))
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.app.resolve()), ensure_ascii=False))
    except Exception as error:
        allowed = {'SOURCE_SYMLINK_REQUIRES_REVIEW', 'INVALID_SOURCE_FILE',
                   'PINNED_SOURCE_HASH_MISMATCH'}
        code = str(error) if isinstance(error, ValueError) and str(error) in allowed else type(error).__name__
        print(json.dumps({'read_only_app': True, 'report_complete': False,
                          'installation_ready': False, 'code': code}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
