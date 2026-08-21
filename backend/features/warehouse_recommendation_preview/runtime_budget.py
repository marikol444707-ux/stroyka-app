"""Private capacity and cooperative-deadline foundation for A9.3."""

import math
import threading
import time
import weakref
from typing import NamedTuple

import psycopg2
import psycopg2.extras


_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "warehouse_anomaly_runtime_input_invalid"
_BUSY = "warehouse_anomaly_runtime_busy"
_DEADLINE_EXCEEDED = "warehouse_anomaly_runtime_deadline_exceeded"
_READ_FAILED = "warehouse_anomaly_runtime_read_failed"
_ROLLBACK_FAILED = "warehouse_anomaly_runtime_rollback_failed"
_CLEANUP_FAILED = "warehouse_anomaly_runtime_cleanup_failed"
_CONTRACT_INVALID = "warehouse_anomaly_runtime_contract_invalid"
_OPERATION_SECONDS = 30.0
_MAX_MONOTONIC_RESOLUTION_SECONDS = 0.000001
_STATEMENT_TIMEOUT_MS = 5000
_CONNECT_TIMEOUT_SECONDS = 5
_MAX_SERVER_STATEMENTS = 18
_MAX_FETCH_RESULT_ROWS = 1_000
_MAX_FETCH_RESULT_NODES = 20_000
_MAX_FETCH_RESULT_DEPTH = 64
_MAX_FETCH_RESULT_TEXT_BYTES = 17_825_792
_DB_CONFIG_KEYS = ("dbname", "user", "password", "host", "port")
_STARTUP_OPTIONS = (
    "-c statement_timeout=5000 "
    "-c lock_timeout=1000 "
    "-c idle_in_transaction_session_timeout=10000 "
    "-c client_encoding=UTF8 "
    "-c search_path=pg_catalog,public"
)
_LEASE_TOKEN = object()
_RUNTIME_SLOT = threading.BoundedSemaphore(1)
_LEASE_STATE_LOCK = threading.RLock()
_LEASE_STATES = weakref.WeakKeyDictionary()
_CURSOR_STATE_LOCK = threading.RLock()
_CURSOR_STATES = weakref.WeakKeyDictionary()
_TRANSACTION_COMPLETE = object()
_BEGIN_SQL = "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
_ROLLBACK_SQL = "ROLLBACK"
_SETTINGS_SQL = """WITH configured AS MATERIALIZED (
    SELECT pg_catalog.set_config(%s, %s, true) AS statement_timeout,
           pg_catalog.set_config(%s, %s, true) AS lock_timeout,
           pg_catalog.set_config(%s, %s, true)
               AS idle_in_transaction_session_timeout,
           pg_catalog.set_config(%s, %s, true) AS search_path
)
SELECT pg_catalog.current_setting(%s) AS statement_timeout,
       pg_catalog.current_setting(%s) AS lock_timeout,
       pg_catalog.current_setting(%s)
           AS idle_in_transaction_session_timeout,
       pg_catalog.current_setting(%s) AS search_path,
       pg_catalog.current_setting(%s) AS client_encoding,
       pg_catalog.current_setting(%s) AS transaction_isolation,
       pg_catalog.current_setting(%s) AS transaction_read_only
  FROM configured"""
_SETTINGS_PARAMS = (
    "statement_timeout", "5s",
    "lock_timeout", "1s",
    "idle_in_transaction_session_timeout", "10s",
    "search_path", "pg_catalog, public",
    "statement_timeout",
    "lock_timeout",
    "idle_in_transaction_session_timeout",
    "search_path",
    "client_encoding",
    "transaction_isolation",
    "transaction_read_only",
)
_EXPECTED_SETTINGS_ROW = {
    "statement_timeout": "5s",
    "lock_timeout": "1s",
    "idle_in_transaction_session_timeout": "10s",
    "search_path": "pg_catalog, public",
    "client_encoding": "UTF8",
    "transaction_isolation": "repeatable read",
    "transaction_read_only": "on",
}


class WarehouseAnomalyRuntimeBudget(NamedTuple):
    deadline_monotonic: float
    statement_timeout_ms: int


class _WarehouseAnomalyRuntimeError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _raise_fixed_error(error):
    try:
        raise error from None
    except _WarehouseAnomalyRuntimeError as raised:
        raised.__context__ = None
        raise


def _fail(code):
    _raise_fixed_error(_WarehouseAnomalyRuntimeError(code))


def _finite_number(value):
    if type(value) not in (int, float):
        _fail(_INPUT_INVALID)
    try:
        converted = float(value)
    except OverflowError:
        _fail(_INPUT_INVALID)
    if (
        not math.isfinite(converted)
        or type(value) is int and converted != value
    ):
        _fail(_INPUT_INVALID)
    return converted


def _validate_budget(budget):
    if (
        type(budget) is not WarehouseAnomalyRuntimeBudget
        or type(budget.deadline_monotonic) is not float
        or not math.isfinite(budget.deadline_monotonic)
        or type(budget.statement_timeout_ms) is not int
        or budget.statement_timeout_ms != _STATEMENT_TIMEOUT_MS
    ):
        _fail(_INPUT_INVALID)


def _validated_db_config(db_config):
    if (
        type(db_config) is not dict
        or len(db_config) != len(_DB_CONFIG_KEYS)
        or any(type(key) is not str for key in db_config)
        or set(db_config) != set(_DB_CONFIG_KEYS)
    ):
        _fail(_INPUT_INVALID)

    copied = {}
    for key in _DB_CONFIG_KEYS:
        value = db_config[key]
        if type(value) is not str or "\x00" in value:
            _fail(_INPUT_INVALID)
        copied[key] = value

    if any(not copied[key] for key in ("dbname", "user", "host")):
        _fail(_INPUT_INVALID)
    if "," in copied["host"] or any(
        character.isspace() for character in copied["host"]
    ):
        _fail(_INPUT_INVALID)

    port = copied["port"]
    if (
        not port
        or len(port) > 5
        or any(character < "0" or character > "9" for character in port)
        or not 1 <= int(port) <= 65535
    ):
        _fail(_INPUT_INVALID)
    return copied


def _raise_after_connection_open_cleanup(
    primary, lease, fallback_code, *, claim_token=None, connection=None,
    connection_close=None,
):
    cleanup_errors = []
    close_attempted = False
    owned_connection = connection
    try:
        try:
            try:
                if connection is not None:
                    close = connection_close
                    if not callable(close):
                        close = connection.close
                    if not callable(close):
                        raise TypeError
                    (close_attempted := True) and close()
                    connection = None
            except BaseException as exc:
                cleanup_errors.append(exc)
                if connection is not None and not close_attempted:
                    try:
                        retry_close = connection.close
                        if not callable(retry_close):
                            raise TypeError
                        (close_attempted := True) and retry_close()
                    except BaseException as retry_error:
                        cleanup_errors.append(retry_error)
        finally:
            try:
                _clear_connection_open_claim(
                    lease, claim_token, owned_connection,
                )
            except BaseException as clear_error:
                cleanup_errors.append(clear_error)
                try:
                    _clear_connection_open_claim(
                        lease, claim_token, owned_connection,
                    )
                except BaseException as retry_error:
                    cleanup_errors.append(retry_error)
            lease.release()
    except BaseException as release_error:
        cleanup_errors.append(release_error)
        try:
            lease.release()
        except BaseException as retry_error:
            cleanup_errors.append(retry_error)

    errors = (primary, *cleanup_errors)
    for error in errors:
        if isinstance(error, _CONTROL_FLOW):
            raise error
    for error in errors:
        if isinstance(error, MemoryError):
            raise error
    if isinstance(primary, _WarehouseAnomalyRuntimeError):
        _raise_fixed_error(primary)
    _fail(fallback_code)


class _LeaseState:
    __slots__ = (
        "budget", "claim_token", "clock", "connection", "connection_close",
        "released", "semaphore", "transaction_token",
    )

    def __init__(
        self, budget, clock, semaphore, *, claim_token=None, connection=None,
        connection_close=None, released=False, transaction_token=None,
    ):
        self.budget = budget
        self.claim_token = claim_token
        self.clock = clock
        self.connection = connection
        self.connection_close = connection_close
        self.semaphore = semaphore
        self.released = released
        self.transaction_token = transaction_token


def _registered_lease_state(lease, *, active):
    if type(lease) is not _WarehouseAnomalyRuntimeLease:
        _fail(_INPUT_INVALID)
    try:
        state = _LEASE_STATES.get(lease)
    except (AttributeError, TypeError):
        _fail(_INPUT_INVALID)
    if type(state) is not _LeaseState:
        _fail(_INPUT_INVALID)
    if type(state.released) is not bool:
        _fail(_INPUT_INVALID)
    if state.released:
        if (
            active
            or state.budget is not None
            or state.claim_token is not None
            or state.clock is not None
            or state.connection is not None
            or state.connection_close is not None
            or state.semaphore is not None
            or state.transaction_token is not None
        ):
            _fail(_INPUT_INVALID)
        return state
    _validate_budget(state.budget)
    if (
        not callable(state.clock)
        or state.semaphore is None
    ):
        _fail(_INPUT_INVALID)
    return state


def _claim_active_lease(lease, claim_token):
    if type(claim_token) is not object:
        _fail(_INPUT_INVALID)
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if state.claim_token is not None:
            _fail(_INPUT_INVALID)
        state.claim_token = claim_token
    return True


def _lease_has_or_recovers_claim(lease, claim_token):
    try:
        with _LEASE_STATE_LOCK:
            state = _registered_lease_state(lease, active=True)
            if state.claim_token is None:
                state.claim_token = claim_token
    except BaseException:
        return False
    return state.claim_token is claim_token


def _bind_connection_to_claim(
    lease, claim_token, connection, connection_close,
):
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if (
            state.claim_token is not claim_token
            or state.connection is not None
            or state.connection_close is not None
            or state.transaction_token is not None
            or not callable(connection_close)
        ):
            _fail(_INPUT_INVALID)
        state.connection = connection
        state.connection_close = connection_close


def _bound_connection_close(lease, connection):
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if (
            connection is None
            or state.claim_token is None
            or state.connection is not connection
            or not callable(state.connection_close)
        ):
            _fail(_INPUT_INVALID)
        return state.connection_close


def _clear_connection_open_claim(lease, claim_token, connection):
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if (
            state.claim_token is not claim_token
            or state.transaction_token is not None
            or state.connection not in (None, connection)
        ):
            _fail(_INPUT_INVALID)
        _LEASE_STATES[lease] = _LeaseState(
            state.budget, state.clock, state.semaphore,
        )


def _claim_transaction_pair(lease, connection, transaction_token):
    if type(transaction_token) is not object:
        _fail(_INPUT_INVALID)
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if (
            connection is None
            or state.claim_token is None
            or state.connection is None
            or state.connection is not connection
            or state.transaction_token is not None
        ):
            _fail(_INPUT_INVALID)
        state.transaction_token = transaction_token
    return True


def _lease_has_or_recovers_transaction_claim(
    lease, connection, transaction_token,
):
    try:
        with _LEASE_STATE_LOCK:
            state = _registered_lease_state(lease, active=True)
            if (
                connection is None
                or state.claim_token is None
                or state.connection is None
                or state.connection is not connection
            ):
                return False
            if state.transaction_token is None:
                state.transaction_token = transaction_token
    except BaseException:
        return False
    return state.transaction_token is transaction_token


def _complete_transaction_claim(lease, connection, transaction_token):
    with _LEASE_STATE_LOCK:
        state = _registered_lease_state(lease, active=True)
        if state.transaction_token is _TRANSACTION_COMPLETE:
            if state.connection is not None:
                _fail(_INPUT_INVALID)
        elif (
            state.connection is connection
            and state.transaction_token is transaction_token
        ):
            state.connection = None
            state.transaction_token = _TRANSACTION_COMPLETE
        elif (
            state.connection is None
            and state.transaction_token is transaction_token
        ):
            state.transaction_token = _TRANSACTION_COMPLETE
        else:
            _fail(_INPUT_INVALID)
        state.connection_close = None
        state.claim_token = None


def _connect_immediately_after_guard(
    lease, connect, connection_config, connect_attempted,
):
    return (
        lease.guard(),
        connect_attempted.append(True),
        connect(**connection_config),
    )[2]


class _GuardedCursorState:
    __slots__ = (
        "active", "begin_attempted", "first_error", "lease", "ledger",
        "raw_close", "raw_cursor", "raw_execute", "raw_fetchall",
        "statement_attempts",
    )

    def __init__(
        self, raw_cursor, lease, raw_execute, raw_fetchall, raw_close, ledger,
        *, active=True, begin_attempted=False, first_error=None,
        statement_attempts=0,
    ):
        self.active = active
        self.begin_attempted = begin_attempted
        self.first_error = first_error
        self.lease = lease
        self.ledger = ledger
        self.raw_close = raw_close
        self.raw_cursor = raw_cursor
        self.raw_execute = raw_execute
        self.raw_fetchall = raw_fetchall
        self.statement_attempts = statement_attempts


def _registered_cursor_state(guarded_cursor, *, active):
    if type(guarded_cursor) is not _WarehouseAnomalyGuardedCursor:
        _fail(_INPUT_INVALID)
    try:
        state = _CURSOR_STATES.get(guarded_cursor)
    except (AttributeError, TypeError):
        _fail(_INPUT_INVALID)
    if type(state) is not _GuardedCursorState:
        _fail(_INPUT_INVALID)
    if type(state.active) is not bool or state.active is not active:
        _fail(_INPUT_INVALID)
    if not active:
        return state
    if (
        not callable(state.raw_execute)
        or not callable(state.raw_fetchall)
        or not callable(state.raw_close)
        or type(state.statement_attempts) is not int
        or state.statement_attempts < 0
        or type(state.begin_attempted) is not bool
        or type(state.ledger) is not _TransactionLedger
    ):
        _fail(_INPUT_INVALID)
    return state


class _TransactionLedger:
    __slots__ = ("begin_attempted",)

    def __init__(self):
        self.begin_attempted = False


def _new_guarded_cursor(raw_cursor, lease, ledger):
    try:
        raw_execute = raw_cursor.execute
        raw_fetchall = raw_cursor.fetchall
        raw_close = raw_cursor.close
    except BaseException:
        raise
    if not all(callable(value) for value in (
        raw_execute, raw_fetchall, raw_close,
    )):
        _fail(_READ_FAILED)
    guarded_cursor = _WarehouseAnomalyGuardedCursor()
    with _CURSOR_STATE_LOCK:
        _CURSOR_STATES[guarded_cursor] = _GuardedCursorState(
            raw_cursor, lease, raw_execute, raw_fetchall, raw_close, ledger,
        )
    return guarded_cursor


def _chosen_driver_error(driver_error, post_guard_error):
    if isinstance(driver_error, _CONTROL_FLOW):
        return driver_error
    if isinstance(post_guard_error, _CONTROL_FLOW):
        return post_guard_error
    if isinstance(driver_error, MemoryError):
        return driver_error
    if isinstance(post_guard_error, MemoryError):
        return post_guard_error
    if post_guard_error is not None:
        return post_guard_error
    if driver_error is not None:
        return _WarehouseAnomalyRuntimeError(_READ_FAILED)
    return None


def _latch_cursor_error(state, error):
    if state.first_error is None:
        state.first_error = error


def _raise_guarded_error(error):
    if isinstance(error, _WarehouseAnomalyRuntimeError):
        _raise_fixed_error(error)
    raise error


def _guarded_execute(guarded_cursor, sql, params, *, begin=False):
    with _CURSOR_STATE_LOCK:
        state = _registered_cursor_state(guarded_cursor, active=True)
        if state.first_error is not None:
            return None, state.first_error
        try:
            if state.statement_attempts >= _MAX_SERVER_STATEMENTS:
                _fail(_CONTRACT_INVALID)
            state.lease.guard()
            state.statement_attempts += 1
            if begin:
                state.begin_attempted = True; state.ledger.begin_attempted = True
            driver_error = None
            try:
                state.raw_execute(sql, params)
            except BaseException as exc:
                driver_error = exc
            post_guard_error = None
            try:
                state.lease.guard()
            except BaseException as exc:
                post_guard_error = exc
            chosen = _chosen_driver_error(driver_error, post_guard_error)
            if chosen is not None:
                _latch_cursor_error(state, chosen)
                return None, chosen
            return None, None
        except BaseException as exc:
            chosen = (
                _WarehouseAnomalyRuntimeError(exc.code)
                if isinstance(exc, _WarehouseAnomalyRuntimeError)
                else exc
            )
            _latch_cursor_error(state, chosen)
            return None, chosen


def _guarded_fetchall(guarded_cursor):
    with _CURSOR_STATE_LOCK:
        state = _registered_cursor_state(guarded_cursor, active=True)
        if state.first_error is not None:
            return None, state.first_error
        try:
            state.lease.guard()
            result = None
            driver_error = None
            try:
                result = state.raw_fetchall()
            except BaseException as exc:
                driver_error = exc
            post_guard_error = None
            try:
                state.lease.guard()
            except BaseException as exc:
                post_guard_error = exc
            chosen = _chosen_driver_error(driver_error, post_guard_error)
            if chosen is not None:
                _latch_cursor_error(state, chosen)
                return None, chosen
            return _validated_closed_fetch_result(result), None
        except BaseException as exc:
            chosen = (
                _WarehouseAnomalyRuntimeError(exc.code)
                if isinstance(exc, _WarehouseAnomalyRuntimeError)
                else exc
            )
            _latch_cursor_error(state, chosen)
            return None, chosen


def _validated_closed_fetch_result(result):
    if (
        type(result) is not list
        or len(result) > _MAX_FETCH_RESULT_ROWS
    ):
        _fail(_READ_FAILED)
    seen = {id(result)}
    ledger = [1, 0]

    def detached(current, depth):
        ledger[0] += 1
        if (
            ledger[0] > _MAX_FETCH_RESULT_NODES
            or depth > _MAX_FETCH_RESULT_DEPTH
        ):
            _fail(_READ_FAILED)
        current_type = type(current)
        if current_type is str:
            try:
                ledger[1] += len(current.encode("utf-8"))
            except UnicodeError:
                _fail(_READ_FAILED)
            if ledger[1] > _MAX_FETCH_RESULT_TEXT_BYTES:
                _fail(_READ_FAILED)
            return current
        if current_type in (type(None), bool, int):
            return current
        if current_type is list:
            identity = id(current)
            if identity in seen:
                _fail(_READ_FAILED)
            seen.add(identity)
            return [detached(value, depth + 1) for value in current]
        if current_type in (dict, psycopg2.extras.RealDictRow):
            if current_type is psycopg2.extras.RealDictRow and vars(current):
                _fail(_READ_FAILED)
            identity = id(current)
            if identity in seen:
                _fail(_READ_FAILED)
            seen.add(identity)
            copied = {}
            for key, value in dict.items(current):
                if type(key) is not str:
                    _fail(_READ_FAILED)
                copied[key] = detached(value, depth + 1)
            return copied
        _fail(_READ_FAILED)

    return [detached(row, 1) for row in result]


def _forbid_guarded_cursor_close(guarded_cursor):
    state = None
    try:
        with _CURSOR_STATE_LOCK:
            state = _registered_cursor_state(guarded_cursor, active=True)
            if state.first_error is not None:
                return state.first_error
            error = _WarehouseAnomalyRuntimeError(_CONTRACT_INVALID)
            _latch_cursor_error(state, error)
            return error
    except BaseException as error:
        if state is not None:
            try:
                _latch_cursor_error(state, error)
            except BaseException:
                pass
        error.__traceback__ = None
        return error


def _terminalize_guarded_cursor(guarded_cursor):
    with _CURSOR_STATE_LOCK:
        if type(guarded_cursor) is not _WarehouseAnomalyGuardedCursor:
            _fail(_INPUT_INVALID)
        state = _CURSOR_STATES.get(guarded_cursor)
        if type(state) is not _GuardedCursorState:
            _fail(_INPUT_INVALID)
        snapshot = (
            state.begin_attempted,
            state.first_error,
            state.raw_close,
            state.statement_attempts,
        )
        if state.active:
            _CURSOR_STATES[guarded_cursor] = _GuardedCursorState(
                None, None, None, None, state.raw_close, None,
                active=False,
                begin_attempted=state.begin_attempted,
                first_error=state.first_error,
                statement_attempts=state.statement_attempts,
            )
    return snapshot


class _WarehouseAnomalyGuardedCursor:
    __slots__ = ("__weakref__",)

    def execute(self, sql, params=()):
        value, error = _guarded_execute(self, sql, params)
        if error is not None:
            _raise_guarded_error(error)
        return value

    def fetchall(self):
        value, error = _guarded_fetchall(self)
        if error is not None:
            _raise_guarded_error(error)
        return value

    def close(self):
        _raise_guarded_error(_forbid_guarded_cursor_close(self))


class _WarehouseAnomalyRuntimeLease:
    __slots__ = ("__weakref__",)

    def __init__(self, *ignored):
        # Construction alone never grants ownership; only acquisition registers it.
        pass

    @property
    def _token(self):
        # Kept as a non-authoritative compatibility marker for hostile-shape tests.
        return _LEASE_TOKEN

    @property
    def budget(self):
        with _LEASE_STATE_LOCK:
            return _registered_lease_state(self, active=True).budget

    def guard(self):
        with _LEASE_STATE_LOCK:
            state = _registered_lease_state(self, active=True)
            try:
                now = state.clock()
            except _CONTROL_FLOW:
                raise
            except MemoryError:
                raise
            except BaseException:
                _fail(_INPUT_INVALID)
            now = _finite_number(now)
            if state.released:
                _fail(_INPUT_INVALID)
            if now >= state.budget.deadline_monotonic:
                _fail(_DEADLINE_EXCEEDED)
        return None

    def release(self):
        with _LEASE_STATE_LOCK:
            state = _registered_lease_state(self, active=False)
            if state.released:
                return None
            if (
                state.connection is not None
                or state.connection_close is not None
                or state.transaction_token not in (
                    None, _TRANSACTION_COMPLETE,
                )
            ):
                _fail(_INPUT_INVALID)
            semaphore = state.semaphore
            terminal_state = _LeaseState(
                None, None, None, claim_token=None, released=True,
            )
            _LEASE_STATES[self] = terminal_state
            semaphore.release()
        return None

    def __enter__(self):
        with _LEASE_STATE_LOCK:
            _registered_lease_state(self, active=True)
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False


def _raise_after_acquisition_cleanup(primary, lease):
    cleanup = None
    try:
        if lease is not None:
            with _LEASE_STATE_LOCK:
                state = _LEASE_STATES.get(lease)
                if type(state) is _LeaseState:
                    terminal_state = _LeaseState(
                        None, None, None, claim_token=None, released=True,
                    )
                    _LEASE_STATES[lease] = terminal_state
        _RUNTIME_SLOT.release()
    except BaseException as exc:
        cleanup = exc

    if isinstance(primary, _CONTROL_FLOW):
        raise primary
    if isinstance(cleanup, _CONTROL_FLOW):
        raise cleanup
    if isinstance(primary, MemoryError):
        raise primary
    if isinstance(cleanup, MemoryError):
        raise cleanup
    _fail(_INPUT_INVALID)


def acquire_warehouse_anomaly_runtime_slot(
    clock=time.monotonic, *, wait_seconds=1.0,
):
    """Acquire the sole private runtime slot and start its operation budget."""

    if not callable(clock):
        _fail(_INPUT_INVALID)
    wait = _finite_number(wait_seconds)
    if wait < 0.0 or wait > 1.0:
        _fail(_INPUT_INVALID)

    acquired = None
    lease = None
    try:
        acquired = _RUNTIME_SLOT.acquire(timeout=wait)
        if acquired is False:
            _fail(_BUSY)
        if acquired is not True:
            _fail(_INPUT_INVALID)
        started = _finite_number(clock())
        deadline = started + _OPERATION_SECONDS
        deadline_resolution = max(
            math.ulp(started),
            math.ulp(deadline),
        )
        if (
            not math.isfinite(deadline)
            or deadline <= started
            or deadline_resolution > _MAX_MONOTONIC_RESOLUTION_SECONDS
            or abs(
                (deadline - started) - _OPERATION_SECONDS
            ) > deadline_resolution
        ):
            _fail(_INPUT_INVALID)
        budget = WarehouseAnomalyRuntimeBudget(
            deadline_monotonic=deadline,
            statement_timeout_ms=_STATEMENT_TIMEOUT_MS,
        )
        lease = _WarehouseAnomalyRuntimeLease()
        with _LEASE_STATE_LOCK:
            _LEASE_STATES[lease] = _LeaseState(
                budget, clock, _RUNTIME_SLOT, claim_token=None,
            )
        return lease
    except BaseException as exc:
        if acquired is True:
            _raise_after_acquisition_cleanup(exc, lease)
        if isinstance(exc, _CONTROL_FLOW) or isinstance(exc, MemoryError):
            raise
        if (
            isinstance(exc, _WarehouseAnomalyRuntimeError)
            and exc.code in {_INPUT_INVALID, _BUSY}
        ):
            raise
        _fail(_INPUT_INVALID)


def open_warehouse_anomaly_read_connection(
    db_config, lease, *, connect=psycopg2.connect,
):
    """Open the private A9 read connection under the lease deadline."""

    claim_token = object()
    lease_owned = False
    connection = None
    close = None
    fallback_code = _INPUT_INVALID
    try:
        lease_owned = _claim_active_lease(lease, claim_token)
        if not callable(connect):
            _fail(_INPUT_INVALID)
        connection_config = _validated_db_config(db_config)
        connection_config["connect_timeout"] = _CONNECT_TIMEOUT_SECONDS
        connection_config["options"] = _STARTUP_OPTIONS
        fallback_code = _READ_FAILED
        connect_error = None
        connect_attempted = []
        try:
            connection = _connect_immediately_after_guard(
                lease, connect, connection_config, connect_attempted,
            )
        except BaseException as exc:
            if not connect_attempted:
                raise
            connect_error = exc

        post_guard_error = None
        try:
            lease.guard()
        except BaseException as exc:
            post_guard_error = exc

        if connect_error is not None:
            if isinstance(connect_error, _CONTROL_FLOW):
                primary = connect_error
            elif isinstance(post_guard_error, _CONTROL_FLOW):
                primary = post_guard_error
            elif isinstance(connect_error, MemoryError):
                primary = connect_error
            elif isinstance(post_guard_error, MemoryError):
                primary = post_guard_error
            elif post_guard_error is not None:
                primary = post_guard_error
            else:
                primary = connect_error
            raise primary
        if post_guard_error is not None:
            raise post_guard_error

        if connection is None or not bool(connection):
            _fail(_READ_FAILED)
        close = connection.close
        if not callable(close):
            _fail(_READ_FAILED)
        connection.autocommit = True
        if connection.autocommit is not True:
            _fail(_READ_FAILED)
        _bind_connection_to_claim(
            lease, claim_token, connection, close,
        )
        return connection
    except BaseException as exc:
        if not lease_owned:
            lease_owned = _lease_has_or_recovers_claim(lease, claim_token)
        if not lease_owned:
            if isinstance(exc, _CONTROL_FLOW) or isinstance(exc, MemoryError):
                raise
            if isinstance(exc, _WarehouseAnomalyRuntimeError):
                _raise_fixed_error(exc)
            _fail(_INPUT_INVALID)
        _raise_after_connection_open_cleanup(
            exc,
            lease,
            fallback_code,
            claim_token=claim_token,
            connection=connection,
            connection_close=close,
        )


def _validated_settings_rows(rows):
    if type(rows) is not list or len(rows) != 1:
        _fail(_READ_FAILED)
    row = rows[0]
    if (
        not isinstance(row, dict)
        or set(row) != set(_EXPECTED_SETTINGS_ROW)
        or any(type(value) is not str for value in row.values())
        or dict(row) != _EXPECTED_SETTINGS_ROW
    ):
        _fail(_READ_FAILED)
    return dict(row)


def _first_control_or_memory(errors):
    for error in errors:
        if isinstance(error, _CONTROL_FLOW):
            return error
    for error in errors:
        if isinstance(error, MemoryError):
            return error
    return None


def _raise_transaction_outcome(
    primary_error,
    rollback_error,
    cleanup_errors,
    post_cleanup_error,
    release_error,
):
    ordered = (
        primary_error,
        rollback_error,
        *cleanup_errors,
        post_cleanup_error,
        release_error,
    )
    identity_error = _first_control_or_memory(ordered)
    if identity_error is not None:
        raise identity_error
    if rollback_error is not None:
        _fail(_ROLLBACK_FAILED)
    if primary_error is not None:
        if (
            isinstance(primary_error, _WarehouseAnomalyRuntimeError)
            and primary_error.code in {
                _INPUT_INVALID,
                _DEADLINE_EXCEEDED,
                _READ_FAILED,
                _CONTRACT_INVALID,
            }
        ):
            _raise_fixed_error(primary_error)
        _fail(_READ_FAILED)
    if cleanup_errors or release_error is not None:
        _fail(_CLEANUP_FAILED)
    if post_cleanup_error is not None:
        if (
            isinstance(post_cleanup_error, _WarehouseAnomalyRuntimeError)
            and post_cleanup_error.code == _DEADLINE_EXCEEDED
        ):
            _raise_fixed_error(post_cleanup_error)
        _fail(_CLEANUP_FAILED)


class _TransactionRunOutcome(NamedTuple):
    result: object
    error: object


class _TransactionLifecycle:
    __slots__ = (
        "claim_completed", "cleanup_errors", "cleanup_finished",
        "connection", "connection_close", "connection_close_attempted",
        "cursor_close_attempted", "error_events",
        "guarded_cursor", "ledger", "lease", "pair_owned",
        "post_cleanup_error", "post_guard_attempted", "primary_error",
        "raw_cursor", "raw_cursor_close", "raw_cursor_execute", "read",
        "release_attempted",
        "release_error", "result", "rollback_attempted", "rollback_error",
        "terminal_snapshot", "transaction_token",
    )

    def __init__(self, connection, lease, read):
        self.claim_completed = False
        self.cleanup_errors = []
        self.cleanup_finished = False
        self.connection = connection
        self.connection_close = None
        self.connection_close_attempted = False
        self.cursor_close_attempted = False
        self.error_events = []
        self.guarded_cursor = None
        self.ledger = _TransactionLedger()
        self.lease = lease
        self.pair_owned = False
        self.post_cleanup_error = None
        self.post_guard_attempted = False
        self.primary_error = None
        self.raw_cursor = None
        self.raw_cursor_close = None
        self.raw_cursor_execute = None
        self.read = read
        self.release_attempted = False
        self.release_error = None
        self.result = None
        self.rollback_attempted = False
        self.rollback_error = None
        self.terminal_snapshot = None
        self.transaction_token = object()


def _record_transaction_error(lifecycle, error, category):
    lifecycle.error_events.append(error)
    if category == "primary" and lifecycle.primary_error is None:
        lifecycle.primary_error = error
    elif category == "rollback" and lifecycle.rollback_error is None:
        lifecycle.rollback_error = error
    elif category == "post_cleanup" and lifecycle.post_cleanup_error is None:
        lifecycle.post_cleanup_error = error
    elif category == "release" and lifecycle.release_error is None:
        lifecycle.release_error = error
    elif category == "cleanup":
        lifecycle.cleanup_errors.append(error)


def _start_transaction_lifecycle(lifecycle):
    connection = lifecycle.connection
    lease = lifecycle.lease
    lifecycle.connection_close = _bound_connection_close(lease, connection)
    lifecycle.pair_owned = _claim_transaction_pair(
        lease, connection, lifecycle.transaction_token,
    )
    lifecycle.connection_close = lifecycle.connection_close
    if not callable(lifecycle.connection_close):
        _fail(_READ_FAILED)
    if not bool(connection):
        _fail(_READ_FAILED)
    if not callable(lifecycle.read):
        _fail(_INPUT_INVALID)
    if connection.autocommit is not True:
        _fail(_READ_FAILED)
    cursor_factory = connection.cursor
    if not callable(cursor_factory):
        _fail(_READ_FAILED)
    lifecycle.raw_cursor = cursor_factory(
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    if lifecycle.raw_cursor is None:
        _fail(_READ_FAILED)
    lifecycle.raw_cursor_close = lifecycle.raw_cursor.close
    lifecycle.raw_cursor_execute = lifecycle.raw_cursor.execute
    if not all(callable(value) for value in (
        lifecycle.raw_cursor_close, lifecycle.raw_cursor_execute,
    )):
        _fail(_READ_FAILED)
    if not bool(lifecycle.raw_cursor):
        _fail(_READ_FAILED)
    lifecycle.guarded_cursor = _new_guarded_cursor(
        lifecycle.raw_cursor, lease, lifecycle.ledger,
    )
    _begin_value, begin_error = _guarded_execute(
        lifecycle.guarded_cursor, _BEGIN_SQL, (), begin=True,
    )
    if begin_error is not None:
        _raise_guarded_error(begin_error)
    lifecycle.guarded_cursor.execute(_SETTINGS_SQL, _SETTINGS_PARAMS)
    _validated_settings_rows(lifecycle.guarded_cursor.fetchall())
    lifecycle.result = lifecycle.read(lifecycle.guarded_cursor)
    with _CURSOR_STATE_LOCK:
        cursor_state = _registered_cursor_state(
            lifecycle.guarded_cursor, active=True,
        )
        if cursor_state.first_error is not None:
            raise cursor_state.first_error


def _finish_transaction_lifecycle(lifecycle):
    if not lifecycle.pair_owned:
        lifecycle.pair_owned = _lease_has_or_recovers_transaction_claim(
            lifecycle.lease,
            lifecycle.connection,
            lifecycle.transaction_token,
        )
    if lifecycle.connection_close is None and lifecycle.pair_owned:
        lifecycle.connection_close = _bound_connection_close(
            lifecycle.lease, lifecycle.connection,
        )
    if not lifecycle.pair_owned:
        lifecycle.cleanup_finished = True
        return None

    if (
        lifecycle.guarded_cursor is not None
        and lifecycle.terminal_snapshot is None
    ):
        lifecycle.terminal_snapshot = _terminalize_guarded_cursor(
            lifecycle.guarded_cursor,
        )
        latched_error = lifecycle.terminal_snapshot[1]
        if lifecycle.raw_cursor_close is None:
            lifecycle.raw_cursor_close = lifecycle.terminal_snapshot[2]
        if lifecycle.primary_error is None and latched_error is not None:
            _record_transaction_error(lifecycle, latched_error, "primary")

    if lifecycle.ledger.begin_attempted and not lifecycle.rollback_attempted:
        try:
            lifecycle.rollback_attempted = True; lifecycle.raw_cursor_execute(
                _ROLLBACK_SQL, (),
            )
        except BaseException as error:
            if not lifecycle.rollback_attempted:
                raise
            _record_transaction_error(lifecycle, error, "rollback")

    if lifecycle.raw_cursor is not None and not lifecycle.cursor_close_attempted:
        if not callable(lifecycle.raw_cursor_close):
            try:
                lifecycle.raw_cursor_close = lifecycle.raw_cursor.close
            except BaseException as error:
                lifecycle.cursor_close_attempted = True
                _record_transaction_error(lifecycle, error, "cleanup")
        if (
            not lifecycle.cursor_close_attempted
            and not callable(lifecycle.raw_cursor_close)
        ):
            lifecycle.cursor_close_attempted = True
            _record_transaction_error(lifecycle, TypeError(), "cleanup")
        if not lifecycle.cursor_close_attempted:
            try:
                lifecycle.cursor_close_attempted = True; lifecycle.raw_cursor_close()
            except BaseException as error:
                if not lifecycle.cursor_close_attempted:
                    raise
                _record_transaction_error(lifecycle, error, "cleanup")

    if not lifecycle.connection_close_attempted:
        if not callable(lifecycle.connection_close):
            lifecycle.connection_close_attempted = True
            _record_transaction_error(lifecycle, TypeError(), "cleanup")
        else:
            try:
                lifecycle.connection_close_attempted = True; lifecycle.connection_close()
            except BaseException as error:
                if not lifecycle.connection_close_attempted:
                    raise
                _record_transaction_error(lifecycle, error, "cleanup")

    if not lifecycle.claim_completed:
        _complete_transaction_claim(
            lifecycle.lease,
            lifecycle.connection,
            lifecycle.transaction_token,
        )
        lifecycle.claim_completed = True

    if not lifecycle.post_guard_attempted:
        try:
            lifecycle.post_guard_attempted = True; lifecycle.lease.guard()
        except BaseException as error:
            lifecycle.post_guard_attempted = True
            _record_transaction_error(lifecycle, error, "post_cleanup")
    lifecycle.cleanup_finished = True
    return None


def _transaction_outcome_error(lifecycle):
    identity_error = _first_control_or_memory(lifecycle.error_events)
    if identity_error is not None:
        return identity_error
    if lifecycle.rollback_error is not None:
        return _WarehouseAnomalyRuntimeError(_ROLLBACK_FAILED)
    if lifecycle.primary_error is not None:
        if (
            isinstance(
                lifecycle.primary_error, _WarehouseAnomalyRuntimeError,
            )
            and lifecycle.primary_error.code in {
                _INPUT_INVALID,
                _DEADLINE_EXCEEDED,
                _READ_FAILED,
                _CONTRACT_INVALID,
            }
        ):
            return lifecycle.primary_error
        return _WarehouseAnomalyRuntimeError(_READ_FAILED)
    if lifecycle.cleanup_errors or lifecycle.release_error is not None:
        return _WarehouseAnomalyRuntimeError(_CLEANUP_FAILED)
    if lifecycle.post_cleanup_error is not None:
        if (
            isinstance(
                lifecycle.post_cleanup_error,
                _WarehouseAnomalyRuntimeError,
            )
            and lifecycle.post_cleanup_error.code == _DEADLINE_EXCEEDED
        ):
            return lifecycle.post_cleanup_error
        return _WarehouseAnomalyRuntimeError(_CLEANUP_FAILED)
    return None


def _finalize_transaction_lifecycle(lifecycle):
    outcome_error = _transaction_outcome_error(lifecycle)
    if (
        outcome_error is not None
        and lifecycle.pair_owned
        and not lifecycle.release_attempted
    ):
        release_errors = []
        try:
            lifecycle.lease.release()
        except BaseException as error:
            release_errors.append(error)
            try:
                lifecycle.lease.release()
            except BaseException as retry_error:
                release_errors.append(retry_error)
        lifecycle.release_attempted = True
        for release_error in release_errors:
            _record_transaction_error(lifecycle, release_error, "release")
        outcome_error = _transaction_outcome_error(lifecycle)
    return _TransactionRunOutcome(
        None if outcome_error is not None else lifecycle.result,
        outcome_error,
    )


def _run_warehouse_anomaly_read_transaction(connection, lease, read):
    lifecycle = _TransactionLifecycle(connection, lease, read)
    try:
        _start_transaction_lifecycle(lifecycle)
    except BaseException as error:
        _record_transaction_error(lifecycle, error, "primary")

    for _attempt in range(16):
        if lifecycle.cleanup_finished:
            break
        try:
            _finish_transaction_lifecycle(lifecycle)
        except BaseException as error:
            _record_transaction_error(lifecycle, error, "cleanup")
    if not lifecycle.cleanup_finished:
        _record_transaction_error(
            lifecycle,
            _WarehouseAnomalyRuntimeError(_CLEANUP_FAILED),
            "cleanup",
        )

    try:
        outcome = _finalize_transaction_lifecycle(lifecycle)
    except BaseException as error:
        _record_transaction_error(lifecycle, error, "cleanup")
        for _attempt in range(16):
            if lifecycle.cleanup_finished:
                break
            try:
                _finish_transaction_lifecycle(lifecycle)
            except BaseException as retry_error:
                _record_transaction_error(
                    lifecycle, retry_error, "cleanup",
                )
        outcome = _finalize_transaction_lifecycle(lifecycle)

    try:
        return outcome
    except BaseException as error:
        _record_transaction_error(lifecycle, error, "primary")
        outcome = _finalize_transaction_lifecycle(lifecycle)
        return outcome


def run_warehouse_anomaly_read_transaction(connection, lease, read):
    """Run one guarded private callback and clean its read transaction."""

    outcome = _run_warehouse_anomaly_read_transaction(
        connection, lease, read,
    )
    connection = None
    lease = None
    read = None
    error = outcome.error
    result = outcome.result
    outcome = None
    if error is not None:
        _raise_guarded_error(error)
    return result


__all__ = []
