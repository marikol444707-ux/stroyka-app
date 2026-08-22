"""Private bounded read-only snapshot for accounting exception checks."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

import psycopg2.extras

from .projection import (
    ACCOUNTING_EXCEPTION_SOURCES,
    MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS,
    build_accounting_exception_projection,
)


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "accounting_exception_snapshot_input_invalid"
_CONTRACT_INVALID = "accounting_exception_snapshot_contract_invalid"
_READ_FAILED = "accounting_exception_snapshot_read_failed"
_ROLLBACK_FAILED = "accounting_exception_snapshot_rollback_failed"
_CLEANUP_FAILED = "accounting_exception_snapshot_cleanup_failed"
_MAX_TEXT_FIELD_BYTES = 64
_MAX_MONTH_FIELD_BYTES = 7
_MAX_QUERY_VARIABLE_BYTES = 1024 * 1024
_MAX_SNAPSHOT_VARIABLE_BYTES = 4 * 1024 * 1024


_SOURCE_SPECS = {
    "brigade_contracts": {
        "fixed": (("id", "bc.id"), ("company_id", "bc.company_id"),
                  ("project_id", "bc.project_id")),
        "variables": (),
        "from": """FROM public.brigade_contracts bc
                     JOIN public.projects p
                       ON p.id=bc.project_id AND p.company_id=bc.company_id
                    WHERE bc.company_id=%s""",
        "company_params": 1,
    },
    "brigade_payments": {
        "fixed": (("id", "bp.id"), ("company_id", "bp.company_id"),
                  ("contract_id", "bp.contract_id"),
                  ("project_payment_id", "bp.project_payment_id")),
        "variables": (("amount", "bp.amount::text", _MAX_TEXT_FIELD_BYTES),),
        "from": """FROM public.brigade_payments bp
                     JOIN public.brigade_contracts bc
                       ON bc.id=bp.contract_id AND bc.company_id=bp.company_id
                     JOIN public.projects p
                       ON p.id=bc.project_id AND p.company_id=bc.company_id
                    WHERE bp.company_id=%s""",
        "company_params": 1,
    },
    "project_payments": {
        "fixed": (("id", "pp.id"), ("company_id", "pp.company_id"),
                  ("project_id", "project_scope.project_id")),
        "variables": (("amount", "pp.amount::text", _MAX_TEXT_FIELD_BYTES),),
        "from": """FROM public.project_payments pp
                     JOIN (
                       SELECT p.name,MIN(p.id)::integer AS project_id
                         FROM public.projects p
                        WHERE p.company_id=%s
                        GROUP BY p.name HAVING COUNT(*)=1
                     ) project_scope ON project_scope.name=pp.project_name
                    WHERE pp.company_id=%s
                      AND pp.company_scope_verified IS TRUE""",
        "company_params": 2,
    },
    "supplier_invoices": {
        "fixed": (("id", "si.id"), ("company_id", "si.company_id"),
                  ("project_id", "project_scope.project_id"),
                  ("warehouse_invoice_id", "si.warehouse_invoice_id")),
        "variables": (
            ("amount", "si.amount::text", _MAX_TEXT_FIELD_BYTES),
            ("paid_amount", "si.paid_amount::text", _MAX_TEXT_FIELD_BYTES),
        ),
        "from": """FROM public.supplier_invoices si
                     LEFT JOIN (
                       SELECT p.name,MIN(p.id)::integer AS project_id
                         FROM public.projects p
                        WHERE p.company_id=%s
                        GROUP BY p.name HAVING COUNT(*)=1
                     ) project_scope ON project_scope.name=si.project_name
                    WHERE si.company_id=%s""",
        "company_params": 2,
    },
    "warehouse_invoices": {
        "fixed": (("id", "wi.id"), ("company_id", "wi.company_id"),
                  ("project_id", "project_scope.project_id"),
                  ("supplier_invoice_id", "wi.supplier_invoice_id")),
        "variables": (),
        "from": """FROM public.warehouse_invoices wi
                     LEFT JOIN (
                       SELECT p.name,MIN(p.id)::integer AS project_id
                         FROM public.projects p
                        WHERE p.company_id=%s
                        GROUP BY p.name HAVING COUNT(*)=1
                     ) project_scope ON project_scope.name=wi.project
                    WHERE wi.company_id=%s""",
        "company_params": 2,
    },
    "accountable_payments": {
        "fixed": (("id", "ap.id"), ("company_id", "ap.company_id"),
                  ("project_id", "ap.project_id")),
        "variables": (
            ("amount", "ap.amount::text", _MAX_TEXT_FIELD_BYTES),
            ("spent_amount", "ap.spent_amount::text", _MAX_TEXT_FIELD_BYTES),
        ),
        "from": """FROM public.accountable_payments ap
                     JOIN public.projects p
                       ON p.id=ap.project_id AND p.company_id=ap.company_id
                    WHERE ap.company_id=%s
                      AND ap.company_scope_verified IS TRUE""",
        "company_params": 1,
    },
    "accountable_expenses": {
        "fixed": (("id", "ae.id"), ("company_id", "ae.company_id"),
                  ("project_id", "ae.project_id"),
                  ("payment_id", "ae.payment_id")),
        "variables": (("amount", "ae.amount::text", _MAX_TEXT_FIELD_BYTES),),
        "from": """FROM public.accountable_expenses ae
                     JOIN public.projects p
                       ON p.id=ae.project_id AND p.company_id=ae.company_id
                    WHERE ae.company_id=%s
                      AND ae.company_scope_verified IS TRUE""",
        "company_params": 1,
    },
    "expense_reports": {
        "fixed": (("id", "er.id"), ("company_id", "er.company_id"),
                  ("project_id", "er.project_id")),
        "variables": (
            ("issued_amount", "er.issued_amount::text", _MAX_TEXT_FIELD_BYTES),
            ("spent_amount", "er.spent_amount::text", _MAX_TEXT_FIELD_BYTES),
            ("balance", "er.balance::text", _MAX_TEXT_FIELD_BYTES),
        ),
        "from": """FROM public.expense_reports er
                     JOIN public.projects p
                       ON p.id=er.project_id AND p.company_id=er.company_id
                    WHERE er.company_id=%s
                      AND er.company_scope_verified IS TRUE""",
        "company_params": 1,
    },
    "staff": {
        "fixed": (("id", "s.id"), ("company_id", "s.company_id")),
        "variables": (),
        "from": """FROM public.staff s
                    WHERE s.company_id=%s
                      AND s.company_scope_verified IS TRUE""",
        "company_params": 1,
    },
    "salary_payments": {
        "fixed": (("id", "sp.id"), ("company_id", "sp.company_id"),
                  ("staff_id", "sp.staff_id")),
        "variables": (("month", "sp.month", _MAX_MONTH_FIELD_BYTES),),
        "from": """FROM public.salary_payments sp
                    WHERE sp.company_id=%s
                      AND sp.company_scope_verified IS TRUE""",
        "company_params": 1,
    },
    "own_expenses": {
        "fixed": (("id", "oe.id"), ("company_id", "oe.company_id"),
                  ("project_id", "oe.project_id"),
                  ("expense_id", "oe.expense_id")),
        "variables": (),
        "from": """FROM public.own_expenses oe
                     LEFT JOIN public.projects p
                       ON p.id=oe.project_id AND p.company_id=oe.company_id
                    WHERE oe.company_id=%s
                      AND oe.company_scope_verified IS TRUE
                      AND (oe.project_id IS NULL OR p.id IS NOT NULL)""",
        "company_params": 1,
    },
    "expenses": {
        "fixed": (("id", "e.id"), ("company_id", "e.company_id"),
                  ("project_id", "e.project_id"),
                  ("own_expense_id", "e.own_expense_id")),
        "variables": (),
        "from": """FROM public.expenses e
                     LEFT JOIN public.projects p
                       ON p.id=e.project_id AND p.company_id=e.company_id
                    WHERE e.company_id=%s
                      AND e.company_scope_verified IS TRUE
                      AND (e.project_id IS NULL OR p.id IS NOT NULL)""",
        "company_params": 1,
    },
}


class AccountingExceptionSnapshotError(ValueError):
    """Fixed private error for invalid snapshot input or DB lifecycle."""


def _fail(code):
    raise AccountingExceptionSnapshotError(code) from None


def _configure_transaction(cur):
    cur.execute(
        """SELECT pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true)""",
        (
            "statement_timeout", "30000",
            "lock_timeout", "1000",
            "idle_in_transaction_session_timeout", "30000",
            "search_path", "pg_catalog,public",
        ),
    )


class _VariableByteBudget:
    def __init__(self):
        self.remaining = _MAX_SNAPSHOT_VARIABLE_BYTES

    def consume(self, amount):
        if type(amount) is not int or amount < 0 or amount > self.remaining:
            _fail(_CONTRACT_INVALID)
        self.remaining -= amount


def _source_query(source, company_id, remaining_bytes):
    spec = _SOURCE_SPECS[source]
    fixed = tuple(name for name, _expression in spec["fixed"])
    variables = tuple(name for name, _expression, _cap in spec["variables"])
    limited_fields = [
        expression + " AS " + name for name, expression in spec["fixed"]
    ] + [
        expression + " AS emitted_" + name
        for name, expression, _cap in spec["variables"]
    ]
    size_fields = [
        "COALESCE(octet_length(convert_to(emitted_"
        + name + ",'UTF8')),0)::bigint AS field_" + name + "_bytes"
        for name in variables
    ]
    size_sum = (
        "+".join("field_" + name + "_bytes" for name in variables)
        if variables else "0"
    )
    max_fields = [
        "MAX(field_" + name + "_bytes) OVER () AS max_field_"
        + name + "_bytes"
        for name in variables
    ]
    cap_conditions = [
        "max_field_" + name + "_bytes <= %s"
        for name in variables
    ]
    cap_conditions.extend((
        "query_text_bytes <= %s",
        "query_variable_bytes <= %s",
    ))
    inner_fields = list(fixed)
    inner_fields.extend(
        "CASE WHEN row_count <= %s AND bytes_allowed "
        "THEN emitted_" + name + " END AS " + name
        for name in variables
    )
    inner_fields.extend(
        "field_" + name + "_bytes" for name in variables
    )
    inner_fields.extend((
        "query_json_bytes", "query_text_bytes", "query_variable_bytes",
        "row_count", "row_count > %s AS cardinality_limit_exceeded",
        "row_count <= %s AND NOT bytes_allowed AS payload_limit_exceeded",
    ))
    outer_fields = list(fixed) + list(variables)
    outer_fields.extend("field_" + name + "_bytes" for name in variables)
    outer_fields.extend((
        "query_json_bytes", "query_text_bytes", "query_variable_bytes",
        "row_count", "cardinality_limit_exceeded", "payload_limit_exceeded",
    ))
    sql = """SELECT {outer}
               FROM (
                 WITH limited AS MATERIALIZED (
                   SELECT {limited}
                     {from_sql}
                    ORDER BY 1 LIMIT %s
                 ), sized AS MATERIALIZED (
                   SELECT limited.*{size_columns},
                          COUNT(*) OVER ()::bigint AS row_count
                     FROM limited
                 ), totaled AS MATERIALIZED (
                   SELECT sized.*{max_columns},
                          0::bigint AS query_json_bytes,
                          SUM({size_sum}) OVER ()::bigint AS query_text_bytes
                     FROM sized
                 ), decided AS MATERIALIZED (
                   SELECT totaled.*,
                          query_text_bytes::bigint AS query_variable_bytes
                     FROM totaled
                 ), gated AS MATERIALIZED (
                   SELECT decided.*,
                          ({cap_conditions}) AS bytes_allowed
                     FROM decided
                 )
                 SELECT {inner}
                   FROM gated
               ) AS bounded
              ORDER BY bounded.id""".format(
        outer=",".join("bounded." + name for name in outer_fields),
        limited=",".join(limited_fields),
        from_sql=spec["from"],
        size_columns=("," + ",".join(size_fields)) if size_fields else "",
        max_columns=("," + ",".join(max_fields)) if max_fields else "",
        size_sum=size_sum,
        cap_conditions=" AND ".join(cap_conditions),
        inner=",".join(inner_fields),
    )
    params = (
        (company_id,) * spec["company_params"]
        + (MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS + 1,)
        + tuple(cap for _name, _expression, cap in spec["variables"])
        + (_MAX_QUERY_VARIABLE_BYTES, remaining_bytes)
        + (MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS,) * (len(variables) + 2)
    )
    return sql, params


def _fetched_rows(cur):
    rows = cur.fetchall() or []
    if type(rows) not in (list, tuple):
        _fail(_CONTRACT_INVALID)
    detached = []
    for row in rows:
        if not isinstance(row, Mapping):
            _fail(_CONTRACT_INVALID)
        detached.append(dict(row))
    return detached


def _exact_nonnegative_int(value):
    return value if type(value) is int and value >= 0 else None


def _utf8_size(value):
    if value is None:
        return 0
    if type(value) is not str:
        _fail(_CONTRACT_INVALID)
    try:
        return len(value.encode("utf-8"))
    except UnicodeError:
        _fail(_CONTRACT_INVALID)


def _accepted_value(field, value):
    if field == "month":
        return value
    if value is None:
        return None
    if type(value) is not str or len(value) > _MAX_TEXT_FIELD_BYTES:
        _fail(_CONTRACT_INVALID)
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, OverflowError):
        _fail(_CONTRACT_INVALID)
    if not number.is_finite():
        _fail(_CONTRACT_INVALID)
    return number


def _validate_source_rows(source, rows, budget):
    spec = _SOURCE_SPECS[source]
    fixed = tuple(name for name, _expression in spec["fixed"])
    variables = tuple(name for name, _expression, _cap in spec["variables"])
    metadata = tuple("field_" + name + "_bytes" for name in variables)
    expected_keys = set(fixed + variables + metadata + (
        "query_json_bytes", "query_text_bytes", "query_variable_bytes",
        "row_count", "cardinality_limit_exceeded", "payload_limit_exceeded",
    ))
    if len(rows) > MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS + 1:
        _fail(_CONTRACT_INVALID)
    if not rows:
        return "accepted", []

    expected_count = rows[0].get("row_count")
    query_json = rows[0].get("query_json_bytes")
    query_text = rows[0].get("query_text_bytes")
    query_variable = rows[0].get("query_variable_bytes")
    cardinality_flag = rows[0].get("cardinality_limit_exceeded")
    payload_flag = rows[0].get("payload_limit_exceeded")
    if (
        _exact_nonnegative_int(expected_count) is None
        or _exact_nonnegative_int(query_json) is None
        or _exact_nonnegative_int(query_text) is None
        or _exact_nonnegative_int(query_variable) is None
        or type(cardinality_flag) is not bool
        or type(payload_flag) is not bool
        or expected_count != len(rows)
        or query_json != 0
        or query_variable != query_text
    ):
        _fail(_CONTRACT_INVALID)

    field_total = 0
    field_overflow = False
    accepted_rows = []
    denied = cardinality_flag or payload_flag
    for row in rows:
        if set(row) != expected_keys:
            _fail(_CONTRACT_INVALID)
        if (
            row["row_count"] != expected_count
            or row["query_json_bytes"] != query_json
            or row["query_text_bytes"] != query_text
            or row["query_variable_bytes"] != query_variable
            or row["cardinality_limit_exceeded"] is not cardinality_flag
            or row["payload_limit_exceeded"] is not payload_flag
        ):
            _fail(_CONTRACT_INVALID)
        clean = {name: row[name] for name in fixed}
        for name, _expression, cap in spec["variables"]:
            field_bytes = row["field_" + name + "_bytes"]
            if _exact_nonnegative_int(field_bytes) is None:
                _fail(_CONTRACT_INVALID)
            field_total += field_bytes
            field_overflow = field_overflow or field_bytes > cap
            if denied:
                if row[name] is not None:
                    _fail(_CONTRACT_INVALID)
            elif _utf8_size(row[name]) != field_bytes:
                _fail(_CONTRACT_INVALID)
            clean[name] = (
                None if denied else _accepted_value(name, row[name])
            )
        clean["owner_status"] = "verified"
        accepted_rows.append(clean)
    if field_total != query_text:
        _fail(_CONTRACT_INVALID)

    cardinality = expected_count > MAX_ACCOUNTING_EXCEPTION_SOURCE_ROWS
    overflow = (
        field_overflow
        or query_text > _MAX_QUERY_VARIABLE_BYTES
        or query_variable > budget.remaining
    )
    if cardinality_flag is not cardinality:
        _fail(_CONTRACT_INVALID)
    if payload_flag is not (not cardinality and overflow):
        _fail(_CONTRACT_INVALID)
    if cardinality:
        return "cardinality", []
    if payload_flag:
        return "overflow", []
    budget.consume(query_variable)
    return "accepted", accepted_rows


def collect_accounting_exception_snapshot(cur, company_id):
    """Collect one detached snapshot; the caller owns the transaction."""

    if (
        type(company_id) is not int
        or company_id <= 0
        or not callable(getattr(cur, "execute", None))
        or not callable(getattr(cur, "fetchall", None))
    ):
        _fail(_INPUT_INVALID)
    budget = _VariableByteBudget()
    rows_by_source = {}
    for source in ACCOUNTING_EXCEPTION_SOURCES:
        sql, params = _source_query(source, company_id, budget.remaining)
        cur.execute(sql, params)
        state, rows = _validate_source_rows(
            source, _fetched_rows(cur), budget
        )
        if state != "accepted":
            empty = {name: [] for name in ACCOUNTING_EXCEPTION_SOURCES}
            return build_accounting_exception_projection(
                company_id, empty, scan_complete=False
            )
        rows_by_source[source] = rows
    return build_accounting_exception_projection(company_id, rows_by_source)


def run_accounting_exception_snapshot(get_db, company_id):
    """Collect one company's verified accounting rows in one transaction."""

    if not callable(get_db) or type(company_id) is not int or company_id <= 0:
        _fail(_INPUT_INVALID)
    connection = None
    cur = None
    result = None
    primary_error = None
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
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure_transaction(cur)
        result = collect_accounting_exception_snapshot(cur, company_id)
    except BaseException as exc:
        primary_error = exc
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
        _fail(_ROLLBACK_FAILED)
    if primary_error is not None:
        if (
            isinstance(primary_error, AccountingExceptionSnapshotError)
            and primary_error.args in ((_INPUT_INVALID,), (_CONTRACT_INVALID,))
        ):
            raise primary_error from None
        _fail(_READ_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    if type(result) is not dict:
        _fail(_CONTRACT_INVALID)
    return result


__all__ = []
