"""Bounded read-only A7.2 brigade assignment and protected-history impact."""

import argparse
import json
import math
from collections import Counter

from backend.features.brigade_lineage.readiness_report import (
    classify_contract_item,
)
from backend.features.estimate_row_transfer.audit import (
    classify_assignment_lineage_and_balance,
)

from .baseline import collect_baseline_audit, run_baseline_audit
from .contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    validate_estimate_revision_source,
)


MAX_ASSIGNMENT_ROWS = 100
PROTECTED_ID_LIMIT = 100
ASSIGNMENT_REQUIRED_COLUMNS = {
    "projects": {"id", "company_id"},
    "estimates": {"id", "company_id", "project_id"},
    "estimate_versions": {
        "id", "estimate_id", "sections_json", "sections_sha256",
    },
    "brigade_contracts": {
        "id", "company_id", "project_id", "work_package",
    },
    "brigade_contract_items": {
        "id", "contract_id", "estimate_item_key", "work_package", "quantity",
        "source_type", "source_estimate_version_id", "source_section_index",
        "source_item_index", "source_item_key",
    },
    "work_journal": {
        "id", "company_id", "contract_item_id", "quantity", "status",
    },
    "hidden_works_acts": {"id", "company_id", "work_journal_id"},
    "brigade_acts": {"id", "contract_id"},
    "brigade_payments": {
        "id", "company_id", "contract_id", "project_payment_id",
    },
    "project_payments": {"id", "company_id", "company_scope_verified"},
}

_HISTORY_FIELDS = (
    ("workJournal", "journal_count", "journal_ids", False),
    (
        "confirmedWorkJournal",
        "confirmed_journal_count",
        "confirmed_journal_ids",
        False,
    ),
    ("hiddenActs", "hidden_act_count", "hidden_act_ids", False),
    ("brigadeActs", "brigade_act_count", "brigade_act_ids", True),
    (
        "brigadePayments",
        "brigade_payment_count",
        "brigade_payment_ids",
        True,
    ),
    (
        "projectPayments",
        "project_payment_count",
        "project_payment_ids",
        True,
    ),
)


def _positive_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _finite_positive(value):
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _history_base():
    return {
        public_name: {"count": 0, "ids": [], "idsTruncated": False}
        for public_name, _count_field, _ids_field, _contract_scoped
        in _HISTORY_FIELDS
    }


def _summary_base(*, assignment_rows=0):
    return {
        "assignmentRows": assignment_rows,
        "uncompletedAssignments": 0,
        "protectedAssignments": 0,
        "needsReview": 0,
        "workJournalRows": 0,
        "confirmedWorkJournalRows": 0,
        "hiddenActs": 0,
        "brigadeActs": 0,
        "brigadePayments": 0,
        "projectPayments": 0,
    }


def _empty_projection(
    state,
    *,
    schema_ready=True,
    missing_columns=None,
    scan_complete=False,
    reason_code=None,
    assignment_rows=0,
):
    review = []
    reason_counts = {}
    if reason_code:
        review = [{
            "sourceKind": "assignment",
            "sourceId": None,
            "reasonCode": reason_code,
        }]
        reason_counts = {reason_code: 1}
    summary = _summary_base(assignment_rows=assignment_rows)
    summary["needsReview"] = len(review)
    return {
        "state": state,
        "schemaReady": bool(schema_ready),
        "missingColumns": list(missing_columns or []),
        "scanComplete": bool(scan_complete),
        "complete": False,
        "summary": summary,
        "uncompletedAssignmentIds": [],
        "protectedAssignmentIds": [],
        "protectedHistory": _history_base(),
        "reasonCounts": reason_counts,
        "needsReview": review,
        "needsReviewTruncated": False,
    }


def _review(source_id, reason_code):
    return {
        "sourceKind": "assignment",
        "sourceId": _positive_int(source_id),
        "reasonCode": reason_code,
    }


def _context_for_e4(context):
    return {
        "companyId": context["companyId"],
        "projectId": context["projectId"],
        "baseEstimateId": context["baseEstimateId"],
        "workPackage": context["workPackage"],
    }


def _safe_ids(row, field):
    raw_ids = row.get(field)
    if not isinstance(raw_ids, (list, tuple)):
        return []
    return sorted({
        item_id for item_id in (_positive_int(value) for value in raw_ids)
        if item_id
    })


def build_assignment_projection(context, rows, *, scan_complete=True):
    """Build the fixed ID/count-only A7.2 public projection."""

    rows = [dict(row or {}) for row in (rows or [])]
    unsafe_contracts = {
        _positive_int(row.get("contract_id"))
        for row in rows
        if _count(row.get("protected_owner_mismatch_count")) not in (0, None)
    }
    unsafe_contracts.discard(None)

    uncompleted_ids = set()
    protected_assignment_ids = set()
    reviews = []
    history_ids = {name: set() for name, *_rest in _HISTORY_FIELDS}
    item_counts = Counter()
    contract_counts = {
        name: {}
        for name, _count_field, _ids_field, contract_scoped in _HISTORY_FIELDS
        if contract_scoped
    }
    count_invalid = False

    for row in rows:
        source_id = _positive_int(row.get("contract_item_id"))
        contract_id = _positive_int(row.get("contract_id"))
        owner_exact = (
            _positive_int(row.get("contract_company_id")),
            _positive_int(row.get("contract_project_id")),
        ) == (context.get("companyId"), context.get("projectId"))

        lineage = classify_contract_item(
            row,
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
            snapshot_evidence=row,
        )
        reason_code = None
        candidate = None
        if lineage.get("status") != "verified_estimate":
            reason_code = lineage.get("reason") or "assignment_lineage_invalid"
        else:
            candidate, blocker = classify_assignment_lineage_and_balance(
                _context_for_e4(context),
                row,
                require_positive_balance=False,
            )
            if blocker:
                reason_code = blocker.get("reasonCode")

        if contract_id in unsafe_contracts and reason_code is None:
            reason_code = "assignment_protected_history_owner_mismatch"
        if reason_code:
            reviews.append(_review(source_id, reason_code))
        elif candidate and candidate.get("transferableQuantity", 0) > 0:
            uncompleted_ids.add(source_id)

        if not owner_exact or contract_id in unsafe_contracts:
            continue

        row_has_protected = _finite_positive(row.get("confirmed_quantity"))
        for public_name, count_field, ids_field, contract_scoped in _HISTORY_FIELDS:
            count = _count(row.get(count_field))
            ids = _safe_ids(row, ids_field)
            if count is None or count < len(ids):
                count_invalid = True
                count = max(len(ids), count or 0)
            if count:
                row_has_protected = True
            history_ids[public_name].update(ids)
            if contract_scoped:
                prior = contract_counts[public_name].get(contract_id)
                contract_counts[public_name][contract_id] = (
                    count if prior is None else max(prior, count)
                )
            else:
                item_counts[public_name] += count
        if row_has_protected and source_id:
            protected_assignment_ids.add(source_id)

    if count_invalid:
        reviews.append(_review(
            None,
            "assignment_protected_history_count_invalid",
        ))

    history = _history_base()
    any_ids_truncated = False
    for public_name, _count_field, _ids_field, contract_scoped in _HISTORY_FIELDS:
        count = (
            sum(contract_counts[public_name].values())
            if contract_scoped
            else item_counts[public_name]
        )
        ids = sorted(history_ids[public_name])
        truncated = len(ids) > PROTECTED_ID_LIMIT or count > len(ids)
        history[public_name] = {
            "count": count,
            "ids": ids[:PROTECTED_ID_LIMIT],
            "idsTruncated": truncated,
        }
        any_ids_truncated = any_ids_truncated or truncated

    review_count = len(reviews)
    reviews_truncated = review_count > MAX_ASSIGNMENT_ROWS
    reason_counts = Counter(item["reasonCode"] for item in reviews)
    review_preview = reviews[:MAX_ASSIGNMENT_ROWS]
    complete = bool(scan_complete) and not reviews and not any_ids_truncated
    if not scan_complete or any_ids_truncated:
        state = "incomplete"
    elif reviews:
        state = "review_required"
    else:
        state = "complete"
    summary = _summary_base(assignment_rows=len(rows))
    summary.update({
        "uncompletedAssignments": len(uncompleted_ids),
        "protectedAssignments": len(protected_assignment_ids),
        "needsReview": review_count,
        "workJournalRows": history["workJournal"]["count"],
        "confirmedWorkJournalRows": history["confirmedWorkJournal"]["count"],
        "hiddenActs": history["hiddenActs"]["count"],
        "brigadeActs": history["brigadeActs"]["count"],
        "brigadePayments": history["brigadePayments"]["count"],
        "projectPayments": history["projectPayments"]["count"],
    })
    return {
        "state": state,
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": bool(scan_complete),
        "complete": complete,
        "summary": summary,
        "uncompletedAssignmentIds": sorted(uncompleted_ids),
        "protectedAssignmentIds": sorted(protected_assignment_ids),
        "protectedHistory": history,
        "reasonCounts": dict(sorted(reason_counts.items())),
        "needsReview": review_preview,
        "needsReviewTruncated": reviews_truncated,
    }


def _load_assignment_schema(cur):
    cur.execute(
        """SELECT table_name,column_name
             FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=ANY(%s)
            ORDER BY table_name,ordinal_position""",
        (sorted(ASSIGNMENT_REQUIRED_COLUMNS),),
    )
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in (cur.fetchall() or [])
    }
    return sorted(
        table + "." + column
        for table, columns in ASSIGNMENT_REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in present
    )


def _load_assignment_rows(cur, context):
    id_limit = PROTECTED_ID_LIMIT + 1
    cur.execute(
        """SELECT bci.id AS contract_item_id,bci.contract_id,
                  TRUE AS contract_exists,
                  bc.company_id AS contract_company_id,
                  bc.project_id AS contract_project_id,
                  COALESCE(NULLIF(bci.work_package,''),'Основная')
                      AS contract_work_package,
                  p.id IS NOT NULL AS project_exists,
                  p.company_id AS project_company_id,
                  bci.estimate_item_key AS legacy_item_key,
                  bci.source_type,ev.estimate_id AS source_estimate_id,
                  bci.source_estimate_version_id,bci.source_section_index,
                  bci.source_item_index,bci.source_item_key,
                  ev.id IS NOT NULL AS snapshot_exists,
                  ev.id AS snapshot_version_id,
                  ev.estimate_id AS snapshot_estimate_id,
                  ev.sections_json AS snapshot_sections_json,
                  ev.sections_sha256 AS snapshot_sections_sha256,
                  source_estimate.id IS NOT NULL AS estimate_exists,
                  source_estimate.company_id AS estimate_company_id,
                  source_estimate.project_id AS estimate_project_id,
                  COALESCE(NULLIF(impact_base.work_package,''),'Основная')
                      AS impact_work_package,
                  bci.quantity AS assignment_quantity,
                  COALESCE((SELECT SUM(wj.quantity)
                              FROM public.work_journal wj
                             WHERE wj.contract_item_id=bci.id
                               AND wj.status='Подтверждено'),0)
                      AS confirmed_quantity,
                  (SELECT COUNT(*) FROM public.work_journal wj
                    WHERE wj.contract_item_id=bci.id) AS journal_count,
                  (SELECT COUNT(*) FROM public.work_journal wj
                    WHERE wj.contract_item_id=bci.id
                      AND wj.status='Подтверждено') AS confirmed_journal_count,
                  (SELECT COUNT(*)
                     FROM public.hidden_works_acts hwa
                     JOIN public.work_journal wj ON wj.id=hwa.work_journal_id
                    WHERE wj.contract_item_id=bci.id) AS hidden_act_count,
                  (SELECT COUNT(*) FROM public.brigade_acts ba
                    WHERE ba.contract_id=bci.contract_id) AS brigade_act_count,
                  (SELECT COUNT(*) FROM public.brigade_payments bp
                    WHERE bp.contract_id=bci.contract_id)
                      AS brigade_payment_count,
                  (SELECT COUNT(*)
                     FROM public.brigade_payments bp
                     JOIN public.project_payments pp
                       ON pp.id=bp.project_payment_id
                    WHERE bp.contract_id=bci.contract_id)
                      AS project_payment_count,
                  ARRAY(SELECT wj.id FROM public.work_journal wj
                         WHERE wj.contract_item_id=bci.id
                         ORDER BY wj.id LIMIT %s) AS journal_ids,
                  ARRAY(SELECT wj.id FROM public.work_journal wj
                         WHERE wj.contract_item_id=bci.id
                           AND wj.status='Подтверждено'
                         ORDER BY wj.id LIMIT %s) AS confirmed_journal_ids,
                  ARRAY(SELECT hwa.id
                          FROM public.hidden_works_acts hwa
                          JOIN public.work_journal wj
                            ON wj.id=hwa.work_journal_id
                         WHERE wj.contract_item_id=bci.id
                         ORDER BY hwa.id LIMIT %s) AS hidden_act_ids,
                  ARRAY(SELECT ba.id FROM public.brigade_acts ba
                         WHERE ba.contract_id=bci.contract_id
                         ORDER BY ba.id LIMIT %s) AS brigade_act_ids,
                  ARRAY(SELECT bp.id FROM public.brigade_payments bp
                         WHERE bp.contract_id=bci.contract_id
                         ORDER BY bp.id LIMIT %s) AS brigade_payment_ids,
                  ARRAY(SELECT pp.id
                          FROM public.brigade_payments bp
                          JOIN public.project_payments pp
                            ON pp.id=bp.project_payment_id
                         WHERE bp.contract_id=bci.contract_id
                         ORDER BY pp.id LIMIT %s) AS project_payment_ids,
                  ((SELECT COUNT(*) FROM public.work_journal wj
                     WHERE wj.contract_item_id=bci.id
                       AND wj.company_id IS DISTINCT FROM bc.company_id)
                   + (SELECT COUNT(*)
                        FROM public.hidden_works_acts hwa
                        JOIN public.work_journal wj
                          ON wj.id=hwa.work_journal_id
                       WHERE wj.contract_item_id=bci.id
                         AND hwa.company_id IS DISTINCT FROM bc.company_id)
                   + (SELECT COUNT(*) FROM public.brigade_payments bp
                       WHERE bp.contract_id=bci.contract_id
                         AND bp.company_id IS DISTINCT FROM bc.company_id)
                   + (SELECT COUNT(*)
                        FROM public.brigade_payments bp
                        JOIN public.project_payments pp
                          ON pp.id=bp.project_payment_id
                       WHERE bp.contract_id=bci.contract_id
                         AND (pp.company_id IS DISTINCT FROM bc.company_id
                              OR pp.company_scope_verified IS DISTINCT FROM TRUE)))
                      AS protected_owner_mismatch_count
             FROM public.brigade_contract_items bci
             JOIN public.brigade_contracts bc ON bc.id=bci.contract_id
             LEFT JOIN public.projects p ON p.id=bc.project_id
             LEFT JOIN public.estimate_versions ev
               ON ev.id=bci.source_estimate_version_id
             LEFT JOIN public.estimates source_estimate
               ON source_estimate.id=ev.estimate_id
             JOIN public.estimates impact_base
               ON impact_base.id=%s AND impact_base.company_id=%s
              AND impact_base.project_id=%s
            WHERE ev.estimate_id=%s
               OR (bc.company_id=%s AND bc.project_id=%s
                   AND COALESCE(NULLIF(bci.work_package,''),'Основная')=
                       COALESCE(NULLIF(impact_base.work_package,''),'Основная')
                   AND (bci.source_type IS DISTINCT FROM 'estimate'
                        OR ev.id IS NULL))
            ORDER BY bci.id
            LIMIT %s""",
        (
            id_limit, id_limit, id_limit, id_limit, id_limit, id_limit,
            context["baseEstimateId"], context["companyId"],
            context["projectId"], context["baseEstimateId"],
            context["companyId"], context["projectId"],
            MAX_ASSIGNMENT_ROWS + 1,
        ),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def collect_assignment_impact_audit(cur, source):
    """Collect A7.1 source plus A7.2 assignment evidence without mutations."""

    report = collect_baseline_audit(cur, source)
    if not report.get("readyForDomainScan"):
        report["readyForAssignmentProjection"] = False
        report["assignmentImpact"] = _empty_projection("not_collected")
        return report

    missing = _load_assignment_schema(cur)
    if missing:
        report["readyForAssignmentProjection"] = False
        report["assignmentImpact"] = _empty_projection(
            "incomplete",
            schema_ready=False,
            missing_columns=missing,
            reason_code="assignment_impact_schema_not_ready",
        )
        return report

    source_context = report["source"]
    context = {
        "companyId": source_context["companyId"],
        "projectId": source_context["projectId"],
        "baseEstimateId": source_context["baseEstimateId"],
        "targetEstimateId": source_context["estimateId"],
        "workPackage": None,
    }
    rows = _load_assignment_rows(cur, context)
    if len(rows) > MAX_ASSIGNMENT_ROWS:
        projection = _empty_projection(
            "incomplete",
            scan_complete=False,
            reason_code="assignment_scan_limit_exceeded",
            assignment_rows=len(rows),
        )
    else:
        if rows:
            context["workPackage"] = rows[0].get("impact_work_package")
        projection = build_assignment_projection(context, rows)
    report["readyForAssignmentProjection"] = projection["complete"]
    report["assignmentImpact"] = projection
    return report


def run_assignment_impact_audit(get_db, source):
    return run_baseline_audit(
        get_db,
        source,
        collect_data=collect_assignment_impact_audit,
    )


def _source_from_args(args):
    return validate_estimate_revision_source({
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": args.company_id,
        "projectId": args.project_id,
        "estimateId": args.estimate_id,
        "sourceRevision": args.source_revision,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Read-only exact estimate revision assignment impact audit"
        ),
    )
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--estimate-id", required=True, type=int)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    try:
        source = _source_from_args(args)
    except EstimateRevisionImpactContractError as exc:
        parser.error(str(exc))
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_assignment_impact_audit(get_db, source)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("readyForAssignmentProjection") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ASSIGNMENT_REQUIRED_COLUMNS",
    "MAX_ASSIGNMENT_ROWS",
    "PROTECTED_ID_LIMIT",
    "build_assignment_projection",
    "collect_assignment_impact_audit",
    "run_assignment_impact_audit",
]
