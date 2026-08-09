"""Read-only A8.3 supplier data-readiness preview for human review."""

import hashlib
import json
from collections.abc import Mapping

import psycopg2.extras

from backend.features.estimate_revision_impact.schema_probe import (
    collect_missing_columns,
    required_column_count,
)

from .rfq_content import (
    RFQ_CONTENT_VERSION,
    calculate_content_sha256,
    collect_prepared_supply_rfq_content,
    prepare_supply_rfq_content,
)


ELIGIBILITY_VERSION = 1
MAX_COMPANY_LINKS = 100
MAX_DIRECT_USER_LINKS = 200
REQUIRED_COLUMNS = {
    "companies": {"id", "platform_account_id", "active"},
    "platform_accounts": {"id", "active", "status"},
    "company_supplier_links": {
        "id", "company_id", "supplier_id", "platform_account_id", "status",
    },
    "suppliers": {"id", "status", "user_id"},
    "users": {"id", "role", "active"},
}
SCHEMA_COLUMN_LIMIT = required_column_count(REQUIRED_COLUMNS)
_CANDIDATE_EVIDENCE = [
    "company_link_exact",
    "supplier_card_active",
    "supplier_portal_user_direct_active",
]
_NON_READY_STATES = {"no_action", "needs_review", "incomplete"}
_ALLOWED_NON_READY_BLOCKERS = {
    "no_action": {
        "supply_rfq_open_balance_zero",
        "supply_rfq_request_status_ineligible",
    },
    "needs_review": {
        "supply_rfq_estimate_pair_invalid",
        "supply_rfq_estimate_snapshot_invalid",
        "supply_rfq_material_identity_changed",
        "supply_rfq_material_lineage_drift",
        "supply_rfq_material_not_ready",
        "supply_rfq_open_request_ambiguous",
        "supply_rfq_project_identity_invalid",
        "supply_rfq_request_invalid",
        "supply_rfq_source_drift",
        "supply_rfq_supply_evidence_invalid",
        "supply_rfq_supply_warehouse_not_ready",
        "supply_rfq_target_material_invalid",
    },
    "incomplete": {
        "supply_rfq_alias_scan_limit_exceeded",
        "supply_rfq_child_scan_limit_exceeded",
        "supply_rfq_material_not_ready",
        "supply_rfq_material_scan_limit_exceeded",
        "supply_rfq_request_item_scan_limit_exceeded",
        "supply_rfq_request_snapshot_too_large",
        "supply_rfq_schema_not_ready",
        "supply_rfq_source_not_ready",
        "supply_rfq_supply_evidence_invalid",
        "supply_rfq_supply_warehouse_not_ready",
    },
}
_RFQ_CONTENT_FIELDS = {
    "contentVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "candidate", "readyForRfqDraft", "blockers", "request",
    "balance", "rfqDraft", "requestItemSha256", "contentSha256",
    "readOnlyTransaction", "rolledBack",
}


class SupplySupplierEligibilityError(ValueError):
    """Fixed error code safe to expose without database or business text."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


class _EligibilityBlock(Exception):
    def __init__(self, state, code):
        self.state = state
        self.code = code
        super().__init__(code)


def _block(state, code):
    raise _EligibilityBlock(state, code)


def _positive_int(value):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _canonical_sha256(value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def calculate_eligibility_sha256(result):
    """Hash the ID-only supplier review decision, excluding runner metadata."""

    return _canonical_sha256({
        "eligibilityVersion": result.get("eligibilityVersion"),
        "state": result.get("state"),
        "source": result.get("source"),
        "candidateKind": result.get("candidateKind"),
        "readyForHumanSupplierReview": result.get(
            "readyForHumanSupplierReview"
        ),
        "materialEligibilityProven": result.get(
            "materialEligibilityProven"
        ),
        "rankingApplied": result.get("rankingApplied"),
        "candidateSupplierLinks": result.get("candidateSupplierLinks"),
        "supplierIds": result.get("supplierIds"),
        "selectionAllowed": result.get("selectionAllowed"),
        "sendAllowed": result.get("sendAllowed"),
        "blockers": result.get("blockers"),
    })


def _source(prepared, content):
    candidate = prepared["candidate"]
    request_item_sha256 = content.get("requestItemSha256")
    content_sha256 = content.get("contentSha256")
    return {
        "companyId": prepared["source"]["companyId"],
        "requestId": candidate["requestId"],
        "requestItemIndex": candidate["requestItemIndex"],
        "requestItemSha256": (
            request_item_sha256 if _is_sha256(request_item_sha256) else None
        ),
        "rfqContentSha256": (
            content_sha256 if _is_sha256(content_sha256) else None
        ),
    }


def _result(prepared, content, state, blockers, candidates=()):
    candidates = sorted(
        (dict(candidate) for candidate in candidates),
        key=lambda item: (item["supplierId"], item["companySupplierLinkId"]),
    )
    result = {
        "eligibilityVersion": ELIGIBILITY_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": state,
        "source": _source(prepared, content),
        "candidateKind": "company_link_account_ready",
        "readyForHumanSupplierReview": state == "review_ready",
        "materialEligibilityProven": False,
        "rankingApplied": False,
        "candidateCount": len(candidates),
        "candidateSupplierLinks": candidates,
        "supplierIds": [],
        "selectionAllowed": False,
        "sendAllowed": False,
        "blockers": sorted(set(blockers)),
        "eligibilitySha256": None,
        "readOnlyTransaction": False,
        "rolledBack": False,
    }
    result["eligibilitySha256"] = calculate_eligibility_sha256(result)
    return result


def _missing_schema_columns(cur):
    return collect_missing_columns(cur, REQUIRED_COLUMNS)


def _has_supporting_index(cur, table, first_column, second_column):
    cur.execute(
        """SELECT EXISTS(
                   SELECT 1
                     FROM pg_catalog.pg_class table_relation
                     JOIN pg_catalog.pg_namespace namespace
                       ON namespace.oid=table_relation.relnamespace
                     JOIN pg_catalog.pg_index index_state
                       ON index_state.indrelid=table_relation.oid
                     JOIN pg_catalog.pg_class index_relation
                       ON index_relation.oid=index_state.indexrelid
                     JOIN pg_catalog.pg_am access_method
                       ON access_method.oid=index_relation.relam
                     JOIN pg_catalog.pg_attribute first_key
                       ON first_key.attrelid=table_relation.oid
                      AND first_key.attnum=index_state.indkey[0]
                     JOIN pg_catalog.pg_attribute second_key
                       ON second_key.attrelid=table_relation.oid
                      AND second_key.attnum=index_state.indkey[1]
                    WHERE namespace.nspname=%s
                      AND table_relation.relname=%s
                      AND access_method.amname=%s
                      AND index_state.indisvalid IS TRUE
                      AND index_state.indisready IS TRUE
                      AND index_state.indislive IS TRUE
                      AND index_state.indcheckxmin IS FALSE
                      AND index_state.indpred IS NULL
                      AND index_state.indexprs IS NULL
                      AND index_state.indnkeyatts>=2
                      AND first_key.attname=%s
                      AND second_key.attname=%s
                    LIMIT 1
               ) AS index_ready
            LIMIT %s""",
        ("public", table, "btree", first_column, second_column, 1),
    )
    rows = list(cur.fetchall() or [])
    return len(rows) == 1 and rows[0].get("index_ready") is True


def _load_company_links(cur, company_id):
    cur.execute(
        """SELECT c.id AS company_id,
                  c.platform_account_id AS company_account_id,
                  c.active AS company_active,
                  pa.id AS account_id,
                  pa.active AS account_active,
                  pa.status AS account_status,
                  link.id AS link_id,
                  link.company_id AS link_company_id,
                  link.supplier_id,
                  link.platform_account_id AS link_account_id,
                  link.status AS link_status,
                  supplier.id AS supplier_parent_id,
                  supplier.status AS supplier_status,
                  supplier.user_id AS supplier_user_link_id,
                  supplier_user.id AS supplier_user_id,
                  supplier_user.role AS supplier_user_role,
                  supplier_user.active AS supplier_user_active
             FROM public.companies c
             LEFT JOIN public.platform_accounts pa
                    ON pa.id=c.platform_account_id
             LEFT JOIN public.company_supplier_links link
                    ON link.company_id=c.id
             LEFT JOIN public.suppliers supplier
                    ON supplier.id=link.supplier_id
             LEFT JOIN public.users supplier_user
                    ON supplier_user.id=supplier.user_id
            WHERE c.id=%s
            ORDER BY link.supplier_id
            LIMIT %s""",
        (company_id, MAX_COMPANY_LINKS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _load_direct_user_links(cur, user_ids):
    cur.execute(
        """SELECT id AS supplier_id,user_id AS supplier_user_id
            FROM public.suppliers
            WHERE user_id=ANY(%s)
            ORDER BY user_id
            LIMIT %s""",
        (sorted(user_ids), MAX_DIRECT_USER_LINKS + 1),
    )
    return [dict(row or {}) for row in (cur.fetchall() or [])]


def _validated_content(prepared, content):
    if not isinstance(content, Mapping):
        _block("needs_review", "supply_supplier_rfq_content_invalid")
    if (
        set(content) != _RFQ_CONTENT_FIELDS
        or content.get("contentVersion") != RFQ_CONTENT_VERSION
        or content.get("ok") is not True
        or content.get("dryRun") is not True
        or content.get("writesAttempted") != 0
        or content.get("readOnlyTransaction") is not False
        or content.get("rolledBack") is not False
    ):
        _block("needs_review", "supply_supplier_rfq_content_invalid")

    state = content.get("state")
    if state in _NON_READY_STATES:
        blockers = content.get("blockers")
        if (
            content.get("readyForRfqDraft") is not False
            or not isinstance(blockers, list)
            or not blockers
            or len(blockers) > 100
            or any(not isinstance(code, str) for code in blockers)
            or set(blockers) - _ALLOWED_NON_READY_BLOCKERS[state]
            or content.get("source") != prepared["source"]
            or content.get("candidate") != prepared["candidate"]
            or content.get("request") is not None
            or content.get("balance") is not None
            or content.get("rfqDraft") is not None
            or content.get("requestItemSha256") is not None
            or content.get("contentSha256") is not None
        ):
            _block("needs_review", "supply_supplier_rfq_content_invalid")
        return state, blockers

    draft = content.get("rfqDraft")
    candidate = prepared["candidate"]
    request = content.get("request")
    if (
        state != "draft_ready"
        or content.get("readyForRfqDraft") is not True
        or content.get("blockers") != []
        or not isinstance(draft, Mapping)
        or draft.get("sendAllowed") is not False
        or draft.get("supplierIds") != []
        or not isinstance(draft.get("items"), list)
        or len(draft["items"]) != 1
        or not isinstance(request, Mapping)
        or request.get("requestId") != candidate["requestId"]
        or request.get("requestItemIndex") != candidate["requestItemIndex"]
        or content.get("source") != prepared["source"]
        or content.get("candidate") != candidate
        or not _is_sha256(content.get("requestItemSha256"))
        or not _is_sha256(content.get("contentSha256"))
        or calculate_content_sha256(content) != content.get("contentSha256")
    ):
        _block("needs_review", "supply_supplier_rfq_content_invalid")
    return state, []


def _company_scope(rows, company_id):
    if not rows:
        _block("needs_review", "supply_supplier_company_scope_invalid")
    if len(rows) > MAX_COMPANY_LINKS:
        _block("incomplete", "supply_supplier_link_scan_incomplete")

    first = rows[0]
    account_id = _positive_int(first.get("company_account_id"))
    if account_id is None:
        _block("needs_review", "supply_supplier_company_scope_invalid")
    scope = (
        _positive_int(first.get("company_id")),
        account_id,
        first.get("company_active"),
        _positive_int(first.get("account_id")),
        first.get("account_active"),
        first.get("account_status"),
    )
    if scope != (company_id, account_id, True, account_id, True, "active"):
        _block("needs_review", "supply_supplier_company_scope_invalid")
    for row in rows[1:]:
        row_scope = (
            _positive_int(row.get("company_id")),
            _positive_int(row.get("company_account_id")),
            row.get("company_active"),
            _positive_int(row.get("account_id")),
            row.get("account_active"),
            row.get("account_status"),
        )
        if row_scope != scope:
            _block("needs_review", "supply_supplier_link_ambiguous")
    return account_id


def _active_link_candidates(rows, company_id, account_id):
    candidates = []
    seen_links = set()
    seen_suppliers = set()
    seen_users = set()
    for row in rows:
        link_id = _positive_int(row.get("link_id"))
        if link_id is None:
            if any(
                row.get(key) is not None
                for key in (
                    "link_company_id", "supplier_id", "link_account_id",
                    "link_status", "supplier_parent_id",
                    "supplier_user_link_id", "supplier_user_id",
                )
            ):
                _block("needs_review", "supply_supplier_link_ambiguous")
            continue
        if row.get("link_status") != "Активный":
            continue

        supplier_id = _positive_int(row.get("supplier_id"))
        user_link_id = _positive_int(row.get("supplier_user_link_id"))
        user_id = _positive_int(row.get("supplier_user_id"))
        raw_link_account = row.get("link_account_id")
        link_account_valid = (
            raw_link_account is None
            or _positive_int(raw_link_account) == account_id
        )
        if (
            _positive_int(row.get("link_company_id")) != company_id
            or supplier_id is None
            or _positive_int(row.get("supplier_parent_id")) != supplier_id
            or not link_account_valid
            or row.get("supplier_status") != "Активный"
            or user_link_id is None
            or user_id != user_link_id
            or row.get("supplier_user_role") != "поставщик"
            or row.get("supplier_user_active") is not True
            or link_id in seen_links
            or supplier_id in seen_suppliers
            or user_id in seen_users
        ):
            _block("needs_review", "supply_supplier_link_ambiguous")
        seen_links.add(link_id)
        seen_suppliers.add(supplier_id)
        seen_users.add(user_id)
        candidates.append({
            "linkId": link_id,
            "supplierId": supplier_id,
            "userId": user_id,
        })
    return candidates


def _review_candidates(cur, prepared):
    if _missing_schema_columns(cur):
        _block("incomplete", "supply_supplier_schema_not_ready")
    if not _has_supporting_index(
        cur, "company_supplier_links", "company_id", "supplier_id",
    ):
        _block("incomplete", "supply_supplier_company_link_index_not_ready")
    company_id = prepared["source"]["companyId"]
    rows = _load_company_links(cur, company_id)
    account_id = _company_scope(rows, company_id)
    candidates = _active_link_candidates(rows, company_id, account_id)
    if not candidates:
        return []

    if not _has_supporting_index(cur, "suppliers", "user_id", "id"):
        _block("incomplete", "supply_supplier_user_index_not_ready")

    user_rows = _load_direct_user_links(
        cur, {candidate["userId"] for candidate in candidates},
    )
    if len(user_rows) > MAX_DIRECT_USER_LINKS:
        _block("incomplete", "supply_supplier_user_scan_incomplete")
    suppliers_by_user = {}
    for row in user_rows:
        supplier_id = _positive_int(row.get("supplier_id"))
        user_id = _positive_int(row.get("supplier_user_id"))
        if supplier_id is None or user_id is None:
            _block("needs_review", "supply_supplier_user_link_ambiguous")
        suppliers_by_user.setdefault(user_id, set()).add(supplier_id)
    for candidate in candidates:
        if suppliers_by_user.get(candidate["userId"]) != {
            candidate["supplierId"]
        }:
            _block("needs_review", "supply_supplier_user_link_ambiguous")

    return [
        {
            "companySupplierLinkId": candidate["linkId"],
            "supplierId": candidate["supplierId"],
            "evidence": list(_CANDIDATE_EVIDENCE),
        }
        for candidate in candidates
    ]


def _collect(cur, prepared):
    content = collect_prepared_supply_rfq_content(cur, prepared)
    try:
        state, blockers = _validated_content(prepared, content)
    except _EligibilityBlock as blocked:
        return _result(prepared, {}, blocked.state, [blocked.code])

    if state != "draft_ready":
        return _result(prepared, content, state, blockers)
    try:
        candidates = _review_candidates(cur, prepared)
        if not candidates:
            return _result(
                prepared,
                content,
                "no_candidates",
                ["supply_supplier_no_active_company_links"],
            )
        return _result(prepared, content, "review_ready", [], candidates)
    except _EligibilityBlock as blocked:
        return _result(prepared, content, blocked.state, [blocked.code])


def run_supply_supplier_eligibility_preview(
    get_db, combined_report, selected,
):
    """Rebuild A8.2 and supplier readiness in one rolled-back snapshot."""

    try:
        prepared = prepare_supply_rfq_content(combined_report, selected)
    except Exception as exc:
        raise SupplySupplierEligibilityError(
            "supply_supplier_input_invalid"
        ) from exc

    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_error = None
    try:
        connection = get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        result = _collect(cur, prepared)
    except BaseException as exc:
        primary_error = exc

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as exc:
            rollback_error = exc

    if cur is not None and hasattr(cur, "close"):
        try:
            cur.close()
        except BaseException as exc:
            cleanup_error = exc
    if connection is not None:
        try:
            connection.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc

    if isinstance(primary_error, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise primary_error
    if rollback_error is not None:
        raise SupplySupplierEligibilityError(
            "supply_supplier_rollback_failed"
        ) from rollback_error
    if isinstance(primary_error, SupplySupplierEligibilityError):
        raise primary_error
    if primary_error is not None:
        raise SupplySupplierEligibilityError(
            "supply_supplier_read_failed"
        ) from primary_error
    if cleanup_error is not None:
        raise SupplySupplierEligibilityError(
            "supply_supplier_cleanup_failed"
        ) from cleanup_error

    result["readOnlyTransaction"] = True
    result["rolledBack"] = True
    return result


__all__ = [
    "ELIGIBILITY_VERSION",
    "MAX_COMPANY_LINKS",
    "MAX_DIRECT_USER_LINKS",
    "REQUIRED_COLUMNS",
    "SCHEMA_COLUMN_LIMIT",
    "SupplySupplierEligibilityError",
    "calculate_eligibility_sha256",
    "run_supply_supplier_eligibility_preview",
]
