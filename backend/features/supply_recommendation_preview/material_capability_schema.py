"""Guarded A8.4b1 migration for authoritative capability evidence."""

import argparse
import json
import sys

import psycopg2.extras

from backend.features.supply_recommendation_preview.material_capability_schema_contract import (
    ADVISORY_LOCK_ID,
    APPLY_CONFIRMATION,
    COLUMN_CONTRACT,
    CONSTRAINT_CONTRACT,
    CONTRACT_VERSION,
    CREATE_STEPS,
    FUNCTION_CONTRACT,
    IDENTITY_SEQUENCE_NAME,
    INDEX_CONTRACT,
    PARENT_RELATION_CONTRACT,
    PARENT_REQUIRED_COLUMNS,
    PLAN_SHA256_RE,
    RELATION_NAMES,
    TABLE_NAME,
    TRIGGER_CONTRACT,
    _body_sha256,
    _canonical_sql,
    build_material_capability_schema_plan,
    calculate_material_capability_schema_plan_sha256,
    material_capability_schema_contract,
)
from backend.features.supply_recommendation_preview.material_capability_schema_probe import (
    collect_material_capability_schema_catalog as _collect_catalog,
)


class MaterialCapabilitySchemaMigrationError(RuntimeError):
    """One fixed-code exception boundary for migration failures."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _validate_invocation(
    *, apply, confirm, expected_change_count, expected_plan_sha256,
):
    guards = (confirm, expected_change_count, expected_plan_sha256)
    if not apply:
        if any(value is not None for value in guards):
            raise MaterialCapabilitySchemaMigrationError(
                "material_capability_schema_apply_guard_invalid"
            )
        return
    if (
        confirm != APPLY_CONFIRMATION
        or type(expected_change_count) is not int
        or expected_change_count < 0
        or type(expected_plan_sha256) is not str
        or PLAN_SHA256_RE.fullmatch(expected_plan_sha256) is None
    ):
        raise MaterialCapabilitySchemaMigrationError(
            "material_capability_schema_apply_guard_invalid"
        )


def _migration_report(
    plan,
    *,
    dry_run,
    writes_attempted=0,
    rolled_back=False,
    committed=False,
):
    result = dict(plan)
    result.update({
        "mode": "dry-run" if dry_run else "apply",
        "dryRun": dry_run,
        "schemaWritesAttempted": writes_attempted,
        "readOnlyTransaction": dry_run,
        "rolledBack": rolled_back,
        "committed": committed,
    })
    return result


def run_material_capability_schema_migration(
    get_db,
    *,
    apply=False,
    confirm=None,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    """Dry-run or atomically apply the exact append-only store contract."""

    _validate_invocation(
        apply=apply,
        confirm=confirm,
        expected_change_count=expected_change_count,
        expected_plan_sha256=expected_plan_sha256,
    )
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = False
    cleanup_error = False
    transaction_resolved = False
    commit_uncertain = False
    writes_attempted = 0

    try:
        connection = get_db()
        connection.set_session(
            readonly=not apply,
            autocommit=False,
            isolation_level="SERIALIZABLE" if apply else "REPEATABLE READ",
        )
        cur = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        cur.execute("SET LOCAL search_path=pg_catalog,public")
        if not apply:
            plan = build_material_capability_schema_plan(
                _collect_catalog(cur)
            )
            result = _migration_report(
                plan, dry_run=True, rolled_back=True
            )
        else:
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute(
                "LOCK TABLE public.companies,public.platform_accounts,"
                "public.company_supplier_links,public.suppliers,public.users,"
                "public.user_company_roles IN SHARE MODE"
            )
            cur.execute(
                "SELECT pg_catalog.pg_advisory_xact_lock(%s) LIMIT %s",
                (ADVISORY_LOCK_ID, 1),
            )
            before = build_material_capability_schema_plan(
                _collect_catalog(cur)
            )
            if (
                before["changeCount"] != expected_change_count
                or before["planSha256"] != expected_plan_sha256
            ):
                raise MaterialCapabilitySchemaMigrationError(
                    "material_capability_schema_apply_guard_mismatch"
                )
            if before["complete"]:
                result = _migration_report(
                    before, dry_run=False, rolled_back=True
                )
            elif not before["readyForApply"]:
                raise MaterialCapabilitySchemaMigrationError(
                    "material_capability_schema_not_ready"
                )
            else:
                for change in before["changes"]:
                    cur.execute(change["sql"])
                    writes_attempted += 1
                after = build_material_capability_schema_plan(
                    _collect_catalog(cur)
                )
                if not after["complete"] or after["blockers"]:
                    raise MaterialCapabilitySchemaMigrationError(
                        "material_capability_schema_postcheck_failed"
                    )
                try:
                    connection.commit()
                except BaseException:
                    commit_uncertain = True
                    raise MaterialCapabilitySchemaMigrationError(
                        "material_capability_schema_commit_outcome_unknown"
                    )
                transaction_resolved = True
                result = _migration_report(
                    after,
                    dry_run=False,
                    writes_attempted=writes_attempted,
                    committed=True,
                )
                result.update({
                    "changeCount": before["changeCount"],
                    "changes": before["changes"],
                    "rollbackSql": before["rollbackSql"],
                    "planSha256": before["planSha256"],
                })
    except BaseException as exc:
        primary_error = exc
    finally:
        if connection is not None and not transaction_resolved:
            try:
                connection.rollback()
                transaction_resolved = True
            except BaseException:
                rollback_error = True
        if cur is not None:
            try:
                cur.close()
            except BaseException:
                cleanup_error = True
        if connection is not None:
            try:
                connection.close()
            except BaseException:
                cleanup_error = True

    if isinstance(primary_error, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise primary_error
    if commit_uncertain:
        raise MaterialCapabilitySchemaMigrationError(
            "material_capability_schema_commit_outcome_unknown"
        ) from None
    if rollback_error:
        raise MaterialCapabilitySchemaMigrationError(
            "material_capability_schema_rollback_failed"
        ) from None
    if cleanup_error:
        raise MaterialCapabilitySchemaMigrationError(
            "material_capability_schema_cleanup_failed"
        ) from None
    if isinstance(primary_error, MaterialCapabilitySchemaMigrationError):
        raise primary_error from None
    if primary_error is not None:
        raise MaterialCapabilitySchemaMigrationError(
            "material_capability_schema_migration_failed"
        ) from None
    return result


def _non_negative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "must be a non-negative integer"
        ) from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _sha256_arg(value):
    normalized = str(value or "")
    if PLAN_SHA256_RE.fullmatch(normalized) is None:
        raise argparse.ArgumentTypeError(
            "must be a lowercase 64-character SHA-256"
        )
    return normalized


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarded A8.4b supplier-material capability schema"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--expected-change-count", type=_non_negative_int)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg)
    args = parser.parse_args(argv)
    if not args.apply and any(value is not None for value in (
        args.confirm,
        args.expected_change_count,
        args.expected_plan_sha256,
    )):
        parser.error("apply guards are valid only with --apply")
    if args.apply and (
        args.confirm != APPLY_CONFIRMATION
        or args.expected_change_count is None
        or args.expected_plan_sha256 is None
    ):
        parser.error(
            "--apply requires exact confirmation, change count and plan SHA"
        )

    from backend.db import get_db

    try:
        result = run_material_capability_schema_migration(
            get_db,
            apply=args.apply,
            confirm=args.confirm,
            expected_change_count=args.expected_change_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    except MaterialCapabilitySchemaMigrationError as exc:
        print(json.dumps({"ok": False, "code": exc.code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


__all__ = [
    "APPLY_CONFIRMATION",
    "CONTRACT_VERSION",
    "MaterialCapabilitySchemaMigrationError",
    "build_material_capability_schema_plan",
    "calculate_material_capability_schema_plan_sha256",
    "material_capability_schema_contract",
    "run_material_capability_schema_migration",
]


if __name__ == "__main__":
    sys.exit(main())
