"""Guarded A8.3a migration for the supplier direct-user read index."""

import argparse
import hashlib
import json
import re
import sys

import psycopg2.extras


INDEX_CONTRACT_VERSION = 1
APPLY_CONFIRMATION = "APPLY_SUPPLIER_REVIEW_INDEX"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INDEX_NAME = "idx_suppliers_user_id_id"
CREATE_SQL = (
    "CREATE INDEX idx_suppliers_user_id_id "
    "ON public.suppliers USING btree (user_id,id)"
)
ROLLBACK_SQL = (
    "DROP INDEX IF EXISTS public.idx_suppliers_user_id_id;"
)
MAX_INDEX_ROWS = 64
ADVISORY_LOCK_ID = 8248301

_CONTRACT = {
    "contractVersion": INDEX_CONTRACT_VERSION,
    "schema": "public",
    "table": "suppliers",
    "indexName": INDEX_NAME,
    "method": "btree",
    "columns": ["user_id", "id"],
    "createSql": CREATE_SQL,
    "rollbackSql": ROLLBACK_SQL,
}
_CHANGE = {
    "name": "create_suppliers_user_id_id_index",
    "schema": "public",
    "table": "suppliers",
    "indexName": INDEX_NAME,
    "method": "btree",
    "columns": ["user_id", "id"],
    "sql": CREATE_SQL,
    "rollbackSql": ROLLBACK_SQL,
}


class SupplierReviewIndexMigrationError(RuntimeError):
    """Fixed error code safe to expose without catalog or database text."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _raise(code):
    raise SupplierReviewIndexMigrationError(code)


def _canonical_json_sha256(value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def supplier_user_index_plan_sha256(changes):
    """Bind the fixed migration contract and its zero-or-one change plan."""

    return _canonical_json_sha256({
        "contract": _CONTRACT,
        "changes": list(changes or []),
    })


def _usable_runtime_index(item):
    keys = list(item.get("keyColumns") or [])
    return (
        item.get("method") == "btree"
        and item.get("valid") is True
        and item.get("ready") is True
        and item.get("live") is True
        and item.get("checkxmin") is False
        and item.get("partial") is False
        and item.get("expression") is False
        and isinstance(item.get("keyCount"), int)
        and not isinstance(item.get("keyCount"), bool)
        and item["keyCount"] >= 2
        and keys[:2] == ["user_id", "id"]
        and list(item.get("operatorClasses") or [])[:2] == [
            "pg_catalog.int4_ops",
            "pg_catalog.int4_ops",
        ]
        and list(item.get("collationOids") or [])[:2] == [0, 0]
    )


def _exact_canonical_index(item):
    return (
        item.get("name") == INDEX_NAME
        and _usable_runtime_index(item)
        and item.get("keyColumns") == ["user_id", "id"]
        and item.get("keyCount") == 2
        and item.get("attributeCount") == 2
        and item.get("unique") is False
        and item.get("exclusion") is False
        and item.get("keyOptions") == [0, 0]
        and item.get("operatorClasses") == [
            "pg_catalog.int4_ops",
            "pg_catalog.int4_ops",
        ]
        and item.get("collationOids") == [0, 0]
    )


def build_supplier_user_index_plan(catalog):
    """Build one deterministic plan from allowlisted point catalog facts."""

    facts = dict(catalog or {})
    table = dict(facts.get("table") or {})
    columns = dict(facts.get("columns") or {})
    indexes = [dict(item or {}) for item in (facts.get("indexes") or [])]
    holder = dict(facts.get("canonicalNameHolder") or {})
    blockers = []

    if table.get("exists") is not True:
        blockers.append("supplier_index_table_missing")
    elif table.get("relkind") != "r":
        blockers.append("supplier_index_table_invalid")

    required = ("id", "user_id")
    if any(dict(columns.get(name) or {}).get("exists") is not True
           for name in required):
        blockers.append("supplier_index_columns_missing")
    elif (
        dict(columns.get("id") or {}).get("integer") is not True
        or dict(columns.get("id") or {}).get("notNull") is not True
        or dict(columns.get("user_id") or {}).get("integer") is not True
    ):
        blockers.append("supplier_index_column_contract_invalid")

    if facts.get("indexesComplete") is not True:
        blockers.append("supplier_index_catalog_incomplete")

    canonical = next(
        (
            item for item in indexes
            if item.get("name") == INDEX_NAME
            and item.get("oid") == holder.get("oid")
        ),
        None,
    )
    if holder.get("exists") is True and (
        holder.get("relkind") != "i"
        or canonical is None
        or not _exact_canonical_index(canonical)
    ):
        blockers.append("supplier_index_name_conflict")
    elif holder.get("exists") is not True and any(
        item.get("name") == INDEX_NAME for item in indexes
    ):
        blockers.append("supplier_index_catalog_incomplete")

    usable = sorted(
        (item for item in indexes if _usable_runtime_index(item)),
        key=lambda item: (
            item.get("name") != INDEX_NAME,
            str(item.get("name") or ""),
        ),
    )
    matching = usable[0] if usable else None
    if matching is None and table.get("canManage") is not True:
        blockers.append("supplier_index_privilege_missing")

    blockers = sorted(set(blockers))
    complete = not blockers and matching is not None
    ready = not blockers and not complete
    changes = [dict(_CHANGE)] if ready else []
    plan_sha256 = supplier_user_index_plan_sha256(changes)
    estimated_rows = table.get("estimatedRows")
    if (
        not isinstance(estimated_rows, int)
        or isinstance(estimated_rows, bool)
        or estimated_rows < 0
    ):
        estimated_rows = None

    return {
        "contractVersion": INDEX_CONTRACT_VERSION,
        "ok": not blockers,
        "schemaReady": not blockers,
        "complete": complete,
        "readyForApply": ready,
        "requiresMaintenanceWindow": True,
        "preferredIndex": INDEX_NAME,
        "matchingIndex": matching.get("name") if matching else None,
        "estimatedRows": estimated_rows,
        "blockers": blockers,
        "changeCount": len(changes),
        "changes": changes,
        "planSha256": plan_sha256,
        "rollbackSql": [ROLLBACK_SQL] if changes else [],
    }


def _rows(cur):
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _collect_catalog(cur):
    """Collect only exact, sentinel-bounded pg_catalog facts."""

    cur.execute(
        """SELECT relation.oid::bigint AS table_oid,
                  relation.relkind::text AS relkind,
                  (
                    pg_catalog.pg_has_role(relation.relowner,'USAGE')
                    AND pg_catalog.has_schema_privilege(
                          namespace.oid,'USAGE'
                        )
                    AND pg_catalog.has_schema_privilege(
                          namespace.oid,'CREATE'
                        )
                  ) AS can_manage,
                  CASE WHEN relation.reltuples<0 THEN 0
                       ELSE relation.reltuples::bigint
                  END AS estimated_rows
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_class relation
               ON relation.relnamespace=namespace.oid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND relation.relname=%s
            ORDER BY relation.oid
            LIMIT %s""",
        ("public", "suppliers", 2),
    )
    table_rows = _rows(cur)
    table_complete = len(table_rows) <= 1
    table_row = table_rows[0] if len(table_rows) == 1 else {}
    table_oid = table_row.get("table_oid")
    table = {
        "exists": bool(table_oid) and table_complete,
        "oid": int(table_oid) if table_oid else None,
        "relkind": table_row.get("relkind") if table_complete else None,
        "canManage": (
            table_row.get("can_manage") is True if table_complete else False
        ),
        "estimatedRows": (
            int(table_row["estimated_rows"])
            if table_complete
            and isinstance(table_row.get("estimated_rows"), int)
            and not isinstance(table_row.get("estimated_rows"), bool)
            and table_row["estimated_rows"] >= 0
            else None
        ),
    }

    columns = {
        name: {"exists": False, "integer": False, "notNull": False}
        for name in ("id", "user_id")
    }
    holder = {"exists": False, "oid": None, "relkind": None}
    indexes = []
    catalog_complete = table_complete
    if not table["exists"]:
        return {
            "table": table,
            "columns": columns,
            "canonicalNameHolder": holder,
            "indexes": indexes,
            "indexesComplete": catalog_complete,
        }

    requirements = json.dumps(
        [{"column_name": "id"}, {"column_name": "user_id"}],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    cur.execute(
        """SELECT required.column_name,
                  attribute.attname IS NOT NULL AS exists,
                  attribute.atttypid=(
                    'pg_catalog.int4'::pg_catalog.regtype
                  ) AS is_integer,
                  COALESCE(attribute.attnotnull,FALSE) AS not_null
             FROM pg_catalog.jsonb_to_recordset(%s::jsonb)
                  AS required(column_name text)
             LEFT JOIN LATERAL (
                  SELECT candidate.attname,candidate.atttypid,
                         candidate.attnotnull
                    FROM pg_catalog.pg_attribute candidate
                   WHERE candidate.attrelid=%s
                     AND candidate.attname=required.column_name
                     AND candidate.attnum>0
                     AND NOT candidate.attisdropped
                   ORDER BY candidate.attnum
                   LIMIT 2
             ) AS attribute ON TRUE
            ORDER BY required.column_name
            LIMIT %s""",
        (requirements, table["oid"], 3),
    )
    column_rows = _rows(cur)
    if len(column_rows) != 2:
        catalog_complete = False
    for row in column_rows[:2]:
        name = str(row.get("column_name") or "")
        if name not in columns:
            catalog_complete = False
            continue
        exists = row.get("exists")
        if exists is None:
            exists = row.get("is_integer") is not None
        columns[name] = {
            "exists": exists is True,
            "integer": row.get("is_integer") is True,
            "notNull": row.get("not_null") is True,
        }

    cur.execute(
        """SELECT relation.oid::bigint AS holder_oid,
                  relation.relkind::text AS relkind
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_class relation
               ON relation.relnamespace=namespace.oid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND relation.relname=%s
            ORDER BY relation.oid
            LIMIT %s""",
        ("public", INDEX_NAME, 2),
    )
    holder_rows = _rows(cur)
    if len(holder_rows) > 1:
        catalog_complete = False
    elif holder_rows:
        holder = {
            "exists": True,
            "oid": int(holder_rows[0]["holder_oid"]),
            "relkind": holder_rows[0].get("relkind"),
        }

    cur.execute(
        """SELECT index_relation.oid::bigint AS index_oid,
                  index_relation.relname AS index_name,
                  access_method.amname AS method,
                  index_state.indisvalid AS valid,
                  index_state.indisready AS ready,
                  index_state.indislive AS live,
                  index_state.indcheckxmin AS checkxmin,
                  index_state.indpred IS NOT NULL AS partial,
                  index_state.indexprs IS NOT NULL AS expression,
                  index_state.indisunique AS unique,
                  index_state.indisexclusion AS exclusion,
                  index_state.indnkeyatts::integer AS key_count,
                  index_state.indnatts::integer AS attribute_count,
                  ARRAY(
                    SELECT attribute.attname
                      FROM pg_catalog.unnest(
                             index_state.indkey::smallint[]
                           ) WITH ORDINALITY
                           AS key_position(attnum,ordinality)
                      LEFT JOIN pg_catalog.pg_attribute attribute
                        ON attribute.attrelid=index_state.indrelid
                       AND attribute.attnum=key_position.attnum
                     WHERE key_position.ordinality
                           <=index_state.indnkeyatts
                     ORDER BY key_position.ordinality
                  ) AS key_columns,
                  ARRAY(
                    SELECT key_option.option::integer
                      FROM pg_catalog.unnest(
                             index_state.indoption::smallint[]
                           ) WITH ORDINALITY
                           AS key_option(option,ordinality)
                     WHERE key_option.ordinality
                           <=index_state.indnkeyatts
                     ORDER BY key_option.ordinality
                  ) AS key_options,
                  ARRAY(
                    SELECT operator_namespace.nspname || '.' ||
                           operator_class.opcname
                      FROM pg_catalog.unnest(
                             index_state.indclass::oid[]
                           ) WITH ORDINALITY
                           AS class_position(class_oid,ordinality)
                      JOIN pg_catalog.pg_opclass operator_class
                        ON operator_class.oid=class_position.class_oid
                      JOIN pg_catalog.pg_namespace operator_namespace
                        ON operator_namespace.oid=
                           operator_class.opcnamespace
                     WHERE class_position.ordinality
                           <=index_state.indnkeyatts
                     ORDER BY class_position.ordinality
                  ) AS operator_classes,
                  ARRAY(
                    SELECT collation_position.collation_oid::bigint
                      FROM pg_catalog.unnest(
                             index_state.indcollation::oid[]
                           ) WITH ORDINALITY
                           AS collation_position(collation_oid,ordinality)
                     WHERE collation_position.ordinality
                           <=index_state.indnkeyatts
                     ORDER BY collation_position.ordinality
                  ) AS collation_oids
             FROM pg_catalog.pg_index index_state
             JOIN pg_catalog.pg_class index_relation
               ON index_relation.oid=index_state.indexrelid
            JOIN pg_catalog.pg_am access_method
               ON access_method.oid=index_relation.relam
            WHERE index_state.indrelid=%s
            LIMIT %s""",
        (table["oid"], MAX_INDEX_ROWS + 1),
    )
    index_rows = _rows(cur)
    if len(index_rows) > MAX_INDEX_ROWS:
        catalog_complete = False
        index_rows = index_rows[:MAX_INDEX_ROWS]
    for row in index_rows:
        indexes.append({
            "oid": int(row["index_oid"]),
            "name": str(row.get("index_name") or ""),
            "method": str(row.get("method") or ""),
            "valid": row.get("valid") is True,
            "ready": row.get("ready") is True,
            "live": row.get("live") is True,
            "checkxmin": row.get("checkxmin") is True,
            "partial": row.get("partial") is True,
            "expression": row.get("expression") is True,
            "unique": row.get("unique") is True,
            "exclusion": row.get("exclusion") is True,
            "keyCount": int(row.get("key_count") or 0),
            "attributeCount": int(row.get("attribute_count") or 0),
            "keyColumns": [
                str(value) if value is not None else None
                for value in (row.get("key_columns") or [])
            ],
            "keyOptions": [
                int(value) for value in (row.get("key_options") or [])
            ],
            "operatorClasses": [
                str(value)
                for value in (row.get("operator_classes") or [])
            ],
            "collationOids": [
                int(value) for value in (row.get("collation_oids") or [])
            ],
        })

    return {
        "table": table,
        "columns": columns,
        "canonicalNameHolder": holder,
        "indexes": indexes,
        "indexesComplete": catalog_complete,
    }


def _validate_invocation(
    *,
    apply,
    confirm,
    expected_change_count,
    expected_plan_sha256,
):
    guards_present = any(value is not None for value in (
        confirm,
        expected_change_count,
        expected_plan_sha256,
    ))
    if not apply:
        if guards_present:
            _raise("supplier_index_apply_guard_invalid")
        return None

    if (
        confirm != APPLY_CONFIRMATION
        or isinstance(expected_change_count, bool)
        or not isinstance(expected_change_count, int)
        or expected_change_count not in (0, 1)
        or not isinstance(expected_plan_sha256, str)
        or not PLAN_SHA256_RE.fullmatch(expected_plan_sha256)
    ):
        _raise("supplier_index_apply_guard_invalid")
    return expected_plan_sha256


def _report(
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


def run_supplier_user_index_migration(
    get_db,
    *,
    apply=False,
    confirm=None,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    """Dry-run or atomically apply the one exact A8.3a index change."""

    normalized_sha = _validate_invocation(
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

        if not apply:
            plan = build_supplier_user_index_plan(_collect_catalog(cur))
            connection.rollback()
            transaction_resolved = True
            result = _report(plan, dry_run=True, rolled_back=True)
        else:
            cur.execute("SET LOCAL lock_timeout='5s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            # At SERIALIZABLE, acquire the relation lock before the first
            # snapshot-bearing SELECT so the guarded catalog plan is current.
            cur.execute(
                "LOCK TABLE public.suppliers "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
            cur.execute(
                "SELECT pg_catalog.pg_advisory_xact_lock(%s)",
                (ADVISORY_LOCK_ID,),
            )
            before = build_supplier_user_index_plan(_collect_catalog(cur))
            if not before["schemaReady"]:
                _raise("supplier_index_catalog_blocked")
            if (
                before["changeCount"] != expected_change_count
                or before["planSha256"] != normalized_sha
            ):
                _raise("supplier_index_apply_guard_mismatch")
            if before["complete"]:
                connection.rollback()
                transaction_resolved = True
                result = _report(
                    before,
                    dry_run=False,
                    rolled_back=True,
                )
            else:
                if not before["readyForApply"]:
                    _raise("supplier_index_catalog_blocked")
                cur.execute(CREATE_SQL)
                writes_attempted = 1
                after = build_supplier_user_index_plan(
                    _collect_catalog(cur)
                )
                if (
                    not after["complete"]
                    or after["matchingIndex"] != INDEX_NAME
                    or after["blockers"]
                ):
                    _raise("supplier_index_postcheck_failed")
                try:
                    connection.commit()
                except BaseException:
                    commit_uncertain = True
                    _raise("supplier_index_commit_outcome_unknown")
                transaction_resolved = True
                result = _report(
                    after,
                    dry_run=False,
                    writes_attempted=writes_attempted,
                    committed=True,
                )
                result.update({
                    "changeCount": before["changeCount"],
                    "changes": before["changes"],
                    "planSha256": before["planSha256"],
                    "rollbackSql": before["rollbackSql"],
                })
    except SupplierReviewIndexMigrationError as exc:
        primary_error = exc
    except BaseException:
        primary_error = SupplierReviewIndexMigrationError(
            "supplier_index_migration_failed"
        )
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

    if commit_uncertain:
        _raise("supplier_index_commit_outcome_unknown")
    if rollback_error:
        _raise("supplier_index_rollback_failed")
    if cleanup_error:
        _raise("supplier_index_cleanup_failed")
    if primary_error is not None:
        raise primary_error from None
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
    if not PLAN_SHA256_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError(
            "must be a lowercase 64-character SHA-256"
        )
    return normalized


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarded A8.3a supplier review index migration"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--expected-change-count", type=_non_negative_int)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg)
    args = parser.parse_args(argv)
    guards = (
        args.confirm,
        args.expected_change_count,
        args.expected_plan_sha256,
    )
    if not args.apply and any(value is not None for value in guards):
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
        result = run_supplier_user_index_migration(
            get_db,
            apply=args.apply,
            confirm=args.confirm,
            expected_change_count=args.expected_change_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    except SupplierReviewIndexMigrationError as exc:
        print(json.dumps({"ok": False, "code": exc.code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


__all__ = [
    "APPLY_CONFIRMATION",
    "CREATE_SQL",
    "INDEX_NAME",
    "PLAN_SHA256_RE",
    "ROLLBACK_SQL",
    "SupplierReviewIndexMigrationError",
    "build_supplier_user_index_plan",
    "run_supplier_user_index_migration",
    "supplier_user_index_plan_sha256",
]


if __name__ == "__main__":
    sys.exit(main())
