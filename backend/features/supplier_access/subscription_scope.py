"""Resolve billing ownership for the supplier's addressed offer mutations.

Suppliers are external to the customer's workforce. Their access comes from the
canonical offer/recipient boundary, never from a selected company header.
"""

import re

from fastapi import HTTPException


_OFFER_MUTATION_PATH = re.compile(
    r"^/supplier-offers/([1-9][0-9]*)(/create-invoice|/ship)?/?$"
)


def resolve_supplier_offer_subscription_context(
    cur, user, method, path, *, require_supplier_offer_visibility,
):
    """Return None outside these routes; otherwise authorize before ownership.

    The caller still checks the returned company's subscription. The business
    route retains its own action, recipient, and tenant authorization checks.
    """
    if (user or {}).get("role") != "поставщик":
        return None
    match = _OFFER_MUTATION_PATH.fullmatch(str(path or ""))
    if not match:
        return None
    expected_method = "POST" if match.group(2) else "PUT"
    if str(method or "").upper() != expected_method:
        return None

    offer_id = int(match.group(1))
    require_supplier_offer_visibility(cur, offer_id, user)
    cur.execute(
        """SELECT offer.company_id, request.company_id AS request_company_id
             FROM supplier_offers offer
             JOIN supply_requests request ON request.id=offer.request_id
            WHERE offer.id=%s""",
        (offer_id,),
    )
    row = cur.fetchone()
    company_id = int((row or {}).get("company_id") or 0)
    request_company_id = int((row or {}).get("request_company_id") or 0)
    if company_id <= 0 or company_id != request_company_id:
        raise HTTPException(status_code=409, detail="Компания КП и заявки не определена однозначно")
    return {"mode": "company", "companyId": company_id}
