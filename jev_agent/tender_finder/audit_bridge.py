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
import sys

WORKER = Path('/usr/local/libexec/hermes-jev-bridge/worker.py')
DIRECTORIES = ('/root/hermes-data/jev-bridge', '/root/hermes-data/jev-bridge/requests',
               '/root/hermes-data/jev-bridge/results', '/opt/data/jev-bridge')
UNITS = ('hermes-jev-search.service', 'hermes-jev-search.timer', 'hermes-jev-search.path')
PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'UnitFileState', 'User', 'Group', 'FragmentPath')
# Reviewed source revisions, not a claim about the installed files until hashes match.
REVIEWED_RUNTIME = {
    'jev_server_tools.py': ('757799e129c108b5407674590f1c4cb572defc208c03c7b0fbc6c89a7ad966f5', 'acb1a3838a13cb650440340a774be46f1a3830a8'),
    'jev_commercial_search.py': ('c73b7a1111f948c083eda7967e4b301ac8175cd45a2b08c01af81f6867e753cc', 'acb1a3838a13cb650440340a774be46f1a3830a8'),
    'jev_eis_probe.py': ('a9175836648e1064c9b255fdc9d2b3b9bdeff8c246f11173760a761f12348fc4', 'e3d08744f07522040dcbd8580ef7f29906daa562'),
}
OPTIONAL_REVIEWED_RUNTIME = {
    'jev_eis_review_runner.py': 'abcad9238cf33264c0c0b2feb02580668ae21a4c8849f198d641ab8f0cd82a43',
    'jev_eis_documents.py': 'e099b7d2dfde271ea08e4a1711eeb9df467cb0a132c56fcf19a9c247d2e7c8c4',
    'jev_eis_document_report.py': '9b4d032dc21dd5a6b6e78e87970210c002db9bb09da278c6f33492a4c9d86a76',
    'jev_eis_document_model.py': '78880f6c6cc78e4ceec57b53720713c7b0f13847157200f444e7574fba198d12',
}


def public_image_metadata(value):
    """Emit only bounded OCI revision/version/public repository identifiers."""
    result = {}
    for key, pattern in (
        ('image_id', r'sha256:[a-f0-9]{64}'),
        ('revision', r'[a-f0-9]{40}|[a-f0-9]{64}'),
        ('version', r'v?[0-9][A-Za-z0-9._+-]{0,39}'),
        ('source', r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?')):
        observed = value.get(key)
        if isinstance(observed,str) and re.fullmatch(pattern,observed):
            result[key] = observed
    result['installed_version_verified'] = False
    return result


def _read_relative_source(root, relative, maximum):
    """Fixed public source paths only, anchored to the container root descriptor."""
    parts=Path(relative).parts
    if not parts or any(part in ('/','..','.') for part in parts):
        return None
    descriptors=[]
    try:
        parent=root
        for part in parts[:-1]:
            parent=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            descriptors.append(parent)
        file=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        descriptors.append(file)
        info=os.fstat(file)
        if not stat.S_ISREG(info.st_mode) or info.st_size>maximum:return None
        with os.fdopen(file,'rb',closefd=False) as stream:
            data=stream.read(maximum+1)
        return data if len(data)<=maximum else None
    except OSError:
        return None
    finally:
        for descriptor in reversed(descriptors):os.close(descriptor)


def hermes_source_inventory(pid):
    """No exec, env, cmdline, history, sessions, .env, git config or tokens.

    Read only pyproject/git revision and named public source modules. All source
    literal/default values are omitted; signatures alone do not prove a send API.
    """
    report={'process_id':pid,'source_modules':[], 'notification_binding_verified':False,
            'application_secrets_read':False,'public_project_metadata_only':True,
            'cmdline_read':False,'commands_executed':False}
    if type(pid) is not int or pid<=0:
        report['code']='HERMES_PROCESS_NOT_IDENTIFIED';return report
    paths=['/opt/hermes','/opt/hermes-agent','/app','/app/hermes-agent']
    try:
        cwd=os.readlink(f'/proc/{pid}/cwd')
        if (re.fullmatch(r'/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+',cwd)
                and cwd.startswith(('/opt/','/app/','/usr/src/')) and '..' not in Path(cwd).parts):
            paths.insert(0,cwd)
        root=os.open(f'/proc/{pid}/root',os.O_RDONLY|os.O_DIRECTORY)
    except OSError:
        report['code']='CONTAINER_SOURCE_UNAVAILABLE';return report
    try:
        for source in dict.fromkeys(paths):
            relative=source.lstrip('/')
            head=_read_relative_source(root,relative+'/.git/HEAD',256)
            if head:
                value=head.decode('ascii',errors='replace').strip()
                if value.startswith('ref: '):
                    ref=value[5:]
                    if re.fullmatch(r'refs/heads/[A-Za-z0-9_./-]{1,120}',ref) and '..' not in Path(ref).parts:
                        raw=_read_relative_source(root,relative+'/.git/'+ref,128)
                        value=raw.decode('ascii',errors='replace').strip() if raw else ''
                if re.fullmatch('[a-f0-9]{40}|[a-f0-9]{64}',value):
                    report.setdefault('repository_revisions',[]).append({'source_root':source,'revision':value})
            project=_read_relative_source(root,relative+'/pyproject.toml',128*1024)
            if project:
                # Parse only project metadata; do not emit dependency URLs/config.
                try:
                    import tomllib
                    metadata=tomllib.loads(project.decode('utf-8')).get('project',{})
                    observed={}
                    for key,pattern in (('name',r'[A-Za-z0-9_.-]{1,80}'),('version',r'[0-9][A-Za-z0-9_.+-]{0,39}')):
                        if isinstance(metadata.get(key),str) and re.fullmatch(pattern,metadata[key]):observed[key]=metadata[key]
                    report.setdefault('projects',[]).append({'source_root':source,**observed})
                except (ImportError,ValueError,UnicodeError,AttributeError):
                    pass
            for module in ('tools/send_message_tool.py','gateway/run.py','gateway/platforms/telegram.py','hermes_cli/main.py'):
                raw=_read_relative_source(root,relative+'/'+module,256*1024)
                if raw is None:continue
                value={'source_root':source,'module':module,'sha256':hashlib.sha256(raw).hexdigest(),
                       'entrypoints':[]}
                try:
                    tree=ast.parse(raw)
                    for node in ast.walk(tree):
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and re.search('send|deliver|notify|dispatch|main',node.name,re.I):
                            args=[arg.arg for arg in (*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs)]
                            value['entrypoints'].append({'name':node.name,'async':isinstance(node,ast.AsyncFunctionDef),
                                                         'parameters':args,'defaults':'OMITTED'})
                            if len(value['entrypoints'])>=32:break
                except (SyntaxError,ValueError,UnicodeError):
                    value['code']='SOURCE_NOT_PYTHON'
                report['source_modules'].append(value)
    finally:
        os.close(root)
    if not report['source_modules']:report['code']='PUBLIC_SOURCE_NOT_FOUND'
    return report


def collect_hermes_interface():
    containers=container_inventory()
    readers=[]
    for container in containers.get('containers',[]):
        for process in container.get('process_credentials',[]):
            if process.get('executable_name')=='hermes':
                readers.append(hermes_source_inventory(process.get('host_pid')))
    return {'read_only':True,'hostname':socket.gethostname(),'services_changed':False,
            'search_executed':False,'model_called':False,'notifications_sent':False,
            'hermes_sources':readers,'notification_binding_verified':False,'installation_ready':False}


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
    executable_names = set()
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str) and node.value.value.endswith('/stroyka-jev')):
            executable_names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    for sequence in ast.walk(tree):
        if not isinstance(sequence, (ast.List, ast.Tuple)):
            continue
        elements = sequence.elts
        if not any(isinstance(item, ast.Constant) and isinstance(item.value, str)
                   and (item.value == 'stroyka-jev' or item.value.endswith('/stroyka-jev'))
                   or isinstance(item, ast.Name) and item.id in executable_names for item in elements):
            continue
        shape=[]
        for item in elements:
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value in safe_tokens:
                shape.append(item.value)
            elif isinstance(item, ast.Name):
                shape.append({'variable':item.id})
            else:
                shape.append('<REDACTED_ARGUMENT>')
        call = next((node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and node.args and node.args[0] is sequence), None)
        report['literal_cli_shapes'].append({'arguments':shape,
            'stdin_keyword_present':any(item.arg == 'input' for item in call.keywords) if call else None})
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
        if not re.search('main|process|dispatch|execute|run|atomic|put_json|read_req|safe_dir|write|save|result|queue|claim|lock|notify', node.name, re.I):
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
            '{"user":{{json .Config.User}},"status":{{json .State.Status}},"pid":{{json .State.Pid}},"privileged":{{json .HostConfig.Privileged}},"mounts":{{json .Mounts}},"image_id":{{json .Image}},"version":{{json (index .Config.Labels "org.opencontainers.image.version")}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},"source":{{json (index .Config.Labels "org.opencontainers.image.source")}}}', name],
            capture_output=True, text=True, timeout=10, env=environment)
        if observed.returncode:
            results.append({'name':name, 'code':'metadata_unavailable'})
            continue
        value=json.loads(observed.stdout)
        row={'name':name,'configured_user':value.get('user'),'status':value.get('status'),
             'bridge_mounts':[], 'privileged':value.get('privileged'), 'risky_mount_kinds':[],
             'real_hermes_result_read_access':'NOT_TESTED','image_metadata':public_image_metadata(value)}
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


def runtime_source(path, allowed_roots=(Path('/opt/stroyka-jev-tools'), Path('/usr/local/libexec')), *, trusted_uid=0):
    """Inspect known source modules through root-owned release symlinks only.

    This is source inventory, not approval to execute a runtime. Never import it.
    """
    value = metadata(path)
    try:
        resolved = path.resolve(strict=True)
        logical_root = next((root for root in allowed_roots if path.is_relative_to(root)), None)
        target_root = next((root for root in allowed_roots if resolved.is_relative_to(root)), None)
        if logical_root is None or target_root is None:
            value['code'] = 'UNTRUSTED_SOURCE_PATH'
            return value
        # Check both sides of a release link. Symlink mode 0777 is normal; its
        # owner and its containing directories must still be protected.
        for candidate, boundary in ((path, logical_root), (resolved, target_root)):
            for node in (candidate, *candidate.parents):
                info = node.lstat()
                if info.st_uid != trusted_uid or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
                    value['code'] = 'UNTRUSTED_SOURCE_PERMISSIONS'
                    return value
                if node == boundary:
                    break
        fd = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > 256 * 1024:
                value['code'] = 'SOURCE_SIZE_OR_TYPE'
                return value
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(256 * 1024 + 1)
            after = os.fstat(fd)
        finally:
            os.close(fd)
        if (len(raw) > 256 * 1024 or path.resolve(strict=True) != resolved
                or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns)):
            value['code'] = 'SOURCE_CHANGED_DURING_AUDIT'
            return value
        value['resolved_path'] = str(resolved)
        value['sha256'] = hashlib.sha256(raw).hexdigest()
        if path.name in REVIEWED_RUNTIME:
            expected, revision = REVIEWED_RUNTIME[path.name]
            value['matches_reviewed_source'] = value['sha256'] == expected
            value['reviewed_revision'] = revision
        elif path.name in OPTIONAL_REVIEWED_RUNTIME:
            value['matches_reviewed_source'] = value['sha256'] == OPTIONAL_REVIEWED_RUNTIME[path.name]
            value['reviewed_revision'] = 'e3d08744f07522040dcbd8580ef7f29906daa562'
        tree = ast.parse(raw)
        value['parser_flags'] = sorted({node.args[0].value for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument'
             and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
             and re.fullmatch('--[a-z][a-z0-9-]{0,63}', node.args[0].value)})
        value['observed_only_not_execution_proof'] = True
    except (OSError, RuntimeError, SyntaxError) as exc:
        value['code'] = type(exc).__name__
    return value


def runtime_cli_inventory():
    result = {}
    root = Path('/usr/local/libexec/stroyka-jev-control')
    paths = {root/name for name in ('jev_server_tools.py','jev_commercial_search.py','jev_eis_probe.py')}
    entrypoint = shutil.which('stroyka-jev')
    if entrypoint:
        entry = Path(entrypoint)
        result['entrypoint'] = {'path': str(entry), **metadata(entry), 'executed': False}
        resolved = entry.resolve()
        if resolved.is_file() and resolved.stat().st_size <= 64 * 1024:
            wrapper = resolved.read_bytes()
            result['entrypoint']['sha256'] = hashlib.sha256(wrapper).hexdigest()
            if resolved.name == 'jev_server_tools.py':
                paths.add(resolved)
            # Inspect only literal paths to the known runtime module, not arbitrary files.
            for match in re.findall(rb'(/(?:[A-Za-z0-9_.-]+/)+jev_server_tools\.py)', wrapper):
                candidate = Path(match.decode('ascii'))
                if str(candidate).startswith(('/usr/local/libexec/', '/opt/')):
                    paths.add(candidate)
    for tools in tuple(paths):
        if tools.name == 'jev_server_tools.py':
            paths.update(tools.parent/name for name in ('jev_commercial_search.py','jev_eis_probe.py',*OPTIONAL_REVIEWED_RUNTIME))
    for path in sorted(paths):
        result[str(path)] = runtime_source(path)
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


def collect_integration_requirements():
    """Focused report: no worker AST, request/result content, env, or paid calls."""
    return {'read_only':True,'hostname':socket.gethostname(),'services_changed':False,
            'search_executed':False,'model_called':False,'notifications_sent':False,
            'database_accessed':False,'runtime_cli':runtime_cli_inventory(),
            'hermes_containers':container_inventory(),'notification_binding_verified':False,
            'reviewed_eis_review_operation':{'search_only':False,'downloads_documents':True,
                                            'writes_snapshots':True,'invokes_model':True},
            'installation_ready':False}


def main():
    try:
        if sys.argv[1:] not in ([],['--integration'],['--hermes-interface']):
            raise ValueError('unsupported_audit_arguments')
        value=(collect_hermes_interface() if sys.argv[1:]==['--hermes-interface'] else
               collect_integration_requirements() if sys.argv[1:] else collect())
        print(json.dumps(value,ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({'read_only':True, 'report_complete':False, 'code':type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
