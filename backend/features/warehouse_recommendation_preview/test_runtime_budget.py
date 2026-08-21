import ast
import gc
import hashlib
import inspect
import math
import sys
import time
import unittest
import weakref
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import psycopg2
import psycopg2.extras

import backend.features.warehouse_recommendation_preview.runtime_budget as runtime_budget
from backend.features import warehouse_recommendation_preview as preview_package


INPUT_INVALID = "warehouse_anomaly_runtime_input_invalid"
BUSY = "warehouse_anomaly_runtime_busy"
DEADLINE_EXCEEDED = "warehouse_anomaly_runtime_deadline_exceeded"
READ_FAILED = "warehouse_anomaly_runtime_read_failed"
CONTRACT_INVALID = "warehouse_anomaly_runtime_contract_invalid"
ROLLBACK_FAILED = "warehouse_anomaly_runtime_rollback_failed"
CLEANUP_FAILED = "warehouse_anomaly_runtime_cleanup_failed"


class _RecordingSemaphore:
    def __init__(self, events, *, acquired=True):
        self.events = events
        self.acquired = acquired
        self.acquire_calls = []
        self.releases = 0

    def acquire(self, blocking=True, timeout=None):
        self.events.append("semaphore_acquire")
        self.acquire_calls.append((blocking, timeout))
        return self.acquired

    def release(self):
        self.events.append("semaphore_release")
        self.releases += 1


class _AcquireFailureSemaphore(_RecordingSemaphore):
    def __init__(self, events, failure):
        super().__init__(events)
        self.failure = failure

    def acquire(self, blocking=True, timeout=None):
        self.events.append("semaphore_acquire")
        self.acquire_calls.append((blocking, timeout))
        raise self.failure


class _CapacityOneSemaphore(_RecordingSemaphore):
    def __init__(self, events):
        super().__init__(events)
        self.available = True

    def acquire(self, blocking=True, timeout=None):
        self.events.append("semaphore_acquire")
        self.acquire_calls.append((blocking, timeout))
        if not self.available:
            return False
        self.available = False
        return True

    def release(self):
        self.events.append("semaphore_release")
        self.releases += 1
        self.available = True


class _ReleaseSideEffectThenFailureSemaphore(_CapacityOneSemaphore):
    def __init__(self, events, failure):
        super().__init__(events)
        self.failure = failure

    def release(self):
        super().release()
        if self.failure is not None:
            failure = self.failure
            self.failure = None
            raise failure


class _ReleaseFailureSemaphore(_RecordingSemaphore):
    def __init__(self, events, failure):
        super().__init__(events)
        self.failure = failure

    def release(self):
        self.events.append("semaphore_release")
        self.releases += 1
        raise self.failure


class _ScriptedClock:
    def __init__(self, events, *values):
        self.events = events
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        self.events.append("clock")
        self.calls += 1
        if not self.values:
            raise AssertionError("clock was called more often than expected")
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def _fixed_error(test_case, expected_code, callback):
    with test_case.assertRaises(ValueError) as raised:
        callback()
    error = raised.exception
    test_case.assertEqual(getattr(error, "code", None), expected_code)
    test_case.assertEqual(str(error), expected_code)
    test_case.assertEqual(error.args, (expected_code,))
    test_case.assertIsNone(error.__cause__)
    test_case.assertIsNone(error.__context__)
    test_case.assertNotIn(
        "PRIVATE", repr(error) + repr(vars(error)),
    )
    return error


def _bounded_semaphore_binding():
    source = Path(runtime_budget.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    matches = []
    for node in tree.body:
        value = None
        targets = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "threading"
            and value.func.attr == "BoundedSemaphore"
        ):
            continue
        matches.append((targets, value))
    if len(matches) != 1:
        raise AssertionError("expected one module-global BoundedSemaphore")
    targets, call = matches[0]
    if (
        len(targets) != 1
        or not isinstance(targets[0], ast.Name)
        or len(call.args) != 1
        or not isinstance(call.args[0], ast.Constant)
        or call.args[0].value != 1
        or call.keywords
    ):
        raise AssertionError("runtime capacity must be exact BoundedSemaphore(1)")
    return targets[0].id


class WarehouseAnomalyRuntimeBudgetContractTests(unittest.TestCase):
    def _acquire_with_fake(self, clock, semaphore, *, default=False, wait=1.0):
        binding = _bounded_semaphore_binding()
        with mock.patch.object(runtime_budget, binding, semaphore):
            if default:
                return runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                    clock,
                )
            return runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                clock, wait_seconds=wait,
            )

    def _close_b2_only_connection_fixture(
        self, lease, connection, *, close=True,
    ):
        with runtime_budget._LEASE_STATE_LOCK:
            state = runtime_budget._registered_lease_state(
                lease, active=True,
            )
            claim_token = state.claim_token
            bound_close = state.connection_close
        if close:
            bound_close()
        runtime_budget._clear_connection_open_claim(
            lease, claim_token, connection,
        )
        lease.release()

    def _new_guarded_transaction_fixture(self):
        events = []
        settings_row = {
            "statement_timeout": "5s",
            "lock_timeout": "1s",
            "idle_in_transaction_session_timeout": "10s",
            "search_path": "pg_catalog, public",
            "client_encoding": "UTF8",
            "transaction_isolation": "repeatable read",
            "transaction_read_only": "on",
        }

        class InvokeEffect:
            __slots__ = ("callback",)

            def __init__(self, callback):
                self.callback = callback

        class SwitchableClock:
            def __init__(self):
                self.blocked = False
                self.calls = 0
                self.default = 10.0
                self.effects = []

            def script(self, *effects):
                self.effects = list(effects)

            def __call__(self):
                events.append("clock")
                self.calls += 1
                if self.blocked:
                    raise AssertionError("guard ran at a forbidden boundary")
                effect = (
                    self.effects.pop(0)
                    if self.effects else self.default
                )
                if isinstance(effect, BaseException):
                    raise effect
                return effect

        class RawCursor:
            def __init__(self):
                self.callback_execute_effects = []
                self.callback_fetch_effects = []
                self.close_after_error = None
                self.close_attempts = 0
                self.close_before_error = None
                self.close_calls = 0
                self.execute_calls = []
                self.falsey = False
                self.fetch_calls = 0
                self.connection = None
                self.rollback_execute_calls = 0
                self.settings_rows = [dict(settings_row)]

            def __bool__(self):
                return not self.falsey

            @staticmethod
            def _resolve(effect):
                if isinstance(effect, BaseException):
                    raise effect
                if type(effect) is InvokeEffect:
                    return effect.callback()
                return effect

            def execute(self, sql, params=()):
                if sql == runtime_budget._ROLLBACK_SQL:
                    self.rollback_execute_calls += 1
                    return self.connection.rollback()
                events.append("execute")
                self.execute_calls.append((sql, tuple(params or ())))
                if (
                    len(self.execute_calls) > 2
                    and self.callback_execute_effects
                ):
                    return self._resolve(
                        self.callback_execute_effects.pop(0),
                    )
                return None

            def fetchall(self):
                events.append("fetchall")
                self.fetch_calls += 1
                if self.fetch_calls == 1:
                    return self._resolve(self.settings_rows)
                if self.callback_fetch_effects:
                    return self._resolve(
                        self.callback_fetch_effects.pop(0),
                    )
                return [{"payload": "bounded"}]

            def close(self):
                self.close_attempts += 1
                if self.close_before_error is not None:
                    raise self.close_before_error
                events.append("cursor_close")
                self.close_calls += 1
                if self.close_after_error is not None:
                    raise self.close_after_error

        class Connection:
            def __init__(self, raw_cursor):
                self.autocommit = False
                self.close_after_error = None
                self.close_attempts = 0
                self.close_before_error = None
                self.close_calls = 0
                self.commit_calls = 0
                self.cursor_calls = []
                self.raw_cursor = raw_cursor
                self.rollback_after_error = None
                self.rollback_attempts = 0
                self.rollback_before_error = None
                self.rollback_calls = 0

            def __bool__(self):
                return True

            def cursor(self, **kwargs):
                events.append("cursor")
                self.cursor_calls.append(dict(kwargs))
                return self.raw_cursor

            def rollback(self):
                self.rollback_attempts += 1
                if self.rollback_before_error is not None:
                    raise self.rollback_before_error
                events.append("rollback")
                self.rollback_calls += 1
                if self.rollback_after_error is not None:
                    raise self.rollback_after_error

            def close(self):
                self.close_attempts += 1
                if self.close_before_error is not None:
                    raise self.close_before_error
                events.append("connection_close")
                self.close_calls += 1
                if self.close_after_error is not None:
                    raise self.close_after_error

            def commit(self):
                self.commit_calls += 1
                raise AssertionError("read transaction committed")

        clock = SwitchableClock()
        semaphore = _RecordingSemaphore(events)
        raw_cursor = RawCursor()
        connection = Connection(raw_cursor)
        raw_cursor.connection = connection
        lease = self._acquire_with_fake(clock, semaphore, wait=0)
        opened = runtime_budget.open_warehouse_anomaly_read_connection(
            {
                "dbname": "warehouse_preview",
                "user": "warehouse_reader",
                "password": "",
                "host": "127.0.0.1",
                "port": "5432",
            },
            lease,
            connect=lambda **ignored: connection,
        )
        return SimpleNamespace(
            clock=clock,
            connection=connection,
            events=events,
            lease=lease,
            opened=opened,
            raw_cursor=raw_cursor,
            semaphore=semaphore,
        )

    @staticmethod
    def _source_line(function, fragment, *, occurrence=0):
        source_lines, first_line = inspect.getsourcelines(function)
        matches = [
            first_line + offset
            for offset, line in enumerate(source_lines)
            if fragment in line
        ]
        if occurrence >= len(matches):
            raise AssertionError(
                "source fragment is absent: " + fragment,
            )
        return matches[occurrence]

    def test_exact_private_budget_and_acquisition_surface(self):
        budget_type = runtime_budget.WarehouseAnomalyRuntimeBudget
        self.assertTrue(issubclass(budget_type, tuple))
        self.assertEqual(
            budget_type._fields,
            ("deadline_monotonic", "statement_timeout_ms"),
        )
        example = budget_type(
            deadline_monotonic=40.25,
            statement_timeout_ms=5000,
        )
        self.assertEqual(tuple(example), (40.25, 5000))
        with self.assertRaises(AttributeError):
            example.deadline_monotonic = 99.0

        signature = inspect.signature(
            runtime_budget.acquire_warehouse_anomaly_runtime_slot
        )
        self.assertEqual(list(signature.parameters), ["clock", "wait_seconds"])
        self.assertIs(signature.parameters["clock"].default, time.monotonic)
        wait = signature.parameters["wait_seconds"]
        self.assertEqual(wait.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(wait.default, 1.0)
        self.assertEqual(runtime_budget.__all__, [])

    def test_acquisition_precedes_clock_and_builds_the_exact_budget(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.25)

        lease = self._acquire_with_fake(
            clock, semaphore, default=True,
        )
        try:
            self.assertEqual(events, ["semaphore_acquire", "clock"])
            self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
            self.assertIsInstance(
                lease.budget,
                runtime_budget.WarehouseAnomalyRuntimeBudget,
            )
            self.assertIs(lease.budget, lease.budget)
            self.assertEqual(lease.budget.deadline_monotonic, 40.25)
            self.assertIs(type(lease.budget.deadline_monotonic), float)
            self.assertEqual(lease.budget.statement_timeout_ms, 5000)
            self.assertIs(type(lease.budget.statement_timeout_ms), int)
            with self.assertRaises(AttributeError):
                lease.budget = runtime_budget.WarehouseAnomalyRuntimeBudget(
                    99.0, 5000,
                )
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_wait_is_finite_non_bool_and_never_exceeds_one_second(self):
        for wait in (0, 0.0, 0.25, 1, 1.0):
            with self.subTest(accepted=wait):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 2.0),
                    semaphore,
                    wait=wait,
                )
                lease.release()
                self.assertEqual(
                    semaphore.acquire_calls,
                    [(True, float(wait))],
                )
                self.assertEqual(semaphore.releases, 1)

        invalid = (
            True,
            False,
            -0.000001,
            1.000001,
            math.nan,
            math.inf,
            -math.inf,
            "1",
            None,
        )
        for wait in invalid:
            with self.subTest(rejected=wait):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = mock.Mock(return_value=1.0)
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: self._acquire_with_fake(
                        clock, semaphore, wait=wait,
                    ),
                )
                self.assertEqual(semaphore.acquire_calls, [])
                self.assertEqual(semaphore.releases, 0)
                clock.assert_not_called()

    def test_busy_is_clock_free_and_does_not_create_a_lease(self):
        events = []
        semaphore = _RecordingSemaphore(events, acquired=False)
        clock = mock.Mock(return_value=10.0)

        error = _fixed_error(
            self,
            BUSY,
            lambda: self._acquire_with_fake(
                clock, semaphore, default=True,
            ),
        )

        self.assertEqual(events, ["semaphore_acquire"])
        self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
        self.assertEqual(semaphore.releases, 0)
        clock.assert_not_called()
        self.assertNotIn("database", repr(error).lower())

    def test_real_capacity_is_one_and_becomes_available_after_release(self):
        first = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
            lambda: 1.0, wait_seconds=0,
        )
        try:
            _fixed_error(
                self,
                BUSY,
                lambda: runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                    mock.Mock(side_effect=AssertionError("busy called clock")),
                    wait_seconds=0,
                ),
            )
        finally:
            first.release()

        second = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
            lambda: 2.0, wait_seconds=0,
        )
        second.release()

    def test_lease_guard_uses_its_clock_and_expires_at_the_exact_boundary(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.0, 39.999999, 40.0)
        lease = self._acquire_with_fake(clock, semaphore)
        try:
            self.assertIsNone(lease.guard())
            self.assertEqual(semaphore.releases, 0)
            _fixed_error(self, DEADLINE_EXCEEDED, lease.guard)
            self.assertEqual(semaphore.releases, 0)
            self.assertEqual(clock.calls, 3)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

        for now in (40.0, 40.000001):
            with self.subTest(expired_now=now):
                local_events = []
                local_semaphore = _RecordingSemaphore(local_events)
                local_clock = _ScriptedClock(local_events, 10.0, now)
                local_lease = self._acquire_with_fake(
                    local_clock, local_semaphore,
                )
                try:
                    _fixed_error(
                        self, DEADLINE_EXCEEDED, local_lease.guard,
                    )
                    self.assertEqual(local_semaphore.releases, 0)
                finally:
                    local_lease.release()

    def test_clock_values_are_exact_finite_non_bool_numbers(self):
        for value in (0, 0.0, 10, 10.5):
            with self.subTest(accepted=value):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, value), semaphore,
                )
                self.assertIs(type(lease.budget.deadline_monotonic), float)
                self.assertEqual(
                    lease.budget.deadline_monotonic,
                    float(value) + 30.0,
                )
                lease.release()

        for value in (True, False, math.nan, math.inf, -math.inf, "10", None):
            with self.subTest(rejected_at_acquire=value):
                events = []
                semaphore = _RecordingSemaphore(events)
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: self._acquire_with_fake(
                        _ScriptedClock(events, value), semaphore,
                    ),
                )
                self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
                self.assertEqual(semaphore.releases, 1)

        for value in (True, False, math.nan, math.inf, -math.inf, "39", None):
            with self.subTest(rejected_at_guard=value):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, value), semaphore,
                )
                try:
                    _fixed_error(self, INPUT_INVALID, lease.guard)
                    self.assertEqual(semaphore.releases, 0)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_scope_and_manual_release_are_exactly_once_and_preserve_exceptions(self):
        cases = (
            ("normal", None),
            ("ordinary", RuntimeError("PRIVATE ordinary")),
            ("keyboard", KeyboardInterrupt("PRIVATE keyboard")),
            ("system_exit", SystemExit("PRIVATE system-exit")),
            ("generator_exit", GeneratorExit("PRIVATE generator-exit")),
        )
        for name, failure in cases:
            with self.subTest(case=name):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 1.0), semaphore,
                )
                captured = None
                try:
                    with lease as entered:
                        self.assertIs(entered, lease)
                        if failure is not None:
                            raise failure
                except BaseException as exc:
                    captured = exc
                if failure is None:
                    self.assertIsNone(captured)
                else:
                    self.assertIs(captured, failure)
                self.assertEqual(semaphore.releases, 1)
                lease.release()
                lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_clock_failure_after_acquire_releases_once_without_detail(self):
        failures = (
            RuntimeError("PRIVATE clock detail"),
            KeyboardInterrupt("PRIVATE keyboard clock"),
            SystemExit("PRIVATE system clock"),
            GeneratorExit("PRIVATE generator clock"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                events = []
                semaphore = _RecordingSemaphore(events)
                captured = None
                try:
                    self._acquire_with_fake(
                        _ScriptedClock(events, failure), semaphore,
                    )
                except BaseException as exc:
                    captured = exc
                self.assertEqual(semaphore.releases, 1)
                if isinstance(
                    failure, (KeyboardInterrupt, SystemExit, GeneratorExit),
                ):
                    self.assertIs(captured, failure)
                else:
                    self.assertIsInstance(captured, ValueError)
                    self.assertEqual(captured.code, INPUT_INVALID)
                    self.assertEqual(str(captured), INPUT_INVALID)
                    self.assertNotIn("PRIVATE", repr(captured) + repr(vars(captured)))

    def test_control_after_successful_acquire_enters_slot_cleanup(self):
        acquire_method = runtime_budget.acquire_warehouse_anomaly_runtime_slot
        source_lines, first_line = inspect.getsourcelines(acquire_method)
        target_line = next(
            first_line + offset
            for offset, line in enumerate(source_lines)
            if "if acquired is False" in line
        )
        events = []
        semaphore = _RecordingSemaphore(events)
        interrupted = KeyboardInterrupt("PRIVATE after successful acquire")
        binding = _bounded_semaphore_binding()

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code is acquire_method.__code__
                and frame.f_lineno == target_line
            ):
                raise interrupted
            return trace

        captured = None
        with mock.patch.object(runtime_budget, binding, semaphore):
            sys.settrace(trace)
            try:
                acquire_method(lambda: 1.0, wait_seconds=0)
            except BaseException as error:
                captured = error
            finally:
                sys.settrace(None)

        self.assertIs(captured, interrupted)
        self.assertEqual(semaphore.acquire_calls, [(True, 0.0)])
        self.assertEqual(semaphore.releases, 1)

    def test_control_before_acquire_return_invalidates_registered_lease(self):
        acquire_method = runtime_budget.acquire_warehouse_anomaly_runtime_slot
        source_lines, first_line = inspect.getsourcelines(acquire_method)
        target_line = next(
            first_line + offset
            for offset, line in enumerate(source_lines)
            if "return lease" in line
        )
        events = []
        semaphore = _CapacityOneSemaphore(events)
        interrupted = KeyboardInterrupt("PRIVATE before lease return")
        binding = _bounded_semaphore_binding()

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code is acquire_method.__code__
                and frame.f_lineno == target_line
            ):
                raise interrupted
            return trace

        captured = None
        with mock.patch.object(runtime_budget, binding, semaphore):
            sys.settrace(trace)
            try:
                acquire_method(lambda: 1.0, wait_seconds=0)
            except BaseException as error:
                captured = error
            finally:
                sys.settrace(None)

            self.assertIs(captured, interrupted)
            recovered = None
            traceback = captured.__traceback__
            while traceback is not None:
                if traceback.tb_frame.f_code is acquire_method.__code__:
                    recovered = traceback.tb_frame.f_locals.get("lease")
                    break
                traceback = traceback.tb_next
            self.assertIsNotNone(recovered)
            self.assertEqual(semaphore.releases, 1)
            _fixed_error(self, INPUT_INVALID, recovered.guard)

            second = acquire_method(lambda: 2.0, wait_seconds=0)
            try:
                recovered.release()
                self.assertEqual(semaphore.releases, 1)
                _fixed_error(
                    self,
                    BUSY,
                    lambda: acquire_method(
                        mock.Mock(side_effect=AssertionError("busy called clock")),
                        wait_seconds=0,
                    ),
                )
            finally:
                second.release()
        self.assertEqual(semaphore.releases, 2)

    def test_acquisition_cleanup_cannot_mask_primary_or_leak_detail(self):
        cases = (
            (
                KeyboardInterrupt("PRIVATE primary keyboard"),
                RuntimeError("PRIVATE release ordinary"),
                "primary",
            ),
            (
                RuntimeError("PRIVATE primary ordinary"),
                SystemExit("PRIVATE release system"),
                "cleanup",
            ),
            (
                MemoryError("PRIVATE primary memory"),
                RuntimeError("PRIVATE release ordinary"),
                "primary",
            ),
            (
                RuntimeError("PRIVATE primary ordinary"),
                RuntimeError("PRIVATE release ordinary"),
                "fixed",
            ),
        )
        for primary, cleanup, expected in cases:
            with self.subTest(
                primary=type(primary).__name__,
                cleanup=type(cleanup).__name__,
            ):
                events = []
                semaphore = _ReleaseFailureSemaphore(events, cleanup)
                captured = None
                try:
                    self._acquire_with_fake(
                        _ScriptedClock(events, primary), semaphore,
                    )
                except BaseException as error:
                    captured = error
                if expected == "primary":
                    self.assertIs(captured, primary)
                elif expected == "cleanup":
                    self.assertIs(captured, cleanup)
                else:
                    self.assertIsInstance(captured, ValueError)
                    self.assertEqual(captured.code, INPUT_INVALID)
                    self.assertEqual(str(captured), INPUT_INVALID)
                    self.assertNotIn(
                        "PRIVATE", repr(captured) + repr(vars(captured)),
                    )
                self.assertEqual(semaphore.releases, 1)

    def test_released_or_forged_lease_and_budget_fail_closed(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.0)
        lease = self._acquire_with_fake(clock, semaphore)
        lease_type = type(lease)
        lease.release()

        _fixed_error(self, INPUT_INVALID, lease.guard)
        _fixed_error(self, INPUT_INVALID, lease.__enter__)
        self.assertEqual(clock.calls, 1)
        self.assertEqual(semaphore.releases, 1)

        valid_budget = runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, 5000)
        forged_budgets = (
            valid_budget,
            runtime_budget.WarehouseAnomalyRuntimeBudget(True, 5000),
            runtime_budget.WarehouseAnomalyRuntimeBudget(40, 5000),
            runtime_budget.WarehouseAnomalyRuntimeBudget(math.nan, 5000),
            runtime_budget.WarehouseAnomalyRuntimeBudget(math.inf, 5000),
            runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, True),
            runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, 5000.0),
            runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, 4999),
        )
        for budget in forged_budgets:
            with self.subTest(forged_budget=budget):
                forged = SimpleNamespace(
                    budget=budget,
                    clock=lambda: 1.0,
                )
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: lease_type.guard(forged),
                )
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: lease_type.release(forged),
                )

    def test_lease_critical_state_is_not_writable_or_expiry_bypassable(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        lease = self._acquire_with_fake(
            _ScriptedClock(events, 10.0, 40.0), semaphore,
        )
        replacements = {
            "_clock": lambda: 0.0,
            "_budget": runtime_budget.WarehouseAnomalyRuntimeBudget(
                1000.0, 5000,
            ),
            "_semaphore": _RecordingSemaphore([]),
            "_released": True,
            "_token": object(),
        }
        missing = object()
        try:
            for attribute, replacement in replacements.items():
                for mutator_name, mutator in (
                    ("setattr", setattr),
                    ("object.__setattr__", object.__setattr__),
                ):
                    with self.subTest(
                        attribute=attribute, mutator=mutator_name,
                    ):
                        try:
                            original = object.__getattribute__(lease, attribute)
                        except AttributeError:
                            original = missing
                        try:
                            with self.assertRaises((AttributeError, TypeError)):
                                mutator(lease, attribute, replacement)
                        finally:
                            if original is missing:
                                try:
                                    object.__delattr__(lease, attribute)
                                except (AttributeError, TypeError):
                                    pass
                            else:
                                try:
                                    object.__setattr__(lease, attribute, original)
                                except (AttributeError, TypeError):
                                    pass

            with self.subTest(attribute="new critical state"):
                with self.assertRaises((AttributeError, TypeError)):
                    lease._attacker_runtime_state = object()

            _fixed_error(self, DEADLINE_EXCEEDED, lease.guard)
            self.assertEqual(semaphore.releases, 0)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_actual_class_direct_and_object_new_clones_are_not_registered(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.0, 11.0)
        lease = self._acquire_with_fake(clock, semaphore)
        lease_type = type(lease)
        try:
            direct = lease_type(
                object.__getattribute__(lease, "_token"),
                lease.budget,
                lambda: 11.0,
                semaphore,
            )
            with self.subTest(clone="direct", operation="guard"):
                _fixed_error(self, INPUT_INVALID, direct.guard)
            with self.subTest(clone="direct", operation="release"):
                _fixed_error(self, INPUT_INVALID, direct.release)

            copied = object.__new__(lease_type)
            slots = lease_type.__slots__
            if isinstance(slots, str):
                slots = (slots,)
            for attribute in slots:
                try:
                    value = object.__getattribute__(lease, attribute)
                    object.__setattr__(copied, attribute, value)
                except (AttributeError, TypeError):
                    pass
            with self.subTest(clone="object.__new__", operation="guard"):
                _fixed_error(
                    self, INPUT_INVALID, lambda: lease_type.guard(copied),
                )
            with self.subTest(clone="object.__new__", operation="release"):
                _fixed_error(
                    self, INPUT_INVALID, lambda: lease_type.release(copied),
                )
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_stale_released_lease_cannot_release_a_new_holder(self):
        events = []
        semaphore = _CapacityOneSemaphore(events)
        binding = _bounded_semaphore_binding()
        with mock.patch.object(runtime_budget, binding, semaphore):
            first = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 1.0, wait_seconds=0,
            )
            first.release()
            second = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 2.0, wait_seconds=0,
            )
            try:
                try:
                    object.__setattr__(first, "_released", False)
                except (AttributeError, TypeError):
                    pass

                with self.subTest(operation="stale guard"):
                    _fixed_error(self, INPUT_INVALID, first.guard)

                releases_before_stale = semaphore.releases
                with self.subTest(operation="stale release"):
                    try:
                        first.release()
                    except ValueError as error:
                        self.assertEqual(
                            getattr(error, "code", None), INPUT_INVALID,
                        )
                    self.assertEqual(
                        semaphore.releases, releases_before_stale,
                    )

                third_clock = mock.Mock(
                    side_effect=AssertionError("busy path called clock"),
                )
                with self.subTest(operation="third acquisition"):
                    error = _fixed_error(
                        self,
                        BUSY,
                        lambda: runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                            third_clock, wait_seconds=0,
                        ),
                    )
                    self.assertEqual(error.code, BUSY)
                    third_clock.assert_not_called()
            finally:
                second.release()
        self.assertEqual(semaphore.releases, 2)

    def test_interrupted_release_is_never_retried_against_a_new_holder(self):
        events = []
        interrupted = KeyboardInterrupt("PRIVATE after release side effect")
        semaphore = _ReleaseSideEffectThenFailureSemaphore(
            events, interrupted,
        )
        binding = _bounded_semaphore_binding()
        with mock.patch.object(runtime_budget, binding, semaphore):
            first = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 1.0, wait_seconds=0,
            )
            with self.assertRaises(KeyboardInterrupt) as raised:
                first.release()
            self.assertIs(raised.exception, interrupted)
            self.assertEqual(semaphore.releases, 1)

            second = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 2.0, wait_seconds=0,
            )
            try:
                first.release()
                self.assertEqual(semaphore.releases, 1)
                _fixed_error(
                    self,
                    BUSY,
                    lambda: runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                        mock.Mock(side_effect=AssertionError("busy called clock")),
                        wait_seconds=0,
                    ),
                )
            finally:
                second.release()
        self.assertEqual(semaphore.releases, 2)

    def test_release_registry_transition_is_atomic_at_control_boundaries(self):
        release_method = runtime_budget._WarehouseAnomalyRuntimeLease.release
        source_lines, first_line = inspect.getsourcelines(release_method)

        def line_for(fragment):
            for offset, line in enumerate(source_lines):
                if fragment in line:
                    return first_line + offset
            self.fail("release transition fragment is missing: " + fragment)

        replace_line = line_for("_LEASE_STATES[self] = terminal_state")
        release_line = line_for("semaphore.release()")

        for boundary, target_line, retry_releases in (
            ("before registry replacement", replace_line, 1),
            ("after registry replacement", release_line, 0),
        ):
            with self.subTest(boundary=boundary):
                events = []
                semaphore = _CapacityOneSemaphore(events)
                lease = self._acquire_with_fake(
                    lambda: 1.0, semaphore, wait=0,
                )
                interrupted = KeyboardInterrupt("PRIVATE release transition")

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is release_method.__code__
                        and frame.f_lineno == target_line
                    ):
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    lease.release()
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)

                self.assertIs(captured, interrupted)
                self.assertEqual(semaphore.releases, 0)
                lease.release()
                self.assertEqual(semaphore.releases, retry_releases)
                if retry_releases == 0:
                    _fixed_error(self, INPUT_INVALID, lease.guard)
                    _fixed_error(
                        self,
                        BUSY,
                        lambda: self._acquire_with_fake(
                            mock.Mock(
                                side_effect=AssertionError("busy called clock"),
                            ),
                            semaphore,
                            wait=0,
                        ),
                    )

    def test_released_lease_registry_does_not_retain_lease_or_clock(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 1.0)
        lease = self._acquire_with_fake(clock, semaphore)
        lease_reference = weakref.ref(lease)
        clock_reference = weakref.ref(clock)
        lease.release()

        del lease
        del clock
        gc.collect()

        self.assertIsNone(lease_reference())
        self.assertIsNone(clock_reference())
        self.assertEqual(semaphore.releases, 1)

        class SelfReferentialClock:
            def __init__(self):
                self.lease = None

            def __call__(self):
                return 2.0

        cyclic_semaphore = _RecordingSemaphore([])
        cyclic_clock = SelfReferentialClock()
        cyclic_lease = self._acquire_with_fake(
            cyclic_clock, cyclic_semaphore,
        )
        cyclic_clock.lease = cyclic_lease
        cyclic_lease_reference = weakref.ref(cyclic_lease)
        cyclic_clock_reference = weakref.ref(cyclic_clock)
        cyclic_lease.release()

        del cyclic_lease
        del cyclic_clock
        gc.collect()

        self.assertIsNone(cyclic_lease_reference())
        self.assertIsNone(cyclic_clock_reference())
        self.assertEqual(cyclic_semaphore.releases, 1)

    def test_extreme_and_subclass_numbers_fail_with_correct_slot_ownership(self):
        class IntSubclass(int):
            pass

        class FloatSubclass(float):
            pass

        for wait in (10 ** 1000, IntSubclass(0), FloatSubclass(0.5)):
            with self.subTest(stage="wait", value_type=type(wait).__name__):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = mock.Mock(return_value=1.0)
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: self._acquire_with_fake(
                        clock, semaphore, wait=wait,
                    ),
                )
                self.assertEqual(semaphore.acquire_calls, [])
                self.assertEqual(semaphore.releases, 0)
                clock.assert_not_called()

        for value in (
            10 ** 1000,
            2 ** 53 + 1,
            2 ** 53 + 3,
            IntSubclass(1),
            FloatSubclass(1.0),
        ):
            with self.subTest(
                stage="initial clock", value_type=type(value).__name__,
            ):
                events = []
                semaphore = _RecordingSemaphore(events)
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: self._acquire_with_fake(
                        _ScriptedClock(events, value), semaphore,
                    ),
                )
                self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
                self.assertEqual(semaphore.releases, 1)

        for value in (
            10 ** 1000,
            2 ** 53 + 1,
            2 ** 53 + 3,
            IntSubclass(39),
            FloatSubclass(39.0),
        ):
            with self.subTest(
                stage="guard clock", value_type=type(value).__name__,
            ):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, value), semaphore,
                )
                try:
                    _fixed_error(self, INPUT_INVALID, lease.guard)
                    self.assertEqual(semaphore.releases, 0)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

        self.assertEqual(
            sys.float_info.max + 30.0, sys.float_info.max,
        )
        events = []
        semaphore = _RecordingSemaphore(events)
        returned = []

        def acquire_max_float():
            lease = self._acquire_with_fake(
                _ScriptedClock(events, sys.float_info.max), semaphore,
            )
            returned.append(lease)
            return lease

        try:
            _fixed_error(self, INPUT_INVALID, acquire_max_float)
        finally:
            for lease in returned:
                lease.release()
        self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
        self.assertEqual(semaphore.releases, 1)

        for exponent in range(54, 58):
            with self.subTest(non_exact_30_second_budget=exponent):
                start = float(2 ** exponent)
                self.assertNotEqual((start + 30.0) - start, 30.0)
                local_events = []
                local_semaphore = _RecordingSemaphore(local_events)
                _fixed_error(
                    self,
                    INPUT_INVALID,
                    lambda: self._acquire_with_fake(
                        _ScriptedClock(local_events, start), local_semaphore,
                    ),
                )
                self.assertEqual(local_semaphore.releases, 1)

    def test_normal_fractional_monotonic_values_keep_the_30_second_budget(self):
        starts = (
            2.8512556107785976,
            2.135719697447644,
        )
        for started in starts:
            with self.subTest(started=started):
                self.assertNotEqual((started + 30.0) - started, 30.0)
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, started),
                    semaphore,
                )
                try:
                    self.assertEqual(
                        lease.budget.deadline_monotonic,
                        started + 30.0,
                    )
                    self.assertLessEqual(
                        abs(
                            (lease.budget.deadline_monotonic - started)
                            - 30.0
                        ),
                        max(
                            math.ulp(started),
                            math.ulp(lease.budget.deadline_monotonic),
                        ),
                    )
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_semaphore_acquire_failures_preserve_control_and_never_release(self):
        failures = (
            RuntimeError("PRIVATE semaphore"),
            KeyboardInterrupt("PRIVATE keyboard semaphore"),
            SystemExit("PRIVATE system semaphore"),
            GeneratorExit("PRIVATE generator semaphore"),
            MemoryError("PRIVATE memory semaphore"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                events = []
                semaphore = _AcquireFailureSemaphore(events, failure)
                clock = mock.Mock(return_value=1.0)
                captured = None
                try:
                    self._acquire_with_fake(clock, semaphore)
                except BaseException as error:
                    captured = error
                if isinstance(failure, RuntimeError):
                    self.assertIsInstance(captured, ValueError)
                    self.assertEqual(captured.code, INPUT_INVALID)
                    self.assertEqual(str(captured), INPUT_INVALID)
                    self.assertIsNone(captured.__cause__)
                    self.assertNotIn(
                        "PRIVATE", repr(captured) + repr(vars(captured)),
                    )
                else:
                    self.assertIs(captured, failure)
                self.assertEqual(semaphore.acquire_calls, [(True, 1.0)])
                self.assertEqual(semaphore.releases, 0)
                clock.assert_not_called()

    def test_guard_clock_failures_preserve_control_until_context_release(self):
        failures = (
            RuntimeError("PRIVATE guard clock"),
            KeyboardInterrupt("PRIVATE keyboard guard"),
            SystemExit("PRIVATE system guard"),
            GeneratorExit("PRIVATE generator guard"),
            MemoryError("PRIVATE memory guard"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, failure), semaphore,
                )
                captured = None
                try:
                    try:
                        lease.guard()
                    except BaseException as error:
                        captured = error
                    if isinstance(failure, RuntimeError):
                        self.assertIsInstance(captured, ValueError)
                        self.assertEqual(captured.code, INPUT_INVALID)
                        self.assertEqual(str(captured), INPUT_INVALID)
                        self.assertIsNone(captured.__cause__)
                        self.assertNotIn(
                            "PRIVATE", repr(captured) + repr(vars(captured)),
                        )
                    else:
                        self.assertIs(captured, failure)
                    self.assertEqual(semaphore.releases, 0)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_exact_config_controls_and_guard_order(self):
        factory = runtime_budget.open_warehouse_anomaly_read_connection
        signature = inspect.signature(factory)
        self.assertEqual(
            list(signature.parameters), ["db_config", "lease", "connect"],
        )
        self.assertEqual(
            signature.parameters["db_config"].kind,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        self.assertEqual(
            signature.parameters["lease"].kind,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        connector_parameter = signature.parameters["connect"]
        self.assertEqual(
            connector_parameter.kind, inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(connector_parameter.default, psycopg2.connect)

        events = []
        semaphore = _CapacityOneSemaphore(events)
        clock = _ScriptedClock(events, 10.0, 11.0, 12.0)
        connection_calls = []

        class RecordingConnection:
            def __init__(self):
                self._autocommit = False
                self.close_calls = 0

            @property
            def autocommit(self):
                return self._autocommit

            @autocommit.setter
            def autocommit(self, value):
                events.append("autocommit")
                self._autocommit = value

            def close(self):
                events.append("close")
                self.close_calls += 1

        connection = RecordingConnection()

        def connect(**kwargs):
            events.append("connect")
            connection_calls.append(dict(kwargs))
            return connection

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "PRIVATE exact password",
            "host": "/private/tmp/warehouse-preview-socket",
            "port": "5432",
        }
        original_config = dict(db_config)
        expected_options = (
            "-c statement_timeout=5000 "
            "-c lock_timeout=1000 "
            "-c idle_in_transaction_session_timeout=10000 "
            "-c client_encoding=UTF8 "
            "-c search_path=pg_catalog,public"
        )

        lease = self._acquire_with_fake(clock, semaphore, wait=0)
        try:
            returned = factory(db_config, lease, connect=connect)

            self.assertIs(returned, connection)
            self.assertEqual(db_config, original_config)
            self.assertEqual(set(db_config), {
                "dbname", "user", "password", "host", "port",
            })
            self.assertEqual(connection_calls, [{
                **original_config,
                "connect_timeout": 5,
                "options": expected_options,
            }])
            self.assertIsNot(connection_calls[0], db_config)
            self.assertIs(connection.autocommit, True)
            self.assertEqual(connection.close_calls, 0)
            self.assertEqual(events, [
                "semaphore_acquire",
                "clock",
                "clock",
                "connect",
                "clock",
                "autocommit",
            ])
            self.assertEqual(clock.calls, 3)
            self.assertFalse(semaphore.available)
            self.assertEqual(semaphore.releases, 0)
            self.assertEqual(
                lease.budget,
                runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, 5000),
            )
        finally:
            self._close_b2_only_connection_fixture(lease, connection)
        self.assertTrue(semaphore.available)
        self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_rejects_noncanonical_config_and_connector(self):
        factory = runtime_budget.open_warehouse_anomaly_read_connection
        valid = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }

        class DictSubclass(dict):
            pass

        class StringSubclass(str):
            pass

        invalid_configs = [
            ("dict subclass", DictSubclass(valid)),
            ("wrong config type", tuple(valid.items())),
            (
                "string-subclass key",
                {
                    StringSubclass(key) if key == "dbname" else key: value
                    for key, value in valid.items()
                },
            ),
        ]
        for key in valid:
            invalid_configs.append((
                "missing " + key,
                {name: value for name, value in valid.items() if name != key},
            ))
        for extra in (
            "connect_timeout", "options", "sslmode", "service", "hostaddr",
            "extra",
        ):
            invalid_configs.append((
                "extra " + extra,
                {**valid, extra: "PRIVATE caller override"},
            ))
        for key in valid:
            invalid_configs.append((
                "string-subclass value " + key,
                {**valid, key: StringSubclass(valid[key])},
            ))
            invalid_configs.append((
                "non-string value " + key,
                {**valid, key: 5432 if key == "port" else None},
            ))
            invalid_configs.append((
                "NUL value " + key,
                {**valid, key: "PRIVATE\x00value"},
            ))
        for key in ("dbname", "user", "host"):
            invalid_configs.append((
                "empty " + key,
                {**valid, key: ""},
            ))
        for host in ("db-one,db-two", "db one"):
            invalid_configs.append((
                "non-single host " + repr(host),
                {**valid, "host": host},
            ))
        for port in (
            "", "0", "65536", "-1", "+1", "1.0", "5432,5433",
            "5432 5433", " 5432", "5432 ",
        ):
            invalid_configs.append((
                "invalid port " + repr(port),
                {**valid, "port": port},
            ))

        for name, db_config in invalid_configs:
            with self.subTest(case=name):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 12.0)
                connector = mock.Mock(
                    side_effect=AssertionError("PRIVATE connector called"),
                )
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                try:
                    _fixed_error(
                        self,
                        INPUT_INVALID,
                        lambda: factory(
                            db_config, lease, connect=connector,
                        ),
                    )
                    connector.assert_not_called()
                    self.assertEqual(semaphore.releases, 1)
                    _fixed_error(self, INPUT_INVALID, lease.guard)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

        for connector in (None, False, "connect", object()):
            with self.subTest(noncallable=repr(connector)):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, 11.0),
                    semaphore,
                    wait=0,
                )
                try:
                    _fixed_error(
                        self,
                        INPUT_INVALID,
                        lambda: factory(
                            valid, lease, connect=connector,
                        ),
                    )
                    self.assertEqual(semaphore.releases, 1)
                    _fixed_error(self, INPUT_INVALID, lease.guard)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_accepts_empty_password_and_port_boundaries(self):
        factory = runtime_budget.open_warehouse_anomaly_read_connection
        for port in ("1", "65535"):
            with self.subTest(port=port):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, 11.0, 12.0),
                    semaphore,
                    wait=0,
                )
                connection = SimpleNamespace(
                    autocommit=False,
                    close=mock.Mock(),
                )
                connector = mock.Mock(return_value=connection)
                db_config = {
                    "dbname": "warehouse_preview",
                    "user": "warehouse_reader",
                    "password": "",
                    "host": "127.0.0.1",
                    "port": port,
                }
                try:
                    returned = factory(
                        db_config, lease, connect=connector,
                    )
                    self.assertIs(returned, connection)
                    connector.assert_called_once()
                    kwargs = connector.call_args.kwargs
                    self.assertEqual(kwargs["password"], "")
                    self.assertEqual(kwargs["port"], port)
                    self.assertIs(connection.autocommit, True)
                    connection.close.assert_not_called()
                    self.assertEqual(semaphore.releases, 0)
                finally:
                    self._close_b2_only_connection_fixture(
                        lease, connection,
                    )
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_rejects_invalid_lease_without_slot_corruption(self):
        factory = runtime_budget.open_warehouse_anomaly_read_connection
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        events = []
        semaphore = _CapacityOneSemaphore(events)
        binding = _bounded_semaphore_binding()
        with mock.patch.object(runtime_budget, binding, semaphore):
            released = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 1.0, wait_seconds=0,
            )
            released.release()
            holder = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                lambda: 2.0, wait_seconds=0,
            )
            forged = type(holder)()
            invalid_leases = (
                ("none", None),
                ("object", object()),
                ("namespace", SimpleNamespace()),
                (
                    "bare budget",
                    runtime_budget.WarehouseAnomalyRuntimeBudget(32.0, 5000),
                ),
                ("actual-class forge", forged),
                ("released genuine", released),
            )
            try:
                for name, invalid_lease in invalid_leases:
                    with self.subTest(case=name):
                        connector = mock.Mock(
                            side_effect=AssertionError(
                                "PRIVATE invalid lease reached connector",
                            ),
                        )
                        releases_before = semaphore.releases
                        _fixed_error(
                            self,
                            INPUT_INVALID,
                            lambda: factory(
                                db_config,
                                invalid_lease,
                                connect=connector,
                            ),
                        )
                        connector.assert_not_called()
                        self.assertEqual(
                            semaphore.releases, releases_before,
                        )
                        busy_clock = mock.Mock(
                            side_effect=AssertionError(
                                "busy invalid-lease path called clock",
                            ),
                        )
                        _fixed_error(
                            self,
                            BUSY,
                            lambda: runtime_budget.acquire_warehouse_anomaly_runtime_slot(
                                busy_clock, wait_seconds=0,
                            ),
                        )
                        busy_clock.assert_not_called()
            finally:
                holder.release()
        self.assertEqual(semaphore.releases, 2)

    def test_connection_factory_preconnect_boundary_releases_without_connector(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.0, 40.0)
        connector = mock.Mock(
            side_effect=AssertionError("PRIVATE expired connector called"),
        )
        lease = self._acquire_with_fake(clock, semaphore, wait=0)
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        try:
            _fixed_error(
                self,
                DEADLINE_EXCEEDED,
                lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config, lease, connect=connector,
                ),
            )
            connector.assert_not_called()
            self.assertEqual(clock.calls, 2)
            self.assertEqual(semaphore.releases, 1)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_connect_error_runs_post_guard_with_precedence(self):
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        for post_clock, expected_code in (
            (39.999999, READ_FAILED),
            (40.0, DEADLINE_EXCEEDED),
        ):
            with self.subTest(
                post_clock=post_clock, expected_code=expected_code,
            ):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(
                    events, 10.0, 11.0, post_clock,
                )
                connector = mock.Mock(
                    side_effect=RuntimeError("PRIVATE connector detail"),
                )
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                try:
                    _fixed_error(
                        self,
                        expected_code,
                        lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                            db_config, lease, connect=connector,
                        ),
                    )
                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_postconnect_expiry_closes_falsey_resource(self):
        missing = object()

        class FalseyConnection:
            def __init__(self, close_value):
                self._close_value = close_value
                self.autocommit_sets = []
                self.bool_calls = 0
                self.close_lookups = 0
                self.cursor_calls = 0
                self.rollback_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                return False

            @property
            def autocommit(self):
                return False

            @autocommit.setter
            def autocommit(self, value):
                self.autocommit_sets.append(value)

            @property
            def close(self):
                self.close_lookups += 1
                if self._close_value is missing:
                    raise AttributeError("PRIVATE missing close")
                return self._close_value

            def cursor(self):
                self.cursor_calls += 1
                raise AssertionError("PRIVATE cursor called")

            def rollback(self):
                self.rollback_calls += 1
                raise AssertionError("PRIVATE rollback called")

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        close_cases = (
            ("normal", mock.Mock(), DEADLINE_EXCEEDED),
            (
                "ordinary",
                mock.Mock(side_effect=RuntimeError("PRIVATE close detail")),
                DEADLINE_EXCEEDED,
            ),
            ("missing", missing, DEADLINE_EXCEEDED),
            ("noncallable", None, DEADLINE_EXCEEDED),
            (
                "keyboard",
                mock.Mock(side_effect=KeyboardInterrupt("PRIVATE close keyboard")),
                None,
            ),
            (
                "system",
                mock.Mock(side_effect=SystemExit("PRIVATE close system")),
                None,
            ),
            (
                "generator",
                mock.Mock(side_effect=GeneratorExit("PRIVATE close generator")),
                None,
            ),
        )
        for name, close_value, fixed_code in close_cases:
            with self.subTest(case=name):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 40.0)
                connection = FalseyConnection(close_value)
                connector = mock.Mock(return_value=connection)
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                try:
                    if fixed_code is not None:
                        _fixed_error(
                            self,
                            fixed_code,
                            lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config, lease, connect=connector,
                            ),
                        )
                    else:
                        expected_control = close_value.side_effect
                        captured = None
                        try:
                            runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config, lease, connect=connector,
                            )
                        except BaseException as error:
                            captured = error
                        self.assertIs(captured, expected_control)

                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    self.assertEqual(connection.bool_calls, 0)
                    self.assertEqual(connection.autocommit_sets, [])
                    self.assertEqual(connection.cursor_calls, 0)
                    self.assertEqual(connection.rollback_calls, 0)
                    if isinstance(close_value, mock.Mock):
                        close_value.assert_called_once_with()
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_connect_controls_run_post_guard_and_release(self):
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        failures = (
            KeyboardInterrupt("PRIVATE connector keyboard"),
            SystemExit("PRIVATE connector system"),
            GeneratorExit("PRIVATE connector generator"),
            MemoryError("PRIVATE connector memory"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 40.0)
                connector = mock.Mock(side_effect=failure)
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                captured = None
                try:
                    try:
                        runtime_budget.open_warehouse_anomaly_read_connection(
                            db_config, lease, connect=connector,
                        )
                    except BaseException as error:
                        captured = error
                    self.assertIs(captured, failure)
                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_clock_faults_close_and_release_by_precedence(self):
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }

        events = []
        semaphore = _RecordingSemaphore(events)
        connector = mock.Mock(
            side_effect=AssertionError("PRIVATE pre-guard connector called"),
        )
        lease = self._acquire_with_fake(
            _ScriptedClock(
                events, 10.0, RuntimeError("PRIVATE pre-guard clock"),
            ),
            semaphore,
            wait=0,
        )
        try:
            _fixed_error(
                self,
                INPUT_INVALID,
                lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config, lease, connect=connector,
                ),
            )
            connector.assert_not_called()
            self.assertEqual(semaphore.releases, 1)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

        failures = (
            RuntimeError("PRIVATE post-guard clock"),
            KeyboardInterrupt("PRIVATE post-guard keyboard"),
            SystemExit("PRIVATE post-guard system"),
            GeneratorExit("PRIVATE post-guard generator"),
        )
        for failure in failures:
            with self.subTest(post_guard=type(failure).__name__):
                local_events = []
                local_semaphore = _RecordingSemaphore(local_events)
                close = mock.Mock()
                connection = SimpleNamespace(
                    autocommit=False,
                    close=close,
                )
                connector = mock.Mock(return_value=connection)
                clock = _ScriptedClock(
                    local_events, 10.0, 11.0, failure,
                )
                local_lease = self._acquire_with_fake(
                    clock, local_semaphore, wait=0,
                )
                try:
                    if isinstance(failure, RuntimeError):
                        _fixed_error(
                            self,
                            INPUT_INVALID,
                            lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config,
                                local_lease,
                                connect=connector,
                            ),
                        )
                    else:
                        captured = None
                        try:
                            runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config,
                                local_lease,
                                connect=connector,
                            )
                        except BaseException as error:
                            captured = error
                        self.assertIs(captured, failure)
                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    close.assert_called_once_with()
                    self.assertIs(connection.autocommit, False)
                    self.assertEqual(local_semaphore.releases, 1)
                finally:
                    local_lease.release()
                self.assertEqual(local_semaphore.releases, 1)

    def test_connection_factory_connector_error_yields_to_postguard_control(self):
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        for control in (
            KeyboardInterrupt("PRIVATE post-connect keyboard"),
            SystemExit("PRIVATE post-connect system"),
            GeneratorExit("PRIVATE post-connect generator"),
        ):
            with self.subTest(control=type(control).__name__):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, control)
                connector = mock.Mock(
                    side_effect=RuntimeError("PRIVATE connector ordinary"),
                )
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                captured = None
                try:
                    try:
                        runtime_budget.open_warehouse_anomaly_read_connection(
                            db_config, lease, connect=connector,
                        )
                    except BaseException as error:
                        captured = error
                    self.assertIs(captured, control)
                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

        first_control = KeyboardInterrupt("PRIVATE first connector control")
        later_control = SystemExit("PRIVATE later post-guard control")
        events = []
        semaphore = _RecordingSemaphore(events)
        lease = self._acquire_with_fake(
            _ScriptedClock(events, 10.0, 11.0, later_control),
            semaphore,
            wait=0,
        )
        captured = None
        try:
            try:
                runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config,
                    lease,
                    connect=mock.Mock(side_effect=first_control),
                )
            except BaseException as error:
                captured = error
            self.assertIs(captured, first_control)
            self.assertEqual(semaphore.releases, 1)
        finally:
            lease.release()

    def test_connection_factory_lease_claim_is_one_use(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        lease = self._acquire_with_fake(
            _ScriptedClock(events, 10.0, 11.0, 12.0),
            semaphore,
            wait=0,
        )
        first = SimpleNamespace(autocommit=False, close=mock.Mock())
        first_connector = mock.Mock(return_value=first)
        second_connector = mock.Mock(
            side_effect=AssertionError("PRIVATE second connector called"),
        )
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        try:
            self.assertIs(
                runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config, lease, connect=first_connector,
                ),
                first,
            )
            _fixed_error(
                self,
                INPUT_INVALID,
                lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config, lease, connect=second_connector,
                ),
            )
            second_connector.assert_not_called()
            first.close.assert_not_called()
            self.assertEqual(semaphore.releases, 0)
        finally:
            first.close()
            self._close_b2_only_connection_fixture(
                lease, first, close=False,
            )
        self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_rejects_invalid_return_and_autocommit(self):
        class MissingAutocommitConnection:
            __slots__ = ("close",)

            def __init__(self, close):
                self.close = close

        class FailingAutocommitConnection:
            def __init__(self, failure, close):
                self._autocommit = False
                self.failure = failure
                self.close = close
                self.set_calls = 0

            @property
            def autocommit(self):
                return self._autocommit

            @autocommit.setter
            def autocommit(self, value):
                self.set_calls += 1
                raise self.failure

        class IgnoringAutocommitConnection:
            def __init__(self, close):
                self.close = close

            @property
            def autocommit(self):
                return False

            @autocommit.setter
            def autocommit(self, value):
                pass

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        missing_close = mock.Mock()
        ordinary_close = mock.Mock()
        keyboard_close = mock.Mock()
        system_close = mock.Mock()
        generator_close = mock.Mock()
        ignored_close = mock.Mock()
        cases = (
            ("none", None, None, READ_FAILED),
            ("false", False, None, READ_FAILED),
            (
                "missing autocommit",
                MissingAutocommitConnection(missing_close),
                missing_close,
                READ_FAILED,
            ),
            (
                "ordinary setter",
                FailingAutocommitConnection(
                    RuntimeError("PRIVATE autocommit ordinary"),
                    ordinary_close,
                ),
                ordinary_close,
                READ_FAILED,
            ),
            (
                "ignored setter",
                IgnoringAutocommitConnection(ignored_close),
                ignored_close,
                READ_FAILED,
            ),
            (
                "keyboard setter",
                FailingAutocommitConnection(
                    KeyboardInterrupt("PRIVATE autocommit keyboard"),
                    keyboard_close,
                ),
                keyboard_close,
                None,
            ),
            (
                "system setter",
                FailingAutocommitConnection(
                    SystemExit("PRIVATE autocommit system"),
                    system_close,
                ),
                system_close,
                None,
            ),
            (
                "generator setter",
                FailingAutocommitConnection(
                    GeneratorExit("PRIVATE autocommit generator"),
                    generator_close,
                ),
                generator_close,
                None,
            ),
        )
        for name, connection, close, fixed_code in cases:
            with self.subTest(case=name):
                if close is not None:
                    close.reset_mock()
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 12.0)
                connector = mock.Mock(return_value=connection)
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                try:
                    if fixed_code is not None:
                        _fixed_error(
                            self,
                            fixed_code,
                            lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config, lease, connect=connector,
                            ),
                        )
                    else:
                        expected_control = connection.failure
                        captured = None
                        try:
                            runtime_budget.open_warehouse_anomaly_read_connection(
                                db_config, lease, connect=connector,
                            )
                        except BaseException as error:
                            captured = error
                        self.assertIs(captured, expected_control)
                    connector.assert_called_once()
                    self.assertEqual(clock.calls, 3)
                    if close is not None:
                        close.assert_called_once_with()
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_cleanup_control_precedence_and_release(self):
        class FailingAutocommitConnection:
            def __init__(self, primary, close):
                self.primary = primary
                self.close = close

            @property
            def autocommit(self):
                return False

            @autocommit.setter
            def autocommit(self, value):
                raise self.primary

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }

        events = []
        semaphore = _RecordingSemaphore(events)
        close = mock.Mock(
            side_effect=RuntimeError("PRIVATE close ordinary"),
        )
        connection = FailingAutocommitConnection(
            RuntimeError("PRIVATE autocommit primary"), close,
        )
        lease = self._acquire_with_fake(
            _ScriptedClock(events, 10.0, 11.0, 12.0),
            semaphore,
            wait=0,
        )
        try:
            _fixed_error(
                self,
                READ_FAILED,
                lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config,
                    lease,
                    connect=mock.Mock(return_value=connection),
                ),
            )
            close.assert_called_once_with()
            self.assertEqual(semaphore.releases, 1)
        finally:
            lease.release()

        for release_control in (
            KeyboardInterrupt("PRIVATE release keyboard"),
            SystemExit("PRIVATE release system"),
            GeneratorExit("PRIVATE release generator"),
        ):
            with self.subTest(release_control=type(release_control).__name__):
                local_events = []
                failing_semaphore = _ReleaseFailureSemaphore(
                    local_events, release_control,
                )
                local_lease = self._acquire_with_fake(
                    _ScriptedClock(local_events, 10.0, 11.0, 12.0),
                    failing_semaphore,
                    wait=0,
                )
                connector = mock.Mock(
                    side_effect=RuntimeError("PRIVATE connector primary"),
                )
                captured = None
                try:
                    try:
                        runtime_budget.open_warehouse_anomaly_read_connection(
                            db_config, local_lease, connect=connector,
                        )
                    except BaseException as error:
                        captured = error
                    self.assertIs(captured, release_control)
                    connector.assert_called_once()
                    self.assertEqual(failing_semaphore.releases, 1)
                finally:
                    local_lease.release()
                self.assertEqual(failing_semaphore.releases, 1)

        first_control = KeyboardInterrupt("PRIVATE first connector control")
        later_control = SystemExit("PRIVATE later release control")
        control_events = []
        control_semaphore = _ReleaseFailureSemaphore(
            control_events, later_control,
        )
        control_lease = self._acquire_with_fake(
            _ScriptedClock(control_events, 10.0, 11.0, 12.0),
            control_semaphore,
            wait=0,
        )
        captured = None
        try:
            try:
                runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config,
                    control_lease,
                    connect=mock.Mock(side_effect=first_control),
                )
            except BaseException as error:
                captured = error
            self.assertIs(captured, first_control)
            self.assertEqual(control_semaphore.releases, 1)
        finally:
            control_lease.release()
        self.assertEqual(control_semaphore.releases, 1)

    def test_connection_factory_rejects_falsey_resource_after_postguard(self):
        class FalseyConnection:
            def __init__(self):
                self._autocommit = False
                self.bool_calls = 0
                self.close = mock.Mock()

            def __bool__(self):
                self.bool_calls += 1
                return False

            @property
            def autocommit(self):
                return self._autocommit

            @autocommit.setter
            def autocommit(self, value):
                self._autocommit = value

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        events = []
        semaphore = _RecordingSemaphore(events)
        lease = self._acquire_with_fake(
            _ScriptedClock(events, 10.0, 11.0, 12.0),
            semaphore,
            wait=0,
        )
        connection = FalseyConnection()
        try:
            _fixed_error(
                self,
                READ_FAILED,
                lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                    db_config,
                    lease,
                    connect=mock.Mock(return_value=connection),
                ),
            )
            self.assertEqual(connection.bool_calls, 1)
            self.assertIs(connection.autocommit, False)
            connection.close.assert_called_once_with()
            self.assertEqual(semaphore.releases, 1)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_requires_callable_close_before_return(self):
        class MissingCloseConnection:
            __slots__ = ("_autocommit", "autocommit_sets")

            def __init__(self):
                self._autocommit = False
                self.autocommit_sets = 0

            @property
            def autocommit(self):
                return self._autocommit

            @autocommit.setter
            def autocommit(self, value):
                self.autocommit_sets += 1
                self._autocommit = value

        class NoncallableCloseConnection(MissingCloseConnection):
            __slots__ = ("close",)

            def __init__(self):
                super().__init__()
                self.close = None

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        for name, connection in (
            ("missing", MissingCloseConnection()),
            ("noncallable", NoncallableCloseConnection()),
        ):
            with self.subTest(case=name):
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 12.0)
                lease = self._acquire_with_fake(clock, semaphore, wait=0)
                try:
                    _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: runtime_budget.open_warehouse_anomaly_read_connection(
                            db_config,
                            lease,
                            connect=mock.Mock(return_value=connection),
                        ),
                    )
                    self.assertEqual(clock.calls, 3)
                    self.assertEqual(connection.autocommit_sets, 0)
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_control_scope_covers_owned_boundaries(self):
        factory = runtime_budget.open_warehouse_anomaly_read_connection
        source_lines, first_line = inspect.getsourcelines(factory)

        def line_for(fragment):
            return next(
                first_line + offset
                for offset, line in enumerate(source_lines)
                if fragment in line
            )

        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }
        for boundary, fragment, connected, autocommit in (
            (
                "after genuine lease validation",
                "if not callable(connect)",
                False,
                False,
            ),
            (
                "after preconnect guard",
                "fallback_code = _READ_FAILED",
                False,
                False,
            ),
            (
                "after connector return",
                "post_guard_error = None",
                True,
                False,
            ),
            (
                "after postconnect guard",
                "if connect_error is not None",
                True,
                False,
            ),
            ("at return", "return connection", True, True),
        ):
            with self.subTest(boundary=boundary):
                target_line = line_for(fragment)
                events = []
                semaphore = _RecordingSemaphore(events)
                clock = _ScriptedClock(events, 10.0, 11.0, 12.0)
                close = mock.Mock()
                connection = SimpleNamespace(
                    autocommit=False,
                    close=close,
                )
                interrupted = KeyboardInterrupt(
                    "PRIVATE before connection return",
                )
                lease = self._acquire_with_fake(
                    clock, semaphore, wait=0,
                )

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is factory.__code__
                        and frame.f_lineno == target_line
                    ):
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    factory(
                        db_config,
                        lease,
                        connect=mock.Mock(return_value=connection),
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertIs(captured, interrupted)
                    self.assertIs(connection.autocommit, autocommit)
                    self.assertEqual(
                        close.call_count, 1 if connected else 0,
                    )
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_claim_boundary_releases_genuine_lease(self):
        claim = runtime_budget._claim_active_lease
        source_lines, first_line = inspect.getsourcelines(claim)
        for boundary, fragment in (
            ("before token write", "state.claim_token = claim_token"),
            ("after token write", "return True"),
        ):
            with self.subTest(boundary=boundary):
                target_line = next(
                    first_line + offset
                    for offset, line in enumerate(source_lines)
                    if fragment in line
                )
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0), semaphore, wait=0,
                )
                interrupted = KeyboardInterrupt("PRIVATE claim boundary")
                connector = mock.Mock(
                    side_effect=AssertionError("PRIVATE connector called"),
                )

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is claim.__code__
                        and frame.f_lineno == target_line
                    ):
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runtime_budget.open_warehouse_anomaly_read_connection(
                        {
                            "dbname": "warehouse_preview",
                            "user": "warehouse_reader",
                            "password": "",
                            "host": "127.0.0.1",
                            "port": "5432",
                        },
                        lease,
                        connect=connector,
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertIs(captured, interrupted)
                    connector.assert_not_called()
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_connection_factory_cleanup_operations_survive_trace_controls(self):
        cleanup = runtime_budget._raise_after_connection_open_cleanup
        source_lines, first_line = inspect.getsourcelines(cleanup)
        self.assertNotIn("release_attempted", "".join(source_lines))
        self.assertNotIn(
            "    finally:\n        try:\n            lease.release()",
            "".join(source_lines),
        )

        def line_for(fragment):
            return next(
                first_line + offset
                for offset, line in enumerate(source_lines)
                if fragment in line
            )

        close_line = line_for("close()")
        connection_line = line_for("if connection is not None")
        release_line = line_for("lease.release()")
        db_config = {
            "dbname": "warehouse_preview",
            "user": "warehouse_reader",
            "password": "",
            "host": "127.0.0.1",
            "port": "5432",
        }

        class FailingAutocommitConnection:
            def __init__(self, close_callback):
                self.close = close_callback

            @property
            def autocommit(self):
                return False

            @autocommit.setter
            def autocommit(self, value):
                raise RuntimeError("PRIVATE autocommit primary")

        for boundary in (
            "before connection branch",
            "before close call",
            "after close before release",
            "before release call",
        ):
            with self.subTest(boundary=boundary):
                events = []
                semaphore = _RecordingSemaphore(events)
                lease = self._acquire_with_fake(
                    _ScriptedClock(events, 10.0, 11.0, 12.0),
                    semaphore,
                    wait=0,
                )
                close_calls = []
                close_completed = []

                def close():
                    close_calls.append(True)
                    close_completed.append(True)

                connection = FailingAutocommitConnection(close)
                interrupted = KeyboardInterrupt(
                    "PRIVATE cleanup boundary",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event != "line"
                        or frame.f_code is not cleanup.__code__
                        or fired
                    ):
                        return trace
                    should_fire = (
                        boundary == "before connection branch"
                        and frame.f_lineno == connection_line
                        or boundary == "before close call"
                        and frame.f_lineno == close_line
                        or boundary == "before release call"
                        and frame.f_lineno == release_line
                        or boundary == "after close before release"
                        and close_completed
                        and frame.f_lineno > close_line
                    )
                    if should_fire:
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runtime_budget.open_warehouse_anomaly_read_connection(
                        db_config,
                        lease,
                        connect=mock.Mock(return_value=connection),
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertIs(captured, interrupted)
                    self.assertEqual(len(close_calls), 1)
                    self.assertEqual(semaphore.releases, 1)
                finally:
                    lease.release()
                self.assertEqual(semaphore.releases, 1)

    def test_read_transaction_happy_path_is_exact_and_guarded(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        signature = inspect.signature(runner)
        self.assertEqual(
            list(signature.parameters), ["connection", "lease", "read"],
        )
        for parameter in signature.parameters.values():
            self.assertEqual(
                parameter.kind, inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            self.assertIs(parameter.default, inspect.Parameter.empty)

        exact_begin = (
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        exact_settings = " ".join(
            """WITH configured AS MATERIALIZED (
                   SELECT pg_catalog.set_config(%s, %s, true)
                              AS statement_timeout,
                          pg_catalog.set_config(%s, %s, true)
                              AS lock_timeout,
                          pg_catalog.set_config(%s, %s, true)
                              AS idle_in_transaction_session_timeout,
                          pg_catalog.set_config(%s, %s, true)
                              AS search_path
                 )
                 SELECT pg_catalog.current_setting(%s)
                            AS statement_timeout,
                        pg_catalog.current_setting(%s)
                            AS lock_timeout,
                        pg_catalog.current_setting(%s)
                            AS idle_in_transaction_session_timeout,
                        pg_catalog.current_setting(%s)
                            AS search_path,
                        pg_catalog.current_setting(%s)
                            AS client_encoding,
                        pg_catalog.current_setting(%s)
                            AS transaction_isolation,
                        pg_catalog.current_setting(%s)
                            AS transaction_read_only
                   FROM configured""".split()
        )
        exact_settings_params = (
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
        settings_row = {
            "statement_timeout": "5s",
            "lock_timeout": "1s",
            "idle_in_transaction_session_timeout": "10s",
            "search_path": "pg_catalog, public",
            "client_encoding": "UTF8",
            "transaction_isolation": "repeatable read",
            "transaction_read_only": "on",
        }
        events = []

        class RawCursor:
            def __init__(self):
                self.calls = []
                self.current = None
                self.close_calls = 0
                self.connection = None
                self.rollback_execute_calls = 0

            def execute(self, sql, params=()):
                normalized = " ".join(str(sql).split())
                parameters = tuple(params or ())
                if normalized == runtime_budget._ROLLBACK_SQL:
                    self.rollback_execute_calls += 1
                    return self.connection.rollback()
                events.append("execute")
                self.calls.append((normalized, parameters))
                if normalized == exact_begin and parameters == ():
                    self.current = None
                    return None
                if (
                    normalized == exact_settings
                    and parameters == exact_settings_params
                ):
                    self.current = [dict(settings_row)]
                    return None
                if normalized == "SELECT %s AS probe" and parameters == (7,):
                    self.current = [{"probe": 7}]
                    return None
                raise AssertionError(
                    "unexpected transaction SQL: " + normalized,
                )

            def fetchall(self):
                events.append("fetchall")
                if self.current is None:
                    raise AssertionError("fetchall without a result")
                return [dict(row) for row in self.current]

            def fetchone(self):
                raise AssertionError("guarded transaction used fetchone")

            def fetchmany(self, *ignored):
                raise AssertionError("guarded transaction used fetchmany")

            def __iter__(self):
                raise AssertionError("guarded transaction iterated raw cursor")

            def close(self):
                events.append("cursor_close")
                self.close_calls += 1

        class Connection:
            def __init__(self, cursor):
                self._autocommit = False
                self.cursor_value = cursor
                self.cursor_calls = []
                self.rollback_calls = 0
                self.close_calls = 0
                self.commit_calls = 0

            def __bool__(self):
                return True

            @property
            def autocommit(self):
                return self._autocommit

            @autocommit.setter
            def autocommit(self, value):
                events.append("autocommit")
                self._autocommit = value

            def cursor(self, **kwargs):
                events.append("cursor")
                self.cursor_calls.append(dict(kwargs))
                return self.cursor_value

            def set_session(self, **kwargs):
                raise AssertionError("transaction must not use set_session")

            def commit(self):
                self.commit_calls += 1
                raise AssertionError("read transaction must never commit")

            def rollback(self):
                events.append("rollback")
                self.rollback_calls += 1

            def close(self):
                events.append("connection_close")
                self.close_calls += 1

        raw_cursor = RawCursor()
        connection = Connection(raw_cursor)
        raw_cursor.connection = connection
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(
            events, *(float(value) for value in range(10, 25)),
        )
        callback_cursors = []

        def connect(**kwargs):
            events.append("connect")
            return connection

        def read(guarded_cursor):
            events.append("read")
            callback_cursors.append(guarded_cursor)
            self.assertEqual({
                name for name in dir(guarded_cursor)
                if not name.startswith("_")
            }, {"execute", "fetchall", "close"})
            execute_signature = inspect.signature(
                type(guarded_cursor).execute,
            )
            self.assertEqual(
                list(execute_signature.parameters),
                ["self", "sql", "params"],
            )
            self.assertEqual(
                execute_signature.parameters["params"].default, (),
            )
            self.assertEqual(
                list(inspect.signature(
                    type(guarded_cursor).fetchall,
                ).parameters),
                ["self"],
            )
            self.assertEqual(
                list(inspect.signature(
                    type(guarded_cursor).close,
                ).parameters),
                ["self"],
            )
            guarded_cursor.execute("SELECT %s AS probe", (7,))
            return guarded_cursor.fetchall()

        lease = self._acquire_with_fake(clock, semaphore, wait=0)
        try:
            opened = runtime_budget.open_warehouse_anomaly_read_connection(
                {
                    "dbname": "warehouse_preview",
                    "user": "warehouse_reader",
                    "password": "",
                    "host": "127.0.0.1",
                    "port": "5432",
                },
                lease,
                connect=connect,
            )
            wrong_cursor = RawCursor()
            wrong_connection = Connection(wrong_cursor)
            wrong_read = mock.Mock(
                side_effect=AssertionError("wrong pair reached callback"),
            )
            _fixed_error(
                self,
                INPUT_INVALID,
                lambda: runner(wrong_connection, lease, wrong_read),
            )
            wrong_read.assert_not_called()
            self.assertEqual(wrong_connection.cursor_calls, [])
            self.assertEqual(wrong_connection.rollback_calls, 0)
            self.assertEqual(wrong_cursor.close_calls, 0)
            self.assertEqual(wrong_connection.close_calls, 0)
            self.assertEqual(connection.cursor_calls, [])
            self.assertEqual(clock.calls, 3)
            self.assertEqual(semaphore.releases, 0)

            result = runner(opened, lease, read)

            self.assertEqual(result, [{"probe": 7}])
            self.assertEqual(len(callback_cursors), 1)
            self.assertIsNot(callback_cursors[0], raw_cursor)
            self.assertEqual(connection.cursor_calls, [{
                "cursor_factory": psycopg2.extras.RealDictCursor,
            }])
            self.assertEqual(raw_cursor.calls, [
                (exact_begin, ()),
                (exact_settings, exact_settings_params),
                ("SELECT %s AS probe", (7,)),
            ])
            self.assertEqual(connection.rollback_calls, 1)
            self.assertEqual(raw_cursor.close_calls, 1)
            self.assertEqual(connection.close_calls, 1)
            self.assertEqual(connection.commit_calls, 0)
            self.assertEqual(clock.calls, 14)
            self.assertEqual(semaphore.releases, 0)
            second_read = mock.Mock(
                side_effect=AssertionError("claimed lifecycle ran twice"),
            )
            _fixed_error(
                self,
                INPUT_INVALID,
                lambda: runner(opened, lease, second_read),
            )
            second_read.assert_not_called()
            self.assertEqual(len(raw_cursor.calls), 3)
            self.assertEqual(connection.rollback_calls, 1)
            self.assertEqual(raw_cursor.close_calls, 1)
            self.assertEqual(connection.close_calls, 1)
            self.assertEqual(clock.calls, 14)
            self.assertEqual(semaphore.releases, 0)
            self.assertEqual(events, [
                "semaphore_acquire", "clock",
                "clock", "connect", "clock", "autocommit",
                "cursor",
                "clock", "execute", "clock",
                "clock", "execute", "clock",
                "clock", "fetchall", "clock",
                "read",
                "clock", "execute", "clock",
                "clock", "fetchall", "clock",
                "rollback", "cursor_close", "connection_close", "clock",
            ])
            self.assertEqual(
                lease.budget,
                runtime_budget.WarehouseAnomalyRuntimeBudget(40.0, 5000),
            )
            events.append("external_finalizer_guard")
            self.assertIsNone(lease.guard())
            self.assertEqual(clock.calls, 15)
            self.assertEqual(
                events[-2:], ["external_finalizer_guard", "clock"],
            )
            self.assertEqual(semaphore.releases, 0)

            module_path = Path(runtime_budget.__file__).resolve()
            root = module_path.parents[3]
            unexpected_callsites = []
            for path in (root / "backend").rglob("*.py"):
                resolved = path.resolve()
                if (
                    resolved in {module_path, Path(__file__).resolve()}
                    or path.name.startswith("test_")
                ):
                    continue
                if (
                    "run_warehouse_anomaly_read_transaction"
                    in path.read_text(encoding="utf-8")
                ):
                    unexpected_callsites.append(str(path.relative_to(root)))
            self.assertEqual(unexpected_callsites, [
                "backend/features/warehouse_recommendation_preview/"
                "runtime_preview.py",
            ])
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_guarded_execute_and_fetchall_pre_post_matrix_is_poisoned(self):
        cases = (
            "pre_deadline",
            "post_deadline",
            "driver_ordinary",
            "driver_control_before_post_control",
            "post_control_after_driver_ordinary",
            "post_control_over_driver_memory",
        )

        for operation in ("execute", "fetchall"):
            for case in cases:
                with self.subTest(operation=operation, case=case):
                    fixture = self._new_guarded_transaction_fixture()
                    first_errors = []
                    driver_error = None
                    post_error = None
                    expected_code = None
                    expected_identity = None

                    if case == "pre_deadline":
                        clock_effects = (40.0,)
                        expected_code = DEADLINE_EXCEEDED
                        driver_effect = AssertionError(
                            "driver ran after pre-operation expiry",
                        )
                    elif case == "post_deadline":
                        clock_effects = (39.999, 40.0)
                        expected_code = DEADLINE_EXCEEDED
                        driver_effect = (
                            [{"payload": object()}]
                            if operation == "fetchall" else object()
                        )
                    elif case == "driver_ordinary":
                        clock_effects = (20.0, 21.0)
                        expected_code = READ_FAILED
                        driver_error = RuntimeError(
                            "PRIVATE guarded driver detail",
                        )
                        driver_effect = driver_error
                    elif case == "driver_control_before_post_control":
                        driver_error = KeyboardInterrupt(
                            "PRIVATE first driver control",
                        )
                        post_error = SystemExit(
                            "PRIVATE later post-guard control",
                        )
                        clock_effects = (20.0, post_error)
                        expected_identity = driver_error
                        driver_effect = driver_error
                    elif case == "post_control_after_driver_ordinary":
                        driver_error = RuntimeError(
                            "PRIVATE earlier ordinary driver",
                        )
                        post_error = GeneratorExit(
                            "PRIVATE later post-guard control",
                        )
                        clock_effects = (20.0, post_error)
                        expected_identity = post_error
                        driver_effect = driver_error
                    else:
                        driver_error = MemoryError(
                            "PRIVATE earlier driver memory",
                        )
                        post_error = SystemExit(
                            "PRIVATE later post-guard control",
                        )
                        clock_effects = (20.0, post_error)
                        expected_identity = post_error
                        driver_effect = driver_error

                    def read(guarded_cursor):
                        if operation == "fetchall":
                            guarded_cursor.execute(
                                "SELECT %s AS bounded_payload", (1,),
                            )
                            fixture.raw_cursor.callback_fetch_effects = [
                                driver_effect,
                            ]
                        else:
                            fixture.raw_cursor.callback_execute_effects = [
                                driver_effect,
                            ]
                        fixture.clock.script(*clock_effects)
                        raw_before = (
                            len(fixture.raw_cursor.execute_calls),
                            fixture.raw_cursor.fetch_calls,
                        )
                        try:
                            if operation == "execute":
                                guarded_cursor.execute(
                                    "SELECT %s AS guarded_probe", (2,),
                                )
                            else:
                                guarded_cursor.fetchall()
                        except BaseException as error:
                            first_errors.append(error)
                        else:
                            raise AssertionError(
                                "guarded operation unexpectedly succeeded",
                            )

                        if case == "pre_deadline":
                            self.assertEqual(
                                (
                                    len(fixture.raw_cursor.execute_calls),
                                    fixture.raw_cursor.fetch_calls,
                                ),
                                raw_before,
                            )
                        clock_after_error = fixture.clock.calls
                        raw_after_error = (
                            len(fixture.raw_cursor.execute_calls),
                            fixture.raw_cursor.fetch_calls,
                        )
                        for retry in (
                            lambda: guarded_cursor.execute(
                                "SELECT %s AS forbidden_retry", (3,),
                            ),
                            guarded_cursor.fetchall,
                        ):
                            try:
                                retry()
                            except BaseException as repeated:
                                self.assertIs(repeated, first_errors[0])
                            else:
                                raise AssertionError(
                                    "poisoned cursor accepted another operation",
                                )
                        self.assertEqual(fixture.clock.calls, clock_after_error)
                        self.assertEqual((
                            len(fixture.raw_cursor.execute_calls),
                            fixture.raw_cursor.fetch_calls,
                        ), raw_after_error)
                        return "caught failure must not become success"

                    captured = None
                    try:
                        try:
                            runtime_budget.run_warehouse_anomaly_read_transaction(
                                fixture.opened, fixture.lease, read,
                            )
                        except BaseException as error:
                            captured = error

                        self.assertEqual(len(first_errors), 1)
                        if expected_identity is not None:
                            self.assertIs(first_errors[0], expected_identity)
                            self.assertIs(captured, expected_identity)
                        else:
                            self.assertIsInstance(captured, ValueError)
                            self.assertEqual(captured.code, expected_code)
                            self.assertEqual(str(captured), expected_code)
                            self.assertIsNone(captured.__cause__)
                            self.assertIsNone(captured.__context__)
                            self.assertIs(captured, first_errors[0])
                            self.assertIsInstance(first_errors[0], ValueError)
                            self.assertEqual(
                                first_errors[0].code, expected_code,
                            )
                            self.assertIsNone(first_errors[0].__cause__)
                            self.assertIsNone(first_errors[0].__context__)
                            self.assertNotIn(
                                "PRIVATE", repr(captured) + repr(vars(captured)),
                            )
                        self.assertEqual(fixture.connection.rollback_calls, 1)
                        self.assertEqual(fixture.raw_cursor.close_calls, 1)
                        self.assertEqual(fixture.connection.close_calls, 1)
                        self.assertEqual(fixture.connection.commit_calls, 0)
                        self.assertEqual(fixture.semaphore.releases, 1)
                    finally:
                        fixture.lease.release()
                    self.assertEqual(fixture.semaphore.releases, 1)

    def test_driver_database_error_cursor_is_sanitized_before_callback(self):
        class CursorBearingDatabaseError(psycopg2.Error):
            @property
            def cursor(self):
                return self.private_cursor

        for operation in ("execute", "fetchall"):
            with self.subTest(operation=operation):
                fixture = self._new_guarded_transaction_fixture()
                dependency_error = CursorBearingDatabaseError(
                    "PRIVATE database detail",
                )
                dependency_error.private_cursor = fixture.raw_cursor
                callback_errors = []

                def read(guarded_cursor):
                    if operation == "fetchall":
                        guarded_cursor.execute(
                            "SELECT %s AS bounded_payload", (1,),
                        )
                        fixture.raw_cursor.callback_fetch_effects = [
                            dependency_error,
                        ]
                        action = guarded_cursor.fetchall
                    else:
                        fixture.raw_cursor.callback_execute_effects = [
                            dependency_error,
                        ]
                        action = lambda: guarded_cursor.execute(
                            "SELECT %s AS bounded_payload", (1,),
                        )
                    try:
                        action()
                    except BaseException as error:
                        callback_errors.append(error)
                    else:
                        raise AssertionError(
                            "dependency driver error did not fail",
                        )
                    self.assertEqual(len(callback_errors), 1)
                    error = callback_errors[0]
                    self.assertIsInstance(error, ValueError)
                    self.assertEqual(error.code, READ_FAILED)
                    self.assertEqual(str(error), READ_FAILED)
                    self.assertIsNone(error.__cause__)
                    self.assertIsNone(error.__context__)
                    self.assertFalse(hasattr(error, "cursor"))
                    self.assertNotIn(
                        "PRIVATE", repr(error) + repr(vars(error)),
                    )
                    for retry in (
                        lambda: guarded_cursor.execute(
                            "SELECT %s AS poisoned_retry", (2,),
                        ),
                        guarded_cursor.fetchall,
                    ):
                        try:
                            retry()
                        except BaseException as repeated:
                            self.assertIs(repeated, error)
                        else:
                            raise AssertionError(
                                "sanitized dependency poison was cleared",
                            )
                    return "caught dependency must not become success"

                try:
                    error = _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        ),
                    )
                    self.assertEqual(callback_errors, [error])
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_guarded_statement_19_is_rejected_before_clock_or_driver(self):
        fixture = self._new_guarded_transaction_fixture()
        callback_errors = []

        def read(guarded_cursor):
            for statement in range(3, 19):
                guarded_cursor.execute(
                    "SELECT %s AS bounded_statement", (statement,),
                )
            self.assertEqual(len(fixture.raw_cursor.execute_calls), 18)
            self.assertEqual(fixture.raw_cursor.fetch_calls, 1)
            fixture.clock.blocked = True
            try:
                guarded_cursor.execute(
                    "SELECT %s AS forbidden_statement", (19,),
                )
            except BaseException as error:
                callback_errors.append(error)
            else:
                raise AssertionError("statement 19 reached the driver")
            self.assertEqual(len(fixture.raw_cursor.execute_calls), 18)
            self.assertEqual(fixture.raw_cursor.fetch_calls, 1)
            clock_at_contract = fixture.clock.calls
            for retry in (
                lambda: guarded_cursor.execute(
                    "SELECT %s AS poisoned_retry", (20,),
                ),
                guarded_cursor.fetchall,
            ):
                try:
                    retry()
                except BaseException as repeated:
                    self.assertIs(repeated, callback_errors[0])
                else:
                    raise AssertionError("statement ceiling poison was cleared")
            self.assertEqual(fixture.clock.calls, clock_at_contract)
            self.assertEqual(len(fixture.raw_cursor.execute_calls), 18)
            self.assertEqual(fixture.raw_cursor.fetch_calls, 1)
            fixture.clock.blocked = False
            return "caught ceiling must not become success"

        try:
            error = _fixed_error(
                self,
                CONTRACT_INVALID,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease, read,
                ),
            )
            self.assertEqual(callback_errors, [error])
            self.assertEqual(fixture.clock.calls, 42)
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.clock.blocked = False
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_callback_close_is_forbidden_and_cannot_erase_cursor_poison(self):
        for prior_driver_error in (False, True):
            with self.subTest(prior_driver_error=prior_driver_error):
                fixture = self._new_guarded_transaction_fixture()
                first_error = []
                close_error = []
                retry_errors = []
                observations = {}

                def read(guarded_cursor):
                    if prior_driver_error:
                        dependency_error = RuntimeError(
                            "PRIVATE dependency cursor detail",
                        )
                        fixture.raw_cursor.callback_execute_effects = [
                            dependency_error,
                        ]
                        try:
                            guarded_cursor.execute(
                                "SELECT %s AS failing_probe", (1,),
                            )
                        except BaseException as error:
                            first_error.append(error)
                    raw_close_before = fixture.raw_cursor.close_calls
                    clock_before = fixture.clock.calls
                    try:
                        guarded_cursor.close()
                    except BaseException as error:
                        close_error.append(error)
                    else:
                        close_error.append(None)
                    observations["raw_close_unchanged"] = (
                        fixture.raw_cursor.close_calls == raw_close_before
                    )
                    observations["clock_unchanged"] = (
                        fixture.clock.calls == clock_before
                    )
                    if not prior_driver_error and close_error[0] is not None:
                        first_error.append(close_error[0])
                    for retry in (
                        lambda: guarded_cursor.execute(
                            "SELECT %s AS forbidden_retry", (2,),
                        ),
                        guarded_cursor.fetchall,
                        guarded_cursor.close,
                    ):
                        try:
                            retry()
                        except BaseException as repeated:
                            retry_errors.append(repeated)
                        else:
                            retry_errors.append(None)
                    observations["completed"] = True
                    return "caught close must not become success"

                try:
                    error = _fixed_error(
                        self,
                        READ_FAILED if prior_driver_error else CONTRACT_INVALID,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        ),
                    )
                    self.assertEqual(observations, {
                        "raw_close_unchanged": True,
                        "clock_unchanged": True,
                        "completed": True,
                    })
                    self.assertEqual(len(first_error), 1)
                    self.assertIs(error, first_error[0])
                    self.assertEqual(len(close_error), 1)
                    self.assertIs(close_error[0], first_error[0])
                    self.assertEqual(len(retry_errors), 3)
                    self.assertTrue(all(
                        repeated is first_error[0]
                        for repeated in retry_errors
                    ))
                    self.assertIsInstance(first_error[0], ValueError)
                    self.assertEqual(
                        first_error[0].code,
                        READ_FAILED if prior_driver_error else CONTRACT_INVALID,
                    )
                    self.assertIsNone(first_error[0].__cause__)
                    self.assertIsNone(first_error[0].__context__)
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_control_before_callback_close_latch_still_poisons_runner(self):
        fixture = self._new_guarded_transaction_fixture()
        close_helper = runtime_budget._forbid_guarded_cursor_close
        source_lines, first_line = inspect.getsourcelines(close_helper)
        latch_line = next(
            first_line + offset
            for offset, line in enumerate(source_lines)
            if "_latch_cursor_error(state, error)" in line
        )
        interrupted = KeyboardInterrupt(
            "PRIVATE control immediately before cursor poison latch",
        )
        callback_errors = []
        fired = []

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code is close_helper.__code__
                and frame.f_lineno == latch_line
                and not fired
            ):
                fired.append(True)
                raise interrupted
            return trace

        def read(guarded_cursor):
            sys.settrace(trace)
            try:
                guarded_cursor.close()
            except BaseException as error:
                callback_errors.append(error)
            finally:
                sys.settrace(None)
            self.assertEqual(callback_errors, [interrupted])
            self.assertEqual(fixture.raw_cursor.close_calls, 0)
            return "caught control must not clear poison"

        captured = None
        try:
            try:
                runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease, read,
                )
            except BaseException as error:
                captured = error
            self.assertEqual(fired, [True])
            self.assertIs(captured, interrupted)
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            sys.settrace(None)
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_fetchall_rejects_raw_cursor_references_and_wrapper_is_terminal(self):
        class RowsSubclass(list):
            pass

        class HidingDict(dict):
            def keys(self):
                return ()

            def values(self):
                return ()

        class Box:
            def __init__(self, value):
                self.value = value

        leak_shapes = (
            "raw_cursor",
            "guarded_cursor",
            "nested_raw_cursor",
            "nested_guarded_cursor",
            "list_subclass",
            "dict_subclass_hiding_raw",
            "opaque_box",
            "weak_reference",
            "weak_proxy",
            "connection",
            "lease",
            "bound_method",
        )
        for shape in leak_shapes:
            with self.subTest(shape=shape):
                fixture = self._new_guarded_transaction_fixture()

                def read(guarded_cursor):
                    guarded_cursor.execute(
                        "SELECT %s AS bounded_payload", (1,),
                    )
                    leaks = {
                        "raw_cursor": fixture.raw_cursor,
                        "guarded_cursor": guarded_cursor,
                        "nested_raw_cursor": [{
                            "payload": fixture.raw_cursor,
                        }],
                        "nested_guarded_cursor": [{
                            "payload": [guarded_cursor],
                        }],
                        "list_subclass": RowsSubclass([
                            fixture.raw_cursor,
                        ]),
                        "dict_subclass_hiding_raw": HidingDict({
                            "payload": fixture.raw_cursor,
                        }),
                        "opaque_box": Box(fixture.raw_cursor),
                        "weak_reference": weakref.ref(
                            fixture.raw_cursor,
                        ),
                        "weak_proxy": weakref.proxy(fixture.raw_cursor),
                        "connection": fixture.connection,
                        "lease": fixture.lease,
                        "bound_method": fixture.raw_cursor.close,
                    }
                    fixture.raw_cursor.callback_fetch_effects = [leaks[shape]]
                    return guarded_cursor.fetchall()

                try:
                    _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        ),
                    )
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

        fixture = self._new_guarded_transaction_fixture()
        returned_wrapper = None
        try:
            returned_wrapper = (
                runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease,
                    lambda guarded_cursor: guarded_cursor,
                )
            )
            clock_after_return = fixture.clock.calls
            driver_after_return = (
                len(fixture.raw_cursor.execute_calls),
                fixture.raw_cursor.fetch_calls,
                fixture.raw_cursor.close_calls,
            )
            for late_operation in (
                lambda: returned_wrapper.execute(
                    "SELECT %s AS escaped", (1,),
                ),
                returned_wrapper.fetchall,
                returned_wrapper.close,
            ):
                _fixed_error(self, INPUT_INVALID, late_operation)
            self.assertEqual(fixture.clock.calls, clock_after_return)
            self.assertEqual((
                len(fixture.raw_cursor.execute_calls),
                fixture.raw_cursor.fetch_calls,
                fixture.raw_cursor.close_calls,
            ), driver_after_return)
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 0)
        finally:
            fixture.lease.release()
        self.assertIsNotNone(returned_wrapper)
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_unbound_none_connection_cannot_claim_or_release_the_holder(self):
        events = []
        semaphore = _RecordingSemaphore(events)
        clock = _ScriptedClock(events, 10.0, 11.0)
        lease = self._acquire_with_fake(clock, semaphore, wait=0)
        read = mock.Mock(
            side_effect=AssertionError("unbound None reached callback"),
        )
        try:
            _fixed_error(
                self,
                INPUT_INVALID,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    None, lease, read,
                ),
            )
            read.assert_not_called()
            self.assertEqual(clock.calls, 1)
            self.assertEqual(semaphore.releases, 0)
            self.assertIsNone(lease.guard())
            self.assertEqual(clock.calls, 2)
            self.assertEqual(semaphore.releases, 0)
        finally:
            lease.release()
        self.assertEqual(semaphore.releases, 1)

    def test_bound_connection_close_is_captured_before_early_validation(self):
        cases = (
            "read_not_callable",
            "autocommit_getter",
            "cursor_descriptor",
            "falsey_bound_connection",
        )
        for case in cases:
            with self.subTest(case=case):
                fixture = self._new_guarded_transaction_fixture()
                read = mock.Mock(return_value="must not run")
                expected_code = READ_FAILED

                if case == "read_not_callable":
                    callback = None
                    expected_code = INPUT_INVALID
                else:
                    callback = read
                if case == "autocommit_getter":
                    def fail_autocommit_getter(ignored):
                        raise RuntimeError("PRIVATE autocommit descriptor")

                    type(fixture.connection).autocommit = property(
                        fail_autocommit_getter,
                    )
                elif case == "cursor_descriptor":
                    def fail_cursor_descriptor(ignored):
                        raise RuntimeError("PRIVATE cursor descriptor")

                    type(fixture.connection).cursor = property(
                        fail_cursor_descriptor,
                    )
                elif case == "falsey_bound_connection":
                    type(fixture.connection).__bool__ = lambda ignored: False

                try:
                    _fixed_error(
                        self,
                        expected_code,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, callback,
                        ),
                    )
                    if callback is not None:
                        read.assert_not_called()
                    self.assertEqual(fixture.connection.cursor_calls, [])
                    self.assertEqual(fixture.raw_cursor.execute_calls, [])
                    self.assertEqual(fixture.connection.rollback_calls, 0)
                    self.assertEqual(fixture.raw_cursor.close_calls, 0)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_falsey_and_malformed_cursor_resources_fail_closed_but_cleanup(self):
        cases = (
            "falsey_valid",
            "none",
            "missing_close",
            "noncallable_close",
            "missing_execute",
            "noncallable_execute",
            "missing_fetchall",
            "noncallable_fetchall",
        )
        for case in cases:
            with self.subTest(case=case):
                fixture = self._new_guarded_transaction_fixture()
                close = mock.Mock()
                if case == "falsey_valid":
                    fixture.raw_cursor.falsey = True
                    returned_cursor = fixture.raw_cursor
                    expected_cursor_closes = 1
                elif case == "none":
                    returned_cursor = None
                    expected_cursor_closes = 0
                elif case == "missing_close":
                    returned_cursor = SimpleNamespace(
                        execute=mock.Mock(), fetchall=mock.Mock(),
                    )
                    expected_cursor_closes = 0
                elif case == "noncallable_close":
                    returned_cursor = SimpleNamespace(
                        execute=mock.Mock(), fetchall=mock.Mock(), close=None,
                    )
                    expected_cursor_closes = 0
                elif case == "missing_execute":
                    returned_cursor = SimpleNamespace(
                        fetchall=mock.Mock(), close=close,
                    )
                    expected_cursor_closes = 1
                elif case == "noncallable_execute":
                    returned_cursor = SimpleNamespace(
                        execute=None, fetchall=mock.Mock(), close=close,
                    )
                    expected_cursor_closes = 1
                elif case == "missing_fetchall":
                    returned_cursor = SimpleNamespace(
                        execute=mock.Mock(), close=close,
                    )
                    expected_cursor_closes = 1
                else:
                    returned_cursor = SimpleNamespace(
                        execute=mock.Mock(), fetchall=None, close=close,
                    )
                    expected_cursor_closes = 1
                fixture.connection.raw_cursor = returned_cursor
                read = mock.Mock(
                    side_effect=AssertionError(
                        "malformed cursor reached callback",
                    ),
                )

                try:
                    _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        ),
                    )
                    read.assert_not_called()
                    self.assertEqual(fixture.connection.rollback_calls, 0)
                    if case == "falsey_valid":
                        self.assertEqual(
                            fixture.raw_cursor.close_calls,
                            expected_cursor_closes,
                        )
                        self.assertEqual(fixture.raw_cursor.execute_calls, [])
                    else:
                        self.assertEqual(
                            close.call_count, expected_cursor_closes,
                        )
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_begin_attempt_ledger_distinguishes_preguard_from_driver(self):
        fixture = self._new_guarded_transaction_fixture()
        fixture.clock.script(40.0, 40.0)
        try:
            _fixed_error(
                self,
                DEADLINE_EXCEEDED,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease,
                    mock.Mock(side_effect=AssertionError("expired callback")),
                ),
            )
            self.assertEqual(fixture.raw_cursor.execute_calls, [])
            self.assertEqual(fixture.connection.rollback_calls, 0)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()

        for driver_kind in ("ordinary", "control"):
            with self.subTest(begin_driver=driver_kind):
                fixture = self._new_guarded_transaction_fixture()
                original_execute = fixture.raw_cursor.execute
                driver_error = (
                    RuntimeError("PRIVATE begin driver")
                    if driver_kind == "ordinary"
                    else KeyboardInterrupt("PRIVATE begin driver control")
                )

                def fail_begin(sql, params=()):
                    result = original_execute(sql, params)
                    if sql == runtime_budget._BEGIN_SQL:
                        raise driver_error
                    return result

                fixture.raw_cursor.execute = fail_begin
                captured = None
                try:
                    try:
                        runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened,
                            fixture.lease,
                            mock.Mock(
                                side_effect=AssertionError("failed BEGIN callback"),
                            ),
                        )
                    except BaseException as error:
                        captured = error
                    if driver_kind == "ordinary":
                        self.assertIsInstance(captured, ValueError)
                        self.assertEqual(captured.code, READ_FAILED)
                        self.assertEqual(str(captured), READ_FAILED)
                        self.assertIsNone(captured.__cause__)
                        self.assertIsNone(captured.__context__)
                    else:
                        self.assertIs(captured, driver_error)
                    self.assertEqual(
                        len(fixture.raw_cursor.execute_calls), 1,
                    )
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_settings_result_requires_the_exact_single_canonical_row(self):
        class TextSubclass(str):
            pass

        canonical = {
            "statement_timeout": "5s",
            "lock_timeout": "1s",
            "idle_in_transaction_session_timeout": "10s",
            "search_path": "pg_catalog, public",
            "client_encoding": "UTF8",
            "transaction_isolation": "repeatable read",
            "transaction_read_only": "on",
        }
        malformed = {
            "none": None,
            "tuple_outer": (dict(canonical),),
            "list_subclass": type("Rows", (list,), {})((dict(canonical),)),
            "empty": [],
            "two_rows": [dict(canonical), dict(canonical)],
            "row_not_mapping": [tuple(canonical.items())],
            "missing_key": [{
                key: value for key, value in canonical.items()
                if key != "client_encoding"
            }],
            "extra_key": [{**canonical, "server_encoding": "UTF8"}],
            "non_string_value": [{**canonical, "statement_timeout": 5}],
            "string_subclass": [{
                **canonical,
                "statement_timeout": TextSubclass("5s"),
            }],
        }
        for key in canonical:
            malformed["wrong_" + key] = [{
                **canonical,
                key: "PRIVATE wrong setting",
            }]

        for name, rows in malformed.items():
            with self.subTest(malformed_settings=name):
                fixture = self._new_guarded_transaction_fixture()
                fixture.raw_cursor.settings_rows = rows
                read = mock.Mock(
                    side_effect=AssertionError(
                        "malformed settings reached callback",
                    ),
                )
                try:
                    _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        ),
                    )
                    read.assert_not_called()
                    self.assertEqual(
                        len(fixture.raw_cursor.execute_calls), 2,
                    )
                    self.assertEqual(fixture.raw_cursor.fetch_calls, 1)
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

        fixture = self._new_guarded_transaction_fixture()
        fixture.raw_cursor.settings_rows = [
            psycopg2.extras.RealDictRow(canonical),
        ]
        try:
            result = runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened,
                fixture.lease,
                lambda ignored: "canonical settings accepted",
            )
            self.assertEqual(result, "canonical settings accepted")
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 0)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_cleanup_retains_every_error_and_applies_exact_precedence(self):
        cases = (
            "later_connection_control",
            "first_primary_control",
            "fixed_rollback",
            "fixed_cleanup",
            "read_precedes_cleanup",
            "cleanup_precedes_postcleanup_deadline",
            "postcleanup_deadline_alone",
            "release_control_identity",
        )
        for case in cases:
            with self.subTest(case=case):
                fixture = self._new_guarded_transaction_fixture()
                primary = None
                rollback_error = None
                cursor_close_error = None
                connection_close_error = None
                expected_identity = None
                expected_code = None
                postcleanup_deadline = False
                release_error = None

                if case == "later_connection_control":
                    primary = RuntimeError("PRIVATE callback ordinary")
                    rollback_error = RuntimeError("PRIVATE rollback ordinary")
                    cursor_close_error = RuntimeError(
                        "PRIVATE cursor close ordinary",
                    )
                    connection_close_error = SystemExit(
                        "PRIVATE later connection close control",
                    )
                    expected_identity = connection_close_error
                elif case == "first_primary_control":
                    primary = KeyboardInterrupt(
                        "PRIVATE first callback control",
                    )
                    rollback_error = SystemExit(
                        "PRIVATE later rollback control",
                    )
                    cursor_close_error = GeneratorExit(
                        "PRIVATE later cursor close control",
                    )
                    connection_close_error = MemoryError(
                        "PRIVATE later connection close memory",
                    )
                    expected_identity = primary
                elif case == "fixed_rollback":
                    primary = RuntimeError("PRIVATE callback ordinary")
                    rollback_error = RuntimeError("PRIVATE rollback ordinary")
                    expected_code = ROLLBACK_FAILED
                elif case == "fixed_cleanup":
                    cursor_close_error = RuntimeError(
                        "PRIVATE cursor close ordinary",
                    )
                    connection_close_error = RuntimeError(
                        "PRIVATE connection close ordinary",
                    )
                    expected_code = CLEANUP_FAILED
                elif case == "read_precedes_cleanup":
                    primary = RuntimeError("PRIVATE callback ordinary")
                    cursor_close_error = RuntimeError(
                        "PRIVATE cursor close ordinary",
                    )
                    expected_code = READ_FAILED
                elif case == "cleanup_precedes_postcleanup_deadline":
                    cursor_close_error = RuntimeError(
                        "PRIVATE cursor close ordinary",
                    )
                    postcleanup_deadline = True
                    expected_code = CLEANUP_FAILED
                elif case == "postcleanup_deadline_alone":
                    postcleanup_deadline = True
                    expected_code = DEADLINE_EXCEEDED
                else:
                    primary = RuntimeError("PRIVATE callback ordinary")
                    release_error = SystemExit(
                        "PRIVATE release control",
                    )
                    expected_identity = release_error

                original_rollback = fixture.connection.rollback
                original_cursor_close = fixture.raw_cursor.close

                def rollback():
                    original_rollback()
                    if rollback_error is not None:
                        raise rollback_error

                def cursor_close():
                    original_cursor_close()
                    if cursor_close_error is not None:
                        raise cursor_close_error

                fixture.connection.rollback = rollback
                fixture.raw_cursor.close = cursor_close
                fixture.connection.close_after_error = connection_close_error
                original_release = fixture.semaphore.release

                def release():
                    original_release()
                    if release_error is not None:
                        raise release_error

                fixture.semaphore.release = release

                def read(ignored):
                    if postcleanup_deadline:
                        fixture.clock.script(40.0)
                    if primary is not None:
                        raise primary
                    return "cleanup decides outcome"

                captured = None
                try:
                    try:
                        runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        )
                    except BaseException as error:
                        captured = error
                    if expected_identity is not None:
                        self.assertIs(captured, expected_identity)
                    else:
                        self.assertIsInstance(captured, ValueError)
                        self.assertEqual(captured.code, expected_code)
                        self.assertEqual(str(captured), expected_code)
                        self.assertEqual(captured.args, (expected_code,))
                        self.assertIsNone(captured.__cause__)
                        self.assertIsNone(captured.__context__)
                        self.assertNotIn(
                            "PRIVATE", repr(captured) + repr(vars(captured)),
                        )
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_b2_bound_connection_close_survives_b3_descriptor_drift(self):
        for drift in ("raises", "replacement"):
            with self.subTest(drift=drift):
                fixture = self._new_guarded_transaction_fixture()
                original_close = fixture.connection.close
                descriptor_reads = []
                replacement_close = mock.Mock()

                def changed_close(ignored):
                    descriptor_reads.append(True)
                    if drift == "raises":
                        raise RuntimeError("PRIVATE changed close descriptor")
                    return replacement_close

                type(fixture.connection).close = property(changed_close)
                captured = None
                result = None
                try:
                    try:
                        result = (
                            runtime_budget.run_warehouse_anomaly_read_transaction(
                                fixture.opened,
                                fixture.lease,
                                lambda ignored: "stable bound close",
                            )
                        )
                    except BaseException as error:
                        captured = error
                    self.assertIsNone(captured)
                    self.assertEqual(result, "stable bound close")
                    self.assertEqual(descriptor_reads, [])
                    replacement_close.assert_not_called()
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 0)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)
                self.assertTrue(callable(original_close))

    def test_claimed_lease_refuses_public_release_without_losing_cleanup(self):
        for phase in ("bound_connection", "active_transaction"):
            with self.subTest(phase=phase):
                fixture = self._new_guarded_transaction_fixture()
                release_errors = []

                def attempt_release():
                    try:
                        fixture.lease.release()
                    except BaseException as error:
                        release_errors.append(error)
                    else:
                        release_errors.append(None)

                def read(ignored):
                    if phase == "active_transaction":
                        attempt_release()
                    return "lease stayed owned"

                if phase == "bound_connection":
                    attempt_release()
                result = None
                runner_error = None
                try:
                    result = (
                        runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened, fixture.lease, read,
                        )
                    )
                except BaseException as error:
                    runner_error = error
                try:
                    self.assertEqual(len(release_errors), 1)
                    self.assertIsInstance(release_errors[0], ValueError)
                    self.assertEqual(release_errors[0].code, INPUT_INVALID)
                    self.assertIsNone(release_errors[0].__cause__)
                    self.assertIsNone(release_errors[0].__context__)
                    self.assertIsNone(runner_error)
                    self.assertEqual(result, "lease stayed owned")
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 0)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_sanitized_driver_error_traceback_retains_no_dependency_handle(self):
        fixture = self._new_guarded_transaction_fixture()
        dependency_error = RuntimeError("PRIVATE dependency traceback")
        dependency_error.cursor = fixture.raw_cursor
        callback_errors = []
        exposed = []

        def read(guarded_cursor):
            fixture.raw_cursor.callback_execute_effects = [dependency_error]
            try:
                guarded_cursor.execute(
                    "SELECT %s AS failing_probe", (1,),
                )
            except BaseException as error:
                callback_errors.append(error)
                traceback = error.__traceback__
                while traceback is not None:
                    if (
                        traceback.tb_frame.f_globals.get("__name__")
                        != runtime_budget.__name__
                    ):
                        traceback = traceback.tb_next
                        continue
                    for name, value in traceback.tb_frame.f_locals.items():
                        if (
                            value is fixture.raw_cursor
                            or value is dependency_error
                            or type(value).__name__ == "_GuardedCursorState"
                            or getattr(value, "__self__", None)
                            is fixture.raw_cursor
                        ):
                            exposed.append((
                                traceback.tb_frame.f_code.co_name, name,
                            ))
                    traceback = traceback.tb_next
            return "caught sanitized dependency failure"

        try:
            error = _fixed_error(
                self,
                READ_FAILED,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease, read,
                ),
            )
            self.assertEqual(len(callback_errors), 1)
            self.assertIs(error, callback_errors[0])
            self.assertEqual(exposed, [])
            self.assertNotIn("cursor", vars(error))
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_forbidden_close_error_traceback_exposes_no_raw_cursor_state(self):
        fixture = self._new_guarded_transaction_fixture()
        exposed = []

        def read(guarded_cursor):
            try:
                guarded_cursor.close()
            except BaseException as error:
                traceback = error.__traceback__
                while traceback is not None:
                    if (
                        traceback.tb_frame.f_globals.get("__name__")
                        == runtime_budget.__name__
                    ):
                        for name, value in traceback.tb_frame.f_locals.items():
                            if (
                                value is fixture.raw_cursor
                                or type(value).__name__
                                == "_GuardedCursorState"
                                or getattr(value, "__self__", None)
                                is fixture.raw_cursor
                            ):
                                exposed.append((
                                    traceback.tb_frame.f_code.co_name,
                                    name,
                                ))
                    traceback = traceback.tb_next
            return "caught forbidden close must not become success"

        try:
            _fixed_error(
                self,
                CONTRACT_INVALID,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease, read,
                ),
            )
            self.assertEqual(exposed, [])
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_closed_fetch_result_is_detached_before_callback_can_mutate_raw(self):
        fixture = self._new_guarded_transaction_fixture()
        raw_nested = ["bounded"]
        raw_row = {"payload": raw_nested}
        raw_result = [raw_row]
        callback_result = []

        def read(guarded_cursor):
            guarded_cursor.execute("SELECT %s AS payload", (1,))
            fixture.raw_cursor.callback_fetch_effects = [raw_result]
            sanitized = guarded_cursor.fetchall()
            callback_result.append(sanitized)
            raw_nested[0] = fixture.raw_cursor
            raw_row["late"] = fixture.connection
            raw_result.append(fixture.lease)
            return sanitized

        try:
            result = runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened, fixture.lease, read,
            )
            self.assertEqual(result, [{"payload": ["bounded"]}])
            self.assertIs(result, callback_result[0])
            self.assertIsNot(result, raw_result)
            self.assertIsNot(result[0], raw_row)
            self.assertIsNot(result[0]["payload"], raw_nested)
            self.assertEqual(fixture.connection.rollback_calls, 1)
            self.assertEqual(fixture.raw_cursor.close_calls, 1)
            self.assertEqual(fixture.connection.close_calls, 1)
            self.assertEqual(fixture.semaphore.releases, 0)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_claim_and_cursor_factory_return_boundaries_recover_cleanup(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        start = runtime_budget._start_transaction_lifecycle
        claim = runtime_budget._claim_transaction_pair
        cases = (
            (
                "claim before token write",
                claim,
                self._source_line(
                    claim, "state.transaction_token = transaction_token",
                ),
                0,
            ),
            (
                "claim after token write",
                claim,
                self._source_line(claim, "return True"),
                0,
            ),
            (
                "claim helper returned",
                start,
                self._source_line(
                    start,
                    "lifecycle.connection_close = lifecycle.connection_close",
                ),
                0,
            ),
            (
                "cursor factory returned",
                start,
                self._source_line(start, "if lifecycle.raw_cursor is None"),
                1,
            ),
        )
        for name, target, target_line, expected_cursor_close in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                interrupted = KeyboardInterrupt(
                    "PRIVATE transaction acquisition boundary",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is target.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runner(
                        fixture.opened,
                        fixture.lease,
                        mock.Mock(
                            side_effect=AssertionError(
                                "boundary reached callback",
                            ),
                        ),
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(fixture.raw_cursor.execute_calls, [])
                    self.assertEqual(fixture.connection.rollback_calls, 0)
                    self.assertEqual(
                        fixture.raw_cursor.close_attempts,
                        expected_cursor_close,
                    )
                    self.assertEqual(
                        fixture.raw_cursor.close_calls,
                        expected_cursor_close,
                    )
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_begin_trace_boundaries_preserve_exact_rollback_ledger(self):
        guarded_execute = runtime_budget._guarded_execute
        cases = (
            (
                "before begin flag",
                self._source_line(
                    guarded_execute, "state.begin_attempted = True",
                ),
                0,
                0,
            ),
            (
                "after begin flag",
                self._source_line(guarded_execute, "driver_error = None"),
                0,
                1,
            ),
            (
                "after begin driver return",
                self._source_line(
                    guarded_execute, "post_guard_error = None",
                ),
                1,
                1,
            ),
        )
        for name, target_line, expected_execute, expected_rollback in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                interrupted = GeneratorExit(
                    "PRIVATE BEGIN ownership boundary",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is guarded_execute.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runtime_budget.run_warehouse_anomaly_read_transaction(
                        fixture.opened,
                        fixture.lease,
                        mock.Mock(
                            side_effect=AssertionError(
                                "BEGIN boundary reached callback",
                            ),
                        ),
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(
                        len(fixture.raw_cursor.execute_calls),
                        expected_execute,
                    )
                    self.assertEqual(
                        fixture.connection.rollback_attempts,
                        expected_rollback,
                    )
                    self.assertEqual(
                        fixture.connection.rollback_calls,
                        expected_rollback,
                    )
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_transaction_phase_dispatch_controls_cannot_skip_later_cleanup(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        finish = runtime_budget._finish_transaction_lifecycle
        finalize = runtime_budget._finalize_transaction_lifecycle
        cases = (
            ("after main body", finish, "if not lifecycle.pair_owned:"),
            (
                "before terminalize", finish,
                "lifecycle.guarded_cursor is not None",
            ),
            (
                "before rollback", finish,
                "if lifecycle.ledger.begin_attempted",
            ),
            (
                "before cursor close", finish,
                "if lifecycle.raw_cursor is not None",
            ),
            (
                "before connection close", finish,
                "if not lifecycle.connection_close_attempted",
            ),
            (
                "before failure calculation", finalize,
                "outcome_error = _transaction_outcome_error",
            ),
            (
                "before failure dispatch", finalize,
                "if outcome_error is not None",
            ),
        )
        for name, target, fragment in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                target_line = self._source_line(
                    target, fragment,
                )
                interrupted = KeyboardInterrupt(
                    "PRIVATE transaction phase dispatch",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is target.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runner(
                        fixture.opened,
                        fixture.lease,
                        lambda ignored: "phase dispatch",
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(fixture.connection.rollback_attempts, 1)
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_terminalizer_boundaries_recover_snapshot_and_seal_wrapper(self):
        terminalize = runtime_budget._terminalize_guarded_cursor
        boundaries = (
            ("before snapshot", "snapshot = ("),
            (
                "before inactive replacement",
                "_CURSOR_STATES[guarded_cursor] = _GuardedCursorState(",
            ),
            ("after inactive replacement", "return snapshot"),
        )
        for name, fragment in boundaries:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                target_line = self._source_line(terminalize, fragment)
                interrupted = SystemExit(
                    "PRIVATE cursor terminalization boundary",
                )
                fired = []
                wrappers = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is terminalize.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                def read(guarded_cursor):
                    wrappers.append(guarded_cursor)
                    return "terminalize me"

                captured = None
                sys.settrace(trace)
                try:
                    runtime_budget.run_warehouse_anomaly_read_transaction(
                        fixture.opened, fixture.lease, read,
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(len(wrappers), 1)
                    runtime_budget._registered_cursor_state(
                        wrappers[0], active=False,
                    )
                    self.assertEqual(fixture.connection.rollback_attempts, 1)
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                    clock_after = fixture.clock.calls
                    raw_after = (
                        len(fixture.raw_cursor.execute_calls),
                        fixture.raw_cursor.fetch_calls,
                        fixture.raw_cursor.close_attempts,
                    )
                    for operation in (
                        lambda: wrappers[0].execute(
                            "SELECT %s AS escaped", (1,),
                        ),
                        wrappers[0].fetchall,
                        wrappers[0].close,
                    ):
                        _fixed_error(self, INPUT_INVALID, operation)
                    self.assertEqual(fixture.clock.calls, clock_after)
                    self.assertEqual((
                        len(fixture.raw_cursor.execute_calls),
                        fixture.raw_cursor.fetch_calls,
                        fixture.raw_cursor.close_attempts,
                    ), raw_after)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

        fixture = self._new_guarded_transaction_fixture()
        target_line = self._source_line(terminalize, "return snapshot")
        ordinary = RuntimeError("PRIVATE ordinary callback first")
        terminal_control = KeyboardInterrupt(
            "PRIVATE terminalizer control after ordinary callback",
        )
        fired = []

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code is terminalize.__code__
                and frame.f_lineno == target_line
                and not fired
            ):
                fired.append(True)
                raise terminal_control
            return trace

        captured = None
        sys.settrace(trace)
        try:
            runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened,
                fixture.lease,
                mock.Mock(side_effect=ordinary),
            )
        except BaseException as error:
            captured = error
        finally:
            sys.settrace(None)
        try:
            self.assertEqual(fired, [True])
            self.assertIs(captured, terminal_control)
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_each_physical_cleanup_is_attempted_once_at_both_effect_sides(self):
        for operation in ("rollback", "cursor_close", "connection_close"):
            for timing in ("before", "after"):
                with self.subTest(operation=operation, timing=timing):
                    fixture = self._new_guarded_transaction_fixture()
                    interrupted = KeyboardInterrupt(
                        "PRIVATE one-shot physical cleanup",
                    )
                    if operation == "rollback":
                        setattr(
                            fixture.connection,
                            "rollback_" + timing + "_error",
                            interrupted,
                        )
                    elif operation == "cursor_close":
                        setattr(
                            fixture.raw_cursor,
                            "close_" + timing + "_error",
                            interrupted,
                        )
                    else:
                        setattr(
                            fixture.connection,
                            "close_" + timing + "_error",
                            interrupted,
                        )

                    captured = None
                    try:
                        runtime_budget.run_warehouse_anomaly_read_transaction(
                            fixture.opened,
                            fixture.lease,
                            lambda ignored: "cleanup boundary",
                        )
                    except BaseException as error:
                        captured = error
                    try:
                        self.assertIs(captured, interrupted)
                        self.assertEqual(
                            fixture.connection.rollback_attempts, 1,
                        )
                        self.assertEqual(
                            fixture.raw_cursor.close_attempts, 1,
                        )
                        self.assertEqual(
                            fixture.connection.close_attempts, 1,
                        )
                        expected_completion = 0 if timing == "before" else 1
                        self.assertEqual(
                            fixture.connection.rollback_calls,
                            expected_completion
                            if operation == "rollback" else 1,
                        )
                        self.assertEqual(
                            fixture.raw_cursor.close_calls,
                            expected_completion
                            if operation == "cursor_close" else 1,
                        )
                        self.assertEqual(
                            fixture.connection.close_calls,
                            expected_completion
                            if operation == "connection_close" else 1,
                        )
                        self.assertEqual(fixture.semaphore.releases, 1)
                    finally:
                        fixture.lease.release()
                    self.assertEqual(fixture.semaphore.releases, 1)

        fixture = self._new_guarded_transaction_fixture()
        first = KeyboardInterrupt("PRIVATE first cleanup control")
        later = SystemExit("PRIVATE later cleanup control")
        fixture.connection.rollback_after_error = first
        fixture.connection.close_after_error = later
        captured = None
        try:
            runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened,
                fixture.lease,
                lambda ignored: "two cleanup controls",
            )
        except BaseException as error:
            captured = error
        try:
            self.assertIs(captured, first)
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_binding_clear_boundaries_finish_cleanup_then_release(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        complete = runtime_budget._complete_transaction_claim
        finish = runtime_budget._finish_transaction_lifecycle
        cases = (
            (
                "before connection clear",
                complete,
                self._source_line(complete, "state.connection = None"),
            ),
            (
                "after connection clear",
                complete,
                self._source_line(
                    complete,
                    "state.transaction_token = _TRANSACTION_COMPLETE",
                ),
            ),
            (
                "claim helper returned before postcleanup guard",
                finish,
                self._source_line(
                    finish,
                    "lifecycle.post_guard_attempted = True; lifecycle.lease.guard()",
                ),
            ),
        )
        for name, target, target_line in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                interrupted = GeneratorExit(
                    "PRIVATE binding handoff boundary",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is target.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runner(
                        fixture.opened,
                        fixture.lease,
                        lambda ignored: "binding boundary",
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(fixture.connection.rollback_attempts, 1)
                    self.assertEqual(fixture.connection.rollback_calls, 1)
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_calls, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_calls, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_failure_release_and_success_return_boundaries_are_one_shot(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        internal = runtime_budget._run_warehouse_anomaly_read_transaction
        finish = runtime_budget._finish_transaction_lifecycle
        finalize = runtime_budget._finalize_transaction_lifecycle
        release_line = self._source_line(
            finalize,
            "lifecycle.lease.release()",
        )
        outcome_line = self._source_line(
            finalize,
            "outcome_error = _transaction_outcome_error",
            occurrence=1,
        )
        postguard_line = self._source_line(
            finish,
            "lifecycle.post_guard_attempted = True; lifecycle.lease.guard()",
        )
        return_line = self._source_line(internal, "return outcome")
        prior_control = KeyboardInterrupt(
            "PRIVATE first callback control",
        )
        cases = (
            (
                "ordinary primary before release",
                finalize,
                release_line,
                RuntimeError("PRIVATE ordinary callback"),
                SystemExit("PRIVATE release boundary"),
                None,
            ),
            (
                "first control survives release boundary",
                finalize,
                release_line,
                prior_control,
                SystemExit("PRIVATE later release control"),
                prior_control,
            ),
            (
                "after physical release",
                finalize,
                outcome_line,
                RuntimeError("PRIVATE ordinary callback"),
                GeneratorExit("PRIVATE after physical release"),
                None,
            ),
            (
                "successful postcleanup guard",
                finish,
                postguard_line,
                None,
                KeyboardInterrupt("PRIVATE postcleanup handoff"),
                None,
            ),
            (
                "successful return",
                internal,
                return_line,
                None,
                SystemExit("PRIVATE successful return boundary"),
                None,
            ),
        )
        for (
            name, target, target_line, primary, boundary_error, preserved,
        ) in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                fired = []
                delivered = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is target.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise boundary_error
                    return trace

                def read(ignored):
                    if primary is not None:
                        raise primary
                    return "must not be delivered"

                captured = None
                sys.settrace(trace)
                try:
                    delivered.append(
                        runner(fixture.opened, fixture.lease, read),
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertEqual(delivered, [])
                    self.assertIs(
                        captured,
                        preserved if preserved is not None else boundary_error,
                    )
                    self.assertEqual(fixture.connection.rollback_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_closed_fetch_graph_rejects_cycles_and_shared_container_aliases(self):
        validator = runtime_budget._validated_closed_fetch_result
        cycle = []
        cycle.append(cycle)
        shared = ["bounded"]
        for name, result in (
            ("self_reference", cycle),
            ("shared_container_alias", [shared, shared]),
        ):
            with self.subTest(shape=name):
                line_events = []

                def trace(frame, event, arg):
                    if event == "line" and frame.f_code is validator.__code__:
                        line_events.append(frame.f_lineno)
                        if len(line_events) > 200:
                            raise AssertionError(
                                "closed-result validation did not terminate",
                            )
                    return trace

                sys.settrace(trace)
                try:
                    _fixed_error(
                        self,
                        READ_FAILED,
                        lambda: validator(result),
                    )
                finally:
                    sys.settrace(None)
                self.assertLessEqual(len(line_events), 200)

    def test_realdictrow_instance_state_cannot_hide_a_raw_cursor(self):
        fixture = self._new_guarded_transaction_fixture()
        row = psycopg2.extras.RealDictRow({"payload": "bounded"})
        row.__dict__["cursor"] = fixture.raw_cursor

        def read(guarded_cursor):
            guarded_cursor.execute(
                "SELECT %s AS bounded_payload", (1,),
            )
            fixture.raw_cursor.callback_fetch_effects = [[row]]
            return guarded_cursor.fetchall()

        try:
            _fixed_error(
                self,
                READ_FAILED,
                lambda: runtime_budget.run_warehouse_anomaly_read_transaction(
                    fixture.opened, fixture.lease, read,
                ),
            )
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_every_actual_transaction_handoff_finishes_owned_cleanup(self):
        runner = runtime_budget.run_warehouse_anomaly_read_transaction
        internal = runtime_budget._run_warehouse_anomaly_read_transaction
        finish = runtime_budget._finish_transaction_lifecycle
        finalize = runtime_budget._finalize_transaction_lifecycle
        cases = (
            ("pair recovery", finish, "if not lifecycle.pair_owned:"),
            (
                "connection close recovery", finish,
                "if lifecycle.connection_close is None",
            ),
            (
                "terminal snapshot handoff", finish,
                "lifecycle.terminal_snapshot = _terminalize_guarded_cursor",
            ),
            (
                "begin ledger handoff", finish,
                "if lifecycle.ledger.begin_attempted",
            ),
            (
                "rollback physical dispatch", finish,
                "lifecycle.rollback_attempted = True; "
                "lifecycle.raw_cursor_execute(",
            ),
            (
                "cursor cleanup ledger", finish,
                "if lifecycle.raw_cursor is not None",
            ),
            (
                "cursor close physical dispatch", finish,
                "lifecycle.cursor_close_attempted = True; "
                "lifecycle.raw_cursor_close()",
            ),
            (
                "connection cleanup ledger", finish,
                "if not lifecycle.connection_close_attempted",
            ),
            (
                "connection close physical dispatch", finish,
                "lifecycle.connection_close_attempted = True; "
                "lifecycle.connection_close()",
            ),
            (
                "claim completion ledger", finish,
                "if not lifecycle.claim_completed",
            ),
            (
                "postcleanup guard ledger", finish,
                "if not lifecycle.post_guard_attempted",
            ),
            (
                "cleanup completion handoff", finish,
                "lifecycle.cleanup_finished = True",
            ),
            (
                "failure calculation", finalize,
                "outcome_error = _transaction_outcome_error",
            ),
            (
                "internal outcome handoff", internal,
                "outcome = _finalize_transaction_lifecycle",
            ),
        )
        for name, target, fragment in cases:
            with self.subTest(boundary=name):
                fixture = self._new_guarded_transaction_fixture()
                target_line = self._source_line(
                    target,
                    fragment,
                    occurrence=(
                        1 if name == "cleanup completion handoff" else 0
                    ),
                )
                interrupted = KeyboardInterrupt(
                    "PRIVATE uncovered transaction handoff",
                )
                fired = []

                def trace(frame, event, arg):
                    if (
                        event == "line"
                        and frame.f_code is target.__code__
                        and frame.f_lineno == target_line
                        and not fired
                    ):
                        fired.append(True)
                        raise interrupted
                    return trace

                captured = None
                sys.settrace(trace)
                try:
                    runner(
                        fixture.opened,
                        fixture.lease,
                        lambda ignored: "handoff result must be discarded",
                    )
                except BaseException as error:
                    captured = error
                finally:
                    sys.settrace(None)
                try:
                    self.assertEqual(fired, [True])
                    self.assertIs(captured, interrupted)
                    self.assertEqual(fixture.connection.rollback_attempts, 1)
                    self.assertEqual(fixture.raw_cursor.close_attempts, 1)
                    self.assertEqual(fixture.connection.close_attempts, 1)
                    self.assertEqual(fixture.semaphore.releases, 1)
                finally:
                    fixture.lease.release()
                self.assertEqual(fixture.semaphore.releases, 1)

    def test_first_named_control_uses_observation_not_error_category_order(self):
        fixture = self._new_guarded_transaction_fixture()
        terminalize = runtime_budget._terminalize_guarded_cursor
        target_line = self._source_line(terminalize, "return snapshot")
        first = KeyboardInterrupt("PRIVATE first terminalizer control")
        later = SystemExit("PRIVATE later rollback control")
        fixture.connection.rollback_after_error = later
        fired = []

        def trace(frame, event, arg):
            if (
                event == "line"
                and frame.f_code is terminalize.__code__
                and frame.f_lineno == target_line
                and not fired
            ):
                fired.append(True)
                raise first
            return trace

        captured = None
        sys.settrace(trace)
        try:
            runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened,
                fixture.lease,
                lambda ignored: "control precedence",
            )
        except BaseException as error:
            captured = error
        finally:
            sys.settrace(None)
        try:
            self.assertEqual(fired, [True])
            self.assertIs(captured, first)
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_final_fixed_error_traceback_retains_no_runtime_resource(self):
        fixture = self._new_guarded_transaction_fixture()
        dependency_error = RuntimeError("PRIVATE final traceback dependency")
        captured = None
        try:
            runtime_budget.run_warehouse_anomaly_read_transaction(
                fixture.opened,
                fixture.lease,
                mock.Mock(side_effect=dependency_error),
            )
        except BaseException as error:
            captured = error
        exposed = []
        traceback = captured.__traceback__
        while traceback is not None:
            if (
                traceback.tb_frame.f_globals.get("__name__")
                == runtime_budget.__name__
            ):
                for name, value in traceback.tb_frame.f_locals.items():
                    if (
                        any(value is resource for resource in (
                            fixture.connection, fixture.raw_cursor,
                            fixture.lease, dependency_error,
                        ))
                        or type(value).__name__ in {
                            "_GuardedCursorState", "_TransactionLedger",
                        }
                        or any(
                            getattr(value, "__self__", None) is resource
                            for resource in (
                                fixture.connection, fixture.raw_cursor,
                            )
                        )
                    ):
                        exposed.append((
                            traceback.tb_frame.f_code.co_name, name,
                        ))
            traceback = traceback.tb_next
        try:
            self.assertIsInstance(captured, ValueError)
            self.assertEqual(captured.code, READ_FAILED)
            self.assertEqual(exposed, [])
            self.assertEqual(fixture.connection.rollback_attempts, 1)
            self.assertEqual(fixture.raw_cursor.close_attempts, 1)
            self.assertEqual(fixture.connection.close_attempts, 1)
            self.assertEqual(fixture.semaphore.releases, 1)
        finally:
            fixture.lease.release()
        self.assertEqual(fixture.semaphore.releases, 1)

    def test_guarded_wrapper_surface_and_transaction_callsites_are_sealed(self):
        wrapper_type = runtime_budget._WarehouseAnomalyGuardedCursor
        self.assertEqual(wrapper_type.__slots__, ("__weakref__",))
        self.assertEqual({
            name
            for name in vars(wrapper_type)
            if not name.startswith("_")
        }, {"execute", "fetchall", "close"})
        forged = wrapper_type()
        for name in (
            "raw_cursor", "raw_execute", "raw_fetchall", "raw_close",
            "connection", "lease", "state", "token",
        ):
            with self.assertRaises(AttributeError):
                setattr(forged, name, object())
        for operation in (
            lambda: forged.execute("SELECT 1"),
            forged.fetchall,
            forged.close,
        ):
            _fixed_error(self, INPUT_INVALID, operation)

        self.assertEqual(runtime_budget._MAX_SERVER_STATEMENTS, 18)
        self.assertEqual(runtime_budget.__all__, [])
        runner_source = inspect.getsource(
            runtime_budget.run_warehouse_anomaly_read_transaction,
        )
        for forbidden in (
            ".commit(", ".set_session(", ".fetchone(", ".fetchmany(",
            "Thread", "Executor", "submit(",
        ):
            self.assertNotIn(forbidden, runner_source)

        module_path = Path(runtime_budget.__file__).resolve()
        root = module_path.parents[3]
        private_names = (
            "run_warehouse_anomaly_read_transaction",
            "_WarehouseAnomalyGuardedCursor",
            "_guarded_execute",
            "_guarded_fetchall",
            "_terminalize_guarded_cursor",
        )
        unexpected = []
        for path in (root / "backend").rglob("*.py"):
            resolved = path.resolve()
            if (
                resolved in {module_path, Path(__file__).resolve()}
                or path.name.startswith("test_")
            ):
                continue
            source = path.read_text(encoding="utf-8")
            for name in private_names:
                if name in source:
                    unexpected.append((str(path.relative_to(root)), name))
        self.assertEqual(unexpected, [(
            "backend/features/warehouse_recommendation_preview/"
            "runtime_preview.py",
            "run_warehouse_anomaly_read_transaction",
        )])

    def test_static_private_surface_has_no_registration_or_abandoned_timeout(self):
        module_path = Path(runtime_budget.__file__).resolve()
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertEqual(_bounded_semaphore_binding(), _bounded_semaphore_binding())

        acquire_source = inspect.getsource(
            runtime_budget.acquire_warehouse_anomaly_runtime_slot
        )
        for forbidden in (
            "get_db", "DB_CONFIG", ".connect(", ".cursor(", ".execute(",
        ):
            self.assertNotIn(forbidden, acquire_source)

        imported = []
        import_manifest = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
                import_manifest.append((
                    "import",
                    tuple((alias.name, alias.asname) for alias in node.names),
                ))
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
                import_manifest.append((
                    "from",
                    node.level,
                    node.module,
                    tuple((alias.name, alias.asname) for alias in node.names),
                ))
        self.assertEqual(import_manifest, [
            ("import", (("math", None),)),
            ("import", (("threading", None),)),
            ("import", (("time", None),)),
            ("import", (("weakref", None),)),
            ("from", 0, "typing", (("NamedTuple", None),)),
            ("import", (("psycopg2", None),)),
            ("import", (("psycopg2.extras", None),)),
        ])
        joined_imports = " ".join(imported).lower()
        for forbidden in (
            "backend.db",
            "backend.main",
            "concurrent.futures",
            "asyncio",
            "multiprocessing",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "routes",
            "writer",
            "provider",
            "model",
            "outbox",
        ):
            self.assertNotIn(forbidden, joined_imports)

        self.assertFalse(any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id in {"Thread", "ThreadPoolExecutor", "Executor"}
                or isinstance(node.func, ast.Attribute)
                and node.func.attr in {
                    "Thread", "ThreadPoolExecutor", "Executor", "submit",
                }
            )
            for node in ast.walk(tree)
        ))

        factory_source = inspect.getsource(
            runtime_budget.open_warehouse_anomaly_read_connection
        )
        for forbidden in (
            "backend.db", "get_db", "DB_CONFIG", "threading", "Thread",
            "Executor", "submit", ".cursor(", ".execute(", ".rollback(",
        ):
            self.assertNotIn(forbidden, factory_source)
        self.assertEqual(runtime_budget.__all__, [])
        self.assertEqual({
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "threading"
        }, {"BoundedSemaphore", "RLock"})
        self.assertFalse(any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec"}
            for node in ast.walk(tree)
        ))

        unchanged_hashes = {
            "__init__.py": "d30babfeb425141af2fbf645be82eef358b6dea7d213b6d6b23cef3e7c551fea",
            "content_preview.py": "6bf1b385b833bd2f02b16e066fbb41a7ea6aa9566cb4ce4c6eeff8d5dea9da64",
            "content_contract.py": "ebfd82c1ed2c1a7216b06636785585c6c02856d2b1df185e5c7210ca90aac10a",
            "readiness.py": "1a268d142efc4133ce3e1b2c869744714b0edf4d630b4bb2530093327efd428f",
        }
        for filename, expected_hash in unchanged_hashes.items():
            self.assertEqual(
                hashlib.sha256(module_path.with_name(filename).read_bytes()).hexdigest(),
                expected_hash,
            )
        package_init = module_path.with_name("__init__.py")
        self.assertEqual(preview_package.__all__, [
            "WAREHOUSE_ANOMALY_READINESS_VERSION",
            "WarehouseAnomalyReadinessError",
            "build_warehouse_anomaly_readiness",
        ])
        self.assertNotIn("runtime_budget", package_init.read_text(encoding="utf-8"))

        root = module_path.parents[3]
        self.assertEqual(
            hashlib.sha256((root / "backend/db.py").read_bytes()).hexdigest(),
            "7e53bc3f1bed6481c9579dc241768b948fc22b37ec5d0809505022e62e2d750f",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "package.json",
        ):
            registered = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn(
                "runtime_budget",
                registered,
            )


if __name__ == "__main__":
    unittest.main()
