"""Validate exact estimate-row lineage for material-control supply requests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


MATERIAL_CONTROL_REQUEST_SOURCE = "estimate_material_control"
LINEAGE_VERSION = 1


class MaterialControlLineageError(ValueError):
    """Raised when an estimate-backed request cannot prove its source rows."""


def _exact_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or not normalized.isascii() or not normalized.isdigit():
        return None
    parsed = int(normalized)
    return parsed


def _positive_int(value: Any) -> int | None:
    parsed = _exact_int(value)
    if parsed is None:
        return None
    return parsed if parsed > 0 else None


def _non_negative_int(value: Any) -> int | None:
    parsed = _exact_int(value)
    if parsed is None:
        return None
    return parsed if parsed >= 0 else None


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _package(value: Any) -> str:
    return _text(value) or "Основная"


def material_control_request_intent(request_source: str, request_notes: str = "") -> bool:
    notes = _text(request_notes)
    return (
        _text(request_source) == MATERIAL_CONTROL_REQUEST_SOURCE
        or "MATERIAL_CONTROL_REQUEST:" in notes
        or "Создано из контроля материалов" in notes
    )


def material_control_estimate_ids(items: list[dict]) -> list[int]:
    estimate_ids: set[int] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        lineage = item.get("estimateLineage")
        if not isinstance(lineage, dict):
            continue
        for source in lineage.get("sources") or []:
            if not isinstance(source, dict):
                continue
            estimate_id = _positive_int(source.get("estimateId"))
            if estimate_id is not None:
                estimate_ids.add(estimate_id)
    return sorted(estimate_ids)


def load_material_control_estimates(cur, estimate_ids: list[int]) -> dict[int, dict]:
    if not estimate_ids:
        return {}
    cur.execute(
        """
        SELECT id,company_id,project_id,project_name,status,
               COALESCE(smeta_type,'Заказчик') AS smeta_type,
               COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
               sections_json
          FROM estimates
         WHERE id = ANY(%s)
        """,
        (estimate_ids,),
    )
    rows = cur.fetchall() or []
    result: dict[int, dict] = {}
    for row in rows:
        if isinstance(row, dict):
            normalized = dict(row)
        else:
            normalized = {
                "id": row[0],
                "company_id": row[1],
                "project_id": row[2],
                "project_name": row[3],
                "status": row[4],
                "smeta_type": row[5],
                "work_package": row[6],
                "sections_json": row[7],
            }
        estimate_id = _positive_int(normalized.get("id"))
        if estimate_id is not None:
            result[estimate_id] = normalized
    return result


def validate_material_control_request_lineage(
    *,
    request_source: str,
    request_notes: str = "",
    project_name: str,
    company_id: int,
    work_package: str,
    items: list[dict],
    estimates_by_id: dict[int, dict],
    parse_sections: Callable[[Any], list],
    item_type: Callable[[dict, str], str],
    item_plan_issue: Callable[[dict, str], str],
    material_key: Callable[[str, str, str], Any],
    normalize_unit: Callable[[str], str],
    item_quantity: Callable[[dict], float] | None = None,
) -> list[dict]:
    if not material_control_request_intent(request_source, request_notes):
        return items
    if _text(request_source) != MATERIAL_CONTROL_REQUEST_SOURCE:
        raise MaterialControlLineageError(
            "устаревший формат заявки; обновите приложение и повторите действие"
        )

    request_project = _text(project_name)
    request_package = _package(work_package)
    if not request_project:
        raise MaterialControlLineageError("У заявки из контроля материалов не указан объект")
    if not items:
        raise MaterialControlLineageError("Заявка из контроля материалов не содержит позиций")

    validated_items: list[dict] = []
    for item_index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            raise MaterialControlLineageError(f"Позиция {item_index}: неверный формат")
        item = deepcopy(raw_item)
        if _text(item.get("sourceType")) != MATERIAL_CONTROL_REQUEST_SOURCE:
            raise MaterialControlLineageError(
                f"Позиция {item_index}: нет проверяемой связи с материалом сметы"
            )
        lineage = item.get("estimateLineage")
        if not isinstance(lineage, dict) or lineage.get("version") != LINEAGE_VERSION:
            raise MaterialControlLineageError(
                f"Позиция {item_index}: нет проверяемой связи с материалом сметы"
            )
        if _text(lineage.get("projectName")) != request_project:
            raise MaterialControlLineageError(
                f"Позиция {item_index}: источник относится к другому объекту"
            )
        if _package(lineage.get("workPackage")) != request_package:
            raise MaterialControlLineageError(
                f"Позиция {item_index}: источник относится к другому пакету сметы"
            )

        sources = lineage.get("sources")
        if not isinstance(sources, list) or not sources:
            raise MaterialControlLineageError(
                f"Позиция {item_index}: нет проверяемой связи с материалом сметы"
            )

        item_name = _text(item.get("materialName") or item.get("name"))
        item_unit = _text(item.get("unit"))
        item_key = material_key(request_project, item_name, item_unit)
        seen_coordinates: set[tuple[int, int, int]] = set()
        validated_sources: list[dict] = []

        for source_index, raw_source in enumerate(sources, start=1):
            if not isinstance(raw_source, dict):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}, источник {source_index}: неверный формат"
                )
            source = deepcopy(raw_source)
            estimate_id = _positive_int(source.get("estimateId"))
            section_index = _non_negative_int(source.get("sectionIndex"))
            estimate_item_index = _non_negative_int(source.get("itemIndex"))
            if estimate_id is None or section_index is None or estimate_item_index is None:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: нет проверяемой связи с конкретной строкой сметы"
                )
            coordinate = (estimate_id, section_index, estimate_item_index)
            if coordinate in seen_coordinates:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: строка сметы указана повторно"
                )
            seen_coordinates.add(coordinate)

            estimate = estimates_by_id.get(estimate_id)
            if not estimate:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} не найдена"
                )
            if _positive_int(estimate.get("company_id")) != _positive_int(company_id):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} принадлежит другой компании"
                )
            if _text(estimate.get("project_name")) != request_project:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} относится к другому объекту"
                )
            if _package(estimate.get("work_package")) != request_package:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} относится к другому пакету"
                )
            if _text(estimate.get("status")).lower() != "активная":
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} больше не активна"
                )
            if _text(estimate.get("smeta_type")) not in ("Заказчик", "Материалы"):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: смета #{estimate_id} не является сметой материалов"
                )

            sections = parse_sections(estimate.get("sections_json"))
            if (
                not isinstance(sections, list)
                or section_index >= len(sections)
                or not isinstance(sections[section_index], dict)
            ):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: строка сметы не найдена, обновите контроль материалов"
                )
            section = sections[section_index]
            section_name = _text(section.get("name"))
            section_items = section.get("items") or []
            if (
                not isinstance(section_items, list)
                or estimate_item_index >= len(section_items)
                or not isinstance(section_items[estimate_item_index], dict)
            ):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: строка сметы не найдена, обновите контроль материалов"
                )
            estimate_item = section_items[estimate_item_index]
            if _text(source.get("sectionName")) != section_name:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: раздел сметы изменился, обновите контроль материалов"
                )
            if item_type(estimate_item, section_name) != "material":
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: указанная строка больше не является материалом"
                )
            plan_issue = _text(item_plan_issue(estimate_item, section_name))
            if plan_issue:
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: строка сметы требует проверки: {plan_issue}"
                )

            estimate_material_name = _text(estimate_item.get("name"))
            estimate_material_unit = _text(estimate_item.get("unit"))
            source_material_name = _text(source.get("materialName"))
            source_unit = _text(source.get("unit"))
            if material_key(request_project, source_material_name, source_unit) != material_key(
                request_project, estimate_material_name, estimate_material_unit
            ):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: материал изменился в исходной строке сметы"
                )
            if item_key != material_key(request_project, estimate_material_name, estimate_material_unit):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: заявленный материал не совпадает с исходной строкой сметы"
                )
            if normalize_unit(source_unit) != normalize_unit(estimate_material_unit):
                raise MaterialControlLineageError(
                    f"Позиция {item_index}: единица материала изменилась в смете"
                )
            if item_quantity is not None:
                current_quantity = _float(item_quantity(estimate_item))
                source_quantity = _float(source.get("quantity"))
                tolerance = max(0.000001, abs(current_quantity) * 0.000001)
                if source_quantity <= 0 or abs(current_quantity - source_quantity) > tolerance:
                    raise MaterialControlLineageError(
                        f"Позиция {item_index}: объём исходной строки сметы изменился"
                    )

            source["validated"] = True
            validated_sources.append(source)

        lineage["sources"] = validated_sources
        lineage["validated"] = True
        lineage["sourceCount"] = len(validated_sources)
        item["estimateLineage"] = lineage
        validated_items.append(item)

    return validated_items
