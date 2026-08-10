"""Auth and session primitives for the Stroyka backend.

Extracted verbatim from backend/main.py (Task 12) with no behavior
changes: password hashing, 2FA/TOTP codes, signed flow tokens, bearer
tokens, server-side session records, CSRF tokens and session cookies.
DB-touching user resolution (get_current_user and friends) stays in
backend/main.py.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from typing import Optional

from fastapi import HTTPException, Request, Response

try:
    from backend.config import APP_PUBLIC_URL, AUTH_SECRET, AUTH_TOKEN_TTL_SECONDS
except ModuleNotFoundError:
    from config import APP_PUBLIC_URL, AUTH_SECRET, AUTH_TOKEN_TTL_SECONDS

PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260000
TWO_FACTOR_REQUIRED_ROLES = (
    "директор", "зам_директора", "бухгалтер",
    "system_owner", "platform_admin", "platform_support", "billing_admin",
    "account_owner", "account_admin",
)
TWO_FACTOR_TOKEN_TTL_SECONDS = 10 * 60
AUTH_SESSION_COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE_NAME", "stroyka_session").strip() or "stroyka_session"
AUTH_SESSION_TTL_SECONDS = int(os.getenv("AUTH_SESSION_TTL_SECONDS", str(30 * 24 * 60 * 60)))
AUTH_SESSION_COOKIE_SECURE = os.getenv(
    "AUTH_SESSION_COOKIE_SECURE",
    "true" if APP_PUBLIC_URL.startswith("https://") else "false",
).lower() in ("1", "true", "yes")
AUTH_SESSION_COOKIE_SAMESITE = os.getenv("AUTH_SESSION_COOKIE_SAMESITE", "lax").strip().lower()
if AUTH_SESSION_COOKIE_SAMESITE not in ("lax", "strict", "none"):
    AUTH_SESSION_COOKIE_SAMESITE = "lax"
CSRF_TOKEN_TTL_SECONDS = int(os.getenv("CSRF_TOKEN_TTL_SECONDS", str(2 * 60 * 60)))
CSRF_LOGOUT_ENFORCED = os.getenv("CSRF_LOGOUT_ENFORCED", "false").strip().lower() in ("1", "true", "yes")
COOKIE_SESSION_AUTHENTICATION_REQUIRED = (
    "cookie_session_authentication_required"
)
COOKIE_SESSION_CSRF_INVALID = "cookie_session_csrf_invalid"
_AUTH_SESSION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{64}$")


class CookieSessionAuthenticationError(ValueError):
    """Fixed, secret-free cookie authentication boundary error."""

    def __init__(self, code: str):
        if code not in {
            COOKIE_SESSION_AUTHENTICATION_REQUIRED,
            COOKIE_SESSION_CSRF_INVALID,
        }:
            code = COOKIE_SESSION_AUTHENTICATION_REQUIRED
        self.code = code
        super().__init__(code)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_HASH_ITERATIONS)
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${salt}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == PASSWORD_HASH_PREFIX:
        try:
            iterations = int(parts[1])
            salt = parts[2]
            expected = parts[3]
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
            return hmac.compare_digest(digest, expected)
        except Exception:
            return False
    # Backward compatibility for existing plaintext passwords. Successful login upgrades it.
    return hmac.compare_digest(password, stored)

def is_legacy_password(stored: str) -> bool:
    return bool(stored) and not stored.startswith(PASSWORD_HASH_PREFIX + "$")

def _role_requires_2fa(role: str) -> bool:
    return (role or "") in TWO_FACTOR_REQUIRED_ROLES

def _user_requires_2fa(user: dict) -> bool:
    return bool(user.get("two_factor_required")) or _role_requires_2fa(user.get("role") or "")

def _generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

def _totp_key(secret: str) -> bytes:
    value = re.sub(r"\s+", "", str(secret or "")).upper()
    if not value:
        raise ValueError("empty secret")
    value += "=" * (-len(value) % 8)
    return base64.b32decode(value, casefold=True)

def _totp_code(secret: str, timestamp: Optional[int] = None, step: int = 30) -> str:
    counter = int((timestamp or int(time.time())) // step)
    digest = hmac.new(_totp_key(secret), counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return str(value % 1000000).zfill(6)

def _verify_totp_code(secret: str, code: str) -> bool:
    cleaned = re.sub(r"\D", "", str(code or ""))
    if len(cleaned) != 6:
        return False
    now = int(time.time())
    for drift in (-30, 0, 30):
        try:
            if hmac.compare_digest(_totp_code(secret, now + drift), cleaned):
                return True
        except Exception:
            return False
    return False

def _signed_flow_token(payload: dict) -> str:
    data = dict(payload or {})
    data["exp"] = int(data.get("exp") or (int(time.time()) + TWO_FACTOR_TOKEN_TTL_SECONDS))
    body = _b64url(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + _b64url(sig)

def _verify_signed_flow_token(token: str, purpose: str) -> dict:
    try:
        body, sig = str(token or "").split(".", 1)
        expected = _b64url(hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if payload.get("purpose") != purpose:
            raise ValueError("bad purpose")
        if int(payload.get("exp") or 0) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Код 2FA устарел. Войдите заново.")

def _two_factor_otpauth_uri(user: dict, secret: str) -> str:
    issuer = "Stroyka"
    label = urllib.parse.quote(f"{issuer}:{user.get('email') or user.get('name') or user.get('id')}")
    return "otpauth://totp/" + label + "?" + urllib.parse.urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": 6, "period": 30})

def _two_factor_setup_response(user: dict, secret: str) -> dict:
    return {
        "twoFactorSetupRequired": True,
        "setupToken": _signed_flow_token({"purpose": "2fa_setup", "userId": user.get("id")}),
        "manualKey": secret,
        "otpauthUri": _two_factor_otpauth_uri(user, secret),
        "email": user.get("email") or "",
        "name": user.get("name") or "",
        "role": user.get("role") or "",
    }

def _two_factor_challenge_response(user: dict) -> dict:
    return {
        "twoFactorRequired": True,
        "challengeToken": _signed_flow_token({"purpose": "2fa_login", "userId": user.get("id")}),
        "email": user.get("email") or "",
        "name": user.get("name") or "",
        "role": user.get("role") or "",
    }

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

def create_auth_token(user: dict, two_factor_passed: bool = False) -> str:
    payload = {
        "id": user.get("id"),
        "email": user.get("email") or "",
        "role": user.get("role") or "",
        "name": user.get("name") or "",
        "twoFactorPassed": bool(two_factor_passed),
        "exp": int(time.time()) + AUTH_TOKEN_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return body + "." + _b64url(sig)

def verify_auth_token(token: str) -> dict:
    try:
        body, sig = token.split(".", 1)
        expected = _b64url(hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp") or 0) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Сессия недействительна. Войдите заново.")

def _session_token_hash(token: str) -> str:
    return hmac.new(AUTH_SECRET.encode("utf-8"), str(token or "").encode("utf-8"), hashlib.sha256).hexdigest()

def _create_csrf_token(session_token: str) -> str:
    payload = {
        "purpose": "csrf",
        "session": _session_token_hash(session_token),
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + CSRF_TOKEN_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), ("csrf:" + body).encode("utf-8"), hashlib.sha256).digest()
    return body + "." + _b64url(sig)

def _valid_csrf_token(token: str, session_token: str) -> bool:
    try:
        body, sig = str(token or "").split(".", 1)
        expected = _b64url(hmac.new(AUTH_SECRET.encode("utf-8"), ("csrf:" + body).encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return False
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if payload.get("purpose") != "csrf":
            return False
        if int(payload.get("exp") or 0) < int(time.time()):
            return False
        return hmac.compare_digest(payload.get("session") or "", _session_token_hash(session_token))
    except Exception:
        return False


def build_cookie_session_authentication(
    request,
    authorization=None,
    csrf_token=None,
    *,
    require_csrf=True,
):
    """Build the exact cookie-session context without touching a database."""

    if authorization is not None or type(require_csrf) is not bool:
        raise CookieSessionAuthenticationError(
            COOKIE_SESSION_AUTHENTICATION_REQUIRED
        )
    try:
        cookies = request.cookies
        session_token = cookies.get(AUTH_SESSION_COOKIE_NAME)
    except Exception:
        raise CookieSessionAuthenticationError(
            COOKIE_SESSION_AUTHENTICATION_REQUIRED
        ) from None
    if (
        type(session_token) is not str
        or _AUTH_SESSION_TOKEN_RE.fullmatch(session_token) is None
    ):
        raise CookieSessionAuthenticationError(
            COOKIE_SESSION_AUTHENTICATION_REQUIRED
        )
    if require_csrf and (
        type(csrf_token) is not str
        or not _valid_csrf_token(csrf_token, session_token)
    ):
        raise CookieSessionAuthenticationError(
            COOKIE_SESSION_CSRF_INVALID
        )
    return {
        "authenticationKind": "cookie_session",
        "sessionHash": _session_token_hash(session_token),
    }

def _request_ip(request: Optional[Request]) -> str:
    if not request:
        return ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")

def _request_user_agent(request: Optional[Request]) -> str:
    if not request:
        return ""
    return (request.headers.get("user-agent") or "")[:500]

def _set_auth_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=AUTH_SESSION_COOKIE_SECURE,
        samesite=AUTH_SESSION_COOKIE_SAMESITE,
        path="/",
    )

def _clear_auth_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        path="/",
    )

def _create_auth_session(cur, user: dict, request: Optional[Request], two_factor_passed: bool) -> str:
    token = secrets.token_urlsafe(48)
    cur.execute(
        """UPDATE user_sessions
           SET revoked_at=NOW()
           WHERE user_id=%s AND expires_at<NOW() AND revoked_at IS NULL""",
        (user.get("id"),),
    )
    cur.execute(
        """INSERT INTO user_sessions
             (user_id, session_hash, ip, user_agent, two_factor_passed, expires_at)
           VALUES (%s,%s,%s,%s,%s,NOW() + (%s || ' seconds')::interval)""",
        (
            user.get("id"),
            _session_token_hash(token),
            _request_ip(request),
            _request_user_agent(request),
            bool(two_factor_passed),
            int(AUTH_SESSION_TTL_SECONDS),
        ),
    )
    return token

def _revoke_user_sessions(cur, user_id) -> int:
    if not user_id:
        return 0
    cur.execute(
        """UPDATE user_sessions
           SET revoked_at=NOW()
           WHERE user_id=%s AND revoked_at IS NULL""",
        (user_id,),
    )
    return int(cur.rowcount or 0)
