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
import os
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


def validation_contract(tree):
    """Static public grammar only; never emit config, request, or credential values."""
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == 'validate']
    report = {'observed_only': True, 'complete': False, 'exact_field_sets': [],
              'version_checks': [], 'source_choices': [], 'topic_selectors': [], 'topic_length_checks': [],
              'return_field_sets': []}
    def string_values(node):
        if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            return None
        values = [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if len(values) != len(node.elts) or len(values) > 64:
            return None
        if not all(re.fullmatch('[A-Za-z_А-Яа-яЁё][A-Za-z0-9_А-Яа-яЁё -]{0,79}', value) for value in values):
            return None
        return values
    for function in functions:
        argument = function.args.args[0].arg if function.args.args else None
        for node in ast.walk(function):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                fields = string_values(ast.List(elts=node.value.keys, ctx=ast.Load()))
                if fields is not None:
                    report['return_field_sets'].append(sorted(fields))
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            for left, operation, right in zip(operands, node.ops, operands[1:]):
                if (isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == 'set'
                        and len(left.args) == 1 and isinstance(left.args[0], ast.Name) and left.args[0].id == argument):
                    fields = string_values(right)
                    if fields is not None and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,63}', item) for item in fields):
                        report['exact_field_sets'].append({'operator':type(operation).__name__, 'fields':sorted(fields)})
                if (isinstance(left, ast.Subscript) and isinstance(left.value, ast.Name)
                        and left.value.id == argument and isinstance(left.slice, ast.Constant)
                        and left.slice.value == 'version' and isinstance(right, ast.Constant)
                        and type(right.value) is int and 0 <= right.value <= 99):
                    report['version_checks'].append({'operator':type(operation).__name__, 'value':right.value})
                if isinstance(left, ast.Name) and left.id == 'topics':
                    choices = string_values(right)
                    if choices is not None:
                        report['topic_selectors'].append({'operator':type(operation).__name__, 'values':choices})
                if isinstance(operation, (ast.In, ast.NotIn)) and isinstance(left, ast.Name):
                    choices = string_values(right)
                    # Only literal choices inside a generator iterating `sources`.
                    if choices is not None and any(isinstance(parent, (ast.GeneratorExp, ast.ListComp))
                            and any(isinstance(item.iter, ast.Name) and item.iter.id == 'sources' for item in parent.generators)
                            and any(child is node for child in ast.walk(parent)) for parent in ast.walk(function)):
                        report['source_choices'].append({'operator':type(operation).__name__, 'values':choices})
            if any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == 'len'
                   and len(item.args) == 1 and isinstance(item.args[0], ast.Name) and item.args[0].id == 'topics'
                   for item in operands):
                numbers = [item.value for item in operands if isinstance(item, ast.Constant)
                           and type(item.value) is int and 0 <= item.value <= 64]
                report['topic_length_checks'].append({'operators':[type(item).__name__ for item in node.ops], 'numbers':numbers})
    report['topic_keys'] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if 'REGION' in names and isinstance(node.value, ast.Constant):
            report['region_is_stavropol'] = node.value.value == 'Ставропольский край'
        if 'REQUEST_RE' in names and isinstance(node.value, ast.Call) and (
                isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == 're' and node.value.func.attr == 'compile'
                and node.value.args and isinstance(node.value.args[0], ast.Constant)
                and isinstance(node.value.args[0].value, str) and len(node.value.args[0].value) <= 256):
            # This is the public identifier grammar, never a request ID or config value.
            report['request_id_pattern'] = node.value.args[0].value
            report['request_id_pattern_flags_ast'] = [ast.unparse(arg) for arg in node.value.args[1:]
                                                      if isinstance(arg, (ast.Name, ast.Attribute))]
        if 'TOPICS' in names and isinstance(node.value, ast.Dict):
            values = string_values(ast.List(elts=node.value.keys, ctx=ast.Load()))
            if values is not None:
                report['topic_keys'] = sorted(values)
    return report


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
    request_names = ('request', 'payload', 'data', 'job', 'req', 'raw')
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
    report['validation_contract'] = validation_contract(tree)
    report['literal_cli_shapes'] = []
    safe_tokens = {'stroyka-jev', 'sudo', '-n', 'commercial-search', 'eis-search',
                   '--query', '--profile-stdin', '--stavropol-open', 'status'}
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call) or not call.args or not isinstance(call.args[0], (ast.List, ast.Tuple)):
            continue
        elements = call.args[0].elts
        if not any(isinstance(item, ast.Constant) and isinstance(item.value, str)
                   and (item.value == 'stroyka-jev' or item.value.endswith('/stroyka-jev')) for item in elements):
            continue
        shape=[]
        for item in elements:
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value in safe_tokens:
                shape.append(item.value)
            elif isinstance(item, ast.Name):
                shape.append({'variable':item.id})
            else:
                shape.append('<REDACTED_ARGUMENT>')
        report['literal_cli_shapes'].append({'arguments':shape,
            'stdin_keyword_present':any(item.arg == 'input' for item in call.keywords)})
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
    report['operational_functions'] = []
    seen = {node.lineno for node in candidates[:4]}
    budget = 24000
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.lineno in seen:
            continue
        if not re.search('main|process|dispatch|run|atomic|write|save|result|queue|claim|lock|notify', node.name, re.I):
            continue
        view = ast.unparse(Redact().visit(copy.deepcopy(node)))
        report['operational_functions'].append({'name':node.name, 'line':node.lineno,
            'redacted_source':view[:budget], 'truncated':len(view)>budget})
        budget -= min(len(view), budget)
        if budget <= 0:
            break
    report['source_stable_during_audit'] = hashlib.sha256(path.read_bytes()).hexdigest() == report['sha256']
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
            '{"user":{{json .Config.User}},"status":{{json .State.Status}},"pid":{{json .State.Pid}},"privileged":{{json .HostConfig.Privileged}},"mounts":{{json .Mounts}}}', name],
            capture_output=True, text=True, timeout=10, env=environment)
        if observed.returncode:
            results.append({'name':name, 'code':'metadata_unavailable'})
            continue
        value=json.loads(observed.stdout)
        row={'name':name,'configured_user':value.get('user'),'status':value.get('status'),
             'bridge_mounts':[], 'privileged':value.get('privileged'), 'risky_mount_kinds':[],
             'real_hermes_result_read_access':'NOT_TESTED'}
        processes = subprocess.run([docker, 'top', name, '-eo', 'pid,euid,egid,comm'],
                                  capture_output=True, text=True, timeout=10, env=environment)
        row['process_credentials'] = []
        if processes.returncode == 0:
            for line in processes.stdout.splitlines()[1:129]:
                fields = line.split()
                if len(fields) == 4 and all(value.isdecimal() for value in fields[:3]):
                    row['process_credentials'].append({'host_pid':int(fields[0]),'euid':int(fields[1]),
                                                       'egid':int(fields[2]),'executable_name':fields[3]})
        row['process_credentials_complete'] = processes.returncode == 0 and (
            len(row['process_credentials']) == max(0,len(processes.stdout.splitlines())-1))
        for mount in value.get('mounts') or []:
            destination=mount.get('Destination','')
            source=mount.get('Source','')
            if source in ('/var/run/docker.sock','/run/docker.sock') or destination in ('/var/run/docker.sock','/run/docker.sock'):
                row['risky_mount_kinds'].append('docker_socket')
            if source == '/':
                row['risky_mount_kinds'].append('host_root')
            if any('/.ssh' in path for path in (source,destination)):
                row['risky_mount_kinds'].append('ssh_material')
            if source == '/var/www/stroyka-app' or source.startswith('/var/www/stroyka-app/'):
                row['risky_mount_kinds'].append('app_installation')
            if destination in ('/opt/data','/opt/data/jev-bridge'):
                row['bridge_mounts'].append({'source':mount.get('Source'), 'destination':destination,'rw':mount.get('RW')})
        results.append(row)
    return {'available':True, 'containers':results}


def result_permissions(path):
    """Aggregate file metadata only: no names, IDs, or file contents are emitted."""
    if not path.is_dir():
        return {'exists':False}
    counts = {}
    skipped_links = 0
    disappeared = 0
    with os.scandir(path) as entries:
        for observed,file in enumerate(entries):
            if observed >= 2000:
                return {'mode_counts':counts,'symlinks_skipped':skipped_links,'complete':False,'code':'FILE_METADATA_LIMIT'}
            if not file.name.endswith('.json'):
                continue
            if file.is_symlink():
                skipped_links += 1
                continue
            try:
                info=file.stat(follow_symlinks=False)
            except FileNotFoundError:
                disappeared += 1
                continue
            if stat.S_ISREG(info.st_mode):
                key='%s:%s:%s' % (info.st_uid,info.st_gid,oct(stat.S_IMODE(info.st_mode)))
                counts[key]=counts.get(key,0)+1
    return {'mode_counts':counts,'symlinks_skipped':skipped_links,'complete':True,
            'files_disappeared_during_audit':disappeared,
            'real_hermes_result_read_access':'NOT_TESTED'}


def runtime_cli_inventory():
    result = {}
    root = Path('/usr/local/libexec/stroyka-jev-control')
    for name in ('jev_server_tools.py','jev_commercial_search.py','jev_eis_probe.py'):
        path=root/name
        value=metadata(path)
        result[name]=value
        if not value.get('exists') or value.get('is_symlink') or not path.is_file() or value['size']>256*1024:
            continue
        raw=path.read_bytes()
        value['sha256']=hashlib.sha256(raw).hexdigest()
        tree=ast.parse(raw)
        value['parser_flags']=sorted({node.args[0].value for node in ast.walk(tree)
             if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument'
             and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)
             and re.fullmatch('--[a-z][a-z0-9-]{0,63}',node.args[0].value)})
        value['observed_only_not_execution_proof']=True
    return result


def collect():
    report = {'read_only': True, 'hostname':socket.gethostname(), 'services_changed': False, 'search_executed': False,
              'database_accessed': False, 'configuration_files_read': False,
              'worker': inspect_worker(WORKER),
              'directories': {name: metadata(Path(name)) for name in DIRECTORIES}, 'units': {}}
    for unit in UNITS:
        result = subprocess.run(['/usr/bin/systemctl', 'show', unit, '--no-pager',
            *[argument for prop in (*PROPERTIES, 'ExecStart', 'TimersMonotonic', 'TimersCalendar') for argument in ('-p', prop)]],
            capture_output=True, text=True, timeout=10,
            env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'})
        value = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        report['units'][unit] = {key:value[key] for key in PROPERTIES if key in value}
        if value.get('ExecStart'):
            report['units'][unit]['exec_start_sha256']=hashlib.sha256(value['ExecStart'].encode()).hexdigest()
            report['units'][unit]['contains_expected_worker_path']=str(WORKER) in value['ExecStart']
        for key in ('TimersMonotonic','TimersCalendar'):
            if key in value:
                report['units'][unit][key]=value[key]
        report['units'][unit]['query_returncode'] = result.returncode
    report['hermes_containers'] = container_inventory()
    report['result_file_permissions'] = result_permissions(Path('/root/hermes-data/jev-bridge/results'))
    report['runtime_cli'] = runtime_cli_inventory()
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
