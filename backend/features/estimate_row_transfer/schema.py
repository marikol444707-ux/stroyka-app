"""Guarded additive schema migration for the inert E4.2 transfer ledger."""

import argparse
import hashlib
import json
import re

import psycopg2.extras


PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PLAN_COLUMNS = {
    "id", "company_id", "project_id", "work_package", "smeta_type",
    "reconciliation_id", "base_estimate_id", "target_estimate_id",
    "target_estimate_version_id", "base_sections_sha256",
    "target_sections_sha256", "base_snapshot_row_count",
    "target_snapshot_row_count", "plan_sha256", "approved_plan_sha256",
    "status", "created_by_user_id", "created_by_name", "created_by_role",
    "approved_by_user_id", "approved_by_name", "approved_by_role",
    "approved_at", "created_at", "updated_at",
}
ENTRY_COLUMNS = {
    "id", "plan_id", "company_id", "project_id", "source_kind",
    "source_id", "source_parent_id", "request_item_index",
    "source_estimate_id", "source_estimate_version_id",
    "source_section_index", "source_item_index", "source_item_key",
    "source_sections_sha256", "target_estimate_id",
    "target_estimate_version_id", "target_section_index",
    "target_item_index", "target_item_key", "target_sections_sha256",
    "source_total_quantity", "source_protected_quantity",
    "source_available_quantity", "quantity", "created_at",
}
PLAN_CONSTRAINTS = {
    "pk_estimate_row_transfer_plans", "fk_etrp_reconciliation",
    "fk_etrp_base_estimate", "fk_etrp_target_estimate",
    "fk_etrp_target_version", "ck_etrp_owner", "ck_etrp_hashes",
    "ck_etrp_status", "ck_etrp_approval", "uq_etrp_id_owner",
    "uq_etrp_hash",
}
ENTRY_CONSTRAINTS = {
    "pk_estimate_row_transfer_entries", "fk_etre_plan_owner",
    "fk_etre_source_estimate", "fk_etre_source_version",
    "fk_etre_target_estimate", "fk_etre_target_version", "ck_etre_owner",
    "ck_etre_source_kind", "ck_etre_source_shape", "ck_etre_coordinates",
    "ck_etre_hashes", "ck_etre_quantities",
}
INDEXES = {
    "idx_etrp_owner_created", "uq_etrp_single_approved", "idx_etre_plan",
    "uq_etre_assignment_source", "uq_etre_supply_source",
}
FUNCTIONS = {
    "reject_estimate_row_transfer_entry_mutation",
    "guard_estimate_row_transfer_plan_mutation",
}
TRIGGERS = {
    "estimate_row_transfer_entry_immutable",
    "estimate_row_transfer_plan_guard",
}


class SchemaMigrationError(RuntimeError):
    pass


CREATE_PLANS_TABLE = """
CREATE TABLE public.estimate_row_transfer_plans (
    id BIGSERIAL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    work_package VARCHAR(100) NOT NULL,
    smeta_type VARCHAR(50) NOT NULL,
    reconciliation_id INTEGER NOT NULL,
    base_estimate_id INTEGER NOT NULL,
    target_estimate_id INTEGER NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    base_sections_sha256 CHAR(64) NOT NULL,
    target_sections_sha256 CHAR(64) NOT NULL,
    base_snapshot_row_count INTEGER NOT NULL,
    target_snapshot_row_count INTEGER NOT NULL,
    plan_sha256 CHAR(64) NOT NULL,
    approved_plan_sha256 CHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by_user_id INTEGER NOT NULL,
    created_by_name TEXT NOT NULL,
    created_by_role VARCHAR(100) NOT NULL,
    approved_by_user_id INTEGER,
    approved_by_name TEXT,
    approved_by_role VARCHAR(100),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_transfer_plans PRIMARY KEY (id),
    CONSTRAINT fk_etrp_reconciliation FOREIGN KEY (reconciliation_id)
        REFERENCES public.estimate_reconciliations(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_base_estimate FOREIGN KEY (base_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_target_estimate FOREIGN KEY (target_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_etrp_owner CHECK (
        company_id>0 AND project_id>0
        AND base_snapshot_row_count>=0 AND target_snapshot_row_count>=0
    ),
    CONSTRAINT ck_etrp_hashes CHECK (
        base_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND target_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND plan_sha256 ~ '^[0-9a-f]{64}$'
        AND (approved_plan_sha256 IS NULL
             OR approved_plan_sha256 ~ '^[0-9a-f]{64}$')
    ),
    CONSTRAINT ck_etrp_status CHECK (status IN ('draft','approved')),
    CONSTRAINT ck_etrp_approval CHECK (
        (status='draft' AND approved_plan_sha256 IS NULL
         AND approved_by_user_id IS NULL AND approved_by_name IS NULL
         AND approved_by_role IS NULL AND approved_at IS NULL)
        OR
        (status='approved' AND approved_plan_sha256=plan_sha256
         AND approved_by_user_id>0 AND approved_by_name IS NOT NULL
         AND approved_by_role IN ('директор','зам_директора')
         AND approved_at IS NOT NULL)
    ),
    CONSTRAINT uq_etrp_id_owner UNIQUE (id,company_id,project_id),
    CONSTRAINT uq_etrp_hash UNIQUE (company_id,reconciliation_id,plan_sha256)
)
"""

CREATE_ENTRIES_TABLE = """
CREATE TABLE public.estimate_row_transfer_entries (
    id BIGSERIAL,
    plan_id BIGINT NOT NULL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    source_kind VARCHAR(20) NOT NULL,
    source_id INTEGER NOT NULL,
    source_parent_id INTEGER NOT NULL,
    request_item_index INTEGER,
    source_estimate_id INTEGER NOT NULL,
    source_estimate_version_id INTEGER NOT NULL,
    source_section_index INTEGER NOT NULL,
    source_item_index INTEGER NOT NULL,
    source_item_key VARCHAR(255) NOT NULL,
    source_sections_sha256 CHAR(64) NOT NULL,
    target_estimate_id INTEGER NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    target_section_index INTEGER NOT NULL,
    target_item_index INTEGER NOT NULL,
    target_item_key VARCHAR(255) NOT NULL,
    target_sections_sha256 CHAR(64) NOT NULL,
    source_total_quantity NUMERIC(20,6) NOT NULL,
    source_protected_quantity NUMERIC(20,6) NOT NULL,
    source_available_quantity NUMERIC(20,6) NOT NULL,
    quantity NUMERIC(20,6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_transfer_entries PRIMARY KEY (id),
    CONSTRAINT fk_etre_plan_owner FOREIGN KEY (plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_plans(id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_etre_source_estimate FOREIGN KEY (source_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_source_version FOREIGN KEY (source_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_target_estimate FOREIGN KEY (target_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_etre_owner CHECK (company_id>0 AND project_id>0),
    CONSTRAINT ck_etre_source_kind CHECK (source_kind IN ('assignment','supply')),
    CONSTRAINT ck_etre_source_shape CHECK (
        (source_kind='assignment' AND request_item_index IS NULL)
        OR
        (source_kind='supply' AND request_item_index>=0
         AND source_parent_id=source_id)
    ),
    CONSTRAINT ck_etre_coordinates CHECK (
        source_id>0 AND source_parent_id>0 AND source_estimate_id>0
        AND source_estimate_version_id>0 AND source_section_index>=0
        AND source_item_index>=0 AND source_item_key<>''
        AND target_estimate_id>0 AND target_estimate_version_id>0
        AND target_section_index>=0 AND target_item_index>=0
        AND target_item_key<>''
    ),
    CONSTRAINT ck_etre_hashes CHECK (
        source_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND target_sections_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_etre_quantities CHECK (
        source_total_quantity>=0 AND source_protected_quantity>=0
        AND source_available_quantity>0 AND quantity>0
        AND source_protected_quantity<=source_total_quantity
        AND source_available_quantity=source_total_quantity-source_protected_quantity
        AND quantity<=source_available_quantity
    )
)
"""

ENTRY_GUARD_FUNCTION = """
CREATE FUNCTION public.reject_estimate_row_transfer_entry_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'estimate_row_transfer_entry_immutable';
END
$$
"""

PLAN_GUARD_FUNCTION = """
CREATE FUNCTION public.guard_estimate_row_transfer_plan_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_immutable';
    END IF;
    IF OLD.status<>'draft' OR NEW.status<>'approved' THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_transition_invalid';
    END IF;
    IF ROW(
        NEW.id,NEW.company_id,NEW.project_id,NEW.work_package,NEW.smeta_type,
        NEW.reconciliation_id,NEW.base_estimate_id,NEW.target_estimate_id,
        NEW.target_estimate_version_id,NEW.base_sections_sha256,
        NEW.target_sections_sha256,NEW.base_snapshot_row_count,
        NEW.target_snapshot_row_count,NEW.plan_sha256,NEW.created_by_user_id,
        NEW.created_by_name,NEW.created_by_role,NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.id,OLD.company_id,OLD.project_id,OLD.work_package,OLD.smeta_type,
        OLD.reconciliation_id,OLD.base_estimate_id,OLD.target_estimate_id,
        OLD.target_estimate_version_id,OLD.base_sections_sha256,
        OLD.target_sections_sha256,OLD.base_snapshot_row_count,
        OLD.target_snapshot_row_count,OLD.plan_sha256,OLD.created_by_user_id,
        OLD.created_by_name,OLD.created_by_role,OLD.created_at
    ) OR NEW.approved_plan_sha256 IS DISTINCT FROM OLD.plan_sha256
      OR NEW.approved_by_user_id IS NULL OR NEW.approved_by_name IS NULL
      OR NEW.approved_by_role NOT IN ('директор','зам_директора')
      OR NEW.approved_at IS NULL OR NEW.updated_at<OLD.updated_at THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_mutation_invalid';
    END IF;
    RETURN NEW;
END
$$
"""

CHANGE_DEFINITIONS = (
    ("create_plans_table", "plans_table", CREATE_PLANS_TABLE),
    ("create_entries_table", "entries_table", CREATE_ENTRIES_TABLE),
    ("create_owner_index", "idx_etrp_owner_created", """
        CREATE INDEX idx_etrp_owner_created
        ON public.estimate_row_transfer_plans(company_id,project_id,created_at DESC,id DESC)
    """),
    ("create_single_approved_index", "uq_etrp_single_approved", """
        CREATE UNIQUE INDEX uq_etrp_single_approved
        ON public.estimate_row_transfer_plans(company_id,reconciliation_id)
        WHERE status='approved'
    """),
    ("create_entry_plan_index", "idx_etre_plan", """
        CREATE INDEX idx_etre_plan ON public.estimate_row_transfer_entries(plan_id,id)
    """),
    ("create_assignment_source_index", "uq_etre_assignment_source", """
        CREATE UNIQUE INDEX uq_etre_assignment_source
        ON public.estimate_row_transfer_entries(plan_id,source_id)
        WHERE source_kind='assignment'
    """),
    ("create_supply_source_index", "uq_etre_supply_source", """
        CREATE UNIQUE INDEX uq_etre_supply_source
        ON public.estimate_row_transfer_entries(plan_id,source_id,request_item_index)
        WHERE source_kind='supply'
    """),
    ("create_entry_guard_function", "reject_estimate_row_transfer_entry_mutation", ENTRY_GUARD_FUNCTION),
    ("create_plan_guard_function", "guard_estimate_row_transfer_plan_mutation", PLAN_GUARD_FUNCTION),
    ("create_entry_guard_trigger", "estimate_row_transfer_entry_immutable", """
        CREATE TRIGGER estimate_row_transfer_entry_immutable
        BEFORE UPDATE OR DELETE ON public.estimate_row_transfer_entries
        FOR EACH ROW EXECUTE FUNCTION public.reject_estimate_row_transfer_entry_mutation()
    """),
    ("create_plan_guard_trigger", "estimate_row_transfer_plan_guard", """
        CREATE TRIGGER estimate_row_transfer_plan_guard
        BEFORE UPDATE OR DELETE ON public.estimate_row_transfer_plans
        FOR EACH ROW EXECUTE FUNCTION public.guard_estimate_row_transfer_plan_mutation()
    """),
)


def _values(catalog, key):
    return {str(value) for value in (catalog.get(key) or [])}


def build_schema_plan(catalog):
    catalog = dict(catalog or {})
    plans_table = bool(catalog.get("plans_table"))
    entries_table = bool(catalog.get("entries_table"))
    blockers = []
    missing_plan_columns = sorted(PLAN_COLUMNS - _values(catalog, "plan_columns")) if plans_table else []
    missing_entry_columns = sorted(ENTRY_COLUMNS - _values(catalog, "entry_columns")) if entries_table else []
    if entries_table and not plans_table:
        blockers.append("table_dependency_invalid")
    constraints = _values(catalog, "constraints")
    if missing_plan_columns:
        blockers.append("plan_columns_invalid")
    if missing_entry_columns:
        blockers.append("entry_columns_invalid")
    if plans_table and not PLAN_CONSTRAINTS.issubset(constraints):
        blockers.append("plan_constraints_invalid")
    if entries_table and not ENTRY_CONSTRAINTS.issubset(constraints):
        blockers.append("entry_constraints_invalid")

    indexes = _values(catalog, "indexes")
    functions = _values(catalog, "functions")
    triggers = _values(catalog, "triggers")
    changes = []
    for name, object_name, sql in CHANGE_DEFINITIONS:
        if object_name == "plans_table":
            missing = not plans_table
        elif object_name == "entries_table":
            missing = not entries_table
        elif object_name in INDEXES:
            missing = object_name not in indexes
        elif object_name in FUNCTIONS:
            missing = object_name not in functions
        else:
            missing = object_name not in triggers
        if missing:
            changes.append({"name": name, "sql": sql.strip()})

    expected = {
        "planColumns": sorted(PLAN_COLUMNS),
        "entryColumns": sorted(ENTRY_COLUMNS),
        "constraints": sorted(PLAN_CONSTRAINTS | ENTRY_CONSTRAINTS),
        "indexes": sorted(INDEXES),
        "functions": sorted(FUNCTIONS),
        "triggers": sorted(TRIGGERS),
    }
    return {
        "schemaReady": not blockers and not changes,
        "readyForApply": not blockers,
        "blockers": blockers,
        "missingPlanColumns": missing_plan_columns,
        "missingEntryColumns": missing_entry_columns,
        "changes": changes,
        "expected": expected,
    }


def schema_plan_sha256(changes):
    normalized = [
        {"name": item["name"], "sql": " ".join(item["sql"].split())}
        for item in changes or []
    ]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_catalog(cur):
    cur.execute("""
        SELECT
          to_regclass('public.estimate_row_transfer_plans') IS NOT NULL AS plans_table,
          to_regclass('public.estimate_row_transfer_entries') IS NOT NULL AS entries_table,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relname='estimate_row_transfer_plans'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS plan_columns,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relname='estimate_row_transfer_entries'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS entry_columns,
          COALESCE((SELECT array_agg(c.conname ORDER BY c.conname)
            FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
           WHERE n.nspname='public' AND t.relname IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries')),ARRAY[]::text[])
            AS constraints,
          COALESCE((SELECT array_agg(indexname ORDER BY indexname)
            FROM pg_indexes WHERE schemaname='public' AND tablename IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries')),ARRAY[]::text[])
            AS indexes,
          COALESCE((SELECT array_agg(p.proname ORDER BY p.proname)
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN
             ('reject_estimate_row_transfer_entry_mutation',
              'guard_estimate_row_transfer_plan_mutation')),ARRAY[]::text[])
            AS functions,
          COALESCE((SELECT array_agg(tg.tgname ORDER BY tg.tgname)
            FROM pg_trigger tg JOIN pg_class c ON c.oid=tg.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT tg.tgisinternal AND tg.tgname IN
             ('estimate_row_transfer_entry_immutable',
              'estimate_row_transfer_plan_guard')),ARRAY[]::text[])
            AS triggers
    """)
    return dict(cur.fetchone() or {})


def run_schema_migration(
    get_db,
    *,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    if apply:
        if (
            isinstance(expected_change_count, bool)
            or not isinstance(expected_change_count, int)
            or expected_change_count < 0
            or not PLAN_SHA256_RE.fullmatch(str(expected_plan_sha256 or ""))
        ):
            raise SchemaMigrationError("schema_apply_guard_invalid")
    conn = get_db()
    cur = None
    try:
        conn.set_session(autocommit=False, isolation_level="SERIALIZABLE")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SET LOCAL statement_timeout='30s'")
        if apply:
            cur.execute("SELECT pg_advisory_xact_lock(8242002)")
        before = build_schema_plan(_load_catalog(cur))
        plan_hash = schema_plan_sha256(before["changes"])
        if not before["readyForApply"]:
            raise SchemaMigrationError("schema_catalog_blocked")
        if apply and (
            expected_change_count != len(before["changes"])
            or expected_plan_sha256 != plan_hash
        ):
            raise SchemaMigrationError("schema_apply_guard_mismatch")

        if not apply:
            conn.rollback()
            return {
                "ok": True,
                "dryRun": True,
                "rolledBack": True,
                "committed": False,
                "writesAttempted": 0,
                "schemaReady": before["schemaReady"],
                "readyForApply": before["readyForApply"],
                "blockers": before["blockers"],
                "changeCount": len(before["changes"]),
                "changes": [item["name"] for item in before["changes"]],
                "planSha256": plan_hash,
            }

        writes_attempted = 0
        for change in before["changes"]:
            cur.execute(change["sql"])
            writes_attempted += 1
        after = build_schema_plan(_load_catalog(cur))
        if not after["schemaReady"]:
            raise SchemaMigrationError(
                "schema_postcheck_failed:"
                + json.dumps({
                    "blockers": after["blockers"],
                    "missingPlanColumns": after["missingPlanColumns"],
                    "missingEntryColumns": after["missingEntryColumns"],
                    "changes": [item["name"] for item in after["changes"]],
                }, sort_keys=True)
            )
        conn.commit()
        return {
            "ok": True,
            "dryRun": False,
            "rolledBack": False,
            "committed": True,
            "writesAttempted": writes_attempted,
            "schemaReady": True,
            "readyForApply": True,
            "blockers": [],
            "changeCount": len(before["changes"]),
            "changes": [item["name"] for item in before["changes"]],
            "planSha256": plan_hash,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded E4.2 inert ledger schema migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-change-count", type=int)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if not args.apply and (
        args.expected_change_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("apply guards are valid only with --apply")
    if args.apply and (
        args.expected_change_count is None or args.expected_plan_sha256 is None
    ):
        parser.error("--apply requires exact change count and plan SHA-256")
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_schema_migration(
        get_db,
        apply=args.apply,
        expected_change_count=args.expected_change_count,
        expected_plan_sha256=args.expected_plan_sha256,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
