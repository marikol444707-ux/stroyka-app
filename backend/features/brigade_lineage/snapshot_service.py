"""Exact immutable snapshot resolution for estimate-derived assignments."""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .canonical import parse_sections, sections_sha256


class LineageResolutionError(ValueError):
    """Bounded fail-closed error that never includes estimate business data."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ResolvedSnapshotItem:
    source_section_index: int
    source_item_index: int
    source_item_key: str
    section: dict
    item: dict


@dataclass(frozen=True)
class SnapshotItemCoordinate:
    section_index: object
    item_index: object
    expected_item_key: object


@dataclass(frozen=True)
class EstimateSnapshotLineage:
    source_type: str
    source_estimate_version_id: int
    source_section_index: int
    source_item_index: int
    source_item_key: str
    sections_sha256: str
    section: dict
    item: dict
    snapshot_created: bool


def _strict_positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _strict_non_negative_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _row_value(row, index, name):
    if isinstance(row, Mapping):
        return row.get(name)
    try:
        return row[index]
    except (IndexError, TypeError):
        return None


def _bounded_key(value, *, missing_code):
    if value in (None, ""):
        raise LineageResolutionError(missing_code)
    if not isinstance(value, str) or value != value.strip() or len(value) > 255:
        raise LineageResolutionError("source_item_key_noncanonical")
    return value


def resolve_snapshot_item(
    *,
    estimate_id,
    sections,
    section_index,
    item_index,
    expected_item_key,
):
    """Resolve one exact coordinate and verify its canonical item key."""

    estimate_id = _strict_positive_int(estimate_id)
    section_index = _strict_non_negative_int(section_index)
    item_index = _strict_non_negative_int(item_index)
    if not estimate_id:
        raise LineageResolutionError("source_estimate_invalid")
    if section_index is None or item_index is None:
        raise LineageResolutionError("source_coordinate_invalid")

    try:
        parsed_sections = parse_sections(sections)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError, UnicodeError, OverflowError):
        raise LineageResolutionError("snapshot_content_invalid")

    try:
        section = parsed_sections[section_index]
        items = section["items"]
        item = items[item_index]
    except (IndexError, KeyError):
        raise LineageResolutionError("source_coordinate_not_found")
    except TypeError:
        raise LineageResolutionError("snapshot_content_invalid")
    if not isinstance(section, dict) or not isinstance(items, list) or not isinstance(item, dict):
        raise LineageResolutionError("snapshot_content_invalid")

    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        raw_value = item.get(field)
        if raw_value in (None, ""):
            continue
        key = _bounded_key(raw_value, missing_code="source_item_key_missing")
        if key not in keys:
            keys.append(key)
    if len(keys) > 1:
        raise LineageResolutionError("source_item_key_ambiguous")
    source_item_key = keys[0] if keys else f"{estimate_id}:{section_index}:{item_index}"
    source_item_key = _bounded_key(source_item_key, missing_code="source_item_key_missing")
    expected_item_key = _bounded_key(expected_item_key, missing_code="source_item_key_required")
    if expected_item_key != source_item_key:
        raise LineageResolutionError("source_item_key_mismatch")

    return ResolvedSnapshotItem(
        source_section_index=section_index,
        source_item_index=item_index,
        source_item_key=source_item_key,
        section=section,
        item=item,
    )


def _decimal(value):
    try:
        result = Decimal(str(value if value is not None else 0).replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)
    return result if result.is_finite() else Decimal(0)


def _snapshot_total(sections):
    total = Decimal(0)
    for section in sections:
        if not isinstance(section, dict):
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict):
                continue
            quantity = _decimal(item.get("quantity"))
            if item.get("isImported"):
                total_work = _decimal(item.get("totalWork") or item.get("workTotal") or item.get("workSum"))
                total_material = _decimal(item.get("totalMaterial") or item.get("materialTotal") or item.get("materialSum"))
                line_total = _decimal(
                    item.get("lineTotal")
                    or item.get("currentTotal")
                    or item.get("total")
                    or item.get("sum")
                    or item.get("amount")
                    or item.get("totalSum")
                )
                if total_work or total_material:
                    total += total_work + total_material
                elif line_total:
                    total += line_total
                else:
                    total += quantity * (_decimal(item.get("priceWork")) + _decimal(item.get("priceMaterial")))
            else:
                total += quantity * (_decimal(item.get("priceWork")) + _decimal(item.get("priceMaterial")))
    return total


def _snapshot_json(raw_sections, parsed_sections):
    if isinstance(raw_sections, str):
        return raw_sections
    return json.dumps(parsed_sections, ensure_ascii=False)


def _validated_coordinates(coordinates):
    if not isinstance(coordinates, (list, tuple)) or not coordinates:
        raise LineageResolutionError("source_coordinates_required")
    validated = []
    seen = set()
    for coordinate in coordinates:
        if not isinstance(coordinate, SnapshotItemCoordinate):
            raise LineageResolutionError("source_coordinate_invalid")
        section_index = _strict_non_negative_int(coordinate.section_index)
        item_index = _strict_non_negative_int(coordinate.item_index)
        if section_index is None or item_index is None:
            raise LineageResolutionError("source_coordinate_invalid")
        expected_item_key = _bounded_key(
            coordinate.expected_item_key,
            missing_code="source_item_key_required",
        )
        coordinate_key = (section_index, item_index)
        if coordinate_key in seen:
            raise LineageResolutionError("source_coordinate_duplicate")
        seen.add(coordinate_key)
        validated.append(SnapshotItemCoordinate(section_index, item_index, expected_item_key))
    return validated


def ensure_estimate_snapshot_lineages(
    cur,
    *,
    estimate_id,
    company_id,
    project_id,
    coordinates,
    created_by="",
):
    """Resolve an assignment batch against one exact current snapshot.

    The caller owns the surrounding transaction. This function never commits or
    rolls back and never accepts ownership or snapshot metadata from a client.
    """

    estimate_id = _strict_positive_int(estimate_id)
    company_id = _strict_positive_int(company_id)
    project_id = _strict_positive_int(project_id)
    if not estimate_id or not company_id or not project_id:
        raise LineageResolutionError("estimate_owner_invalid")
    coordinates = _validated_coordinates(coordinates)

    cur.execute(
        """SELECT id, company_id, project_id, version, sections_json
             FROM public.estimates
            WHERE id=%s AND company_id=%s AND project_id=%s
            FOR UPDATE""",
        (estimate_id, company_id, project_id),
    )
    estimate = cur.fetchone()
    if not estimate:
        raise LineageResolutionError("estimate_owner_not_found")
    if (
        _row_value(estimate, 0, "id") != estimate_id
        or _row_value(estimate, 1, "company_id") != company_id
        or _row_value(estimate, 2, "project_id") != project_id
    ):
        raise LineageResolutionError("estimate_owner_mismatch")

    raw_sections = _row_value(estimate, 4, "sections_json")
    try:
        parsed_sections = parse_sections(raw_sections)
        digest = sections_sha256(parsed_sections)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError, UnicodeError, OverflowError):
        raise LineageResolutionError("snapshot_content_invalid")
    resolved_items = []
    for coordinate in coordinates:
        resolved = resolve_snapshot_item(
            estimate_id=estimate_id,
            sections=parsed_sections,
            section_index=coordinate.section_index,
            item_index=coordinate.item_index,
            expected_item_key=coordinate.expected_item_key,
        )
        resolved_items.append(resolved)

    cur.execute(
        """SELECT id, sections_json, sections_sha256
             FROM public.estimate_versions
            WHERE estimate_id=%s AND sections_sha256=%s
            ORDER BY id LIMIT 2 FOR UPDATE""",
        (estimate_id, digest),
    )
    snapshots = cur.fetchall()
    if len(snapshots) > 1:
        raise LineageResolutionError("snapshot_hash_ambiguous")

    snapshot_created = False
    if snapshots:
        snapshot = snapshots[0]
        snapshot_id = _strict_positive_int(_row_value(snapshot, 0, "id"))
        stored_hash = _row_value(snapshot, 2, "sections_sha256")
        try:
            stored_content_hash = sections_sha256(_row_value(snapshot, 1, "sections_json"))
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError, UnicodeError, OverflowError):
            raise LineageResolutionError("snapshot_hash_mismatch")
        if not snapshot_id or stored_hash != digest or stored_content_hash != digest:
            raise LineageResolutionError("snapshot_hash_mismatch")
    else:
        version_label = str(_row_value(estimate, 3, "version") or "")[:100]
        snapshot_json = _snapshot_json(raw_sections, parsed_sections)
        cur.execute(
            """INSERT INTO public.estimate_versions
                 (estimate_id, version_label, sections_json, total, comment, created_by, sections_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                estimate_id,
                version_label,
                snapshot_json,
                _snapshot_total(parsed_sections),
                "Assignment source snapshot",
                str(created_by or "").strip()[:255],
                digest,
            ),
        )
        inserted = cur.fetchone()
        snapshot_id = _strict_positive_int(_row_value(inserted, 0, "id"))
        if not snapshot_id:
            raise LineageResolutionError("snapshot_insert_failed")
        snapshot_created = True

    return [
        EstimateSnapshotLineage(
            source_type="estimate",
            source_estimate_version_id=snapshot_id,
            source_section_index=resolved.source_section_index,
            source_item_index=resolved.source_item_index,
            source_item_key=resolved.source_item_key,
            sections_sha256=digest,
            section=resolved.section,
            item=resolved.item,
            snapshot_created=snapshot_created,
        )
        for resolved in resolved_items
    ]
