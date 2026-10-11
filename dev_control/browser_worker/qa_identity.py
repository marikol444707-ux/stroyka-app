"""Strict QA-only projection of a server-validated company-context response.

This module NEVER authenticates by itself. Callers must first GET the existing
/api/users/qa-readonly-context/identity endpoint in the isolated QA BrowserContext using its
HttpOnly session cookie and validate the response status, origin and TLS.
Until that flow is wired end-to-end, the worker remains AUTH_NOT_ESTABLISHED.
Do not persist tokens, session hashes or fabricated user/company identities.
"""
from __future__ import annotations

from urllib.parse import urlsplit


class QAIdentityNotEstablished(ValueError):
    def __init__(self):
        super().__init__("AUTH_NOT_ESTABLISHED")


def _positive_int(value):
    if type(value) is int and value > 0:
        return value
    raise QAIdentityNotEstablished()


def project_qa_user(payload: object) -> dict:
    """Accept only a single active, explicit company membership.

    Reject platform/all-company, account-level, ambiguous, inactive or
    incomplete responses. This is deliberately narrower than production
    company switching and is not an authorization grant.
    """
    if type(payload) is not dict or payload.get("ok") is not True:
        raise QAIdentityNotEstablished()
    user = payload.get("user")
    companies = payload.get("companies")
    if type(user) is not dict or type(companies) is not list or len(companies) != 1:
        raise QAIdentityNotEstablished()
    company = companies[0]
    if type(company) is not dict:
        raise QAIdentityNotEstablished()
    if company.get("source") != "membership" or company.get("accountLevel") is not False:
        raise QAIdentityNotEstablished()
    if company.get("active") is not True or company.get("companyActive") is not True:
        raise QAIdentityNotEstablished()
    if company.get("readOnly") is not False:
        raise QAIdentityNotEstablished()
    uid = _positive_int(user.get("id"))
    cid = _positive_int(company.get("companyId"))
    _positive_int(company.get("membershipId"))
    if _positive_int(user.get("companyId")) != cid:
        raise QAIdentityNotEstablished()
    if _positive_int(payload.get("defaultCompanyId")) != cid:
        raise QAIdentityNotEstablished()
    if payload.get("canUseAllCompanies") is not False:
        raise QAIdentityNotEstablished()
    role = user.get("role")
    if type(role) is not str or not role or role != role.strip() or company.get("role") != role:
        raise QAIdentityNotEstablished()
    name = user.get("name")
    email = user.get("email")
    if type(name) is not str or type(email) is not str or not (name.strip() or email.strip()):
        raise QAIdentityNotEstablished()
    if any(key in user for key in ("authToken", "token", "password", "session", "sessionHash")):
        raise QAIdentityNotEstablished()
    return {
        "id": uid,
        "companyId": cid,
        "role": role,
        "name": name.strip(),
        "email": email.strip(),
    }

def verify_qa_identity_http_response(
    *, base_url: str, response_url: str, status: int,
    content_type: str, payload: object,
) -> dict:
    """Fail closed unless the exact authenticated QA context GET returned 200.

    The caller must fetch in the SAME isolated Chrome BrowserContext with its
    HttpOnly cookie. This helper does not fetch, authenticate, or grant access.
    Redirected login HTML and foreign-origin responses must never be accepted.
    """
    try:
        base = urlsplit(base_url)
        target = urlsplit(response_url)
        if (
            base.scheme != "https"
            or not base.hostname
            or base.username is not None
            or base.password is not None
            or base.query or base.fragment
            or target.scheme != "https"
            or target.username is not None
            or target.password is not None
            or target.query or target.fragment
            or target.path != "/api/users/qa-readonly-context/identity"
            or (base.scheme, base.hostname.lower().rstrip("."), base.port or 443)
               != (target.scheme, (target.hostname or "").lower().rstrip("."), target.port or 443)
            or type(status) is not int or status != 200
            or type(content_type) is not str
            or content_type.split(";", 1)[0].strip().lower() != "application/json"
        ):
            raise QAIdentityNotEstablished()
    except (ValueError, TypeError) as exc:
        raise QAIdentityNotEstablished() from None
    return project_qa_user(payload)

# Execute only in a CDP-created isolated world, never in the app's main JS
# world. No cookie, token or personal data is included in the script.
_QA_IDENTITY_FETCH_JS = r"""(async () => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch('/api/users/qa-readonly-context/identity', {
      method: 'GET', credentials: 'same-origin', redirect: 'error',
      cache: 'no-store', signal: controller.signal,
    });
    const type = response.headers.get('content-type') || '';
    const length = Number(response.headers.get('content-length') || '0');
    if (length > 16384) throw Error('oversize');
    const body = await response.text();
    if (body.length > 16384) throw Error('oversize');
    return {
      status: response.status,
      url: response.url,
      content_type: type,
      payload: JSON.parse(body),
    };
  } finally { clearTimeout(timer); }
})()"""


def verify_qa_identity_in_browser(browser, base_url: str) -> bool:
    """Validate session against QA backend using a CDP isolated world.

    Must be invoked only after navigation to the exact allowed QA origin,
    with Fetch network guard already active and an injected HttpOnly cookie.
    Return only a boolean to the caller; never persist the user projection.
    """
    try:
        tree = browser.call("Page.getFrameTree")
        frame_id = tree["frameTree"]["frame"]["id"]
        world = browser.call(
            "Page.createIsolatedWorld",
            frameId=frame_id,
            worldName="stroyka-qa-session-probe",
            grantUniveralAccess=False,
        )
        result = browser.call(
            "Runtime.evaluate",
            contextId=world["executionContextId"],
            expression=_QA_IDENTITY_FETCH_JS,
            awaitPromise=True,
            returnByValue=True,
            timeout=10000,
        )
        if result.get("exceptionDetails"):
            raise QAIdentityNotEstablished()
        value = result["result"]["value"]
        if type(value) is not dict:
            raise QAIdentityNotEstablished()
        verify_qa_identity_http_response(
            base_url=base_url,
            response_url=value.get("url"),
            status=value.get("status"),
            content_type=value.get("content_type"),
            payload=value.get("payload"),
        )
        return True
    except Exception:
        # Never include exception details: CDP/browser errors may contain
        # URLs, response text, cookies or other secret-bearing values.
        raise QAIdentityNotEstablished() from None
