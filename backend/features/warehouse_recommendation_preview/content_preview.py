"""Read-only transaction runner for one A9.2 warehouse anomaly preview."""

import psycopg2.extras

from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    collect_supply_warehouse_impact_audit,
)
from backend.features.warehouse_recommendation_preview.content_contract import (
    WAREHOUSE_ANOMALY_CONTENT_VERSION,
    WarehouseAnomalyContentError,
    _finalize_warehouse_anomaly_content,
    _prepare_warehouse_anomaly_content,
    _validate_current_warehouse_anomaly_report,
    _validated_warehouse_anomaly_content_result,
)


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_FINALIZER_ERROR_CODES = frozenset({
    "warehouse_anomaly_content_contract_invalid",
    "warehouse_anomaly_content_current_report_invalid",
})


class _CurrentReportInvalid(Exception):
    pass


def _fail(code):
    raise WarehouseAnomalyContentError(code) from None


def _configure_transaction(cur):
    cur.execute(
        """SELECT pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true)""",
        (
            "statement_timeout", "60000",
            "lock_timeout", "5000",
            "idle_in_transaction_session_timeout", "60000",
            "search_path", "pg_catalog,public",
        ),
    )


def _collect_current_warehouse_anomaly_evidence(cur, prepared):
    raw = collect_supply_warehouse_impact_audit(
        cur, prepared.source_contract,
    )
    try:
        return _validate_current_warehouse_anomaly_report(
            raw, prepared.source_contract,
        )
    except _CONTROL_FLOW:
        raise
    except Exception:
        raise _CurrentReportInvalid() from None


def run_warehouse_anomaly_content_preview(get_db, combined_report, selected):
    """Collect once, roll back and close, then finalize fixed content."""

    if not callable(get_db):
        _fail("warehouse_anomaly_content_input_invalid")
    prepared = _prepare_warehouse_anomaly_content(combined_report, selected)

    connection = None
    cur = None
    current = None
    primary_error = None
    primary_kind = None
    rollback_error = None
    cleanup_error = None
    first_control = None

    try:
        connection = get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        _configure_transaction(cur)
        current = _collect_current_warehouse_anomaly_evidence(cur, prepared)
    except BaseException as exc:
        primary_error = exc
        primary_kind = (
            "current" if isinstance(exc, _CurrentReportInvalid) else "read"
        )
        if isinstance(exc, _CONTROL_FLOW):
            first_control = exc

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            else:
                rollback_error = exc

    if cur is not None:
        try:
            cur.close()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            elif cleanup_error is None:
                cleanup_error = exc
    if connection is not None:
        try:
            connection.close()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            elif cleanup_error is None:
                cleanup_error = exc

    if first_control is not None:
        raise first_control
    if rollback_error is not None:
        _fail("warehouse_anomaly_content_rollback_failed")
    if primary_error is not None and primary_kind == "read":
        _fail("warehouse_anomaly_content_read_failed")
    if cleanup_error is not None:
        _fail("warehouse_anomaly_content_cleanup_failed")
    if primary_error is not None:
        _fail("warehouse_anomaly_content_current_report_invalid")

    try:
        result = _finalize_warehouse_anomaly_content(prepared, current)
        return _validated_warehouse_anomaly_content_result(result, prepared)
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except WarehouseAnomalyContentError as exc:
        if exc.code in _FINALIZER_ERROR_CODES:
            _fail(exc.code)
        _fail("warehouse_anomaly_content_contract_invalid")
    except Exception:
        _fail("warehouse_anomaly_content_contract_invalid")


__all__ = [
    "WAREHOUSE_ANOMALY_CONTENT_VERSION",
    "WarehouseAnomalyContentError",
    "run_warehouse_anomaly_content_preview",
]
