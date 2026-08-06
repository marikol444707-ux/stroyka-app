"""Guarded additive E3.2 migration for brigade assignment source lineage."""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extensions
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / "backend" / ".env"
APPLY_CONFIRMATION = "APPLY_BRIGADE_LINEAGE"
PLAN_CONTRACT = "brigade-lineage-e3.2-legacy-v1"
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PREVIEW_LIMIT = 100
VALID_SOURCE_TYPES = ("legacy", "estimate", "manual", "pricelist")

_BCI_TABLE = "brigade_contract_items"
_SNAPSHOT_TABLE = "estimate_versions"
_TARGET_TABLES = (_BCI_TABLE, _SNAPSHOT_TABLE)
_BCI_COLUMNS = (
    "source_type",
    "source_estimate_version_id",
    "source_section_index",
    "source_item_index",
    "source_item_key",
)
_COORDINATE_COLUMNS = _BCI_COLUMNS[1:]
_SNAPSHOT_COLUMN = "sections_sha256"
_TARGET_SPECS = {
    (_BCI_TABLE, "source_type"): {
        "data_type": "character varying",
        "udt_name": "varchar",
        "length": 20,
        "legacy_default": True,
    },
    (_BCI_TABLE, "source_estimate_version_id"): {
        "data_type": "integer",
        "udt_name": "int4",
        "length": None,
        "legacy_default": False,
    },
    (_BCI_TABLE, "source_section_index"): {
        "data_type": "integer",
        "udt_name": "int4",
        "length": None,
        "legacy_default": False,
    },
    (_BCI_TABLE, "source_item_index"): {
        "data_type": "integer",
        "udt_name": "int4",
        "length": None,
        "legacy_default": False,
    },
    (_BCI_TABLE, "source_item_key"): {
        "data_type": "character varying",
        "udt_name": "varchar",
        "length": 255,
        "legacy_default": False,
    },
    (_SNAPSHOT_TABLE, _SNAPSHOT_COLUMN): {
        "data_type": "character varying",
        "udt_name": "varchar",
        "length": 64,
        "legacy_default": False,
    },
}
_LEGACY_DEFAULT_RE = re.compile(
    r"^\(?\s*'legacy'(?:::(?:character varying|varchar|text))?\s*\)?$",
    re.IGNORECASE,
)


class SnapshotPhaseError(RuntimeError):
    """The additive snapshot-column phase failed before phase two started."""

    def __init__(
        self,
        message,
        *,
        phase_one_rolled_back=True,
        snapshot_outcome_unknown=False,
    ):
        self.phase_one_rolled_back = phase_one_rolled_back
        self.snapshot_outcome_unknown = snapshot_outcome_unknown
        self.retry_safe = True
        outcome = (
            "snapshot phase outcome is unknown; rerun dry-run before retrying: "
            if snapshot_outcome_unknown
            else "snapshot phase rolled back; retry is safe after a new dry-run: "
        )
        super().__init__(outcome + str(message))

    def as_result(self):
        return {
            "ok": False,
            "failureReason": "brigade_lineage_snapshot_phase_failed",
            "snapshotSchemaCommitted": None if self.snapshot_outcome_unknown else False,
            "snapshotOutcomeUnknown": self.snapshot_outcome_unknown,
            "phaseOneRolledBack": self.phase_one_rolled_back,
            "retrySafe": self.retry_safe,
            "message": str(self),
        }


class MigrationPhaseError(RuntimeError):
    """Phase two failed after the additive snapshot schema phase committed."""

    def __init__(
        self,
        message,
        *,
        phase_two_rolled_back=True,
        phase_two_outcome_unknown=False,
    ):
        self.snapshot_schema_committed = True
        self.retry_safe = True
        self.phase_two_rolled_back = phase_two_rolled_back
        self.phase_two_outcome_unknown = phase_two_outcome_unknown
        outcome = (
            "phase 2 outcome is unknown; rerun dry-run before retrying: "
            if phase_two_outcome_unknown
            else "phase 2 rolled back; retry is safe after a new dry-run: "
        )
        super().__init__(
            "phase 2 failed after snapshot schema commit; " + outcome + str(message)
        )

    def as_result(self):
        return {
            "ok": False,
            "failureReason": "brigade_lineage_phase_two_failed",
            "snapshotSchemaCommitted": self.snapshot_schema_committed,
            "phaseTwoRolledBack": self.phase_two_rolled_back,
            "phaseTwoOutcomeUnknown": self.phase_two_outcome_unknown,
            "retrySafe": self.retry_safe,
            "message": str(self),
        }


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _non_negative_value(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _non_negative_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return result


def _sha256_arg(value):
    normalized = str(value or "").strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError("must be a 64-character SHA-256 hex digest")
    return normalized


def _classification(row, status, reason, source_type=None):
    item = dict(row or {})
    return {
        "contractItemId": _positive_int(item.get("contract_item_id")),
        "status": status,
        "reason": reason,
        "sourceType": source_type,
    }


def classify_lineage_row(row):
    """Classify only the stored lineage shape; never infer business lineage."""

    item = dict(row or {})
    if not _positive_int(item.get("contract_item_id")):
        return _classification(item, "needs_review", "contract_item_id_invalid")

    raw_type = item.get("source_type")
    coordinates = [item.get(name) for name in _COORDINATE_COLUMNS]
    has_coordinates = any(value is not None for value in coordinates)
    if raw_type is None:
        if has_coordinates:
            return _classification(
                item, "needs_review", "source_type_missing_with_coordinates"
            )
        return _classification(item, "ready", "legacy_lineage_empty", "legacy")

    if not isinstance(raw_type, str) or raw_type != raw_type.strip().lower():
        return _classification(item, "needs_review", "source_type_not_canonical")
    source_type = raw_type
    if source_type not in VALID_SOURCE_TYPES:
        return _classification(item, "needs_review", "source_type_unknown", source_type)

    if source_type in ("legacy", "manual", "pricelist"):
        if has_coordinates:
            return _classification(
                item,
                "needs_review",
                source_type + "_source_has_coordinates",
                source_type,
            )
        return _classification(
            item, "stored", "stored_" + source_type + "_source", source_type
        )

    raw_key = item.get("source_item_key")
    if (
        not _positive_int(item.get("source_estimate_version_id"))
        or _non_negative_value(item.get("source_section_index")) is None
        or _non_negative_value(item.get("source_item_index")) is None
        or not isinstance(raw_key, str)
        or not raw_key
        or raw_key != raw_key.strip()
    ):
        return _classification(
            item, "needs_review", "estimate_source_incomplete", source_type
        )
    return _classification(item, "stored", "stored_estimate_source", source_type)


def _legacy_default(value):
    return isinstance(value, str) and bool(_LEGACY_DEFAULT_RE.fullmatch(value.strip()))


def _validate_column(key, row, *, require_legacy_default=False):
    spec = _TARGET_SPECS[key]
    item = dict(row or {})
    table, column = key
    if item.get("data_type") != spec["data_type"] or item.get("udt_name") != spec["udt_name"]:
        raise RuntimeError(f"incompatible type for {table}.{column}")
    if item.get("character_maximum_length") != spec["length"]:
        raise RuntimeError(f"incompatible length for {table}.{column}")
    if item.get("is_nullable") != "YES":
        raise RuntimeError(f"incompatible nullability for {table}.{column}")
    default = item.get("column_default")
    if spec["legacy_default"]:
        if default is None and not require_legacy_default:
            return
        if not _legacy_default(default):
            raise RuntimeError(f"incompatible default for {table}.{column}")
    elif default is not None:
        raise RuntimeError(f"incompatible default for {table}.{column}")


def _validate_schema_state(state, require_complete=False):
    item = dict(state or {})
    tables = set(item.get("tables") or ())
    missing_tables = [table for table in _TARGET_TABLES if table not in tables]
    if missing_tables:
        raise RuntimeError("missing base table(s): " + ",".join(missing_tables))
    columns = dict(item.get("columns") or {})
    unknown = sorted(set(columns) - set(_TARGET_SPECS))
    if unknown:
        raise RuntimeError("unexpected target column metadata")
    for key, row in columns.items():
        _validate_column(
            key,
            row,
            require_legacy_default=require_complete,
        )
    source = columns.get((_BCI_TABLE, "source_type"))
    if (
        source
        and _legacy_default(source.get("column_default"))
        and len(columns) != len(_TARGET_SPECS)
    ):
        raise RuntimeError(
            "incompatible partial schema with unproven source_type legacy default"
        )
    missing = [key for key in _TARGET_SPECS if key not in columns]
    if require_complete and missing:
        names = ["%s.%s" % key for key in missing]
        raise RuntimeError("missing target column(s): " + ",".join(names))
    return True


def _schema_report(state):
    columns = dict((state or {}).get("columns") or {})
    present = len(columns)
    total = len(_TARGET_SPECS)
    source = columns.get((_BCI_TABLE, "source_type"))
    columns_complete = present == total
    temporary_default = bool(
        source and _legacy_default(source.get("column_default"))
    )
    contract_complete = columns_complete and temporary_default
    if present == 0:
        schema_state = "pre_migration"
    elif contract_complete:
        schema_state = "complete"
    else:
        schema_state = "partial"
    return {
        "state": schema_state,
        "complete": contract_complete,
        "columnsComplete": columns_complete,
        "presentColumns": present,
        "expectedColumns": total,
        "temporaryLegacyDefault": temporary_default,
        "columns": {
            table + "." + column: (table, column) in columns
            for table, column in _TARGET_SPECS
        },
    }


def build_migration_report(state, classified):
    _validate_schema_state(state, require_complete=False)
    rows = list(classified or ())
    counts = Counter(item.get("status") for item in rows)
    ready = sorted(
        (item for item in rows if item.get("status") == "ready"),
        key=lambda item: item.get("contractItemId") or 0,
    )
    review = sorted(
        (item for item in rows if item.get("status") == "needs_review"),
        key=lambda item: item.get("contractItemId") or 0,
    )
    stored_by_type = Counter(
        item.get("sourceType")
        for item in rows
        if item.get("status") == "stored"
    )
    consistent = len(rows) == counts["ready"] + counts["stored"] + counts["needs_review"]
    schema_info = _schema_report(state)
    complete = (
        consistent
        and schema_info["complete"]
        and schema_info["temporaryLegacyDefault"]
        and not ready
        and not review
    )
    return {
        "ok": True,
        "table": _BCI_TABLE,
        "schema": schema_info,
        "reportConsistent": consistent,
        "readyForMigration": consistent and not review,
        "migrationComplete": complete,
        "schemaMigrationComplete": complete,
        "readyForStrictRuntime": False,
        "constraintAuditIncluded": False,
        "writerAuditIncluded": False,
        "summary": {
            "totalRows": len(rows),
            "readyLegacy": len(ready),
            "needsReview": len(review),
            "storedRows": counts["stored"],
            "storedLegacy": stored_by_type["legacy"],
            "storedEstimate": stored_by_type["estimate"],
            "storedManual": stored_by_type["manual"],
            "storedPricelist": stored_by_type["pricelist"],
        },
        "backfillPreview": [
            {
                "contractItemId": item.get("contractItemId"),
                "reason": item.get("reason"),
            }
            for item in ready[:PREVIEW_LIMIT]
        ],
        "needsReview": [
            {
                "contractItemId": item.get("contractItemId"),
                "reason": item.get("reason"),
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "previewTruncated": len(ready) > PREVIEW_LIMIT or len(review) > PREVIEW_LIMIT,
    }


def _plan_sha256(classified):
    ids = []
    for item in classified or ():
        if item.get("status") != "ready":
            continue
        record_id = _positive_int(item.get("contractItemId"))
        if not record_id or item.get("sourceType") != "legacy":
            raise ValueError("ready lineage row is not an exact legacy plan row")
        ids.append(record_id)
    if len(ids) != len(set(ids)):
        raise ValueError("ready lineage plan contains duplicate IDs")
    payload = {
        "contract": PLAN_CONTRACT,
        "readyLegacy": [[record_id, "legacy"] for record_id in sorted(ids)],
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dict_row(row, names):
    if isinstance(row, dict):
        return dict(row)
    return dict(zip(names, row))


def _load_schema_state(cur):
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name = ANY(%s) "
        "ORDER BY table_name",
        ("public", list(_TARGET_TABLES)),
    )
    tables = {
        str(_dict_row(row, ("table_name",)).get("table_name") or "")
        for row in (cur.fetchall() or ())
    }
    cur.execute(
        """SELECT table_name,column_name,data_type,udt_name,
                  character_maximum_length,is_nullable,column_default
             FROM information_schema.columns
            WHERE table_schema=%s
              AND (
                    (table_name=%s AND column_name = ANY(%s))
                 OR (table_name=%s AND column_name=%s)
              )
            ORDER BY table_name,column_name""",
        (
            "public",
            _BCI_TABLE,
            list(_BCI_COLUMNS),
            _SNAPSHOT_TABLE,
            _SNAPSHOT_COLUMN,
        ),
    )
    names = (
        "table_name", "column_name", "data_type", "udt_name",
        "character_maximum_length", "is_nullable", "column_default",
    )
    columns = {}
    for raw in cur.fetchall() or ():
        row = _dict_row(raw, names)
        key = (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        if key in columns:
            raise RuntimeError("duplicate target column metadata")
        columns[key] = row
    return {"tables": tables, "columns": columns}


def _load_lineage_rows(cur, state):
    columns = dict((state or {}).get("columns") or {})
    expressions = {
        "source_type": "NULL::VARCHAR(20)",
        "source_estimate_version_id": "NULL::INTEGER",
        "source_section_index": "NULL::INTEGER",
        "source_item_index": "NULL::INTEGER",
        "source_item_key": "NULL::VARCHAR(255)",
    }
    select = ["bci.id AS contract_item_id"]
    for name in _BCI_COLUMNS:
        expression = "bci." + name if (_BCI_TABLE, name) in columns else expressions[name]
        select.append(expression + " AS " + name)
    cur.execute(
        "SELECT " + ",".join(select)
        + " FROM public.brigade_contract_items bci ORDER BY bci.id"
    )
    names = ("contract_item_id",) + _BCI_COLUMNS
    return [_dict_row(row, names) for row in (cur.fetchall() or ())]


def collect_migration_plan(cur):
    state = _load_schema_state(cur)
    _validate_schema_state(state, require_complete=False)
    classified = [classify_lineage_row(row) for row in _load_lineage_rows(cur, state)]
    report = build_migration_report(state, classified)
    return state, classified, report


def _set_local_timeouts(cur):
    cur.execute("SET LOCAL lock_timeout = '5s'")
    cur.execute("SET LOCAL statement_timeout = '120s'")


def _ensure_snapshot_schema(cur):
    cur.execute(
        "ALTER TABLE public.estimate_versions "
        "ADD COLUMN IF NOT EXISTS sections_sha256 VARCHAR(64) NULL"
    )


def _assert_snapshot_schema(cur):
    state = _load_schema_state(cur)
    missing_tables = [
        table for table in _TARGET_TABLES if table not in state["tables"]
    ]
    if missing_tables:
        raise RuntimeError("missing base table(s): " + ",".join(missing_tables))
    key = (_SNAPSHOT_TABLE, _SNAPSHOT_COLUMN)
    if key not in state["columns"]:
        raise RuntimeError("snapshot schema postcheck missing estimate_versions.sections_sha256")
    _validate_column(key, state["columns"][key])


def _lock_bci(cur):
    cur.execute(
        "LOCK TABLE public.brigade_contract_items IN ACCESS EXCLUSIVE MODE"
    )


def _ensure_bci_schema(cur):
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ADD COLUMN IF NOT EXISTS source_type VARCHAR(20) NULL"
    )
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ADD COLUMN IF NOT EXISTS source_estimate_version_id INTEGER NULL"
    )
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ADD COLUMN IF NOT EXISTS source_section_index INTEGER NULL"
    )
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ADD COLUMN IF NOT EXISTS source_item_index INTEGER NULL"
    )
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ADD COLUMN IF NOT EXISTS source_item_key VARCHAR(255) NULL"
    )
    cur.execute(
        "ALTER TABLE public.brigade_contract_items "
        "ALTER COLUMN source_type SET DEFAULT 'legacy'"
    )


def _apply_ready_rows(cur, ready_rows):
    selected = sorted(
        list(ready_rows or ()), key=lambda item: item.get("contractItemId") or 0
    )
    if not selected:
        return 0
    ids = [item.get("contractItemId") for item in selected]
    if any(not _positive_int(record_id) for record_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("legacy update contains invalid or duplicate IDs")
    cur.execute(
        """UPDATE public.brigade_contract_items
              SET source_type=%s
            WHERE id = ANY(%s::INTEGER[])
              AND source_type IS NULL
              AND source_estimate_version_id IS NULL
              AND source_section_index IS NULL
              AND source_item_index IS NULL
              AND source_item_key IS NULL""",
        ("legacy", ids),
    )
    return cur.rowcount


def _base_result(report, mode, classified):
    ready_count = int(report.get("summary", {}).get("readyLegacy") or 0)
    return {
        **report,
        "mode": mode,
        "dryRun": mode == "dry-run",
        "readyCount": ready_count,
        "reviewCount": int(report.get("summary", {}).get("needsReview") or 0),
        "planSha256": _plan_sha256(classified),
        "writesAttempted": 0,
        "updated": 0,
        "writeConflicts": 0,
        "rolledBack": False,
        "snapshotSchemaCommitted": False,
        "complete": report.get("migrationComplete") is True,
    }


def _validate_postcheck(before, after):
    before_summary = before.get("summary") or {}
    after_summary = after.get("summary") or {}
    ready = int(before_summary.get("readyLegacy") or 0)
    if int(after_summary.get("totalRows") or 0) != int(before_summary.get("totalRows") or 0):
        raise RuntimeError("postcheck totalRows changed")
    if after.get("reportConsistent") is not True:
        raise RuntimeError("postcheck report is inconsistent")
    if after.get("migrationComplete") is not True:
        raise RuntimeError("postcheck lineage migration is incomplete")
    if int(after_summary.get("storedLegacy") or 0) != int(before_summary.get("storedLegacy") or 0) + ready:
        raise RuntimeError("postcheck stored legacy count mismatch")
    for name in ("storedEstimate", "storedManual", "storedPricelist"):
        if int(after_summary.get(name) or 0) != int(before_summary.get(name) or 0):
            raise RuntimeError("postcheck " + name + " count changed")


def _validate_apply_guards(expected_ready_count, expected_plan_sha256):
    if (
        isinstance(expected_ready_count, bool)
        or not isinstance(expected_ready_count, int)
        or expected_ready_count < 0
    ):
        raise ValueError("apply requires a non-negative expected_ready_count")
    normalized_sha = str(expected_plan_sha256 or "").strip().lower()
    if not PLAN_SHA256_RE.fullmatch(normalized_sha):
        raise ValueError("apply requires a valid expected_plan_sha256")
    return normalized_sha


def run_migration(
    conn,
    apply=False,
    expected_ready_count=None,
    expected_plan_sha256=None,
):
    if not apply:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level=psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ,
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            _state, classified, report = collect_migration_plan(cur)
            result = _base_result(report, "dry-run", classified)
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    normalized_sha = _validate_apply_guards(
        expected_ready_count, expected_plan_sha256
    )
    conn.set_session(
        readonly=False,
        autocommit=False,
        isolation_level=psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED,
    )

    snapshot_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    snapshot_commit_started = False
    try:
        _set_local_timeouts(snapshot_cur)
        _ensure_snapshot_schema(snapshot_cur)
        _assert_snapshot_schema(snapshot_cur)
        snapshot_commit_started = True
        conn.commit()
    except Exception as exc:
        rollback_confirmed = False
        try:
            conn.rollback()
            rollback_confirmed = not snapshot_commit_started
        except Exception:
            rollback_confirmed = False
        raise SnapshotPhaseError(
            str(exc),
            phase_one_rolled_back=rollback_confirmed,
            snapshot_outcome_unknown=not rollback_confirmed,
        ) from exc
    finally:
        snapshot_cur.close()

    lineage_cur = None
    phase_two_commit_started = False
    try:
        lineage_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _set_local_timeouts(lineage_cur)
        _lock_bci(lineage_cur)
        _state, classified, report = collect_migration_plan(lineage_cur)
        result = _base_result(report, "apply", classified)
        if report.get("reportConsistent") is not True or result["reviewCount"]:
            raise RuntimeError("lineage rows need review before migration")
        if result["readyCount"] != expected_ready_count:
            raise RuntimeError(
                "migration ready legacy count changed; rerun dry-run"
            )
        if result["planSha256"] != normalized_sha:
            raise RuntimeError("migration plan SHA-256 changed; rerun dry-run")

        _ensure_bci_schema(lineage_cur)
        ready = [item for item in classified if item.get("status") == "ready"]
        updated = _apply_ready_rows(lineage_cur, ready)
        if updated != result["readyCount"]:
            raise RuntimeError(
                "legacy backfill rowcount mismatch: expected %s, updated %s"
                % (result["readyCount"], updated)
            )

        _post_state, _post_classified, post_report = collect_migration_plan(lineage_cur)
        _validate_postcheck(report, post_report)
        phase_two_commit_started = True
        conn.commit()
        pre_summary = result["summary"]
        result.update(
            {
                "schema": post_report["schema"],
                "preSummary": pre_summary,
                "summary": post_report["summary"],
                "postSummary": post_report["summary"],
                "reportConsistent": post_report["reportConsistent"],
                "readyForMigration": post_report["readyForMigration"],
                "migrationComplete": post_report["migrationComplete"],
                "writesAttempted": result["readyCount"],
                "updated": updated,
                "snapshotSchemaCommitted": True,
                "schemaMigrationComplete": True,
                "complete": True,
            }
        )
        return result
    except Exception as exc:
        rollback_confirmed = False
        try:
            conn.rollback()
            rollback_confirmed = not phase_two_commit_started
        except Exception:
            rollback_confirmed = False
        raise MigrationPhaseError(
            str(exc),
            phase_two_rolled_back=rollback_confirmed,
            phase_two_outcome_unknown=not rollback_confirmed,
        ) from exc
    finally:
        if lineage_cur is not None:
            lineage_cur.close()


def _load_env():
    values = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config():
    env = _load_env()
    return {
        "dbname": os.getenv("DB_NAME") or env.get("DB_NAME") or "stroyka",
        "user": os.getenv("DB_USER") or env.get("DB_USER") or "stroyka",
        "password": os.getenv("DB_PASSWORD") or env.get("DB_PASSWORD") or "password123",
        "host": os.getenv("DB_HOST") or env.get("DB_HOST") or "localhost",
        "port": os.getenv("DB_PORT") or env.get("DB_PORT") or "5432",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarded additive E3.2 brigade lineage migration"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expected-ready-count", type=_non_negative_int, default=None)
    parser.add_argument("--expected-plan-sha256", type=_sha256_arg, default=None)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("choose either --dry-run or --apply")
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")
    if args.apply and args.expected_ready_count is None:
        parser.error("--apply requires --expected-ready-count from dry-run")
    if args.apply and args.expected_plan_sha256 is None:
        parser.error("--apply requires --expected-plan-sha256 from dry-run")
    if not args.apply and (
        args.expected_ready_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("expected guards are valid only with --apply")

    conn = psycopg2.connect(**_db_config())
    try:
        result = run_migration(
            conn,
            apply=args.apply,
            expected_ready_count=args.expected_ready_count,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    except (SnapshotPhaseError, MigrationPhaseError) as exc:
        print(json.dumps(exc.as_result(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
