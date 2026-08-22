"""Private same-transaction authorization for assignment/daily previews."""

import psycopg2.extras

from .snapshot import (
    AssignmentDailySnapshot,
    AssignmentDailySnapshotError,
    AssignmentDailySnapshotRequest,
    _configure_transaction,
    collect_assignment_daily_snapshot,
)


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "assignment_daily_snapshot_input_invalid"
_NOT_FOUND = "assignment_daily_preview_not_found"
_READ_FAILED = "assignment_daily_snapshot_read_failed"
_ROLLBACK_FAILED = "assignment_daily_snapshot_rollback_failed"
_CLEANUP_FAILED = "assignment_daily_snapshot_cleanup_failed"
_ROLES = ("директор", "зам_директора")

_AUTHORIZATION_SQL = """
WITH actor AS MATERIALIZED (
    SELECT membership.id,
           membership.role
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
       AND membership.role IN ('директор','зам_директора')
       AND membership.active IS TRUE
       AND company.active IS TRUE
       AND membership.platform_account_id=company.platform_account_id
       AND platform_account.active IS TRUE
       AND platform_account.status='active'
     ORDER BY membership.id
     LIMIT %s
),
actor_count AS MATERIALIZED (
    SELECT COUNT(*)::bigint AS actor_count,
           MIN(actor.role) AS role
      FROM actor
)
SELECT actor_count.actor_count,
       actor_count.role,
       CASE
         WHEN actor_count.actor_count=1 THEN EXISTS (
             SELECT 1
               FROM public.projects project
              WHERE project.id=%s
                AND project.company_id=%s
         )
         ELSE FALSE
       END AS project_exists
  FROM actor_count
"""


class AssignmentDailyPreviewError(ValueError):
    """Fixed, source-free error at the HTTP preview runtime boundary."""


def _fail(code):
    raise AssignmentDailyPreviewError(code) from None


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and type(value.get("sessionHash")) is str
        and len(value["sessionHash"]) == 64
        and all(character in "0123456789abcdef" for character in value["sessionHash"])
    )


def _authorize(cur, authentication, request):
    cur.execute(
        _AUTHORIZATION_SQL,
        (
            authentication["sessionHash"],
            request.company_id,
            2,
            request.project_id,
            request.company_id,
        ),
    )
    rows = cur.fetchall()
    if type(rows) not in (list, tuple) or len(rows) != 1:
        _fail(_READ_FAILED)
    row = rows[0]
    if not isinstance(row, dict):
        try:
            row = dict(row)
        except Exception:
            _fail(_READ_FAILED)
    if set(row) != {"actor_count", "project_exists", "role"}:
        _fail(_READ_FAILED)
    actor_count = row.get("actor_count")
    project_exists = row.get("project_exists")
    role = row.get("role")
    if (
        type(actor_count) is not int
        or actor_count < 0
        or type(project_exists) is not bool
        or (role is not None and type(role) is not str)
    ):
        _fail(_READ_FAILED)
    if (
        actor_count != 1
        or project_exists is not True
        or role not in _ROLES
    ):
        _fail(_NOT_FOUND)


def run_authorized_assignment_daily_snapshot(get_db, authentication, request):
    """Authorize and collect one snapshot, then always roll back and close."""

    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or type(request) is not AssignmentDailySnapshotRequest
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
        _authorize(cur, authentication, request)
        result = collect_assignment_daily_snapshot(cur, request)
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
        if (
            type(primary_error) is AssignmentDailyPreviewError
            and primary_error.args in ((_NOT_FOUND,), (_INPUT_INVALID,))
        ):
            _fail(primary_error.args[0])
        if (
            type(primary_error) is AssignmentDailySnapshotError
            and primary_error.args == (_INPUT_INVALID,)
        ):
            _fail(_INPUT_INVALID)
        _fail(_READ_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    if type(result) is not AssignmentDailySnapshot:
        _fail(_READ_FAILED)
    return result


__all__ = []
