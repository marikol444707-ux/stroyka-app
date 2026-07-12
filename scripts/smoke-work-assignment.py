#!/usr/bin/env python3
import base64
import copy
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:8]
PREFIX = f"CODEX WORK ASSIGNMENT SMOKE {RUN_ID}"
PROJECT_NAME = f"{PREFIX} Project"
WORKER_EMAIL = f"work-assignment-worker-{RUN_ID}@stroyka.local"
WORKER_NAME = f"{PREFIX} Master"
DIRECTOR_EMAIL = f"work-assignment-director-{RUN_ID}@stroyka.local"
DIRECTOR_NAME = f"{PREFIX} Deputy"
WORK_PACKAGE = "Общестрой"
ITEM_KEY = f"{RUN_ID}:work:1"
ITEM_KEY_2 = f"{RUN_ID}:work:2"


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
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


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def auth_token_for(user: dict) -> str:
    payload = {
        "id": user.get("id"),
        "email": user.get("email") or "",
        "role": user.get("role") or "",
        "name": user.get("name") or "",
        "exp": int(time.time()) + 3600,
    }
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    secret = env_value("AUTH_SECRET") or (env_value("DB_PASSWORD", "password") + "|stroyka-auth")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + b64url(sig)


def api_json(method, path, token=None, data=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def login_director():
    email = os.getenv("SMOKE_EMAIL", "")
    password = os.getenv("SMOKE_PASSWORD", "")
    if not email or not password:
        return None
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken") if isinstance(body, dict) else None
    if not token:
        if isinstance(body, dict) and (body.get("twoFactorRequired") or body.get("challengeToken") or body.get("setupToken")):
            print(f"login {email}: включен 2FA, использую временного smoke-замдиректора", file=sys.stderr)
            return None
        raise RuntimeError(f"login {email}: authToken не получен. Body: {body}")
    return token


def cleanup():
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM ai_task_attachments
            WHERE task_id IN (SELECT id FROM ai_tasks WHERE project_name=%s)
               OR report_id IN (
                   SELECT r.id
                   FROM ai_task_reports r
                   JOIN ai_tasks t ON t.id=r.task_id
                   WHERE t.project_name=%s
               )
            """,
            (PROJECT_NAME, PROJECT_NAME),
        )
        cur.execute(
            """
            DELETE FROM ai_task_reports
            WHERE task_id IN (SELECT id FROM ai_tasks WHERE project_name=%s)
            """,
            (PROJECT_NAME,),
        )
        cur.execute("DELETE FROM ai_tasks WHERE project_name=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM ai_findings WHERE project_name=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM room_works WHERE project=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM work_journal WHERE project=%s", (PROJECT_NAME,))
        cur.execute(
            """
            DELETE FROM brigade_payments
            WHERE contract_id IN (SELECT id FROM brigade_contracts WHERE project_name=%s)
            """,
            (PROJECT_NAME,),
        )
        cur.execute(
            """
            DELETE FROM brigade_contract_items
            WHERE contract_id IN (SELECT id FROM brigade_contracts WHERE project_name=%s)
            """,
            (PROJECT_NAME,),
        )
        cur.execute("DELETE FROM brigade_contracts WHERE project_name=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM estimates WHERE project_name=%s", (PROJECT_NAME,))
        cur.execute("DELETE FROM projects WHERE name=%s", (PROJECT_NAME,))
        cur.execute(
            "DELETE FROM users WHERE LOWER(email) IN (LOWER(%s), LOWER(%s))",
            (WORKER_EMAIL, DIRECTOR_EMAIL),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def create_temp_director_token():
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users
                (name, email, password, role, project_id, project_name, assigned_projects, assigned_packages, active, two_factor_required, two_factor_enabled)
            VALUES
                (%s, %s, %s, 'зам_директора', NULL, '', '[]'::jsonb, '[]'::jsonb, TRUE, FALSE, FALSE)
            RETURNING id, name, email, role
            """,
            (DIRECTOR_NAME, DIRECTOR_EMAIL, hash_password(secrets.token_urlsafe(16))),
        )
        row = cur.fetchone()
        conn.commit()
        return auth_token_for({"id": row[0], "name": row[1], "email": row[2], "role": row[3]})
    finally:
        cur.close()
        conn.close()


def prepare_scope():
    cleanup()
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO projects (name, client, status, budget, deadline, progress, tasks, pricelist_id)
            VALUES (%s, %s, 'В работе', 0, '2026-07-31', 0, '{}'::text[], NULL)
            RETURNING id
            """,
            (PROJECT_NAME, f"{PREFIX} Client"),
        )
        project_id = cur.fetchone()[0]
        sections = [
            {
                "name": "Раздел smoke",
                "items": [
                    {
                        "name": "Штукатурка стен smoke",
                        "unit": "м2",
                        "quantity": 12,
                        "priceWork": 1000,
                        "estimateItemKey": ITEM_KEY,
                    },
                    {
                        "name": "Грунтовка стен smoke",
                        "unit": "м2",
                        "quantity": 9,
                        "priceWork": 500,
                        "estimateItemKey": ITEM_KEY_2,
                    }
                ],
            }
        ]
        cur.execute(
            """
            INSERT INTO estimates (project_id, project_name, name, version, sections_json, smeta_type, work_package, status)
            VALUES (%s, %s, %s, '1.0', %s, 'Заказчик', %s, 'Активная')
            RETURNING id
            """,
            (project_id, PROJECT_NAME, f"{PREFIX} Estimate", json.dumps(sections, ensure_ascii=False), WORK_PACKAGE),
        )
        estimate_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO users
                (name, email, password, role, project_id, project_name, assigned_projects, assigned_packages, active, two_factor_required, two_factor_enabled)
            VALUES
                (%s, %s, %s, 'мастер', NULL, '', '[]'::jsonb, '[]'::jsonb, TRUE, FALSE, FALSE)
            RETURNING id, name, email, role
            """,
            (WORKER_NAME, WORKER_EMAIL, hash_password(secrets.token_urlsafe(12))),
        )
        worker = {"id": cur.fetchone()[0], "name": WORKER_NAME, "email": WORKER_EMAIL, "role": "мастер"}
        conn.commit()
        return project_id, estimate_id, worker
    finally:
        cur.close()
        conn.close()


def rows(body):
    return body if isinstance(body, list) else []


def clear_worker_explicit_access(worker_id):
    conn = db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE users
               SET project_name='',
                   assigned_projects='[]'::jsonb,
                   assigned_packages='[]'::jsonb
             WHERE id=%s
            """,
            (worker_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def main():
    director_token = login_director()
    project_id, estimate_id, worker = prepare_scope()
    if not director_token:
        director_token = create_temp_director_token()
    worker_token = auth_token_for(worker)
    try:
        api_json(
            "PUT",
            f"/projects/{project_id}",
            token=director_token,
            expected=200,
            data={"client": f"{PREFIX} Client updated", "archived": False, "archivedAt": None},
        )
        api_json(
            "PUT",
            f"/projects/{project_id}",
            token=director_token,
            expected=403,
            data={"archived": True},
        )

        _, director_estimates = api_json("GET", "/estimates?summary=true", token=director_token, expected=200)
        director_estimate_rows = rows(director_estimates)
        if not any(row.get("id") == estimate_id for row in director_estimate_rows if isinstance(row, dict)):
            raise RuntimeError("director /estimates?summary=true does not include active smoke estimate")

        _, created = api_json(
            "POST",
            f"/estimates/{estimate_id}/work-assignment",
            token=director_token,
            expected=200,
            data={
                "assignee": {
                    "contractorId": worker["id"],
                    "brigadeName": WORKER_NAME,
                    "contractorType": "мастер",
                },
                "priceMode": "coefficient",
                "coefficient": 0.6,
                "items": [
                    {
                        "sectionIndex": 0,
                        "itemIndex": 0,
                        "estimateItemKey": ITEM_KEY,
                    },
                    {
                        "sectionIndex": 0,
                        "itemIndex": 1,
                        "estimateItemKey": ITEM_KEY_2,
                    }
                ],
            },
        )
        if not created.get("ok") or not created.get("contractId") or len(created.get("items") or []) != 2:
            raise RuntimeError(f"work-assignment returned unexpected body: {created}")

        clear_worker_explicit_access(worker["id"])

        _, worker_projects = api_json("GET", "/projects", token=worker_token, expected=200)
        if PROJECT_NAME not in {row.get("name") for row in rows(worker_projects) if isinstance(row, dict)}:
            raise RuntimeError("worker /projects does not include assigned project")

        _, worker_estimates = api_json("GET", "/estimates?summary=true", token=worker_token, expected=200)
        estimate_rows = rows(worker_estimates)
        if not any(row.get("id") == estimate_id for row in estimate_rows if isinstance(row, dict)):
            raise RuntimeError("worker /estimates?summary=true does not include assigned estimate")

        _, worker_full_estimates = api_json("GET", "/estimates", token=worker_token, expected=200)
        full_estimate = next((row for row in rows(worker_full_estimates) if isinstance(row, dict) and row.get("id") == estimate_id), None)
        if not full_estimate:
            raise RuntimeError("worker /estimates does not include assigned estimate")
        assigned_rows = [
            item
            for section in full_estimate.get("sections") or []
            for item in (section.get("items") or [])
            if isinstance(item, dict)
        ]
        assigned_keys = {row.get("estimateItemKey") for row in assigned_rows}
        if ITEM_KEY not in assigned_keys or ITEM_KEY_2 not in assigned_keys:
            raise RuntimeError(f"worker /estimates does not include assigned section item: {full_estimate}")

        _, worker_items = api_json("GET", "/brigade-contract-items-all", token=worker_token, expected=200)
        item_rows = rows(worker_items)
        target = next((row for row in item_rows if isinstance(row, dict) and row.get("estimateItemKey") == ITEM_KEY), None)
        target2 = next((row for row in item_rows if isinstance(row, dict) and row.get("estimateItemKey") == ITEM_KEY_2), None)
        if not target or not target2:
            raise RuntimeError(f"worker /brigade-contract-items-all does not include assigned items: {item_rows}")
        if round(float(target.get("quantity") or 0), 2) != 12 or round(float(target.get("priceBrigade") or 0), 2) != 600:
            raise RuntimeError(f"assigned item values are wrong: {target}")
        if round(float(target2.get("quantity") or 0), 2) != 9 or round(float(target2.get("priceBrigade") or 0), 2) != 300:
            raise RuntimeError(f"assigned item 2 values are wrong: {target2}")

        work_key = f"{estimate_id}:0:0"
        work_key_2 = f"{estimate_id}:0:1"
        daily_date = "2026-07-07"
        daily_comment = f"{PREFIX} daily batch"
        daily_photo = f"/uploads/{RUN_ID}-daily.jpg"
        updated_estimate = copy.deepcopy(full_estimate)
        updated_estimate["sections"][0]["items"][0]["doneQuantity"] = 5
        updated_estimate["sections"][0]["items"][1]["doneQuantity"] = 3
        updated_estimate["_workJournalParams"] = {
            work_key: {
                "estimateItemKey": ITEM_KEY,
                "contractItemId": target.get("id"),
                "workPackage": WORK_PACKAGE,
                "executionPricePerUnit": target.get("priceBrigade"),
                "executionPriceMode": "brigade_contract",
                "date": daily_date,
                "comment": daily_comment,
                "photoUrl": daily_photo,
            },
            work_key_2: {
                "estimateItemKey": ITEM_KEY_2,
                "contractItemId": target2.get("id"),
                "workPackage": WORK_PACKAGE,
                "executionPricePerUnit": target2.get("priceBrigade"),
                "executionPriceMode": "brigade_contract",
                "date": daily_date,
                "comment": daily_comment,
                "photoUrl": daily_photo,
            }
        }
        updated_estimate["_workJournalMaterials"] = {work_key: [], work_key_2: []}
        api_json("PUT", f"/estimates/{estimate_id}", token=worker_token, data=updated_estimate, expected=200)
        conn = db_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT estimate_item_key, room_name, quantity, contract_item_id, date, comment, photo_url
                  FROM work_journal
                 WHERE project=%s AND estimate_item_key IN (%s, %s)
                 ORDER BY estimate_item_key
                """,
                (PROJECT_NAME, ITEM_KEY, ITEM_KEY_2),
            )
            work_rows = cur.fetchall()
            if len(work_rows) != 2:
                raise RuntimeError(f"worker daily batch did not create two work_journal rows: {work_rows}")
            expected = {
                ITEM_KEY: {"qty": 5, "contractItemId": target.get("id")},
                ITEM_KEY_2: {"qty": 3, "contractItemId": target2.get("id")},
            }
            for work_row in work_rows:
                key = work_row[0]
                if (work_row[1] or "") != "Без помещения":
                    raise RuntimeError(f"worker estimate submit used wrong room fallback: {work_row}")
                if round(float(work_row[2] or 0), 2) != expected[key]["qty"]:
                    raise RuntimeError(f"worker estimate submit used wrong quantity: {work_row}")
                if int(work_row[3] or 0) != int(expected[key]["contractItemId"] or 0):
                    raise RuntimeError(f"worker estimate submit used wrong contract item: {work_row}")
                if str(work_row[4])[:10] != daily_date:
                    raise RuntimeError(f"worker daily batch used wrong date: {work_row}")
                if (work_row[5] or "") != daily_comment:
                    raise RuntimeError(f"worker daily batch used wrong comment: {work_row}")
                if (work_row[6] or "") != daily_photo:
                    raise RuntimeError(f"worker daily batch used wrong photo: {work_row}")
        finally:
            cur.close()
            conn.close()

        api_json("DELETE", f"/brigade-contract-items/{target.get('id')}", token=director_token, expected=200)
        api_json("DELETE", f"/brigade-contract-items/{target2.get('id')}", token=director_token, expected=200)
        _, after_delete_items = api_json("GET", "/brigade-contract-items-all", token=worker_token, expected=200)
        if any(isinstance(row, dict) and row.get("estimateItemKey") in (ITEM_KEY, ITEM_KEY_2) for row in rows(after_delete_items)):
            raise RuntimeError("worker still sees assignment after delete")

        print(json.dumps({
            "ok": True,
            "baseUrl": BASE_URL,
            "projectId": project_id,
            "estimateId": estimate_id,
            "contractId": created.get("contractId"),
            "workerItemIds": [target.get("id"), target2.get("id")],
            "projectEditArchivedFalseChecked": True,
            "projectArchiveBlockedChecked": True,
            "directorEstimateSummaryChecked": True,
            "noRoomWorkSubmitChecked": True,
            "dailyBatchTwoEstimateRowsChecked": True,
            "deleteChecked": True,
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "baseUrl": BASE_URL}, ensure_ascii=False, indent=2), file=sys.stderr)
        try:
            cleanup()
        except Exception:
            pass
        raise SystemExit(1)
