"""Dispatch v2 while preserving the installed v1 validator as a trusted callback.

The caller must bind the reviewed installed validator; this module never imports
worker.py, recreates its topic mapping, or assumes its filesystem/auth behavior.
Passing unit tests here is not a deployed-worker compatibility acceptance.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from .contract import SearchRequest, validate_v2_request

LEGACY_FIELDS = frozenset(('version', 'request_id', 'region', 'sources', 'topics'))


class LegacyBindingError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyRequest:
    """Keep the v1 wire payload, including topic labels and ordering, unchanged."""
    _payload: dict

    @property
    def request_id(self):
        return self._payload['request_id']

    def legacy_payload(self):
        return deepcopy(self._payload)


def normalize_request(payload, *, legacy_validator: Callable | None = None) -> SearchRequest | LegacyRequest:
    if type(payload) is dict and type(payload.get('version')) is int and payload['version'] == 2:
        return validate_v2_request(payload)
    if legacy_validator is None:
        raise LegacyBindingError('reviewed_legacy_validator_required')
    # Preserve v1 rejection semantics as well; never silently pass it through v2.
    original = deepcopy(payload)
    normalized = legacy_validator(deepcopy(payload))
    if (type(normalized) is not dict or set(normalized) != LEGACY_FIELDS
            or type(normalized.get('version')) is not int or normalized['version'] != 1
            or type(original) is not dict or normalized.get('request_id') != original.get('request_id')):
        raise LegacyBindingError('legacy_validator_contract_mismatch')
    return LegacyRequest(deepcopy(normalized))
