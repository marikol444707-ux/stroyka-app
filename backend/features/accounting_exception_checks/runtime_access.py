"""Private one-company authorization boundary for the A11 snapshot."""

from collections.abc import Mapping

import psycopg2.extras

from .snapshot import (
    _configure_transaction,
    collect_accounting_exception_snapshot,
)


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "accounting_exception_review_input_invalid"
_AUTHENTICATION_REQUIRED = (
    "accounting_exception_review_authentication_required"
)
_REQUEST_FORBIDDEN = "accounting_exception_review_request_forbidden"
_READ_FAILED = "accounting_exception_review_read_failed"
_ROLLBACK_FAILED = "accounting_exception_review_rollback_failed"
_CLEANUP_FAILED = "accounting_exception_review_cleanup_failed"


class AccountingExceptionAccessError(ValueError):
    """Fixed private access/lifecycle error with no dependency text."""

    def __init__(self, code):
        allowed = {
            _INPUT_INVALID,
            _AUTHENTICATION_REQUIRED,
            _REQUEST_FORBIDDEN,
            _READ_FAILED,
            _ROLLBACK_FAILED,
            _CLEANUP_FAILED,
        }
        self.code = code if code in allowed else _READ_FAILED
        super().__init__(self.code)


def _fail(code):
    raise AccountingExceptionAccessError(code) from None


def _valid_authentication(value):
    if (
        type(value) is not dict
        or set(value) != {"authenticationKind", "sessionHash"}
        or value.get("authenticationKind") != "cookie_session"
    ):
        return False
    session_hash = value.get("sessionHash")
    return (
        type(session_hash) is str
        and len(session_hash) == 64
        and all(character in "0123456789abcdef" for character in session_hash)
    )


def _valid_finance_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(type(role) is str and 0 < len(role) <= 64 for role in value)
    )


def _rows(cur, keys):
    rows = cur.fetchall()
    if type(rows) not in (list, tuple) or len(rows) > 2:
        _fail(_READ_FAILED)
    detached = []
    for row in rows:
        if not isinstance(row, Mapping):
            _fail(_READ_FAILED)
        item = dict(row)
        if set(item) != set(keys):
            _fail(_READ_FAILED)
        detached.append(item)
    return detached


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
    sessions = _rows(cur, ("user_id",))
    if len(sessions) != 1:
        _fail(_AUTHENTICATION_REQUIRED)
    user_id = sessions[0]["user_id"]
    if type(user_id) is not int or user_id <= 0:
        _fail(_READ_FAILED)

    cur.execute(
        """SELECT m.role
             FROM public.user_company_roles m
             JOIN public.companies c ON c.id=m.company_id
            WHERE m.user_id=%s
              AND m.company_id=%s
              AND COALESCE(m.active,TRUE)=TRUE
              AND COALESCE(c.active,TRUE)=TRUE
            ORDER BY m.id LIMIT 2""",
        (user_id, company_id),
    )
    memberships = _rows(cur, ("role",))
    if (
        len(memberships) != 1
        or type(memberships[0]["role"]) is not str
        or memberships[0]["role"] not in finance_roles
    ):
        _fail(_REQUEST_FORBIDDEN)


def run_authorized_accounting_exception_snapshot(
    get_db,
    authentication,
    company_id,
    finance_roles,
):
    """Authorize and collect one immutable result in one transaction."""

    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or type(company_id) is not int
        or company_id <= 0
        or not _valid_finance_roles(finance_roles)
    ):
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
        _authorize(cur, authentication, company_id, finance_roles)
        result = collect_accounting_exception_snapshot(cur, company_id)
    except BaseException as error:
        primary_error = error
        if isinstance(error, _CONTROL_FLOW):
            first_control = error

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as error:
            if isinstance(error, _CONTROL_FLOW):
                if first_control is None:
                    first_control = error
            else:
                rollback_error = error
    if cur is not None:
        try:
            cur.close()
        except BaseException as error:
            if isinstance(error, _CONTROL_FLOW):
                if first_control is None:
                    first_control = error
            elif cleanup_error is None:
                cleanup_error = error
    if connection is not None:
        try:
            connection.close()
        except BaseException as error:
            if isinstance(error, _CONTROL_FLOW):
                if first_control is None:
                    first_control = error
            elif cleanup_error is None:
                cleanup_error = error

    if first_control is not None:
        raise first_control
    if rollback_error is not None:
        _fail(_ROLLBACK_FAILED)
    if primary_error is not None:
        if isinstance(primary_error, AccountingExceptionAccessError):
            raise primary_error from None
        _fail(_READ_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    if type(result) is not dict:
        _fail(_READ_FAILED)
    return result


__all__ = []
