#!/usr/bin/env python3
"""Protected end-to-end smoke for the supply-request approval workflow.

The test creates temporary users and supplier cards, exercises every business
transition through the HTTP API, verifies supplier disclosure, then removes or
disables all temporary fixtures. It must be run manually after deployment.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    import psycopg2
    import psycopg2.extras
except ModuleNotFoundError:  # unit helpers can load without DB driver
    psycopg2 = None


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
DEFAULT_BASE_URL = "https://stroyka26.pro"
CONFIRMATION_PHRASE = "RUN SUPPLY WORKFLOW SMOKE"
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260000
TEMP_EMAIL_DOMAIN = "stroyka.local"
TEMP_EMAIL_PREFIX = "supply-workflow-smoke-"
TEMP_NAME_PREFIX = "CODEX QA supply workflow"
PRIVATE_SUPPLIER_FIELDS = frozenset((
    "createdBy",
    "selectedSuppliers",
    "requestedByRole",
    "requestedById",
    "prorabId",
    "prorabName",
    "prorabConfirmedAt",
    "directorId",
    "directorName",
    "directorApprovedAt",
    "rejectReason",
    "notes",
))
PRIVATE_ITEM_KEYS = frozenset((
    "estimateControl",
    "estimateLineage",
    "plannedSum",
    "plannedWorkSum",
    "price",
    "priceMaterial",
    "priceWork",
    "unitPrice",
    "lineTotal",
    "total",
    "sum",
    "amount",
    "cost",
    "budget",
    "vat",
    "vatAmount",
    "companyId",
    "projectId",
    "estimateId",
    "estimateItemKey",
    "sectionIndex",
    "itemIndex",
    "requestSource",
    "sourceType",
    "sourceId",
    "allocationId",
    "transferPlanId",
))


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name: str, default: str = "") -> str:
    return str(os.getenv(name) or ENV.get(name) or default)


def db_config() -> dict[str, str]:
    return {
        "dbname": env_value("DB_NAME", "stroyka"),
        "user": env_value("DB_USER", "stroyka"),
        "password": env_value("DB_PASSWORD", "password123"),
        "host": env_value("DB_HOST", "localhost"),
        "port": env_value("DB_PORT", "5432"),
    }


def db_conn():
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required to run the live workflow smoke")
    return psycopg2.connect(**db_config())


def validate_confirmation(value: str) -> None:
    if str(value or "") != CONFIRMATION_PHRASE:
        raise ValueError(
            "Smoke requires --confirm '" + CONFIRMATION_PHRASE + "'"
        )


def api_json(
    method: str,
    path: str,
    *,
    base_url: str,
    token: str | None = None,
    data: Any = None,
    headers: Mapping[str, str] | None = None,
    expected: int | Iterable[int] | None = None,
) -> tuple[int, Any]:
    request_headers = {
        "Content-Type": "application/json",
        **dict(headers or {}),
    }
    if token:
        request_headers["Authorization"] = "Bearer " + token
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = int(response.status)
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        text = exc.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"raw": text}
    if expected is not None:
        expected_values = (
            {int(expected)}
            if isinstance(expected, int)
            else {int(value) for value in expected}
        )
        if status not in expected_values:
            raise RuntimeError(
                f"{method} {path}: got {status}, expected "
                f"{sorted(expected_values)}. Body: "
                + json.dumps(parsed, ensure_ascii=False)[:900]
            )
    return status, parsed


def login(base_url: str, email: str, password: str) -> str:
    _, body = api_json(
        "POST",
        "/login",
        base_url=base_url,
        data={"email": email, "password": password},
        expected=200,
    )
    token = body.get("authToken") if isinstance(body, dict) else None
    if not token:
        raise RuntimeError(
            f"Login for {email} did not return authToken: "
            + json.dumps(body, ensure_ascii=False)[:500]
        )
    return str(token)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return (
        f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}"
        f"${salt}${digest}"
    )


def internal_headers(company_id: int) -> dict[str, str]:
    return {
        "X-Company-Mode": "company",
        "X-Company-Id": str(int(company_id)),
    }


def normal_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[.,;:()«»\"'`/\\]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        if isinstance(value, str):
            value = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return default


def base_unit(value: Any) -> str:
    text = normal_text(str(value or "").replace("²", "2").replace("³", "3"))
    compact = text.replace(" ", "")
    aliases = {
        "м": {"м", "мп", "пм", "погм", "метр", "метра", "метров"},
        "м2": {"м2", "квм", "квадратныйметр"},
        "м3": {"м3", "кубм", "кубическийметр"},
        "шт": {"шт", "штук", "штука", "штуки"},
        "компл": {"компл", "комплект", "комплекта", "комплектов"},
        "кг": {"кг", "килограмм", "килограмма", "килограммов"},
        "л": {"л", "литр", "литра", "литров"},
        "т": {"т", "тонна", "тонны", "тонн"},
    }
    for canonical, variants in aliases.items():
        if compact in variants:
            return canonical
    return text or "шт"


def estimate_sections(raw: Any) -> list[Any]:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def looks_material(item: Mapping[str, Any], section_name: str) -> bool:
    raw_type = str(
        item.get("itemType") or item.get("type") or item.get("kind") or ""
    ).casefold()
    if "материал" in raw_type or raw_type in ("material", "materials"):
        return True
    text = normal_text((item.get("name") or "") + " " + section_name)
    markers = (
        "смесь", "штукатур", "шпатлев", "шпаклев", "клей", "краск",
        "грунтов", "кабель", "провод", "гофр", "лист", "профиль",
        "саморез", "кирпич", "бетон", "плит", "труб", "панел",
        "плинтус", "уголок", "арматур", "цемент", "песок",
    )
    strong_work_markers = (
        "монтаж", "установка", "устройство", "демонтаж", "разбор",
        "прокладка", "замена", "подключение", "ремонт", "окраска",
        "кладка", "стяжка",
    )
    looks_like_material = any(marker in text for marker in markers)
    looks_like_work = any(marker in text for marker in strong_work_markers)
    if raw_type in ("work", "works", "работа", "работы"):
        return bool(item.get("isImported")) and looks_like_material and not looks_like_work
    return looks_like_material and not looks_like_work


def reviewer_assignment_sql(project_alias: str = "p") -> str:
    return f"""
        EXISTS (
            SELECT 1
              FROM user_company_roles membership
              JOIN users reviewer
                ON reviewer.id=membership.user_id
               AND COALESCE(reviewer.active,TRUE)=TRUE
             WHERE membership.company_id={project_alias}.company_id
               AND membership.role IN ('прораб','главный_инженер')
               AND COALESCE(membership.active,TRUE)=TRUE
               AND (
                    reviewer.project_id={project_alias}.id
                 OR LOWER(BTRIM(COALESCE(reviewer.project_name,'')))=
                    LOWER(BTRIM({project_alias}.name))
                 OR EXISTS (
                        SELECT 1
                          FROM jsonb_array_elements_text(
                              CASE WHEN jsonb_typeof(membership.assigned_projects)='array'
                                   THEN membership.assigned_projects ELSE '[]'::jsonb END
                          ) assigned(project_name)
                         WHERE LOWER(BTRIM(assigned.project_name))=
                               LOWER(BTRIM({project_alias}.name))
                    )
                 OR EXISTS (
                        SELECT 1
                          FROM jsonb_array_elements_text(
                              CASE WHEN jsonb_typeof(reviewer.assigned_projects)='array'
                                   THEN reviewer.assigned_projects ELSE '[]'::jsonb END
                          ) assigned(project_name)
                         WHERE LOWER(BTRIM(assigned.project_name))=
                               LOWER(BTRIM({project_alias}.name))
                    )
               )
        )
    """


def select_target_project() -> dict[str, Any]:
    requested_company = int(env_value("SUPPLY_WORKFLOW_SMOKE_COMPANY_ID", "0") or 0)
    requested_project = int(env_value("SUPPLY_WORKFLOW_SMOKE_PROJECT_ID", "0") or 0)
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        clauses = [
            "COALESCE(p.archived,FALSE)=FALSE",
            "EXISTS (SELECT 1 FROM estimates e WHERE "
            "(e.project_id=p.id OR (e.project_id IS NULL AND e.project_name=p.name)) "
            "AND COALESCE(e.status,'Активная')='Активная' "
            "AND COALESCE(e.is_template,FALSE)=FALSE "
            "AND COALESCE(e.smeta_type,'Заказчик') IN ('Заказчик','Материалы'))",
            "NOT " + reviewer_assignment_sql("p"),
        ]
        params: list[Any] = []
        if requested_company > 0:
            clauses.append("p.company_id=%s")
            params.append(requested_company)
        if requested_project > 0:
            clauses.append("p.id=%s")
            params.append(requested_project)
        cur.execute(
            "SELECT p.id AS project_id,p.company_id,p.name AS project_name,"
            "c.platform_account_id FROM projects p JOIN companies c ON c.id=p.company_id "
            "WHERE COALESCE(c.active,TRUE)=TRUE AND "
            + " AND ".join(clauses) + " ORDER BY p.id LIMIT 1",
            params,
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                "No active-estimate project without an assigned reviewer was found"
            )
        return dict(row)
    finally:
        cur.close()
        conn.close()


def select_candidate(project: Mapping[str, Any]) -> dict[str, Any]:
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id,name,COALESCE(NULLIF(work_package,''),'Основная') AS work_package,
                   sections_json
              FROM estimates
             WHERE (project_id=%s OR (project_id IS NULL AND project_name=%s))
               AND COALESCE(status,'Активная')='Активная'
               AND COALESCE(is_template,FALSE)=FALSE
               AND COALESCE(smeta_type,'Заказчик') IN ('Заказчик','Материалы')
             ORDER BY id
            """,
            (project["project_id"], project["project_name"]),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    for row in rows:
        package = str(row.get("work_package") or "Основная")
        for section in estimate_sections(row.get("sections_json")):
            if not isinstance(section, dict):
                continue
            section_name = str(section.get("name") or section.get("title") or "")
            for item in section.get("items") or []:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                quantity = as_float(item.get("quantity"))
                if not name or quantity <= 0:
                    continue
                candidate = {
                    "materialName": name,
                    "quantity": round(min(0.001, quantity), 6),
                    "unit": base_unit(item.get("unit") or item.get("measure") or "шт"),
                    "workPackage": package,
                    "estimateId": int(row["id"]),
                }
                if looks_material(item, section_name):
                    return candidate
    raise RuntimeError("Target project has no positive material estimate item for the smoke")


def create_company_user(
    *,
    run_id: str,
    role: str,
    name_suffix: str,
    password: str,
    project: Mapping[str, Any],
    work_package: str,
    assigned_to_project: bool,
) -> dict[str, Any]:
    email = f"{TEMP_EMAIL_PREFIX}{run_id}-{name_suffix}@{TEMP_EMAIL_DOMAIN}"
    name = f"{TEMP_NAME_PREFIX} {name_suffix} {run_id}"
    assigned_projects = [project["project_name"]] if assigned_to_project else []
    assigned_packages = [work_package] if work_package else []
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,company_id,platform_account_id,
                 project_id,project_name,assigned_projects,assigned_packages,active)
            VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE)
            RETURNING id
            """,
            (
                name,
                email,
                hash_password(password),
                role,
                project["company_id"],
                project.get("platform_account_id"),
                project["project_id"] if assigned_to_project else None,
                project["project_name"] if assigned_to_project else "",
                json.dumps(assigned_projects, ensure_ascii=False),
                json.dumps(assigned_packages, ensure_ascii=False),
            ),
        )
        user_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO user_company_roles
                (user_id,platform_account_id,company_id,role,assigned_projects,
                 assigned_packages,active,is_default)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE,TRUE)
            """,
            (
                user_id,
                project.get("platform_account_id"),
                project["company_id"],
                role,
                json.dumps(assigned_projects, ensure_ascii=False),
                json.dumps(assigned_packages, ensure_ascii=False),
            ),
        )
        conn.commit()
        return {"id": user_id, "email": email, "name": name, "role": role}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def create_supplier_user(*, run_id: str, suffix: str, password: str) -> dict[str, Any]:
    email = f"{TEMP_EMAIL_PREFIX}{run_id}-{suffix}@{TEMP_EMAIL_DOMAIN}"
    name = f"{TEMP_NAME_PREFIX} {suffix} {run_id}"
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,assigned_projects,assigned_packages,active)
            VALUES (%s,%s,%s,'поставщик','[]'::jsonb,'[]'::jsonb,TRUE)
            RETURNING id
            """,
            (name, email, hash_password(password)),
        )
        user_id = int(cur.fetchone()["id"])
        conn.commit()
        return {"id": user_id, "email": email, "name": name, "role": "поставщик"}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def deactivate_user(user_id: int) -> None:
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE user_company_roles SET active=FALSE WHERE user_id=%s", (user_id,))
        cur.execute("UPDATE users SET active=FALSE WHERE id=%s", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def count_active_project_reviewers(project: Mapping[str, Any]) -> int:
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM projects p WHERE p.id=%s AND p.company_id=%s AND "
            + reviewer_assignment_sql("p"),
            (project["project_id"], project["company_id"]),
        )
        return int(cur.fetchone()[0])
    finally:
        cur.close()
        conn.close()


def create_supplier_card(
    *,
    base_url: str,
    director_token: str,
    company_id: int,
    supplier_user: Mapping[str, Any],
    serial: int,
) -> int:
    digits = str(serial).zfill(6)[-6:]
    _, body = api_json(
        "POST",
        "/suppliers",
        base_url=base_url,
        token=director_token,
        headers=internal_headers(company_id),
        data={
            "name": supplier_user["name"],
            "email": supplier_user["email"],
            "phone": "+7999" + digits,
            "inn": "7701" + digits,
            "specialization": "Материалы",
            "category": "Материалы",
            "rating": 5,
            "status": "Активный",
        },
        expected=200,
    )
    supplier_id = int(body.get("id") or 0)
    if supplier_id <= 0:
        raise RuntimeError("Supplier creation did not return id")
    return supplier_id


def request_list(
    *,
    base_url: str,
    token: str,
    company_id: int | None,
) -> list[dict[str, Any]]:
    _, body = api_json(
        "GET",
        "/supply-requests",
        base_url=base_url,
        token=token,
        headers=internal_headers(company_id) if company_id else None,
        expected=200,
    )
    if not isinstance(body, list):
        raise RuntimeError("GET /supply-requests returned a non-list response")
    return [dict(row) for row in body if isinstance(row, dict)]


def request_by_id(rows: Iterable[Mapping[str, Any]], request_id: int):
    return next(
        (dict(row) for row in rows if int(row.get("id") or 0) == int(request_id)),
        None,
    )


def assert_internal_request_status(
    *,
    base_url: str,
    token: str,
    company_id: int,
    request_id: int,
    expected_status: str,
    actor_label: str,
) -> dict[str, Any]:
    row = request_by_id(
        request_list(
            base_url=base_url,
            token=token,
            company_id=company_id,
        ),
        request_id,
    )
    if not row:
        raise RuntimeError(actor_label + " cannot see request " + str(request_id))
    if row.get("status") != expected_status:
        raise RuntimeError(
            actor_label + " sees status " + repr(row.get("status"))
            + ", expected " + repr(expected_status)
        )
    return row


def parse_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def find_private_item_key(value: Any, path: str = "items") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in PRIVATE_ITEM_KEYS or key_text.startswith("_"):
                return path + "." + key_text
            nested = find_private_item_key(item, path + "." + key_text)
            if nested:
                return nested
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested = find_private_item_key(item, f"{path}[{index}]")
            if nested:
                return nested
    return None


def assert_supplier_request_safe(row: Mapping[str, Any]) -> None:
    private = sorted(set(row) & PRIVATE_SUPPLIER_FIELDS)
    if private:
        raise AssertionError("Supplier response leaked fields: " + ", ".join(private))
    private_item = find_private_item_key(parse_items(row.get("itemsJson")))
    if private_item:
        raise AssertionError("Supplier response leaked item field: " + private_item)
    for required in ("id", "project", "status", "itemsJson"):
        if required not in row:
            raise AssertionError("Supplier response omitted required field: " + required)


def create_request(
    *,
    base_url: str,
    master: Mapping[str, Any],
    master_token: str,
    project: Mapping[str, Any],
    candidate: Mapping[str, Any],
    note: str,
) -> dict[str, Any]:
    _, body = api_json(
        "POST",
        "/supply-requests",
        base_url=base_url,
        token=master_token,
        headers=internal_headers(project["company_id"]),
        data={
            "companyId": project["company_id"],
            "projectId": project["project_id"],
            "project": project["project_name"],
            "materialName": candidate["materialName"],
            "quantity": candidate["quantity"],
            "unit": candidate["unit"],
            "workPackage": candidate["workPackage"],
            "createdBy": master["name"],
            "requestedByRole": "мастер",
            "requestedById": master["id"],
            "date": dt.date.today().isoformat(),
            "notes": note,
            "urgency": "обычная",
            "category": "Материалы",
            "selectedSuppliers": [],
            "items": [{
                "materialName": candidate["materialName"],
                "quantity": candidate["quantity"],
                "unit": candidate["unit"],
                "workPackage": candidate["workPackage"],
            }],
        },
        expected=200,
    )
    request_id = int(body.get("id") or 0)
    if request_id <= 0 or body.get("status") != "Новая":
        raise RuntimeError("Master request was not created in status Новая")
    return dict(body)


def update_request_action(
    *,
    base_url: str,
    request_id: int,
    actor: Mapping[str, Any],
    token: str,
    company_id: int,
    action: str,
    expected: int | Iterable[int],
) -> tuple[int, Any]:
    return api_json(
        "PUT",
        f"/supply-requests/{request_id}",
        base_url=base_url,
        token=token,
        headers=internal_headers(company_id),
        data={
            "action": action,
            "userId": actor["id"],
            "userName": actor["name"],
            "companyId": company_id,
        },
        expected=expected,
    )


def dispatch_request(
    *,
    base_url: str,
    request_id: int,
    supply_token: str,
    company_id: int,
    supplier_id: int,
    expected: int | Iterable[int],
) -> tuple[int, Any]:
    return api_json(
        "POST",
        f"/supply-requests/{request_id}/request-kp",
        base_url=base_url,
        token=supply_token,
        headers=internal_headers(company_id),
        data={
            "supplierIds": [supplier_id],
            "aiRecommendedIds": [],
            "companyId": company_id,
        },
        expected=expected,
    )


def assert_supplier_visibility(
    *,
    base_url: str,
    request_id: int,
    addressed_token: str,
    unaddressed_token: str,
) -> dict[str, Any]:
    addressed = request_by_id(
        request_list(base_url=base_url, token=addressed_token, company_id=None),
        request_id,
    )
    if not addressed:
        raise RuntimeError("Addressed supplier cannot see the dispatched request")
    assert_supplier_request_safe(addressed)
    if addressed.get("status") != "КП запрошены":
        raise RuntimeError("Supplier received a request in an unexpected status")
    hidden = request_by_id(
        request_list(base_url=base_url, token=unaddressed_token, company_id=None),
        request_id,
    )
    if hidden:
        raise RuntimeError("Unaddressed supplier can see another supplier's request")
    return addressed


def respond_to_offer(
    *,
    base_url: str,
    request_id: int,
    supplier_token: str,
    supply_token: str,
    company_id: int,
    candidate: Mapping[str, Any],
) -> int:
    _, supplier_offers = api_json(
        "GET",
        "/supplier-offers",
        base_url=base_url,
        token=supplier_token,
        expected=200,
    )
    offer = next(
        (
            row for row in supplier_offers
            if int(row.get("requestId") or 0) == int(request_id)
        ),
        None,
    )
    if not offer:
        raise RuntimeError("Addressed supplier cannot see the offer request")
    offer_id = int(offer.get("id") or 0)
    price = 123.45
    total = round(price * as_float(candidate["quantity"]), 2)
    _, responded = api_json(
        "PUT",
        f"/supplier-offers/{offer_id}",
        base_url=base_url,
        token=supplier_token,
        data={
            "action": "respond",
            "pricePerUnit": price,
            "totalPrice": total,
            "deliveryDays": 2,
            "paymentTerms": "Постоплата",
            "vatIncluded": True,
            "supplierMessage": TEMP_NAME_PREFIX,
            "itemsKp": [{
                "materialName": candidate["materialName"],
                "quantity": candidate["quantity"],
                "unit": candidate["unit"],
                "workPackage": candidate["workPackage"],
                "pricePerUnit": price,
                "totalPrice": total,
                "deliveryDays": 2,
            }],
        },
        expected=200,
    )
    if responded.get("status") != "Получено":
        raise RuntimeError("Supplier offer did not move to status Получено")
    _, internal_offers = api_json(
        "GET",
        "/supplier-offers",
        base_url=base_url,
        token=supply_token,
        headers=internal_headers(company_id),
        expected=200,
    )
    internal = next(
        (row for row in internal_offers if int(row.get("id") or 0) == offer_id),
        None,
    )
    if not internal or internal.get("status") != "Получено":
        raise RuntimeError("Supply specialist cannot see the supplier response")
    return offer_id


def run_assigned_reviewer_path(ctx: dict[str, Any]) -> dict[str, int]:
    project = ctx["project"]
    candidate = ctx["candidate"]
    request = create_request(
        base_url=ctx["base_url"],
        master=ctx["master"],
        master_token=ctx["master_token"],
        project=project,
        candidate=candidate,
        note=TEMP_NAME_PREFIX + " assigned reviewer " + ctx["run_id"],
    )
    request_id = int(request["id"])
    ctx["fixtures"]["request_ids"].append(request_id)

    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["master_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Новая",
        actor_label="Master",
    )
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["foreman_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Новая",
        actor_label="Assigned foreman",
    )
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Новая",
        actor_label="Director",
    )

    update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["master"],
        token=ctx["master_token"],
        company_id=project["company_id"],
        action="confirm_prorab",
        expected=403,
    )
    update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["director"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        action="confirm_prorab",
        expected=409,
    )
    dispatch_request(
        base_url=ctx["base_url"],
        request_id=request_id,
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        supplier_id=ctx["addressed_supplier_id"],
        expected=400,
    )

    _, confirmed = update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["foreman"],
        token=ctx["foreman_token"],
        company_id=project["company_id"],
        action="confirm_prorab",
        expected=200,
    )
    if confirmed.get("status") != "Подтверждена прорабом":
        raise RuntimeError("Foreman confirmation did not advance the request")
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Подтверждена прорабом",
        actor_label="Director",
    )

    _, approved = update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["director"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        action="approve_director",
        expected=200,
    )
    if approved.get("status") != "Утверждена":
        raise RuntimeError("Director approval did not advance the request")
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["supply_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Утверждена",
        actor_label="Supply specialist",
    )

    _, dispatched = dispatch_request(
        base_url=ctx["base_url"],
        request_id=request_id,
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        supplier_id=ctx["addressed_supplier_id"],
        expected=200,
    )
    if not dispatched.get("ok"):
        raise RuntimeError("Supply specialist did not dispatch the approved request")

    assert_supplier_visibility(
        base_url=ctx["base_url"],
        request_id=request_id,
        addressed_token=ctx["addressed_supplier_token"],
        unaddressed_token=ctx["unaddressed_supplier_token"],
    )
    offer_id = respond_to_offer(
        base_url=ctx["base_url"],
        request_id=request_id,
        supplier_token=ctx["addressed_supplier_token"],
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        candidate=candidate,
    )
    return {"request_id": request_id, "offer_id": offer_id}


def run_director_fallback_path(ctx: dict[str, Any]) -> dict[str, int]:
    deactivate_user(ctx["foreman"]["id"])
    if count_active_project_reviewers(ctx["project"]) != 0:
        raise RuntimeError("Fallback project still has an active assigned reviewer")

    project = ctx["project"]
    candidate = ctx["candidate"]
    request = create_request(
        base_url=ctx["base_url"],
        master=ctx["master"],
        master_token=ctx["master_token"],
        project=project,
        candidate=candidate,
        note=TEMP_NAME_PREFIX + " director fallback " + ctx["run_id"],
    )
    request_id = int(request["id"])
    ctx["fixtures"]["request_ids"].append(request_id)

    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Новая",
        actor_label="Director fallback",
    )

    dispatch_request(
        base_url=ctx["base_url"],
        request_id=request_id,
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        supplier_id=ctx["addressed_supplier_id"],
        expected=400,
    )

    _, confirmed = update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["director"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        action="confirm_prorab",
        expected=200,
    )
    if confirmed.get("status") != "Подтверждена прорабом":
        raise RuntimeError("Director fallback confirmation did not advance the request")
    if int(confirmed.get("prorabId") or 0) != int(ctx["director"]["id"]):
        raise RuntimeError("Fallback confirmation did not record the director actor")
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["supply_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Подтверждена прорабом",
        actor_label="Supply specialist",
    )

    dispatch_request(
        base_url=ctx["base_url"],
        request_id=request_id,
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        supplier_id=ctx["addressed_supplier_id"],
        expected=400,
    )

    _, approved = update_request_action(
        base_url=ctx["base_url"],
        request_id=request_id,
        actor=ctx["director"],
        token=ctx["director_token"],
        company_id=project["company_id"],
        action="approve_director",
        expected=200,
    )
    if approved.get("status") != "Утверждена":
        raise RuntimeError("Separate director approval did not advance fallback request")
    assert_internal_request_status(
        base_url=ctx["base_url"],
        token=ctx["supply_token"],
        company_id=project["company_id"],
        request_id=request_id,
        expected_status="Утверждена",
        actor_label="Supply specialist",
    )

    dispatch_request(
        base_url=ctx["base_url"],
        request_id=request_id,
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        supplier_id=ctx["addressed_supplier_id"],
        expected=200,
    )
    assert_supplier_visibility(
        base_url=ctx["base_url"],
        request_id=request_id,
        addressed_token=ctx["addressed_supplier_token"],
        unaddressed_token=ctx["unaddressed_supplier_token"],
    )
    offer_id = respond_to_offer(
        base_url=ctx["base_url"],
        request_id=request_id,
        supplier_token=ctx["addressed_supplier_token"],
        supply_token=ctx["supply_token"],
        company_id=project["company_id"],
        candidate=candidate,
    )
    return {"request_id": request_id, "offer_id": offer_id}


def cleanup(fixtures: dict[str, Any]) -> None:
    conn = None
    try:
        conn = db_conn()
        conn.autocommit = False
        cur = conn.cursor()
        request_ids = sorted({int(value) for value in fixtures.get("request_ids", []) if int(value) > 0})
        supplier_ids = sorted({int(value) for value in fixtures.get("supplier_ids", []) if int(value) > 0})
        user_ids = sorted({int(value) for value in fixtures.get("user_ids", []) if int(value) > 0})

        if request_ids:
            cur.execute(
                "DELETE FROM messenger_outbox WHERE entity_type='supply_request' AND entity_id=ANY(%s)",
                (request_ids,),
            )
            cur.execute(
                "DELETE FROM supplier_offer_events WHERE offer_id IN "
                "(SELECT id FROM supplier_offers WHERE request_id=ANY(%s))",
                (request_ids,),
            )
            cur.execute(
                "DELETE FROM supplier_invoices WHERE offer_id IN "
                "(SELECT id FROM supplier_offers WHERE request_id=ANY(%s))",
                (request_ids,),
            )
            cur.execute("DELETE FROM supplier_offers WHERE request_id=ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_request_recipients WHERE request_id=ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_history WHERE request_id=ANY(%s)", (request_ids,))
            cur.execute("DELETE FROM supply_requests WHERE id=ANY(%s)", (request_ids,))

        if supplier_ids:
            cur.execute("DELETE FROM supplier_aliases WHERE supplier_id=ANY(%s)", (supplier_ids,))
            cur.execute("DELETE FROM supplier_documents WHERE supplier_id=ANY(%s)", (supplier_ids,))
            cur.execute("DELETE FROM supplier_catalog WHERE supplier_id=ANY(%s)", (supplier_ids,))
            cur.execute("DELETE FROM suppliers WHERE id=ANY(%s)", (supplier_ids,))

        if user_ids:
            cur.execute("UPDATE user_company_roles SET active=FALSE WHERE user_id=ANY(%s)", (user_ids,))
            cur.execute("UPDATE users SET active=FALSE WHERE id=ANY(%s)", (user_ids,))

        conn.commit()
        cur.close()
        print("cleanup: removed workflow requests/suppliers and disabled temp users")
    except Exception as exc:
        if conn:
            conn.rollback()
        print("cleanup warning: " + str(exc), file=sys.stderr)
    finally:
        if conn:
            conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Protected E2E smoke for supply request approval and supplier visibility",
    )
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--base-url",
        default=env_value("BASE_URL", DEFAULT_BASE_URL),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        validate_confirmation(args.confirm)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    run_id = uuid.uuid4().hex[:10]
    password = "SupplyWorkflowSmoke-" + secrets.token_urlsafe(18)
    fixtures: dict[str, Any] = {
        "request_ids": [],
        "supplier_ids": [],
        "user_ids": [],
    }

    try:
        project = select_target_project()
        candidate = select_candidate(project)
        print(
            "target:",
            json.dumps({**project, **candidate}, ensure_ascii=False, default=str),
        )

        director = create_company_user(
            run_id=run_id,
            role="директор",
            name_suffix="director",
            password=password,
            project=project,
            work_package=candidate["workPackage"],
            assigned_to_project=False,
        )
        fixtures["user_ids"].append(director["id"])
        master = create_company_user(
            run_id=run_id,
            role="мастер",
            name_suffix="master",
            password=password,
            project=project,
            work_package=candidate["workPackage"],
            assigned_to_project=True,
        )
        fixtures["user_ids"].append(master["id"])
        foreman = create_company_user(
            run_id=run_id,
            role="прораб",
            name_suffix="foreman",
            password=password,
            project=project,
            work_package=candidate["workPackage"],
            assigned_to_project=True,
        )
        fixtures["user_ids"].append(foreman["id"])
        supply = create_company_user(
            run_id=run_id,
            role="снабженец",
            name_suffix="supply",
            password=password,
            project=project,
            work_package=candidate["workPackage"],
            assigned_to_project=True,
        )
        fixtures["user_ids"].append(supply["id"])
        addressed_supplier = create_supplier_user(
            run_id=run_id,
            suffix="supplier-a",
            password=password,
        )
        fixtures["user_ids"].append(addressed_supplier["id"])
        unaddressed_supplier = create_supplier_user(
            run_id=run_id,
            suffix="supplier-b",
            password=password,
        )
        fixtures["user_ids"].append(unaddressed_supplier["id"])

        base_url = args.base_url.rstrip("/")
        director_token = login(base_url, director["email"], password)
        master_token = login(base_url, master["email"], password)
        foreman_token = login(base_url, foreman["email"], password)
        supply_token = login(base_url, supply["email"], password)
        addressed_supplier_token = login(
            base_url,
            addressed_supplier["email"],
            password,
        )
        unaddressed_supplier_token = login(
            base_url,
            unaddressed_supplier["email"],
            password,
        )

        serial = int(
            hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12],
            16,
        ) % 900000 + 100000
        addressed_supplier_id = create_supplier_card(
            base_url=base_url,
            director_token=director_token,
            company_id=project["company_id"],
            supplier_user=addressed_supplier,
            serial=serial,
        )
        fixtures["supplier_ids"].append(addressed_supplier_id)
        unaddressed_supplier_id = create_supplier_card(
            base_url=base_url,
            director_token=director_token,
            company_id=project["company_id"],
            supplier_user=unaddressed_supplier,
            serial=(serial + 1) % 1000000,
        )
        fixtures["supplier_ids"].append(unaddressed_supplier_id)

        ctx = {
            "base_url": base_url,
            "run_id": run_id,
            "fixtures": fixtures,
            "project": project,
            "candidate": candidate,
            "director": director,
            "director_token": director_token,
            "master": master,
            "master_token": master_token,
            "foreman": foreman,
            "foreman_token": foreman_token,
            "supply": supply,
            "supply_token": supply_token,
            "addressed_supplier_id": addressed_supplier_id,
            "addressed_supplier_token": addressed_supplier_token,
            "unaddressed_supplier_id": unaddressed_supplier_id,
            "unaddressed_supplier_token": unaddressed_supplier_token,
        }

        if count_active_project_reviewers(project) < 1:
            raise RuntimeError("Temporary assigned foreman was not detected")

        assigned_result = run_assigned_reviewer_path(ctx)
        print("OK assigned reviewer path", json.dumps(assigned_result))

        fallback_result = run_director_fallback_path(ctx)
        print("OK director fallback path", json.dumps(fallback_result))

        visible_to_other = request_list(
            base_url=base_url,
            token=unaddressed_supplier_token,
            company_id=None,
        )
        leaked_ids = {
            int(row.get("id") or 0)
            for row in visible_to_other
            if int(row.get("id") or 0) in set(fixtures["request_ids"])
        }
        if leaked_ids:
            raise RuntimeError(
                "Unaddressed supplier leaked workflow requests: "
                + repr(sorted(leaked_ids))
            )

        print(
            "SUPPLY_WORKFLOW_E2E_OK",
            json.dumps(
                {
                    "companyId": project["company_id"],
                    "projectId": project["project_id"],
                    "assignedRequestId": assigned_result["request_id"],
                    "fallbackRequestId": fallback_result["request_id"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    finally:
        cleanup(fixtures)


if __name__ == "__main__":
    main()
