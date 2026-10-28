#!/usr/bin/env python3
"""Read-only installed bridge inventory. Never execute/import worker or read env.

The source view is deliberately redacted and is NOT executable or a complete v1
compatibility proof. It identifies schema declarations and relevant control flow
without printing literal credentials, personal IDs, or private configuration.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess

WORKER = Path('/usr/local/libexec/hermes-jev-bridge/worker.py')
DIRECTORIES = ('/root/hermes-data/jev-bridge', '/root/hermes-data/jev-bridge/requests',
               '/root/hermes-data/jev-bridge/results', '/opt/data/jev-bridge')
UNITS = ('hermes-jev-search.service', 'hermes-jev-search.timer', 'hermes-jev-search.path')
PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'UnitFileState', 'User', 'Group', 'FragmentPath')


def metadata(path):
    try:
        value = {'exists': path.exists(), 'is_symlink': path.is_symlink()}
        if value['exists']:
            info = path.stat()
            value.update(uid=info.st_uid, gid=info.st_gid, mode=oct(stat.S_IMODE(info.st_mode)), size=info.st_size)
        return value
    except PermissionError:
        return {'exists': None, 'code': 'permission_denied'}


def inspect_worker(path):
    report = metadata(path)
    report['schema_compatibility_verified'] = False
    if not report['exists']:
        return report
    if any(node.is_symlink() for node in (path, *path.parents)) or not path.is_file():
        report['code'] = 'SOURCE_LINK_OR_NONREGULAR_FILE'
        return report
    if report['size'] > 256 * 1024:
        report['code'] = 'SOURCE_SIZE_LIMIT'
        return report
    raw = path.read_bytes()
    report['sha256'] = hashlib.sha256(raw).hexdigest()
    tree = ast.parse(raw)
    schemas = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name) and 'field' in target.id.casefold()]
        if not names:
            continue
        try:
            if isinstance(node.value, ast.Dict):
                fields = [ast.literal_eval(key) for key in node.value.keys]
            else:
                fields = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
        if not isinstance(fields, (set, tuple, list)) or not 1 <= len(fields) <= 64:
            continue
        if not all(isinstance(field, str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', field) for field in fields):
            continue
        for name in names:
            schemas[name] = sorted(set(fields))
    public_fields = set().union(*map(set, schemas.values())) if schemas else set()
    request_names = ('request', 'payload', 'data', 'job', 'req')
    accessed = set()
    for node in ast.walk(tree):
        key = None
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'get' and isinstance(node.func.value, ast.Name)
                and node.func.value.id in request_names and node.args):
            key = node.args[0]
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in request_names:
            key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', key.value):
            accessed.add(key.value)
    public_fields.update(accessed)
    report['declared_field_sets'] = schemas
    report['observed_request_field_accesses'] = sorted(accessed)
    class Redact(ast.NodeTransformer):
        def visit_Constant(self, node):
            if node.value is None or type(node.value) is bool:
                return node
            return ast.copy_location(ast.Constant(value='<REDACTED_LITERAL>'), node)
        def visit_Call(self, node):
            # Field names are public protocol keys, not request/config values.
            key = node.args[0] if node.args else None
            known_access = (isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id in request_names
                            and isinstance(key, ast.Constant) and isinstance(key.value, str)
                            and key.value in public_fields)
            value = key.value if known_access else None
            node = self.generic_visit(node)
            if known_access:
                node.args[0] = ast.Constant(value=value)
            return node
        def visit_Subscript(self, node):
            key = node.slice
            known_access = (isinstance(node.value, ast.Name) and node.value.id in request_names
                            and isinstance(key, ast.Constant) and isinstance(key.value, str)
                            and key.value in public_fields)
            value = key.value if known_access else None
            node = self.generic_visit(node)
            if known_access:
                node.slice = ast.Constant(value=value)
            return node
    candidates = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and any(isinstance(item, ast.Constant) and item.value == 'invalid_fields' for item in ast.walk(node))]
    if not candidates:
        candidates = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and re.search('valid|request|schema|parse', node.name, re.I)][:4]
    report['request_functions'] = []
    budget = 24000
    for node in candidates[:4]:
        view = ast.unparse(Redact().visit(copy.deepcopy(node)))
        report['request_functions'].append({'name': node.name, 'line': node.lineno,
            'redacted_source': view[:budget], 'truncated': len(view) > budget})
        budget -= min(len(view), budget)
        if budget <= 0:
            break
    report['source_view'] = 'REDACTED_AUDIT_ONLY_NOT_EXECUTABLE'
    return report


def container_inventory():
    docker = shutil.which('docker')
    if docker is None:
        return {'available': False, 'containers': []}
    environment = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'LANG':'C.UTF-8'}
    names = subprocess.run([docker, 'ps', '--all', '--format', '{{.Names}}'],
                           capture_output=True, text=True, timeout=10, env=environment)
    if names.returncode:
        return {'available':False, 'code':'docker_metadata_unavailable', 'containers':[]}
    results = []
    for name in names.stdout.splitlines():
        if 'hermes' not in name.casefold() or not re.fullmatch('[A-Za-z0-9_.-]{1,128}', name):
            continue
        if len(results) >= 4:
            break
        observed = subprocess.run([docker, 'inspect', '--format',
            '{"user":{{json .Config.User}},"status":{{json .State.Status}},"pid":{{json .State.Pid}},"mounts":{{json .Mounts}}}', name],
            capture_output=True, text=True, timeout=10, env=environment)
        if observed.returncode:
            results.append({'name':name, 'code':'metadata_unavailable'})
            continue
        value=json.loads(observed.stdout)
        row={'name':name,'configured_user':value.get('user'),'status':value.get('status'),
             'bridge_mounts':[], 'real_hermes_result_read_access':'NOT_TESTED'}
        for mount in value.get('mounts') or []:
            destination=mount.get('Destination','')
            if destination in ('/opt/data','/opt/data/jev-bridge'):
                row['bridge_mounts'].append({'source':mount.get('Source'), 'destination':destination,'rw':mount.get('RW')})
        results.append(row)
    return {'available':True, 'containers':results}


def collect():
    report = {'read_only': True, 'hostname':socket.gethostname(), 'services_changed': False, 'search_executed': False,
              'database_accessed': False, 'configuration_values_read': False,
              'worker': inspect_worker(WORKER),
              'directories': {name: metadata(Path(name)) for name in DIRECTORIES}, 'units': {}}
    for unit in UNITS:
        result = subprocess.run(['/usr/bin/systemctl', 'show', unit, '--no-pager',
            *[argument for prop in PROPERTIES for argument in ('-p', prop)]],
            capture_output=True, text=True, timeout=10,
            env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'})
        value = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        report['units'][unit] = {key:value[key] for key in PROPERTIES if key in value}
        report['units'][unit]['query_returncode'] = result.returncode
    report['hermes_containers'] = container_inventory()
    return report


def main():
    try:
        print(json.dumps(collect(), ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({'read_only':True, 'report_complete':False, 'code':type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
