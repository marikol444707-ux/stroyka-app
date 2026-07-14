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
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:10]
ERROR_TYPE = f"CodexTenantSmoke{RUN_ID}"
ERROR_PATH = f"/codex-smoke/api-error-owner/{RUN_ID}"
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
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
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


def cleanup():
    conn = None
    try:
        conn = psycopg2.connect(**db_config())
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM api_errors WHERE method='CLIENT' AND path=%s AND error_type=%s",
            (ERROR_PATH, ERROR_TYPE),
        )
        removed = int(cur.rowcount or 0)
        conn.commit()
        cur.close()
        print(f"cleanup: removed {removed} api_errors smoke row(s)")
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"cleanup warning: {exc}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


def query(path, params):
    return path + "?" + urllib.parse.urlencode(params)


def assert_company_rows(rows, allowed_company_ids, label):
    allowed = {int(value) for value in allowed_company_ids}
    for row in rows or []:
        if row.get("ownerScope") != "company":
            raise RuntimeError(f"system-status exposed non-company {label} row #{row.get('id')}")
        if int(row.get("companyId") or 0) not in allowed:
            raise RuntimeError(f"system-status exposed foreign company {label} row #{row.get('id')}")


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    _, context = api_json("GET", "/users/company-context", token=token, expected=200)
    companies = [
        item for item in context.get("companies") or []
        if item.get("role") in LEADERSHIP_ROLES and int(item.get("companyId") or 0) > 0
    ]
    requested_company_id = int(env_value("SMOKE_COMPANY_ID", "0") or 0)
    selected = next(
        (item for item in companies if int(item.get("companyId") or 0) == requested_company_id),
        companies[0] if companies and not requested_company_id else None,
    )
    if not selected:
        raise RuntimeError("У smoke-пользователя нет руководящей роли в выбранной компании")
    company_id = int(selected["companyId"])
    headers = {"X-Company-Mode": "company", "X-Company-Id": str(company_id)}
    started_at = int(time.time()) - 5

    try:
        api_json(
            "POST",
            "/client-errors",
            token=token,
            headers=headers,
            expected=200,
            data={
                "path": ERROR_PATH,
                "type": ERROR_TYPE,
                "message": f"CODEX QA tenant api_error {RUN_ID}",
            },
        )
        _, selected_status = api_json(
            "GET",
            query("/system-status", {"api_errors_since": started_at}),
            token=token,
            headers=headers,
            expected=200,
        )
        selected_rows = selected_status.get("apiErrors") or []
        assert_company_rows(selected_rows, {company_id}, "api_error")
        assert_company_rows(selected_status.get("recentAudit") or [], {company_id}, "audit")
        matching = [row for row in selected_rows if row.get("errorType") == ERROR_TYPE]
        if len(matching) != 1:
            raise RuntimeError("Маркированная frontend-ошибка не найдена в выбранной компании")
        if int(matching[0].get("companyId") or 0) != company_id:
            raise RuntimeError("Маркированная frontend-ошибка записана в другую компанию")

        api_json(
            "GET",
            "/system-status",
            token=token,
            headers={"X-Company-Mode": "company", "X-Company-Id": "2147483647"},
            expected=403,
        )

        all_companies_count = None
        checked = [
            "client error stores exact selected company owner",
            "selected company system status excludes platform, legacy and foreign errors",
            "recent audit rows use the same selected company scope",
            "foreign company header is rejected",
        ]
        skipped = []
        if context.get("canUseAllCompanies"):
            allowed_ids = {int(item["companyId"]) for item in companies}
            _, all_status = api_json(
                "GET",
                query("/system-status", {"api_errors_since": started_at}),
                token=token,
                headers={"X-Company-Mode": "all_companies"},
                expected=200,
            )
            all_rows = all_status.get("apiErrors") or []
            assert_company_rows(all_rows, allowed_ids, "api_error")
            assert_company_rows(all_status.get("recentAudit") or [], allowed_ids, "audit")
            all_companies_count = len(all_rows)
            checked.append("all-companies mode includes only leadership memberships")
        else:
            skipped.append("all-companies mode: current user context does not expose this mode")

        print(json.dumps({
            "ok": True,
            "companyId": company_id,
            "apiErrorId": matching[0].get("id"),
            "allCompaniesItems": all_companies_count,
            "checked": checked,
            "skipped": skipped,
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    main()
