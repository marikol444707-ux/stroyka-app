#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_SUPPLIER_PREFIX = "CODEX QA Поставщик снабжение"
TEST_NOTE_PREFIX = "CODEX QA supply chain smoke"
TEST_QTY_DEFAULT = float(os.getenv("SUPPLY_SMOKE_QTY", "0.001"))
TEST_PRICE = float(os.getenv("SUPPLY_SMOKE_PRICE", "123.45"))


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name, default=""):
    return os.getenv(name) or ENV.get(name, default)


def db_config():
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def db_conn():
    return psycopg2.connect(**db_config())


def api_json(method, path, token=None, data=None, expected=None):
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def require_env(name):
    value = env_value(name, "")
    if not value:
        raise SystemExit(f"Нужно задать {name} в окружении или backend/.env")
    return value


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


def norm_text(value):
    text = str(value or "").lower()
    text = re.sub(r"[.,;:()«»\"'`/\\]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def as_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            text = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
            return float(text)
        return float(value)
    except Exception:
        return default


def base_unit(value):
    text = norm_text(str(value or "").replace("²", "2").replace("³", "3"))
    text = re.sub(r"^\d{2,}\s*", "", text).strip()
    compact = text.replace(" ", "")
    aliases = {
        "м": {"м", "мп", "пм", "погм", "метр", "метра", "метров"},
        "м2": {"м2", "квм", "квадратныйметр", "квадратногометра", "квадратныхметров"},
        "м3": {"м3", "кубм", "кубическийметр", "кубическогометра", "кубическихметров"},
        "шт": {"шт", "штук", "штука", "штуки"},
        "компл": {"компл", "комплект", "комплекта", "комплектов"},
        "кг": {"кг", "килограмм", "килограмма", "килограммов"},
        "л": {"л", "литр", "литра", "литров"},
        "т": {"т", "тонна", "тонны", "тонн"},
        "мешок": {"мешок", "мешка", "мешков"},
    }
    for canonical, variants in aliases.items():
        if compact in variants:
            return canonical
    return text or "шт"


def looks_material(item, section_name):
    raw = str(item.get("itemType") or item.get("type") or item.get("kind") or "").lower()
    text = norm_text((item.get("name") or "") + " " + section_name)
    source_code = str(item.get("sourceCode") or item.get("obosn") or item.get("code") or "").strip()
    material_markers = (
        "смесь", "штукатурка", "штукатурк", "шпатлевка", "шпатлевк", "шпаклевка",
        "шпаклевк", "клей", "краска", "акрил", "грунтовка", "грунтовк", "кабель",
        "провод", "гофра", "лист гкл", "профиль", "саморез", "кирпич", "бетон",
        "плитка", "плитк", "керамическ", "керамогранит", "гранит", "пвх", "уголок",
        "панель", "плинтус", "наличник",
    )
    strong_work_markers = (
        "монтаж", "установка", "устройство", "демонтаж", "разбор", "разборка",
        "прокладка", "замена", "подключение", "снятие", "очистка", "ремонт",
        "облицовка", "окраска", "кладка", "стяжка", "отбивка", "отбивк", "грунтование",
    )
    source_looks_work = bool(re.match(r"^(ГЭСН|ФЕР|ТЕР)", source_code, re.I))
    source_looks_resource = bool(
        re.match(r"^\d{2,}[-/]\d+", source_code)
        or re.match(r"^\d{3,}$", source_code)
        or re.match(r"^(ТЦ_|ФСБЦ|ФССЦ)", source_code, re.I)
    )
    if raw in ("material", "материал", "materials", "материалы") or "материал" in raw:
        return True
    if raw in ("work", "работа", "works", "работы") and item.get("isImported") and source_looks_work:
        return False
    if raw in ("work", "работа", "works", "работы") and item.get("isImported"):
        return (source_looks_resource or any(m in text for m in material_markers)) and not any(w in text for w in strong_work_markers)
    if raw in ("work", "работа", "works", "работы"):
        return False
    return any(m in text for m in material_markers) and not any(w in text for w in strong_work_markers)


def estimate_sections(raw):
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def is_synthetic_material_name(name):
    text = norm_text(name)
    return (
        text.startswith("материалы по позиции")
        or text.startswith("комплектация укрупненной работы")
        or text.startswith("комплектация укрупнённой работы")
    )


def iter_candidate_materials():
    preferred_project = os.getenv("SUPPLY_SMOKE_PROJECT", "").strip()
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if preferred_project:
        cur.execute("SELECT id, name FROM projects WHERE name=%s AND COALESCE(archived,FALSE)=FALSE LIMIT 1", (preferred_project,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        cur.close()
        conn.close()
        raise SystemExit("FAIL: нет активного объекта для smoke снабжения")
    cur.execute(
        """
        SELECT id, name, project_name, COALESCE(NULLIF(work_package,''),'Основная') AS work_package, sections_json
          FROM estimates
         WHERE project_name=%s
           AND COALESCE(status,'Активная')='Активная'
           AND COALESCE(smeta_type,'Заказчик') IN ('Заказчик','Материалы')
         ORDER BY id
        """,
        (project["name"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    seen = set()
    primary_candidates = []
    fallback_candidates = []
    for row in rows:
        package = (row.get("work_package") or "Основная").strip() or "Основная"
        if package.startswith("CODEX QA"):
            continue
        for section in estimate_sections(row.get("sections_json")):
            if not isinstance(section, dict):
                continue
            section_name = section.get("name") or section.get("title") or row.get("name") or ""
            for item in section.get("items") or []:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or "").strip()
                qty = as_float(item.get("quantity"))
                unit = base_unit(item.get("unit") or item.get("measure") or "")
                if not name or qty < TEST_QTY_DEFAULT or not looks_material(item, section_name):
                    continue
                key = (norm_text(name), unit, package)
                if key in seen:
                    continue
                seen.add(key)
                smoke_qty = min(TEST_QTY_DEFAULT, qty)
                candidate = {
                    "projectName": project["name"],
                    "projectId": project["id"],
                    "estimateId": row["id"],
                    "estimateName": row["name"],
                    "workPackage": package,
                    "materialName": name,
                    "unit": unit,
                    "plannedQuantity": qty,
                    "quantity": round(smoke_qty, 6),
                }
                if is_synthetic_material_name(name):
                    fallback_candidates.append(candidate)
                else:
                    primary_candidates.append(candidate)
    yield from primary_candidates
    yield from fallback_candidates


def create_supplier(token, stamp):
    _, body = api_json(
        "POST",
        "/suppliers",
        token=token,
        data={
            "name": f"{TEST_SUPPLIER_PREFIX} {stamp}",
            "phone": "+70000000000",
            "email": f"supply-smoke-{stamp}@stroyka.local",
            "specialization": "CODEX QA",
            "category": "Материалы",
            "rating": 5,
            "status": "Активный",
        },
        expected=200,
    )
    supplier_id = body.get("id")
    if not supplier_id:
        raise RuntimeError("POST /suppliers не вернул id")
    return supplier_id


def create_supply_request_for_candidate(token, supplier_id, candidate, stamp):
    item = {
        "materialName": candidate["materialName"],
        "quantity": candidate["quantity"],
        "unit": candidate["unit"],
        "workPackage": candidate["workPackage"],
    }
    data = {
        "project": candidate["projectName"],
        "workPackage": candidate["workPackage"],
        "createdBy": "CODEX QA",
        "date": dt.date.today().isoformat(),
        "notes": f"{TEST_NOTE_PREFIX} {stamp}",
        "selectedSuppliers": [supplier_id],
        "urgency": "обычная",
        "category": "Материалы",
        "items": [item],
    }
    status, body = api_json("POST", "/supply-requests", token=token, data=data)
    if status != 200:
        return None, f"{status}: {json.dumps(body, ensure_ascii=False)[:500]}"
    request_id = body.get("id")
    if not request_id:
        return None, "ответ заявки без id"
    return body, None


def select_working_candidate(token, supplier_id, stamp):
    errors = []
    for candidate in iter_candidate_materials():
        request, error = create_supply_request_for_candidate(token, supplier_id, candidate, stamp)
        if request:
            candidate["requestId"] = request["id"]
            candidate["request"] = request
            return candidate
        errors.append(f"{candidate['materialName'][:80]} / {candidate['workPackage']}: {error}")
    raise RuntimeError("Не удалось создать заявку по положительному материалу сметы. Последние ошибки: " + " | ".join(errors[-5:]))


def create_and_select_offer(token, candidate, supplier_id):
    qty = candidate["quantity"]
    total = round(TEST_PRICE * qty, 2)
    _, offer = api_json(
        "POST",
        "/supplier-offers",
        token=token,
        data={
            "requestId": candidate["requestId"],
            "supplierId": supplier_id,
            "pricePerUnit": TEST_PRICE,
            "totalPrice": total,
            "deliveryDays": 1,
            "notes": TEST_NOTE_PREFIX,
        },
        expected=200,
    )
    offer_id = offer.get("id")
    if not offer_id:
        raise RuntimeError("POST /supplier-offers не вернул id")
    items_kp = [{
        "materialName": candidate["materialName"],
        "quantity": qty,
        "unit": candidate["unit"],
        "workPackage": candidate["workPackage"],
        "pricePerUnit": TEST_PRICE,
        "totalPrice": total,
        "deliveryDays": 1,
        "notes": TEST_NOTE_PREFIX,
    }]
    api_json(
        "PUT",
        f"/supplier-offers/{offer_id}",
        token=token,
        data={
            "action": "respond",
            "pricePerUnit": TEST_PRICE,
            "totalPrice": total,
            "deliveryDays": 1,
            "paymentTerms": "Постоплата",
            "vatIncluded": True,
            "supplierMessage": TEST_NOTE_PREFIX,
            "itemsKp": items_kp,
        },
        expected=200,
    )
    api_json("PUT", f"/supplier-offers/{offer_id}", token=token, data={"action": "select"}, expected=200)
    return offer_id


def ship_and_receive(token, candidate, offer_id, stamp):
    qty = candidate["quantity"]
    _, shipped = api_json(
        "POST",
        f"/supplier-offers/{offer_id}/ship",
        token=token,
        data={
            "waybillNumber": f"CODEX-SUPPLY-{stamp}",
            "waybillDate": dt.date.today().isoformat(),
            "vehicleNumber": "CODEX",
            "driverName": "CODEX QA",
            "shippedItems": [{
                "materialName": candidate["materialName"],
                "quantity": qty,
                "shippedQuantity": qty,
                "unit": candidate["unit"],
                "workPackage": candidate["workPackage"],
            }],
        },
        expected=200,
    )
    if isinstance(shipped, dict) and shipped.get("deliveries"):
        delivery_id = shipped["deliveries"][0].get("id")
    else:
        delivery_id = shipped.get("id")
    if not delivery_id:
        raise RuntimeError("Отгрузка не вернула id поставки")
    _, received = api_json(
        "PUT",
        f"/supply-deliveries/{delivery_id}/receive",
        token=token,
        data={
            "receivedQuantity": qty,
            "receivedBy": "CODEX QA",
            "qualityStatus": "Принято",
            "qualityNotes": TEST_NOTE_PREFIX,
        },
        expected=200,
    )
    invoice_id = received.get("invoiceId")
    if not invoice_id:
        raise RuntimeError("Приемка не создала автоматическую накладную")
    return delivery_id, invoice_id


def assert_visible_chain(token, candidate, delivery_id, invoice_id):
    _, invoices = api_json("GET", "/warehouse-invoices", token=token, expected=200)
    invoice = next((r for r in invoices if int(r.get("id") or 0) == int(invoice_id)), None)
    if not invoice:
        raise RuntimeError("Автоматическая накладная не видна в /warehouse-invoices")
    invoice_items = invoice.get("items") or []
    if not any(norm_text(i.get("name")) == norm_text(candidate["materialName"]) for i in invoice_items if isinstance(i, dict)):
        raise RuntimeError("В автоматической накладной нет принятого материала")

    _, materials = api_json("GET", "/materials", token=token, expected=200)
    material = next(
        (
            r for r in materials
            if norm_text(r.get("name")) == norm_text(candidate["materialName"])
            and (r.get("project") or "") == candidate["projectName"]
        ),
        None,
    )
    if not material:
        raise RuntimeError("Материал после приемки не появился в материалах объекта")

    _, history = api_json("GET", "/supply-history", token=token, expected=200)
    matched_history = next(
        (
            r for r in history
            if norm_text(r.get("materialName")) == norm_text(candidate["materialName"])
            and (r.get("project") or "") == candidate["projectName"]
            and (r.get("workPackage") or "") == candidate["workPackage"]
        ),
        None,
    )
    if not matched_history:
        raise RuntimeError("История снабжения не содержит принятую поставку")

    manual_material_name = f"CODEX QA прямой заказ директора {delivery_id}"
    _, manual_invoice = api_json(
        "POST",
        "/warehouse-invoices",
        token=token,
        data={
            "number": f"CODEX-MANUAL-{delivery_id}",
            "date": dt.date.today().isoformat(),
            "supplierName": "CODEX QA",
            "acceptedBy": "CODEX QA",
            "location": candidate["projectName"],
            "project": candidate["projectName"],
            "items": [{
                "name": manual_material_name,
                "quantity": candidate["quantity"],
                "unit": candidate["unit"],
                "price": TEST_PRICE,
                "workPackage": candidate["workPackage"],
            }],
            "totalBase": round(TEST_PRICE * candidate["quantity"], 2),
            "totalVat": 0,
            "totalWithVat": round(TEST_PRICE * candidate["quantity"], 2),
        },
        expected=200,
    )
    manual_invoice_id = manual_invoice.get("id")
    if not manual_invoice_id:
        raise RuntimeError("Ручная приходная накладная на объект не вернула id")

    _, invoices_after_manual = api_json("GET", "/warehouse-invoices", token=token, expected=200)
    saved_manual_invoice = next((r for r in invoices_after_manual if int(r.get("id") or 0) == int(manual_invoice_id)), None)
    if not saved_manual_invoice:
        raise RuntimeError("Ручная приходная накладная на объект не видна в /warehouse-invoices")
    if saved_manual_invoice.get("sourceType") != "manual_project_invoice":
        raise RuntimeError("Ручная приходная накладная на объект сохранена без sourceType=manual_project_invoice")
    saved_items = saved_manual_invoice.get("items") or []
    saved_manual_item = next((i for i in saved_items if isinstance(i, dict) and norm_text(i.get("name")) == norm_text(manual_material_name)), None)
    if not saved_manual_item:
        raise RuntimeError("Ручная приходная накладная не сохранила прямой материал директора")
    estimate_control = saved_manual_item.get("estimateControl") or {}
    if not estimate_control.get("manualProjectInvoiceOverride"):
        raise RuntimeError("Ручная приходная накладная на объект не получила контрольную пометку manualProjectInvoiceOverride")
    _, materials_after_manual = api_json("GET", "/materials", token=token, expected=200)
    if not any(
        norm_text(r.get("name")) == norm_text(manual_material_name)
        and (r.get("project") or "") == candidate["projectName"]
        for r in materials_after_manual
    ):
        raise RuntimeError("Прямой материал директора не попал на склад объекта")
    return manual_invoice_id, manual_material_name


def cleanup(created):
    conn = None
    try:
        conn = db_conn()
        conn.autocommit = False
        cur = conn.cursor()
        material_names = [created.get("materialName"), created.get("manualMaterialName")]
        project_name = created.get("projectName")
        package = created.get("workPackage")
        unit = created.get("unit")
        qty_by_name = {
            created.get("materialName"): as_float(created.get("quantity")),
            created.get("manualMaterialName"): as_float(created.get("manualQuantity")),
        }

        for material_name in [n for n in material_names if n]:
            qty = qty_by_name.get(material_name, 0)
            if material_name and project_name and qty > 0:
                remaining = qty
                cur.execute(
                    """
                    SELECT id, COALESCE(quantity,0) AS quantity
                      FROM materials
                     WHERE LOWER(name)=LOWER(%s)
                       AND project=%s
                       AND COALESCE(work_package,'')=%s
                       AND LOWER(COALESCE(unit,''))=LOWER(%s)
                     ORDER BY id DESC
                    """,
                    (material_name, project_name, package or "", unit or ""),
                )
                for row_id, row_qty in cur.fetchall():
                    if remaining <= 0:
                        break
                    row_qty = as_float(row_qty)
                    take = min(row_qty, remaining)
                    new_qty = row_qty - take
                    if new_qty <= 0.0000001:
                        cur.execute("DELETE FROM materials WHERE id=%s", (row_id,))
                    else:
                        cur.execute("UPDATE materials SET quantity=%s WHERE id=%s", (new_qty, row_id))
                    remaining -= take

        ids = {
            "invoiceId": created.get("invoiceId"),
            "manualInvoiceId": created.get("manualInvoiceId"),
            "deliveryId": created.get("deliveryId"),
            "offerId": created.get("offerId"),
            "requestId": created.get("requestId"),
            "supplierId": created.get("supplierId"),
        }
        if ids["invoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["invoiceId"],))
        if ids["manualInvoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["manualInvoiceId"],))
        if ids["deliveryId"]:
            cur.execute("DELETE FROM material_inspection_journal WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM cable_journal WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_claims WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_history WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_deliveries WHERE id=%s", (ids["deliveryId"],))
        if ids["requestId"]:
            cur.execute("DELETE FROM supply_history WHERE request_id=%s", (ids["requestId"],))
        if ids["offerId"]:
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id=%s", (ids["offerId"],))
            cur.execute("DELETE FROM supplier_offers WHERE id=%s", (ids["offerId"],))
        if ids["requestId"]:
            cur.execute("DELETE FROM supply_requests WHERE id=%s", (ids["requestId"],))
        for material_name in [n for n in material_names if n]:
            if material_name and project_name:
                cur.execute(
                    """
                    DELETE FROM warehouse_history
                     WHERE material=%s
                       AND project=%s
                       AND COALESCE(work_package,'')=%s
                       AND issued_by='Снабжение'
                       AND type='приход (поставка)'
                    """,
                    (material_name, project_name, package or ""),
                )
                cur.execute(
                    """
                    DELETE FROM warehouse_history
                     WHERE material=%s
                       AND project=%s
                       AND COALESCE(work_package,'')=%s
                       AND issued_by='CODEX QA'
                       AND type='приход'
                    """,
                    (material_name, project_name, package or ""),
                )
        if ids["supplierId"]:
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["supplierId"], TEST_SUPPLIER_PREFIX + "%"))
        conn.commit()
        cur.close()
        print("cleanup: removed supply-chain smoke rows", json.dumps(created, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def main():
    admin_email = require_env("SMOKE_EMAIL")
    admin_password = require_env("SMOKE_PASSWORD")
    token = login(admin_email, admin_password)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    created = {}
    try:
        supplier_id = create_supplier(token, stamp)
        created["supplierId"] = supplier_id
        candidate = select_working_candidate(token, supplier_id, stamp)
        created.update({
            "projectName": candidate["projectName"],
            "workPackage": candidate["workPackage"],
            "materialName": candidate["materialName"],
            "unit": candidate["unit"],
            "quantity": candidate["quantity"],
            "requestId": candidate["requestId"],
        })
        offer_id = create_and_select_offer(token, candidate, supplier_id)
        created["offerId"] = offer_id
        delivery_id, invoice_id = ship_and_receive(token, candidate, offer_id, stamp)
        created["deliveryId"] = delivery_id
        created["invoiceId"] = invoice_id
        manual_invoice_id, manual_material_name = assert_visible_chain(token, candidate, delivery_id, invoice_id)
        created["manualInvoiceId"] = manual_invoice_id
        created["manualMaterialName"] = manual_material_name
        created["manualQuantity"] = candidate["quantity"]
        print(json.dumps({
            "ok": True,
            "projectName": candidate["projectName"],
            "workPackage": candidate["workPackage"],
            "material": candidate["materialName"],
            "quantity": candidate["quantity"],
            "unit": candidate["unit"],
            "requestId": candidate["requestId"],
            "offerId": offer_id,
            "deliveryId": delivery_id,
            "invoiceId": invoice_id,
            "manualInvoiceId": manual_invoice_id,
            "manualMaterial": manual_material_name,
            "checked": [
                "positive estimate material selected",
                "supply request passed estimate control",
                "supplier offer responded and selected",
                "shipment created",
                "receipt created automatic invoice",
                "receipt updated project materials",
                "receipt wrote supply history",
                "manual director object invoice is allowed, controlled and written to object warehouse",
            ],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:supply-chain: {exc}")
    finally:
        cleanup(created)


if __name__ == "__main__":
    main()
