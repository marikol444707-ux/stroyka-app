#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
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


def env_value(name):
    return os.getenv(name) or ENV.get(name, "")


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


def assert_items(items, allowed_company_ids):
    allowed = {int(company_id) for company_id in allowed_company_ids}
    for item in items or []:
        if item.get("ownerScope") != "company":
            raise RuntimeError(f"Outbox #{item.get('id')} returned non-company owner scope")
        if int(item.get("companyId") or 0) not in allowed:
            raise RuntimeError(f"Outbox #{item.get('id')} returned foreign companyId={item.get('companyId')}")


def main():
    email = env_value("SMOKE_EMAIL")
    password = env_value("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD в окружении или backend/.env")
    token = login(email, password)
    _, context = api_json("GET", "/users/company-context", token=token, expected=200)
    leadership_companies = [
        company
        for company in context.get("companies") or []
        if company.get("role") in LEADERSHIP_ROLES and int(company.get("companyId") or 0) > 0
    ]
    if not leadership_companies:
        raise RuntimeError("У smoke-пользователя нет руководящей роли ни в одной компании")

    selected_id = int(leadership_companies[0]["companyId"])
    selected_headers = {"X-Company-Mode": "company", "X-Company-Id": str(selected_id)}
    _, selected = api_json(
        "GET",
        "/messenger-outbox?status=all&limit=500",
        token=token,
        headers=selected_headers,
        expected=200,
    )
    assert_items(selected.get("items") or [], {selected_id})

    api_json(
        "GET",
        "/messenger-outbox?status=all&limit=1",
        token=token,
        headers={"X-Company-Mode": "company", "X-Company-Id": "2147483647"},
        expected=403,
    )

    all_items_count = None
    if context.get("canUseAllCompanies"):
        allowed_ids = {int(company["companyId"]) for company in leadership_companies}
        _, all_companies = api_json(
            "GET",
            "/messenger-outbox?status=all&limit=500",
            token=token,
            headers={"X-Company-Mode": "all_companies"},
            expected=200,
        )
        all_items = all_companies.get("items") or []
        assert_items(all_items, allowed_ids)
        all_items_count = len(all_items)

    print(json.dumps({
        "ok": True,
        "selectedCompanyId": selected_id,
        "selectedItems": len(selected.get("items") or []),
        "allCompaniesItems": all_items_count,
        "checked": [
            "selected company returns only stored company-owned outbox rows",
            "foreign company header is rejected",
            "all-companies mode excludes non-leadership memberships",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
