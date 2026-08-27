"""Pure deterministic plan for safe supplier/warehouse document link repair."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
import unicodedata

from backend.features.warehouse_receipts.duplicate_guard import (
    normalize_invoice_date,
    normalize_invoice_number,
)


PLAN_VERSION = "accounting-exception-link-repair-v2"
MAX_SOURCE_ROWS = 1000
MAX_REPAIRS = 100
_PROOFS = ("reciprocal", "delivery", "request", "identity")
_INPUT_INVALID = "accounting_link_repair_plan_input_invalid"
_LIMIT_EXCEEDED = "accounting_link_repair_plan_limit_exceeded"
_PLAN_LIMIT_BLOCKER = "accounting_link_repair_plan_too_large"
_SUPPLIER_ANNULLED = "Аннулирован"
_WAREHOUSE_ANNULLED = "Аннулирована"
_DELIVERY_INACTIVE = frozenset({"Аннулировано", "Отклонено"})


class LinkRepairPlanError(ValueError):
    """Fixed pure-contract error without source data disclosure."""

    def __init__(self, code):
        self.code = code if code in {_INPUT_INVALID, _LIMIT_EXCEEDED} else _INPUT_INVALID
        super().__init__(self.code)


@dataclass(frozen=True)
class LinkRepair:
    company_id: int
    project_id: int
    supplier_invoice_id: int
    warehouse_invoice_id: int
    proof: str

    def canonical(self):
        return {
            "companyId": self.company_id,
            "projectId": self.project_id,
            "proof": self.proof,
            "supplierInvoiceId": self.supplier_invoice_id,
            "warehouseInvoiceId": self.warehouse_invoice_id,
        }


@dataclass(frozen=True)
class LinkRepairPlan:
    company_id: int
    state: str
    repairs: tuple
    unresolved_count: int
    proof_counts: dict
    plan_sha256: str
    blockers: tuple

    def public_result(self):
        return {
            "version": PLAN_VERSION,
            "companyId": self.company_id,
            "state": self.state,
            "repairCount": len(self.repairs),
            "unresolvedCount": self.unresolved_count,
            "proofCounts": {
                proof: self.proof_counts[proof] for proof in _PROOFS
            },
            "planSha256": self.plan_sha256,
            "blockers": list(self.blockers),
        }


def _fail(code=_INPUT_INVALID):
    raise LinkRepairPlanError(code) from None


def _positive_int(value, *, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or value <= 0 or value > 9223372036854775807:
        _fail()
    return value


def _text(value, *, limit=255):
    if type(value) is not str or len(value.encode("utf-8")) > limit:
        _fail()
    return value.strip()


def _money(value):
    if type(value) is int:
        value = Decimal(value)
    if type(value) is not Decimal or not value.is_finite() or value < 0:
        _fail()
    return value


def _rows(value):
    if type(value) not in (list, tuple):
        _fail()
    if len(value) > MAX_SOURCE_ROWS:
        _fail(_LIMIT_EXCEEDED)
    return value


def _row(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        _fail()
    return value


def _supplier_name_key(value):
    value = unicodedata.normalize("NFKC", _text(value)).casefold().replace("ё", "е")
    value = re.sub(r"[\"'«»„“”`]+", "", value)
    return " ".join(re.sub(r"[^0-9a-zа-я]+", " ", value).split())


def _normalize_projects(rows):
    clean = []
    fields = {"id", "company_id", "name"}
    for raw in _rows(rows):
        row = _row(raw, fields)
        clean.append({
            "id": _positive_int(row["id"]),
            "company_id": _positive_int(row["company_id"]),
            "name": _text(row["name"]),
        })
    return clean


def _normalize_supplier_invoices(rows):
    clean = []
    fields = {
        "id", "company_id", "supplier_id", "supplier_name", "project_name",
        "amount", "offer_id", "request_id", "warehouse_invoice_id", "status",
        "invoice_number", "invoice_date",
    }
    for raw in _rows(rows):
        row = _row(raw, fields)
        clean.append({
            "id": _positive_int(row["id"]),
            "company_id": _positive_int(row["company_id"]),
            "supplier_id": _positive_int(row["supplier_id"], optional=True),
            "supplier_name": _text(row["supplier_name"]),
            "project_name": _text(row["project_name"]),
            "amount": _money(row["amount"]),
            "offer_id": _positive_int(row["offer_id"], optional=True),
            "request_id": _positive_int(row["request_id"], optional=True),
            "warehouse_invoice_id": _positive_int(
                row["warehouse_invoice_id"], optional=True,
            ),
            "invoice_number": _text(row["invoice_number"], limit=512),
            "invoice_date": _text(row["invoice_date"], limit=32),
            "status": _text(row["status"], limit=100),
        })
    return clean


def _normalize_warehouse_invoices(rows):
    clean = []
    fields = {
        "id", "company_id", "supplier_id", "supplier_name", "project",
        "total_with_vat", "total_base", "supply_delivery_id",
        "supply_request_id", "supplier_invoice_id", "status", "number", "date",
    }
    for raw in _rows(rows):
        row = _row(raw, fields)
        clean.append({
            "id": _positive_int(row["id"]),
            "company_id": _positive_int(row["company_id"]),
            "supplier_id": _positive_int(row["supplier_id"], optional=True),
            "supplier_name": _text(row["supplier_name"]),
            "project": _text(row["project"]),
            "total_with_vat": _money(row["total_with_vat"]),
            "total_base": _money(row["total_base"]),
            "supply_delivery_id": _positive_int(
                row["supply_delivery_id"], optional=True,
            ),
            "supply_request_id": _positive_int(
                row["supply_request_id"], optional=True,
            ),
            "supplier_invoice_id": _positive_int(
                row["supplier_invoice_id"], optional=True,
            ),
            "number": _text(row["number"], limit=512),
            "date": _text(row["date"], limit=32),
            "status": _text(row["status"], limit=100),
        })
    return clean


def _normalize_deliveries(rows):
    clean = []
    fields = {
        "id", "company_id", "offer_id", "request_id", "supplier_id",
        "supplier_name", "project", "status",
    }
    for raw in _rows(rows):
        row = _row(raw, fields)
        clean.append({
            "id": _positive_int(row["id"]),
            "company_id": _positive_int(row["company_id"]),
            "offer_id": _positive_int(row["offer_id"], optional=True),
            "request_id": _positive_int(row["request_id"], optional=True),
            "supplier_id": _positive_int(row["supplier_id"], optional=True),
            "supplier_name": _text(row["supplier_name"]),
            "project": _text(row["project"]),
            "status": _text(row["status"], limit=100),
        })
    return clean


def _unique_by_id(rows):
    result = {}
    for row in rows:
        if row["id"] in result:
            _fail()
        result[row["id"]] = row
    return result


def _project_map(projects, company_id):
    grouped = {}
    for row in projects:
        if row["company_id"] != company_id or not row["name"]:
            continue
        grouped.setdefault(row["name"], []).append(row["id"])
    return {
        name: ids[0]
        for name, ids in grouped.items()
        if len(ids) == 1
    }


def _same_supplier(left, right):
    left_id = left["supplier_id"]
    right_id = right["supplier_id"]
    if left_id is not None or right_id is not None:
        return left_id is not None and left_id == right_id
    left_name = _supplier_name_key(left["supplier_name"])
    right_name = _supplier_name_key(right["supplier_name"])
    return bool(left_name and left_name == right_name)


def _live_supplier(row, company_id):
    return row["company_id"] == company_id and row["status"] != _SUPPLIER_ANNULLED


def _live_warehouse(row, company_id):
    return row["company_id"] == company_id and row["status"] != _WAREHOUSE_ANNULLED


def _live_delivery(row, company_id):
    return row["company_id"] == company_id and row["status"] not in _DELIVERY_INACTIVE


def _warehouse_amount(row):
    return row["total_with_vat"] or row["total_base"]


def _pair_scope(supplier, warehouse, project_ids, company_id):
    if not (_live_supplier(supplier, company_id) and _live_warehouse(warehouse, company_id)):
        return None
    supplier_project = project_ids.get(supplier["project_name"])
    warehouse_project = project_ids.get(warehouse["project"])
    if supplier_project is None or supplier_project != warehouse_project:
        return None
    if not _same_supplier(supplier, warehouse):
        return None
    return supplier_project


def _link_is_compatible(supplier, warehouse, live_suppliers, live_warehouses):
    supplier_link = supplier["warehouse_invoice_id"]
    if supplier_link is not None and supplier_link != warehouse["id"]:
        if supplier_link in live_warehouses:
            return False
    warehouse_link = warehouse["supplier_invoice_id"]
    if warehouse_link is not None and warehouse_link != supplier["id"]:
        if warehouse_link in live_suppliers:
            return False
    return True


def _delivery_matches(supplier, warehouse, delivery):
    if warehouse["supply_delivery_id"] != delivery["id"]:
        return False
    lineage_matches = (
        supplier["offer_id"] is not None
        and supplier["offer_id"] == delivery["offer_id"]
    ) or (
        supplier["request_id"] is not None
        and supplier["request_id"] == delivery["request_id"]
    )
    return (
        lineage_matches
        and supplier["project_name"] == delivery["project"]
        and _same_supplier(supplier, delivery)
        and _same_supplier(warehouse, delivery)
    )


def _request_matches(supplier, warehouse):
    return (
        supplier["request_id"] is not None
        and supplier["request_id"] == warehouse["supply_request_id"]
    )


def _document_date_key(value):
    normalized = normalize_invoice_date(value)
    try:
        return date.fromisoformat(normalized).isoformat()
    except (TypeError, ValueError):
        return ""


def _identity_matches(supplier, warehouse):
    supplier_number = normalize_invoice_number(supplier["invoice_number"])
    warehouse_number = normalize_invoice_number(warehouse["number"])
    supplier_date = _document_date_key(supplier["invoice_date"])
    warehouse_date = _document_date_key(warehouse["date"])
    amount = supplier["amount"]
    return (
        bool(supplier_number)
        and supplier_number == warehouse_number
        and bool(supplier_date)
        and supplier_date == warehouse_date
        and amount > 0
        and amount == _warehouse_amount(warehouse)
    )


def _proof_candidates(
    supplier,
    warehouses,
    deliveries,
    project_ids,
    company_id,
    live_suppliers,
    live_warehouses,
):
    def compatible(warehouse):
        return (
            _pair_scope(supplier, warehouse, project_ids, company_id) is not None
            and _link_is_compatible(
                supplier, warehouse, live_suppliers, live_warehouses,
            )
        )

    direct = [
        warehouse for warehouse in warehouses
        if compatible(warehouse)
        and (
            (
                warehouse["id"] == supplier["warehouse_invoice_id"]
                and warehouse["supplier_invoice_id"] in (None, supplier["id"])
            )
            or (
                warehouse["supplier_invoice_id"] == supplier["id"]
                and supplier["warehouse_invoice_id"] in (None, warehouse["id"])
            )
        )
    ]
    if len(direct) == 1:
        return "reciprocal", direct

    delivery_by_id = {row["id"]: row for row in deliveries}
    delivery_matches = []
    for warehouse in warehouses:
        delivery = delivery_by_id.get(warehouse["supply_delivery_id"])
        if (
            delivery is not None
            and _live_delivery(delivery, company_id)
            and compatible(warehouse)
            and _delivery_matches(supplier, warehouse, delivery)
        ):
            delivery_matches.append(warehouse)
    if len(delivery_matches) == 1:
        return "delivery", delivery_matches
    if len(delivery_matches) > 1:
        return None, []

    request_matches = [
        warehouse for warehouse in warehouses
        if compatible(warehouse) and _request_matches(supplier, warehouse)
    ]
    if len(request_matches) > 1:
        request_matches = [
            warehouse for warehouse in request_matches
            if supplier["amount"] > 0
            and supplier["amount"] == _warehouse_amount(warehouse)
        ]
    if len(request_matches) == 1:
        return "request", request_matches

    identity_matches = [
        warehouse for warehouse in warehouses
        if compatible(warehouse) and _identity_matches(supplier, warehouse)
    ]
    if len(identity_matches) == 1:
        return "identity", identity_matches
    return None, []


def _broken_subjects(suppliers, warehouses, supplier_by_id, warehouse_by_id):
    broken = set()
    for supplier in suppliers:
        warehouse_id = supplier["warehouse_invoice_id"]
        if warehouse_id is None:
            continue
        warehouse = warehouse_by_id.get(warehouse_id)
        if warehouse is None or warehouse["supplier_invoice_id"] != supplier["id"]:
            broken.add(("supplier_invoice", supplier["id"]))
    for warehouse in warehouses:
        supplier_id = warehouse["supplier_invoice_id"]
        if supplier_id is None:
            continue
        supplier = supplier_by_id.get(supplier_id)
        if supplier is None or supplier["warehouse_invoice_id"] != warehouse["id"]:
            broken.add(("warehouse_invoice", warehouse["id"]))
    return broken


def _canonical_sha(company_id, repairs):
    payload = {
        "companyId": company_id,
        "repairs": [repair.canonical() for repair in repairs],
        "version": PLAN_VERSION,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_accounting_link_repair_plan(
    *,
    company_id,
    projects,
    supplier_invoices,
    warehouse_invoices,
    deliveries,
):
    """Build one immutable, ordered, company-scoped repair plan."""

    company_id = _positive_int(company_id)
    projects = _normalize_projects(projects)
    suppliers = _normalize_supplier_invoices(supplier_invoices)
    warehouses = _normalize_warehouse_invoices(warehouse_invoices)
    deliveries = _normalize_deliveries(deliveries)
    _unique_by_id(projects)
    _unique_by_id(suppliers)
    _unique_by_id(warehouses)
    _unique_by_id(deliveries)

    project_ids = _project_map(projects, company_id)
    live_suppliers = {
        row["id"]: row for row in suppliers if _live_supplier(row, company_id)
    }
    live_warehouses = {
        row["id"]: row for row in warehouses if _live_warehouse(row, company_id)
    }
    selected_deliveries = [
        row for row in deliveries if _live_delivery(row, company_id)
    ]
    broken = _broken_subjects(
        tuple(live_suppliers.values()),
        tuple(live_warehouses.values()),
        live_suppliers,
        live_warehouses,
    )

    proposed = {}
    resolved_by_pair = {}
    for kind, subject_id in sorted(broken):
        supplier_candidates = []
        if kind == "supplier_invoice":
            supplier = live_suppliers.get(subject_id)
            if supplier is not None:
                supplier_candidates = [supplier]
        else:
            warehouse = live_warehouses.get(subject_id)
            if warehouse is not None:
                supplier_candidates = [
                    supplier for supplier in live_suppliers.values()
                    if supplier["id"] == warehouse["supplier_invoice_id"]
                ]
                if not supplier_candidates:
                    supplier_candidates = list(live_suppliers.values())

        subject_results = []
        for supplier in supplier_candidates:
            proof, candidates = _proof_candidates(
                supplier,
                tuple(live_warehouses.values()),
                selected_deliveries,
                project_ids,
                company_id,
                live_suppliers,
                live_warehouses,
            )
            for warehouse in candidates:
                if (
                    kind == "warehouse_invoice"
                    and warehouse["id"] != subject_id
                ):
                    continue
                project_id = _pair_scope(
                    supplier, warehouse, project_ids, company_id,
                )
                if proof and project_id:
                    subject_results.append(LinkRepair(
                        company_id=company_id,
                        project_id=project_id,
                        supplier_invoice_id=supplier["id"],
                        warehouse_invoice_id=warehouse["id"],
                        proof=proof,
                    ))
        unique = {
            (item.supplier_invoice_id, item.warehouse_invoice_id): item
            for item in subject_results
        }
        if len(unique) == 1:
            pair, repair = next(iter(unique.items()))
            proposed[pair] = repair
            resolved_by_pair.setdefault(pair, set()).add((kind, subject_id))

    supplier_pairs = {}
    warehouse_pairs = {}
    for pair in proposed:
        supplier_pairs.setdefault(pair[0], []).append(pair)
        warehouse_pairs.setdefault(pair[1], []).append(pair)
    valid_pairs = {
        pair for pair in proposed
        if len(supplier_pairs[pair[0]]) == 1
        and len(warehouse_pairs[pair[1]]) == 1
    }
    repairs = tuple(sorted(
        (proposed[pair] for pair in valid_pairs),
        key=lambda item: (item.supplier_invoice_id, item.warehouse_invoice_id),
    ))
    resolved = set()
    for pair in valid_pairs:
        resolved.update(resolved_by_pair[pair])
    unresolved_count = len(broken - resolved)

    if len(repairs) > MAX_REPAIRS:
        repairs = ()
        blockers = (_PLAN_LIMIT_BLOCKER,)
        state = "blocked"
        unresolved_count = len(broken)
    else:
        blockers = ()
        state = "ready" if repairs else "clear"
    proof_counts = {
        proof: sum(repair.proof == proof for repair in repairs)
        for proof in _PROOFS
    }
    return LinkRepairPlan(
        company_id=company_id,
        state=state,
        repairs=repairs,
        unresolved_count=unresolved_count,
        proof_counts=proof_counts,
        plan_sha256=_canonical_sha(company_id, repairs),
        blockers=blockers,
    )


__all__ = []
