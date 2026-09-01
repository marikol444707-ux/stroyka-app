import datetime as dt
import json
import re
import uuid
from collections.abc import Mapping

import psycopg2.extras
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from .subscription_state import billing_state


SUBSCRIPTION_READ_ONLY_CODE = "subscription_read_only"
SUBSCRIPTION_CHECK_UNAVAILABLE_CODE = "subscription_check_unavailable"
SUBSCRIPTION_READ_ONLY_MESSAGE = (
    "Срок подписки закончился. Компания работает в режиме «только просмотр»: "
    "просмотр данных доступен, создание и изменения заблокированы до продления."
)

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_EXEMPT_MUTATION_PATHS = frozenset({
    "/login",
    "/logout",
    "/register",
    "/client-errors",
    "/password-reset-request",
    "/password-reset",
    "/password-reset/request",
    "/password-reset/confirm",
})
_EXEMPT_MUTATION_PREFIXES = (
    "/login/",
    "/site/",
)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def should_check_subscription_access(method, path):
    normalized_method = str(method or "GET").strip().upper()
    normalized_path = str(path or "").strip() or "/"
    if normalized_method in _READ_METHODS:
        return False
    if normalized_path in _EXEMPT_MUTATION_PATHS:
        return False
    return not any(normalized_path.startswith(prefix) for prefix in _EXEMPT_MUTATION_PREFIXES)


def _row_mapping(cur, row):
    if row is None:
        return None
    if isinstance(row, Mapping):
        return dict(row)
    columns = [column[0] for column in (getattr(cur, "description", None) or [])]
    if isinstance(row, (list, tuple)) and len(columns) == len(row):
        return dict(zip(columns, row))
    raise TypeError("Company subscription query returned a row without column mapping")


def load_company_billing_state(cur, company_id, *, today=None):
    cur.execute(
        """SELECT id, plan, trial_until, plan_expires_at, payment_status, suspended_at
             FROM companies
            WHERE id=%s
            LIMIT 1""",
        (int(company_id),),
    )
    company = _row_mapping(cur, cur.fetchone())
    if not company:
        raise LookupError("Company subscription record not found")
    return billing_state(company, today=today)


def _error_response(status_code, code, detail, **extra):
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "code": code, "detail": detail, **extra},
    )


def _request_correlation_id(request):
    candidate = str(request.headers.get("x-request-id") or "").strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def _write_structured_log(payload):
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def register_subscription_read_only_middleware(app, deps):
    get_db = deps["get_db"]
    request_user_snapshot = deps["request_user_snapshot"]
    resolve_work_company_context = deps["resolve_work_company_context"]
    platform_staff_roles = frozenset(deps.get("platform_staff_roles") or ())
    today_provider = deps.get("today") or dt.date.today

    @app.middleware("http")
    async def subscription_read_only_middleware(request, call_next):
        if not should_check_subscription_access(request.method, request.url.path):
            return await call_next(request)

        conn = None
        cur = None
        rejection = None
        correlation_id = _request_correlation_id(request)
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            user = request_user_snapshot(request, cur) or {}
            role = str(user.get("role") or "").strip()
            if user and role not in platform_staff_roles:
                try:
                    context = resolve_work_company_context(
                        cur,
                        user,
                        None,
                        "write",
                        x_company_id=request.headers.get("x-company-id"),
                        x_company_mode=request.headers.get("x-company-mode"),
                    )
                except HTTPException as exc:
                    _write_structured_log({
                        "event": "subscription_company_context_rejected",
                        "correlationId": correlation_id,
                        "method": str(request.method or "").upper(),
                        "path": str(request.url.path or "/")[:240],
                        "statusCode": int(exc.status_code),
                    })
                    rejection = _error_response(
                        int(exc.status_code),
                        "company_context_invalid",
                        exc.detail,
                    )
                    context = None

                company_id = (
                    (context or {}).get("companyId")
                    or (context or {}).get("company_id")
                    or user.get("companyId")
                    or user.get("company_id")
                )
                if rejection is None and company_id:
                    state = load_company_billing_state(cur, company_id, today=today_provider())
                    if state and state.get("readOnly"):
                        _write_structured_log({
                            "event": "subscription_write_blocked",
                            "correlationId": correlation_id,
                            "companyId": int(company_id),
                            "method": str(request.method or "").upper(),
                            "path": str(request.url.path or "/")[:240],
                            "billingStatus": state.get("status") or "unknown",
                        })
                        rejection = _error_response(
                            403,
                            SUBSCRIPTION_READ_ONLY_CODE,
                            SUBSCRIPTION_READ_ONLY_MESSAGE,
                            billingState=state,
                        )
        except Exception as exc:
            _write_structured_log({
                "event": "subscription_access_check_failed",
                "correlationId": correlation_id,
                "method": str(request.method or "").upper(),
                "path": str(request.url.path or "/")[:240],
                "errorType": exc.__class__.__name__,
            })
            rejection = _error_response(
                503,
                SUBSCRIPTION_CHECK_UNAVAILABLE_CODE,
                "Не удалось проверить доступ компании. Повторите действие позже.",
            )
        finally:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        if rejection is not None:
            rejection.headers["X-Request-Id"] = correlation_id
            return rejection
        return await call_next(request)

    return subscription_read_only_middleware
