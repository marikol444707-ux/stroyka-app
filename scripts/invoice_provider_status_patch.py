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
MAIN_TARGET = Path('backend/main.py')
MARKER = 'STROYKA_INVOICE_PROVIDER_DIAG'
RESPONSE_MARKER = 'STROYKA_INVOICE_RESPONSE_DIAG'


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
    target = Path(meta.get('target', str(TARGET)))
    require(target in (TARGET, MAIN_TARGET), 'unknown_backup_target')
    path = root / target
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
    return install_change(root, meta, before, after, backup_root, service, operate,
                          'diagnostic_installed_awaiting_scan')


def add_image_detail(source):
    tree = ast.parse(source)
    methods = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == '_provider_input']
    require(len(methods) == 1, 'unsupported_image_builder')
    images = [node for node in ast.walk(methods[0]) if isinstance(node, ast.Dict)
              and any(isinstance(key, ast.Constant) and key.value == 'type'
                      and isinstance(value, ast.Constant) and value.value == 'input_image'
                      for key, value in zip(node.keys, node.values))]
    require(len(images) == 1, 'unsupported_image_builder')
    node = images[0]
    require([key.value if isinstance(key, ast.Constant) else None for key in node.keys]
            == ['type', 'image_url'], 'image_detail_already_present_or_unknown')
    require(ast.unparse(node.values[1]) == 'part.value' and node.lineno == node.end_lineno,
            'unsupported_image_builder')
    segment = ast.get_source_segment(source, node)
    require(source.count(segment) == 1 and segment.endswith('}'), 'unsupported_image_builder')
    patched = source.replace(segment, segment[:-1] + ', "detail": "auto"}', 1)
    compile(patched, '<invoice-image-detail-repair>', 'exec')
    return patched


def repair_plan(root, expected_head, diagnostic_backup, service='stroyka'):
    root = root.resolve()
    require(diagnostic_backup is not None, 'diagnostic_backup_required')
    require(re.fullmatch(r'[0-9a-f]{8,40}', expected_head or '') is not None, 'expected_head_required')
    prior = json.loads((diagnostic_backup.resolve() / 'manifest.json').read_text())
    require(prior['appRoot'] == str(root) and prior['service'] == service, 'backup_target_mismatch')
    head = git(root, 'rev-parse', 'HEAD')
    require(head.startswith(expected_head) and head == prior['head'], 'installed_head_mismatch')
    path = root / TARGET
    require(not path.is_symlink(), 'symlink_target_refused')
    git(root, 'ls-files', '--error-unmatch', str(TARGET))
    original = (diagnostic_backup.resolve() / 'source.py').read_bytes()
    require(digest(original) == prior['beforeHash'], 'backup_hash_mismatch')
    tracked = subprocess.run(['git', '-C', str(root), 'show', 'HEAD:' + TARGET.as_posix()],
                             capture_output=True, check=True).stdout
    require(digest(tracked) == prior['beforeHash'], 'backup_not_installed_original')
    before = path.read_bytes()
    require(digest(before) == prior['afterHash'] and MARKER in before.decode('utf-8'),
            'adapter_changed_repair_refused')
    after = add_image_detail(before.decode('utf-8')).encode('utf-8')
    return {'head': head, 'beforeHash': digest(before), 'afterHash': digest(after)}, before, after


def repair_image_detail(root, expected_head, diagnostic_backup, backup_root, service='stroyka',
                        operate=service_operation):
    root = root.resolve()
    meta, before, after = repair_plan(root, expected_head, diagnostic_backup, service)
    return install_change(root, meta, before, after, backup_root, service, operate,
                          'image_detail_repaired_awaiting_scan')


def repair_pdf_source(source):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == '_invoice_scan_ai_content']
    require(len(functions) == 1, 'unsupported_pdf_builder')
    node = functions[0]
    shape = digest(ast.dump(node, include_attributes=False).encode('utf-8'))
    require(shape == 'ab474a8d8e6066d554a0597cbcbfadec470aef25838717c9c393d4558200a39b',
            'pdf_builder_changed_or_already_repaired')
    segment = ast.get_source_segment(source, node)
    inline_files = [item for item in ast.walk(node) if isinstance(item, ast.Expr)
                    and isinstance(item.value, ast.Call)
                    and ast.unparse(item.value.func) == 'content.append'
                    and any(isinstance(child, ast.keyword) and child.arg == 'kind'
                            and isinstance(child.value, ast.Constant) and child.value.value == 'file_data_url'
                            for child in ast.walk(item))]
    require(len(inline_files) == 1, 'unsupported_pdf_builder')
    removal = ast.get_source_segment(source, inline_files[0])
    segment = segment.replace(removal, '', 1)
    old = 'rendered_pages = _render_invoice_scan_pdf_pages(pdf_bytes)'
    require(segment.count(old) == 1, 'unsupported_pdf_renderer_call')
    new = '''rendered_pages = _render_invoice_scan_pdf_pages(pdf_bytes, max_pages=7)
        if not rendered_pages:
            raise HTTPException(status_code=422, detail="Не удалось преобразовать PDF в изображения. Загрузите фотографии страниц или другой PDF.")
        if len(rendered_pages) > 6:
            raise HTTPException(status_code=422, detail="В PDF больше 6 страниц. Разделите документ на файлы до 6 страниц и проверьте позиции перед приёмкой.")'''
    segment = segment.replace(old, new, 1)
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [segment + '\n']
    patched = ''.join(lines)
    compile(patched, '<invoice-pdf-image-repair>', 'exec')
    return patched


def pdf_repair_plan(root, expected_head):
    root = root.resolve()
    require(re.fullmatch(r'[0-9a-f]{8,40}', expected_head or '') is not None, 'expected_head_required')
    head = git(root, 'rev-parse', 'HEAD')
    require(head.startswith(expected_head), 'installed_head_mismatch')
    path = root / MAIN_TARGET
    require(not path.is_symlink(), 'symlink_target_refused')
    git(root, 'ls-files', '--error-unmatch', str(MAIN_TARGET))
    require(not git(root, 'status', '--porcelain', '--', str(MAIN_TARGET)), 'main_has_local_changes')
    before = path.read_bytes()
    after = repair_pdf_source(before.decode('utf-8')).encode('utf-8')
    return {'head': head, 'beforeHash': digest(before), 'afterHash': digest(after)}, before, after


def repair_pdf(root, expected_head, backup_root, service='stroyka', operate=service_operation):
    root = root.resolve()
    meta, before, after = pdf_repair_plan(root, expected_head)
    return install_change(root, meta, before, after, backup_root, service, operate,
                          'pdf_images_repaired_awaiting_scan', target=MAIN_TARGET)


def instrument_responses(source):
    require(RESPONSE_MARKER not in source and '_stroyka_response_' not in source,
            'response_diagnostic_already_present')
    tree = ast.parse(source)
    methods = [node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == 'YandexModelAdapter'
               for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'generate']
    require(len(methods) == 1, 'unsupported_adapter')
    assignments = [node for node in ast.walk(methods[0]) if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == 'output_text'
                   and ast.unparse(node.value) == "getattr(response, 'output_text', None)"]
    require(len(assignments) == 1, 'unsupported_response_reader')
    node = assignments[0]
    require(node.lineno == node.end_lineno, 'unsupported_response_reader')
    block = '''if request.capability == "invoice_scan":
    try:
        def _stroyka_response_get(value, name):
            return value.get(name) if type(value) is dict else getattr(value, name, None)
        def _stroyka_response_number(value):
            return value if type(value) is int and 0 <= value <= 10000000 else None
        _stroyka_response_status = _stroyka_response_get(response, "status")
        _stroyka_response_reason = _stroyka_response_get(_stroyka_response_get(response, "incomplete_details"), "reason")
        _stroyka_response_output = _stroyka_response_get(response, "output")
        _stroyka_response_output = _stroyka_response_output if type(_stroyka_response_output) in (list, tuple) else ()
        _stroyka_response_types = {}
        _stroyka_response_content_types = {}
        _stroyka_response_text_chars = 0
        for _stroyka_response_item in _stroyka_response_output[:64]:
            _stroyka_response_kind = _stroyka_response_get(_stroyka_response_item, "type")
            if type(_stroyka_response_kind) is not str or _stroyka_response_kind not in ("message", "reasoning", "function_call", "web_search_call", "file_search_call", "image_generation_call"):
                _stroyka_response_kind = "other"
            _stroyka_response_types[_stroyka_response_kind] = _stroyka_response_types.get(_stroyka_response_kind, 0) + 1
            if _stroyka_response_kind != "message":
                continue
            _stroyka_response_content = _stroyka_response_get(_stroyka_response_item, "content")
            if type(_stroyka_response_content) not in (list, tuple):
                continue
            for _stroyka_response_part in _stroyka_response_content[:64]:
                _stroyka_response_part_kind = _stroyka_response_get(_stroyka_response_part, "type")
                if type(_stroyka_response_part_kind) is not str or _stroyka_response_part_kind not in ("output_text", "text", "refusal"):
                    _stroyka_response_part_kind = "other"
                _stroyka_response_content_types[_stroyka_response_part_kind] = _stroyka_response_content_types.get(_stroyka_response_part_kind, 0) + 1
                if _stroyka_response_part_kind in ("output_text", "text"):
                    _stroyka_response_text = _stroyka_response_get(_stroyka_response_part, "text")
                    if type(_stroyka_response_text) is str:
                        _stroyka_response_text_chars += len(_stroyka_response_text)
        _stroyka_response_usage = _stroyka_response_get(response, "usage")
        _stroyka_response_token_details = _stroyka_response_get(_stroyka_response_usage, "output_tokens_details")
        print("STROYKA_INVOICE_RESPONSE_DIAG", {
            "status": _stroyka_response_status if type(_stroyka_response_status) is str and _stroyka_response_status in ("completed", "incomplete", "failed", "in_progress", "queued", "cancelled") else "other",
            "incompleteReason": _stroyka_response_reason if type(_stroyka_response_reason) is str and _stroyka_response_reason in ("max_output_tokens", "content_filter", "max_tokens", "length") else None,
            "outputTypes": _stroyka_response_types,
            "contentTypes": _stroyka_response_content_types,
            "outputTextChars": min(len(output_text), 10000000) if type(output_text) is str else 0,
            "messageTextChars": min(_stroyka_response_text_chars, 10000000),
            "inputTokens": _stroyka_response_number(_stroyka_response_get(_stroyka_response_usage, "input_tokens")),
            "outputTokens": _stroyka_response_number(_stroyka_response_get(_stroyka_response_usage, "output_tokens")),
            "reasoningTokens": _stroyka_response_number(_stroyka_response_get(_stroyka_response_token_details, "reasoning_tokens")),
            "requestedOutputTokens": request.max_output_tokens,
            "images": sum(part.kind == "image_data_url" for part in request.input_parts),
            "files": sum(part.kind in ("file_data_url", "file_id") for part in request.input_parts),
        }, flush=True)
    except Exception:
        pass
'''
    indent = ' ' * node.col_offset
    lines = source.splitlines(keepends=True)
    lines.insert(node.end_lineno, ''.join(indent + line + '\n' for line in block.splitlines()))
    patched = ''.join(lines)
    compile(patched, '<invoice-response-diagnostic>', 'exec')
    return patched


def observe_responses(root, expected_head, known_backup, backup_root, service='stroyka',
                      operate=service_operation, expected_blob=None):
    root = root.resolve()
    require(known_backup is not None, 'diagnostic_backup_required')
    require(re.fullmatch(r'[0-9a-f]{8,40}', expected_head or '') is not None, 'expected_head_required')
    prior = json.loads((known_backup.resolve() / 'manifest.json').read_text())
    require(prior['appRoot'] == str(root) and prior['service'] == service, 'backup_target_mismatch')
    require(prior.get('target', str(TARGET)) == str(TARGET), 'unknown_backup_target')
    head = git(root, 'rev-parse', 'HEAD')
    require(head.startswith(expected_head), 'installed_head_mismatch')
    if expected_blob is not None:
        require(re.fullmatch(r'[0-9a-f]{40}', expected_blob) is not None, 'expected_adapter_blob_required')
        for commit in (head, prior['head']):
            require(git(root, 'rev-parse', commit + ':' + TARGET.as_posix()) == expected_blob,
                    'adapter_code_changed_since_backup')
    else:
        require(head == prior['head'], 'backup_head_changed_requires_review')
    if head != prior['head']:
        git(root, 'merge-base', '--is-ancestor', prior['head'], head)
    path = root / TARGET
    require(not path.is_symlink(), 'symlink_target_refused')
    git(root, 'ls-files', '--error-unmatch', str(TARGET))
    before = path.read_bytes()
    require(digest(before) == prior['afterHash'] and MARKER in before.decode('utf-8'),
            'adapter_changed_response_diagnostic_refused')
    after = instrument_responses(before.decode('utf-8')).encode('utf-8')
    meta = {'head': head, 'beforeHash': digest(before), 'afterHash': digest(after),
            'sourceBackupHead': prior['head']}
    if expected_blob is not None:
        meta['reviewedAdapterBlob'] = expected_blob
    return install_change(root, meta, before, after, backup_root, service, operate,
                          'response_diagnostic_installed_awaiting_scan')


def install_change(root, meta, before, after, backup_root, service, operate, state, target=TARGET):
    operate(service, 'check')
    backup = Path(tempfile.mkdtemp(prefix='stroyka-invoice-provider-', dir=backup_root))
    shutil.copy2(root / target, backup / 'source.py')
    require(digest((backup / 'source.py').read_bytes()) == meta['beforeHash'], 'backup_source_changed')
    meta['appRoot'] = str(root)
    meta['service'] = service
    meta['target'] = str(target)
    (backup / 'manifest.json').write_text(json.dumps(meta, indent=2))
    (backup / 'invoice_status_tool.py').write_text(tool_source())
    require(git(root, 'rev-parse', 'HEAD') == meta['head']
            and (root / target).read_bytes() == before, 'source_changed_before_apply')
    atomic_write(root / target, after)
    try:
        operate(service, 'restart')
    except Exception:
        try:
            restore(root, backup, service, operate)
        except Exception:
            raise Stop('restart_failed_restore_needs_review_backup_' + str(backup)) from None
        raise Stop('restart_failed_original_restored_backup_' + str(backup)) from None
    return {'state': state, 'backup': str(backup), 'head': meta['head'],
            'restoreCommand': shlex.join(['python3', str(backup / 'invoice_status_tool.py'), '--restore', str(backup),
                                         '--app-root', str(root), '--service', service])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--restore', type=Path)
    modes.add_argument('--print-command', action='store_true')
    modes.add_argument('--repair-image-detail', action='store_true')
    modes.add_argument('--repair-pdf-images', action='store_true')
    modes.add_argument('--plan-pdf-images', action='store_true')
    modes.add_argument('--observe-responses', action='store_true')
    parser.add_argument('--diagnostic-backup', type=Path)
    parser.add_argument('--expect-adapter-blob')
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
        elif args.repair_image_detail:
            result = repair_image_detail(args.app_root, args.expect_head, args.diagnostic_backup,
                                         args.backup_root, args.service)
        elif args.repair_pdf_images:
            result = repair_pdf(args.app_root, args.expect_head, args.backup_root, args.service)
        elif args.plan_pdf_images:
            meta, _, _ = pdf_repair_plan(args.app_root, args.expect_head)
            result = dict(meta, state='pdf_repair_plan_only')
        elif args.observe_responses:
            result = observe_responses(args.app_root, args.expect_head, args.diagnostic_backup,
                                       args.backup_root, args.service, expected_blob=args.expect_adapter_blob)
        elif args.restore:
            result = restore(args.app_root, args.restore, args.service)
        elif args.diagnostic_backup:
            meta, _, _ = repair_plan(args.app_root, args.expect_head, args.diagnostic_backup, args.service)
            result = dict(meta, state='repair_plan_only')
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
