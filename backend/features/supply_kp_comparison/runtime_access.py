"""Same-snapshot authorization for one supply technical comparison."""

from collections.abc import Mapping

import psycopg2.extras

from . import source_resolver


_MAX_ID = 9223372036854775807
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "supply_technical_comparison_access_input_invalid"
_NOT_FOUND = "supply_technical_comparison_access_not_found"
_READ_FAILED = "supply_technical_comparison_access_read_failed"
_ROLLBACK_FAILED = "supply_technical_comparison_access_rollback_failed"
_CLEANUP_FAILED = "supply_technical_comparison_access_cleanup_failed"
_CODES = frozenset({
    _INPUT_INVALID,
    _NOT_FOUND,
    _READ_FAILED,
    _ROLLBACK_FAILED,
    _CLEANUP_FAILED,
})
_ACTOR_FIELDS = frozenset({
    "actor_user_id",
    "actor_membership_id",
    "actor_company_id",
    "actor_role",
})


class SupplyTechnicalComparisonAccessError(ValueError):
    """Fixed public-safe runtime error."""

    def __init__(self, code):
        self.code = code if code in _CODES else _READ_FAILED
        super().__init__(self.code)


class _ActorNotFound(Exception):
    pass


def _fail(code):
    raise SupplyTechnicalComparisonAccessError(code) from None


def _positive_id(value):
    return type(value) is int and 0 < value <= _MAX_ID


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and type(value.get("sessionHash")) is str
        and len(value["sessionHash"]) == 64
        and all(character in "0123456789abcdef" for character in value["sessionHash"])
    )


def _valid_roles(value):
    return (
        type(value) is tuple
        and 0 < len(value) <= 10
        and len(value) == len(set(value))
        and all(
            type(role) is str
            and 0 < len(role.encode("utf-8")) <= 64
            for role in value
        )
    )


def _validate_inputs(get_db, authentication, allowed_roles, values):
    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or not _valid_roles(allowed_roles)
        or set(values) != {
            "company_id",
            "project_id",
            "request_id",
            "source_kind",
            "source_id",
            "file_id",
        }
        or not all(
            _positive_id(values[name])
            for name in (
                "company_id",
                "project_id",
                "request_id",
                "source_id",
                "file_id",
            )
        )
        or type(values.get("source_kind")) is not str
        or values["source_kind"] not in source_resolver.SOURCE_KINDS
    ):
        _fail(_INPUT_INVALID)


def _configure_transaction(cursor):
    cursor.execute("SET LOCAL statement_timeout='60s'")
    cursor.execute("SET LOCAL lock_timeout='5s'")
    cursor.execute("SET LOCAL idle_in_transaction_session_timeout='60s'")
    cursor.execute("SET LOCAL search_path=pg_catalog,public")


def _authorize(cursor, authentication, company_id, allowed_roles):
    cursor.execute(
        """SELECT actor_user.id AS actor_user_id,
                  membership.id AS actor_membership_id,
                  company.id AS actor_company_id,
                  membership.role AS actor_role
             FROM public.user_sessions session
             JOIN public.users actor_user
               ON actor_user.id=session.user_id
             JOIN public.user_company_roles membership
               ON membership.user_id=actor_user.id
             JOIN public.companies company
               ON company.id=membership.company_id
             JOIN public.platform_accounts platform_account
               ON platform_account.id=company.platform_account_id
            WHERE session.session_hash=%s
              AND membership.company_id=%s
              AND session.revoked_at IS NULL
              AND session.expires_at>clock_timestamp()
              AND session.two_factor_passed IS TRUE
              AND actor_user.active IS TRUE
              AND actor_user.two_factor_enabled IS TRUE
              AND membership.active IS TRUE
              AND company.active IS TRUE
              AND membership.platform_account_id=company.platform_account_id
              AND platform_account.active IS TRUE
              AND platform_account.status='active'
            ORDER BY membership.id
            LIMIT %s""",
        (authentication["sessionHash"], company_id, 2),
    )
    try:
        raw_rows = cursor.fetchall()
        if type(raw_rows) not in (list, tuple):
            raise TypeError
        rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)]
    except Exception:
        _fail(_READ_FAILED)
    if len(rows) != 1 or len(raw_rows) != 1:
        raise _ActorNotFound()
    actor = rows[0]
    if (
        set(actor) != _ACTOR_FIELDS
        or not _positive_id(actor.get("actor_user_id"))
        or not _positive_id(actor.get("actor_membership_id"))
        or actor.get("actor_company_id") != company_id
        or type(actor.get("actor_role")) is not str
        or actor["actor_role"] not in allowed_roles
    ):
        raise _ActorNotFound()


def run_authorized_supply_technical_comparison(
    get_db,
    authentication,
    allowed_roles,
    *,
    company_id,
    project_id,
    request_id,
    source_kind,
    source_id,
    file_id,
):
    """Authorize and resolve one comparison, then always roll back."""

    values = {
        "company_id": company_id,
        "project_id": project_id,
        "request_id": request_id,
        "source_kind": source_kind,
        "source_id": source_id,
        "file_id": file_id,
    }
    _validate_inputs(get_db, authentication, allowed_roles, values)

    connection = None
    cursor = None
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
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        _configure_transaction(cursor)
        _authorize(cursor, authentication, company_id, allowed_roles)
        rows = source_resolver.load_supply_technical_source_rows(
            cursor,
            **values,
        )
        result = source_resolver.resolve_supply_technical_source_rows(
            rows,
            **values,
        )
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
    if cursor is not None:
        try:
            cursor.close()
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
    if isinstance(primary_error, _ActorNotFound):
        _fail(_NOT_FOUND)
    if isinstance(
        primary_error,
        source_resolver.SupplyTechnicalSourceResolverError,
    ):
        _fail(_NOT_FOUND)
    if primary_error is not None:
        if isinstance(primary_error, SupplyTechnicalComparisonAccessError):
            raise primary_error from None
        _fail(_READ_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    if type(result) is not dict:
        _fail(_READ_FAILED)
    return {
        **result,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }


__all__ = [
    "SupplyTechnicalComparisonAccessError",
    "run_authorized_supply_technical_comparison",
]
