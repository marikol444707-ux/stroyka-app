"""Guarded E6 project-budget exact-money and immutable-receipt migration."""

import argparse
import hashlib
import json
import re

import psycopg2.extras


PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GUARD_V2_MARKER = "e6_guard_v2_reconciliation_totals"

RECEIPT_COLUMNS = {
    "id", "company_id", "project_id", "reconciliation_id",
    "base_estimate_id", "next_estimate_id", "project_budget_before",
    "estimate_base_total", "estimate_next_total", "adjustment_amount",
    "project_budget_after", "plan_sha256", "approved_by_user_id",
    "approved_by_name", "approved_by_role", "approved_at", "created_at",
}

RECEIPT_COLUMN_DEFINITIONS = {
    "id": {"type": "bigint", "notNull": True},
    "company_id": {"type": "integer", "notNull": True},
    "project_id": {"type": "integer", "notNull": True},
    "reconciliation_id": {"type": "integer", "notNull": True},
    "base_estimate_id": {"type": "integer", "notNull": True},
    "next_estimate_id": {"type": "integer", "notNull": True},
    "project_budget_before": {"type": "numeric(14,2)", "notNull": True},
    "estimate_base_total": {"type": "numeric(14,2)", "notNull": True},
    "estimate_next_total": {"type": "numeric(14,2)", "notNull": True},
    "adjustment_amount": {"type": "numeric(14,2)", "notNull": True},
    "project_budget_after": {"type": "numeric(14,2)", "notNull": True},
    "plan_sha256": {"type": "character varying(64)", "notNull": True},
    "approved_by_user_id": {"type": "integer", "notNull": True},
    "approved_by_name": {"type": "character varying(255)", "notNull": True},
    "approved_by_role": {"type": "character varying(100)", "notNull": True},
    "approved_at": {"type": "timestamp with time zone", "notNull": True},
    "created_at": {"type": "timestamp with time zone", "notNull": True},
}

CONSTRAINTS = {
    "pk_project_budget_adjustments",
    "fk_pba_project",
    "fk_pba_reconciliation",
    "fk_pba_base_estimate",
    "fk_pba_next_estimate",
    "fk_pba_approved_user",
    "ck_pba_owner_sources",
    "ck_pba_money",
    "ck_pba_equations",
    "ck_pba_hash",
    "ck_pba_actor",
    "uq_pba_reconciliation",
    "uq_pba_plan_sha256",
}

INDEXES = {"idx_pba_owner_approved"}
FUNCTIONS = {
    "guard_project_budget_adjustment_insert",
    "reject_project_budget_adjustment_mutation",
}
TRIGGERS = {
    "project_budget_adjustment_insert_guard",
    "project_budget_adjustment_immutable",
}

CONSTRAINT_SIGNATURES = {
    "pk_project_budget_adjustments": ("PRIMARY KEY (id)",),
    "fk_pba_project": (
        "FOREIGN KEY (project_id)", "REFERENCES projects (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_pba_reconciliation": (
        "FOREIGN KEY (reconciliation_id)",
        "REFERENCES estimate_reconciliations (id)", "ON DELETE RESTRICT",
    ),
    "fk_pba_base_estimate": (
        "FOREIGN KEY (base_estimate_id)", "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_pba_next_estimate": (
        "FOREIGN KEY (next_estimate_id)", "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_pba_approved_user": (
        "FOREIGN KEY (approved_by_user_id)", "REFERENCES users (id)",
        "ON DELETE RESTRICT",
    ),
    "ck_pba_owner_sources": (
        "company_id > 0", "project_id > 0", "reconciliation_id > 0",
        "base_estimate_id > 0", "next_estimate_id > 0",
        "base_estimate_id <> next_estimate_id",
    ),
    "ck_pba_money": (
        "project_budget_before >= 0", "estimate_base_total >= 0",
        "estimate_next_total >= 0", "project_budget_after >= 0",
        "project_budget_before < 1000000000000.00",
        "estimate_base_total < 1000000000000.00",
        "estimate_next_total < 1000000000000.00",
        "project_budget_after < 1000000000000.00",
    ),
    "ck_pba_equations": (
        "adjustment_amount = estimate_next_total - estimate_base_total",
        "project_budget_after = project_budget_before + adjustment_amount",
        "adjustment_amount <> 0",
    ),
    "ck_pba_hash": ("plan_sha256", "[0-9a-f]{64}"),
    "ck_pba_actor": (
        "approved_by_user_id > 0", "approved_by_name", "approved_by_role",
        "директор", "зам_директора",
    ),
    "uq_pba_reconciliation": ("UNIQUE (reconciliation_id)",),
    "uq_pba_plan_sha256": ("UNIQUE (plan_sha256)",),
}

INDEX_SIGNATURES = {
    "idx_pba_owner_approved": (
        "project_budget_adjustments", "company_id", "project_id",
        "approved_at DESC", "id DESC",
    ),
}

FUNCTION_SIGNATURES = {
    "guard_project_budget_adjustment_insert": (
        "RETURNS trigger", "projects", "estimate_reconciliations",
        "estimates", "user_company_roles", "NEW.company_id",
        "NEW.project_id", "NEW.reconciliation_id", "NEW.base_estimate_id",
        "NEW.next_estimate_id", "NEW.project_budget_before",
        "NEW.estimate_base_total", "NEW.estimate_next_total",
        "p.budget=NEW.project_budget_before",
        "r.base_estimate_id=NEW.base_estimate_id",
        "r.next_estimate_id=NEW.next_estimate_id",
        "r.base_total=NEW.estimate_base_total",
        "r.next_total=NEW.estimate_next_total",
        "actor.role=NEW.approved_by_role",
        "COALESCE(actor.active,TRUE)=TRUE",
        "Утверждена", "Заказчик", "Активная",
        "project_budget_adjustment_source_invalid",
    ),
    "reject_project_budget_adjustment_mutation": (
        "RETURNS trigger", "project_budget_adjustment_immutable",
    ),
}

TRIGGER_SIGNATURES = {
    "project_budget_adjustment_insert_guard": (
        "BEFORE INSERT", "project_budget_adjustments",
        "guard_project_budget_adjustment_insert",
    ),
    "project_budget_adjustment_immutable": (
        "BEFORE", "UPDATE", "DELETE", "project_budget_adjustments",
        "reject_project_budget_adjustment_mutation",
    ),
}


def _guard_function_sql(*, replace):
    create = "CREATE OR REPLACE" if replace else "CREATE"
    return f"""
        {create} FUNCTION public.guard_project_budget_adjustment_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          -- {GUARD_V2_MARKER}
          IF NOT EXISTS (
            SELECT 1
              FROM public.projects p
              JOIN public.estimate_reconciliations r
                ON r.id=NEW.reconciliation_id
              JOIN public.estimates base_estimate
                ON base_estimate.id=NEW.base_estimate_id
              JOIN public.estimates next_estimate
                ON next_estimate.id=NEW.next_estimate_id
             WHERE p.id=NEW.project_id
               AND p.company_id=NEW.company_id
               AND p.budget=NEW.project_budget_before
               AND r.base_estimate_id=NEW.base_estimate_id
               AND r.next_estimate_id=NEW.next_estimate_id
               AND r.status='Утверждена'
               AND COALESCE(NULLIF(r.smeta_type,''),'Заказчик')='Заказчик'
               AND base_estimate.company_id=NEW.company_id
               AND base_estimate.project_id=NEW.project_id
               AND COALESCE(NULLIF(base_estimate.smeta_type,''),'Заказчик')='Заказчик'
               AND next_estimate.company_id=NEW.company_id
               AND next_estimate.project_id=NEW.project_id
               AND COALESCE(NULLIF(next_estimate.smeta_type,''),'Заказчик')='Заказчик'
               AND next_estimate.status='Активная'
               AND r.base_total=NEW.estimate_base_total
               AND r.next_total=NEW.estimate_next_total
               AND COALESCE(NULLIF(r.work_package,''),'Основная')
                   =COALESCE(NULLIF(base_estimate.work_package,''),'Основная')
               AND COALESCE(NULLIF(r.work_package,''),'Основная')
                   =COALESCE(NULLIF(next_estimate.work_package,''),'Основная')
               AND EXISTS (
                 SELECT 1
                   FROM public.user_company_roles actor
                  WHERE actor.user_id=NEW.approved_by_user_id
                    AND actor.company_id=NEW.company_id
                    AND actor.role=NEW.approved_by_role
                    AND actor.role IN ('директор','зам_директора')
                    AND COALESCE(actor.active,TRUE)=TRUE
               )
          ) THEN
            RAISE EXCEPTION 'project_budget_adjustment_source_invalid'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$
    """


CHANGE_DEFINITIONS = (
    (
        "alter_project_budget_numeric",
        "budget_numeric",
        """
        ALTER TABLE public.projects
          ALTER COLUMN budget TYPE NUMERIC(14,2)
            USING budget::numeric(14,2),
          ALTER COLUMN budget SET DEFAULT 0.00
        """,
    ),
    (
        "create_project_budget_adjustments_table",
        "receipt_table",
        """
        CREATE TABLE public.project_budget_adjustments (
          id BIGSERIAL CONSTRAINT pk_project_budget_adjustments PRIMARY KEY,
          company_id INTEGER NOT NULL,
          project_id INTEGER NOT NULL,
          reconciliation_id INTEGER NOT NULL,
          base_estimate_id INTEGER NOT NULL,
          next_estimate_id INTEGER NOT NULL,
          project_budget_before NUMERIC(14,2) NOT NULL,
          estimate_base_total NUMERIC(14,2) NOT NULL,
          estimate_next_total NUMERIC(14,2) NOT NULL,
          adjustment_amount NUMERIC(14,2) NOT NULL,
          project_budget_after NUMERIC(14,2) NOT NULL,
          plan_sha256 VARCHAR(64) NOT NULL,
          approved_by_user_id INTEGER NOT NULL,
          approved_by_name VARCHAR(255) NOT NULL,
          approved_by_role VARCHAR(100) NOT NULL,
          approved_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT fk_pba_project FOREIGN KEY (project_id)
            REFERENCES public.projects(id) ON DELETE RESTRICT,
          CONSTRAINT fk_pba_reconciliation FOREIGN KEY (reconciliation_id)
            REFERENCES public.estimate_reconciliations(id) ON DELETE RESTRICT,
          CONSTRAINT fk_pba_base_estimate FOREIGN KEY (base_estimate_id)
            REFERENCES public.estimates(id) ON DELETE RESTRICT,
          CONSTRAINT fk_pba_next_estimate FOREIGN KEY (next_estimate_id)
            REFERENCES public.estimates(id) ON DELETE RESTRICT,
          CONSTRAINT fk_pba_approved_user FOREIGN KEY (approved_by_user_id)
            REFERENCES public.users(id) ON DELETE RESTRICT,
          CONSTRAINT ck_pba_owner_sources CHECK (
            company_id>0 AND project_id>0 AND reconciliation_id>0
            AND base_estimate_id>0 AND next_estimate_id>0
            AND base_estimate_id<>next_estimate_id
          ),
          CONSTRAINT ck_pba_money CHECK (
            project_budget_before>=0
            AND estimate_base_total>=0 AND estimate_next_total>=0
            AND project_budget_after>=0
            AND project_budget_before<1000000000000.00
            AND estimate_base_total<1000000000000.00
            AND estimate_next_total<1000000000000.00
            AND project_budget_after<1000000000000.00
          ),
          CONSTRAINT ck_pba_equations CHECK (
            adjustment_amount=estimate_next_total-estimate_base_total
            AND project_budget_after=project_budget_before+adjustment_amount
            AND adjustment_amount<>0
          ),
          CONSTRAINT ck_pba_hash CHECK (
            plan_sha256 ~ '^[0-9a-f]{64}$'
          ),
          CONSTRAINT ck_pba_actor CHECK (
            approved_by_user_id>0 AND BTRIM(approved_by_name)<>''
            AND approved_by_role IN ('директор','зам_директора')
          ),
          CONSTRAINT uq_pba_reconciliation UNIQUE (reconciliation_id),
          CONSTRAINT uq_pba_plan_sha256 UNIQUE (plan_sha256)
        )
        """,
    ),
    (
        "create_project_budget_adjustment_owner_index",
        "idx_pba_owner_approved",
        """
        CREATE INDEX idx_pba_owner_approved
          ON public.project_budget_adjustments
          (company_id,project_id,approved_at DESC,id DESC)
        """,
    ),
    (
        "create_project_budget_adjustment_insert_guard_function",
        "guard_project_budget_adjustment_insert",
        _guard_function_sql(replace=False),
    ),
    (
        "replace_project_budget_adjustment_insert_guard_function_v2",
        "guard_function_v2",
        _guard_function_sql(replace=True),
    ),
    (
        "create_project_budget_adjustment_insert_guard_trigger",
        "project_budget_adjustment_insert_guard",
        """
        CREATE TRIGGER project_budget_adjustment_insert_guard
          BEFORE INSERT ON public.project_budget_adjustments
          FOR EACH ROW
          EXECUTE FUNCTION public.guard_project_budget_adjustment_insert()
        """,
    ),
    (
        "create_project_budget_adjustment_immutable_function",
        "reject_project_budget_adjustment_mutation",
        """
        CREATE FUNCTION public.reject_project_budget_adjustment_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'project_budget_adjustment_immutable'
            USING ERRCODE='55000';
        END;
        $$
        """,
    ),
    (
        "create_project_budget_adjustment_immutable_trigger",
        "project_budget_adjustment_immutable",
        """
        CREATE TRIGGER project_budget_adjustment_immutable
          BEFORE UPDATE OR DELETE ON public.project_budget_adjustments
          FOR EACH ROW
          EXECUTE FUNCTION public.reject_project_budget_adjustment_mutation()
        """,
    ),
)


class SchemaMigrationError(RuntimeError):
    pass


def _values(catalog, key):
    return {str(value) for value in (catalog.get(key) or [])}


def _compact_definition(value):
    compact = re.sub(r'[\s"()]', "", str(value or "").lower())
    return compact.replace("public.", "")


def _invalid_definitions(present_names, definitions, signatures):
    definitions = dict(definitions or {})
    invalid = []
    for name, required_fragments in signatures.items():
        if name not in present_names:
            continue
        actual = _compact_definition(definitions.get(name))
        if not actual or any(
            _compact_definition(fragment) not in actual
            for fragment in required_fragments
        ):
            invalid.append(name)
    return invalid


def _guard_v2(catalog):
    definitions = dict(catalog.get("function_definitions") or {})
    actual = _compact_definition(
        definitions.get("guard_project_budget_adjustment_insert")
    )
    return bool(
        GUARD_V2_MARKER in actual
        and "base_estimate.total" not in actual
        and "next_estimate.total" not in actual
    )


def _budget_exact(catalog):
    return (
        catalog.get("budget_type") == "numeric"
        and catalog.get("budget_udt") == "numeric"
        and catalog.get("budget_precision") == 14
        and catalog.get("budget_scale") == 2
    )


def _budget_float(catalog):
    return (
        catalog.get("budget_type") == "double precision"
        and catalog.get("budget_udt") == "float8"
    )


def _normalized_conversion_audit(audit):
    source = dict(audit or {})
    keys = (
        "rows_total", "null_budget", "non_finite_budget",
        "negative_budget", "out_of_range_budget", "precision_loss_budget",
    )
    return {key: int(source.get(key) or 0) for key in keys}


def _column_definitions_ready(catalog):
    actual = dict(catalog.get("receipt_column_definitions") or {})
    for name, expected in RECEIPT_COLUMN_DEFINITIONS.items():
        value = dict(actual.get(name) or {})
        if value.get("type") != expected["type"]:
            return False
        if bool(value.get("notNull")) is not expected["notNull"]:
            return False
    return True


def build_schema_plan(catalog, conversion_audit=None):
    catalog = dict(catalog or {})
    budget_exact = _budget_exact(catalog)
    budget_float = _budget_float(catalog)
    receipt_table = bool(catalog.get("receipt_table"))
    blockers = []

    if not budget_exact and not budget_float:
        blockers.append("project_budget_column_invalid")

    conversion = _normalized_conversion_audit(conversion_audit)
    unsafe_count = sum(
        conversion[key]
        for key in (
            "null_budget", "non_finite_budget", "negative_budget",
            "out_of_range_budget", "precision_loss_budget",
        )
    )
    conversion_ready = budget_exact or (budget_float and conversion_audit is not None and unsafe_count == 0)
    if budget_float and conversion_audit is None:
        blockers.append("project_budget_conversion_not_audited")
    elif budget_float and unsafe_count:
        blockers.append("project_budget_conversion_unsafe")

    receipt_columns = _values(catalog, "receipt_columns")
    constraints = _values(catalog, "constraints")
    indexes = _values(catalog, "indexes")
    functions = _values(catalog, "functions")
    triggers = _values(catalog, "triggers")
    if receipt_table and (
        receipt_columns != RECEIPT_COLUMNS or not _column_definitions_ready(catalog)
    ):
        blockers.append("receipt_columns_invalid")
    if receipt_table and not CONSTRAINTS.issubset(constraints):
        blockers.append("receipt_constraints_invalid")

    for prefix, names in (
        ("invalidConstraint", _invalid_definitions(
            constraints, catalog.get("constraint_definitions"),
            CONSTRAINT_SIGNATURES,
        )),
        ("invalidIndex", _invalid_definitions(
            indexes, catalog.get("index_definitions"), INDEX_SIGNATURES,
        )),
        ("invalidFunction", _invalid_definitions(
            functions, catalog.get("function_definitions"),
            FUNCTION_SIGNATURES,
        )),
        ("invalidTrigger", _invalid_definitions(
            triggers, catalog.get("trigger_definitions"), TRIGGER_SIGNATURES,
        )),
    ):
        blockers.extend("{}:{}".format(prefix, name) for name in names)

    changes = []
    for name, object_name, sql in CHANGE_DEFINITIONS:
        if object_name == "budget_numeric":
            missing = not budget_exact
        elif object_name == "receipt_table":
            missing = not receipt_table
        elif object_name == "guard_function_v2":
            missing = (
                "guard_project_budget_adjustment_insert" in functions
                and not _guard_v2(catalog)
            )
        elif object_name in INDEXES:
            missing = object_name not in indexes
        elif object_name in FUNCTIONS:
            missing = object_name not in functions
        else:
            missing = object_name not in triggers
        if missing:
            changes.append({"name": name, "sql": sql.strip()})

    expected_function_definitions = {
        name: " ".join(parts)
        for name, parts in sorted(FUNCTION_SIGNATURES.items())
    }
    expected_function_definitions[
        "guard_project_budget_adjustment_insert"
    ] += " " + GUARD_V2_MARKER
    expected = {
        "receiptColumns": sorted(RECEIPT_COLUMNS),
        "receiptColumnDefinitions": RECEIPT_COLUMN_DEFINITIONS,
        "constraints": sorted(CONSTRAINTS),
        "indexes": sorted(INDEXES),
        "functions": sorted(FUNCTIONS),
        "triggers": sorted(TRIGGERS),
        "constraintDefinitions": {
            name: " ".join(parts)
            for name, parts in sorted(CONSTRAINT_SIGNATURES.items())
        },
        "indexDefinitions": {
            name: " ".join(parts)
            for name, parts in sorted(INDEX_SIGNATURES.items())
        },
        "functionDefinitions": expected_function_definitions,
        "triggerDefinitions": {
            name: " ".join(parts)
            for name, parts in sorted(TRIGGER_SIGNATURES.items())
        },
    }
    return {
        "schemaReady": not blockers and not changes,
        "readyForApply": not blockers,
        "budgetColumnExact": budget_exact,
        "conversionReady": conversion_ready,
        "conversionAudit": conversion,
        "blockers": blockers,
        "changes": changes,
        "expected": expected,
    }


def schema_plan_sha256(changes):
    normalized = [
        {"name": item["name"], "sql": " ".join(item["sql"].split())}
        for item in (changes or [])
    ]
    payload = json.dumps(
        normalized, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_catalog(cur):
    cur.execute("""
        SELECT
          (SELECT data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name='projects'
              AND column_name='budget') AS budget_type,
          (SELECT udt_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='projects'
              AND column_name='budget') AS budget_udt,
          (SELECT numeric_precision FROM information_schema.columns
            WHERE table_schema='public' AND table_name='projects'
              AND column_name='budget') AS budget_precision,
          (SELECT numeric_scale FROM information_schema.columns
            WHERE table_schema='public' AND table_name='projects'
              AND column_name='budget') AS budget_scale,
          to_regclass('public.project_budget_adjustments') IS NOT NULL
            AS receipt_table,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='project_budget_adjustments'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS receipt_columns,
          COALESCE((SELECT jsonb_object_agg(
              a.attname,
              jsonb_build_object(
                'type',format_type(a.atttypid,a.atttypmod),
                'notNull',a.attnotnull
              )
            )
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='project_budget_adjustments'
             AND a.attnum>0 AND NOT a.attisdropped),'{}'::jsonb)
            AS receipt_column_definitions,
          COALESCE((SELECT array_agg(con.conname ORDER BY con.conname)
            FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='project_budget_adjustments'),ARRAY[]::text[])
            AS constraints,
          COALESCE((SELECT jsonb_object_agg(
              con.conname,pg_get_constraintdef(con.oid,true))
            FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='project_budget_adjustments'),'{}'::jsonb)
            AS constraint_definitions,
          COALESCE((SELECT array_agg(indexname ORDER BY indexname)
            FROM pg_indexes WHERE schemaname='public'
              AND tablename='project_budget_adjustments'),ARRAY[]::text[])
            AS indexes,
          COALESCE((SELECT jsonb_object_agg(indexname,indexdef)
            FROM pg_indexes WHERE schemaname='public'
              AND tablename='project_budget_adjustments'),'{}'::jsonb)
            AS index_definitions,
          COALESCE((SELECT array_agg(p.proname ORDER BY p.proname)
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN
             ('guard_project_budget_adjustment_insert',
              'reject_project_budget_adjustment_mutation')
             AND p.pronargs=0),ARRAY[]::text[]) AS functions,
          COALESCE((SELECT jsonb_object_agg(p.proname,pg_get_functiondef(p.oid))
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN
             ('guard_project_budget_adjustment_insert',
              'reject_project_budget_adjustment_mutation')
             AND p.pronargs=0),'{}'::jsonb) AS function_definitions,
          COALESCE((SELECT array_agg(t.tgname ORDER BY t.tgname)
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT t.tgisinternal
             AND t.tgname IN
             ('project_budget_adjustment_insert_guard',
              'project_budget_adjustment_immutable')),ARRAY[]::text[])
            AS triggers,
          COALESCE((SELECT jsonb_object_agg(
              t.tgname,pg_get_triggerdef(t.oid,true))
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT t.tgisinternal
             AND t.tgname IN
             ('project_budget_adjustment_insert_guard',
              'project_budget_adjustment_immutable')),'{}'::jsonb)
            AS trigger_definitions
    """)
    return dict(cur.fetchone() or {})


def _load_conversion_audit(cur):
    cur.execute("""
        SELECT
          COUNT(*)::bigint AS rows_total,
          COUNT(*) FILTER (WHERE budget IS NULL)::bigint AS null_budget,
          COUNT(*) FILTER (
            WHERE budget::text IN ('NaN','Infinity','-Infinity')
          )::bigint AS non_finite_budget,
          COUNT(*) FILTER (
            WHERE budget<0
              AND budget::text NOT IN ('NaN','Infinity','-Infinity')
          )::bigint AS negative_budget,
          COUNT(*) FILTER (
            WHERE budget>=1000000000000.00
              AND budget::text NOT IN ('NaN','Infinity','-Infinity')
          )::bigint AS out_of_range_budget,
          SUM(CASE
            WHEN budget IS NULL
              OR budget::text IN ('NaN','Infinity','-Infinity')
              OR budget<0 OR budget>=1000000000000.00 THEN 0
            WHEN budget=(budget::numeric(14,2))::double precision THEN 0
            ELSE 1
          END)::bigint AS precision_loss_budget
        FROM public.projects
    """)
    return _normalized_conversion_audit(cur.fetchone())


def _report(plan, plan_hash, *, dry_run, writes_attempted=0):
    return {
        "ok": plan["readyForApply"],
        "dryRun": dry_run,
        "rolledBack": dry_run,
        "committed": not dry_run,
        "writesAttempted": writes_attempted,
        "schemaReady": plan["schemaReady"],
        "readyForApply": plan["readyForApply"],
        "budgetColumnExact": plan["budgetColumnExact"],
        "conversionReady": plan["conversionReady"],
        "conversionAudit": plan["conversionAudit"],
        "blockers": plan["blockers"],
        "changeCount": len(plan["changes"]),
        "changes": [change["name"] for change in plan["changes"]],
        "planSha256": plan_hash,
    }


def _current_plan(cur):
    catalog = _load_catalog(cur)
    conversion_audit = (
        _load_conversion_audit(cur) if _budget_float(catalog) else None
    )
    return build_schema_plan(catalog, conversion_audit)


def run_schema_migration(
    get_db,
    *,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    if apply and (
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
            cur.execute("SELECT pg_advisory_xact_lock(8246002)")

        before = _current_plan(cur)
        plan_hash = schema_plan_sha256(before["changes"])

        if not apply:
            conn.rollback()
            return _report(before, plan_hash, dry_run=True)
        if not before["readyForApply"]:
            raise SchemaMigrationError("schema_catalog_blocked")
        if (
            expected_change_count != len(before["changes"])
            or expected_plan_sha256 != plan_hash
        ):
            raise SchemaMigrationError("schema_apply_guard_mismatch")

        # Prevent a concurrent manual writer from introducing a value after the
        # lossless audit but before PostgreSQL converts the float column.
        cur.execute("LOCK TABLE public.projects IN ACCESS EXCLUSIVE MODE")
        locked = _current_plan(cur)
        locked_hash = schema_plan_sha256(locked["changes"])
        if not locked["readyForApply"]:
            raise SchemaMigrationError("schema_catalog_blocked")
        if (
            expected_change_count != len(locked["changes"])
            or expected_plan_sha256 != locked_hash
        ):
            raise SchemaMigrationError("schema_apply_guard_mismatch")
        before = locked

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
                    "changes": [change["name"] for change in after["changes"]],
                }, sort_keys=True)
            )
        conn.commit()
        report = _report(
            after,
            plan_hash,
            dry_run=False,
            writes_attempted=writes_attempted,
        )
        report.update({
            "changeCount": len(before["changes"]),
            "changes": [change["name"] for change in before["changes"]],
            "conversionAudit": before["conversionAudit"],
        })
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarded E6 project-budget adjustment schema migration"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-change-count", type=int)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if not args.apply and (
        args.expected_change_count is not None
        or args.expected_plan_sha256 is not None
    ):
        parser.error("apply guards are valid only with --apply")
    if args.apply and (
        args.expected_change_count is None
        or args.expected_plan_sha256 is None
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
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
