"""Guarded A8.4b1 migration for authoritative capability evidence."""

import argparse
import json
import sys

import psycopg2.extras

from backend.features.estimate_revision_impact.schema_probe import (
    collect_missing_columns,
)
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


class MaterialCapabilitySchemaMigrationError(RuntimeError):
    """One fixed-code exception boundary for migration failures."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _rows(cur):
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _bounded_rows(cur, limit):
    rows = _rows(cur)
    return rows if len(rows) <= limit else None


def _collect_parent_relations(cur):
    cur.execute(
        """SELECT relation.relname AS object_name,
                  relation.relkind::text AS relkind,
                  relation.relpersistence::text AS persistence
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_class relation
               ON relation.relnamespace=namespace.oid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND relation.relname=ANY(%s)
            LIMIT %s""",
        (
            "public",
            sorted(PARENT_RELATION_CONTRACT),
            len(PARENT_RELATION_CONTRACT) + 1,
        ),
    )
    rows = _bounded_rows(cur, len(PARENT_RELATION_CONTRACT))
    if rows is None:
        return {}, True
    return {
        row.get("object_name"): {
            "relkind": row.get("relkind"),
            "persistence": row.get("persistence"),
        }
        for row in rows if row.get("object_name")
    }, False


def _collect_relation_holders(cur):
    cur.execute(
        """SELECT relation.oid::bigint AS object_oid,
                  relation.relname AS object_name,
                  relation.relkind::text AS relkind,
                  relation.relpersistence::text AS persistence,
                  relation.relrowsecurity AS row_security,
                  relation.relforcerowsecurity AS force_row_security,
                  relation.relhasrules AS has_rules,
                  EXISTS (
                    SELECT 1 FROM pg_catalog.pg_inherits parent_edge
                     WHERE parent_edge.inhrelid=relation.oid LIMIT 1
                  ) AS has_parents,
                  EXISTS (
                    SELECT 1 FROM pg_catalog.pg_inherits child_edge
                     WHERE child_edge.inhparent=relation.oid LIMIT 1
                  ) AS has_children,
                  EXISTS (
                    SELECT 1 FROM pg_catalog.pg_policy policy
                     WHERE policy.polrelid=relation.oid LIMIT 1
                  ) AS has_policies
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_class relation
               ON relation.relnamespace=namespace.oid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND relation.relname=ANY(%s)
            LIMIT %s""",
        ("public", list(RELATION_NAMES), len(RELATION_NAMES) + 1),
    )
    rows = _bounded_rows(cur, len(RELATION_NAMES))
    if rows is None:
        return {}, None, True
    holders = {
        row.get("object_name"): {
            "oid": row.get("object_oid"),
            "relkind": row.get("relkind"),
        }
        for row in rows if row.get("object_name")
    }
    row = next(
        (item for item in rows if item.get("object_name") == TABLE_NAME),
        None,
    )
    table = None
    if row is not None:
        table = {
            "oid": row.get("object_oid"),
            "relkind": row.get("relkind"),
            "persistence": row.get("persistence"),
            "rowSecurity": row.get("row_security") is True,
            "forceRowSecurity": row.get("force_row_security") is True,
            "hasRules": row.get("has_rules") is True,
            "hasParents": row.get("has_parents") is True,
            "hasChildren": row.get("has_children") is True,
            "hasPolicies": row.get("has_policies") is True,
        }
    return holders, table, False


def _collect_type_holder(cur):
    cur.execute(
        """SELECT type_state.oid::bigint AS type_oid,
                  type_state.typtype::text AS type_kind,
                  type_state.typrelid::bigint AS relation_oid
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_type type_state
               ON type_state.typnamespace=namespace.oid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND type_state.typname=%s
            LIMIT %s""",
        ("public", TABLE_NAME, 2),
    )
    rows = _bounded_rows(cur, 1)
    if rows is None:
        return None, True
    if not rows:
        return None, False
    return {
        "oid": rows[0].get("type_oid"),
        "type": rows[0].get("type_kind"),
        "relationOid": rows[0].get("relation_oid"),
    }, False


def _collect_functions(cur):
    names = sorted(FUNCTION_CONTRACT)
    cur.execute(
        """SELECT procedure.proname AS object_name,
                  language.lanname AS language,
                  pg_catalog.pg_get_function_result(procedure.oid)
                    AS result_type,
                  procedure.prokind::text AS kind,
                  procedure.prosecdef AS security_definer,
                  procedure.proleakproof AS leakproof,
                  procedure.provolatile::text AS volatility,
                  procedure.proparallel::text AS parallel,
                  procedure.proisstrict AS strict,
                  COALESCE(procedure.proconfig,ARRAY[]::text[]) AS config,
                  procedure.prosrc AS body
             FROM pg_catalog.pg_proc procedure
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=procedure.pronamespace
             JOIN pg_catalog.pg_language language
               ON language.oid=procedure.prolang
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND procedure.proname=ANY(%s)
              AND procedure.pronargs=0
            LIMIT %s""",
        ("public", names, len(names) + 1),
    )
    rows = _bounded_rows(cur, len(names))
    if rows is None:
        return {}, True
    return {
        row.get("object_name"): {
            "language": row.get("language"),
            "returns": row.get("result_type"),
            "kind": row.get("kind"),
            "securityDefiner": row.get("security_definer") is True,
            "leakproof": row.get("leakproof") is True,
            "volatility": row.get("volatility"),
            "parallel": row.get("parallel"),
            "strict": row.get("strict") is True,
            "config": [str(item) for item in (row.get("config") or [])],
            "bodySha256": _body_sha256(row.get("body")),
        }
        for row in rows if row.get("object_name")
    }, False


def _collect_columns(cur, table_oid):
    cur.execute(
        """SELECT attribute.attname AS column_name,
                  attribute.attnum::integer AS position,
                  pg_catalog.format_type(
                      attribute.atttypid,attribute.atttypmod
                  ) AS data_type,
                  attribute.attnotnull AS not_null,
                  attribute.attidentity::text AS identity_kind,
                  attribute.attgenerated::text AS generated_kind,
                  pg_catalog.pg_get_expr(
                      default_value.adbin,default_value.adrelid,true
                  ) AS default_expression,
                  CASE WHEN attribute.attcollation=0 THEN NULL
                       ELSE collation_namespace.nspname || '.' ||
                            collation_state.collname END AS collation_name
             FROM pg_catalog.pg_attribute attribute
             LEFT JOIN pg_catalog.pg_attrdef default_value
               ON default_value.adrelid=attribute.attrelid
              AND default_value.adnum=attribute.attnum
             LEFT JOIN pg_catalog.pg_collation collation_state
               ON collation_state.oid=attribute.attcollation
             LEFT JOIN pg_catalog.pg_namespace collation_namespace
               ON collation_namespace.oid=collation_state.collnamespace
            WHERE attribute.attrelid=%s
              AND attribute.attnum>0
              AND NOT attribute.attisdropped
            LIMIT %s""",
        (table_oid, len(COLUMN_CONTRACT) + 1),
    )
    rows = _bounded_rows(cur, len(COLUMN_CONTRACT))
    if rows is None:
        return {}, True
    return {
        row.get("column_name"): {
            "position": row.get("position"),
            "type": row.get("data_type"),
            "notNull": row.get("not_null") is True,
            "default": (
                None if row.get("default_expression") is None
                else _canonical_sql(row.get("default_expression"))
            ),
            "identity": row.get("identity_kind") or "",
            "generated": row.get("generated_kind") or "",
            "collation": row.get("collation_name"),
        }
        for row in rows if row.get("column_name")
    }, False


def _collect_identity_sequence(cur, table_oid):
    cur.execute(
        """SELECT sequence_relation.oid::bigint AS sequence_oid,
                  sequence_relation.relname AS sequence_name,
                  sequence_relation.relkind::text AS relkind,
                  pg_catalog.format_type(
                    sequence_state.seqtypid,NULL
                  ) AS data_type,
                  sequence_state.seqstart::bigint AS start_value,
                  sequence_state.seqincrement::bigint AS increment_value,
                  sequence_state.seqmin::bigint AS minimum_value,
                  sequence_state.seqmax::bigint AS maximum_value,
                  sequence_state.seqcache::bigint AS cache_value,
                  sequence_state.seqcycle AS cycle,
                  dependency.refobjid::bigint AS table_oid,
                  owned_attribute.attname AS owned_column,
                  dependency.deptype::text AS dependency_type
             FROM pg_catalog.pg_namespace namespace
             JOIN pg_catalog.pg_class sequence_relation
               ON sequence_relation.relnamespace=namespace.oid
             JOIN pg_catalog.pg_sequence sequence_state
               ON sequence_state.seqrelid=sequence_relation.oid
             JOIN pg_catalog.pg_depend dependency
               ON dependency.classid='pg_catalog.pg_class'::regclass
              AND dependency.objid=sequence_relation.oid
              AND dependency.objsubid=0
              AND dependency.refclassid='pg_catalog.pg_class'::regclass
              AND dependency.refobjid=%s
              AND dependency.deptype='i'
             JOIN pg_catalog.pg_attribute owned_attribute
               ON owned_attribute.attrelid=dependency.refobjid
              AND owned_attribute.attnum=dependency.refobjsubid
            WHERE namespace.nspname=%s
              AND NOT pg_catalog.pg_is_other_temp_schema(namespace.oid)
              AND sequence_relation.relname=%s
            LIMIT %s""",
        (table_oid, "public", IDENTITY_SEQUENCE_NAME, 2),
    )
    rows = _bounded_rows(cur, 1)
    if rows is None:
        return None, True
    if not rows:
        return None, False
    row = rows[0]
    return {
        "oid": row.get("sequence_oid"),
        "tableOid": row.get("table_oid"),
        "name": row.get("sequence_name"),
        "relkind": row.get("relkind"),
        "dataType": row.get("data_type"),
        "start": row.get("start_value"),
        "increment": row.get("increment_value"),
        "minimum": row.get("minimum_value"),
        "maximum": row.get("maximum_value"),
        "cache": row.get("cache_value"),
        "cycle": row.get("cycle") is True,
        "ownedColumn": row.get("owned_column"),
        "dependencyType": row.get("dependency_type"),
    }, False


def _collect_constraints(cur, table_oid):
    cur.execute(
        """SELECT constraint_state.conname AS object_name,
                  constraint_state.contype::text AS constraint_type,
                  constraint_state.convalidated AS validated,
                  constraint_state.condeferrable AS deferrable,
                  constraint_state.condeferred AS deferred,
                  constraint_state.connoinherit AS no_inherit,
                  constraint_state.coninhcount::integer AS inherited_count,
                  constraint_state.conparentid<>0 AS has_parent,
                  constraint_state.confrelid=%s AS references_self,
                  pg_catalog.pg_get_constraintdef(
                      constraint_state.oid,true
                  ) AS definition
             FROM pg_catalog.pg_constraint constraint_state
            WHERE constraint_state.conrelid=%s
            LIMIT %s""",
        (table_oid, table_oid, len(CONSTRAINT_CONTRACT) + 1),
    )
    rows = _bounded_rows(cur, len(CONSTRAINT_CONTRACT))
    if rows is None:
        return {}, True
    return {
        row.get("object_name"): {
            "type": row.get("constraint_type"),
            "validated": row.get("validated") is True,
            "deferrable": row.get("deferrable") is True,
            "deferred": row.get("deferred") is True,
            "definition": _canonical_sql(row.get("definition")),
            "noInherit": row.get("no_inherit") is True,
            "inheritedCount": row.get("inherited_count"),
            "hasParent": row.get("has_parent") is True,
            "referencesSelf": row.get("references_self") is True,
        }
        for row in rows if row.get("object_name")
    }, False


def _collect_indexes(cur, table_oid):
    cur.execute(
        """SELECT index_relation.oid::bigint AS index_oid,
                  index_relation.relname AS index_name,
                  index_state.indrelid::bigint AS table_oid,
                  access_method.amname AS access_method,
                  index_state.indisunique AS is_unique,
                  index_state.indisprimary AS is_primary,
                  index_state.indisexclusion AS is_exclusion,
                  index_state.indisvalid AS is_valid,
                  index_state.indisready AS is_ready,
                  index_state.indislive AS is_live,
                  index_state.indcheckxmin AS check_xmin,
                  index_state.indexprs IS NOT NULL AS has_expressions,
                  index_state.indnkeyatts::integer AS key_count,
                  index_state.indnatts::integer AS attribute_count,
                  pg_catalog.pg_get_expr(
                    index_state.indpred,index_state.indrelid,true
                  ) AS predicate,
                  ARRAY(
                    SELECT attribute.attname
                      FROM pg_catalog.unnest(
                        index_state.indkey::smallint[]
                      ) WITH ORDINALITY key_position(attnum,ordinality)
                      LEFT JOIN pg_catalog.pg_attribute attribute
                        ON attribute.attrelid=index_state.indrelid
                       AND attribute.attnum=key_position.attnum
                     WHERE key_position.ordinality<=index_state.indnkeyatts
                     ORDER BY key_position.ordinality
                  ) AS key_names,
                  ARRAY(
                    SELECT option_position.option::integer
                      FROM pg_catalog.unnest(
                        index_state.indoption::smallint[]
                      ) WITH ORDINALITY option_position(option,ordinality)
                     WHERE option_position.ordinality<=index_state.indnkeyatts
                     ORDER BY option_position.ordinality
                  ) AS key_options,
                  ARRAY(
                    SELECT class_namespace.nspname || '.' ||
                           operator_class.opcname
                      FROM pg_catalog.unnest(
                        index_state.indclass::oid[]
                      ) WITH ORDINALITY class_position(class_oid,ordinality)
                      JOIN pg_catalog.pg_opclass operator_class
                        ON operator_class.oid=class_position.class_oid
                      JOIN pg_catalog.pg_namespace class_namespace
                        ON class_namespace.oid=operator_class.opcnamespace
                     WHERE class_position.ordinality<=index_state.indnkeyatts
                     ORDER BY class_position.ordinality
                  ) AS operator_classes,
                  COALESCE((
                    SELECT pg_catalog.bool_and(
                      collation_position.collation_oid=
                      COALESCE(attribute.attcollation,0)
                    )
                      FROM pg_catalog.unnest(
                        index_state.indcollation::oid[]
                      ) WITH ORDINALITY
                        collation_position(collation_oid,ordinality)
                      LEFT JOIN pg_catalog.unnest(
                        index_state.indkey::smallint[]
                      ) WITH ORDINALITY key_position(attnum,ordinality)
                        USING (ordinality)
                      LEFT JOIN pg_catalog.pg_attribute attribute
                        ON attribute.attrelid=index_state.indrelid
                       AND attribute.attnum=key_position.attnum
                     WHERE collation_position.ordinality<=
                           index_state.indnkeyatts
                  ),FALSE) AS collations_match_columns
             FROM pg_catalog.pg_index index_state
             JOIN pg_catalog.pg_class index_relation
               ON index_relation.oid=index_state.indexrelid
             JOIN pg_catalog.pg_namespace index_namespace
               ON index_namespace.oid=index_relation.relnamespace
             JOIN pg_catalog.pg_am access_method
               ON access_method.oid=index_relation.relam
            WHERE index_state.indrelid=%s
              AND index_namespace.nspname=%s
            LIMIT %s""",
        (table_oid, "public", len(INDEX_CONTRACT) + 1),
    )
    rows = _bounded_rows(cur, len(INDEX_CONTRACT))
    if rows is None:
        return {}, True
    return {
        row.get("index_name"): {
            "oid": row.get("index_oid"),
            "tableOid": row.get("table_oid"),
            "accessMethod": row.get("access_method"),
            "unique": row.get("is_unique") is True,
            "primary": row.get("is_primary") is True,
            "exclusion": row.get("is_exclusion") is True,
            "valid": row.get("is_valid") is True,
            "ready": row.get("is_ready") is True,
            "live": row.get("is_live") is True,
            "checkXmin": row.get("check_xmin") is True,
            "hasExpressions": row.get("has_expressions") is True,
            "predicate": (
                None if row.get("predicate") is None
                else _canonical_sql(row.get("predicate"))
            ),
            "keyCount": row.get("key_count"),
            "attributeCount": row.get("attribute_count"),
            "keyNames": [
                item if item is None else str(item)
                for item in (row.get("key_names") or [])
            ],
            "keyOptions": [
                int(item) for item in (row.get("key_options") or [])
            ],
            "operatorClasses": [
                str(item) for item in (row.get("operator_classes") or [])
            ],
            "collationsMatchColumns": (
                row.get("collations_match_columns") is True
            ),
        }
        for row in rows if row.get("index_name")
    }, False


def _collect_triggers(cur, table_oid):
    cur.execute(
        """SELECT trigger_state.tgname AS object_name,
                  trigger_state.tgenabled::text AS enabled,
                  trigger_state.tgtype::integer AS trigger_type,
                  function_namespace.nspname || '.' ||
                    function_state.proname AS function_name,
                  pg_catalog.pg_get_expr(
                    trigger_state.tgqual,trigger_state.tgrelid,true
                  ) AS condition,
                  pg_catalog.encode(trigger_state.tgargs,'hex')
                    AS arguments_hex,
                  trigger_state.tgattr::smallint[] AS columns,
                  trigger_state.tgconstraint<>0 AS is_constraint,
                  trigger_state.tgdeferrable AS deferrable,
                  trigger_state.tginitdeferred AS initially_deferred,
                  trigger_state.tgoldtable AS old_table,
                  trigger_state.tgnewtable AS new_table
             FROM pg_catalog.pg_trigger trigger_state
             JOIN pg_catalog.pg_proc function_state
               ON function_state.oid=trigger_state.tgfoid
             JOIN pg_catalog.pg_namespace function_namespace
               ON function_namespace.oid=function_state.pronamespace
            WHERE trigger_state.tgrelid=%s
              AND NOT trigger_state.tgisinternal
            LIMIT %s""",
        (table_oid, len(TRIGGER_CONTRACT) + 1),
    )
    rows = _bounded_rows(cur, len(TRIGGER_CONTRACT))
    if rows is None:
        return {}, True
    return {
        row.get("object_name"): {
            "enabled": row.get("enabled"),
            "type": row.get("trigger_type"),
            "function": row.get("function_name"),
            "condition": (
                None if row.get("condition") is None
                else _canonical_sql(row.get("condition"))
            ),
            "argumentsHex": row.get("arguments_hex") or "",
            "columns": [
                int(item) for item in (row.get("columns") or [])
            ],
            "constraint": row.get("is_constraint") is True,
            "deferrable": row.get("deferrable") is True,
            "initiallyDeferred": row.get("initially_deferred") is True,
            "oldTable": row.get("old_table"),
            "newTable": row.get("new_table"),
        }
        for row in rows if row.get("object_name")
    }, False


def _collect_catalog(cur):
    """Collect exact, structurally bounded facts for every contract object."""

    parent_missing = collect_missing_columns(cur, PARENT_REQUIRED_COLUMNS)
    parent_relations, parent_overflow = _collect_parent_relations(cur)
    holders, table, holder_overflow = _collect_relation_holders(cur)
    type_holder, type_overflow = _collect_type_holder(cur)
    functions, function_overflow = _collect_functions(cur)
    overflow = any((
        parent_overflow,
        holder_overflow,
        type_overflow,
        function_overflow,
    ))
    columns = {}
    identity_sequence = None
    constraints = {}
    indexes = {}
    triggers = {}
    if table is not None and table.get("relkind") == "r":
        table_oid = table.get("oid")
        columns, column_overflow = _collect_columns(cur, table_oid)
        identity_sequence, sequence_overflow = _collect_identity_sequence(
            cur, table_oid
        )
        constraints, constraint_overflow = _collect_constraints(
            cur, table_oid
        )
        indexes, index_overflow = _collect_indexes(cur, table_oid)
        triggers, trigger_overflow = _collect_triggers(cur, table_oid)
        overflow = overflow or any((
            column_overflow,
            sequence_overflow,
            constraint_overflow,
            index_overflow,
            trigger_overflow,
        ))
    return {
        "parentColumnsMissing": sorted(set(parent_missing or [])),
        "parentRelations": parent_relations,
        "catalogComplete": not overflow,
        "table": table,
        "typeHolder": type_holder,
        "identitySequence": identity_sequence,
        "nameHolders": holders,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "functions": functions,
        "triggers": triggers,
    }


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
