#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:10]
TEST_EMAILS = [
    f"messenger-account-{RUN_ID}-a@stroyka.local",
    f"messenger-account-{RUN_ID}-b@stroyka.local",
]
EXTERNAL_USER_ID = f"codex-max-account-{RUN_ID}"
CHAT_ID = f"codex-max-chat-{RUN_ID}"
LEADERSHIP_ROLES = {"директор", "зам_директора"}


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


def api_json(method, path, *, token=None, data=None, headers=None, expected=None):
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:900]}")
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {path}: backend returned non-JSON body: {text[:300]}") from exc


def totp_code(secret):
    normalized = re.sub(r"\s+", "", str(secret or "")).upper()
    normalized += "=" * (-len(normalized) % 8)
    key = base64.b32decode(normalized, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    if body.get("authToken"):
        return body["authToken"]
    if body.get("twoFactorRequired"):
        code = env_value("SMOKE_2FA_CODE")
        if not code and env_value("SMOKE_TOTP_SECRET"):
            code = totp_code(env_value("SMOKE_TOTP_SECRET"))
        if not code:
            raise SystemExit("Нужно задать SMOKE_2FA_CODE или SMOKE_TOTP_SECRET")
        _, verified = api_json(
            "POST",
            "/login/2fa/verify",
            data={"challengeToken": body.get("challengeToken"), "code": code},
            expected=200,
        )
        if verified.get("authToken"):
            return verified["authToken"]
    raise RuntimeError("authToken не получен")


def select_company(context):
    leadership = [
        item
        for item in context.get("companies") or []
        if item.get("role") in LEADERSHIP_ROLES and int(item.get("companyId") or 0) > 0
    ]
    requested = str(env_value("SMOKE_COMPANY_ID") or "").strip()
    if requested:
        requested_id = int(requested)
        selected = next((item for item in leadership if int(item.get("companyId") or 0) == requested_id), None)
        if not selected:
            raise RuntimeError("SMOKE_COMPANY_ID не входит в руководящий контур smoke-пользователя")
        return requested_id, leadership
    if not leadership:
        raise RuntimeError("У smoke-пользователя нет руководящей роли ни в одной компании")
    return int(leadership[0]["companyId"]), leadership


def create_test_users(company_id):
    conn = psycopg2.connect(**db_config())
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    user_ids = []
    try:
        cur.execute("SELECT platform_account_id FROM companies WHERE id=%s", (company_id,))
        company = cur.fetchone()
        if not company:
            raise RuntimeError(f"Компания #{company_id} не найдена")
        for index, email in enumerate(TEST_EMAILS, start=1):
            cur.execute(
                """
                INSERT INTO users
                    (name,email,password,role,company_id,platform_account_id,
                     assigned_projects,assigned_packages,active)
                VALUES
                    (%s,%s,%s,'мастер',%s,%s,'[]'::jsonb,'[]'::jsonb,TRUE)
                RETURNING id
                """,
                (
                    f"CODEX MAX account smoke {RUN_ID} {index}",
                    email,
                    "smoke-account-not-for-login",
                    company_id,
                    company.get("platform_account_id"),
                ),
            )
            user_id = int(cur.fetchone()["id"])
            user_ids.append(user_id)
            cur.execute(
                """
                INSERT INTO user_company_roles
                    (user_id,platform_account_id,company_id,role,assigned_projects,
                     assigned_packages,active,is_default)
                VALUES
                    (%s,%s,%s,'мастер','[]'::jsonb,'[]'::jsonb,TRUE,TRUE)
                """,
                (user_id, company.get("platform_account_id"), company_id),
            )
        conn.commit()
        return user_ids
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def cleanup(account_id=None, user_ids=None):
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        if account_id:
            cur.execute("DELETE FROM messenger_accounts WHERE id=%s", (account_id,))
        cur.execute("DELETE FROM messenger_accounts WHERE external_user_id=%s OR chat_id=%s", (EXTERNAL_USER_ID, CHAT_ID))
        ids = [int(value) for value in user_ids or [] if int(value) > 0]
        if ids:
            cur.execute("DELETE FROM user_company_roles WHERE user_id=ANY(%s)", (ids,))
            cur.execute("DELETE FROM users WHERE id=ANY(%s)", (ids,))
        conn.commit()
        cur.close()
        print("cleanup: removed messenger account smoke rows")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def assert_company_scope(items, allowed_company_ids):
    allowed = {int(value) for value in allowed_company_ids}
    for item in items or []:
        item_companies = {int(value) for value in item.get("companyIds") or []}
        if not item_companies or not item_companies.issubset(allowed):
            raise RuntimeError(
                f"Messenger account #{item.get('id')} returned companies {sorted(item_companies)} outside {sorted(allowed)}"
            )


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")

    token = login(email, password)
    _, context = api_json("GET", "/users/company-context", token=token, expected=200)
    company_id, leadership_companies = select_company(context)
    selected_headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    user_ids = []
    account_id = None
    try:
        user_ids = create_test_users(company_id)
        _, created = api_json(
            "POST",
            "/messenger-accounts",
            token=token,
            headers=selected_headers,
            data={
                "provider": "max",
                "userId": user_ids[0],
                "externalUserId": EXTERNAL_USER_ID,
                "chatId": CHAT_ID,
                "displayName": f"CODEX MAX account {RUN_ID}",
            },
            expected=200,
        )
        account = created.get("account") or {}
        account_id = int(account.get("id") or 0)
        if not account_id or account.get("companyIds") != [company_id]:
            raise RuntimeError(f"Созданная MAX-связка получила неверного владельца: {account}")

        _, selected = api_json(
            "GET",
            "/messenger-accounts",
            token=token,
            headers=selected_headers,
            expected=200,
        )
        selected_items = selected.get("items") or []
        assert_company_scope(selected_items, {company_id})
        if account_id not in {int(item.get("id") or 0) for item in selected_items}:
            raise RuntimeError("Созданная MAX-связка не видна в выбранной компании")

        api_json(
            "GET",
            "/messenger-accounts",
            token=token,
            headers={"X-Company-Mode": "company", "X-Company-Id": "2147483647"},
            expected=403,
        )
        api_json(
            "POST",
            "/messenger-accounts",
            token=token,
            headers=selected_headers,
            data={
                "provider": "max",
                "userId": user_ids[1],
                "externalUserId": EXTERNAL_USER_ID,
            },
            expected=409,
        )

        all_companies_count = None
        if context.get("canUseAllCompanies"):
            allowed_ids = {
                int(item["companyId"])
                for item in leadership_companies
                if int(item.get("companyId") or 0) > 0
            }
            _, all_companies = api_json(
                "GET",
                "/messenger-accounts",
                token=token,
                headers={"X-Company-Mode": "all_companies"},
                expected=200,
            )
            all_items = all_companies.get("items") or []
            assert_company_scope(all_items, allowed_ids)
            all_companies_count = len(all_items)
            api_json(
                "POST",
                "/messenger-accounts",
                token=token,
                headers={"X-Company-Mode": "all_companies"},
                data={
                    "provider": "max",
                    "userId": user_ids[0],
                    "externalUserId": EXTERNAL_USER_ID,
                },
                expected=400,
            )

        print(json.dumps({
            "ok": True,
            "selectedCompanyId": company_id,
            "accountId": account_id,
            "selectedItems": len(selected_items),
            "allCompaniesItems": all_companies_count,
            "checked": [
                "director creates MAX identity only for an employee of selected company",
                "selected company lists only accounts derived from its employee memberships",
                "foreign company header is rejected",
                "existing MAX identity cannot be reassigned to another employee",
                "all-companies read excludes non-leadership memberships and remains read-only",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup(account_id, user_ids)


if __name__ == "__main__":
    main()
