"""Immutable requester identity projected when an approved RFQ is dispatched."""

import json
from datetime import datetime, timezone


class RfqRequesterSnapshotError(ValueError):
    pass


_FIELDS = (
    "version", "requestId", "companyId", "companyName", "companyEmail",
    "companyPhone", "contactUserId", "contactName", "contactEmail",
    "contactPhone", "projectId", "projectName", "deliveryAddress", "frozenAt",
)


def _positive_int(value, *, optional=False):
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid") from exc
    if result <= 0:
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid")
    return result


def _text(value, limit, *, required=False):
    result = " ".join(str(value or "").split()).strip()
    if len(result) > limit or (required and not result):
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid")
    return result


def _first(source, *keys):
    source = source if isinstance(source, dict) else {}
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def build_rfq_requester_snapshot(
    *, request_id, company_id, project_id, project_name, delivery_address,
    company, actor, frozen_at,
):
    company = company if isinstance(company, dict) else {}
    actor = actor if isinstance(actor, dict) else {}
    company_name = _first(company, "short_name", "shortName", "full_name", "fullName", "name")
    return {
        "version": 1,
        "requestId": _positive_int(request_id),
        "companyId": _positive_int(company_id),
        "companyName": _text(company_name, 500, required=True),
        "companyEmail": _text(_first(company, "email", "contact_email", "contactEmail"), 255),
        "companyPhone": _text(_first(company, "phone", "contact_phone", "contactPhone"), 100),
        "contactUserId": _positive_int(actor.get("id")),
        "contactName": _text(_first(actor, "name"), 255),
        "contactEmail": _text(_first(actor, "email"), 255),
        "contactPhone": _text(_first(actor, "phone"), 100),
        "projectId": _positive_int(project_id, optional=True),
        "projectName": _text(project_name, 255, required=True),
        "deliveryAddress": _text(delivery_address, 2000),
        "frozenAt": _text(frozen_at, 40, required=True),
    }


def validate_rfq_requester_snapshot(value, *, request_id, company_id, project_name):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid") from exc
    if not isinstance(value, dict) or set(value) != set(_FIELDS) or value.get("version") != 1:
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_invalid")
    normalized = build_rfq_requester_snapshot(
        request_id=value.get("requestId"),
        company_id=value.get("companyId"),
        project_id=value.get("projectId"),
        project_name=value.get("projectName"),
        delivery_address=value.get("deliveryAddress"),
        company={
            "short_name": value.get("companyName"),
            "email": value.get("companyEmail"),
            "phone": value.get("companyPhone"),
        },
        actor={
            "id": value.get("contactUserId"),
            "name": value.get("contactName"),
            "email": value.get("contactEmail"),
            "phone": value.get("contactPhone"),
        },
        frozen_at=value.get("frozenAt"),
    )
    if (
        normalized["requestId"] != _positive_int(request_id)
        or normalized["companyId"] != _positive_int(company_id)
        or normalized["projectName"] != _text(project_name, 255, required=True)
    ):
        raise RfqRequesterSnapshotError("rfq_requester_snapshot_scope_mismatch")
    return normalized


def requester_snapshot_identity(snapshot):
    return {
        "companyName": snapshot["companyName"],
        "companyEmail": snapshot["companyEmail"],
        "companyPhone": snapshot["companyPhone"],
        "contactName": snapshot["contactName"],
        "contactEmail": snapshot["contactEmail"],
        "contactPhone": snapshot["contactPhone"],
        "project": snapshot["projectName"],
        "deliveryAddress": snapshot["deliveryAddress"],
    }


def freeze_rfq_requester_snapshot(cursor, request, actor, *, frozen_at=None):
    request = request if isinstance(request, dict) else dict(request or {})
    request_id = _positive_int(request.get("id"))
    company_id = _positive_int(request.get("company_id"))
    project_name = _text(request.get("project"), 255, required=True)
    existing = request.get("requester_snapshot_json")
    if existing:
        return validate_rfq_requester_snapshot(
            existing,
            request_id=request_id,
            company_id=company_id,
            project_name=project_name,
        )

    project_id = None
    if project_name != "Основной склад":
        cursor.execute(
            "SELECT id FROM projects WHERE company_id=%s AND BTRIM(name)=BTRIM(%s) "
            "AND COALESCE(archived,FALSE)=FALSE ORDER BY id FOR SHARE",
            (company_id, project_name),
        )
        projects = list(cursor.fetchall() or [])
        if len(projects) != 1:
            raise RfqRequesterSnapshotError("rfq_requester_project_ambiguous")
        project_id = _positive_int(projects[0].get("id"))

    cursor.execute(
        """SELECT c.name,c.contact_email,c.contact_phone,
                  r.full_name,r.short_name,r.email,r.phone
             FROM companies c
             LEFT JOIN company_requisites r ON r.company_id=c.id
            WHERE c.id=%s
            FOR SHARE OF c""",
        (company_id,),
    )
    company = cursor.fetchone()
    if not company:
        raise RfqRequesterSnapshotError("rfq_requester_company_missing")
    source = dict(company)
    source["email"] = _first(source, "email", "contact_email")
    source["phone"] = _first(source, "phone", "contact_phone")
    snapshot = build_rfq_requester_snapshot(
        request_id=request_id,
        company_id=company_id,
        project_id=project_id,
        project_name=project_name,
        delivery_address=request.get("delivery_address"),
        company=source,
        actor=actor,
        frozen_at=frozen_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    cursor.execute(
        """UPDATE supply_requests
              SET requester_snapshot_json=%s::jsonb
            WHERE id=%s AND company_id=%s AND requester_snapshot_json IS NULL""",
        (json.dumps(snapshot, ensure_ascii=False, sort_keys=True), request_id, company_id),
    )
    if cursor.rowcount == 1:
        return snapshot
    cursor.execute(
        "SELECT requester_snapshot_json FROM supply_requests WHERE id=%s AND company_id=%s FOR UPDATE",
        (request_id, company_id),
    )
    current = cursor.fetchone() or {}
    return validate_rfq_requester_snapshot(
        current.get("requester_snapshot_json"),
        request_id=request_id,
        company_id=company_id,
        project_name=project_name,
    )
