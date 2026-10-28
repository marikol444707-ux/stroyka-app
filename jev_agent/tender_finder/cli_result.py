"""Decode bounded existing JEV CLI output without losing nonzero partial JSON.

No process launching, shell, model calls, import-to-CRM, or source fetching here.
The runtime adapter must still verify CLI identity and operation capabilities.
"""
from dataclasses import dataclass
import json

MAX_RESULT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CLIResult:
    status: str
    report: dict | None
    code: str | None
    returncode: int


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_field')
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError('nonfinite_number')


def decode_commercial_result(stdout, returncode):
    """The commercial report shape; EIS runtime output needs its own adapter."""
    if type(returncode) is not int:
        raise ValueError('integer_returncode_required')
    if not isinstance(stdout, bytes):
        raise ValueError('stdout_bytes_required')
    if len(stdout) > MAX_RESULT_BYTES:
        return CLIResult('failed', None, 'cli_result_too_large', returncode)
    try:
        data = json.loads(stdout.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        return CLIResult('failed', None, 'invalid_cli_json', returncode)
    if type(data) is not dict or type(data.get('ok')) is not bool:
        return CLIResult('failed', None, 'invalid_cli_report', returncode)
    # Recognize only the source report shape already present in JEV source.
    if type(data.get('sources')) is not list or any(type(item) is not dict for item in data['sources']):
        return CLIResult('failed', None, 'invalid_cli_sources', returncode)
    for field in ('confirmed', 'review'):
        if type(data.get(field)) is not list or any(type(item) is not dict for item in data[field]):
            return CLIResult('failed', None, 'invalid_cli_candidates', returncode)
    candidates = bool(data['confirmed'] or data['review'])
    source_success = any(item.get('ok') is True for item in data['sources'])
    all_sources_success = bool(data['sources']) and all(item.get('ok') is True for item in data['sources'])
    if returncode == 0 and data['ok'] and all_sources_success:
        return CLIResult('completed', data, None, returncode)
    if candidates or source_success:
        # Retain evidence, but never upgrade a nonzero/contradictory run to success.
        return CLIResult('partial', data, 'cli_nonzero_exit' if returncode else 'source_coverage_partial', returncode)
    return CLIResult('failed', data, 'cli_failed_without_verified_coverage', returncode)
