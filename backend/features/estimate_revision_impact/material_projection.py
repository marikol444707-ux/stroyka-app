"""Bounded read-only A7.3 material revision projection."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from backend.features.brigade_lineage.canonical import parse_sections
from backend.features.estimate_row_transfer.policy import (
    is_explicit_material_item,
)

from .baseline import collect_baseline_audit, run_baseline_audit
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)


PREVIEW_LIMIT = 100
MAX_MATERIAL_ROWS = 1000
MAX_ALIAS_ROWS = 200
MATERIAL_REQUIRED_COLUMNS = {
    "projects": {"id", "company_id", "name"},
    "estimates": {
        "id", "company_id", "project_id", "work_package", "sections_json",
    },
    "material_aliases": {
        "id", "project_name", "alias_name", "canonical_name",
        "canonical_unit", "active",
    },
}


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _name_key(value):
    return " ".join(_text(value).casefold().replace("ё", "е").split())


def _unit_key(value):
    raw = _name_key(value).replace("²", "2").replace("³", "3").replace(" ", "")
    aliases = {
        "штук": "шт", "штука": "шт", "штуки": "шт",
        "килограмм": "кг", "килограмма": "кг", "килограммов": "кг",
        "литр": "л", "литра": "л", "литров": "л",
        "м²": "м2", "м³": "м3",
    }
    return aliases.get(raw, raw)


def _quantity(value):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number <= 0 or number.as_tuple().exponent < -6:
        return None
    return number.normalize()


def _item_key(estimate_id, section_index, item_index, item):
    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        raw = item.get(field)
        if raw in (None, ""):
            continue
        if not isinstance(raw, str) or raw != raw.strip() or len(raw) > 255:
            return None, None, "material_item_key_invalid"
        if raw not in keys:
            keys.append(raw)
    if len(keys) > 1:
        return None, None, "material_item_key_ambiguous"
    if keys:
        return keys[0], True, None
    return f"{estimate_id}:{section_index}:{item_index}", False, None


def _coordinate(row):
    return {
        "estimateId": row["estimateId"],
        "sectionIndex": row["sectionIndex"],
        "itemIndex": row["itemIndex"],
    }


def _review(row, reason_code):
    item = {
        "sourceKind": "material",
        "sourceId": row.get("estimateId"),
        "reasonCode": reason_code,
    }
    if isinstance(row.get("sectionIndex"), int):
        item["sectionIndex"] = row["sectionIndex"]
    if isinstance(row.get("itemIndex"), int):
        item["itemIndex"] = row["itemIndex"]
    return item


def _material_rows(estimate_id, sections):
    rows = []
    reviews = []
    if not isinstance(sections, list):
        return [], [_review({"estimateId": estimate_id}, "material_snapshot_invalid")]
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict) or not isinstance(section.get("items") or [], list):
            reviews.append(_review(
                {"estimateId": estimate_id, "sectionIndex": section_index},
                "material_snapshot_invalid",
            ))
            continue
        for item_index, item in enumerate(section.get("items") or []):
            if not isinstance(item, dict):
                reviews.append(_review({
                    "estimateId": estimate_id,
                    "sectionIndex": section_index,
                    "itemIndex": item_index,
                }, "material_snapshot_invalid"))
                continue
            if not is_explicit_material_item(item):
                continue
            base = {
                "estimateId": estimate_id,
                "sectionIndex": section_index,
                "itemIndex": item_index,
            }
            key, stable_key, key_error = _item_key(
                estimate_id, section_index, item_index, item,
            )
            name = _name_key(item.get("name"))
            unit = _unit_key(item.get("unit"))
            quantity = _quantity(item.get("quantity"))
            plan_issue = any(_text(item.get(field)) for field in (
                "materialPlanIssue", "material_plan_issue", "planIssue",
                "plan_issue", "normIssue", "norm_issue",
            ))
            reason = key_error
            if reason is None and not name:
                reason = "material_identity_invalid"
            if reason is None and not unit:
                reason = "material_unit_invalid"
            if reason is None and quantity is None:
                reason = "material_quantity_invalid"
            if reason is None and plan_issue:
                reason = "material_norm_ambiguous"
            if reason:
                reviews.append(_review(base, reason))
                continue
            rows.append({
                **base,
                "itemKey": key,
                "stableKey": stable_key,
                "nameKey": name,
                "unitKey": unit,
                "quantity": quantity,
                "aliasIdentity": None,
                "aliasIds": [],
            })
    return rows, reviews


def _alias_rules(aliases):
    rules = []
    invalid_ids = []
    for alias in aliases or []:
        if not isinstance(alias, dict) or alias.get("active") is False:
            continue
        alias_id = _positive_int(alias.get("id"))
        alias_name = _name_key(alias.get("alias_name") or alias.get("aliasName"))
        canonical_name = _name_key(
            alias.get("canonical_name") or alias.get("canonicalName")
        )
        canonical_unit = _unit_key(
            alias.get("canonical_unit") or alias.get("canonicalUnit")
        )
        if not alias_id or not alias_name or not canonical_name:
            invalid_ids.append(alias_id)
            continue
        rules.append({
            "id": alias_id,
            "names": {alias_name, canonical_name},
            "identity": (canonical_name, canonical_unit),
        })
    return rules, invalid_ids


def _attach_aliases(rows, rules):
    reviews = []
    for row in rows:
        candidates = [
            rule for rule in rules
            if row["nameKey"] in rule["names"]
            and (not rule["identity"][1] or rule["identity"][1] == row["unitKey"])
        ]
        identities = {rule["identity"] for rule in candidates}
        if len(identities) > 1:
            reviews.append(_review(row, "material_alias_ambiguous"))
            row["invalid"] = True
        elif len(identities) == 1:
            row["aliasIdentity"] = next(iter(identities))
            row["aliasIds"] = sorted({rule["id"] for rule in candidates})
    return reviews


def _pair_result(base, target, match_kind):
    change_kinds = []
    if base["quantity"] != target["quantity"]:
        change_kinds.append("quantity_changed")
    if base["nameKey"] != target["nameKey"]:
        change_kinds.append("alias_identity_changed" if match_kind == "confirmed_alias" else "identity_changed")
    return {
        "base": _coordinate(base),
        "target": _coordinate(target),
        "matchKind": match_kind,
        "aliasIds": sorted(set(base["aliasIds"] + target["aliasIds"])),
        "changeKinds": sorted(change_kinds),
    }


def build_material_projection(context, base_sections, target_sections, aliases, *, scan_complete=True):
    """Compare exact material rows without exposing material business text."""

    base_rows, reviews = _material_rows(context["baseEstimateId"], base_sections)
    target_rows, target_reviews = _material_rows(
        context["targetEstimateId"], target_sections,
    )
    reviews.extend(target_reviews)
    rules, invalid_alias_ids = _alias_rules(aliases)
    if invalid_alias_ids:
        reviews.append({
            "sourceKind": "materialAlias",
            "sourceId": next((item for item in invalid_alias_ids if item), None),
            "reasonCode": "material_alias_invalid",
        })
        rules = []
    if rules and context.get("projectNameOwnerCount") != 1:
        reviews.append({
            "sourceKind": "project",
            "sourceId": _positive_int(context.get("projectId")),
            "reasonCode": "material_alias_owner_ambiguous",
        })
        rules = []
    reviews.extend(_attach_aliases(base_rows, rules))
    reviews.extend(_attach_aliases(target_rows, rules))

    key_counts = Counter(
        (side, row["itemKey"])
        for side, rows in (("base", base_rows), ("target", target_rows))
        for row in rows if row["stableKey"] and not row.get("invalid")
    )
    duplicate_keys = {
        (side, key) for side, key in key_counts
        if key_counts[(side, key)] > 1
    }
    for side, rows in (("base", base_rows), ("target", target_rows)):
        for row in rows:
            if row["stableKey"] and (side, row["itemKey"]) in duplicate_keys:
                reviews.append(_review(row, "material_item_key_duplicate"))
                row["invalid"] = True

    paired = []
    base_by_key = {
        row["itemKey"]: row for row in base_rows
        if row["stableKey"] and not row.get("invalid")
    }
    target_by_key = {
        row["itemKey"]: row for row in target_rows
        if row["stableKey"] and not row.get("invalid")
    }
    for key in sorted(set(base_by_key).intersection(target_by_key)):
        base = base_by_key[key]
        target = target_by_key[key]
        if base["unitKey"] != target["unitKey"]:
            reviews.append(_review(base, "material_unit_changed"))
            reviews.append(_review(target, "material_unit_changed"))
            base["invalid"] = target["invalid"] = True
            continue
        base["paired"] = target["paired"] = True
        paired.append(_pair_result(base, target, "stable_item_key"))

    alias_groups = defaultdict(lambda: {"base": [], "target": []})
    for side, rows in (("base", base_rows), ("target", target_rows)):
        for row in rows:
            if not row.get("invalid") and not row.get("paired") and row["aliasIdentity"]:
                alias_groups[row["aliasIdentity"]][side].append(row)
    for identity in sorted(alias_groups):
        group = alias_groups[identity]
        if len(group["base"]) > 1 or len(group["target"]) > 1:
            for row in group["base"] + group["target"]:
                reviews.append(_review(row, "material_alias_match_ambiguous"))
                row["invalid"] = True
            continue
        if len(group["base"]) == len(group["target"]) == 1:
            base, target = group["base"][0], group["target"][0]
            if base["unitKey"] != target["unitKey"]:
                reviews.append(_review(base, "material_unit_changed"))
                reviews.append(_review(target, "material_unit_changed"))
                base["invalid"] = target["invalid"] = True
                continue
            base["paired"] = target["paired"] = True
            paired.append(_pair_result(base, target, "confirmed_alias"))

    changed = [item for item in paired if item["changeKinds"]]
    base_only = [
        _coordinate(row) for row in base_rows
        if not row.get("invalid") and not row.get("paired")
    ]
    target_only = [
        _coordinate(row) for row in target_rows
        if not row.get("invalid") and not row.get("paired")
    ]
    facts_truncated = any(
        len(items) > PREVIEW_LIMIT for items in (changed, base_only, target_only)
    )
    reason_counts = Counter(item["reasonCode"] for item in reviews)
    reviews_truncated = len(reviews) > PREVIEW_LIMIT
    complete = bool(scan_complete) and not reviews and not facts_truncated
    state = "complete" if complete else (
        "incomplete" if not scan_complete or facts_truncated else "review_required"
    )
    return {
        "state": state,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": bool(scan_complete),
        "complete": complete,
        "summary": {
            "baseMaterialRows": len(base_rows),
            "targetMaterialRows": len(target_rows),
            "pairedRows": len(paired),
            "changedPairs": len(changed),
            "baseOnlyRows": len(base_only),
            "targetOnlyRows": len(target_only),
            "needsReview": len(reviews),
        },
        "changedPairs": changed[:PREVIEW_LIMIT],
        "baseOnlyRows": base_only[:PREVIEW_LIMIT],
        "targetOnlyRows": target_only[:PREVIEW_LIMIT],
        "factsTruncated": facts_truncated,
        "reasonCounts": dict(sorted(reason_counts.items())),
        "needsReview": reviews[:PREVIEW_LIMIT],
        "needsReviewTruncated": reviews_truncated,
    }


def _empty_projection(state, reason_code=None, *, schema_ready=True, missing_columns=None):
    reviews = []
    reason_counts = {}
    if reason_code:
        reviews = [{
            "sourceKind": "material",
            "sourceId": None,
            "reasonCode": reason_code,
        }]
        reason_counts = {reason_code: 1}
    return {
        "state": state,
        "schemaReady": bool(schema_ready),
        "missingColumns": list(missing_columns or []),
        "scanComplete": state not in ("not_collected", "incomplete"),
        "complete": False,
        "summary": {
            "baseMaterialRows": 0,
            "targetMaterialRows": 0,
            "pairedRows": 0,
            "changedPairs": 0,
            "baseOnlyRows": 0,
            "targetOnlyRows": 0,
            "needsReview": len(reviews),
        },
        "changedPairs": [],
        "baseOnlyRows": [],
        "targetOnlyRows": [],
        "factsTruncated": False,
        "reasonCounts": reason_counts,
        "needsReview": reviews,
        "needsReviewTruncated": False,
    }


def _load_material_schema(cur):
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(MATERIAL_REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    return sorted(
        table + "." + column
        for table, columns in MATERIAL_REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )


def _load_estimate_pair(cur, source_context):
    estimate_ids = [
        source_context["baseEstimateId"], source_context["estimateId"],
    ]
    cur.execute(
        """SELECT id AS estimate_id,company_id,project_id,
                  COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                  sections_json
             FROM public.estimates
            WHERE id=ANY(%s) AND company_id=%s AND project_id=%s
            ORDER BY id
            LIMIT 3""",
        (
            estimate_ids,
            source_context["companyId"],
            source_context["projectId"],
        ),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_project_identity(cur, source_context):
    cur.execute(
        """SELECT p.name AS project_name,
                  (SELECT COUNT(*) FROM public.projects same_name
                    WHERE same_name.name=p.name) AS owner_count
             FROM public.projects p
            WHERE p.id=%s AND p.company_id=%s
            ORDER BY p.id
            LIMIT 2""",
        (source_context["projectId"], source_context["companyId"]),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows[0] if len(rows) == 1 else None


def _load_aliases(cur, project_name):
    cur.execute(
        """SELECT id,project_name,alias_name,canonical_name,canonical_unit,active
             FROM public.material_aliases
            WHERE active=TRUE
              AND (project_name=%s OR COALESCE(project_name,'')='')
            ORDER BY COALESCE(project_name,'') DESC,id
            LIMIT %s""",
        (project_name, MAX_ALIAS_ROWS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _parsed_sections(value):
    try:
        return parse_sections(value)
    except (
        TypeError, ValueError, json.JSONDecodeError, RecursionError,
        UnicodeError, OverflowError,
    ):
        return None


def _explicit_material_count(sections):
    return sum(
        1
        for section in sections or []
        if isinstance(section, dict)
        for item in (section.get("items") or [])
        if is_explicit_material_item(item)
    )


def collect_material_impact_audit(cur, source):
    """Collect A7.1 source plus exact A7.3 material evidence."""

    report = collect_baseline_audit(cur, source)
    if not report.get("readyForDomainScan"):
        report["readyForMaterialProjection"] = False
        report["materialImpact"] = _empty_projection("not_collected")
        return report

    missing = _load_material_schema(cur)
    if missing:
        report["readyForMaterialProjection"] = False
        report["materialImpact"] = _empty_projection(
            "incomplete",
            "material_impact_schema_not_ready",
            schema_ready=False,
            missing_columns=missing,
        )
        return report

    source_context = report["source"]
    estimates = _load_estimate_pair(cur, source_context)
    estimates_by_id = {
        _positive_int(row.get("estimate_id")): row for row in estimates
    }
    base = estimates_by_id.get(source_context["baseEstimateId"])
    target = estimates_by_id.get(source_context["estimateId"])
    if len(estimates) != 2 or base is None or target is None:
        projection = _empty_projection(
            "review_required", "material_estimate_pair_invalid",
        )
    elif base.get("work_package") != target.get("work_package"):
        projection = _empty_projection(
            "review_required", "material_estimate_package_mismatch",
        )
    else:
        base_sections = _parsed_sections(base.get("sections_json"))
        target_sections = _parsed_sections(target.get("sections_json"))
        if base_sections is None or target_sections is None:
            projection = _empty_projection(
                "review_required", "material_snapshot_invalid",
            )
        elif max(
            _explicit_material_count(base_sections),
            _explicit_material_count(target_sections),
        ) > MAX_MATERIAL_ROWS:
            projection = _empty_projection(
                "incomplete", "material_scan_limit_exceeded",
            )
        else:
            project = _load_project_identity(cur, source_context)
            if project is None or not _text(project.get("project_name")):
                projection = _empty_projection(
                    "review_required", "material_project_identity_invalid",
                )
            else:
                aliases = _load_aliases(cur, project["project_name"])
                if len(aliases) > MAX_ALIAS_ROWS:
                    projection = _empty_projection(
                        "incomplete", "material_alias_scan_limit_exceeded",
                    )
                else:
                    context = {
                        "companyId": source_context["companyId"],
                        "projectId": source_context["projectId"],
                        "projectNameOwnerCount": project.get("owner_count"),
                        "baseEstimateId": source_context["baseEstimateId"],
                        "targetEstimateId": source_context["estimateId"],
                        "workPackage": base["work_package"],
                    }
                    projection = build_material_projection(
                        context, base_sections, target_sections, aliases,
                    )
    report["readyForMaterialProjection"] = projection["complete"]
    report["materialImpact"] = projection
    return report


def run_material_impact_audit(get_db, source):
    return run_baseline_audit(
        get_db,
        source,
        collect_data=collect_material_impact_audit,
    )


def _source_from_args(args):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": args.company_id,
        "projectId": args.project_id,
        "estimateId": args.estimate_id,
        "sourceRevision": args.source_revision,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only exact estimate revision material impact audit",
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    try:
        source = _source_from_args(args)
    except EstimateRevisionImpactContractError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_material_impact_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForMaterialProjection") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MATERIAL_REQUIRED_COLUMNS",
    "MAX_ALIAS_ROWS",
    "MAX_MATERIAL_ROWS",
    "PREVIEW_LIMIT",
    "build_material_projection",
    "collect_material_impact_audit",
    "run_material_impact_audit",
]
