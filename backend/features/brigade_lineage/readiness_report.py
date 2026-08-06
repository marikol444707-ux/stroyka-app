"""Read-only readiness diagnostics for brigade assignment source lineage."""

import hashlib
import json
import re
from collections import Counter

import psycopg2.extras


PREVIEW_LIMIT = 100
REPORT_VERSION = 1
HASH_CONTRACT = "canonical-json-v1"
LINEAGE_COLUMNS = (
    "source_type",
    "source_estimate_version_id",
    "source_section_index",
    "source_item_index",
    "source_item_key",
)
SNAPSHOT_COLUMNS = ("sections_sha256",)
_SOURCE_COORDINATE_COLUMNS = LINEAGE_COLUMNS[1:]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_BASE_COLUMNS = {
    "brigade_contract_items": ("id", "contract_id", "estimate_item_key"),
    "brigade_contracts": ("id", "company_id", "project_id"),
    "projects": ("id", "company_id"),
    "estimates": ("id", "company_id", "project_id"),
    "estimate_versions": ("id", "estimate_id", "sections_json"),
}
_TABLES = tuple(_BASE_COLUMNS)


def _positive_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _non_negative_int(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _text(value):
    return str(value or "").strip()


def _sections(value):
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("estimate snapshot sections must be a list")
    return parsed


def sections_sha256(sections):
    canonical = json.dumps(
        {"sections": _sections(sections)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result(row, status, reason):
    raw_source_type = (row or {}).get("source_type")
    if raw_source_type in ("estimate", "manual", "pricelist", "legacy"):
        source_type = raw_source_type
    elif raw_source_type in (None, "") and status == "legacy":
        source_type = "legacy"
    else:
        source_type = "unclassified"
    return {
        "contractItemId": _positive_int((row or {}).get("contract_item_id")),
        "status": status,
        "reason": reason,
        "sourceType": source_type,
        "hasLegacyItemKey": bool(_text((row or {}).get("legacy_item_key"))),
    }


def _coordinate_present(row):
    item = row or {}
    return any(name in item and item.get(name) is not None for name in _SOURCE_COORDINATE_COLUMNS)


def _snapshot_item_key_status(row, sections):
    section_index = _non_negative_int(row.get("source_section_index"))
    item_index = _non_negative_int(row.get("source_item_index"))
    try:
        item = sections[section_index]["items"][item_index]
    except (IndexError, KeyError, TypeError):
        return "mismatch"
    if not isinstance(item, dict):
        return "mismatch"
    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        raw_value = item.get(field)
        if raw_value in (None, ""):
            continue
        if not isinstance(raw_value, str) or raw_value != raw_value.strip():
            return "noncanonical"
        value = raw_value
        if value and value not in keys:
            keys.append(value)
    if len(keys) > 1:
        return "ambiguous"
    generated = "%s:%s:%s" % (
        _positive_int(row.get("snapshot_estimate_id")),
        section_index,
        item_index,
    )
    if not keys:
        keys.append(generated)
    return "match" if row.get("source_item_key") in keys else "mismatch"


def _prepare_snapshot_evidence(row):
    evidence = dict(row or {})
    if "_snapshot_content_reason" in evidence:
        return evidence
    raw_hash = evidence.get("snapshot_sections_sha256")
    if (
        not isinstance(raw_hash, str)
        or raw_hash != raw_hash.strip()
        or raw_hash != raw_hash.lower()
        or not _SHA256_RE.fullmatch(raw_hash)
    ):
        evidence["_snapshot_content_reason"] = "snapshot_hash_not_canonical"
        return evidence
    try:
        sections = _sections(evidence.get("snapshot_sections_json"))
        if sections_sha256(sections) != raw_hash:
            evidence["_snapshot_content_reason"] = "snapshot_hash_mismatch"
            return evidence
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ):
        evidence["_snapshot_content_reason"] = "snapshot_content_invalid"
        return evidence
    evidence["_snapshot_content_reason"] = None
    evidence["_snapshot_sections"] = sections
    return evidence


def classify_contract_item(
    row,
    *,
    lineage_schema_ready,
    snapshot_schema_ready,
    snapshot_evidence=None,
):
    item = dict(row or {})
    if item.get("contract_exists") is not True:
        return _result(item, "invalid", "contract_not_found")
    contract_company = _positive_int(item.get("contract_company_id"))
    contract_project = _positive_int(item.get("contract_project_id"))
    if not contract_company or not contract_project:
        return _result(item, "invalid", "contract_owner_missing")
    if item.get("project_exists") is not True:
        return _result(item, "invalid", "contract_project_not_found")
    if _positive_int(item.get("project_company_id")) != contract_company:
        return _result(item, "invalid", "contract_project_owner_mismatch")
    if not lineage_schema_ready:
        return _result(item, "legacy", "legacy_source_unproven")

    raw_source_type = item.get("source_type")
    if raw_source_type in (None, ""):
        if _coordinate_present(item):
            return _result(item, "invalid", "source_type_missing_with_coordinates")
        return _result(item, "invalid", "source_type_missing")
    if (
        not isinstance(raw_source_type, str)
        or raw_source_type != raw_source_type.strip().lower()
    ):
        return _result(item, "invalid", "source_type_not_canonical")
    source_type = raw_source_type
    if source_type == "legacy":
        if _coordinate_present(item):
            return _result(item, "invalid", "legacy_source_has_estimate_coordinates")
        return _result(item, "legacy", "explicit_legacy_source")
    if source_type in ("manual", "pricelist"):
        if _coordinate_present(item):
            return _result(
                item,
                "invalid",
                source_type + "_source_has_estimate_coordinates",
            )
        if _text(item.get("legacy_item_key")):
            return _result(
                item,
                "invalid",
                source_type + "_source_has_legacy_item_key",
            )
        return _result(
            item,
            "declared_" + source_type,
            "explicit_" + source_type + "_source",
        )
    if source_type != "estimate":
        return _result(item, "invalid", "source_type_unknown")
    if not snapshot_schema_ready:
        return _result(item, "invalid", "snapshot_schema_missing")

    source_version = _positive_int(item.get("source_estimate_version_id"))
    section_index = _non_negative_int(item.get("source_section_index"))
    item_index = _non_negative_int(item.get("source_item_index"))
    raw_source_item_key = item.get("source_item_key")
    source_item_key = _text(raw_source_item_key)
    if (
        not source_version
        or section_index is None
        or item_index is None
        or not source_item_key
    ):
        return _result(item, "invalid", "estimate_source_incomplete")
    if (
        not isinstance(raw_source_item_key, str)
        or raw_source_item_key != source_item_key
    ):
        return _result(item, "invalid", "source_item_key_not_canonical")
    evidence = item if snapshot_evidence is None else dict(snapshot_evidence or {})
    if evidence.get("snapshot_exists") is not True:
        return _result(item, "invalid", "snapshot_not_found")
    if _positive_int(evidence.get("snapshot_version_id")) != source_version:
        return _result(item, "invalid", "snapshot_version_mismatch")
    source_estimate = _positive_int(evidence.get("snapshot_estimate_id"))
    if not source_estimate:
        return _result(item, "invalid", "snapshot_estimate_missing")
    if evidence.get("estimate_exists") is not True:
        return _result(item, "invalid", "estimate_not_found")
    if (
        _positive_int(evidence.get("estimate_company_id")),
        _positive_int(evidence.get("estimate_project_id")),
    ) != (contract_company, contract_project):
        return _result(item, "invalid", "estimate_owner_mismatch")

    evidence = _prepare_snapshot_evidence(evidence)
    content_reason = evidence.get("_snapshot_content_reason")
    if content_reason:
        return _result(item, "invalid", content_reason)
    key_context = {**evidence, **item}
    item_key_status = _snapshot_item_key_status(
        key_context,
        evidence.get("_snapshot_sections"),
    )
    if item_key_status == "noncanonical":
        return _result(item, "invalid", "snapshot_row_key_not_canonical")
    if item_key_status == "ambiguous":
        return _result(item, "invalid", "snapshot_row_key_ambiguous")
    if item_key_status != "match":
        return _result(item, "invalid", "snapshot_row_key_mismatch")
    if item.get("legacy_item_key") != source_item_key:
        return _result(item, "invalid", "compatibility_item_key_mismatch")
    return _result(item, "verified_estimate", "exact_snapshot_row_verified")


def _missing(schema, table, required):
    columns = set((schema or {}).get(table) or ())
    return [column for column in required if column not in columns]


def build_report_from_rows(schema, rows, *, snapshot_rows=None):
    schema = schema or {}
    rows = list(rows or [])
    missing_base = {
        table: _missing(schema, table, required)
        for table, required in _BASE_COLUMNS.items()
    }
    missing_lineage = _missing(
        schema,
        "brigade_contract_items",
        LINEAGE_COLUMNS,
    )
    missing_snapshot = _missing(
        schema,
        "estimate_versions",
        SNAPSHOT_COLUMNS,
    )
    lineage_ready = not missing_base["brigade_contract_items"] and not missing_lineage
    snapshot_ready = not missing_base["estimate_versions"] and not missing_snapshot
    snapshot_evidence = None
    if snapshot_rows is not None:
        snapshot_evidence = {}
        for raw_snapshot in snapshot_rows or ():
            version_id = _positive_int((raw_snapshot or {}).get("snapshot_version_id"))
            if version_id and version_id not in snapshot_evidence:
                snapshot_evidence[version_id] = _prepare_snapshot_evidence(raw_snapshot)
    classified = []
    for row in rows:
        evidence = None
        if snapshot_evidence is not None:
            version_id = _positive_int((row or {}).get("source_estimate_version_id"))
            evidence = snapshot_evidence.get(version_id, {})
        classified.append(
            classify_contract_item(
                row,
                lineage_schema_ready=lineage_ready,
                snapshot_schema_ready=snapshot_ready,
                snapshot_evidence=evidence,
            )
        )
    counts = Counter(item["status"] for item in classified)
    statuses = (
        "verified_estimate",
        "declared_manual",
        "declared_pricelist",
        "legacy",
        "invalid",
    )
    report_consistent = len(classified) == sum(counts[status] for status in statuses)
    review = [item for item in classified if item["status"] in ("legacy", "invalid")]
    base_ready = all(not missing for missing in missing_base.values())
    source_counts = Counter(item["sourceType"] for item in classified)
    reason_counts = Counter(item["reason"] for item in classified)
    lineage_present = len(LINEAGE_COLUMNS) - len(missing_lineage)
    snapshot_present = len(SNAPSHOT_COLUMNS) - len(missing_snapshot)
    if not base_ready:
        schema_state = "base_incomplete"
    elif lineage_present == 0 and snapshot_present == 0:
        schema_state = "pre_migration"
    elif not missing_lineage and not missing_snapshot:
        schema_state = "complete"
    else:
        schema_state = "partial"
    return {
        "reportVersion": REPORT_VERSION,
        "ok": True,
        "dryRun": True,
        "tables": list(_BASE_COLUMNS),
        "writesAttempted": 0,
        "hashContract": HASH_CONTRACT,
        "schemaState": schema_state,
        "schema": {
            "brigadeContractItems": {
                "tableExists": "brigade_contract_items" in schema,
                "missingBaseColumns": missing_base["brigade_contract_items"],
                "missingLineageColumns": missing_lineage,
            },
            "brigadeContracts": {
                "tableExists": "brigade_contracts" in schema,
                "missingBaseColumns": missing_base["brigade_contracts"],
            },
            "projects": {
                "tableExists": "projects" in schema,
                "missingBaseColumns": missing_base["projects"],
            },
            "estimates": {
                "tableExists": "estimates" in schema,
                "missingBaseColumns": missing_base["estimates"],
            },
            "estimateVersions": {
                "tableExists": "estimate_versions" in schema,
                "missingBaseColumns": missing_base["estimate_versions"],
                "missingSnapshotColumns": missing_snapshot,
            },
        },
        "baseSchemaPresent": base_ready,
        "lineageDataReady": (
            base_ready
            and lineage_ready
            and snapshot_ready
            and report_consistent
            and not review
        ),
        "constraintAuditIncluded": False,
        "writerAuditIncluded": False,
        "reportConsistent": report_consistent,
        "summary": {
            "totalRows": len(classified),
            "byState": {
                "verifiedEstimate": counts["verified_estimate"],
                "declaredManual": counts["declared_manual"],
                "declaredPricelist": counts["declared_pricelist"],
                "legacy": counts["legacy"],
                "invalid": counts["invalid"],
            },
            "bySourceType": {
                source_type: source_counts[source_type]
                for source_type in (
                    "estimate",
                    "manual",
                    "pricelist",
                    "legacy",
                    "unclassified",
                )
            },
            "legacyWithItemKey": sum(
                1 for item in classified
                if item["status"] == "legacy" and item["hasLegacyItemKey"]
            ),
            "legacyWithoutItemKey": sum(
                1 for item in classified
                if item["status"] == "legacy" and not item["hasLegacyItemKey"]
            ),
        },
        "reasonCounts": dict(sorted(reason_counts.items())),
        "needsReview": [
            {
                "contractItemId": item["contractItemId"],
                "status": item["status"],
                "reasonCode": item["reason"],
            }
            for item in review[:PREVIEW_LIMIT]
        ],
        "needsReviewTruncated": len(review) > PREVIEW_LIMIT,
    }


def load_schema(cur):
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema=current_schema()
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (list(_TABLES),),
    )
    schema = {}
    for row in cur.fetchall() or []:
        item = dict(row or {})
        table = _text(item.get("table_name"))
        column = _text(item.get("column_name"))
        if table in _TABLES and column:
            schema.setdefault(table, set()).add(column)
    return schema


def load_contract_item_rows(cur, schema):
    schema = schema or {}
    if any(_missing(schema, table, required) for table, required in _BASE_COLUMNS.items()):
        return []
    lineage_ready = not _missing(
        schema,
        "brigade_contract_items",
        LINEAGE_COLUMNS,
    )
    select_fields = [
        "bci.id AS contract_item_id",
        "COALESCE(bci.estimate_item_key,'') AS legacy_item_key",
        "bc.id IS NOT NULL AS contract_exists",
        "bc.company_id AS contract_company_id",
        "bc.project_id AS contract_project_id",
        "p.id IS NOT NULL AS project_exists",
        "p.company_id AS project_company_id",
    ]
    joins = [
        "LEFT JOIN brigade_contracts bc ON bc.id=bci.contract_id",
        "LEFT JOIN projects p ON p.id=bc.project_id",
    ]
    if lineage_ready:
        select_fields.extend("bci.%s" % column for column in LINEAGE_COLUMNS)
    cur.execute(
        "SELECT %s FROM brigade_contract_items bci %s ORDER BY bci.id"
        % (", ".join(select_fields), " ".join(joins))
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def load_snapshot_rows(cur, schema, version_ids):
    if _missing(schema, "estimate_versions", _BASE_COLUMNS["estimate_versions"]):
        return []
    if _missing(schema, "estimate_versions", SNAPSHOT_COLUMNS):
        return []
    if _missing(schema, "estimates", _BASE_COLUMNS["estimates"]):
        return []
    normalized_ids = sorted({
        version_id
        for version_id in (_positive_int(value) for value in (version_ids or ()))
        if version_id
    })
    if not normalized_ids:
        return []
    cur.execute(
        """SELECT ev.id IS NOT NULL AS snapshot_exists,
                  ev.id AS snapshot_version_id,
                  ev.estimate_id AS snapshot_estimate_id,
                  ev.sections_sha256 AS snapshot_sections_sha256,
                  ev.sections_json AS snapshot_sections_json,
                  e.id IS NOT NULL AS estimate_exists,
                  e.company_id AS estimate_company_id,
                  e.project_id AS estimate_project_id
             FROM estimate_versions ev
             LEFT JOIN estimates e ON e.id=ev.estimate_id
            WHERE ev.id=ANY(%s)
            ORDER BY ev.id""",
        (normalized_ids,),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def build_readiness_report(cur):
    schema = load_schema(cur)
    contract_rows = load_contract_item_rows(cur, schema)
    snapshot_rows = None
    if (
        not _missing(schema, "brigade_contract_items", LINEAGE_COLUMNS)
        and not _missing(schema, "estimate_versions", SNAPSHOT_COLUMNS)
    ):
        snapshot_rows = load_snapshot_rows(
            cur,
            schema,
            [row.get("source_estimate_version_id") for row in contract_rows],
        )
    return build_report_from_rows(
        schema,
        contract_rows,
        snapshot_rows=snapshot_rows,
    )


def run_readiness_report(get_db):
    conn = get_db()
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            result = build_readiness_report(cur)
            conn.rollback()
            result["rolledBack"] = True
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    print(json.dumps(run_readiness_report(get_db), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
