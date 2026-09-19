"""Resolve billing ownership for the supplier's addressed offer mutations.

Suppliers are external to the customer's workforce. Their access comes from the
canonical offer/recipient boundary, never from a selected company header.
"""

import re

from fastapi import HTTPException


_OFFER_MUTATION_PATH = re.compile(
    r"^/supplier-offers/([1-9][0-9]*)(/create-invoice|/ship)?/?$"
)


def is_owned_supplier_profile_mutation(cur, user, method, path):
    """A supplier's public profile does not consume a customer's subscription."""
    if user.get('role') == 'поставщик' and str(method).upper() == 'POST':
        team_match = re.fullmatch(r'/supplier-team/([1-9][0-9]*)/commands/?', str(path))
        if team_match:
            from ..supplier_team.policy import enabled, customer_assignments_enabled, leader_policy
            if not enabled() or not customer_assignments_enabled():
                return False
            sql, params = leader_policy(user.get('id'), 's.id')
            cur.execute('SELECT s.id FROM suppliers s WHERE s.id=%s AND '+sql,
                        [int(team_match.group(1))]+params)
            return bool(cur.fetchone())
    if user.get('role') != 'поставщик' or str(method).upper() != 'PUT':
        return False
    match = re.fullmatch(r'/suppliers/([1-9][0-9]*)/requisites/?', str(path))
    if not match:
        return False
    cur.execute('SELECT id FROM suppliers WHERE id=%s AND user_id=%s', (int(match.group(1)), user.get('id')))
    return bool(cur.fetchone())


def resolve_supplier_offer_subscription_context(
    cur, user, method, path, *, require_supplier_offer_visibility,
):
    """Return None outside these routes; otherwise authorize before ownership.

    The caller still checks the returned company's subscription. The business
    route retains its own action, recipient, and tenant authorization checks.
    """
    if (user or {}).get("role") != "поставщик":
        return None
    claim_match = re.fullmatch(r'/supply-claims/([1-9][0-9]*)(/case)?/?', str(path or ''))
    if claim_match and str(method or '').upper() == ('POST' if claim_match.group(2) else 'PUT'):
        cur.execute('''SELECT d.company_id,d.offer_id FROM supply_claims c
            JOIN supply_deliveries d ON d.id=c.delivery_id AND d.request_id=c.request_id
              AND d.offer_id=c.offer_id AND d.supplier_id=c.supplier_id AND d.project=c.project
            JOIN supplier_offers o ON o.id=d.offer_id AND o.company_id=d.company_id
              AND o.supplier_id=d.supplier_id AND o.request_id=d.request_id
            JOIN supply_requests r ON r.id=o.request_id AND r.company_id=o.company_id
              AND r.project=d.project WHERE c.id=%s''', (int(claim_match.group(1)),))
        claim = cur.fetchone()
        if not claim:
            raise HTTPException(403, 'Нет доступа к претензии')
        require_supplier_offer_visibility(cur, claim['offer_id'], user)
        return {'mode': 'company', 'companyId': claim['company_id']}
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
