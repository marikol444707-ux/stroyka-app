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
DISABLE_EMAIL = f"auth-session-disabled-{RUN_ID}@stroyka.local"
DISABLE_PASSWORD = secrets.token_urlsafe(14)
DISABLE_ROLE = "снабженец"
PASSWORD_CHANGE_EMAIL = f"auth-session-password-{RUN_ID}@stroyka.local"
PASSWORD_CHANGE_PASSWORD = secrets.token_urlsafe(14)
PASSWORD_CHANGE_NEW_PASSWORD = secrets.token_urlsafe(14)
PASSWORD_CHANGE_ROLE = "снабженец"
ROLE_CHANGE_EMAIL = f"auth-session-role-{RUN_ID}@stroyka.local"
ROLE_CHANGE_PASSWORD = secrets.token_urlsafe(14)
ROLE_CHANGE_FROM_ROLE = "снабженец"
ROLE_CHANGE_TO_ROLE = "кладовщик"
ADMIN_EMAIL = f"auth-session-admin-{RUN_ID}@stroyka.local"
ADMIN_PASSWORD = secrets.token_urlsafe(14)
COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE_NAME", "stroyka_session")
EXPECT_CSRF_LOGOUT_ENFORCED = os.getenv(
    "EXPECT_CSRF_LOGOUT_ENFORCED",
    os.getenv("CSRF_LOGOUT_ENFORCED", "false"),
).strip().lower() in ("1", "true", "yes")


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


def prepare_user(email=EMAIL, password=PASSWORD, name=None, role="прораб"):
    conn = db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("DELETE FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    cur.execute(
        """INSERT INTO users
              (name,email,password,role,project_id,project_name,assigned_projects,assigned_packages,
               active,two_factor_required,two_factor_enabled,company_id)
           VALUES
              (%s,%s,%s,%s,NULL,'','[]'::jsonb,'[]'::jsonb,TRUE,FALSE,FALSE,1)
           RETURNING id""",
        (name or f"Auth Session Smoke {RUN_ID}", email, hash_password(password), role),
    )
    user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def cleanup():
    conn = db_conn()
    cur = conn.cursor()
    emails = (EMAIL, DISABLE_EMAIL, PASSWORD_CHANGE_EMAIL, ROLE_CHANGE_EMAIL, ADMIN_EMAIL)
    cur.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE LOWER(email)=ANY(%s))", ([email.lower() for email in emails],))
    cur.execute("DELETE FROM users WHERE LOWER(email)=ANY(%s)", ([email.lower() for email in emails],))
    conn.commit()
    cur.close()
    conn.close()


def request_json(opener, method, path, data=None, token=None, headers_extra=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if headers_extra:
        headers.update(headers_extra)
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


def active_session_count(user_id):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM user_sessions WHERE user_id=%s AND revoked_at IS NULL AND expires_at>NOW()",
        (user_id,),
    )
    count = int((cur.fetchone() or [0])[0] or 0)
    cur.close()
    conn.close()
    return count


def auth_token_for(user_id, email=EMAIL, role="прораб", name=None, two_factor_passed=False):
    payload = {
        "id": user_id,
        "email": email,
        "role": role,
        "name": name or f"Auth Session Smoke {RUN_ID}",
        "twoFactorPassed": bool(two_factor_passed),
        "exp": int(time.time()) + 3600,
    }
    body = b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    secret = env_value("AUTH_SECRET") or (env_value("DB_PASSWORD", "password") + "|stroyka-auth")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + b64url(sig)


def assert_disabling_user_revokes_cookie_sessions(admin_token):
    user_id = prepare_user(
        DISABLE_EMAIL,
        DISABLE_PASSWORD,
        name=f"Auth Session Disabled {RUN_ID}",
        role=DISABLE_ROLE,
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request_json(
        opener,
        "POST",
        "/login",
        data={"email": DISABLE_EMAIL, "password": DISABLE_PASSWORD},
        expected=200,
    )
    request_json(opener, "GET", "/users", expected=200)
    if active_session_count(user_id) < 1:
        raise RuntimeError("disabled-user scenario did not create an active cookie session")
    request_json(
        urllib.request.build_opener(),
        "PUT",
        f"/users/{user_id}",
        token=admin_token,
        data={
            "name": f"Auth Session Disabled {RUN_ID}",
            "email": DISABLE_EMAIL,
            "password": "",
            "role": DISABLE_ROLE,
            "projectId": "",
            "projectName": "",
            "assignedProjects": [],
            "assignedPackages": [],
            "active": False,
        },
        expected=200,
    )
    remaining = active_session_count(user_id)
    if remaining != 0:
        raise RuntimeError(f"disabling user left {remaining} active cookie session(s)")
    request_json(opener, "GET", "/users", expected=401)


def assert_password_change_revokes_cookie_sessions(admin_token):
    user_id = prepare_user(
        PASSWORD_CHANGE_EMAIL,
        PASSWORD_CHANGE_PASSWORD,
        name=f"Auth Session Password {RUN_ID}",
        role=PASSWORD_CHANGE_ROLE,
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request_json(
        opener,
        "POST",
        "/login",
        data={"email": PASSWORD_CHANGE_EMAIL, "password": PASSWORD_CHANGE_PASSWORD},
        expected=200,
    )
    request_json(opener, "GET", "/users", expected=200)
    if active_session_count(user_id) < 1:
        raise RuntimeError("password-change scenario did not create an active cookie session")
    request_json(
        urllib.request.build_opener(),
        "PUT",
        f"/users/{user_id}",
        token=admin_token,
        data={
            "name": f"Auth Session Password {RUN_ID}",
            "email": PASSWORD_CHANGE_EMAIL,
            "password": PASSWORD_CHANGE_NEW_PASSWORD,
            "role": PASSWORD_CHANGE_ROLE,
            "projectId": "",
            "projectName": "",
            "assignedProjects": [],
            "assignedPackages": [],
            "active": True,
        },
        expected=200,
    )
    remaining = active_session_count(user_id)
    if remaining != 0:
        raise RuntimeError(f"password change left {remaining} active cookie session(s)")
    request_json(opener, "GET", "/users", expected=401)
    request_json(
        urllib.request.build_opener(),
        "POST",
        "/login",
        data={"email": PASSWORD_CHANGE_EMAIL, "password": PASSWORD_CHANGE_NEW_PASSWORD},
        expected=200,
    )


def assert_role_change_revokes_cookie_sessions(admin_token):
    user_id = prepare_user(
        ROLE_CHANGE_EMAIL,
        ROLE_CHANGE_PASSWORD,
        name=f"Auth Session Role {RUN_ID}",
        role=ROLE_CHANGE_FROM_ROLE,
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request_json(
        opener,
        "POST",
        "/login",
        data={"email": ROLE_CHANGE_EMAIL, "password": ROLE_CHANGE_PASSWORD},
        expected=200,
    )
    request_json(opener, "GET", "/users", expected=200)
    if active_session_count(user_id) < 1:
        raise RuntimeError("role-change scenario did not create an active cookie session")
    request_json(
        urllib.request.build_opener(),
        "PUT",
        f"/users/{user_id}",
        token=admin_token,
        data={
            "name": f"Auth Session Role {RUN_ID}",
            "email": ROLE_CHANGE_EMAIL,
            "password": "",
            "role": ROLE_CHANGE_TO_ROLE,
            "projectId": "",
            "projectName": "",
            "assignedProjects": [],
            "assignedPackages": [],
            "active": True,
        },
        expected=200,
    )
    remaining = active_session_count(user_id)
    if remaining != 0:
        raise RuntimeError(f"role change left {remaining} active cookie session(s)")
    request_json(opener, "GET", "/users", expected=401)
    request_json(
        urllib.request.build_opener(),
        "POST",
        "/login",
        data={"email": ROLE_CHANGE_EMAIL, "password": ROLE_CHANGE_PASSWORD},
        expected=200,
    )


def main():
    cleanup()
    user_id = prepare_user()
    admin_id = prepare_user(
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
        name=f"Auth Session Admin {RUN_ID}",
        role="директор",
    )
    admin_token = auth_token_for(
        admin_id,
        email=ADMIN_EMAIL,
        role="директор",
        name=f"Auth Session Admin {RUN_ID}",
        two_factor_passed=True,
    )
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
            _, csrf_body, _ = request_json(opener, "GET", "/csrf-token", expected=200)
            csrf_token = csrf_body.get("csrfToken")
            if not csrf_token:
                raise RuntimeError(f"/csrf-token did not return csrfToken: {csrf_body}")
            if EXPECT_CSRF_LOGOUT_ENFORCED:
                request_json(opener, "POST", "/logout", expected=403)
                request_json(opener, "POST", "/logout", headers_extra={"X-CSRF-Token": "bad-token"}, expected=403)
                request_json(opener, "GET", "/users", expected=200)
            request_json(opener, "POST", "/logout", headers_extra={"X-CSRF-Token": csrf_token}, expected=200)
            request_json(opener, "GET", "/users", expected=401)

        bearer_token = auth_token_for(user_id)
        request_json(urllib.request.build_opener(), "GET", "/users", token=bearer_token, expected=200)
        if BASE_URL.startswith("https://"):
            assert_disabling_user_revokes_cookie_sessions(admin_token)
            assert_password_change_revokes_cookie_sessions(admin_token)
            assert_role_change_revokes_cookie_sessions(admin_token)
        print(json.dumps({
            "ok": True,
            "baseUrl": BASE_URL,
            "checked": [
                "login returns transition Bearer token",
                "login sets HttpOnly session cookie",
                "cookie opens protected endpoint" if BASE_URL.startswith("https://") else "cookie endpoint skipped on non-https BASE_URL",
                "csrf token endpoint returns token" if BASE_URL.startswith("https://") else "csrf token endpoint skipped on non-https BASE_URL",
                "missing/invalid csrf rejected for cookie logout" if BASE_URL.startswith("https://") and EXPECT_CSRF_LOGOUT_ENFORCED else "csrf logout rejection not expected in compatibility mode",
                "valid csrf logout succeeds" if BASE_URL.startswith("https://") else "valid csrf logout skipped on non-https BASE_URL",
                "logout revokes cookie session" if BASE_URL.startswith("https://") else "logout cookie revocation skipped on non-https BASE_URL",
                "Bearer fallback remains compatible",
                "disabling user revokes active cookie sessions" if BASE_URL.startswith("https://") else "disable-user session revocation skipped on non-https BASE_URL",
                "password change revokes active cookie sessions" if BASE_URL.startswith("https://") else "password-change session revocation skipped on non-https BASE_URL",
                "role change revokes active cookie sessions" if BASE_URL.startswith("https://") else "role-change session revocation skipped on non-https BASE_URL",
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
