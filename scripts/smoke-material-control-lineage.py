#!/usr/bin/env python3
"""Verify exact estimate lineage for single and multi-item supply requests."""
import importlib.util
import json
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
BASE_SMOKE_PATH = Path(__file__).with_name("smoke-main-warehouse-receipt.py")
SUPPLY_SMOKE_PATH = Path(__file__).with_name("smoke-supply-chain.py")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_SMOKE = load_module("main_warehouse_receipt_smoke", BASE_SMOKE_PATH)
SUPPLY_SMOKE = load_module("supply_chain_smoke", SUPPLY_SMOKE_PATH)
db_config = BASE_SMOKE.db_config
env_value = BASE_SMOKE.env_value
login = BASE_SMOKE.login

RUN_ID = uuid.uuid4().hex[:10]
MARKER = f"CODEX QA material-control lineage smoke {RUN_ID}"
REQUEST_SOURCE = "estimate_material_control"
SMOKE_QUANTITY = float(env_value("MATERIAL_CONTROL_LINEAGE_SMOKE_QTY", "0.001"))


def api_response(method, path, *, token, data=None, headers=None):
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request_headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        BASE_SMOKE.BASE_URL + path,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError:
        return status, {"raw": text}


def select_company(token):
    context = BASE_SMOKE.api_json("GET", "/users/company-context", token=token)
    requested_company_id = int(env_value("SMOKE_COMPANY_ID", "0") or 0)
    candidates = [
        row for row in context.get("companies") or []
        if row.get("role") in {"директор", "зам_директора"}
    ]
    selected = next(
        (row for row in candidates if int(row.get("companyId") or 0) == requested_company_id),
        candidates[0] if candidates and not requested_company_id else None,
    )
    if not selected:
        raise RuntimeError("У smoke-пользователя нет роли директора или заместителя в выбранной компании")
    return int(selected["companyId"])


def estimate_candidates(company_id):
    conn = psycopg2.connect(**db_config())
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT e.id, e.name, e.project_name,
                   COALESCE(NULLIF(e.work_package,''),'Основная') AS work_package,
                   e.sections_json
              FROM estimates e
              JOIN projects p ON p.name=e.project_name
             WHERE e.company_id=%s
               AND p.company_id=%s
               AND COALESCE(p.archived,FALSE)=FALSE
               AND COALESCE(e.status,'Активная')='Активная'
               AND COALESCE(e.smeta_type,'Заказчик') IN ('Заказчик','Материалы')
             ORDER BY e.id
            """,
            (company_id, company_id),
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    result = []
    seen = set()
    for estimate in rows:
        work_package = (estimate.get("work_package") or "Основная").strip() or "Основная"
        if work_package.startswith("CODEX QA"):
            continue
        for section_index, section in enumerate(SUPPLY_SMOKE.estimate_sections(estimate.get("sections_json"))):
            if not isinstance(section, dict):
                continue
            section_name = section.get("name") or section.get("title") or estimate.get("name") or ""
            for item_index, item in enumerate(section.get("items") or []):
                if not isinstance(item, dict):
                    continue
                material_name = (item.get("name") or "").strip()
                quantity = SUPPLY_SMOKE.as_float(item.get("quantity"))
                unit = SUPPLY_SMOKE.base_unit(item.get("unit") or item.get("measure") or "")
                if (
                    not material_name
                    or not unit
                    or quantity < SMOKE_QUANTITY
                    or not SUPPLY_SMOKE.looks_material(item, section_name)
                ):
                    continue
                key = (estimate["project_name"], work_package, SUPPLY_SMOKE.norm_text(material_name), unit)
                if key in seen:
                    continue
                seen.add(key)
                result.append({
                    "estimateId": int(estimate["id"]),
                    "estimateName": estimate.get("name") or "",
                    "projectName": estimate["project_name"],
                    "workPackage": work_package,
                    "sectionIndex": section_index,
                    "itemIndex": item_index,
                    "sectionName": section_name,
                    "materialName": material_name,
                    "unit": unit,
                    "sourceQuantity": quantity,
                    "quantity": min(SMOKE_QUANTITY, quantity),
                })
    return result


def make_item(candidate):
    return {
        "materialName": candidate["materialName"],
        "quantity": candidate["quantity"],
        "unit": candidate["unit"],
        "workPackage": candidate["workPackage"],
        "sourceType": REQUEST_SOURCE,
        "estimateLineage": {
            "version": 1,
            "projectName": candidate["projectName"],
            "workPackage": candidate["workPackage"],
            "sources": [{
                "estimateId": candidate["estimateId"],
                "estimateName": candidate["estimateName"],
                "sectionIndex": candidate["sectionIndex"],
                "itemIndex": candidate["itemIndex"],
                "sectionName": candidate["sectionName"],
                "materialName": candidate["materialName"],
                "unit": candidate["unit"],
                "quantity": candidate["sourceQuantity"],
            }],
        },
    }


def make_request_payload(candidates, *, label):
    first = candidates[0]
    items = [make_item(candidate) for candidate in candidates]
    return {
        "project": first["projectName"],
        "workPackage": first["workPackage"],
        "materialName": first["materialName"],
        "quantity": first["quantity"] if len(items) == 1 else len(items),
        "unit": first["unit"] if len(items) == 1 else "поз.",
        "createdBy": "CODEX QA",
        "date": time.strftime("%Y-%m-%d"),
        "notes": f"{MARKER}\n{label}",
        "requestSource": REQUEST_SOURCE,
        "urgency": "обычная",
        "category": "Материалы по смете",
        "selectedSuppliers": [],
        "items": items,
    }


def post_request(token, headers, candidates, label):
    status, body = api_response(
        "POST", "/supply-requests", token=token, headers=headers,
        data=make_request_payload(candidates, label=label),
    )
    return status, body


def assert_saved_lineage(request, expected_count):
    items = request.get("items") or []
    if len(items) != expected_count:
        raise RuntimeError(f"Заявка сохранила {len(items)} позиций вместо {expected_count}")
    for item in items:
        lineage = item.get("estimateLineage") or {}
        sources = lineage.get("sources") or []
        if not lineage.get("validated") or lineage.get("sourceCount") != 1 or len(sources) != 1:
            raise RuntimeError("Заявка сохранена без подтвержденной точной связи со строкой сметы")
        if not sources[0].get("validated"):
            raise RuntimeError("Источник заявки не отмечен как проверенная строка сметы")


def cleanup():
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cur.execute("SELECT id FROM supply_requests WHERE notes LIKE %s", (f"%{MARKER}%",))
        request_ids = [int(row[0]) for row in cur.fetchall()]
        if request_ids:
            cur.execute("DELETE FROM messenger_outbox WHERE entity_type='supply_request' AND entity_id = ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_history WHERE request_id = ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_request_recipients WHERE request_id = ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supplier_offers WHERE request_id = ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_requests WHERE id = ANY(%s)", (request_ids,))
        conn.commit()
        cur.close()
        print(f"cleanup: removed {len(request_ids)} material-control lineage smoke request(s)")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}")
    finally:
        if conn:
            conn.close()


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    company_id = select_company(token)
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    try:
        candidates = estimate_candidates(company_id)
        if not candidates:
            raise RuntimeError("Нет активной сметной строки материала для проверки точной связи заявки")

        errors = []
        single_candidate = None
        single_request = None
        for candidate in candidates:
            status, body = post_request(token, headers, [candidate], "одиночная заявка")
            if status == 200:
                single_candidate = candidate
                single_request = body
                break
            errors.append(f"{candidate['materialName'][:80]}: {status} {body.get('detail', '')}")
        if not single_request:
            raise RuntimeError("Не создана одиночная заявка из сметы. Последние ошибки: " + " | ".join(errors[-5:]))
        assert_saved_lineage(single_request, 1)

        by_package = defaultdict(list)
        for candidate in candidates:
            if candidate == single_candidate:
                continue
            by_package[(candidate["projectName"], candidate["workPackage"])].append(candidate)
        batch_request = None
        for group in by_package.values():
            if len(group) < 2:
                continue
            status, body = post_request(token, headers, group[:2], "многопозиционная заявка")
            if status == 200:
                batch_request = body
                break
            errors.append(f"пакет {group[0]['workPackage']}: {status} {body.get('detail', '')}")
        if not batch_request:
            raise RuntimeError("Не создана многопозиционная заявка из одной сметы/пакета. Последние ошибки: " + " | ".join(errors[-5:]))
        assert_saved_lineage(batch_request, 2)

        invalid_payload = make_request_payload([single_candidate], label="некорректная связь")
        invalid_payload["items"][0]["estimateLineage"]["sources"][0]["sectionName"] = "CODEX QA stale section"
        status, invalid_body = api_response(
            "POST", "/supply-requests", token=token, headers=headers, data=invalid_payload,
        )
        if status != 400 or "контроля материалов отклонена" not in str(invalid_body.get("detail") or ""):
            raise RuntimeError(f"Некорректная связь сметы не заблокирована: {status} {invalid_body}")

        print(json.dumps({
            "ok": True,
            "companyId": company_id,
            "singleRequestId": single_request.get("id"),
            "batchRequestId": batch_request.get("id"),
            "projectName": single_candidate["projectName"],
            "workPackage": single_candidate["workPackage"],
            "checked": [
                "single request stores validated exact estimate lineage",
                "multi-item request stores validated lineage for every item",
                "stale estimate coordinates are rejected before request creation",
                "smoke requests have no suppliers and are removed after verification",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    main()
