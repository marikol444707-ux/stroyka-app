"""Read-only cutover readiness report for the complete E4 transfer ledger."""

import argparse
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

import psycopg2.extras

from .cutover_inventory import audit_cutover_inventory
from .plan import calculate_plan_sha256
from .schema import _load_catalog, build_schema_plan
from .storage import ENTRY_SELECT, PLAN_SELECT, _stored_payload


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_ISSUES = 100
MAX_PLAN_PREVIEW = 100

_ASSIGNMENT_RECEIPT_SELECT = """SELECT id,entry_id,plan_id,company_id,project_id,
       plan_sha256,transfer_quantity
  FROM public.estimate_row_assignment_transfers"""
_SUPPLY_ALLOCATION_SELECT = """SELECT id,entry_id,plan_id,company_id,project_id,
       plan_sha256,allocation_quantity
  FROM public.estimate_row_supply_allocations"""


def normalize_cutover_scope(plan_id=None, expected_plan_sha256=None):
    if plan_id is None and expected_plan_sha256 is None:
        return {"planId": None, "expectedPlanSha256": None}
    if (
        not isinstance(plan_id, int)
        or isinstance(plan_id, bool)
        or plan_id <= 0
        or not isinstance(expected_plan_sha256, str)
        or not _SHA256_RE.fullmatch(expected_plan_sha256)
    ):
        raise ValueError("cutover_scope_invalid")
    return {"planId": plan_id, "expectedPlanSha256": expected_plan_sha256}


def _decimal(value):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


class _Issues:
    def __init__(self, maximum):
        self.maximum = maximum
        self.count = 0
        self.preview = []

    def add(self, reason_code, *, plan_id=None, entry_id=None, receipt_id=None):
        self.count += 1
        if len(self.preview) >= self.maximum:
            return
        item = {"reasonCode": reason_code}
        if isinstance(plan_id, int) and not isinstance(plan_id, bool):
            item["planId"] = plan_id
        if isinstance(entry_id, int) and not isinstance(entry_id, bool):
            item["entryId"] = entry_id
        if isinstance(receipt_id, int) and not isinstance(receipt_id, bool):
            item["receiptId"] = receipt_id
        self.preview.append(item)


def _receipt_issues(
    *,
    kind,
    header,
    entries,
    receipts,
    quantity_column,
    issues,
):
    plan_id = header.get("id")
    entry_by_id = {row.get("id"): row for row in entries}
    seen = Counter()
    valid_count = 0
    for receipt in receipts:
        entry_id = receipt.get("entry_id")
        receipt_id = receipt.get("id")
        entry = entry_by_id.get(entry_id)
        seen[entry_id] += 1
        if entry is None or entry.get("source_kind") != kind:
            issues.add(
                kind + "_receipt_entry_mismatch",
                plan_id=plan_id,
                entry_id=entry_id,
                receipt_id=receipt_id,
            )
            continue
        valid_count += 1
        if (
            receipt.get("plan_id") != plan_id
            or receipt.get("company_id") != header.get("company_id")
            or receipt.get("project_id") != header.get("project_id")
            or receipt.get("plan_sha256") != header.get("plan_sha256")
        ):
            issues.add(
                kind + "_receipt_owner_mismatch",
                plan_id=plan_id,
                entry_id=entry_id,
                receipt_id=receipt_id,
            )
        planned_quantity = _decimal(entry.get("quantity"))
        receipt_quantity = _decimal(receipt.get(quantity_column))
        if planned_quantity is None or receipt_quantity != planned_quantity:
            issues.add(
                kind + "_receipt_quantity_mismatch",
                plan_id=plan_id,
                entry_id=entry_id,
                receipt_id=receipt_id,
            )
    for entry_id, count in seen.items():
        if count > 1:
            issues.add(
                kind + "_receipt_duplicate",
                plan_id=plan_id,
                entry_id=entry_id,
            )
    expected_count = len([row for row in entries if row.get("source_kind") == kind])
    if 0 < valid_count < expected_count:
        issues.add(kind + "_receipts_partial", plan_id=plan_id)
    if valid_count > expected_count:
        issues.add(kind + "_receipt_count_invalid", plan_id=plan_id)
    return expected_count, valid_count


def build_ledger_report(
    headers,
    entries,
    assignment_receipts,
    supply_allocations,
    *,
    expected_plan_id=None,
    expected_plan_sha256=None,
    max_issues=MAX_ISSUES,
    max_plan_preview=MAX_PLAN_PREVIEW,
):
    scope = normalize_cutover_scope(expected_plan_id, expected_plan_sha256)
    issues = _Issues(max_issues)
    all_headers = [dict(row or {}) for row in (headers or [])]
    all_entries = [dict(row or {}) for row in (entries or [])]
    all_assignment_receipts = [dict(row or {}) for row in (assignment_receipts or [])]
    all_supply_allocations = [dict(row or {}) for row in (supply_allocations or [])]
    if scope["planId"] is not None:
        all_headers = [row for row in all_headers if row.get("id") == scope["planId"]]
    plan_ids = {row.get("id") for row in all_headers}
    if scope["planId"] is None:
        for row in all_entries:
            if row.get("plan_id") not in plan_ids:
                issues.add(
                    "entry_plan_missing",
                    plan_id=row.get("plan_id"),
                    entry_id=row.get("id"),
                )
        for row in all_assignment_receipts:
            if row.get("plan_id") not in plan_ids:
                issues.add(
                    "assignment_receipt_plan_missing",
                    plan_id=row.get("plan_id"),
                    entry_id=row.get("entry_id"),
                    receipt_id=row.get("id"),
                )
        for row in all_supply_allocations:
            if row.get("plan_id") not in plan_ids:
                issues.add(
                    "supply_receipt_plan_missing",
                    plan_id=row.get("plan_id"),
                    entry_id=row.get("entry_id"),
                    receipt_id=row.get("id"),
                )
    scoped_entries = [
        row for row in all_entries if row.get("plan_id") in plan_ids
    ]
    scoped_assignment = [
        row for row in all_assignment_receipts if row.get("plan_id") in plan_ids
    ]
    scoped_supply = [
        row for row in all_supply_allocations if row.get("plan_id") in plan_ids
    ]
    if scope["planId"] is not None and not all_headers:
        issues.add("expected_plan_not_found", plan_id=scope["planId"])

    entries_by_plan = defaultdict(list)
    assignments_by_plan = defaultdict(list)
    supply_by_plan = defaultdict(list)
    for row in scoped_entries:
        entries_by_plan[row.get("plan_id")].append(row)
    for row in scoped_assignment:
        assignments_by_plan[row.get("plan_id")].append(row)
    for row in scoped_supply:
        supply_by_plan[row.get("plan_id")].append(row)

    plans = []
    summary = {
        "plansTotal": len(all_headers),
        "draftPlans": 0,
        "approvedPlans": 0,
        "entriesTotal": len(scoped_entries),
        "assignmentEntries": sum(
            row.get("source_kind") == "assignment" for row in scoped_entries
        ),
        "supplyEntries": sum(
            row.get("source_kind") == "supply" for row in scoped_entries
        ),
        "assignmentReceipts": len(scoped_assignment),
        "supplyAllocations": len(scoped_supply),
        "pendingPlans": 0,
        "partialPlans": 0,
        "completePlans": 0,
    }
    exact_plan_ready = scope["planId"] is None

    for header in sorted(all_headers, key=lambda row: row.get("id") or 0):
        plan_id = header.get("id")
        plan_issue_start = issues.count
        plan_entries = sorted(
            entries_by_plan.get(plan_id, []), key=lambda row: row.get("id") or 0
        )
        if not plan_entries:
            issues.add("plan_entries_missing", plan_id=plan_id)

        stored = _stored_payload(header, plan_entries)
        canonical = stored["canonicalPlan"]
        stored_hash = canonical.get("planSha256")
        if not isinstance(stored_hash, str) or not _SHA256_RE.fullmatch(stored_hash):
            issues.add("plan_hash_invalid", plan_id=plan_id)
        elif calculate_plan_sha256(canonical) != stored_hash:
            issues.add("plan_hash_mismatch", plan_id=plan_id)

        for entry in plan_entries:
            if (
                entry.get("company_id") != header.get("company_id")
                or entry.get("project_id") != header.get("project_id")
            ):
                issues.add(
                    "entry_owner_mismatch",
                    plan_id=plan_id,
                    entry_id=entry.get("id"),
                )
        identities = Counter(
            (row.get("source_kind"), row.get("source_id"), row.get("request_item_index"))
            for row in plan_entries
        )
        for identity, count in identities.items():
            if count > 1:
                duplicate = next(
                    row for row in plan_entries
                    if (
                        row.get("source_kind"), row.get("source_id"),
                        row.get("request_item_index"),
                    ) == identity
                )
                issues.add(
                    "entry_source_duplicate",
                    plan_id=plan_id,
                    entry_id=duplicate.get("id"),
                )

        status = header.get("status")
        if status == "draft":
            summary["draftPlans"] += 1
            if any(header.get(field) is not None for field in (
                "approved_plan_sha256", "approved_by_user_id", "approved_at",
            )):
                issues.add("draft_approval_residue", plan_id=plan_id)
        elif status == "approved":
            summary["approvedPlans"] += 1
            if header.get("approved_plan_sha256") != stored_hash:
                issues.add("approved_plan_hash_mismatch", plan_id=plan_id)
        else:
            issues.add("plan_status_invalid", plan_id=plan_id)

        if (
            scope["planId"] == plan_id
            and header.get("plan_sha256") != scope["expectedPlanSha256"]
        ):
            issues.add("expected_plan_hash_mismatch", plan_id=plan_id)

        assignment_expected, assignment_stored = _receipt_issues(
            kind="assignment",
            header=header,
            entries=plan_entries,
            receipts=assignments_by_plan.get(plan_id, []),
            quantity_column="transfer_quantity",
            issues=issues,
        )
        supply_expected, supply_stored = _receipt_issues(
            kind="supply",
            header=header,
            entries=plan_entries,
            receipts=supply_by_plan.get(plan_id, []),
            quantity_column="allocation_quantity",
            issues=issues,
        )
        if status != "approved" and (assignment_stored or supply_stored):
            issues.add("unapproved_plan_has_receipts", plan_id=plan_id)

        assignment_complete = bool(
            assignment_expected and assignment_stored == assignment_expected
        )
        supply_complete = bool(supply_expected and supply_stored == supply_expected)
        applicable_complete = (
            (not assignment_expected or assignment_complete)
            and (not supply_expected or supply_complete)
        )
        plan_has_issues = issues.count != plan_issue_start
        if plan_has_issues:
            state = "needs_review"
            summary["partialPlans"] += 1
        elif status == "draft":
            state = "draft"
        elif applicable_complete:
            state = "complete"
            summary["completePlans"] += 1
        elif assignment_complete:
            state = "assignment_applied"
            summary["pendingPlans"] += 1
        elif supply_complete:
            state = "supply_allocated"
            summary["pendingPlans"] += 1
        else:
            state = "approved_pending"
            summary["pendingPlans"] += 1
        plan_result = {
            "planId": plan_id,
            "status": status,
            "state": state,
            "assignmentEntries": assignment_expected,
            "assignmentReceipts": assignment_stored,
            "assignmentReadyForApply": bool(
                status == "approved"
                and assignment_expected
                and assignment_stored == 0
                and not plan_has_issues
            ),
            "supplyEntries": supply_expected,
            "supplyAllocations": supply_stored,
            "supplyReadyForApply": bool(
                status == "approved"
                and supply_expected
                and supply_stored == 0
                and not plan_has_issues
            ),
        }
        if len(plans) < max_plan_preview:
            plans.append(plan_result)
        if scope["planId"] == plan_id:
            exact_plan_ready = bool(status == "approved" and not plan_has_issues)

    return {
        "ledgerReady": issues.count == 0,
        "exactPlanRequested": scope["planId"] is not None,
        "exactPlanReady": exact_plan_ready if scope["planId"] is not None else None,
        "summary": summary,
        "planCount": len(all_headers),
        "plans": plans,
        "plansTruncated": len(all_headers) > len(plans),
        "issueCount": issues.count,
        "issues": issues.preview,
        "issuesTruncated": issues.count > len(issues.preview),
    }


def collect_schema_readiness(cur):
    plan = build_schema_plan(_load_catalog(cur))
    return {
        "schemaReady": bool(plan.get("schemaReady")),
        "readyForApply": bool(plan.get("readyForApply")),
        "changeCount": len(plan.get("changes") or []),
        "changes": [item.get("name") for item in (plan.get("changes") or [])],
        "blockers": list(plan.get("blockers") or []),
        "missingPlanColumns": list(plan.get("missingPlanColumns") or []),
        "missingEntryColumns": list(plan.get("missingEntryColumns") or []),
        "missingAssignmentTransferColumns": list(
            plan.get("missingAssignmentTransferColumns") or []
        ),
        "missingSupplyAllocationColumns": list(
            plan.get("missingSupplyAllocationColumns") or []
        ),
    }


def collect_ledger_readiness(
    cur,
    *,
    expected_plan_id=None,
    expected_plan_sha256=None,
):
    if expected_plan_id is None:
        cur.execute(PLAN_SELECT + " ORDER BY id")
        headers = cur.fetchall() or []
        cur.execute(ENTRY_SELECT + " ORDER BY plan_id,id")
        entries = cur.fetchall() or []
        cur.execute(_ASSIGNMENT_RECEIPT_SELECT + " ORDER BY plan_id,entry_id,id")
        assignments = cur.fetchall() or []
        cur.execute(_SUPPLY_ALLOCATION_SELECT + " ORDER BY plan_id,entry_id,id")
        supplies = cur.fetchall() or []
    else:
        cur.execute(PLAN_SELECT + " WHERE id=%s", (expected_plan_id,))
        headers = cur.fetchall() or []
        cur.execute(ENTRY_SELECT + " WHERE plan_id=%s ORDER BY id", (expected_plan_id,))
        entries = cur.fetchall() or []
        cur.execute(
            _ASSIGNMENT_RECEIPT_SELECT + " WHERE plan_id=%s ORDER BY entry_id,id",
            (expected_plan_id,),
        )
        assignments = cur.fetchall() or []
        cur.execute(
            _SUPPLY_ALLOCATION_SELECT + " WHERE plan_id=%s ORDER BY entry_id,id",
            (expected_plan_id,),
        )
        supplies = cur.fetchall() or []
    return build_ledger_report(
        headers,
        entries,
        assignments,
        supplies,
        expected_plan_id=expected_plan_id,
        expected_plan_sha256=expected_plan_sha256,
    )


def run_readiness_report(
    get_db,
    *,
    plan_id=None,
    expected_plan_sha256=None,
    collect_schema=collect_schema_readiness,
    collect_ledger=collect_ledger_readiness,
    collect_inventory=audit_cutover_inventory,
):
    scope = normalize_cutover_scope(plan_id, expected_plan_sha256)
    conn = get_db()
    cur = None
    try:
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        schema = collect_schema(cur)
        if schema.get("schemaReady"):
            ledger = collect_ledger(
                cur,
                expected_plan_id=scope["planId"],
                expected_plan_sha256=scope["expectedPlanSha256"],
            )
        else:
            ledger = {
                "ledgerReady": False,
                "exactPlanRequested": scope["planId"] is not None,
                "exactPlanReady": False if scope["planId"] is not None else None,
                "summary": {},
                "planCount": 0,
                "plans": [],
                "plansTruncated": False,
                "issueCount": 1,
                "issues": [{"reasonCode": "transfer_schema_not_ready"}],
                "issuesTruncated": False,
            }
        conn.rollback()
        inventory = collect_inventory()
        ready = bool(
            schema.get("schemaReady")
            and ledger.get("ledgerReady")
            and inventory.get("ok")
            and (
                scope["planId"] is None
                or ledger.get("exactPlanReady")
            )
        )
        return {
            "ok": ready,
            "dryRun": True,
            "readOnlyTransaction": True,
            "writesAttempted": 0,
            "schemaReady": bool(schema.get("schemaReady")),
            "schemaAudit": schema,
            "ledgerReady": bool(ledger.get("ledgerReady")),
            "ledgerAudit": ledger,
            "writerInventoryReady": bool(inventory.get("ok")),
            "writerInventory": inventory,
            "readyForCutover": ready,
            "rolledBack": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None and hasattr(cur, "close"):
            cur.close()
        conn.close()


def _parser():
    parser = argparse.ArgumentParser(
        description="Read-only E4 estimate-row transfer cutover readiness audit",
    )
    parser.add_argument("--plan-id", type=int)
    parser.add_argument("--expected-plan-sha256")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        scope = normalize_cutover_scope(args.plan_id, args.expected_plan_sha256)
    except ValueError as exc:
        _parser().error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_readiness_report(
        get_db,
        plan_id=scope["planId"],
        expected_plan_sha256=scope["expectedPlanSha256"],
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("readyForCutover") else 1


if __name__ == "__main__":
    raise SystemExit(main())
