"""Private unregistered same-snapshot warehouse anomaly runtime."""

import time
from typing import NamedTuple

import psycopg2

from backend.features.warehouse_recommendation_preview import (
    runtime_access as _runtime_access,
)
from backend.features.warehouse_recommendation_preview import (
    runtime_budget as _runtime_budget,
)
from backend.features.warehouse_recommendation_preview import (
    runtime_contract as _runtime_contract,
)
from backend.features.warehouse_recommendation_preview.content_contract import (
    WarehouseAnomalyContentError,
    _finalize_warehouse_anomaly_content as _finalize,
    _prepare_warehouse_anomaly_content as _prepare,
    _validated_warehouse_anomaly_content_result as _validate,
)
from backend.features.warehouse_recommendation_preview.content_preview import (
    _collect_current_warehouse_anomaly_evidence as _collect,
)


_project = _runtime_contract._public_warehouse_anomaly_runtime_projection
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_BUSINESS_CODES = frozenset({
    _runtime_contract._AUTHENTICATION_REQUIRED,
    _runtime_contract._RESOURCE_NOT_FOUND,
    _runtime_access._ARTIFACT_INVALID,
})
_CONTENT_NOT_FOUND_CODES = frozenset({
    "warehouse_anomaly_content_selection_invalid",
    "warehouse_anomaly_content_stored_readiness_blocked",
})


class _RuntimeSnapshot(NamedTuple):
    prepared: object
    current: object
    business_code: object


def _contract_failure():
    raise _runtime_budget._WarehouseAnomalyRuntimeError(
        _runtime_budget._CONTRACT_INVALID,
    ) from None


def _business_snapshot(code):
    if code not in _BUSINESS_CODES:
        _contract_failure()
    return _RuntimeSnapshot(None, None, code)


def _read_runtime_snapshot(cur, claims, lease):
    try:
        _runtime_access._authorize_warehouse_anomaly_runtime_access(
            cur, claims,
        )
        artifact = _runtime_access._resolve_warehouse_anomaly_runtime_artifact(
            cur, claims,
        )
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except _runtime_contract._WarehouseAnomalyRuntimeContractError as error:
        if error.code in _BUSINESS_CODES:
            return _business_snapshot(error.code)
        _contract_failure()

    try:
        prepared = _prepare(
            artifact["combinedReport"],
            artifact["selected"],
        )
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except WarehouseAnomalyContentError as error:
        if error.code in _CONTENT_NOT_FOUND_CODES:
            return _business_snapshot(_runtime_contract._RESOURCE_NOT_FOUND)
        return _business_snapshot(_runtime_access._ARTIFACT_INVALID)
    except BaseException:
        _contract_failure()

    current = _collect(cur, prepared)
    lease.guard()
    return _RuntimeSnapshot(prepared, current, None)


def _first_identity_error(primary_error, release_error):
    for error in (primary_error, release_error):
        if isinstance(error, _CONTROL_FLOW):
            return error
    for error in (primary_error, release_error):
        if isinstance(error, MemoryError):
            return error
    return None


def _raise_primary_runtime_error(error):
    if isinstance(error, _runtime_budget._WarehouseAnomalyRuntimeError):
        _runtime_budget._raise_guarded_error(error)
    if isinstance(
        error, _runtime_contract._WarehouseAnomalyRuntimeContractError,
    ):
        _runtime_contract._raise_fixed_error(error)
    _runtime_budget._fail(_runtime_budget._READ_FAILED)


def _dispatch_runtime_outcome(
    *,
    result,
    primary_error,
    primary_kind,
    business_code,
    release_error,
):
    identity_error = _first_identity_error(primary_error, release_error)
    if identity_error is not None:
        raise identity_error

    if primary_kind == "primary":
        _raise_primary_runtime_error(primary_error)
    if primary_kind == "finalizer":
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)
    if release_error is not None:
        _runtime_budget._fail(_runtime_budget._CLEANUP_FAILED)
    if primary_kind == "post_deadline":
        if (
            isinstance(
                primary_error, _runtime_budget._WarehouseAnomalyRuntimeError,
            )
            and primary_error.code == _runtime_budget._DEADLINE_EXCEEDED
        ):
            _runtime_budget._raise_guarded_error(primary_error)
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)
    if business_code is not None:
        _runtime_contract._fail(business_code)
    if primary_error is not None:
        _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)
    return result


def run_warehouse_anomaly_runtime_preview(
    db_config,
    authentication,
    *,
    company_mode,
    company_id,
    body,
    clock=time.monotonic,
    connect=psycopg2.connect,
):
    """Compose one private same-snapshot preview and release its lease."""

    claims = _runtime_contract._parse_warehouse_anomaly_runtime_claims(
        authentication,
        company_mode=company_mode,
        company_id=company_id,
        body=body,
    )
    lease = None
    result = None
    primary_error = None
    primary_kind = None
    business_code = None
    release_error = None
    stage = "primary"
    try:
        lease = _runtime_budget.acquire_warehouse_anomaly_runtime_slot(clock)
        connection = _runtime_budget.open_warehouse_anomaly_read_connection(
            db_config,
            lease,
            connect=connect,
        )
        snapshot = _runtime_budget.run_warehouse_anomaly_read_transaction(
            connection,
            lease,
            lambda cur: _read_runtime_snapshot(cur, claims, lease),
        )
        stage = "finalizer"
        if (
            type(snapshot) is not _RuntimeSnapshot
            or (
                snapshot.business_code is None
                and (snapshot.prepared is None or snapshot.current is None)
            )
            or (
                snapshot.business_code is not None
                and (
                    snapshot.prepared is not None
                    or snapshot.current is not None
                    or snapshot.business_code not in _BUSINESS_CODES
                )
            )
        ):
            _runtime_contract._fail(_runtime_contract._CONTRACT_INVALID)

        stage = "post_deadline"
        lease.guard()
        if snapshot.business_code is not None:
            business_code = snapshot.business_code
        else:
            stage = "finalizer"
            internal = _finalize(snapshot.prepared, snapshot.current)
            internal = _validate(internal, snapshot.prepared)
            result = _project(internal)
            stage = "post_deadline"
            lease.guard()
    except BaseException as error:
        primary_error = error
        primary_kind = stage
    finally:
        if lease is not None:
            try:
                lease.release()
            except BaseException as error:
                release_error = error

    return _dispatch_runtime_outcome(
        result=result,
        primary_error=primary_error,
        primary_kind=primary_kind,
        business_code=business_code,
        release_error=release_error,
    )

__all__ = []
