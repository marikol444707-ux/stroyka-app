"""Offline calls for the reviewed repository CLI; does not execute anything.

Installed CLI bytes/capabilities still require comparison. EIS 223/615 are not
silently represented by the 44-FZ-only --stavropol-open operation. Card-level
price/deadline/law/region checks remain mandatory after these discovery calls.
"""
from dataclasses import dataclass
import json

from .catalog import BY_ID, normalized_text
from .contract import SearchRequest
from .state import Scope

EXECUTABLE = '/usr/local/bin/stroyka-jev'


@dataclass(frozen=True)
class DiscoveryCall:
    source: str
    argv: tuple[str, ...]
    stdin: bytes | None
    query: str | None = None


@dataclass(frozen=True)
class DiscoveryPlan:
    calls: tuple[DiscoveryCall, ...]
    unsupported: tuple[tuple[str, str], ...]
    postfilter_required: bool = True
    installed_cli_verified: bool = False


def build_cli_plan(request: SearchRequest, scope: Scope) -> DiscoveryPlan:
    """scope comes from protected auth/configuration, never model request JSON.

    No shell/sudo/CRM import command, outer browser flock, implicit source, or
    fallback company. Call sequentially only after installed-capability binding.
    """
    if type(request) is not SearchRequest or type(scope) is not Scope:
        raise ValueError('normalized_request_and_protected_scope_required')
    scope.key()
    calls, unsupported = [], []
    if 'eis' in request.sources:
        for regime in request.legal_regimes:
            if regime in ('223-ФЗ', '615-ПП'):
                unsupported.append(('eis', regime))
        if '44-ФЗ' in request.legal_regimes:
            phrases = {normalized_text(BY_ID[topic].query): BY_ID[topic].query for topic in request.topic_ids}
            for keyword in request.keywords:
                phrases.setdefault(normalized_text(keyword), keyword)
            for key in sorted(phrases):
                query = phrases[key]
                calls.append(DiscoveryCall('eis', (EXECUTABLE, 'eis-search', '--query', query,
                                                   '--stavropol-open'), None, query))
    if 'commercial' in request.sources:
        profile = request.company_profile(scope.company_id)
        data = json.dumps(profile, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(data) > 32768:
            raise ValueError('profile_size_limit')
        calls.append(DiscoveryCall('commercial', (EXECUTABLE, 'commercial-search', '--profile-stdin'), data))
    return DiscoveryPlan(tuple(calls), tuple(unsupported))
