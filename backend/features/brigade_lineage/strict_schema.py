"""Pure plan and static DDL contract for strict brigade source lineage."""

import hashlib
import json

from . import constraint_audit


PLAN_CONTRACT = "brigade-lineage-e3.4.2b-strict-v1"

_SOURCE_COLUMN = "brigade_contract_items.source_type"
_COLUMN_GAPS = {
    _SOURCE_COLUMN + ".noDefault": {
        "kind": "column",
        "name": _SOURCE_COLUMN,
        "action": "dropDefault",
        "planKey": "column:brigade_contract_items.source_type:dropDefault",
    },
    _SOURCE_COLUMN + ".notNull": {
        "kind": "column",
        "name": _SOURCE_COLUMN,
        "action": "setNotNull",
        "planKey": "column:brigade_contract_items.source_type:setNotNull",
    },
}
_CONSTRAINT_NAMES = frozenset(constraint_audit._CONSTRAINT_NAMES)
_INDEX_NAMES = frozenset(constraint_audit._INDEX_NAMES)
_TRIGGER_NAMES = frozenset(constraint_audit._TRIGGER_NAMES)

_ROLLBACK_BY_PLAN_KEY = {
    "column:brigade_contract_items.source_type:dropDefault": (
        "ALTER TABLE public.brigade_contract_items "
        "ALTER COLUMN source_type SET DEFAULT 'legacy';",
    ),
    "column:brigade_contract_items.source_type:setNotNull": (
        "ALTER TABLE public.brigade_contract_items "
        "ALTER COLUMN source_type DROP NOT NULL;",
    ),
    "constraint:chk_brigade_contract_items_source_shape": (
        "ALTER TABLE public.brigade_contract_items DROP CONSTRAINT "
        "IF EXISTS chk_brigade_contract_items_source_shape;",
    ),
    "constraint:chk_brigade_contract_items_source_type": (
        "ALTER TABLE public.brigade_contract_items DROP CONSTRAINT "
        "IF EXISTS chk_brigade_contract_items_source_type;",
    ),
    "constraint:chk_estimate_versions_sections_sha256": (
        "ALTER TABLE public.estimate_versions DROP CONSTRAINT "
        "IF EXISTS chk_estimate_versions_sections_sha256;",
    ),
    "constraint:fk_brigade_contract_items_contract_id": (
        "ALTER TABLE public.brigade_contract_items DROP CONSTRAINT "
        "IF EXISTS fk_brigade_contract_items_contract_id;",
    ),
    "constraint:fk_brigade_contract_items_source_estimate_version_id": (
        "ALTER TABLE public.brigade_contract_items DROP CONSTRAINT "
        "IF EXISTS fk_brigade_contract_items_source_estimate_version_id;",
    ),
    "constraint:fk_estimate_versions_estimate_id": (
        "ALTER TABLE public.estimate_versions DROP CONSTRAINT "
        "IF EXISTS fk_estimate_versions_estimate_id;",
    ),
    "index:idx_brigade_contract_items_source_estimate_version": (
        "DROP INDEX IF EXISTS "
        "public.idx_brigade_contract_items_source_estimate_version;",
    ),
    "index:uq_brigade_contract_items_estimate_source": (
        "DROP INDEX IF EXISTS public.uq_brigade_contract_items_estimate_source;",
    ),
    "index:uq_estimate_versions_estimate_sections_sha256": (
        "DROP INDEX IF EXISTS "
        "public.uq_estimate_versions_estimate_sections_sha256;",
    ),
    "trigger:trg_brigade_contract_items_source_guard": (
        "DROP TRIGGER IF EXISTS trg_brigade_contract_items_source_guard "
        "ON public.brigade_contract_items;",
        "DROP FUNCTION IF EXISTS public.brigade_contract_items_source_guard();",
    ),
    "trigger:trg_estimate_versions_snapshot_immutable": (
        "DROP TRIGGER IF EXISTS trg_estimate_versions_snapshot_immutable "
        "ON public.estimate_versions;",
        "DROP FUNCTION IF EXISTS public.estimate_versions_snapshot_immutable_guard();",
    ),
}

_DDL_BY_PLAN_KEY = {
    "column:brigade_contract_items.source_type:dropDefault": (
        "ALTER TABLE public.brigade_contract_items "
        "ALTER COLUMN source_type DROP DEFAULT",
    ),
    "column:brigade_contract_items.source_type:setNotNull": (
        "ALTER TABLE public.brigade_contract_items "
        "ALTER COLUMN source_type SET NOT NULL",
    ),
    "constraint:chk_brigade_contract_items_source_shape": (
        """ALTER TABLE public.brigade_contract_items
             ADD CONSTRAINT chk_brigade_contract_items_source_shape CHECK (
               (source_type='estimate'
                AND source_estimate_version_id IS NOT NULL
                AND source_section_index >= 0
                AND source_item_index >= 0
                AND source_item_key IS NOT NULL
                AND btrim(source_item_key) <> '')
               OR
               (source_type IN ('manual','pricelist','legacy')
                AND source_estimate_version_id IS NULL
                AND source_section_index IS NULL
                AND source_item_index IS NULL
                AND source_item_key IS NULL)
             )""",
    ),
    "constraint:chk_brigade_contract_items_source_type": (
        """ALTER TABLE public.brigade_contract_items
             ADD CONSTRAINT chk_brigade_contract_items_source_type
             CHECK (source_type IN ('estimate','manual','pricelist','legacy'))""",
    ),
    "constraint:chk_estimate_versions_sections_sha256": (
        """ALTER TABLE public.estimate_versions
             ADD CONSTRAINT chk_estimate_versions_sections_sha256
             CHECK (sections_sha256 IS NULL
                    OR sections_sha256 ~ '^[0-9a-f]{64}$')""",
    ),
    "constraint:fk_brigade_contract_items_contract_id": (
        """ALTER TABLE public.brigade_contract_items
             ADD CONSTRAINT fk_brigade_contract_items_contract_id
             FOREIGN KEY (contract_id)
             REFERENCES public.brigade_contracts(id) ON DELETE RESTRICT""",
    ),
    "constraint:fk_brigade_contract_items_source_estimate_version_id": (
        """ALTER TABLE public.brigade_contract_items
             ADD CONSTRAINT fk_brigade_contract_items_source_estimate_version_id
             FOREIGN KEY (source_estimate_version_id)
             REFERENCES public.estimate_versions(id) ON DELETE RESTRICT""",
    ),
    "constraint:fk_estimate_versions_estimate_id": (
        """ALTER TABLE public.estimate_versions
             ADD CONSTRAINT fk_estimate_versions_estimate_id
             FOREIGN KEY (estimate_id)
             REFERENCES public.estimates(id) ON DELETE RESTRICT""",
    ),
    "index:idx_brigade_contract_items_source_estimate_version": (
        """CREATE INDEX idx_brigade_contract_items_source_estimate_version
             ON public.brigade_contract_items(source_estimate_version_id)
             WHERE source_estimate_version_id IS NOT NULL""",
    ),
    "index:uq_brigade_contract_items_estimate_source": (
        """CREATE UNIQUE INDEX uq_brigade_contract_items_estimate_source
             ON public.brigade_contract_items(
               contract_id,source_estimate_version_id,source_section_index,
               source_item_index,source_item_key
             ) WHERE source_type='estimate'""",
    ),
    "index:uq_estimate_versions_estimate_sections_sha256": (
        """CREATE UNIQUE INDEX uq_estimate_versions_estimate_sections_sha256
             ON public.estimate_versions(estimate_id,sections_sha256)
             WHERE sections_sha256 IS NOT NULL""",
    ),
    "trigger:trg_brigade_contract_items_source_guard": (
        """CREATE FUNCTION
             public.brigade_contract_items_source_guard()
             RETURNS trigger LANGUAGE plpgsql AS $$
             BEGIN
               IF TG_OP='UPDATE' THEN
                 IF OLD.source_type IS DISTINCT FROM NEW.source_type
                    OR OLD.source_estimate_version_id IS DISTINCT FROM
                       NEW.source_estimate_version_id
                    OR OLD.source_section_index IS DISTINCT FROM
                       NEW.source_section_index
                    OR OLD.source_item_index IS DISTINCT FROM
                       NEW.source_item_index
                    OR OLD.source_item_key IS DISTINCT FROM NEW.source_item_key
                 THEN
                   RAISE EXCEPTION 'brigade assignment source is immutable'
                     USING ERRCODE='23514';
                 END IF;
               END IF;
               IF NEW.source_type='estimate' AND NOT EXISTS (
                 SELECT 1
                   FROM public.brigade_contracts bc
                   JOIN public.estimate_versions ev
                     ON ev.id=NEW.source_estimate_version_id
                   JOIN public.estimates e ON e.id=ev.estimate_id
                  WHERE bc.id=NEW.contract_id
                    AND ev.sections_sha256 IS NOT NULL
                    AND bc.company_id IS NOT NULL
                    AND bc.project_id IS NOT NULL
                    AND e.company_id IS NOT NULL
                    AND e.project_id IS NOT NULL
                    AND NOT (bc.company_id IS DISTINCT FROM e.company_id)
                    AND NOT (bc.project_id IS DISTINCT FROM e.project_id)
               ) THEN
                 RAISE EXCEPTION 'brigade assignment source owner mismatch'
                   USING ERRCODE='23514';
               END IF;
               RETURN NEW;
             END;
             $$""",
        """CREATE TRIGGER trg_brigade_contract_items_source_guard
             BEFORE INSERT OR UPDATE ON public.brigade_contract_items
             FOR EACH ROW
             EXECUTE FUNCTION public.brigade_contract_items_source_guard()""",
    ),
    "trigger:trg_estimate_versions_snapshot_immutable": (
        """CREATE FUNCTION
             public.estimate_versions_snapshot_immutable_guard()
             RETURNS trigger LANGUAGE plpgsql AS $$
             BEGIN
               IF OLD.estimate_id IS DISTINCT FROM NEW.estimate_id
                  OR OLD.sections_json IS DISTINCT FROM NEW.sections_json
                  OR OLD.sections_sha256 IS DISTINCT FROM NEW.sections_sha256
               THEN
                 RAISE EXCEPTION 'estimate version snapshot is immutable'
                   USING ERRCODE='23514';
               END IF;
               RETURN NEW;
             END;
             $$""",
        """CREATE TRIGGER trg_estimate_versions_snapshot_immutable
             BEFORE UPDATE OF estimate_id,sections_json,sections_sha256
             ON public.estimate_versions
             FOR EACH ROW
             EXECUTE FUNCTION public.estimate_versions_snapshot_immutable_guard()""",
    ),
}


def _fixed_blockers(constraints, writers, deletion, lineage):
    blockers = []
    if (
        constraints.get("dryRun") is not True
        or constraints.get("writesAttempted") != 0
    ):
        blockers.append("constraintAuditInvalid")
    if writers.get("dryRun") is not True or writers.get("writesAttempted") != 0:
        blockers.append("writerAuditInvalid")
    if deletion.get("dryRun") is not True or deletion.get("writesAttempted") != 0:
        blockers.append("deleteAuditInvalid")

    blockers.extend(
        "missingColumn:" + str(name)
        for name in sorted(constraints.get("missingColumns") or ())
    )
    blockers.extend(
        "invalidColumn:" + str(name)
        for name in sorted(constraints.get("invalidColumns") or ())
        if name not in _COLUMN_GAPS
    )
    blockers.extend(
        "invalidConstraint:" + str(name)
        for name in sorted(constraints.get("invalidConstraints") or ())
    )
    blockers.extend(
        "invalidIndex:" + str(name)
        for name in sorted(constraints.get("invalidIndexes") or ())
    )
    blockers.extend(
        "invalidTrigger:" + str(name)
        for name in sorted(constraints.get("invalidTriggers") or ())
    )
    blockers.extend(
        "data:" + str(name)
        for name in sorted(constraints.get("dataIssues") or ())
    )
    if constraints.get("dataReadyForConstraints") is not True and not (
        constraints.get("dataIssues") or ()
    ):
        blockers.append("constraintDataNotReady")
    if writers.get("ok") is not True:
        blockers.append("writersNotReady")
    if deletion.get("deleteRestrictionsReady") is not True:
        blockers.append("deleteRestrictionsNotReady")
    lineage_summary = lineage.get("summary") or {}
    by_state = lineage_summary.get("byState") or {}
    invalid_rows = by_state.get("invalid")
    if (
        lineage.get("schemaState") != "complete"
        or lineage.get("baseSchemaPresent") is not True
    ):
        blockers.append("lineageSchemaNotReady")
    if lineage.get("reportConsistent") is not True:
        blockers.append("lineageReportInconsistent")
    if (
        not isinstance(invalid_rows, int)
        or isinstance(invalid_rows, bool)
        or invalid_rows != 0
    ):
        blockers.append("lineageRowsInvalid")
    return blockers


def _planned_changes(constraints, blockers):
    changes = []
    for gap in sorted(constraints.get("invalidColumns") or ()):
        if gap in _COLUMN_GAPS:
            changes.append(dict(_COLUMN_GAPS[gap]))

    targets = (
        ("constraint", "missingConstraints", _CONSTRAINT_NAMES),
        ("index", "missingIndexes", _INDEX_NAMES),
        ("trigger", "missingTriggers", _TRIGGER_NAMES),
    )
    for kind, field, allowed in targets:
        for name in sorted(constraints.get(field) or ()):
            if name not in allowed:
                blockers.append("unexpectedMissing%s:%s" % (kind.title(), name))
                continue
            changes.append({
                "kind": kind,
                "name": name,
                "action": "create",
                "planKey": kind + ":" + name,
            })
    return changes


def _plan_sha256(changes, constraints, writers, deletion, lineage):
    data = constraints.get("data") or {}
    payload = {
        "contract": PLAN_CONTRACT,
        "changes": [item["planKey"] for item in changes],
        "data": {str(key): data[key] for key in sorted(data)},
        "writers": {
            "ready": writers.get("ok") is True,
            "insertStatements": writers.get("insertStatements"),
            "updateStatements": writers.get("updateStatements"),
        },
        "deleteRestrictionsReady": (
            deletion.get("deleteRestrictionsReady") is True
        ),
        "lineage": {
            "schemaState": lineage.get("schemaState"),
            "baseSchemaPresent": lineage.get("baseSchemaPresent"),
            "reportConsistent": lineage.get("reportConsistent"),
            "summary": lineage.get("summary"),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rollback_sql(changes):
    result = []
    for item in reversed(changes):
        result.extend(_ROLLBACK_BY_PLAN_KEY.get(item["planKey"], ()))
    return result


def build_strict_migration_report(constraints, writers, deletion, lineage):
    """Build a bounded apply plan from read-only readiness reports."""
    constraint_result = dict(constraints or {})
    writer_result = dict(writers or {})
    delete_result = dict(deletion or {})
    lineage_result = dict(lineage or {})
    blockers = _fixed_blockers(
        constraint_result, writer_result, delete_result, lineage_result
    )
    changes = _planned_changes(constraint_result, blockers)
    complete = bool(
        not blockers
        and not changes
        and constraint_result.get("constraintsReady") is True
    )
    if not blockers and not changes and not complete:
        blockers.append("constraintStateInconsistent")
    if constraint_result.get("constraintsReady") is True and changes:
        blockers.append("constraintStateInconsistent")

    data = constraint_result.get("data") or {}
    summary = {
        "columnChanges": sum(item["kind"] == "column" for item in changes),
        "constraints": sum(item["kind"] == "constraint" for item in changes),
        "indexes": sum(item["kind"] == "index" for item in changes),
        "triggers": sum(item["kind"] == "trigger" for item in changes),
        "blockers": len(blockers),
        "explicitLegacy": data.get("explicitLegacy"),
    }
    return {
        "ok": not blockers,
        "reportConsistent": not blockers,
        "readyForApply": not blockers and bool(changes),
        "complete": complete,
        "changeCount": len(changes),
        "planSha256": _plan_sha256(
            changes,
            constraint_result,
            writer_result,
            delete_result,
            lineage_result,
        ),
        "summary": summary,
        "plannedChanges": changes,
        "blockers": sorted(set(blockers)),
        "rollbackSql": _rollback_sql(changes),
    }


def execute_strict_plan(cur, changes):
    attempted = 0
    for item in changes:
        statements = _DDL_BY_PLAN_KEY.get(item.get("planKey"))
        if not statements:
            raise RuntimeError("strict migration contains an unknown plan item")
        for statement in statements:
            cur.execute(statement)
            attempted += 1
    return attempted
