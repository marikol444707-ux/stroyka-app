#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
TEST_EMAIL = os.getenv("WORK_DOC_SMOKE_USER_EMAIL", "work-doc-smoke@stroyka.local")
TEST_NAME = os.getenv("WORK_DOC_SMOKE_USER_NAME", "CODEX QA Исполнитель ЖПР")
TEST_ROLE = os.getenv("WORK_DOC_SMOKE_USER_ROLE", "субподрядчик")
TEST_PACKAGE = os.getenv("WORK_DOC_SMOKE_PACKAGE", "CODEX QA D")
TEST_DESCRIPTION_PREFIX = "CODEX QA ЖПР АОСР акт"


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


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def api_json(method, path, token=None, data=None, expected=None):
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise SystemExit(f"FAIL {method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
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


def db_conn():
    return psycopg2.connect(**db_config())


def prepare_temp_worker():
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    project_name = os.getenv("WORK_DOC_SMOKE_PROJECT", "").strip()
    if project_name:
        cur.execute("SELECT id, name FROM projects WHERE name=%s LIMIT 1", (project_name,))
    else:
        cur.execute("SELECT id, name FROM projects WHERE COALESCE(archived,FALSE)=FALSE ORDER BY id LIMIT 1")
    project = cur.fetchone()
    if not project:
        cur.close()
        conn.close()
        raise SystemExit("FAIL: нет активного объекта для smoke ЖПР/АОСР/акта")

    password = secrets.token_urlsafe(12)
    assigned_projects = json.dumps([project["name"]], ensure_ascii=False)
    assigned_packages = json.dumps([TEST_PACKAGE], ensure_ascii=False)
    password_hash = hash_password(password)
    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (TEST_EMAIL,))
    existing = cur.fetchone()
    if existing:
        cur.execute(
            """
            UPDATE users
               SET name=%s,
                   email=%s,
                   password=%s,
                   role=%s,
                   project_id=%s,
                   project_name=%s,
                   assigned_projects=%s::jsonb,
                   assigned_packages=%s::jsonb,
                   active=TRUE,
                   failed_login_count=0,
                   locked_until=NULL
             WHERE id=%s
            """,
            (
                TEST_NAME,
                TEST_EMAIL,
                password_hash,
                TEST_ROLE,
                project["id"],
                project["name"],
                assigned_projects,
                assigned_packages,
                existing["id"],
            ),
        )
        user_id = existing["id"]
    else:
        cur.execute(
            """
            INSERT INTO users
                (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,active)
            VALUES
                (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE)
            RETURNING id
            """,
            (
                TEST_NAME,
                TEST_EMAIL,
                password_hash,
                TEST_ROLE,
                project["id"],
                project["name"],
                assigned_projects,
                assigned_packages,
            ),
        )
        user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": user_id, "name": TEST_NAME, "email": TEST_EMAIL, "password": password, "projectName": project["name"], "projectId": project["id"]}


def cleanup(created):
    conn = None
    try:
        conn = db_conn()
        conn.autocommit = False
        cur = conn.cursor()
        payment_id = created.get("projectPaymentId")
        interim_act_ids = [
            value for value in (
                created.get("finalInterimActId"),
                created.get("dailyInterimActId"),
                created.get("interimActId"),
            )
            if value
        ]
        work_journal_id = created.get("workJournalId")
        contract_id = created.get("contractId")
        contract_item_id = created.get("contractItemId")

        if payment_id:
            cur.execute("DELETE FROM project_payments WHERE id=%s", (payment_id,))
        if interim_act_ids:
            cur.execute("DELETE FROM interim_acts WHERE id = ANY(%s)", (interim_act_ids,))
        if work_journal_id:
            cur.execute("DELETE FROM hidden_works_acts WHERE work_journal_id=%s", (work_journal_id,))
            cur.execute("DELETE FROM room_works WHERE work_journal_id=%s", (work_journal_id,))
            cur.execute("DELETE FROM piecework WHERE work_journal_id=%s", (work_journal_id,))
            cur.execute("DELETE FROM work_journal WHERE id=%s", (work_journal_id,))
        if contract_item_id:
            cur.execute("DELETE FROM brigade_contract_items WHERE id=%s", (contract_item_id,))
        if contract_id:
            cur.execute("DELETE FROM brigade_contract_items WHERE contract_id=%s", (contract_id,))
            cur.execute("DELETE FROM brigade_contracts WHERE id=%s", (contract_id,))
        conn.commit()
        cur.close()
        print("cleanup: removed work-doc smoke rows", json.dumps(created, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def find_row(rows, predicate):
    for row in rows or []:
        if predicate(row):
            return row
    return None


def main():
    director_email = require_env("SMOKE_EMAIL")
    director_password = require_env("SMOKE_PASSWORD")
    director_token = login(director_email, director_password)
    worker = prepare_temp_worker()
    worker_token = login(worker["email"], worker["password"])

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    stamp = now.strftime("%Y%m%d%H%M%S")
    description = f"{TEST_DESCRIPTION_PREFIX} {stamp}"
    room_name = f"CODEX QA помещение {stamp}"
    photo_url = f"/uploads/codex-work-doc-{stamp}.jpg"
    qty = 2.0
    price_brigade = 111.0
    total = qty * price_brigade
    created = {}

    try:
        _, contract = api_json(
            "POST",
            "/brigade-contracts",
            token=director_token,
            data={
                "projectId": worker["projectId"],
                "projectName": worker["projectName"],
                "workPackage": TEST_PACKAGE,
                "brigadeName": worker["name"],
                "contractorType": "Субподрядчик",
                "contractorId": worker["id"],
                "totalAmount": total,
                "status": "Активен",
                "notes": f"CODEX QA smoke {stamp}",
            },
            expected=200,
        )
        created["contractId"] = contract.get("id")
        if not created["contractId"]:
            raise SystemExit(f"FAIL contract create: {contract}")

        _, item = api_json(
            "POST",
            "/brigade-contract-items",
            token=director_token,
            data={
                "contractId": created["contractId"],
                "estimateSection": "CODEX QA",
                "description": description,
                "name": description,
                "workPackage": TEST_PACKAGE,
                "unit": "м2",
                "quantity": 5,
                "priceSmeta": 333,
                "priceBrigade": price_brigade,
                "doneQuantity": 0,
            },
            expected=200,
        )
        created["contractItemId"] = item.get("id")
        if not created["contractItemId"]:
            raise SystemExit(f"FAIL contract item create: {item}")

        missing_room_status, missing_room_body = api_json(
            "POST",
            "/work-journal",
            token=worker_token,
            data={
                "masterId": worker["id"],
                "masterName": worker["name"],
                "project": worker["projectName"],
                "description": description,
                "unit": "м2",
                "quantity": qty,
                "date": today,
                "comment": f"CODEX QA smoke no room {stamp}",
                "hiddenWork": True,
                "qualityStatus": "На проверке",
                "workPackage": TEST_PACKAGE,
                "contractItemId": created["contractItemId"],
            },
        )
        if missing_room_status != 400:
            raise SystemExit(f"FAIL work journal room guard: got {missing_room_status}, expected 400. Body: {missing_room_body}")

        _, work = api_json(
            "POST",
            "/work-journal",
            token=worker_token,
            data={
                "masterId": worker["id"],
                "masterName": worker["name"],
                "project": worker["projectName"],
                "description": description,
                "unit": "м2",
                "quantity": qty,
                "date": today,
                "comment": f"CODEX QA smoke {stamp}",
                "photoUrl": photo_url,
                "hiddenWork": True,
                "qualityStatus": "На проверке",
                "workPackage": TEST_PACKAGE,
                "roomName": room_name,
                "surface": "Стены",
                "contractItemId": created["contractItemId"],
            },
            expected=200,
        )
        created["workJournalId"] = work.get("id")
        if not created["workJournalId"]:
            raise SystemExit(f"FAIL work journal create: {work}")
        if abs(float(work.get("executionTotal") or work.get("total") or 0) - total) > 0.01:
            raise SystemExit(f"FAIL work execution total: {work}")

        duplicate_status, duplicate_body = api_json(
            "POST",
            "/work-journal",
            token=worker_token,
            data={
                "masterId": worker["id"],
                "masterName": worker["name"],
                "project": worker["projectName"],
                "description": description,
                "unit": "м2",
                "quantity": 1,
                "date": today,
                "comment": f"CODEX QA smoke duplicate {stamp}",
                "hiddenWork": True,
                "qualityStatus": "На проверке",
                "workPackage": TEST_PACKAGE,
                "roomName": room_name,
                "surface": "Стены",
                "contractItemId": created["contractItemId"],
            },
        )
        if duplicate_status != 409:
            raise SystemExit(f"FAIL work journal duplicate guard: got {duplicate_status}, expected 409. Body: {duplicate_body}")

        _, confirm_body = api_json(
            "PUT",
            f"/work-journal/{created['workJournalId']}",
            token=director_token,
            data={"status": "Подтверждено", "confirmedBy": "Codex smoke", "confirmedAt": today},
            expected=200,
        )
        _, journal_rows = api_json("GET", "/work-journal", token=director_token, expected=200)
        journal_row = find_row(journal_rows, lambda row: str(row.get("id")) == str(created["workJournalId"]))
        if not journal_row or journal_row.get("status") != "Подтверждено":
            raise SystemExit(f"FAIL work journal confirm: {journal_row}")

        query = urllib.parse.urlencode({"project_name": worker["projectName"]})
        _, hidden_rows = api_json("GET", f"/hidden-works-acts?{query}", token=director_token, expected=200)
        hidden_row = find_row(hidden_rows, lambda row: str(row.get("workJournalId")) == str(created["workJournalId"]))
        if not hidden_row:
            raise SystemExit("FAIL hidden works: АОСР по ЖПР не найден")
        if hidden_row.get("workPackage") != TEST_PACKAGE:
            raise SystemExit(f"FAIL hidden works package: {hidden_row}")
        created["hiddenWorksActId"] = hidden_row.get("id")

        _, interim_rows = api_json("GET", "/interim-acts", token=director_token, expected=200)
        expected_daily_id = confirm_body.get("dailyActId")
        interim = find_row(
            interim_rows,
            lambda row: (
                str(row.get("id")) == str(expected_daily_id)
                or (
                    row.get("sourceType") == "daily_work"
                    and row.get("project") == worker["projectName"]
                    and row.get("workPackage") == TEST_PACKAGE
                    and row.get("periodStart") == today
                    and row.get("periodEnd") == today
                    and str(row.get("masterId")) == str(worker["id"])
                    and str(created["workJournalId"]) in str(row.get("workJournalIds") or "")
                )
            ),
        )
        if not interim:
            raise SystemExit(f"FAIL daily interim act auto-create: dailyActId={expected_daily_id}, rows={interim_rows[:3]}")
        created["dailyInterimActId"] = interim.get("id")
        if not created["dailyInterimActId"]:
            raise SystemExit(f"FAIL daily interim act id: {interim}")
        if interim.get("sourceType") != "daily_work":
            raise SystemExit(f"FAIL daily interim act sourceType: {interim}")
        if abs(float(interim.get("totalAmount") or 0) - total) > 0.01:
            raise SystemExit(f"FAIL daily interim act total: {interim}")
        if str(created["workJournalId"]) not in str(interim.get("workJournalIds") or ""):
            raise SystemExit(f"FAIL daily interim act workJournalIds: {interim}")
        if photo_url not in str(interim.get("photoUrls") or ""):
            raise SystemExit(f"FAIL daily interim act photoUrls: {interim}")

        daily_pay_status, daily_pay_body = api_json(
            "POST",
            f"/interim-acts/{created['dailyInterimActId']}/pay",
            token=director_token,
            data={"amount": total, "paidBy": "Codex smoke", "paidDate": today, "note": f"CODEX QA payment {stamp}"},
        )
        if daily_pay_status != 400:
            raise SystemExit(f"FAIL daily interim act payment guard: got {daily_pay_status}, expected 400. Body: {daily_pay_body}")

        daily_update_status, daily_update_body = api_json(
            "PUT",
            f"/interim-acts/{created['dailyInterimActId']}",
            token=director_token,
            data={"status": "Оплачен", "paidAmount": total},
        )
        if daily_update_status != 400:
            raise SystemExit(f"FAIL daily interim act update guard: got {daily_update_status}, expected 400. Body: {daily_update_body}")

        _, final_act = api_json(
            "POST",
            "/interim-acts",
            token=director_token,
            data={
                "masterId": worker["id"],
                "masterName": worker["name"],
                "project": worker["projectName"],
                "workPackage": TEST_PACKAGE,
                "periodStart": today,
                "periodEnd": today,
                "totalAmount": total,
                "paidAmount": 0,
                "contractId": created["contractId"],
                "workJournalIds": [created["workJournalId"]],
            },
            expected=200,
        )
        created["finalInterimActId"] = final_act.get("id")
        if not created["finalInterimActId"]:
            raise SystemExit(f"FAIL final interim act create: {final_act}")
        if str(created["workJournalId"]) not in str(final_act.get("workJournalIds") or ""):
            raise SystemExit(f"FAIL final interim act workJournalIds: {final_act}")

        _, pay = api_json(
            "POST",
            f"/interim-acts/{created['finalInterimActId']}/pay",
            token=director_token,
            data={"amount": total, "paidBy": "Codex smoke", "paidDate": today, "note": f"CODEX QA payment {stamp}"},
            expected=200,
        )
        created["projectPaymentId"] = pay.get("projectPaymentId")
        if not created["projectPaymentId"]:
            raise SystemExit(f"FAIL interim act pay: {pay}")

        _, payments = api_json("GET", f"/project-payments?{query}", token=director_token, expected=200)
        payment_row = find_row(payments, lambda row: str(row.get("id")) == str(created["projectPaymentId"]))
        if not payment_row:
            raise SystemExit("FAIL project payment: платеж из оплаты акта не найден")
        if abs(float(payment_row.get("amount") or 0) + total) > 0.01:
            raise SystemExit(f"FAIL project payment amount: {payment_row}")

        print(json.dumps({
            "ok": True,
            "projectName": worker["projectName"],
            "worker": worker["email"],
            "workPackage": TEST_PACKAGE,
            "workJournalId": created["workJournalId"],
            "hiddenWorksActId": created.get("hiddenWorksActId"),
            "dailyInterimActId": created["dailyInterimActId"],
            "finalInterimActId": created["finalInterimActId"],
            "projectPaymentId": created["projectPaymentId"],
            "checked": [
                "temporary worker access",
                "brigade contract and line",
                "worker cannot create work_journal without room",
                "worker creates work_journal with room",
                "worker cannot duplicate same work in same room",
                "director confirms work_journal",
                "hidden_works_act auto-created from hidden work",
                "daily interim_act auto-created from confirmed work_journal with photo",
                "daily interim_act payment is blocked as control package",
                "daily interim_act paid status update is blocked as control package",
                "final contractor interim_act can include daily work_journal",
                "final interim_act payment creates project payment",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(created)


if __name__ == "__main__":
    main()
