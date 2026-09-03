"""Fail-closed company boundary for supply comparison sources.

This module is intentionally pure.  It does not open the database, read files,
call HTTP services or invoke a model.  It turns a server-owned company scope
into immutable metadata and rejects every attempt to widen or replace that
scope with values from an untrusted payload.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional


BOUNDARY_CONTRACT_VERSION = 1
OWNER_SCOPE_COMPANY = "company"
COMPANY_MODE = "company"
READ_ONLY_MODE = "read_only"
MAX_BOUNDARY_PAYLOAD_BYTES = 64 * 1024
MAX_BOUNDARY_DEPTH = 32
MAX_BOUNDARY_NODES = 10_000

BOUNDARY_INPUT_INVALID = "supply_company_boundary_input_invalid"
BOUNDARY_VIOLATION = "supply_company_boundary_violation"

_ERROR_CODES = frozenset({BOUNDARY_INPUT_INVALID, BOUNDARY_VIOLATION})
_SQL_COLUMN_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$"
)
_COMPANY_KEYS = frozenset(
    {
        "companyid",
        "ownercompanyid",
        "resourcecompanyid",
        "tenantcompanyid",
    }
)
_PROJECT_KEYS = frozenset(
    {
        "projectid",
        "projectscopeid",
        "ownerprojectid",
        "resourceprojectid",
    }
)
_COMPANY_MODE_KEYS = frozenset({"companymode"})
_OWNER_SCOPE_KEYS = frozenset({"ownerscope"})


class SupplyCompanyBoundaryError(ValueError):
    """Fixed non-leaking boundary error."""

    def __init__(self, code=BOUNDARY_INPUT_INVALID):
        self.code = code if code in _ERROR_CODES else BOUNDARY_INPUT_INVALID
        super().__init__(self.code)


def _fail(code=BOUNDARY_INPUT_INVALID):
    raise SupplyCompanyBoundaryError(code) from None


def _positive_int(value):
    if type(value) is not int or value <= 0:
        _fail()
    return value


def _optional_positive_int(value):
    if value is None:
        return None
    return _positive_int(value)


def _normalized_key(value):
    if type(value) is not str:
        _fail()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _json_safe(value, *, depth=0, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_BOUNDARY_NODES or depth > MAX_BOUNDARY_DEPTH:
        _fail()

    if isinstance(value, Mapping):
        result = {}
        for key, nested in value.items():
            if type(key) is not str or key in result:
                _fail()
            result[key] = _json_safe(
                nested,
                depth=depth + 1,
                counter=counter,
            )
        return result

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            _json_safe(item, depth=depth + 1, counter=counter)
            for item in value
        ]

    if value is None or type(value) in (str, int, bool):
        return value

    if type(value) is float and math.isfinite(value):
        return value

    _fail()


def _canonical_bytes(value):
    safe = _json_safe(value)
    try:
        encoded = json.dumps(
            safe,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        _fail()
    if len(encoded) > MAX_BOUNDARY_PAYLOAD_BYTES:
        _fail()
    return safe, encoded


def _sha256(value):
    _, encoded = _canonical_bytes(value)
    return hashlib.sha256(encoded).hexdigest()


def _scope_values(mapping, keys):
    values = []
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            values.append(mapping[key])
    return values


def _single_company_id(mapping):
    values = _scope_values(mapping, ("companyId", "company_id"))
    if not values:
        _fail(BOUNDARY_VIOLATION)
    normalized = [_positive_int(value) for value in values]
    if len(set(normalized)) != 1:
        _fail(BOUNDARY_VIOLATION)
    return normalized[0]


def _inspect_payload(value, *, company_id, project_id):
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized_key = _normalized_key(key)
            if normalized_key in _COMPANY_KEYS and nested not in (None, ""):
                if _positive_int(nested) != company_id:
                    _fail(BOUNDARY_VIOLATION)
            elif normalized_key in _PROJECT_KEYS and nested not in (None, ""):
                nested_project_id = _positive_int(nested)
                if project_id is None or nested_project_id != project_id:
                    _fail(BOUNDARY_VIOLATION)
            elif normalized_key in _COMPANY_MODE_KEYS and nested not in (None, ""):
                if type(nested) is not str or nested.strip().lower() != COMPANY_MODE:
                    _fail(BOUNDARY_VIOLATION)
            elif normalized_key in _OWNER_SCOPE_KEYS and nested not in (None, ""):
                if (
                    type(nested) is not str
                    or nested.strip().lower() != OWNER_SCOPE_COMPANY
                ):
                    _fail(BOUNDARY_VIOLATION)
            _inspect_payload(
                nested,
                company_id=company_id,
                project_id=project_id,
            )
        return

    if isinstance(value, list):
        for nested in value:
            _inspect_payload(
                nested,
                company_id=company_id,
                project_id=project_id,
            )


@dataclass(frozen=True)
class SupplyCompanyBoundary:
    """Immutable server-owned scope metadata for one read-only run."""

    company_id: int
    project_id: Optional[int]
    owner_scope: str
    company_mode: str
    execution_mode: str
    payload_sha256: str
    boundary_sha256: str
    writes_attempted: int = 0
    model_calls: int = 0

    def to_dict(self):
        return {
            "contractVersion": BOUNDARY_CONTRACT_VERSION,
            "ownerScope": self.owner_scope,
            "companyId": self.company_id,
            "projectId": self.project_id,
            "companyMode": self.company_mode,
            "executionMode": self.execution_mode,
            "readOnly": True,
            "payloadSha256": self.payload_sha256,
            "boundarySha256": self.boundary_sha256,
            "writesAttempted": self.writes_attempted,
            "modelCalls": self.model_calls,
            "automaticApprovalAllowed": False,
        }


def build_company_boundary(
    *,
    owner_scope,
    company_id,
    project_id=None,
    company_mode=COMPANY_MODE,
    payload=None,
):
    """Build one immutable boundary from server-owned scope values."""

    if (
        type(owner_scope) is not str
        or owner_scope.strip().lower() != OWNER_SCOPE_COMPANY
    ):
        _fail(BOUNDARY_VIOLATION)
    if (
        type(company_mode) is not str
        or company_mode.strip().lower() != COMPANY_MODE
    ):
        _fail(BOUNDARY_VIOLATION)

    company_id = _positive_int(company_id)
    project_id = _optional_positive_int(project_id)
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        _fail()

    safe_payload, payload_bytes = _canonical_bytes(payload)
    _inspect_payload(
        safe_payload,
        company_id=company_id,
        project_id=project_id,
    )
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    boundary_payload = {
        "contractVersion": BOUNDARY_CONTRACT_VERSION,
        "ownerScope": OWNER_SCOPE_COMPANY,
        "companyId": company_id,
        "projectId": project_id,
        "companyMode": COMPANY_MODE,
        "executionMode": READ_ONLY_MODE,
        "payloadSha256": payload_sha256,
    }
    return SupplyCompanyBoundary(
        company_id=company_id,
        project_id=project_id,
        owner_scope=OWNER_SCOPE_COMPANY,
        company_mode=COMPANY_MODE,
        execution_mode=READ_ONLY_MODE,
        payload_sha256=payload_sha256,
        boundary_sha256=_sha256(boundary_payload),
    )


def boundary_from_request_context(context, *, project_id=None, payload=None):
    """Build a boundary from an already server-resolved company context."""

    if not isinstance(context, Mapping):
        _fail()
    mode = context.get("mode")
    if type(mode) is not str or mode.strip().lower() != COMPANY_MODE:
        _fail(BOUNDARY_VIOLATION)

    company_id = _single_company_id(context)
    context_company_ids = context.get("companyIds")
    if context_company_ids is not None:
        if (
            not isinstance(context_company_ids, Sequence)
            or isinstance(context_company_ids, (str, bytes, bytearray))
            or len(context_company_ids) != 1
            or _positive_int(context_company_ids[0]) != company_id
        ):
            _fail(BOUNDARY_VIOLATION)

    return build_company_boundary(
        owner_scope=OWNER_SCOPE_COMPANY,
        company_id=company_id,
        project_id=project_id,
        company_mode=mode,
        payload=payload,
    )


def assert_resource_company(
    boundary,
    row,
    *,
    company_keys=("company_id", "companyId"),
):
    """Require one resource row to belong to the boundary company."""

    if not isinstance(boundary, SupplyCompanyBoundary):
        _fail()
    if not isinstance(row, Mapping):
        _fail()
    if (
        not isinstance(company_keys, Sequence)
        or isinstance(company_keys, (str, bytes, bytearray))
        or not company_keys
        or any(type(key) is not str or not key for key in company_keys)
    ):
        _fail()

    values = _scope_values(row, tuple(company_keys))
    if not values:
        _fail(BOUNDARY_VIOLATION)
    normalized = [_positive_int(value) for value in values]
    if len(set(normalized)) != 1 or normalized[0] != boundary.company_id:
        _fail(BOUNDARY_VIOLATION)
    return normalized[0]


def assert_resource_project(
    boundary,
    row,
    *,
    project_keys=("project_id", "projectId"),
    required=False,
):
    """Reject a project mismatch without inventing a missing project."""

    if not isinstance(boundary, SupplyCompanyBoundary):
        _fail()
    if not isinstance(row, Mapping) or type(required) is not bool:
        _fail()
    if (
        not isinstance(project_keys, Sequence)
        or isinstance(project_keys, (str, bytes, bytearray))
        or not project_keys
        or any(type(key) is not str or not key for key in project_keys)
    ):
        _fail()

    values = _scope_values(row, tuple(project_keys))
    if not values:
        if required:
            _fail(BOUNDARY_VIOLATION)
        return None

    normalized = [_positive_int(value) for value in values]
    if len(set(normalized)) != 1:
        _fail(BOUNDARY_VIOLATION)
    if boundary.project_id is None or normalized[0] != boundary.project_id:
        _fail(BOUNDARY_VIOLATION)
    return normalized[0]


def assert_company_chain(boundary, *rows):
    """Require every row in a source chain to have the same tenant owner."""

    if not rows:
        _fail()
    return tuple(assert_resource_company(boundary, row) for row in rows)


def company_sql_predicate(boundary, column="company_id"):
    """Return one parameterized equality predicate for a safe SQL identifier."""

    if not isinstance(boundary, SupplyCompanyBoundary):
        _fail()
    if type(column) is not str or not _SQL_COLUMN_RE.fullmatch(column):
        _fail()
    return f"{column}=%s", (boundary.company_id,)


def boundary_metadata_view(boundary):
    """Expose immutable metadata only; never expose tenant payload contents."""

    if not isinstance(boundary, SupplyCompanyBoundary):
        _fail()
    return MappingProxyType(boundary.to_dict())
