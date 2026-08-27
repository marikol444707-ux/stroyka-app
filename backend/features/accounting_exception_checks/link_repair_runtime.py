"""Authorized preview and atomic apply runtime for A11.9 link repairs."""

from collections.abc import Mapping

import psycopg2.extras

from .link_repair_plan import (
    LinkRepairPlanError,
    MAX_SOURCE_ROWS,
    build_accounting_link_repair_plan,
)


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "accounting_link_repair_input_invalid"
_AUTHENTICATION_REQUIRED = "accounting_link_repair_authentication_required"
_REQUEST_FORBIDDEN = "accounting_link_repair_request_forbidden"
_READ_FAILED = "accounting_link_repair_read_failed"
_PLAN_STALE = "accounting_link_repair_plan_stale"
_PLAN_BLOCKED = "accounting_link_repair_plan_blocked"
_BUSY = "accounting_link_repair_busy"
_WRITE_FAILED = "accounting_link_repair_write_failed"
_COMMIT_UNCERTAIN = "accounting_link_repair_commit_uncertain"
_ROLLBACK_FAILED = "accounting_link_repair_rollback_failed"
_CLEANUP_FAILED = "accounting_link_repair_cleanup_failed"
_ERRORS = frozenset({
    _INPUT_INVALID,
    _AUTHENTICATION_REQUIRED,
    _REQUEST_FORBIDDEN,
    _READ_FAILED,
    _PLAN_STALE,
    _PLAN_BLOCKED,
    _BUSY,
    _WRITE_FAILED,
    _COMMIT_UNCERTAIN,
    _ROLLBACK_FAILED,
    _CLEANUP_FAILED,
})


class AccountingLinkRepairRuntimeError(ValueError):
    """Fixed lifecycle error that never exposes database details."""

    def __init__(self, code):
        self.code = code if code in _ERRORS else _READ_FAILED
        super().__init__(self.code)


def _fail(code):
    raise AccountingLinkRepairRuntimeError(code) from None


def _positive_int(value):
    return type(value) is int and 0 < value <= 9223372036854775807


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and type(value.get("sessionHash")) is str
        and len(value["sessionHash"]) == 64
        and all(character in "0123456789abcdef" for character in value["sessionHash"])
    )


def _valid_finance_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(type(role) is str and 0 < len(role) <= 64 for role in value)
    )


def _valid_sha(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _detached_rows(cur, fields, *, maximum):
    rows = cur.fetchall()
    if type(rows) not in (list, tuple) or len(rows) > maximum:
        _fail(_READ_FAILED)
    result = []
    expected = set(fields)
    for row in rows:
        if not isinstance(row, Mapping):
            _fail(_READ_FAILED)
        item = dict(row)
        if set(item) != expected:
            _fail(_READ_FAILED)
        result.append(item)
    return result


def _configure(cur):
    cur.execute(
        "SELECT pg_catalog.set_config('statement_timeout','10000',true)"
    )
    cur.execute(
        "SELECT pg_catalog.set_config('lock_timeout','3000',true)"
    )
    cur.execute(
        "SELECT pg_catalog.set_config('idle_in_transaction_session_timeout','15000',true)"
    )


def _authorize(cur, authentication, company_id, finance_roles):
    cur.execute(
        """SELECT u.id AS user_id
             FROM public.user_sessions s
             JOIN public.users u ON u.id=s.user_id
            WHERE s.session_hash=%s
              AND s.revoked_at IS NULL
              AND s.expires_at>NOW()
              AND s.two_factor_passed IS TRUE
              AND COALESCE(u.active,TRUE)=TRUE
            ORDER BY u.id LIMIT 2""",
        (authentication["sessionHash"],),
    )
    sessions = _detached_rows(cur, ("user_id",), maximum=2)
    if len(sessions) != 1 or not _positive_int(sessions[0]["user_id"]):
        _fail(_AUTHENTICATION_REQUIRED)
    user_id = sessions[0]["user_id"]

    cur.execute(
        """SELECT m.id AS membership_id,m.role
             FROM public.user_company_roles m
             JOIN public.companies c ON c.id=m.company_id
            WHERE m.user_id=%s
              AND m.company_id=%s
              AND COALESCE(m.active,TRUE)=TRUE
              AND COALESCE(c.active,TRUE)=TRUE
            ORDER BY m.id LIMIT 2""",
        (user_id, company_id),
    )
    memberships = _detached_rows(
        cur, ("membership_id", "role"), maximum=2,
    )
    if (
        len(memberships) != 1
        or not _positive_int(memberships[0]["membership_id"])
        or type(memberships[0]["role"]) is not str
        or memberships[0]["role"] not in finance_roles
    ):
        _fail(_REQUEST_FORBIDDEN)
    return {
        "user_id": user_id,
        "membership_id": memberships[0]["membership_id"],
        "role": memberships[0]["role"],
    }


def _collect_sources(cur, company_id):
    limit = MAX_SOURCE_ROWS + 1
    cur.execute(
        """SELECT id,company_id,name
             FROM public.projects
            WHERE company_id=%s
            ORDER BY id LIMIT %s""",
        (company_id, limit),
    )
    projects = _detached_rows(
        cur, ("id", "company_id", "name"), maximum=MAX_SOURCE_ROWS,
    )

    cur.execute(
        """SELECT id,company_id,supplier_id,COALESCE(supplier_name,'') AS supplier_name,
                  COALESCE(project_name,'') AS project_name,COALESCE(amount,0) AS amount,
                  offer_id,request_id,warehouse_invoice_id,COALESCE(status,'') AS status,
                  COALESCE(invoice_number,'') AS invoice_number,
                  COALESCE(invoice_date::text,'') AS invoice_date
             FROM public.supplier_invoices
            WHERE company_id=%s
            ORDER BY id LIMIT %s""",
        (company_id, limit),
    )
    suppliers = _detached_rows(
        cur,
        (
            "id", "company_id", "supplier_id", "supplier_name", "project_name",
            "amount", "offer_id", "request_id", "warehouse_invoice_id", "status",
            "invoice_number", "invoice_date",
        ),
        maximum=MAX_SOURCE_ROWS,
    )

    cur.execute(
        """SELECT id,company_id,supplier_id,COALESCE(supplier_name,'') AS supplier_name,
                  COALESCE(NULLIF(BTRIM(project),''),NULLIF(BTRIM(location),''),'') AS project,
                  COALESCE(total_with_vat,0) AS total_with_vat,
                  COALESCE(total_base,0) AS total_base,supply_delivery_id,
                  supply_request_id,supplier_invoice_id,COALESCE(status,'') AS status,
                  COALESCE(number,'') AS number,COALESCE(date::text,'') AS date
             FROM public.warehouse_invoices
            WHERE company_id=%s
            ORDER BY id LIMIT %s""",
        (company_id, limit),
    )
    warehouses = _detached_rows(
        cur,
        (
            "id", "company_id", "supplier_id", "supplier_name", "project",
            "total_with_vat", "total_base", "supply_delivery_id",
            "supply_request_id", "supplier_invoice_id", "status",
            "number", "date",
        ),
        maximum=MAX_SOURCE_ROWS,
    )

    cur.execute(
        """SELECT id,company_id,offer_id,request_id,supplier_id,
                  COALESCE(supplier_name,'') AS supplier_name,
                  COALESCE(project,'') AS project,COALESCE(status,'') AS status
             FROM public.supply_deliveries
            WHERE company_id=%s
            ORDER BY id LIMIT %s""",
        (company_id, limit),
    )
    deliveries = _detached_rows(
        cur,
        (
            "id", "company_id", "offer_id", "request_id", "supplier_id",
            "supplier_name", "project", "status",
        ),
        maximum=MAX_SOURCE_ROWS,
    )
    return {
        "company_id": company_id,
        "projects": projects,
        "supplier_invoices": suppliers,
        "warehouse_invoices": warehouses,
        "deliveries": deliveries,
    }


def _build_plan(cur, company_id):
    try:
        return build_accounting_link_repair_plan(
            **_collect_sources(cur, company_id)
        )
    except AccountingLinkRepairRuntimeError:
        raise
    except LinkRepairPlanError:
        _fail(_READ_FAILED)
    except MemoryError:
        raise
    except Exception:
        _fail(_READ_FAILED)


def _lock_plan_rows(cur, plan):
    supplier_ids = sorted(
        repair.supplier_invoice_id for repair in plan.repairs
    )
    warehouse_ids = sorted(
        repair.warehouse_invoice_id for repair in plan.repairs
        if repair.action == "link_pair"
    )
    cur.execute(
        """SELECT id FROM public.supplier_invoices
            WHERE company_id=%s AND id = ANY(%s)
            ORDER BY id FOR UPDATE""",
        (plan.company_id, supplier_ids),
    )
    locked_suppliers = _detached_rows(
        cur, ("id",), maximum=len(supplier_ids),
    )
    locked_warehouses = []
    if warehouse_ids:
        cur.execute(
            """SELECT id FROM public.warehouse_invoices
                WHERE company_id=%s AND id = ANY(%s)
                ORDER BY id FOR UPDATE""",
            (plan.company_id, warehouse_ids),
        )
        locked_warehouses = _detached_rows(
            cur, ("id",), maximum=len(warehouse_ids),
        )
    if (
        [row["id"] for row in locked_suppliers] != supplier_ids
        or [row["id"] for row in locked_warehouses] != warehouse_ids
    ):
        _fail(_PLAN_STALE)


def _matches_expected(plan, count, sha256):
    return len(plan.repairs) == count and plan.plan_sha256 == sha256


def _apply_plan(cur, plan, actor):
    for repair in plan.repairs:
        if repair.action == "link_pair":
            cur.execute(
                """UPDATE public.supplier_invoices
                      SET warehouse_invoice_id=%s
                    WHERE id=%s AND company_id=%s""",
                (
                    repair.warehouse_invoice_id,
                    repair.supplier_invoice_id,
                    repair.company_id,
                ),
            )
            if cur.rowcount != 1:
                _fail(_PLAN_STALE)
            cur.execute(
                """UPDATE public.warehouse_invoices
                      SET supplier_invoice_id=%s
                    WHERE id=%s AND company_id=%s""",
                (
                    repair.supplier_invoice_id,
                    repair.warehouse_invoice_id,
                    repair.company_id,
                ),
            )
            audit_action = "accounting_supplier_warehouse_link_repaired"
            audit_description = "supplier/warehouse document link repaired"
        elif repair.action == "clear_dangling_supplier_link":
            cur.execute(
                """UPDATE public.supplier_invoices
                      SET warehouse_invoice_id=NULL
                    WHERE id=%s AND company_id=%s AND warehouse_invoice_id=%s""",
                (
                    repair.supplier_invoice_id,
                    repair.company_id,
                    repair.warehouse_invoice_id,
                ),
            )
            audit_action = "accounting_supplier_dangling_warehouse_link_cleared"
            audit_description = "missing warehouse document link cleared"
        else:
            _fail(_WRITE_FAILED)
        if cur.rowcount != 1:
            _fail(_PLAN_STALE)
        cur.execute(
            """INSERT INTO public.audit_log
                 (user_id,user_name,user_role,action,entity_type,entity_id,
                  description,owner_scope,company_id,project_id)
               VALUES (%s,'authenticated_user',%s,%s,
                       'supplier_invoice',%s,%s,
                       'company',%s,%s)
               RETURNING id""",
            (
                actor["user_id"], actor["role"], audit_action,
                repair.supplier_invoice_id, audit_description,
                repair.company_id, repair.project_id,
            ),
        )
        audit = cur.fetchone()
        if (
            not isinstance(audit, Mapping)
            or set(audit) != {"id"}
            or not _positive_int(audit["id"])
        ):
            _fail(_WRITE_FAILED)


def _run_transaction(get_db, *, readonly, operation):
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_error = None
    commit_error = None
    first_control = None
    completed = False
    try:
        connection = get_db()
        connection.set_session(
            readonly=readonly,
            autocommit=False,
            isolation_level="REPEATABLE READ" if readonly else "SERIALIZABLE",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure(cur)
        result = operation(cur)
        if readonly:
            connection.rollback()
        else:
            try:
                connection.commit()
            except BaseException as error:
                commit_error = error
                if isinstance(error, _CONTROL_FLOW):
                    first_control = error
                raise
        completed = True
    except BaseException as error:
        primary_error = error
        if isinstance(error, _CONTROL_FLOW) and first_control is None:
            first_control = error

    if connection is not None and not completed:
        try:
            connection.rollback()
        except BaseException as error:
            rollback_error = error
            if isinstance(error, _CONTROL_FLOW) and first_control is None:
                first_control = error
    if cur is not None:
        try:
            cur.close()
        except BaseException as error:
            cleanup_error = error
            if isinstance(error, _CONTROL_FLOW) and first_control is None:
                first_control = error
    if connection is not None:
        try:
            connection.close()
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
            if isinstance(error, _CONTROL_FLOW) and first_control is None:
                first_control = error

    if first_control is not None:
        raise first_control
    if rollback_error is not None:
        _fail(_ROLLBACK_FAILED)
    if commit_error is not None:
        _fail(_COMMIT_UNCERTAIN)
    if primary_error is not None:
        if isinstance(primary_error, AccountingLinkRepairRuntimeError):
            raise primary_error from None
        if getattr(primary_error, "pgcode", None) in {
            "40001", "40P01", "55P03", "57014",
        }:
            _fail(_BUSY)
        _fail(_READ_FAILED if readonly else _WRITE_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    return result


def _validate_common(get_db, authentication, company_id, finance_roles):
    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or not _positive_int(company_id)
        or not _valid_finance_roles(finance_roles)
    ):
        _fail(_INPUT_INVALID)


def preview_accounting_link_repairs(
    get_db, authentication, company_id, finance_roles,
):
    """Return one bounded public preview and perform no writes."""

    _validate_common(get_db, authentication, company_id, finance_roles)

    def operation(cur):
        _authorize(cur, authentication, company_id, finance_roles)
        return _build_plan(cur, company_id).public_result()

    return _run_transaction(get_db, readonly=True, operation=operation)


def apply_accounting_link_repairs(
    get_db,
    authentication,
    company_id,
    finance_roles,
    *,
    expected_repair_count,
    expected_plan_sha256,
):
    """Rebuild, lock, revalidate and atomically apply one exact plan."""

    _validate_common(get_db, authentication, company_id, finance_roles)
    if (
        type(expected_repair_count) is not int
        or not 1 <= expected_repair_count <= 100
        or not _valid_sha(expected_plan_sha256)
    ):
        _fail(_INPUT_INVALID)

    def operation(cur):
        actor = _authorize(cur, authentication, company_id, finance_roles)
        plan = _build_plan(cur, company_id)
        if plan.state == "blocked":
            _fail(_PLAN_BLOCKED)
        if not _matches_expected(
            plan, expected_repair_count, expected_plan_sha256,
        ):
            _fail(_PLAN_STALE)
        _lock_plan_rows(cur, plan)
        locked_plan = _build_plan(cur, company_id)
        if not _matches_expected(
            locked_plan, expected_repair_count, expected_plan_sha256,
        ):
            _fail(_PLAN_STALE)
        try:
            _apply_plan(cur, locked_plan, actor)
        except AccountingLinkRepairRuntimeError:
            raise
        except MemoryError:
            raise
        except Exception:
            _fail(_WRITE_FAILED)
        return {
            "ok": True,
            "appliedCount": len(locked_plan.repairs),
            "unresolvedCount": locked_plan.unresolved_count,
            "planSha256": locked_plan.plan_sha256,
        }

    return _run_transaction(get_db, readonly=False, operation=operation)


__all__ = []
