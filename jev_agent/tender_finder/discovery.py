"""Sequential discovery adapter for the reviewed CLI, separate from card acceptance.

No CLI entry point, service, timer or subprocess default is installed here. The
existing worker must bind a protected invoker; tests use synthetic responses.
"""
from pathlib import Path
import errno
import subprocess

from .audit_bridge import REVIEWED_RUNTIME, runtime_source
from .cli_plan import EXECUTABLE, build_cli_plan
from .cli_result import decode_commercial_result, decode_eis_result

RUNTIME_ROOT = Path('/opt/stroyka-jev-tools/current/scripts')
WRAPPER_SHA256 = 'a23a76efb8eba8a1a37648fab630e326c910dbe93651b89f3543a9c6ae02bb09'
PROVIDER_LABELS = {
    'B2B-Center':'B2B-Center', 'Росэлторг':'Росэлторг', 'Фабрикант':'Фабрикант',
    'ЭТП ГПБ':'ЭТП ГПБ', 'Сбер А':'Сбер А',
    'ТЭК-Торг · 223-ФЗ и коммерческие':'ТЭК-Торг',
    'Торги Федерации · коммерческие':'Торги Федерации',
    'Р-ТЕНДЕР · коммерческие':'Р-ТЕНДЕР',
}


class RuntimeMismatch(ValueError):
    pass


def verify_installed_runtime():
    """Fresh read-only check; the owner's prior report alone is not a runtime gate."""
    for name, (expected, _) in REVIEWED_RUNTIME.items():
        evidence = runtime_source(RUNTIME_ROOT/name)
        if evidence.get('code') or evidence.get('sha256') != expected:
            raise RuntimeMismatch('reviewed_runtime_required')
    # The pinned entrypoint is a shell wrapper. Its syntax is deliberately not
    # Python; the hash is emitted only after ownership/path/read checks succeed.
    wrapper = runtime_source(Path(EXECUTABLE), (Path('/usr/local/bin'),))
    if wrapper.get('code') not in (None,'SyntaxError') or wrapper.get('sha256') != WRAPPER_SHA256:
        raise RuntimeMismatch('reviewed_entrypoint_required')


def discover(request, scope, *, invoke, verify_runtime=verify_installed_runtime):
    """invoke(call, timeout_seconds) -> (stdout bytes, integer exit code).

    Both callbacks are trusted worker bindings, never values from request JSON.
    No outer browser flock: the reviewed CLI already acquires that same lock.
    Completion here means discovery only, not accepted cards or Telegram delivery.
    """
    plan = build_cli_plan(request, scope)
    if not callable(invoke) or not callable(verify_runtime):
        raise ValueError('protected_runtime_bindings_required')
    outputs = []
    for call in plan.calls:
        # Recheck immediately before every call, so a changed release stops this
        # run before the next source. A mismatch is not a provider outage.
        verify_runtime()
        try:
            stdout, returncode = invoke(call, 330 if call.source == 'commercial' else 100)
        except subprocess.TimeoutExpired:
            outputs.append({'source':call.source,'query':call.query,'status':'failed','code':'cli_timeout','report':None})
            continue
        except OSError as exc:
            outputs.append({'source':call.source,'query':call.query,'status':'failed',
                            'code':'cli_output_limit' if exc.errno == errno.EFBIG else 'cli_launch_failed','report':None})
            continue
        result = (decode_commercial_result(stdout, returncode) if call.source == 'commercial'
                  else decode_eis_result(stdout, returncode, query=call.query))
        output = {'source':call.source,'query':call.query,'status':result.status,
                  'code':result.code,'report':result.report}
        if call.source == 'commercial' and result.report is not None:
            labels = [item.get('provider') for item in result.report['sources']]
            observed = {PROVIDER_LABELS[label] for label in labels if isinstance(label,str) and label in PROVIDER_LABELS}
            missing = sorted(set(request.commercial_sources) - observed)
            unexpected = (observed - set(request.commercial_sources)
                          or any(not isinstance(label,str) or label not in PROVIDER_LABELS for label in labels))
            output['sources_not_reported'] = missing
            output['unexpected_source_labels'] = bool(unexpected)
            if result.status == 'completed' and (missing or unexpected):
                output.update(status='partial',code='commercial_coverage_not_verified')
        outputs.append(output)
    complete = bool(outputs) and all(item['status']=='completed' for item in outputs) and not plan.unsupported
    useful = any(item['status'] in ('completed','partial') for item in outputs)
    return {'request_id':request.request_id,'company_id':scope.company_id,
            'status':'completed' if complete else 'partial' if useful else 'failed',
            'discovery_complete':complete,'card_acceptance_complete':False,
            'telegram_delivery_verified':False,'postfilter_required':True,
            'outputs':outputs,'unsupported_regimes':[{'source':source,'regime':regime} for source,regime in plan.unsupported]}
