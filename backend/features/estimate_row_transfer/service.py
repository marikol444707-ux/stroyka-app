"""Authoritative repeatable-read plan resolution for E4.2."""

import json
import re

from backend.features.brigade_lineage.canonical import parse_sections, sections_sha256
from backend.features.brigade_lineage.snapshot_service import (
    LineageResolutionError,
    resolve_snapshot_item,
)
from backend.features.estimate_row_transfer.audit import collect_transfer_impact
from backend.features.estimate_row_transfer.plan import (
    PlanValidationError,
    build_reviewed_plan,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except (IndexError, TypeError):
        return None


def load_reconciliation_scope(cur, reconciliation_id):
    """Load only the owner boundary needed before the full impact scan."""
    cur.execute(
        """SELECT b.company_id,b.project_id,
                  COALESCE(NULLIF(r.work_package,''),'Основная') AS work_package
             FROM public.estimate_reconciliations r
             JOIN public.estimates b ON b.id=r.base_estimate_id
            WHERE r.id=%s""",
        (reconciliation_id,),
    )
    row = cur.fetchone()
    company_id = _positive_int(_row_value(row, "company_id", 0))
    project_id = _positive_int(_row_value(row, "project_id", 1))
    work_package = str(_row_value(row, "work_package", 2) or "").strip()
    if not company_id or not project_id or not work_package:
        return None
    return {
        "companyId": company_id,
        "projectId": project_id,
        "workPackage": work_package,
    }


def _validated_snapshot(row, *, estimate_id, expected_hash, error_prefix):
    snapshot_id = _positive_int(_row_value(row, "id", 0))
    stored_estimate_id = _positive_int(_row_value(row, "estimate_id", 1))
    raw_sections = _row_value(row, "sections_json", 2)
    stored_hash = _row_value(row, "sections_sha256", 3)
    if not snapshot_id or stored_estimate_id != estimate_id:
        raise PlanValidationError(error_prefix + "_identity_mismatch")
    if (
        not isinstance(stored_hash, str)
        or stored_hash != stored_hash.strip().lower()
        or not _SHA256_RE.fullmatch(stored_hash)
        or stored_hash != expected_hash
    ):
        raise PlanValidationError(error_prefix + "_hash_mismatch")
    try:
        sections = parse_sections(raw_sections)
        actual_hash = sections_sha256(sections)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ):
        raise PlanValidationError(error_prefix + "_content_invalid")
    if actual_hash != stored_hash:
        raise PlanValidationError(error_prefix + "_hash_mismatch")
    return snapshot_id, sections, stored_hash


def _resolve_target_snapshot(cur, report):
    target = dict(report.get("targetSnapshot") or {})
    estimate_id = _positive_int(target.get("estimateId"))
    digest = target.get("sectionsSha256")
    if not estimate_id or not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise PlanValidationError("target_snapshot_context_invalid")
    cur.execute(
        """SELECT id,estimate_id,sections_json,sections_sha256
             FROM public.estimate_versions
            WHERE estimate_id=%s AND sections_sha256=%s
            ORDER BY id LIMIT 2""",
        (estimate_id, digest),
    )
    rows = cur.fetchall() or []
    if not rows:
        raise PlanValidationError("target_snapshot_missing")
    if len(rows) != 1:
        raise PlanValidationError("target_snapshot_ambiguous")
    snapshot_id, _sections, _stored_hash = _validated_snapshot(
        rows[0],
        estimate_id=estimate_id,
        expected_hash=digest,
        error_prefix="target_snapshot",
    )
    report["targetSnapshot"] = {**target, "estimateVersionId": snapshot_id}


def _supply_candidate(report, entry):
    matches = [
        candidate
        for candidate in (report.get("supplyCandidates") or [])
        if candidate.get("sourceId") == entry["sourceId"]
        and candidate.get("requestItemIndex") == entry["requestItemIndex"]
    ]
    if len(matches) != 1:
        raise PlanValidationError("supply_source_not_candidate")
    return matches[0]


def _resolve_supply_snapshots(cur, report, entries):
    supply_entries = [entry for entry in entries if entry["sourceKind"] == "supply"]
    if not supply_entries:
        return {}
    version_ids = sorted({entry["sourceEstimateVersionId"] for entry in supply_entries})
    cur.execute(
        """SELECT id,estimate_id,sections_json,sections_sha256
             FROM public.estimate_versions
            WHERE id=ANY(%s)
            ORDER BY id""",
        (version_ids,),
    )
    rows = {
        _positive_int(_row_value(row, "id", 0)): row
        for row in (cur.fetchall() or [])
    }
    base_snapshot = dict(report.get("baseSnapshot") or {})
    base_estimate_id = _positive_int(base_snapshot.get("estimateId"))
    base_hash = base_snapshot.get("sectionsSha256")
    snapshots = {}
    for entry in supply_entries:
        row = rows.get(entry["sourceEstimateVersionId"])
        if not row:
            raise PlanValidationError("supply_source_snapshot_missing")
        snapshot_id, sections, digest = _validated_snapshot(
            row,
            estimate_id=base_estimate_id,
            expected_hash=base_hash,
            error_prefix="supply_source_snapshot",
        )
        candidate = _supply_candidate(report, entry)
        source = dict(candidate.get("source") or {})
        try:
            resolved = resolve_snapshot_item(
                estimate_id=base_estimate_id,
                sections=sections,
                section_index=source.get("sectionIndex"),
                item_index=source.get("itemIndex"),
                expected_item_key=source.get("itemKey"),
            )
        except LineageResolutionError:
            raise PlanValidationError("supply_source_snapshot_coordinate_invalid")
        key = (entry["sourceId"], entry["requestItemIndex"], snapshot_id)
        snapshots[key] = {
            "estimateId": base_estimate_id,
            "estimateVersionId": snapshot_id,
            "sectionIndex": resolved.source_section_index,
            "itemIndex": resolved.source_item_index,
            "itemKey": resolved.source_item_key,
            "sectionsSha256": digest,
        }
    return snapshots


def build_current_plan(cur, payload, *, impact_collector=collect_transfer_impact):
    reconciliation_id = payload["reconciliationId"]
    entries = payload["entries"]
    report = impact_collector(cur, reconciliation_id, entries)
    _resolve_target_snapshot(cur, report)
    supply_snapshots = _resolve_supply_snapshots(cur, report, entries)
    return build_reviewed_plan(report, entries, supply_snapshots)
