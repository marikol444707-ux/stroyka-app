#!/usr/bin/env python3
import base64
import hashlib
import hmac
import http.cookiejar
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
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
RUN_ID = uuid.uuid4().hex[:8]
EMAIL = f"auth-session-smoke-{RUN_ID}@stroyka.local"
PASSWORD = secrets.token_urlsafe(14)
COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE_NAME", "stroyka_session")


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


def db_conn():
    return psycopg2.connect(
        dbname=env_value("DB_NAME", "stroyka"),
        user=env_value("DB_USER", "stroyka"),
        password=env_value("DB_PASSWORD", "password123"),
        host=env_value("DB_HOST", "localhost"),
        port=env_value("DB_PORT", "5432"),
    )


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def prepare_user():
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (EMAIL,))
    cur.execute(
        """INSERT INTO users
              (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,
               active,two_factor_required,two_factor_enabled,company_id)
           VALUES
              (%s,%s,%s,'прораб',NULL,'','[]'::jsonb,'[]'::jsonb,TRUE,FALSE,FALSE,1)
           RETURNING id""",
        (f"Auth Session Smoke {RUN_ID}", EMAIL, hash_password(PASSWORD)),
    )
    user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def cleanup():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=LOWER(%s))", (EMAIL,))
    cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (EMAIL,))
    conn.commit()
    cur.close()
    conn.close()


def request_json(opener, method, path, data=None, token=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with opener.open(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
            set_cookie = resp.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
        set_cookie = exc.headers.get_all("Set-Cookie") or []
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:500]}")
    body_json = json.loads(text) if text else {}
    return status, body_json, set_cookie


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def auth_token_for(user_id):
    payload = {
        "id": user_id,
        "email": EMAIL,
        "role": "прораб",
        "name": f"Auth Session Smoke {RUN_ID}",
        "exp": int(time.time()) + 3600,
    }
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    secret = env_value("AUTH_SECRET") or (env_value("DB_PASSWORD", "password") + "|stroyka-auth")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + b64url(sig)


def main():
    cleanup()
    user_id = prepare_user()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        _, login_body, set_cookie = request_json(
            opener,
            "POST",
            "/login",
            data={"email": EMAIL, "password": PASSWORD},
            expected=200,
        )
        if not login_body.get("authToken"):
            raise RuntimeError(f"login did not return transition authToken: {login_body}")
        cookie_header = "\n".join(set_cookie)
        if COOKIE_NAME not in cookie_header or "HttpOnly" not in cookie_header:
            raise RuntimeError(f"login did not set HttpOnly session cookie. Set-Cookie: {set_cookie}")

        if BASE_URL.startswith("https://"):
            request_json(opener, "GET", "/users", expected=200)
            request_json(opener, "POST", "/logout", expected=200)
            request_json(opener, "GET", "/users", expected=401)

        bearer_token = auth_token_for(user_id)
        request_json(urllib.request.build_opener(), "GET", "/users", token=bearer_token, expected=200)
        print(json.dumps({
            "ok": True,
            "baseUrl": BASE_URL,
            "checked": [
                "login returns transition Bearer token",
                "login sets HttpOnly session cookie",
                "cookie opens protected endpoint" if BASE_URL.startswith("https://") else "cookie endpoint skipped on non-https BASE_URL",
                "logout revokes cookie session" if BASE_URL.startswith("https://") else "logout cookie revocation skipped on non-https BASE_URL",
                "Bearer fallback remains compatible",
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL:", exc, file=sys.stderr)
        cleanup()
        sys.exit(1)
