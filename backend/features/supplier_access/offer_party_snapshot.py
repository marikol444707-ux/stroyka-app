"""Immutable buyer and supplier identity captured on the first sent quotation."""

import json
import re
from datetime import datetime, timezone

from .rfq_requester_snapshot import (
    RfqRequesterSnapshotError,
    requester_snapshot_identity,
    validate_rfq_requester_snapshot,
)


class OfferPartySnapshotError(ValueError):
    pass


_PARTY_FIELDS = (
    "fullName", "shortName", "inn", "kpp", "ogrn", "legalAddress",
    "actualAddress", "phone", "email",
)
_FIELDS = (
    "version", "offerId", "requestId", "companyId", "supplierId", "buyer",
    "supplier", "supplierContact", "frozenAt",
)
_ALIASES = {
    "fullName": ("fullName", "full_name", "name"),
    "shortName": ("shortName", "short_name"),
    "inn": ("inn",),
    "kpp": ("kpp",),
    "ogrn": ("ogrn", "ogrnip"),
    "legalAddress": ("legalAddress", "legal_address"),
    "actualAddress": ("actualAddress", "actual_address"),
    "phone": ("phone", "contact_phone", "contactPhone"),
    "email": ("email", "contact_email", "contactEmail"),
}
_LIMITS = {
    "fullName": 500, "shortName": 255, "legalAddress": 2000,
    "actualAddress": 2000, "phone": 100, "email": 255,
}


def _positive_int(value):
    if isinstance(value, bool):
        raise OfferPartySnapshotError("offer_party_snapshot_invalid")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise OfferPartySnapshotError("offer_party_snapshot_invalid") from exc
    if result <= 0:
        raise OfferPartySnapshotError("offer_party_snapshot_invalid")
    return result


def _text(value, limit=2000, *, required=False):
    result = " ".join(str(value or "").split()).strip()
    if len(result) > limit or (required and not result):
        raise OfferPartySnapshotError("offer_party_snapshot_invalid")
    return result


def _first(source, names):
    source = source if isinstance(source, dict) else {}
    for name in names:
        if name in source and str(source.get(name) or "").strip():
            return source.get(name)
    return ""


def _party(source):
    result = {
        field: _text(_first(source, _ALIASES[field]), _LIMITS.get(field, 100))
        for field in _PARTY_FIELDS
    }
    for field, limit in (("inn", 12), ("kpp", 9), ("ogrn", 15)):
        digits = re.sub(r"\D+", "", result[field])
        if len(digits) > limit:
            raise OfferPartySnapshotError("offer_party_snapshot_invalid")
        result[field] = digits
    result["email"] = result["email"].lower()
    if not result["fullName"]:
        raise OfferPartySnapshotError("offer_party_snapshot_party_name_missing")
    return result


def _contact(source):
    source = source if isinstance(source, dict) else {}
    return {
        "userId": _positive_int(source.get("id")),
        "name": _text(source.get("name"), 255),
        "email": _text(source.get("email"), 255).lower(),
        "phone": _text(source.get("phone"), 100),
    }


def build_offer_party_snapshot(
    *, offer_id, request_id, company_id, supplier_id, buyer, supplier, actor,
    frozen_at,
):
    return {
        "version": 1,
        "offerId": _positive_int(offer_id),
        "requestId": _positive_int(request_id),
        "companyId": _positive_int(company_id),
        "supplierId": _positive_int(supplier_id),
        "buyer": _party(buyer),
        "supplier": _party(supplier),
        "supplierContact": _contact(actor),
        "frozenAt": _text(frozen_at, 40, required=True),
    }


def validate_offer_party_snapshot(
    value, *, offer_id, request_id, company_id, supplier_id,
):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise OfferPartySnapshotError("offer_party_snapshot_invalid") from exc
    if not isinstance(value, dict) or set(value) != set(_FIELDS) or value.get("version") != 1:
        raise OfferPartySnapshotError("offer_party_snapshot_invalid")
    contact = value.get("supplierContact") or {}
    if (
        not isinstance(value.get("buyer"), dict)
        or set(value["buyer"]) != set(_PARTY_FIELDS)
        or not isinstance(value.get("supplier"), dict)
        or set(value["supplier"]) != set(_PARTY_FIELDS)
        or not isinstance(contact, dict)
        or set(contact) != {"userId", "name", "email", "phone"}
    ):
        raise OfferPartySnapshotError("offer_party_snapshot_invalid")
    normalized = build_offer_party_snapshot(
        offer_id=value.get("offerId"), request_id=value.get("requestId"),
        company_id=value.get("companyId"), supplier_id=value.get("supplierId"),
        buyer=value.get("buyer"), supplier=value.get("supplier"),
        actor={"id": contact.get("userId"), "name": contact.get("name"),
               "email": contact.get("email"), "phone": contact.get("phone")},
        frozen_at=value.get("frozenAt"),
    )
    expected = tuple(map(_positive_int, (offer_id, request_id, company_id, supplier_id)))
    actual = tuple(normalized[key] for key in ("offerId", "requestId", "companyId", "supplierId"))
    if actual != expected:
        raise OfferPartySnapshotError("offer_party_snapshot_scope_mismatch")
    return normalized


def freeze_offer_party_snapshot(cursor, offer, actor, *, frozen_at=None):
    offer = dict(offer or {})
    ids = {
        "offer_id": _positive_int(offer.get("id")),
        "request_id": _positive_int(offer.get("request_id")),
        "company_id": _positive_int(offer.get("company_id")),
        "supplier_id": _positive_int(offer.get("supplier_id")),
    }
    existing = offer.get("party_snapshot_json")
    if existing:
        return validate_offer_party_snapshot(existing, **ids)

    cursor.execute(
        """SELECT r.id AS request_id,r.company_id,r.project,r.requester_snapshot_json,
                  c.name AS company_name,c.contact_email,c.contact_phone,
                  q.full_name,q.short_name,q.inn,q.kpp,q.ogrn,q.legal_address,
                  q.actual_address,q.phone,q.email
             FROM supply_requests r
             JOIN companies c ON c.id=r.company_id
             LEFT JOIN company_requisites q ON q.company_id=c.id
            WHERE r.id=%s AND r.company_id=%s FOR SHARE OF r,c""",
        (ids["request_id"], ids["company_id"]),
    )
    buyer_row = cursor.fetchone()
    if not buyer_row:
        raise OfferPartySnapshotError("offer_party_snapshot_buyer_missing")
    buyer = dict(buyer_row)
    requester = buyer.get("requester_snapshot_json") or {}
    if requester:
        try:
            requester = validate_rfq_requester_snapshot(
                requester,
                request_id=buyer.get("request_id"),
                company_id=buyer.get("company_id"),
                project_name=buyer.get("project"),
            )
        except RfqRequesterSnapshotError as exc:
            raise OfferPartySnapshotError("offer_party_snapshot_requester_invalid") from exc
        identity = requester_snapshot_identity(requester)
        buyer["full_name"] = identity.get("companyName") or buyer.get("full_name")
        buyer["email"] = identity.get("companyEmail") or buyer.get("email")
        buyer["phone"] = identity.get("companyPhone") or buyer.get("phone")
    buyer["full_name"] = buyer.get("full_name") or buyer.get("company_name")
    buyer["email"] = buyer.get("email") or buyer.get("contact_email")
    buyer["phone"] = buyer.get("phone") or buyer.get("contact_phone")

    cursor.execute(
        """SELECT name,inn,kpp,ogrn,legal_address,actual_address,phone,email
             FROM suppliers WHERE id=%s FOR SHARE""",
        (ids["supplier_id"],),
    )
    supplier = cursor.fetchone()
    if not supplier:
        raise OfferPartySnapshotError("offer_party_snapshot_supplier_missing")
    snapshot = build_offer_party_snapshot(
        **ids, buyer=buyer, supplier=dict(supplier), actor=actor,
        frozen_at=frozen_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    cursor.execute(
        """UPDATE supplier_offers SET party_snapshot_json=%s::jsonb
            WHERE id=%s AND request_id=%s AND company_id=%s AND supplier_id=%s
              AND party_snapshot_json IS NULL""",
        (json.dumps(snapshot, ensure_ascii=False, sort_keys=True), ids["offer_id"],
         ids["request_id"], ids["company_id"], ids["supplier_id"]),
    )
    if cursor.rowcount == 1:
        return snapshot
    cursor.execute(
        """SELECT party_snapshot_json FROM supplier_offers
            WHERE id=%s AND request_id=%s AND company_id=%s AND supplier_id=%s FOR UPDATE""",
        (ids["offer_id"], ids["request_id"], ids["company_id"], ids["supplier_id"]),
    )
    row = cursor.fetchone() or {}
    return validate_offer_party_snapshot(row.get("party_snapshot_json"), **ids)
