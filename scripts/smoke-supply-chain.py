#!/usr/bin/env python3
import datetime as dt
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
TEST_FOREMAN_EMAIL = os.getenv("SUPPLY_SMOKE_FOREMAN_EMAIL", "supply-foreman-smoke@stroyka.local")
TEST_FOREMAN_NAME = "CODEX QA Прораб накладная"
TEST_FOREMAN_PASSWORD = os.getenv("SUPPLY_SMOKE_FOREMAN_PASSWORD", "SupplyForemanSmoke123!")
TEST_SUPPLIER_PASSWORD = os.getenv("SUPPLY_SMOKE_SUPPLIER_PASSWORD", "SupplySupplierSmoke123!")


def test_supplier_name(stamp):
    return f"{TEST_SUPPLIER_PREFIX} {stamp}"


def test_supplier_email(stamp):
    return f"supply-smoke-{stamp}@stroyka.local"


def test_supplier_phone(stamp):
    digits = re.sub(r"\D", "", str(stamp or ""))[-10:].rjust(10, "0")
    return "+7" + digits


def test_unlinked_supplier_name(stamp):
    return f"{TEST_SUPPLIER_PREFIX} без кабинета {stamp}"


def test_unlinked_supplier_email(stamp):
    return f"supply-unlinked-{stamp}@stroyka.local"


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


def api_json(method, path, token=None, data=None, expected=None, headers=None):
    body = None
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
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
    if token:
        return token
    if body.get("twoFactorSetupRequired"):
        raise SystemExit(f"FAIL login {email}: требуется первичная настройка 2FA. Для smoke используйте аккаунт с уже настроенной 2FA или отдельный smoke-аккаунт.")
    if body.get("twoFactorRequired") and body.get("challengeToken"):
        code = os.getenv("SMOKE_2FA_CODE", "").strip()
        if not code and env_value("SMOKE_TOTP_SECRET", "").strip():
            code = totp_code_from_secret(env_value("SMOKE_TOTP_SECRET", "").strip())
        if not code:
            raise SystemExit(f"FAIL login {email}: требуется 2FA. Передайте SMOKE_2FA_CODE или SMOKE_TOTP_SECRET.")
        _, verified = api_json(
            "POST",
            "/login/2fa/verify",
            data={"challengeToken": body.get("challengeToken"), "code": code},
            expected=200,
        )
        token = verified.get("authToken")
        if token:
            return token
        raise SystemExit(f"FAIL login {email}: 2FA не вернула authToken")
    raise SystemExit(f"FAIL login {email}: authToken не получен")
    return token


def totp_code_from_secret(secret):
    clean = re.sub(r"\s+", "", secret or "").upper()
    if not clean:
        return ""
    clean += "=" * (-len(clean) % 8)
    key = base64.b32decode(clean, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


def ensure_foreman_user(project_name):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "manage-temp-user.py"),
            "create",
            "--email",
            TEST_FOREMAN_EMAIL,
            "--name",
            TEST_FOREMAN_NAME,
            "--password",
            TEST_FOREMAN_PASSWORD,
            "--role",
            "прораб",
            "--project",
            project_name,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return login(TEST_FOREMAN_EMAIL, TEST_FOREMAN_PASSWORD)


def ensure_supplier_user(email, name):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "manage-temp-user.py"),
            "create",
            "--email",
            email,
            "--name",
            name,
            "--password",
            TEST_SUPPLIER_PASSWORD,
            "--role",
            "поставщик",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return login(email, TEST_SUPPLIER_PASSWORD)


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
    supplier_name = test_supplier_name(stamp)
    supplier_email = test_supplier_email(stamp)
    _, body = api_json(
        "POST",
        "/suppliers",
        token=token,
        data={
            "name": supplier_name,
            "phone": test_supplier_phone(stamp),
            "email": supplier_email,
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
    if (body.get("name") or "").strip() != supplier_name or (body.get("email") or "").strip().lower() != supplier_email.lower():
        raise RuntimeError(
            "POST /suppliers вернул не тестовую карточку поставщика: "
            + json.dumps(
                {
                    "id": supplier_id,
                    "name": body.get("name"),
                    "email": body.get("email"),
                    "expectedName": supplier_name,
                    "expectedEmail": supplier_email,
                },
                ensure_ascii=False,
            )
        )
    return supplier_id


def create_unlinked_supplier_record(stamp):
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO suppliers
                (name, phone, email, specialization, category, rating, status, source_type, source_detail)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                test_unlinked_supplier_name(stamp),
                "",
                test_unlinked_supplier_email(stamp),
                "CODEX QA",
                "Материалы",
                5,
                "Активный",
                "smoke_unlinked_supplier",
                TEST_NOTE_PREFIX,
            ),
        )
        supplier_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return supplier_id
    finally:
        conn.close()


def create_legacy_supplier_offer_record(request_id, supplier_id):
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(company_id,1) FROM supply_requests WHERE id=%s", (request_id,))
        row = cur.fetchone()
        company_id = row[0] if row else 1
        cur.execute(
            """
            INSERT INTO supplier_offers
                (request_id, supplier_id, company_id, status, notes, requested_at)
            VALUES (%s,%s,%s,%s,%s,NOW())
            RETURNING id
            """,
            (request_id, supplier_id, company_id, "Ожидает ответа", TEST_NOTE_PREFIX),
        )
        offer_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return offer_id
    finally:
        conn.close()


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
        "selectedSuppliers": [supplier_id] if supplier_id else [],
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


def create_and_select_offer(token, candidate, supplier_id, supplier_token=None):
    qty = candidate["quantity"]
    total = round(TEST_PRICE * qty, 2)
    _, offers = api_json("GET", "/supplier-offers", token=token, expected=200)
    offer = next(
        (
            o for o in offers
            if int(o.get("requestId") or 0) == int(candidate["requestId"])
            and int(o.get("supplierId") or 0) == int(supplier_id)
        ),
        None,
    )
    if not offer:
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
        raise RuntimeError("Для выбранного поставщика не создан supplier_offer")
    if supplier_token:
        _, supplier_offers = api_json("GET", "/supplier-offers", token=supplier_token, expected=200)
        if not any(int(row.get("id") or 0) == int(offer_id) for row in supplier_offers):
            raise RuntimeError("Поставщик не видит адресованное ему КП через recipient/company scope")
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
        token=supplier_token or token,
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


def create_supplier_invoice_for_offer(supplier_token, offer_id, candidate, stamp):
    invoice_payload = {
        "invoiceNumber": f"CODEX-SUPINV-{stamp}",
        "invoiceDate": dt.date.today().isoformat(),
        "amount": round(TEST_PRICE * candidate["quantity"], 2),
        "vatAmount": 0,
        "description": f"{TEST_NOTE_PREFIX} invoice",
    }
    _, body = api_json(
        "POST",
        f"/supplier-offers/{offer_id}/create-invoice",
        token=supplier_token,
        data=invoice_payload,
        expected=200,
    )
    invoice_id = body.get("id")
    if not invoice_id:
        raise RuntimeError("Создание счета поставщика не вернуло id")
    _, repeated = api_json(
        "POST",
        f"/supplier-offers/{offer_id}/create-invoice",
        token=supplier_token,
        data=invoice_payload,
        expected=200,
    )
    if repeated.get("id") != invoice_id or repeated.get("alreadyExists") is not True:
        raise RuntimeError("Повторное создание счета по КП должно вернуть существующий счет")
    _, offer_history = api_json(
        "GET",
        f"/supplier-offers/{offer_id}/history",
        token=supplier_token,
        expected=200,
    )
    invoice_event = next(
        (row for row in offer_history if row.get("eventType") == "invoice_created"),
        None,
    )
    if not invoice_event:
        raise RuntimeError("Создание счета по КП не записано в историю предложения")
    try:
        event_payload = json.loads(invoice_event.get("payloadJson") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        event_payload = {}
    if int(event_payload.get("invoiceId") or 0) != int(invoice_id):
        raise RuntimeError("История КП содержит неверную ссылку на созданный счет")
    return invoice_id


def ship_and_receive(ship_token, receive_token, candidate, offer_id, stamp):
    qty = candidate["quantity"]
    _, shipped = api_json(
        "POST",
        f"/supplier-offers/{offer_id}/ship",
        token=ship_token,
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
        token=receive_token,
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


def assert_supplier_invoice_scope(admin_token, supplier_token, candidate, offer_id, supplier_invoice_id, warehouse_invoice_id):
    _, supplier_invoices = api_json("GET", "/supplier-invoices", token=supplier_token, expected=200)
    invoice = next((r for r in supplier_invoices if int(r.get("id") or 0) == int(supplier_invoice_id)), None)
    if not invoice:
        raise RuntimeError("Поставщик не видит свой счет в /supplier-invoices")
    if int(invoice.get("offerId") or 0) != int(offer_id):
        raise RuntimeError("Счет поставщика не связан с выбранным КП")
    if int(invoice.get("warehouseInvoiceId") or 0) != int(warehouse_invoice_id):
        raise RuntimeError("Поставщик не видит связь счета со складской накладной")
    if not invoice.get("warehouseInvoiceNumber"):
        raise RuntimeError("Поставщик не видит номер складской накладной")
    if not invoice.get("warehouseInvoiceDate"):
        raise RuntimeError("Поставщик не видит дату складской накладной")
    if invoice.get("deliveryStatus") != "Принято":
        raise RuntimeError("Поставщик не видит статус приемки Принято")
    if as_float(invoice.get("receivedQuantity")) < candidate["quantity"] - 0.000001:
        raise RuntimeError("Поставщик видит неверное принятое количество")
    items = invoice.get("warehouseInvoiceItems") or []
    if not any(norm_text(i.get("name") or i.get("materialName")) == norm_text(candidate["materialName"]) for i in items if isinstance(i, dict)):
        raise RuntimeError("Поставщик не видит список материалов складской накладной")
    request_company_id = int(
        (candidate.get("request") or {}).get("companyId")
        or (candidate.get("request") or {}).get("company_id")
        or 0
    )
    invoice_company_id = int(invoice.get("companyId") or 0)
    if request_company_id and invoice_company_id != request_company_id:
        raise RuntimeError("Кабинет поставщика получил счёт из неверной компании")
    expected_company_id = request_company_id or invoice_company_id
    if expected_company_id <= 0:
        raise RuntimeError("У счёта поставщика не определена компания")
    _, internal_invoices = api_json(
        "GET",
        "/supplier-invoices",
        token=admin_token,
        expected=200,
        headers={
            "X-Company-Mode": "company",
            "X-Company-Id": str(expected_company_id),
        },
    )
    foreign_company_rows = [
        row
        for row in internal_invoices
        if int(row.get("companyId") or 0) != expected_company_id
    ]
    if foreign_company_rows:
        raise RuntimeError("Внутренний список счетов смешал несколько компаний")
    internal_invoice = next(
        (row for row in internal_invoices if int(row.get("id") or 0) == int(supplier_invoice_id)),
        None,
    )
    if not internal_invoice:
        raise RuntimeError("Внутренний кабинет выбранной компании не видит счёт поставщика")
    if int(internal_invoice.get("companyId") or 0) != int(invoice.get("companyId") or 0):
        raise RuntimeError("Внутренний кабинет и поставщик получили разные компании счёта")
    return invoice


def assert_supplier_offer_withdraw_and_resubmit(admin_token, supplier_token, supplier_id, candidate, stamp, created):
    extra = dict(candidate)
    request, error = create_supply_request_for_candidate(admin_token, supplier_id, extra, stamp + "-withdraw")
    if not request:
        raise RuntimeError("Не удалось создать заявку для проверки отзыва КП: " + str(error))
    request_id = request["id"]
    created["withdrawRequestId"] = request_id
    _, offer = api_json(
        "POST",
        "/supplier-offers",
        token=admin_token,
        data={
            "requestId": request_id,
            "supplierId": supplier_id,
            "pricePerUnit": 0,
            "totalPrice": 0,
            "deliveryDays": 0,
            "notes": TEST_NOTE_PREFIX,
        },
        expected=200,
    )
    offer_id = offer.get("id")
    if not offer_id:
        raise RuntimeError("КП для проверки отзыва не создано")
    created["withdrawOfferId"] = offer_id
    _, request_offers = api_json("GET", "/supplier-offers", token=admin_token, expected=200)
    same_request_offers = [
        row for row in request_offers
        if int(row.get("requestId") or 0) == int(request_id)
    ]
    if len(same_request_offers) != 1 or int(same_request_offers[0].get("id") or 0) != int(offer_id):
        raise RuntimeError("Повторный POST supplier-offer создал дубль вместо обновления адресованного КП")
    _, repeated_offer_history = api_json(
        "GET",
        f"/supplier-offers/{offer_id}/history",
        token=admin_token,
        expected=200,
    )
    if not any(row.get("eventType") == "draft_updated" for row in repeated_offer_history):
        raise RuntimeError("Обновление адресованного КП через POST не записано в аудит")
    qty = extra["quantity"]
    api_json(
        "PUT",
        f"/supplier-offers/{offer_id}",
        token=supplier_token,
        data={
            "action": "respond",
            "pricePerUnit": TEST_PRICE,
            "quantity": qty,
            "totalPrice": round(TEST_PRICE * qty, 2),
            "deliveryDays": 1,
            "paymentTerms": "Постоплата",
        },
        expected=200,
    )
    _, withdrawn = api_json(
        "PUT",
        f"/supplier-offers/{offer_id}",
        token=supplier_token,
        data={"action": "withdraw"},
        expected=200,
    )
    if withdrawn.get("status") != "Отозвано":
        raise RuntimeError("КП не перешло в статус Отозвано")
    _, resubmitted = api_json(
        "PUT",
        f"/supplier-offers/{offer_id}",
        token=supplier_token,
        data={
            "action": "respond",
            "pricePerUnit": TEST_PRICE + 1,
            "quantity": qty,
            "totalPrice": round((TEST_PRICE + 1) * qty, 2),
            "deliveryDays": 2,
            "paymentTerms": "Постоплата",
        },
        expected=200,
    )
    if resubmitted.get("status") != "Получено":
        raise RuntimeError("Отозванное КП нельзя подать заново")
    _, history = api_json("GET", f"/supplier-offers/{offer_id}/history", token=supplier_token, expected=200)
    events = [row.get("eventType") for row in history]
    if "withdrawn" not in events or events.count("responded") < 2:
        raise RuntimeError("История КП не сохранила отзыв и повторную подачу")


def assert_unlinked_supplier_recipient_diagnostics(admin_token, candidate, stamp, created):
    extra = dict(candidate)
    request, error = create_supply_request_for_candidate(admin_token, None, extra, stamp + "-unlinked")
    if not request:
        raise RuntimeError("Не удалось создать заявку для проверки несвязанного поставщика: " + str(error))
    request_id = request["id"]
    created["diagnosticRequestId"] = request_id

    supplier_id = create_unlinked_supplier_record(stamp)
    created["diagnosticSupplierId"] = supplier_id

    status, body = api_json(
        "POST",
        f"/supply-requests/{request_id}/request-kp",
        token=admin_token,
        data={"supplierIds": [supplier_id]},
    )
    detail = str(body.get("detail") or body.get("error") or body)
    if status != 400 or "не привязан" not in detail:
        raise RuntimeError(f"Несвязанный поставщик не был заблокирован перед КП: HTTP {status}, {detail[:300]}")

    offer_id = create_legacy_supplier_offer_record(request_id, supplier_id)
    created["diagnosticOfferId"] = offer_id

    _, recipients = api_json("GET", f"/supply-requests/{request_id}/recipients", token=admin_token, expected=200)
    if not isinstance(recipients, list):
        raise RuntimeError("Диагностика получателей КП вернула не список")
    row = next(
        (
            r for r in recipients
            if int(r.get("targetSupplierId") or r.get("supplierId") or 0) == int(supplier_id)
        ),
        None,
    )
    if not row:
        raise RuntimeError("Диагностика получателей КП не восстановила legacy supplier_offer")
    if row.get("visibleToSupplier"):
        raise RuntimeError("Несвязанный legacy-поставщик ошибочно отмечен как видимый")
    if row.get("linkAction") != "link_supplier_user":
        raise RuntimeError("Диагностика несвязанного поставщика не дала действие link_supplier_user")
    if int(row.get("linkSupplierId") or 0) != int(supplier_id):
        raise RuntimeError("Диагностика несвязанного поставщика ведет не к той supplier-карточке")
    if not row.get("problemReason"):
        raise RuntimeError("Диагностика несвязанного поставщика не объясняет причину невидимости")
    if row.get("source") != "supplier_offers":
        raise RuntimeError("Legacy-диагностика получателей КП не помечена source=supplier_offers")
    offer_statuses = row.get("offerStatuses") or []
    if not any(int(item.get("offerId") or 0) == int(offer_id) for item in offer_statuses if isinstance(item, dict)):
        raise RuntimeError("Диагностика получателей КП не показала статус legacy КП")


def ensure_supplier_max_account(email, stamp, created):
    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messenger_accounts (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(40) NOT NULL,
                user_id INT,
                staff_id INT,
                external_user_id VARCHAR(120),
                chat_id VARCHAR(120),
                display_name VARCHAR(255),
                phone_hash VARCHAR(255),
                verified_at TIMESTAMP DEFAULT NOW(),
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            SELECT id, name
              FROM users
             WHERE LOWER(email)=LOWER(%s)
               AND COALESCE(role,'')=%s
               AND COALESCE(active, TRUE)=TRUE
             ORDER BY id
             LIMIT 1
            """,
            (email, "поставщик"),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Не найден пользователь поставщика для MAX smoke")
        user_id, user_name = row
        external_user_id = f"codex-max-supplier-{stamp}"
        chat_id = f"codex-max-supplier-chat-{stamp}"
        cur.execute(
            """
            INSERT INTO messenger_accounts
                (provider, user_id, external_user_id, chat_id, display_name, enabled, verified_at, created_at, updated_at)
            VALUES ('max',%s,%s,%s,%s,TRUE,NOW(),NOW(),NOW())
            RETURNING id
            """,
            (user_id, external_user_id, chat_id, user_name or email),
        )
        account_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        created["notificationMessengerAccountId"] = account_id
        return account_id
    finally:
        conn.close()


def assert_supply_request_notifications(admin_token, supplier_id, supplier_email, candidate, stamp, created):
    account_id = ensure_supplier_max_account(supplier_email, stamp, created)
    extra = dict(candidate)
    request, error = create_supply_request_for_candidate(admin_token, supplier_id, extra, stamp + "-notify")
    if not request:
        raise RuntimeError("Не удалось создать заявку для проверки уведомлений КП: " + str(error))
    request_id = request["id"]
    created["notificationRequestId"] = request_id

    notifications = request.get("notifications") or []
    if not notifications:
        raise RuntimeError("Создание КП не вернуло статусы уведомлений")

    _, recipients = api_json("GET", f"/supply-requests/{request_id}/recipients", token=admin_token, expected=200)
    row = next(
        (
            r for r in recipients
            if int(r.get("targetSupplierId") or r.get("supplierId") or 0) == int(supplier_id)
        ),
        None,
    )
    if not row:
        raise RuntimeError("Диагностика получателей не показала поставщика для проверки уведомлений")
    if not row.get("visibleToSupplier"):
        raise RuntimeError("Связанный поставщик ошибочно не видит КП в диагностике")
    email_status = row.get("emailNotificationStatus") or ""
    if email_status not in ("Пропущено: тестовый email", "SMTP не настроен", "Отправлено", "Ошибка отправки"):
        raise RuntimeError("Диагностика получателей КП не записала понятный email-статус: " + str(email_status))
    if row.get("maxNotificationStatus") != "В очереди MAX":
        raise RuntimeError("MAX-уведомление по КП не поставлено в очередь: " + str(row.get("maxNotificationStatus")))
    outbox_id = row.get("maxOutboxId")
    if not outbox_id:
        raise RuntimeError("Диагностика получателей КП не вернула maxOutboxId")

    conn = db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, provider, messenger_account_id, event_type, entity_type, entity_id, status, actions_json
              FROM messenger_outbox
             WHERE id=%s
            """,
            (outbox_id,),
        )
        outbox = cur.fetchone()
        cur.close()
        if not outbox:
            raise RuntimeError("MAX outbox-запись по КП не найдена в базе")
        if outbox.get("provider") != "max" or int(outbox.get("messenger_account_id") or 0) != int(account_id):
            raise RuntimeError("MAX outbox-запись по КП привязана не к аккаунту поставщика")
        if outbox.get("event_type") != "supplier_kp_requested" or outbox.get("entity_type") != "supply_request":
            raise RuntimeError("MAX outbox-запись по КП имеет неверный тип события")
        if int(outbox.get("entity_id") or 0) != int(request_id):
            raise RuntimeError("MAX outbox-запись по КП указывает не на заявку")
        if outbox.get("status") != "queued":
            raise RuntimeError("MAX outbox-запись по КП не в статусе queued")
        actions = outbox.get("actions_json") or []
        if isinstance(actions, str):
            actions = json.loads(actions)
        if not any(isinstance(action, dict) and action.get("kind") == "open_app" for action in actions):
            raise RuntimeError("MAX outbox-запись по КП не содержит open_app кнопку")
    finally:
        conn.close()

    created["notificationOutboxId"] = outbox_id
    offer_id = next((n.get("offerId") for n in notifications if isinstance(n, dict) and n.get("offerId")), None)
    if not offer_id:
        _, offers = api_json("GET", "/supplier-offers", token=admin_token, expected=200)
        offer = next(
            (
                o for o in offers
                if int(o.get("requestId") or 0) == int(request_id)
                and int(o.get("supplierId") or 0) == int(supplier_id)
            ),
            None,
        )
        offer_id = offer.get("id") if offer else None
    if offer_id:
        created["notificationOfferId"] = offer_id
    return request_id, outbox_id


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

    def matching_candidate_inspections(rows):
        return [
            r for r in rows
            if norm_text(r.get("materialName")) == norm_text(candidate["materialName"])
            and (r.get("projectName") or "") == candidate["projectName"]
            and (r.get("workPackage") or "Основная") == candidate["workPackage"]
            and as_float(r.get("quantity")) >= candidate["quantity"] - 0.000001
        ]

    _, inspections = api_json("GET", f"/material-inspection?project_name={urllib.parse.quote(candidate['projectName'])}", token=token, expected=200)
    matched_inspections = matching_candidate_inspections(inspections)
    if not matched_inspections:
        raise RuntimeError("Журнал входного контроля не подтянул принятую поставку")
    _, inspections_again = api_json("GET", f"/material-inspection?project_name={urllib.parse.quote(candidate['projectName'])}", token=token, expected=200)
    matched_again = matching_candidate_inspections(inspections_again)
    if len(matched_again) != len(matched_inspections):
        raise RuntimeError("Повторное открытие входного контроля создало дубль записи")

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

    _, inspections_after_manual = api_json("GET", f"/material-inspection?project_name={urllib.parse.quote(candidate['projectName'])}", token=token, expected=200)
    if not any(
        int(r.get("invoiceId") or 0) == int(manual_invoice_id)
        and norm_text(r.get("materialName")) == norm_text(manual_material_name)
        for r in inspections_after_manual
    ):
        raise RuntimeError("Журнал входного контроля не подтянул ручную накладную объекта")
    return manual_invoice_id, manual_material_name


def assert_cable_journal_chain(token, candidate, delivery_id):
    cable_name = f"Кабель ВВГнг-LS 3х2.5 CODEX QA {delivery_id}"
    cable_qty = max(1.0, candidate["quantity"])
    _, cable_invoice = api_json(
        "POST",
        "/warehouse-invoices",
        token=token,
        data={
            "number": f"CODEX-CABLE-{delivery_id}",
            "date": dt.date.today().isoformat(),
            "supplierName": "CODEX QA",
            "acceptedBy": "CODEX QA",
            "location": candidate["projectName"],
            "project": candidate["projectName"],
            "sourceType": "manual_project_invoice",
            "items": [{
                "name": cable_name,
                "quantity": cable_qty,
                "unit": "м",
                "price": TEST_PRICE,
                "workPackage": candidate["workPackage"],
            }],
            "totalBase": round(TEST_PRICE * cable_qty, 2),
            "totalVat": 0,
            "totalWithVat": round(TEST_PRICE * cable_qty, 2),
        },
        expected=200,
    )
    cable_invoice_id = cable_invoice.get("id")
    if not cable_invoice_id:
        raise RuntimeError("Кабельная накладная не вернула id")

    def matching_cables(rows):
        return [
            r for r in rows
            if int(r.get("invoiceId") or 0) == int(cable_invoice_id)
            and norm_text(r.get("cableBrand")) == norm_text(cable_name)
        ]

    _, cables = api_json("GET", f"/cable-journal?project_name={urllib.parse.quote(candidate['projectName'])}", token=token, expected=200)
    matched_rows = matching_cables(cables)
    matched = matched_rows[0] if matched_rows else None
    if not matched:
        raise RuntimeError("Журнал кабельной продукции не подтянул кабельную накладную")
    _, cables_again = api_json("GET", f"/cable-journal?project_name={urllib.parse.quote(candidate['projectName'])}", token=token, expected=200)
    if len(matching_cables(cables_again)) != len(matched_rows):
        raise RuntimeError("Повторное открытие кабельного журнала создало дубль записи")
    if as_float(matched.get("lengthReceived")) < cable_qty - 0.000001:
        raise RuntimeError("Журнал кабельной продукции показал неверную длину прихода")
    if "силовой" not in norm_text(matched.get("cableType") or ""):
        raise RuntimeError("Кабель ВВГнг-LS не классифицирован как силовой")
    return cable_invoice_id, cable_name, cable_qty


def assert_foreman_invoice_chain(admin_token, candidate, delivery_id):
    foreman_token = ensure_foreman_user(candidate["projectName"])
    foreman_material_name = f"CODEX QA прямой заказ прораба {delivery_id}"
    _, foreman_invoice = api_json(
        "POST",
        "/warehouse-invoices",
        token=foreman_token,
        data={
            "number": f"CODEX-FOREMAN-{delivery_id}",
            "date": dt.date.today().isoformat(),
            "supplierName": "CODEX QA",
            "acceptedBy": TEST_FOREMAN_NAME,
            "location": candidate["projectName"],
            "project": candidate["projectName"],
            "sourceType": "manual_project_invoice",
            "items": [{
                "name": foreman_material_name,
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
    foreman_invoice_id = foreman_invoice.get("id")
    if not foreman_invoice_id:
        raise RuntimeError("Прорабская приходная накладная на объект не вернула id")

    _, invoices = api_json("GET", "/warehouse-invoices", token=foreman_token, expected=200)
    saved_invoice = next((r for r in invoices if int(r.get("id") or 0) == int(foreman_invoice_id)), None)
    if not saved_invoice:
        raise RuntimeError("Прораб не видит созданную им накладную на объект")
    if saved_invoice.get("location") != candidate["projectName"]:
        raise RuntimeError("Прорабская накладная ушла не на закрепленный объект")
    saved_items = saved_invoice.get("items") or []
    saved_item = next((i for i in saved_items if isinstance(i, dict) and norm_text(i.get("name")) == norm_text(foreman_material_name)), None)
    if not saved_item:
        raise RuntimeError("Прорабская накладная не сохранила материал")
    estimate_control = saved_item.get("estimateControl") or {}
    if not estimate_control.get("manualProjectInvoiceOverride"):
        raise RuntimeError("Прорабская накладная на объект не получила контрольную пометку manualProjectInvoiceOverride")

    _, materials = api_json("GET", "/materials", token=admin_token, expected=200)
    if not any(
        norm_text(r.get("name")) == norm_text(foreman_material_name)
        and (r.get("project") or "") == candidate["projectName"]
        for r in materials
    ):
        raise RuntimeError("Прямой материал прораба не попал на склад объекта")

    blocked_status, _ = api_json(
        "POST",
        "/warehouse-invoices",
        token=foreman_token,
        data={
            "number": f"CODEX-FOREMAN-MAIN-{delivery_id}",
            "date": dt.date.today().isoformat(),
            "supplierName": "CODEX QA",
            "acceptedBy": TEST_FOREMAN_NAME,
            "location": "Основной склад",
            "project": "",
            "sourceType": "manual_main_invoice",
            "items": [{
                "name": f"{foreman_material_name} основной склад",
                "quantity": candidate["quantity"],
                "unit": candidate["unit"],
                "price": TEST_PRICE,
                "workPackage": candidate["workPackage"],
            }],
            "totalBase": round(TEST_PRICE * candidate["quantity"], 2),
            "totalVat": 0,
            "totalWithVat": round(TEST_PRICE * candidate["quantity"], 2),
        },
        expected=None,
    )
    if blocked_status != 403:
        raise RuntimeError(f"Прораб смог или некорректно попытался принять на основной склад: HTTP {blocked_status}")
    return foreman_invoice_id, foreman_material_name


def assert_alias_invoice_chain(token, candidate, delivery_id):
    alias_name = f"CODEX QA алиас накладной {delivery_id}"
    canonical_name = candidate["materialName"]
    canonical_unit = candidate["unit"]
    _, alias = api_json(
        "POST",
        "/material-aliases",
        token=token,
        data={
            "projectName": candidate["projectName"],
            "aliasName": alias_name,
            "canonicalName": canonical_name,
            "canonicalUnit": canonical_unit,
            "source": "smoke-supply-chain",
            "active": True,
        },
        expected=200,
    )
    alias_id = alias.get("id")
    if not alias_id:
        raise RuntimeError("Сопоставление материала не вернуло id")

    _, invoice = api_json(
        "POST",
        "/warehouse-invoices",
        token=token,
        data={
            "number": f"CODEX-ALIAS-{delivery_id}",
            "date": dt.date.today().isoformat(),
            "supplierName": "CODEX QA",
            "acceptedBy": "CODEX QA",
            "location": candidate["projectName"],
            "project": candidate["projectName"],
            "sourceType": "manual_project_invoice",
            "items": [{
                "name": alias_name,
                "quantity": candidate["quantity"],
                "unit": canonical_unit,
                "price": TEST_PRICE,
                "workPackage": candidate["workPackage"],
            }],
            "totalBase": round(TEST_PRICE * candidate["quantity"], 2),
            "totalVat": 0,
            "totalWithVat": round(TEST_PRICE * candidate["quantity"], 2),
        },
        expected=200,
    )
    alias_invoice_id = invoice.get("id")
    if not alias_invoice_id:
        raise RuntimeError("Накладная по алиасу не вернула id")

    _, invoices = api_json("GET", "/warehouse-invoices", token=token, expected=200)
    saved_invoice = next((r for r in invoices if int(r.get("id") or 0) == int(alias_invoice_id)), None)
    if not saved_invoice:
        raise RuntimeError("Накладная по алиасу не найдена в списке накладных")
    saved_items = saved_invoice.get("items") or []
    saved_item = next((i for i in saved_items if isinstance(i, dict) and norm_text(i.get("name")) == norm_text(canonical_name)), None)
    if not saved_item:
        raise RuntimeError("Накладная по алиасу не переписала материал в сметное название")
    if norm_text(saved_item.get("invoiceOriginalName") or saved_item.get("originalName")) != norm_text(alias_name):
        raise RuntimeError("Накладная по алиасу не сохранила исходное название поставщика")
    material_alias = saved_item.get("materialAlias") or {}
    if norm_text(material_alias.get("canonicalName")) != norm_text(canonical_name):
        raise RuntimeError("Накладная по алиасу не сохранила информацию о сопоставлении")
    estimate_control = saved_item.get("estimateControl") or {}
    if estimate_control.get("status") == "no_estimate_material":
        raise RuntimeError("Сметный контроль не применился после сопоставления алиаса")

    _, materials = api_json("GET", "/materials", token=token, expected=200)
    canonical_rows = [
        r for r in materials
        if norm_text(r.get("name")) == norm_text(canonical_name)
        and (r.get("project") or "") == candidate["projectName"]
        and (r.get("workPackage") or r.get("work_package") or "Основная") == candidate["workPackage"]
    ]
    raw_rows = [
        r for r in materials
        if norm_text(r.get("name")) == norm_text(alias_name)
        and (r.get("project") or "") == candidate["projectName"]
    ]
    if not canonical_rows:
        raise RuntimeError("Материал по алиасу не попал на склад под сметным названием")
    if raw_rows:
        raise RuntimeError("Сырой материал поставщика попал на склад отдельной строкой вместо сметного материала")
    return alias_invoice_id, alias_id, alias_name


def assert_backfill_uncertain_supplier_review(token, candidate, stamp, created):
    supplier_name = f"{TEST_SUPPLIER_PREFIX} backfill спорный {stamp}"
    invoice_number = f"CODEX-BACKFILL-{stamp}"
    conn = db_conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO suppliers
                (name, phone, email, specialization, category, rating, status, source_type, source_detail)
            VALUES (%s,'','','CODEX QA','Материалы',5,'Активный','smoke_backfill_supplier',%s)
            RETURNING id
            """,
            (supplier_name, TEST_NOTE_PREFIX),
        )
        supplier_id = cur.fetchone()[0]
        items = [{
            "name": candidate["materialName"],
            "quantity": candidate["quantity"],
            "unit": candidate["unit"],
            "price": TEST_PRICE,
            "workPackage": candidate["workPackage"],
        }]
        total = round(TEST_PRICE * candidate["quantity"], 2)
        cur.execute(
            """
            INSERT INTO warehouse_invoices
                (company_id, number, date, supplier_id, supplier_name, accepted_by,
                 location, project, items, total_base, total_vat, total_with_vat,
                 status, added_by, source_type)
            VALUES (1,%s,%s,NULL,%s,'CODEX QA',%s,%s,%s,%s,0,%s,'Принято','CODEX QA','legacy_smoke_backfill')
            RETURNING id
            """,
            (
                invoice_number,
                dt.date.today().isoformat(),
                supplier_name,
                candidate["projectName"],
                candidate["projectName"],
                json.dumps(items, ensure_ascii=False),
                total,
                total,
            ),
        )
        invoice_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
    finally:
        conn.close()

    created["backfillInvoiceId"] = invoice_id
    created["backfillSupplierId"] = supplier_id

    _, preview = api_json(
        "POST",
        "/supplier-documents/backfill",
        token=token,
        data={"warehouseInvoiceId": invoice_id, "limit": 1},
        expected=200,
    )
    preview_items = preview.get("items") or []
    if preview.get("dryRun") is not True or not preview_items:
        raise RuntimeError(f"Backfill preview не показал тестовую накладную: {preview}")
    if not preview_items[0].get("needsReview"):
        raise RuntimeError(f"Backfill preview не пометил name-only связь как needsReview: {preview_items[0]}")

    _, result = api_json(
        "POST",
        "/supplier-documents/backfill",
        token=token,
        data={"warehouseInvoiceId": invoice_id, "apply": True, "limit": 1},
        expected=200,
    )
    result_items = result.get("items") or []
    result_item = result_items[0] if result_items else {}
    supplier_invoice_id = result_item.get("supplierInvoiceId")
    if result.get("linked") != 1 or not supplier_invoice_id:
        raise RuntimeError(f"Backfill не создал первичку поставщика по тестовой накладной: {result}")
    if not result_item.get("needsReview") or result_item.get("accountingStatus") != "Нужно уточнение":
        raise RuntimeError(f"Backfill не перевел спорную связь в Нужно уточнение: {result_item}")
    review_reason = str(result_item.get("reviewReason") or "").lower()
    if not any(fragment in review_reason for fragment in ["назв", "старой накладной", "не подтвержден"]):
        raise RuntimeError(f"Backfill не объяснил причину уточнения: {result_item}")
    backfill_created_supplier_id = int(result_item.get("supplierId") or 0)
    if backfill_created_supplier_id:
        created["backfillCreatedSupplierId"] = backfill_created_supplier_id

    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT accounting_status, supplier_invoice_id FROM warehouse_invoices WHERE id=%s", (invoice_id,))
        invoice_row = cur.fetchone()
        if not invoice_row or invoice_row[0] != "Нужно уточнение" or int(invoice_row[1] or 0) != int(supplier_invoice_id):
            raise RuntimeError("Складская накладная после backfill не получила статус Нужно уточнение")
        cur.execute("SELECT status, supplier_id FROM supplier_invoices WHERE id=%s", (supplier_invoice_id,))
        supplier_invoice_row = cur.fetchone()
        expected_supplier_id = backfill_created_supplier_id or supplier_id
        if not supplier_invoice_row or supplier_invoice_row[0] != "Нужно уточнение" or int(supplier_invoice_row[1] or 0) != int(expected_supplier_id):
            raise RuntimeError("Первичка поставщика после спорного backfill не получила статус Нужно уточнение")
        cur.close()
    finally:
        conn.close()
    created["backfillSupplierInvoiceId"] = supplier_invoice_id
    return invoice_id, supplier_invoice_id, supplier_id, backfill_created_supplier_id


def assert_name_only_warehouse_invoice_does_not_link_supplier(token, candidate, stamp, created):
    supplier_name = f"{TEST_SUPPLIER_PREFIX} name-only {stamp}"
    invoice_number = f"CODEX-NAMEONLY-{stamp}"
    material_name = f"{TEST_SUPPLIER_PREFIX} name-only material {stamp}"
    conn = db_conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO suppliers
                (name, phone, email, specialization, category, rating, status, source_type, source_detail)
            VALUES (%s,'','','CODEX QA','Материалы',5,'Активный','smoke_name_only_supplier',%s)
            RETURNING id
            """,
            (supplier_name, TEST_NOTE_PREFIX),
        )
        existing_supplier_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
    finally:
        conn.close()

    created["nameOnlyExistingSupplierId"] = existing_supplier_id
    created["nameOnlyMaterialName"] = material_name

    _, invoice = api_json(
        "POST",
        "/warehouse-invoices",
        token=token,
        data={
            "number": invoice_number,
            "date": dt.date.today().isoformat(),
            "supplierName": supplier_name,
            "acceptedBy": "CODEX QA",
            "location": "Основной склад",
            "warehouseTarget": "main",
            "sourceType": "manual_main_invoice",
            "reviewUncertainSupplierMatch": True,
            "items": [{
                "name": material_name,
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
    invoice_id = invoice.get("id")
    supplier_invoice_id = invoice.get("supplierInvoiceId")
    if not invoice_id:
        raise RuntimeError(f"Name-only складская накладная не вернула id: {invoice}")
    created["nameOnlyInvoiceId"] = invoice_id
    created["nameOnlySupplierInvoiceId"] = supplier_invoice_id

    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT supplier_id, supplier_invoice_id, accounting_status FROM warehouse_invoices WHERE id=%s", (invoice_id,))
        warehouse_row = cur.fetchone()
        if not warehouse_row:
            raise RuntimeError("Name-only складская накладная не найдена после создания")
        warehouse_supplier_id = int(warehouse_row[0] or 0)
        linked_supplier_invoice_id = int(warehouse_row[1] or 0)
        if warehouse_supplier_id == int(existing_supplier_id):
            raise RuntimeError("Складская накладная привязалась к существующему поставщику только по названию")
        if linked_supplier_invoice_id:
            created["nameOnlySupplierInvoiceId"] = linked_supplier_invoice_id
            cur.execute("SELECT supplier_id, status FROM supplier_invoices WHERE id=%s", (linked_supplier_invoice_id,))
            invoice_row = cur.fetchone()
            if invoice_row and int(invoice_row[0] or 0) == int(existing_supplier_id):
                raise RuntimeError("Первичка поставщика привязалась к существующему поставщику только по названию")
            if invoice_row and invoice_row[1] != "Нужно уточнение":
                raise RuntimeError(f"Name-only первичка не получила статус Нужно уточнение: {invoice_row[1]}")
            if invoice_row and int(invoice_row[0] or 0):
                created["nameOnlyCreatedSupplierId"] = int(invoice_row[0] or 0)
        cur.close()
    finally:
        conn.close()
    return invoice_id, supplier_invoice_id, existing_supplier_id


def assert_supplier_invoice_dedupe(token, supplier_invoice_id, created):
    conn = db_conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO supplier_invoices
                (company_id,supplier_id,supplier_name,project_name,invoice_number,invoice_date,
                 amount,vat_amount,description,file_url,photo_url,status,
                 offer_id,request_id,payment_terms,material_name,work_package,warehouse_invoice_id)
            SELECT company_id,supplier_id,supplier_name,project_name,invoice_number,invoice_date,
                   amount,vat_amount,description,file_url,photo_url,status,
                   offer_id,request_id,payment_terms,material_name,work_package,NULL
              FROM supplier_invoices
             WHERE id=%s
            RETURNING id
            """,
            (supplier_invoice_id,),
        )
        duplicate_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
    finally:
        conn.close()

    created["dedupeSupplierInvoiceDuplicateId"] = duplicate_id

    _, preview = api_json(
        "POST",
        "/supplier-documents/dedupe",
        token=token,
        data={"projectName": created.get("projectName"), "limit": 50},
        expected=200,
    )
    groups = preview.get("groups") or []
    target_group = next((g for g in groups if duplicate_id in (g.get("duplicateIds") or [])), None)
    if preview.get("dryRun") is not True or not target_group:
        raise RuntimeError(f"Дедупликация первички не показала тестовый дубль: {preview}")
    if target_group.get("canonicalId") != supplier_invoice_id:
        raise RuntimeError(f"Дедупликация выбрала неверный основной счет: {target_group}")
    if target_group.get("needsManualReview"):
        raise RuntimeError(f"Очевидный дубль первички ошибочно ушел в ручную проверку: {target_group}")

    _, result = api_json(
        "POST",
        "/supplier-documents/dedupe",
        token=token,
        data={"projectName": created.get("projectName"), "apply": True, "limit": 50},
        expected=200,
    )
    applied_groups = result.get("groups") or []
    applied_group = next((g for g in applied_groups if duplicate_id in (g.get("duplicateIds") or [])), None)
    if result.get("dryRun") is not False or not applied_group or not applied_group.get("applied"):
        raise RuntimeError(f"Дедупликация первички не применила тестовый дубль: {result}")

    conn = db_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM supplier_invoices WHERE id=%s", (duplicate_id,))
        duplicate_status = (cur.fetchone() or [""])[0]
        if duplicate_status != "Аннулирован":
            raise RuntimeError(f"Дубль первички не аннулирован: {duplicate_status}")
        cur.execute("SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s", (supplier_invoice_id,))
        canonical_warehouse_id = (cur.fetchone() or [None])[0]
        if not canonical_warehouse_id:
            raise RuntimeError("Основная первичка после дедупликации потеряла складскую накладную")
        cur.execute("SELECT supplier_invoice_id FROM warehouse_invoices WHERE id=%s", (canonical_warehouse_id,))
        linked_supplier_invoice_id = (cur.fetchone() or [None])[0]
        if int(linked_supplier_invoice_id or 0) != int(supplier_invoice_id):
            raise RuntimeError("Складская накладная после дедупликации не указывает на основной счет")
        cur.close()
    finally:
        conn.close()
    return duplicate_id


def assert_supplier_documents_group_scope(token, supplier_id, stamp, created):
    duplicate_supplier_id = None
    document_ids = []
    conn = db_conn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SELECT name FROM suppliers WHERE id=%s", (supplier_id,))
        supplier_row = cur.fetchone()
        if not supplier_row:
            raise RuntimeError("Не найден тестовый поставщик для проверки документов группы")
        supplier_name = supplier_row[0]
        cur.execute(
            """
            INSERT INTO suppliers
                (name, phone, email, specialization, category, rating, status, source_type, source_detail)
            VALUES (%s,%s,'','CODEX QA','Материалы',5,'Активный','smoke_supplier_duplicate',%s)
            RETURNING id
            """,
            ("CODEX QA ручной дубль поставщика " + stamp, "+7999000" + str(stamp)[-4:], TEST_NOTE_PREFIX),
        )
        duplicate_supplier_id = cur.fetchone()[0]
        for sid, title in [
            (supplier_id, "CODEX QA основной документ поставщика"),
            (duplicate_supplier_id, "CODEX QA документ дубля поставщика"),
        ]:
            cur.execute(
                """
                INSERT INTO supplier_documents
                    (supplier_id, doc_type, title, file_url, status, notes, uploaded_by)
                VALUES (%s,'Реквизиты',%s,'','Загружен',%s,'CODEX QA')
                RETURNING id
                """,
                (sid, title + " " + stamp, TEST_NOTE_PREFIX),
            )
            document_ids.append(cur.fetchone()[0])
        conn.commit()
        cur.close()
    finally:
        conn.close()

    created["supplierDocumentDuplicateSupplierId"] = duplicate_supplier_id
    created["supplierDocumentIds"] = document_ids

    _, linked = api_json(
        "POST",
        f"/suppliers/{supplier_id}/link-duplicate",
        token=token,
        data={"duplicateSupplierId": duplicate_supplier_id},
        expected=200,
    )
    related_ids = [int(x) for x in (linked.get("relatedSupplierIds") or [])]
    if int(duplicate_supplier_id) not in related_ids:
        raise RuntimeError(f"Связка дубля поставщика не вернула общий supplier scope: {linked}")

    _, documents = api_json(
        "GET",
        f"/supplier-documents?supplier_id={supplier_id}",
        token=token,
        expected=200,
    )
    returned_ids = {int(doc.get("id") or 0) for doc in documents if doc.get("id")}
    missing_ids = [doc_id for doc_id in document_ids if int(doc_id) not in returned_ids]
    if missing_ids:
        raise RuntimeError(
            "Документы дубля поставщика не попали в /supplier-documents по основной карточке: "
            + json.dumps({"missing": missing_ids, "returned": sorted(returned_ids)}, ensure_ascii=False)
        )
    return duplicate_supplier_id, document_ids


def cleanup_request_ids(created):
    request_ids = set()
    for key in ("requestId", "withdrawRequestId", "diagnosticRequestId", "notificationRequestId"):
        try:
            request_id = int(created.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if request_id > 0:
            request_ids.add(request_id)
    return sorted(request_ids)


def cleanup_request_outbox(cur, created):
    for request_id in cleanup_request_ids(created):
        cur.execute(
            "DELETE FROM messenger_outbox WHERE provider='max' AND entity_type='supply_request' AND entity_id=%s",
            (request_id,),
        )


def cleanup(created):
    conn = None
    try:
        conn = db_conn()
        conn.autocommit = False
        cur = conn.cursor()
        project_name = created.get("projectName")
        package = created.get("workPackage")
        default_unit = created.get("unit")
        qty_by_material = {}
        for material_name, qty, material_unit in [
            (created.get("materialName"), created.get("quantity"), default_unit),
            (created.get("manualMaterialName"), created.get("manualQuantity"), default_unit),
            (created.get("foremanManualMaterialName"), created.get("foremanManualQuantity"), default_unit),
            (created.get("aliasCanonicalMaterialName"), created.get("aliasQuantity"), default_unit),
            (created.get("cableMaterialName"), created.get("cableQuantity"), created.get("cableUnit") or "м"),
        ]:
            if material_name:
                key = (material_name, material_unit or default_unit or "")
                qty_by_material[key] = qty_by_material.get(key, 0) + as_float(qty)
        material_names = [name for name, _unit in qty_by_material.keys()]

        for material_name, material_unit in [k for k in qty_by_material.keys() if k[0]]:
            qty = qty_by_material.get((material_name, material_unit), 0)
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
                    (material_name, project_name, package or "", material_unit or ""),
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
            "foremanManualInvoiceId": created.get("foremanManualInvoiceId"),
            "aliasInvoiceId": created.get("aliasInvoiceId"),
            "cableInvoiceId": created.get("cableInvoiceId"),
            "deliveryId": created.get("deliveryId"),
            "offerId": created.get("offerId"),
            "requestId": created.get("requestId"),
            "supplierInvoiceId": created.get("supplierInvoiceId"),
            "withdrawOfferId": created.get("withdrawOfferId"),
            "withdrawRequestId": created.get("withdrawRequestId"),
            "diagnosticOfferId": created.get("diagnosticOfferId"),
            "diagnosticRequestId": created.get("diagnosticRequestId"),
            "diagnosticSupplierId": created.get("diagnosticSupplierId"),
            "backfillInvoiceId": created.get("backfillInvoiceId"),
            "backfillSupplierInvoiceId": created.get("backfillSupplierInvoiceId"),
            "backfillSupplierId": created.get("backfillSupplierId"),
            "backfillCreatedSupplierId": created.get("backfillCreatedSupplierId"),
            "dedupeSupplierInvoiceDuplicateId": created.get("dedupeSupplierInvoiceDuplicateId"),
            "notificationRequestId": created.get("notificationRequestId"),
            "notificationOfferId": created.get("notificationOfferId"),
            "notificationOutboxId": created.get("notificationOutboxId"),
            "notificationMessengerAccountId": created.get("notificationMessengerAccountId"),
            "supplierDocumentDuplicateSupplierId": created.get("supplierDocumentDuplicateSupplierId"),
            "nameOnlyInvoiceId": created.get("nameOnlyInvoiceId"),
            "nameOnlySupplierInvoiceId": created.get("nameOnlySupplierInvoiceId"),
            "nameOnlyExistingSupplierId": created.get("nameOnlyExistingSupplierId"),
            "nameOnlyCreatedSupplierId": created.get("nameOnlyCreatedSupplierId"),
            "supplierId": created.get("supplierId"),
        }
        cleanup_request_outbox(cur, created)
        for document_id in created.get("supplierDocumentIds") or []:
            cur.execute("DELETE FROM supplier_documents WHERE id=%s", (document_id,))
        if ids["dedupeSupplierInvoiceDuplicateId"]:
            cur.execute("DELETE FROM supplier_invoices WHERE id=%s", (ids["dedupeSupplierInvoiceDuplicateId"],))
        if ids["nameOnlySupplierInvoiceId"]:
            cur.execute("DELETE FROM supplier_invoices WHERE id=%s", (ids["nameOnlySupplierInvoiceId"],))
        if ids["backfillSupplierInvoiceId"]:
            cur.execute("DELETE FROM supplier_invoices WHERE id=%s", (ids["backfillSupplierInvoiceId"],))
        if ids["backfillInvoiceId"]:
            cur.execute("DELETE FROM supplier_invoices WHERE warehouse_invoice_id=%s", (ids["backfillInvoiceId"],))
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["backfillInvoiceId"],))
        if ids["nameOnlyInvoiceId"]:
            cur.execute("DELETE FROM warehouse_history WHERE project='Основной склад' AND material=%s", (created.get("nameOnlyMaterialName") or "",))
            cur.execute("DELETE FROM warehouse_main WHERE LOWER(name)=LOWER(%s)", (created.get("nameOnlyMaterialName") or "",))
            cur.execute("DELETE FROM supplier_invoices WHERE warehouse_invoice_id=%s", (ids["nameOnlyInvoiceId"],))
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["nameOnlyInvoiceId"],))
        for invoice_key in ["invoiceId", "manualInvoiceId", "foremanManualInvoiceId", "aliasInvoiceId", "cableInvoiceId"]:
            if ids.get(invoice_key):
                cur.execute("DELETE FROM material_inspection_journal WHERE invoice_id=%s", (ids[invoice_key],))
                cur.execute("DELETE FROM cable_journal WHERE invoice_id=%s", (ids[invoice_key],))
        if ids["invoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["invoiceId"],))
        if ids["manualInvoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["manualInvoiceId"],))
        if ids["foremanManualInvoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["foremanManualInvoiceId"],))
        if ids["aliasInvoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["aliasInvoiceId"],))
        if ids["cableInvoiceId"]:
            cur.execute("DELETE FROM warehouse_invoices WHERE id=%s", (ids["cableInvoiceId"],))
        if ids["deliveryId"]:
            cur.execute("DELETE FROM material_inspection_journal WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM cable_journal WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_claims WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_history WHERE delivery_id=%s", (ids["deliveryId"],))
            cur.execute("DELETE FROM supply_deliveries WHERE id=%s", (ids["deliveryId"],))
        if ids["requestId"]:
            cur.execute("DELETE FROM supply_history WHERE request_id=%s", (ids["requestId"],))
        if ids["offerId"]:
            cur.execute("DELETE FROM supplier_offer_events WHERE offer_id=%s", (ids["offerId"],))
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id=%s", (ids["offerId"],))
            cur.execute("DELETE FROM supplier_offers WHERE id=%s", (ids["offerId"],))
        if ids["withdrawOfferId"]:
            cur.execute("DELETE FROM supplier_offer_events WHERE offer_id=%s", (ids["withdrawOfferId"],))
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id=%s", (ids["withdrawOfferId"],))
            cur.execute("DELETE FROM supplier_offers WHERE id=%s", (ids["withdrawOfferId"],))
        if ids["diagnosticOfferId"]:
            cur.execute("DELETE FROM supplier_offer_events WHERE offer_id=%s", (ids["diagnosticOfferId"],))
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id=%s", (ids["diagnosticOfferId"],))
            cur.execute("DELETE FROM supplier_offers WHERE id=%s", (ids["diagnosticOfferId"],))
        if ids["notificationOutboxId"]:
            cur.execute("DELETE FROM messenger_outbox WHERE id=%s", (ids["notificationOutboxId"],))
        if ids["notificationOfferId"]:
            cur.execute("DELETE FROM supplier_offer_events WHERE offer_id=%s", (ids["notificationOfferId"],))
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id=%s", (ids["notificationOfferId"],))
            cur.execute("DELETE FROM supplier_offers WHERE id=%s", (ids["notificationOfferId"],))
        if ids["notificationRequestId"]:
            cur.execute("DELETE FROM supplier_offer_events WHERE offer_id IN (SELECT id FROM supplier_offers WHERE request_id=%s)", (ids["notificationRequestId"],))
            cur.execute("DELETE FROM supplier_invoices WHERE offer_id IN (SELECT id FROM supplier_offers WHERE request_id=%s)", (ids["notificationRequestId"],))
            cur.execute("DELETE FROM supplier_offers WHERE request_id=%s", (ids["notificationRequestId"],))
            cur.execute("DELETE FROM supply_request_recipients WHERE request_id=%s", (ids["notificationRequestId"],))
            cur.execute("DELETE FROM supply_history WHERE request_id=%s", (ids["notificationRequestId"],))
        if ids["requestId"]:
            cur.execute("DELETE FROM supply_requests WHERE id=%s", (ids["requestId"],))
        if ids["withdrawRequestId"]:
            cur.execute("DELETE FROM supply_requests WHERE id=%s", (ids["withdrawRequestId"],))
        if ids["diagnosticRequestId"]:
            cur.execute("DELETE FROM supply_requests WHERE id=%s", (ids["diagnosticRequestId"],))
        if ids["notificationRequestId"]:
            cur.execute("DELETE FROM supply_requests WHERE id=%s", (ids["notificationRequestId"],))
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
                       AND issued_by IN ('CODEX QA', %s)
                       AND type='приход'
                    """,
                    (material_name, project_name, package or "", TEST_FOREMAN_NAME),
                )
        if ids["supplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["supplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["supplierId"], TEST_SUPPLIER_PREFIX + "%"))
        if ids["supplierDocumentDuplicateSupplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["supplierDocumentDuplicateSupplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["supplierDocumentDuplicateSupplierId"], "CODEX QA ручной дубль поставщика%"))
        if ids["nameOnlyExistingSupplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["nameOnlyExistingSupplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["nameOnlyExistingSupplierId"], TEST_SUPPLIER_PREFIX + "%"))
        if ids["nameOnlyCreatedSupplierId"] and ids["nameOnlyCreatedSupplierId"] != ids["nameOnlyExistingSupplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["nameOnlyCreatedSupplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["nameOnlyCreatedSupplierId"], TEST_SUPPLIER_PREFIX + "%"))
        if ids["diagnosticSupplierId"]:
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["diagnosticSupplierId"], TEST_SUPPLIER_PREFIX + "%"))
        if ids["backfillSupplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["backfillSupplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["backfillSupplierId"], TEST_SUPPLIER_PREFIX + "%"))
        if ids["backfillCreatedSupplierId"] and ids["backfillCreatedSupplierId"] != ids["backfillSupplierId"]:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=%s", (ids["backfillCreatedSupplierId"],))
            cur.execute("DELETE FROM suppliers WHERE id=%s AND name LIKE %s", (ids["backfillCreatedSupplierId"], TEST_SUPPLIER_PREFIX + "%"))
        orphan_supplier_filter = """
            SELECT s.id
              FROM suppliers s
             WHERE s.name LIKE %s
               AND COALESCE(s.source_type,'') IN ('warehouse_invoice','smoke_backfill_supplier','smoke_name_only_supplier')
               AND NOT EXISTS (SELECT 1 FROM warehouse_invoices wi WHERE wi.supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supplier_invoices si WHERE si.supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supplier_offers so WHERE so.supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supply_deliveries sd WHERE sd.supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supply_request_recipients sr WHERE sr.supplier_id=s.id OR sr.target_supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supplier_documents doc WHERE doc.supplier_id=s.id)
               AND NOT EXISTS (SELECT 1 FROM supplier_catalog cat WHERE cat.supplier_id=s.id)
        """
        cur.execute(
            "DELETE FROM supplier_aliases WHERE supplier_id IN (" + orphan_supplier_filter + ")",
            (TEST_SUPPLIER_PREFIX + "%",),
        )
        cur.execute(
            "DELETE FROM suppliers WHERE id IN (" + orphan_supplier_filter + ")",
            (TEST_SUPPLIER_PREFIX + "%",),
        )
        if ids["notificationMessengerAccountId"]:
            cur.execute("DELETE FROM messenger_accounts WHERE id=%s", (ids["notificationMessengerAccountId"],))
        if created.get("supplierEmail"):
            cur.execute("UPDATE users SET active=FALSE WHERE LOWER(email)=LOWER(%s)", (created["supplierEmail"],))
        if created.get("aliasId"):
            cur.execute("UPDATE material_aliases SET active=FALSE, updated_at=NOW() WHERE id=%s", (created["aliasId"],))
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
        supplier_name = test_supplier_name(stamp)
        supplier_email = test_supplier_email(stamp)
        created["supplierId"] = supplier_id
        created["supplierEmail"] = supplier_email
        supplier_token = ensure_supplier_user(supplier_email, supplier_name)
        candidate = select_working_candidate(token, supplier_id, stamp)
        created.update({
            "projectName": candidate["projectName"],
            "workPackage": candidate["workPackage"],
            "materialName": candidate["materialName"],
            "unit": candidate["unit"],
            "quantity": candidate["quantity"],
            "requestId": candidate["requestId"],
        })
        notification_request_id, notification_outbox_id = assert_supply_request_notifications(token, supplier_id, supplier_email, candidate, stamp, created)
        offer_id = create_and_select_offer(token, candidate, supplier_id, supplier_token=supplier_token)
        created["offerId"] = offer_id
        supplier_invoice_id = create_supplier_invoice_for_offer(supplier_token, offer_id, candidate, stamp)
        created["supplierInvoiceId"] = supplier_invoice_id
        delivery_id, invoice_id = ship_and_receive(supplier_token, token, candidate, offer_id, stamp)
        created["deliveryId"] = delivery_id
        created["invoiceId"] = invoice_id
        supplier_invoice_view = assert_supplier_invoice_scope(token, supplier_token, candidate, offer_id, supplier_invoice_id, invoice_id)
        assert_supplier_offer_withdraw_and_resubmit(token, supplier_token, supplier_id, candidate, stamp, created)
        assert_unlinked_supplier_recipient_diagnostics(token, candidate, stamp, created)
        manual_invoice_id, manual_material_name = assert_visible_chain(token, candidate, delivery_id, invoice_id)
        created["manualInvoiceId"] = manual_invoice_id
        created["manualMaterialName"] = manual_material_name
        created["manualQuantity"] = candidate["quantity"]
        cable_invoice_id, cable_material_name, cable_quantity = assert_cable_journal_chain(token, candidate, delivery_id)
        created["cableInvoiceId"] = cable_invoice_id
        created["cableMaterialName"] = cable_material_name
        created["cableQuantity"] = cable_quantity
        created["cableUnit"] = "м"
        foreman_invoice_id, foreman_material_name = assert_foreman_invoice_chain(token, candidate, delivery_id)
        created["foremanManualInvoiceId"] = foreman_invoice_id
        created["foremanManualMaterialName"] = foreman_material_name
        created["foremanManualQuantity"] = candidate["quantity"]
        alias_invoice_id, alias_id, alias_name = assert_alias_invoice_chain(token, candidate, delivery_id)
        created["aliasInvoiceId"] = alias_invoice_id
        created["aliasId"] = alias_id
        created["aliasName"] = alias_name
        created["aliasCanonicalMaterialName"] = candidate["materialName"]
        created["aliasQuantity"] = candidate["quantity"]
        name_only_invoice_id, name_only_supplier_invoice_id, name_only_existing_supplier_id = assert_name_only_warehouse_invoice_does_not_link_supplier(token, candidate, stamp, created)
        backfill_invoice_id, backfill_supplier_invoice_id, _, backfill_created_supplier_id = assert_backfill_uncertain_supplier_review(token, candidate, stamp, created)
        dedupe_supplier_invoice_duplicate_id = assert_supplier_invoice_dedupe(token, backfill_supplier_invoice_id, created)
        document_duplicate_supplier_id, supplier_document_ids = assert_supplier_documents_group_scope(token, supplier_id, stamp, created)
        print(json.dumps({
            "ok": True,
            "projectName": candidate["projectName"],
            "workPackage": candidate["workPackage"],
            "material": candidate["materialName"],
            "quantity": candidate["quantity"],
            "unit": candidate["unit"],
            "requestId": candidate["requestId"],
            "offerId": offer_id,
            "supplierInvoiceId": supplier_invoice_id,
            "deliveryId": delivery_id,
            "invoiceId": invoice_id,
            "supplierWarehouseInvoiceNumber": supplier_invoice_view.get("warehouseInvoiceNumber"),
            "manualInvoiceId": manual_invoice_id,
            "manualMaterial": manual_material_name,
            "cableInvoiceId": cable_invoice_id,
            "cableMaterial": cable_material_name,
            "foremanManualInvoiceId": foreman_invoice_id,
            "foremanManualMaterial": foreman_material_name,
            "aliasInvoiceId": alias_invoice_id,
            "aliasName": alias_name,
            "nameOnlyInvoiceId": name_only_invoice_id,
            "nameOnlySupplierInvoiceId": name_only_supplier_invoice_id,
            "nameOnlyExistingSupplierId": name_only_existing_supplier_id,
            "backfillInvoiceId": backfill_invoice_id,
            "backfillSupplierInvoiceId": backfill_supplier_invoice_id,
            "backfillCreatedSupplierId": backfill_created_supplier_id,
            "dedupeSupplierInvoiceDuplicateId": dedupe_supplier_invoice_duplicate_id,
            "notificationRequestId": notification_request_id,
            "notificationOutboxId": notification_outbox_id,
            "diagnosticRequestId": created.get("diagnosticRequestId"),
            "diagnosticOfferId": created.get("diagnosticOfferId"),
            "diagnosticSupplierId": created.get("diagnosticSupplierId"),
            "supplierDocumentDuplicateSupplierId": document_duplicate_supplier_id,
            "supplierDocumentIds": supplier_document_ids,
            "checked": [
                "positive estimate material selected",
                "supply request passed estimate control",
                "selected supplier received KP request",
                "supplier offer list exposes the addressed offer through recipient and company scope",
                "selected supplier KP request records email status and queues MAX notification",
                "supplier account responded to KP and director selected it",
                "supplier invoice creation is tenant-scoped, idempotent and recorded in offer history",
                "supplier invoice list keeps internal company scope and supplier cross-client identity scope",
                "linked delivery and warehouse document stay in the supplier invoice company",
                "supplier shipment created",
                "receipt created automatic invoice",
                "supplier cabinet sees linked invoice, warehouse receipt, received quantity and receipt items",
                "supplier offer can be withdrawn and resubmitted with history",
                "supplier offer POST reuses and audits the addressed pending offer without creating a duplicate",
                "unlinked supplier is blocked before KP send",
                "legacy invisible supplier recipient exposes link action diagnostics",
                "receipt updated project materials",
                "receipt wrote supply history",
                "manual director object invoice is allowed, controlled and written to object warehouse",
                "material inspection journal follows supply and manual object invoice",
                "cable journal follows cable invoice from project warehouse",
                "foreman object invoice is allowed for assigned project warehouse",
                "foreman main warehouse invoice is blocked",
                "invoice alias rewrites raw supplier material to estimate material",
                "name-only warehouse invoice does not link to existing supplier without strong identity",
                "targeted supplier document backfill marks name-only legacy links as needs_review",
                "supplier accounting dedupe annuls repeated primary document without losing warehouse link",
                "supplier documents endpoint returns documents from the whole duplicate supplier group",
            ],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        raise SystemExit(f"FAIL smoke:supply-chain: {exc}")
    finally:
        cleanup(created)


if __name__ == "__main__":
    main()
