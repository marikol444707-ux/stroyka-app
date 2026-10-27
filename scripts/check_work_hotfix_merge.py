#!/usr/bin/env python3
"""Check a pinned source-only three-way merge, without modifying the app.

This is a compatibility diagnostic, not an installer. It never imports the app,
reads configuration, contacts PostgreSQL, or manages services. Temporary merge
inputs are private and removed before the report is printed.
"""
import argparse
import ast
import copy
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import io
import tokenize
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


def run_merge(current, base, incoming, details=False):
    with tempfile.TemporaryDirectory(prefix='stroyka-merge-check-') as folder:
        directory = Path(folder)
        files = [directory / name for name in ('current', 'base', 'incoming')]
        for path, data in zip(files, (current, base, incoming)):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
        result = subprocess.run(
            ['/usr/bin/git', 'merge-file', '-p',
             *(['--diff3', '-L', 'SERVER', '-L', 'BASE', '-L', 'UPDATE'] if details else []),
             '--', *map(str, files)],
            cwd=directory, capture_output=True, timeout=10,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
        )
    return result


def merge_source(current, base, incoming, python_functions=False):
    if current == incoming:
        return 'already_present', current
    if current == base:
        return 'applicable', incoming
    if current is None or base is None:
        return 'conflict', None
    result = run_merge(current, base, incoming)
    if result.returncode != 0:
        if python_functions and 0 < result.returncode < 128:
            return merge_reviewed_python_functions(current, base, incoming)
        return ('conflict' if 0 < result.returncode < 128 else 'merge_error'), None
    return 'applicable_preserving_local_changes', result.stdout


def merge_reviewed_python_functions(current, base, incoming):
    """Replace reviewed functions only when local ASTs match the pinned base.

    This does not resolve competing logic: every edited function must already
    equal either the pinned base or update. Unrelated bytes and all server
    comments must survive. Any failed proof keeps the original conflict closed.
    """
    allowed = {'get_work_journal', '_apply_supplier_invoice_template_metadata', 'scan_invoice'}
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    def signature(node):
        return ast.dump(node, include_attributes=False)
    def split(source):
        tree = ast.parse(source)
        nodes = [node for node in tree.body if isinstance(node, function_types)]
        globals_ = [signature(node) for node in tree.body if not isinstance(node, function_types)]
        counts = Counter(node.name for node in nodes)
        return {node.name: node for node in nodes}, globals_, counts
    old, old_globals, old_counts = split(base)
    update, update_globals, update_counts = split(incoming)
    local, _, local_counts = split(current)
    if old.keys() != update.keys() or old_globals != update_globals:
        return 'conflict', None
    changed = {name for name in old if signature(old[name]) != signature(update[name])}
    if not changed or not changed <= allowed:
        return 'conflict', None
    if any(old_counts[name] != 1 or update_counts[name] != 1 or local_counts[name] != 1 for name in changed):
        return 'conflict', None
    old_lines = current.splitlines(keepends=True)
    update_lines = incoming.splitlines(keepends=True)
    def bounds(node):
        return min([node.lineno] + [item.lineno for item in node.decorator_list]) - 1, node.end_lineno
    def fragment(lines, node):
        start, end = bounds(node)
        return b''.join(lines[start:end])
    def comments(source):
        return Counter(token.string for token in tokenize.tokenize(io.BytesIO(source).readline)
                       if token.type == tokenize.COMMENT)
    replacements = []
    for name in changed:
        if signature(local[name]) == signature(update[name]):
            continue
        if signature(local[name]) != signature(old[name]):
            return 'conflict', None
        source = fragment(old_lines, local[name])
        replacement = fragment(update_lines, update[name])
        if comments(source) - comments(replacement):
            return 'conflict', None
        start, end = bounds(local[name])
        replacements.append((start, end, replacement))
    merged_lines = old_lines[:]
    for start, end, replacement in sorted(replacements, reverse=True):
        merged_lines[start:end] = [replacement]
    merged = b''.join(merged_lines)
    compile(merged, 'merged-main.py', 'exec')  # No execution.
    merged_nodes, _, merged_counts = split(merged)
    if any(merged_counts[name] != 1 or signature(merged_nodes[name]) != signature(update[name]) for name in changed):
        return 'conflict', None
    def outside(source, nodes):
        lines = source.splitlines(keepends=True)
        for start, end, name in sorted((*bounds(nodes[name]), name) for name in changed)[::-1]:
            lines[start:end] = [b'# reviewed-function:' + name.encode('ascii') + b'\n']
        return b''.join(lines)
    if outside(current, local) != outside(merged, merged_nodes):
        return 'conflict', None
    return 'applicable_verified_function_merge', merged


def sanitized_source(current, base, incoming):
    """Reveal code structure, but only literal tokens already in pinned public code."""
    fstring_middle = getattr(tokenize, 'FSTRING_MIDDLE', -1)
    literal_types = (tokenize.STRING, tokenize.NUMBER, fstring_middle)
    public = set()
    for source in (base, incoming):
        public.update(token.string for token in tokenize.tokenize(io.BytesIO(source).readline)
                      if token.type in literal_types)
    source = current.decode('utf-8')
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    replacements = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            replacement = ''
        elif token.type == fstring_middle and token.string not in public:
            replacement = '<PRIVATE_LITERAL>' + '\n' * token.string.count('\n')
        elif token.type in literal_types and token.string not in public:
            replacement = "'''<PRIVATE_LITERAL>" + '\n' * token.string.count('\n') + "'''"
        else:
            continue
        start = offsets[token.start[0] - 1] + token.start[1]
        end = offsets[token.end[0] - 1] + token.end[1]
        replacements.append((start, end, replacement))
    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    return source.splitlines(keepends=True)


def describe_conflict(current, base, incoming):
    if current is None or base is None:
        return {'details_complete': False, 'code': 'SOURCE_ADDITION_OR_DELETION'}
    result = run_merge(current, base, incoming, details=True)
    if not 0 < result.returncode < 128:
        return {'details_complete': False, 'code': 'NO_TEXT_CONFLICT'}
    raw = current.decode('utf-8')
    safe = sanitized_source(current, base, incoming)
    merged = result.stdout.decode('utf-8')
    blocks = []
    remaining = merged
    while '\n<<<<<<< SERVER\n' in '\n' + remaining:
        _, _, remaining = ('\n' + remaining).partition('\n<<<<<<< SERVER\n')
        ours, marker, remaining = remaining.partition('||||||| BASE\n')
        if not marker or not ours:
            return {'details_complete': False, 'code': 'CONFLICT_MARKERS_INVALID'}
        _, marker, remaining = remaining.partition('>>>>>>> UPDATE\n')
        position = raw.find(ours)
        if not marker or position < 0 or raw.find(ours, position + 1) >= 0:
            return {'details_complete': False, 'code': 'CONFLICT_LOCATION_AMBIGUOUS'}
        first_line = raw[:position].count('\n')
        count = len(ours.splitlines())
        blocks.append({'line': first_line + 1, 'lines': count,
                       'server_code': ''.join(safe[first_line:first_line + count])})
    if not blocks:
        return {'details_complete': False, 'code': 'CONFLICT_MARKERS_NOT_FOUND'}
    if sum(block['lines'] for block in blocks) > 250:
        return describe_function_differences(current, base, incoming)
    return {'details_complete': True, 'private_literals_and_comments_redacted': True,
            'blocks': blocks}


def describe_function_differences(current, base, incoming):
    """Summarize oversized conflict blocks using only functions changed upstream.

    This is diagnostic output, never a fallback merge or an application gate.
    Large unchanged function bodies do not need to be printed to inspect a small
    local change. The original merge still returns conflict.
    """
    sources = {'server': current, 'base': base, 'update': incoming}
    trees = {key: ast.parse(value) for key, value in sources.items()}
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    functions = {key: {node.name: node for node in tree.body if isinstance(node, function_types)}
                 for key, tree in trees.items()}
    def signature(node):
        return ast.dump(node, include_attributes=False) if node is not None else None
    globals_base = [signature(node) for node in trees['base'].body if not isinstance(node, function_types)]
    globals_update = [signature(node) for node in trees['update'].body if not isinstance(node, function_types)]
    if globals_base != globals_update:
        return {'details_complete': False, 'code': 'UPSTREAM_GLOBAL_CHANGES_REQUIRE_REVIEW'}
    changed = sorted(name for name in functions['base'].keys() | functions['update'].keys()
                     if signature(functions['base'].get(name)) != signature(functions['update'].get(name)))
    if not changed or len(changed) > 12:
        return {'details_complete': False, 'code': 'FUNCTION_SCOPE_REQUIRES_REVIEW'}
    public_constants = {(type(node.value), node.value)
                        for key in ('base', 'update') for node in ast.walk(trees[key])
                        if isinstance(node, ast.Constant)}
    class RedactConstants(ast.NodeTransformer):
        def visit_Constant(self, node):
            if (type(node.value), node.value) not in public_constants:
                return ast.copy_location(ast.Constant(value='<PRIVATE_LITERAL>'), node)
            return node
    def normalized(node):
        return (ast.unparse(RedactConstants().visit(copy.deepcopy(node))) + '\n').splitlines(keepends=True)
    reports = []
    total_lines = 0
    for name in changed:
        old, server, update = (functions[key].get(name) for key in ('base', 'server', 'update'))
        if old is None or server is None or update is None:
            return {'details_complete': False, 'code': 'FUNCTION_ADDITION_OR_DELETION', 'function': name}
        diff = [] if signature(server) == signature(old) else list(difflib.unified_diff(
                    normalized(old), normalized(server),
                    fromfile='published-base/' + name, tofile='server/' + name, n=3))
        total_lines += len(diff)
        reports.append({'function': name, 'server_line': server.lineno,
                        'server_ast_matches_base': signature(server) == signature(old),
                        'server_ast_matches_update': signature(server) == signature(update),
                        'local_change_diff': ''.join(diff)})
    if total_lines > 250:
        return {'details_complete': False, 'code': 'FUNCTION_DIFF_DETAILS_LIMIT',
                'diff_lines': total_lines, 'functions': changed}
    return {'details_complete': True, 'details_kind': 'function_local_diffs',
            'code_format': 'normalized_python_ast',
            'private_literals_and_comments_redacted': True,
            'original_merge_remains_blocked': True, 'functions': reports}


def function_ast(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.dump(node, include_attributes=False)
    return None


def startup_fingerprints(source):
    names = {'init_db', '_startup_num', '_startup_repair_saved_estimate_adjustments',
             'DEFAULT_MATERIAL_NORMS', 'SITE_PRICE_RULE_DEFAULTS', 'OWN_EXPENSE_NO_PROJECT_CATEGORY'}
    found = {}
    for node in ast.parse(source).body:
        targets = [node.name] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else (
            [target.id for target in node.targets if isinstance(target, ast.Name)] if isinstance(node, ast.Assign) else [])
        for name in targets:
            if name in names:
                found[name] = digest(ast.dump(node, include_attributes=False).encode())
    return found


def inspect(root, fetch=fetch_source, details=False):
    before = {path: read_current(root, path) for path in SOURCES}
    report = []
    init_unchanged = None
    startup = {'evaluated': False}
    for path, pins in SOURCES.items():
        base = fetch(BASE, path, pins['base'])
        incoming = fetch(TARGET, path, pins['target'])
        # Keep verification at this boundary too, including injected test fetchers.
        if digest(base) != pins['base'] or digest(incoming) != pins['target']:
            raise ValueError('PINNED_SOURCE_HASH_MISMATCH')
        status, merged = merge_source(before[path], base, incoming, python_functions=path == 'backend/main.py')
        if path == 'backend/main.py' and before[path] is not None:
            current_startup = startup_fingerprints(before[path])
            expected_startup = startup_fingerprints(incoming)
            startup = {'evaluated': True, 'current_ast_sha256': current_startup,
                       'matches_reviewed_target': len(current_startup) == 6 and current_startup == expected_startup,
                       'data_effects_checked': False}
        if merged is not None and path.endswith('.py'):
            compile(merged, path, 'exec')  # Syntax only: no execution or imports.
        if path == 'backend/main.py' and merged is not None:
            original = function_ast(before[path], 'init_db') if before[path] else None
            init_unchanged = original is not None and original == function_ast(merged, 'init_db')
            if not init_unchanged:
                status = 'startup_code_requires_review'
        row = {'path': path, 'status': status,
               'current_sha256': digest(before[path]),
               'candidate_sha256': digest(merged)}
        if status == 'applicable_verified_function_merge':
            row['merge_proof'] = {'edited_functions_match_pinned_base_or_update': True,
                                  'unrelated_source_bytes_preserved': True,
                                  'server_comments_preserved': True}
        if details and status == 'conflict' and path == 'backend/main.py':
            row['conflict_details'] = describe_conflict(before[path], base, incoming)
        report.append(row)
    stable = all(read_current(root, path) == value for path, value in before.items())
    applicable = stable and all(row['status'] in (
        'already_present', 'applicable', 'applicable_preserving_local_changes',
        'applicable_verified_function_merge') for row in report)
    return {'read_only_app': True, 'report_complete': True,
            'application_files_changed': False, 'services_changed': False,
            'database_accessed': False, 'source_stable_during_check': stable,
            'text_merge_applicable': applicable and all(row['status'] != 'applicable_verified_function_merge' for row in report),
            'source_merge_applicable': applicable, 'init_db_code_unchanged': init_unchanged,
            'startup_source_compatibility': startup,
            'startup_data_gate': 'NOT_EVALUATED', 'maintenance_quiescence': 'NOT_ESTABLISHED',
            'merged_application_tests': 'NOT_RUN', 'installation_ready': False,
            'files': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path('/var/www/stroyka-app'))
    parser.add_argument('--conflict-details', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.app.resolve(), details=args.conflict_details), ensure_ascii=False))
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
