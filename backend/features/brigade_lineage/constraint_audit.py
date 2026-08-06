"""Read-only structural and aggregate preflight for strict brigade lineage."""

import re


SCHEMA = "public"
VALID_SOURCE_TYPES = ("estimate", "manual", "pricelist", "legacy")

_REQUIRED_COLUMNS = (
    ("brigade_contract_items", "id"),
    ("brigade_contract_items", "contract_id"),
    ("brigade_contract_items", "source_type"),
    ("brigade_contract_items", "source_estimate_version_id"),
    ("brigade_contract_items", "source_section_index"),
    ("brigade_contract_items", "source_item_index"),
    ("brigade_contract_items", "source_item_key"),
    ("brigade_contracts", "id"),
    ("brigade_contracts", "company_id"),
    ("brigade_contracts", "project_id"),
    ("estimate_versions", "id"),
    ("estimate_versions", "estimate_id"),
    ("estimate_versions", "sections_json"),
    ("estimate_versions", "sections_sha256"),
    ("estimates", "id"),
    ("estimates", "company_id"),
    ("estimates", "project_id"),
)

_CONSTRAINT_NAMES = (
    "fk_brigade_contract_items_contract_id",
    "fk_brigade_contract_items_source_estimate_version_id",
    "fk_estimate_versions_estimate_id",
    "chk_brigade_contract_items_source_type",
    "chk_brigade_contract_items_source_shape",
    "chk_estimate_versions_sections_sha256",
)

_INDEX_NAMES = (
    "uq_brigade_contract_items_estimate_source",
    "idx_brigade_contract_items_source_estimate_version",
    "uq_estimate_versions_estimate_sections_sha256",
)

_TRIGGER_NAMES = (
    "trg_brigade_contract_items_source_guard",
    "trg_estimate_versions_snapshot_immutable",
)

_DATA_FIELDS = (
    ("source_type_null", "sourceTypeNull"),
    ("invalid_source_type", "invalidSourceType"),
    ("invalid_source_shape", "invalidSourceShape"),
    ("orphan_contract", "orphanContract"),
    ("orphan_source_version", "orphanSourceVersion"),
    ("orphan_estimate_version", "orphanEstimateVersion"),
    ("cross_owner_estimate_source", "crossOwnerEstimateSource"),
    ("missing_snapshot_hash", "missingSnapshotHash"),
    ("invalid_snapshot_hash", "invalidSnapshotHash"),
    ("duplicate_estimate_lineage", "duplicateEstimateLineage"),
    ("duplicate_snapshot_hash", "duplicateSnapshotHash"),
)

_QUOTED_LITERAL_RE = re.compile(r"'((?:''|[^'])*)'")


def _text(value):
    return str(value or "").strip()


def _sql_text(value):
    text = _text(value).lower().replace('"', "")
    text = re.sub(r"\bpublic\.", "", text)
    text = re.sub(r"::(?:character varying|varchar|text|bpchar)\b", "", text)
    return " ".join(text.split())


def _rows_by_name(rows, key):
    result = {}
    for raw in rows or ():
        row = dict(raw or {})
        name = _text(row.get(key))
        if name:
            result.setdefault(name, []).append(row)
    return result


def _column_audit(rows):
    by_key = {}
    for raw in rows or ():
        row = dict(raw or {})
        key = (_text(row.get("table_name")), _text(row.get("column_name")))
        if key in _REQUIRED_COLUMNS:
            by_key.setdefault(key, []).append(row)
    missing = [
        "%s.%s" % key for key in _REQUIRED_COLUMNS if not by_key.get(key)
    ]
    invalid = []
    for key, matches in by_key.items():
        if len(matches) != 1:
            invalid.append("%s.%s.metadata" % key)
    source_rows = by_key.get(("brigade_contract_items", "source_type"), [])
    if len(source_rows) == 1:
        source = source_rows[0]
        if source.get("is_nullable") != "NO":
            invalid.append("brigade_contract_items.source_type.notNull")
        if source.get("column_default") is not None:
            invalid.append("brigade_contract_items.source_type.noDefault")
    return sorted(missing), sorted(invalid)


def _foreign_key_valid(row, *, table, local, foreign_table, foreign):
    return (
        _text(row.get("table_name")) == table
        and _text(row.get("constraint_type")) == "f"
        and row.get("validated") is True
        and list(row.get("local_columns") or ()) == [local]
        and _text(row.get("foreign_table")) == foreign_table
        and list(row.get("foreign_columns") or ()) == [foreign]
        and _text(row.get("delete_action")) == "r"
    )


def _source_type_check_valid(row):
    definition = _sql_text(row.get("definition"))
    literals = {
        value.replace("''", "'")
        for value in _QUOTED_LITERAL_RE.findall(definition)
    }
    return (
        _text(row.get("table_name")) == "brigade_contract_items"
        and _text(row.get("constraint_type")) == "c"
        and row.get("validated") is True
        and "source_type" in definition
        and literals == set(VALID_SOURCE_TYPES)
        and (" in " in definition or " any " in definition)
        and " not in " not in definition
    )


def _source_shape_check_valid(row):
    definition = _sql_text(row.get("definition"))
    required = (
        "source_type",
        "source_estimate_version_id",
        "source_section_index",
        "source_item_index",
        "source_item_key",
        "is not null",
        "is null",
        ">= 0",
        "btrim",
    ) + tuple("'%s'" % value for value in VALID_SOURCE_TYPES)
    return (
        _text(row.get("table_name")) == "brigade_contract_items"
        and _text(row.get("constraint_type")) == "c"
        and row.get("validated") is True
        and all(token in definition for token in required)
    )


def _snapshot_hash_check_valid(row):
    definition = _sql_text(row.get("definition"))
    return (
        _text(row.get("table_name")) == "estimate_versions"
        and _text(row.get("constraint_type")) == "c"
        and row.get("validated") is True
        and "sections_sha256" in definition
        and "is null" in definition
        and "^[0-9a-f]{64}$" in definition
    )


def _constraint_valid(name, row):
    if name == "fk_brigade_contract_items_contract_id":
        return _foreign_key_valid(
            row,
            table="brigade_contract_items",
            local="contract_id",
            foreign_table="brigade_contracts",
            foreign="id",
        )
    if name == "fk_brigade_contract_items_source_estimate_version_id":
        return _foreign_key_valid(
            row,
            table="brigade_contract_items",
            local="source_estimate_version_id",
            foreign_table="estimate_versions",
            foreign="id",
        )
    if name == "fk_estimate_versions_estimate_id":
        return _foreign_key_valid(
            row,
            table="estimate_versions",
            local="estimate_id",
            foreign_table="estimates",
            foreign="id",
        )
    if name == "chk_brigade_contract_items_source_type":
        return _source_type_check_valid(row)
    if name == "chk_brigade_contract_items_source_shape":
        return _source_shape_check_valid(row)
    if name == "chk_estimate_versions_sections_sha256":
        return _snapshot_hash_check_valid(row)
    return False


def _named_object_audit(rows, names, key, validator):
    by_name = _rows_by_name(rows, key)
    missing = [name for name in names if not by_name.get(name)]
    invalid = [
        name
        for name in names
        if by_name.get(name)
        and (
            len(by_name[name]) != 1
            or not validator(name, by_name[name][0])
        )
    ]
    return sorted(missing), sorted(invalid)


def _predicate_has(predicate, *tokens):
    normalized = _sql_text(predicate)
    return all(token in normalized for token in tokens)


def _index_valid(name, row):
    common = row.get("is_valid") is True and row.get("is_ready") is True
    columns = [_sql_text(value) for value in (row.get("columns") or ())]
    if name == "uq_brigade_contract_items_estimate_source":
        return (
            common
            and _text(row.get("table_name")) == "brigade_contract_items"
            and row.get("is_unique") is True
            and columns == [
                "contract_id",
                "source_estimate_version_id",
                "source_section_index",
                "source_item_index",
                "source_item_key",
            ]
            and _predicate_has(row.get("predicate"), "source_type", "=", "'estimate'")
        )
    if name == "idx_brigade_contract_items_source_estimate_version":
        return (
            common
            and _text(row.get("table_name")) == "brigade_contract_items"
            and row.get("is_unique") is False
            and columns == ["source_estimate_version_id"]
            and _predicate_has(
                row.get("predicate"),
                "source_estimate_version_id",
                "is not null",
            )
        )
    if name == "uq_estimate_versions_estimate_sections_sha256":
        return (
            common
            and _text(row.get("table_name")) == "estimate_versions"
            and row.get("is_unique") is True
            and columns == ["estimate_id", "sections_sha256"]
            and _predicate_has(
                row.get("predicate"), "sections_sha256", "is not null"
            )
        )
    return False


def _trigger_valid(name, row):
    function_definition = _sql_text(row.get("function_definition"))
    common = (
        _text(row.get("enabled")) in ("O", "A")
        and row.get("is_row") is True
        and row.get("is_before") is True
        and row.get("fires_update") is True
        and row.get("fires_delete") is False
        and _text(row.get("function_schema")) == SCHEMA
        and "raise exception" in function_definition
        and "old." in function_definition
        and "new." in function_definition
    )
    if name == "trg_brigade_contract_items_source_guard":
        required = (
            "source_type",
            "source_estimate_version_id",
            "source_section_index",
            "source_item_index",
            "source_item_key",
            "estimate_versions",
            "estimates",
            "brigade_contracts",
            "company_id",
            "project_id",
        )
        return (
            common
            and _text(row.get("table_name")) == "brigade_contract_items"
            and row.get("fires_insert") is True
            and _text(row.get("function_name"))
            == "brigade_contract_items_source_guard"
            and all(token in function_definition for token in required)
        )
    if name == "trg_estimate_versions_snapshot_immutable":
        required = ("estimate_id", "sections_json", "sections_sha256")
        return (
            common
            and _text(row.get("table_name")) == "estimate_versions"
            and row.get("fires_insert") is False
            and _text(row.get("function_name"))
            == "estimate_versions_snapshot_immutable_guard"
            and all(token in function_definition for token in required)
        )
    return False


def _data_audit(raw_data):
    data = dict(raw_data or {})
    output = {}
    issues = []
    for source_key, output_key in _DATA_FIELDS:
        value = data.get(source_key)
        valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        output[output_key] = value if valid else None
        if not valid or value != 0:
            issues.append(output_key)
    legacy = data.get("explicit_legacy")
    output["explicitLegacy"] = (
        legacy
        if isinstance(legacy, int) and not isinstance(legacy, bool) and legacy >= 0
        else None
    )
    return output, sorted(issues)


def build_constraint_audit(facts):
    """Build a bounded readiness result from already collected catalog facts."""
    source = dict(facts or {})
    missing_columns, invalid_columns = _column_audit(source.get("columns"))
    missing_constraints, invalid_constraints = _named_object_audit(
        source.get("constraints"),
        _CONSTRAINT_NAMES,
        "constraint_name",
        _constraint_valid,
    )
    missing_indexes, invalid_indexes = _named_object_audit(
        source.get("indexes"), _INDEX_NAMES, "index_name", _index_valid
    )
    missing_triggers, invalid_triggers = _named_object_audit(
        source.get("triggers"), _TRIGGER_NAMES, "trigger_name", _trigger_valid
    )
    data, data_issues = _data_audit(source.get("data"))
    catalog_ready = not any((
        missing_columns,
        invalid_columns,
        missing_constraints,
        invalid_constraints,
        missing_indexes,
        invalid_indexes,
        missing_triggers,
        invalid_triggers,
    ))
    data_ready = not data_issues
    constraints_ready = catalog_ready and data_ready
    return {
        "ok": constraints_ready,
        "dryRun": True,
        "writesAttempted": 0,
        "catalogReady": catalog_ready,
        "dataReadyForConstraints": data_ready,
        "constraintsReady": constraints_ready,
        "missingColumns": missing_columns,
        "invalidColumns": invalid_columns,
        "missingConstraints": missing_constraints,
        "invalidConstraints": invalid_constraints,
        "missingIndexes": missing_indexes,
        "invalidIndexes": invalid_indexes,
        "missingTriggers": missing_triggers,
        "invalidTriggers": invalid_triggers,
        "data": data,
        "dataIssues": data_issues,
    }


def _load_columns(cur):
    tables = sorted({table for table, _column in _REQUIRED_COLUMNS})
    columns = sorted({column for _table, column in _REQUIRED_COLUMNS})
    cur.execute(
        """SELECT table_name,column_name,is_nullable,column_default
             FROM information_schema.columns
            WHERE table_schema=%s
              AND table_name=ANY(%s)
              AND column_name=ANY(%s)
            ORDER BY table_name,column_name""",
        (SCHEMA, tables, columns),
    )
    return [dict(row or {}) for row in (cur.fetchall() or ())]


def _load_constraints(cur):
    cur.execute(
        """SELECT c.conname AS constraint_name,
                  tbl.relname AS table_name,
                  c.contype AS constraint_type,
                  c.convalidated AS validated,
                  c.confdeltype AS delete_action,
                  foreign_tbl.relname AS foreign_table,
                  ARRAY(
                    SELECT a.attname
                      FROM unnest(c.conkey) WITH ORDINALITY AS key(attnum,ord)
                      JOIN pg_attribute a
                        ON a.attrelid=c.conrelid AND a.attnum=key.attnum
                     ORDER BY key.ord
                  ) AS local_columns,
                  ARRAY(
                    SELECT a.attname
                      FROM unnest(c.confkey) WITH ORDINALITY AS key(attnum,ord)
                      JOIN pg_attribute a
                        ON a.attrelid=c.confrelid AND a.attnum=key.attnum
                     ORDER BY key.ord
                  ) AS foreign_columns,
                  pg_get_constraintdef(c.oid,TRUE) AS definition
             FROM pg_constraint c
             JOIN pg_class tbl ON tbl.oid=c.conrelid
             JOIN pg_namespace n ON n.oid=tbl.relnamespace
             LEFT JOIN pg_class foreign_tbl ON foreign_tbl.oid=c.confrelid
            WHERE n.nspname=%s AND c.conname=ANY(%s)
            ORDER BY c.conname""",
        (SCHEMA, list(_CONSTRAINT_NAMES)),
    )
    return [dict(row or {}) for row in (cur.fetchall() or ())]


def _load_indexes(cur):
    cur.execute(
        """SELECT idx.relname AS index_name,
                  tbl.relname AS table_name,
                  i.indisunique AS is_unique,
                  i.indisvalid AS is_valid,
                  i.indisready AS is_ready,
                  ARRAY(
                    SELECT pg_get_indexdef(i.indexrelid,key_position,TRUE)
                      FROM generate_series(1,i.indnkeyatts) key_position
                     ORDER BY key_position
                  ) AS columns,
                  pg_get_expr(i.indpred,i.indrelid,TRUE) AS predicate
             FROM pg_index i
             JOIN pg_class idx ON idx.oid=i.indexrelid
             JOIN pg_class tbl ON tbl.oid=i.indrelid
             JOIN pg_namespace n ON n.oid=tbl.relnamespace
            WHERE n.nspname=%s AND idx.relname=ANY(%s)
            ORDER BY idx.relname""",
        (SCHEMA, list(_INDEX_NAMES)),
    )
    return [dict(row or {}) for row in (cur.fetchall() or ())]


def _load_triggers(cur):
    cur.execute(
        """SELECT t.tgname AS trigger_name,
                  tbl.relname AS table_name,
                  t.tgenabled AS enabled,
                  (t.tgtype & 1) <> 0 AS is_row,
                  (t.tgtype & 2) <> 0 AS is_before,
                  (t.tgtype & 4) <> 0 AS fires_insert,
                  (t.tgtype & 16) <> 0 AS fires_update,
                  (t.tgtype & 8) <> 0 AS fires_delete,
                  fn_ns.nspname AS function_schema,
                  p.proname AS function_name,
                  pg_get_functiondef(p.oid) AS function_definition
             FROM pg_trigger t
             JOIN pg_class tbl ON tbl.oid=t.tgrelid
             JOIN pg_namespace n ON n.oid=tbl.relnamespace
             JOIN pg_proc p ON p.oid=t.tgfoid
             JOIN pg_namespace fn_ns ON fn_ns.oid=p.pronamespace
            WHERE n.nspname=%s
              AND NOT t.tgisinternal
              AND t.tgname=ANY(%s)
            ORDER BY t.tgname""",
        (SCHEMA, list(_TRIGGER_NAMES)),
    )
    return [dict(row or {}) for row in (cur.fetchall() or ())]


def _load_data_counts(cur):
    cur.execute(
        """SELECT
          (SELECT COUNT(*) FROM public.brigade_contract_items
            WHERE source_type IS NULL) AS source_type_null,
          (SELECT COUNT(*) FROM public.brigade_contract_items
            WHERE source_type IS NOT NULL AND NOT (source_type=ANY(%s)))
            AS invalid_source_type,
          (SELECT COUNT(*) FROM public.brigade_contract_items
            WHERE source_type IS NOT NULL AND NOT (
              (source_type=%s
               AND source_estimate_version_id IS NOT NULL
               AND source_section_index >= 0
               AND source_item_index >= 0
               AND source_item_key IS NOT NULL
               AND btrim(source_item_key) <> '')
              OR
              (source_type=ANY(%s)
               AND source_estimate_version_id IS NULL
               AND source_section_index IS NULL
               AND source_item_index IS NULL
               AND source_item_key IS NULL)
            )) AS invalid_source_shape,
          (SELECT COUNT(*) FROM public.brigade_contract_items bci
             LEFT JOIN public.brigade_contracts bc ON bc.id=bci.contract_id
            WHERE bc.id IS NULL) AS orphan_contract,
          (SELECT COUNT(*) FROM public.brigade_contract_items bci
             LEFT JOIN public.estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
            WHERE bci.source_estimate_version_id IS NOT NULL AND ev.id IS NULL)
            AS orphan_source_version,
          (SELECT COUNT(*) FROM public.estimate_versions ev
             LEFT JOIN public.estimates e ON e.id=ev.estimate_id
            WHERE e.id IS NULL) AS orphan_estimate_version,
          (SELECT COUNT(*) FROM public.brigade_contract_items bci
             JOIN public.brigade_contracts bc ON bc.id=bci.contract_id
             JOIN public.estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
             JOIN public.estimates e ON e.id=ev.estimate_id
            WHERE bci.source_type=%s
              AND (bc.company_id IS DISTINCT FROM e.company_id
                   OR bc.project_id IS DISTINCT FROM e.project_id))
            AS cross_owner_estimate_source,
          (SELECT COUNT(*) FROM public.brigade_contract_items bci
             JOIN public.estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
            WHERE bci.source_type=%s
              AND ev.sections_sha256 IS NULL) AS missing_snapshot_hash,
          (SELECT COUNT(*) FROM public.estimate_versions
            WHERE sections_sha256 IS NOT NULL
              AND sections_sha256 !~ '^[0-9a-f]{64}$') AS invalid_snapshot_hash,
          (SELECT COUNT(*) FROM (
             SELECT 1 FROM public.brigade_contract_items
              WHERE source_type=%s
              GROUP BY contract_id,source_estimate_version_id,
                       source_section_index,source_item_index,source_item_key
             HAVING COUNT(*) > 1
          ) duplicate_lineage) AS duplicate_estimate_lineage,
          (SELECT COUNT(*) FROM (
             SELECT 1 FROM public.estimate_versions
              WHERE sections_sha256 IS NOT NULL
              GROUP BY estimate_id,sections_sha256
             HAVING COUNT(*) > 1
          ) duplicate_hash) AS duplicate_snapshot_hash,
          (SELECT COUNT(*) FROM public.brigade_contract_items
            WHERE source_type=%s) AS explicit_legacy
        FROM (SELECT %s::text AS schema_name) audit_scope
        WHERE schema_name='public'""",
        (
            list(VALID_SOURCE_TYPES),
            "estimate",
            ["manual", "pricelist", "legacy"],
            "estimate",
            "estimate",
            "estimate",
            "legacy",
            SCHEMA,
        ),
    )
    row = cur.fetchone()
    return dict(row or {}) if row is not None else None


def audit_brigade_lineage_constraints(cur):
    """Collect catalog/data facts with SELECT only and return readiness."""
    columns = _load_columns(cur)
    facts = {
        "columns": columns,
        "constraints": _load_constraints(cur),
        "indexes": _load_indexes(cur),
        "triggers": _load_triggers(cur),
        "data": None,
    }
    present = {
        (_text(row.get("table_name")), _text(row.get("column_name")))
        for row in columns
    }
    if all(key in present for key in _REQUIRED_COLUMNS):
        facts["data"] = _load_data_counts(cur)
    return build_constraint_audit(facts)
