#!/usr/bin/env python3
"""Plan or explicitly install reversible, metadata-only invoice failure logging."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile
import time
import zlib

TARGET = Path('backend/features/model_gateway/yandex_adapter.py')
MARKER = 'STROYKA_INVOICE_PROVIDER_DIAG'


class Stop(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Stop(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tool_source():
    return globals().get('_STROYKA_OPERATOR_SOURCE') or Path(__file__).read_text()


def delivery_command(expected_head):
    require(re.fullmatch(r'[0-9a-f]{8,40}', expected_head or '') is not None, 'expected_head_required')
    source = tool_source().encode('utf-8')
    payload = base64.b64encode(zlib.compress(source, 9)).decode('ascii')
    bootstrap = ('import base64,zlib,hashlib; s=zlib.decompress(base64.b64decode(' + json.dumps(payload)
                 + ')); assert hashlib.sha256(s).hexdigest()==' + json.dumps(digest(source))
                 + '; exec(compile(s,"invoice_provider_status_patch.py","exec"),'
                   '{"__name__":"__main__","_STROYKA_OPERATOR_SOURCE":s.decode("utf-8")})')
    return shlex.join(['python3', '-B', '-c', bootstrap, '--apply', '--expect-head', expected_head])


def instrument(source):
    require(MARKER not in source, 'diagnostic_already_present')
    tree = ast.parse(source)
    methods = [method for cls in tree.body if isinstance(cls, ast.ClassDef)
               and cls.name == 'YandexModelAdapter' for method in cls.body
               if isinstance(method, ast.FunctionDef) and method.name == 'generate']
    require(len(methods) == 1, 'unsupported_adapter')
    method = methods[0]
    require([arg.arg for arg in method.args.args] == ['self', 'request'], 'unsupported_signature')
    handlers = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Try) or len(node.body) != 1 or not isinstance(node.body[0], ast.Assign):
            continue
        call = node.body[0].value
        if not isinstance(call, ast.Call) or ast.unparse(call.func) != 'self._client.responses.create':
            continue
        handlers.extend(handler for handler in node.handlers
                        if isinstance(handler.type, ast.Name) and handler.type.id == 'Exception')
    require(len(handlers) == 1, 'unsupported_exception_handler')
    handler = handlers[0]
    require(any(isinstance(node, ast.Continue) for statement in handler.body
                for node in ast.walk(statement)), 'unsupported_retry_flow')
    names = {node.id for node in ast.walk(method) if isinstance(node, ast.Name)}
    require(not any(name.startswith('_stroyka_diag_') for name in names), 'diagnostic_name_conflict')
    lines = source.splitlines(keepends=True)
    index = handler.lineno - 1
    header = lines[index]
    require(re.fullmatch(r' *except Exception(?: as [A-Za-z_][A-Za-z_0-9]*)?:\s*\n', header) is not None,
            'unsupported_exception_header')
    indent = header[:len(header) - len(header.lstrip())] + '    '
    error = handler.name or '_stroyka_diag_error'
    if handler.name is None:
        lines[index] = header.replace('except Exception:', 'except Exception as ' + error + ':')
    block = '''if request.capability == "invoice_scan":
    try:
        _stroyka_diag_status = getattr(ERROR, "status_code", None)
        _stroyka_diag_kind = type(ERROR).__name__
        _stroyka_diag_body = str(getattr(ERROR, "body", "")).lower()
        print("STROYKA_INVOICE_PROVIDER_DIAG", {
            "stage": "STAGE",
            "httpStatus": _stroyka_diag_status if type(_stroyka_diag_status) is int and 400 <= _stroyka_diag_status <= 599 else None,
            "exceptionType": _stroyka_diag_kind if _stroyka_diag_kind in ("BadRequestError", "AuthenticationError", "PermissionDeniedError", "NotFoundError", "ConflictError", "UnprocessableEntityError", "RateLimitError", "InternalServerError", "APIConnectionError", "APITimeoutError", "APIStatusError", "APIError", "TypeError", "ValueError") else "other",
            "mentions": [field for field in ("temperature", "max_output_tokens", "image_url", "detail", "model", "input_file", "file_data", "mime", "format", "size", "context_length") if field in _stroyka_diag_body],
            "images": sum(getattr(part, "kind", None) == "image_data_url" for part in getattr(request, "input_parts", ())),
            "files": sum(getattr(part, "kind", None) in ("file_id", "file_data_url") for part in getattr(request, "input_parts", ())),
        }, flush=True)
    except Exception:
        pass
'''
    provider_block = block.replace('ERROR', error).replace('STAGE', 'provider')
    lines.insert(index + 1, ''.join(indent + line + '\n' for line in provider_block.splitlines()))
    patched = ''.join(lines)
    # The runtime helper also maps local adapter exceptions to provider_failed.
    # Report them separately and re-raise the exact original exception.
    tree = ast.parse(patched)
    method = next(method for cls in tree.body if isinstance(cls, ast.ClassDef)
                  and cls.name == 'YandexModelAdapter' for method in cls.body
                  if isinstance(method, ast.FunctionDef) and method.name == 'generate')
    body = method.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    require(bool(body), 'unsupported_method_body')
    lines = patched.splitlines(keepends=True)
    start, end = body[0].lineno - 1, body[-1].end_lineno
    body_indent = ' ' * (method.col_offset + 4)
    outer_error = '_stroyka_diag_outer_error'
    local_block = block.replace('ERROR', outer_error).replace('STAGE', 'adapter')
    replacement = body_indent + 'try:\n' + ''.join('    ' + line for line in lines[start:end])
    if not replacement.endswith('\n'):
        replacement += '\n'
    replacement += body_indent + 'except Exception as ' + outer_error + ':\n'
    replacement += body_indent + '    if not isinstance(' + outer_error + ', ModelGatewayError):\n'
    replacement += ''.join(body_indent + '        ' + line + '\n' for line in local_block.splitlines())
    replacement += body_indent + '    raise\n'
    lines[start:end] = [replacement]
    patched = ''.join(lines)
    compile(patched, '<invoice-provider-diagnostic>', 'exec')
    return patched


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    require(result.returncode == 0, 'git_preflight_failed')
    return result.stdout.strip()


def atomic_write(path, data):
    current = path.stat()
    fd, temporary = tempfile.mkstemp(prefix='.invoice-provider-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, current.st_mode & 0o777)
        if os.geteuid() == 0:
            os.chown(temporary, current.st_uid, current.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def service_operation(service, action):
    args = ['systemctl', 'restart', service] if action == 'restart' else ['systemctl', 'is-active', '--quiet', service]
    result = subprocess.run(args, capture_output=True, timeout=60)
    require(result.returncode == 0, 'service_' + action + '_failed')
    if action == 'restart':
        time.sleep(2)
        service_operation(service, 'check')


def plan(root):
    root = root.resolve()
    path = root / TARGET
    require(not path.is_symlink(), 'symlink_target_refused')
    git(root, 'ls-files', '--error-unmatch', str(TARGET))
    require(not git(root, 'status', '--porcelain', '--', str(TARGET)), 'adapter_has_local_changes')
    before = path.read_bytes()
    after = instrument(before.decode('utf-8')).encode('utf-8')
    return {'head': git(root, 'rev-parse', 'HEAD'), 'beforeHash': digest(before), 'afterHash': digest(after)}, before, after


def restore(root, backup, service='stroyka', operate=service_operation):
    root, backup = root.resolve(), backup.resolve()
    meta = json.loads((backup / 'manifest.json').read_text())
    require(meta['appRoot'] == str(root), 'backup_root_mismatch')
    require(meta['service'] == service, 'backup_service_mismatch')
    require(git(root, 'rev-parse', 'HEAD') == meta['head'], 'head_changed_restore_refused')
    path = root / TARGET
    require(not path.is_symlink() and digest(path.read_bytes()) == meta['afterHash'], 'adapter_changed_restore_refused')
    original = (backup / 'source.py').read_bytes()
    require(digest(original) == meta['beforeHash'], 'backup_hash_mismatch')
    atomic_write(path, original)
    operate(service, 'restart')
    return {'state': 'source_restored', 'backupRetained': str(backup)}


def apply(root, expected_head, backup_root, service='stroyka', operate=service_operation):
    root = root.resolve()
    require(re.fullmatch(r'[0-9a-f]{8,40}', expected_head or '') is not None, 'expected_head_required')
    meta, before, after = plan(root)
    require(meta['head'].startswith(expected_head), 'installed_head_mismatch')
    operate(service, 'check')
    backup = Path(tempfile.mkdtemp(prefix='stroyka-invoice-provider-', dir=backup_root))
    shutil.copy2(root / TARGET, backup / 'source.py')
    require(digest((backup / 'source.py').read_bytes()) == meta['beforeHash'], 'backup_source_changed')
    meta['appRoot'] = str(root)
    meta['service'] = service
    (backup / 'manifest.json').write_text(json.dumps(meta, indent=2))
    (backup / 'invoice_status_tool.py').write_text(tool_source())
    require(git(root, 'rev-parse', 'HEAD') == meta['head']
            and (root / TARGET).read_bytes() == before, 'source_changed_before_apply')
    atomic_write(root / TARGET, after)
    try:
        operate(service, 'restart')
    except Exception:
        try:
            restore(root, backup, service, operate)
        except Exception:
            raise Stop('restart_failed_restore_needs_review_backup_' + str(backup)) from None
        raise Stop('restart_failed_original_restored_backup_' + str(backup)) from None
    return {'state': 'diagnostic_installed_awaiting_scan', 'backup': str(backup), 'head': meta['head'],
            'restoreCommand': shlex.join(['python3', str(backup / 'invoice_status_tool.py'), '--restore', str(backup),
                                         '--app-root', str(root), '--service', service])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--restore', type=Path)
    modes.add_argument('--print-command', action='store_true')
    parser.add_argument('--expect-head')
    parser.add_argument('--backup-root', type=Path, default=Path('/root'))
    parser.add_argument('--service', default='stroyka')
    args = parser.parse_args()
    try:
        if args.print_command:
            print(delivery_command(args.expect_head))
            return 0
        if args.apply:
            result = apply(args.app_root, args.expect_head, args.backup_root, args.service)
        elif args.restore:
            result = restore(args.app_root, args.restore, args.service)
        else:
            meta, _, _ = plan(args.app_root)
            result = dict(meta, state='plan_only')
        print(json.dumps(result))
        return 0
    except Stop as error:
        print(json.dumps({'error': str(error)}))
    except Exception:
        print('{"error":"diagnostic_preflight_unavailable"}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
