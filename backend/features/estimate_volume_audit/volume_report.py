"""Read-only report for estimate rows that can distort procurement demand."""

import json
import os
import re
from collections import Counter, defaultdict

import psycopg2.extras


PREVIEW_LIMIT = 200
WORK_PREFIXES = (
    "монтаж", "установка", "устройство", "демонтаж", "разбор", "разборка",
    "прокладка", "замена", "подключение", "снятие", "ремонт",
)
MATERIAL_TYPES = {"material", "материал", "materials", "материалы"}
MATERIAL_HINTS = ("затир", "доск", "кабель", "провод", "труба", "дюб", "смесь", "краск", "кирпич", "блок", "ввг")
VOLUME_LIMITS = {
    "т": 1000,
    "м3": 10000,
    "мешок": 100000,
    "компл": 100000,
    "шт": 100000,
    "м": 1000000,
    "м2": 1000000,
    "кг": 1000000,
}


def number(value, default=0.0):
    try:
        return float(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return default


def unit_info(unit):
    text = str(unit or "").strip().lower().replace("²", "2").replace("³", "3")
    match = re.match(r"^(\d{2,})\s*(.+)$", text)
    factor = int(match.group(1)) if match else 1
    base = (match.group(2) if match else text).strip().replace(" ", "")
    aliases = {
        "м3": {"м3", "кубм"}, "м2": {"м2", "квм"}, "м": {"м", "мп", "пм"},
        "т": {"т", "тонна", "тонны", "тонн"}, "кг": {"кг"},
        "шт": {"шт", "штук", "штука", "штуки"}, "компл": {"компл", "комплект"},
        "мешок": {"мешок", "мешка", "мешков"},
    }
    normalized = next((key for key, values in aliases.items() if base in values), base)
    return factor, normalized


def parsed_sections(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def source_quantity(item):
    for key in ("rawQuantity", "quantityFinal", "quantityBase"):
        if item.get(key) not in (None, ""):
            return number(item[key]), key
    return number(item.get("quantity")), "quantity"


def is_work_name(name):
    text = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    return any(text == prefix or text.startswith(prefix + " ") for prefix in WORK_PREFIXES)


def is_material_candidate(item, name, raw_type):
    if raw_type in MATERIAL_TYPES:
        return True
    if is_work_name(name):
        return False
    code = str(item.get("sourceCode") or item.get("obosn") or item.get("code") or "").strip()
    resource_code = bool(re.match(r"^\d{2,}[-/]\d+|^\d{3,}$|^(ТЦ_|ФСБЦ|ФССЦ)", code, re.I))
    text = name.lower()
    return resource_code or any(hint in text for hint in MATERIAL_HINTS)


def inspect_estimate_rows(estimates):
    findings = []
    material_rows = []
    for estimate in estimates or []:
        for section_index, section in enumerate(parsed_sections(estimate.get("sections_json"))):
            if not isinstance(section, dict):
                continue
            for item_index, item in enumerate(section.get("items") or []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                raw_type = str(item.get("itemType") or item.get("type") or item.get("kind") or "").strip().lower()
                if not name or not is_material_candidate(item, name, raw_type):
                    continue
                raw_qty, source_field = source_quantity(item)
                factor, base_unit = unit_info(item.get("rawUnit") or item.get("unit"))
                normalized_qty = raw_qty * factor
                row = {
                    "estimateId": estimate.get("id"), "estimateName": estimate.get("name") or "",
                    "projectName": estimate.get("project_name") or "", "workPackage": estimate.get("work_package") or "Основная",
                    "sectionIndex": section_index, "sectionName": section.get("name") or section.get("title") or "",
                    "itemIndex": item_index, "name": name, "itemType": raw_type,
                    "sourceCode": item.get("sourceCode") or item.get("obosn") or item.get("code") or "",
                    "sourceQuantity": raw_qty, "sourceField": source_field,
                    "sourceUnit": item.get("rawUnit") or item.get("unit") or "", "unitFactor": factor,
                    "normalizedQuantity": normalized_qty, "normalizedUnit": base_unit,
                    "reasons": [],
                }
                material_rows.append(row)
                if is_work_name(name):
                    row["reasons"].append("work_name_marked_as_material")
                if factor > 1:
                    row["reasons"].append("scaled_unit")
                if normalized_qty > VOLUME_LIMITS.get(base_unit, float("inf")):
                    row["reasons"].append("suspicious_volume")
                if row["reasons"]:
                    findings.append(row)

    by_material = defaultdict(list)
    for row in material_rows:
        key = (row["projectName"], row["workPackage"], row["name"].lower(), row["normalizedUnit"])
        by_material[key].append(row)
    for same_material in by_material.values():
        estimate_ids = {row["estimateId"] for row in same_material}
        if len(estimate_ids) < 2:
            continue
        for row in same_material:
            if "multiple_active_estimates" not in row["reasons"]:
                row["reasons"].append("multiple_active_estimates")
                if row not in findings:
                    findings.append(row)
    return findings, material_rows


def material_totals(material_rows):
    grouped = defaultdict(list)
    for row in material_rows:
        key = (row["projectName"], row["workPackage"], row["name"].lower(), row["normalizedUnit"])
        grouped[key].append(row)
    totals = []
    for same_rows in grouped.values():
        first = same_rows[0]
        total = sum(row["normalizedQuantity"] for row in same_rows)
        totals.append({
            "projectName": first["projectName"], "workPackage": first["workPackage"],
            "name": first["name"], "unit": first["normalizedUnit"],
            "totalQuantity": total, "sourceRowCount": len(same_rows), "sourceRows": same_rows[:30],
        })
    return totals


def build_report(rows, search_terms=()):
    findings, material_rows = inspect_estimate_rows(rows)
    totals = material_totals(material_rows)
    for total in totals:
        limit = VOLUME_LIMITS.get(total["unit"], float("inf"))
        if total["totalQuantity"] > limit:
            findings.append({
                "estimateId": None, "estimateName": "", "projectName": total["projectName"],
                "workPackage": total["workPackage"], "sectionIndex": None, "sectionName": "",
                "itemIndex": None, "name": total["name"], "itemType": "aggregate",
                "sourceCode": "", "sourceQuantity": total["totalQuantity"], "sourceField": "sum",
                "sourceUnit": total["unit"], "unitFactor": 1,
                "normalizedQuantity": total["totalQuantity"], "normalizedUnit": total["unit"],
                "reasons": ["aggregate_suspicious_volume"], "sourceRows": total["sourceRows"],
            })
    reason_counts = Counter(reason for row in findings for reason in row["reasons"])
    search_terms = tuple(term.strip().lower() for term in search_terms if term.strip())
    matches = [total for total in totals if not search_terms or any(term in total["name"].lower() for term in search_terms)]
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "summary": {"activeEstimates": len(rows or []), "needsReview": len(findings)},
        "byReason": dict(sorted(reason_counts.items())),
        "needsReview": findings[:PREVIEW_LIMIT],
        "reviewListTruncated": len(findings) > PREVIEW_LIMIT,
        "matches": matches if search_terms else [],
    }


def run_report(get_db, search_terms=()):
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("""SELECT id,name,project_name,COALESCE(NULLIF(work_package,''),'Основная') AS work_package,sections_json
                           FROM estimates
                          WHERE COALESCE(status,'Активная')='Активная'
                            AND COALESCE(smeta_type,'Заказчик') IN ('Заказчик','Материалы')
                          ORDER BY project_name,id""")
            return build_report([dict(row) for row in cur.fetchall()], search_terms=search_terms)
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    terms = os.getenv("ESTIMATE_VOLUME_AUDIT_FIND", "").split(",")
    report = run_report(get_db, search_terms=terms)
    if os.getenv("ESTIMATE_VOLUME_AUDIT_ONLY_MATCHES", "").lower() in {"1", "true", "yes"}:
        report = {"ok": report["ok"], "dryRun": True, "writesAttempted": 0, "matches": report["matches"]}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
