"""QA-only read-only cookie/session membership resolver, not an HTTP route.

This is a pure, fail-closed SQL projection for future QA bootstrap. It does not
use get_current_user (which may touch last_seen_at) and must be called inside a
read-only database transaction with a cookie-only session hash produced by
backend.auth.build_cookie_session_authentication. No deployment is authorized.
"""
from __future__ import annotations

import re

_SESSION_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_QA_COMPANY_ROLES = frozenset({
    "директор", "зам_директора", "бухгалтер", "прораб",
    "главный_инженер", "сметчик", "кладовщик", "снабженец",
    "стройконтроль", "мастер",
})
_SQL = """
SELECT u.id AS user_id, u.name AS user_name, u.email AS user_email,
       m.company_id, m.id AS membership_id, m.role
  FROM public.user_sessions s
  JOIN public.users u ON u.id=s.user_id
  JOIN public.user_company_roles m ON m.user_id=u.id
  JOIN public.companies c ON c.id=m.company_id
  JOIN public.platform_accounts pa ON pa.id=c.platform_account_id
 WHERE s.session_hash=%s
   AND s.revoked_at IS NULL
   AND s.expires_at>clock_timestamp()
   AND s.two_factor_passed IS TRUE
   AND u.active IS TRUE
   AND m.active IS TRUE
   AND c.active IS TRUE
   AND m.platform_account_id=c.platform_account_id
   AND pa.active IS TRUE
   AND pa.status='active'
 ORDER BY m.id
 LIMIT 2
"""


class QAReadOnlyAuthRejected(ValueError):
    def __init__(self):
        super().__init__("QA_READ_ONLY_AUTH_REJECTED")


def resolve_qa_identity_read_only(cur, authentication: object) -> dict:
    """Read exactly one active membership. Never return session details.

    The caller MUST begin a database READ ONLY transaction; this helper
    alone cannot enforce transaction state or authenticate a raw cookie.
    """
    if (
        type(authentication) is not dict
        or set(authentication) != {"authenticationKind", "sessionHash"}
        or authentication["authenticationKind"] != "cookie_session"
        or type(authentication["sessionHash"]) is not str
        or _SESSION_HASH_RE.fullmatch(authentication["sessionHash"]) is None
    ):
        raise QAReadOnlyAuthRejected()
    try:
        cur.execute(_SQL, (authentication["sessionHash"],))
        rows = cur.fetchall()
        if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
            raise QAReadOnlyAuthRejected()
        row = rows[0]
        for field in ("user_id", "company_id", "membership_id"):
            if type(row.get(field)) is not int or row[field] <= 0:
                raise QAReadOnlyAuthRejected()
        role = row.get("role")
        name = row.get("user_name")
        email = row.get("user_email")
        if (
            type(role) is not str or role not in _QA_COMPANY_ROLES
            or type(name) is not str or type(email) is not str
            or not (name.strip() or email.strip())
        ):
            raise QAReadOnlyAuthRejected()
        cid = row["company_id"]
        return {
            "ok": True,
            "user": {
                "id": row["user_id"], "name": name.strip(),
                "email": email.strip(), "role": role, "companyId": cid,
            },
            "defaultCompanyId": cid,
            "canUseAllCompanies": False,
            "companies": [{
                "source": "membership", "membershipId": row["membership_id"],
                "companyId": cid, "role": role, "active": True,
                "companyActive": True, "readOnly": False,
                "accountLevel": False,
            }],
        }
    except Exception:
        # No DB diagnostics or secret-bearing row values in API errors.
        raise QAReadOnlyAuthRejected() from None
