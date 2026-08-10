"""Same-snapshot, read-only proof for exact supplier-material subjects."""

import copy
import hashlib
import json

import psycopg2.extras

from .material_capability_confirmation import (
    SUBJECT_KIND,
    MaterialCapabilityConfirmationError,
    _build_material_capability_confirmation_snapshot,
    build_material_capability_confirmation_readiness,
)
from .material_capability_schema_contract import CONTRACT_VERSION
from . import material_capability_schema_probe
from .rfq_content import (
    collect_prepared_supply_rfq_content,
    prepare_supply_rfq_content,
)
from .supplier_eligibility import (
    collect_prepared_supply_supplier_eligibility,
)


PROOF_VERSION = 1
MAX_CONFIRMATION_SUBJECTS = 100
PROOF_DOMAIN = "stroyka.supply.supplier_material_capability.proof"

_INPUT_INVALID = "supply_supplier_material_proof_input_invalid"
_READ_FAILED = "supply_supplier_material_proof_read_failed"
_ROLLBACK_FAILED = "supply_supplier_material_proof_rollback_failed"
_CLEANUP_FAILED = "supply_supplier_material_proof_cleanup_failed"
_SCHEMA_NOT_READY = "supply_supplier_material_schema_not_ready"
_EVIDENCE_INVALID = "supply_supplier_material_evidence_invalid"
_SCAN_INCOMPLETE = "supply_supplier_material_evidence_scan_incomplete"
_CONFIRMATION_REQUIRED = "supply_supplier_material_confirmation_required"
_PROOF_PARTIAL = "supply_supplier_material_proof_partial"
_DEPENDENCY_INVALID = "supply_supplier_material_dependency_invalid"
_DEPENDENCY_INCOMPLETE = "supply_supplier_material_dependency_incomplete"
_NO_CANDIDATES = "supply_supplier_no_active_company_links"

_CONFIRMATION_FIELDS = {
    "confirmationVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "subjectKind", "readyForMaterialCapabilityConfirmation",
    "confirmationSubjectCount", "confirmationSubjects",
    "materialEligibilityProven", "rankingApplied", "supplierIds",
    "selectionAllowed", "sendAllowed", "blockers", "confirmationSha256",
}
_SOURCE_FIELDS = {
    "companyId", "requestId", "requestItemIndex", "requestItemSha256",
    "rfqContentSha256", "supplierEligibilitySha256",
    "materialIdentitySha256",
}
_CONFIRMATION_SUBJECT_FIELDS = {
    "companySupplierLinkId", "supplierId", "confirmationSubjectSha256",
}
_ASSERTION_FIELDS = {
    "id", "confirmation_version", "event_kind", "company_id",
    "company_supplier_link_id", "supplier_id",
    "material_identity_sha256", "confirmation_subject_sha256",
    "actor_membership_id", "actor_user_id", "actor_role", "source_kind",
    "revokes_assertion_id",
}


class SupplierMaterialCapabilityProofError(ValueError):
    """Fixed error code safe to expose without database or business text."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


class _EvidenceInvalid(Exception):
    pass


def _canonical_sha256(value):
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _positive_int(value):
    return type(value) is int and value > 0


def _non_negative_int(value):
    return type(value) is int and value >= 0


def calculate_proof_sha256(result):
    """Hash the full inert proof decision, including transaction metadata."""

    return _canonical_sha256({
        "domain": PROOF_DOMAIN,
        "version": result.get("proofVersion"),
        "ok": result.get("ok"),
        "dryRun": result.get("dryRun"),
        "writesAttempted": result.get("writesAttempted"),
        "state": result.get("state"),
        "source": result.get("source"),
        "subjectKind": result.get("subjectKind"),
        "confirmationSha256": result.get("confirmationSha256"),
        "confirmationSubjectCount": result.get(
            "confirmationSubjectCount"
        ),
        "proofSubjectCount": result.get("proofSubjectCount"),
        "provenSubjectCount": result.get("provenSubjectCount"),
        "proofSubjects": result.get("proofSubjects"),
        "materialEligibilityProven": result.get(
            "materialEligibilityProven"
        ),
        "rankingApplied": result.get("rankingApplied"),
        "supplierIds": result.get("supplierIds"),
        "selectionAllowed": result.get("selectionAllowed"),
        "sendAllowed": result.get("sendAllowed"),
        "blockers": result.get("blockers"),
        "readOnlyTransaction": result.get("readOnlyTransaction"),
        "rolledBack": result.get("rolledBack"),
    })


def _result(
    *, source, confirmation_sha256, confirmation_subject_count, state,
    blockers, proof_subjects=(), transaction_complete=False,
):
    subjects = [copy.deepcopy(subject) for subject in proof_subjects]
    proven = sum(
        subject.get("proofState") == "confirmed" for subject in subjects
    )
    result = {
        "proofVersion": PROOF_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": state,
        "source": copy.deepcopy(source),
        "subjectKind": SUBJECT_KIND,
        "confirmationSha256": confirmation_sha256,
        "confirmationSubjectCount": confirmation_subject_count,
        "proofSubjectCount": len(subjects),
        "provenSubjectCount": proven,
        "proofSubjects": subjects,
        "materialEligibilityProven": (
            state == "proof_complete"
            and confirmation_subject_count > 0
            and proven == confirmation_subject_count
        ),
        "rankingApplied": False,
        "supplierIds": [],
        "selectionAllowed": False,
        "sendAllowed": False,
        "blockers": sorted(set(blockers)),
        "proofSha256": None,
        "readOnlyTransaction": transaction_complete,
        "rolledBack": transaction_complete,
    }
    result["proofSha256"] = calculate_proof_sha256(result)
    return result


def _validated_confirmation(value):
    if type(value) is not dict or set(value) != _CONFIRMATION_FIELDS:
        raise _EvidenceInvalid()
    source = value.get("source")
    subjects = value.get("confirmationSubjects")
    if (
        value.get("confirmationVersion") != 1
        or type(value.get("confirmationVersion")) is not int
        or value.get("ok") is not True
        or value.get("dryRun") is not True
        or type(value.get("writesAttempted")) is not int
        or value.get("writesAttempted") != 0
        or value.get("subjectKind") != SUBJECT_KIND
        or value.get("materialEligibilityProven") is not False
        or value.get("rankingApplied") is not False
        or type(value.get("supplierIds")) is not list
        or value.get("supplierIds") != []
        or value.get("selectionAllowed") is not False
        or value.get("sendAllowed") is not False
        or type(source) is not dict
        or set(source) != _SOURCE_FIELDS
        or not _positive_int(source.get("companyId"))
        or not _positive_int(source.get("requestId"))
        or not _non_negative_int(source.get("requestItemIndex"))
        or any(not _sha256(source.get(field)) for field in (
            "requestItemSha256", "rfqContentSha256",
            "supplierEligibilitySha256", "materialIdentitySha256",
        ))
        or not _sha256(value.get("confirmationSha256"))
        or type(subjects) is not list
        or len(subjects) > MAX_CONFIRMATION_SUBJECTS
        or type(value.get("confirmationSubjectCount")) is not int
        or value.get("confirmationSubjectCount") != len(subjects)
        or type(value.get("blockers")) is not list
    ):
        raise _EvidenceInvalid()

    state = value.get("state")
    if state == "confirmation_ready":
        if (
            not subjects
            or value.get("readyForMaterialCapabilityConfirmation") is not True
            or value.get("blockers") != []
        ):
            raise _EvidenceInvalid()
    elif state == "no_candidates":
        if (
            subjects
            or value.get("readyForMaterialCapabilityConfirmation") is not False
            or value.get("blockers") != [_NO_CANDIDATES]
        ):
            raise _EvidenceInvalid()
    else:
        raise _EvidenceInvalid()

    validated = []
    seen_links = set()
    seen_suppliers = set()
    seen_hashes = set()
    for raw in subjects:
        if type(raw) is not dict or set(raw) != _CONFIRMATION_SUBJECT_FIELDS:
            raise _EvidenceInvalid()
        link_id = raw.get("companySupplierLinkId")
        supplier_id = raw.get("supplierId")
        subject_sha256 = raw.get("confirmationSubjectSha256")
        if (
            not _positive_int(link_id)
            or not _positive_int(supplier_id)
            or not _sha256(subject_sha256)
            or link_id in seen_links
            or supplier_id in seen_suppliers
            or subject_sha256 in seen_hashes
        ):
            raise _EvidenceInvalid()
        seen_links.add(link_id)
        seen_suppliers.add(supplier_id)
        seen_hashes.add(subject_sha256)
        validated.append({
            "companySupplierLinkId": link_id,
            "supplierId": supplier_id,
            "confirmationSubjectSha256": subject_sha256,
        })
    if validated != sorted(
        validated,
        key=lambda item: (
            item["supplierId"], item["companySupplierLinkId"]
        ),
    ):
        raise _EvidenceInvalid()
    return copy.deepcopy(source), validated


def _dependency_source(prepared, content, eligibility):
    source = prepared.get("source") if type(prepared) is dict else {}
    candidate = prepared.get("candidate") if type(prepared) is dict else {}
    content_hash = content.get("contentSha256") if type(content) is dict else None
    item_hash = content.get("requestItemSha256") if type(content) is dict else None
    eligibility_hash = (
        eligibility.get("eligibilitySha256")
        if type(eligibility) is dict else None
    )
    return {
        "companyId": source.get("companyId") if type(source) is dict else None,
        "requestId": (
            candidate.get("requestId") if type(candidate) is dict else None
        ),
        "requestItemIndex": (
            candidate.get("requestItemIndex")
            if type(candidate) is dict else None
        ),
        "requestItemSha256": item_hash if _sha256(item_hash) else None,
        "rfqContentSha256": content_hash if _sha256(content_hash) else None,
        "supplierEligibilitySha256": (
            eligibility_hash if _sha256(eligibility_hash) else None
        ),
        "materialIdentitySha256": None,
    }


def _configure_transaction(cur):
    cur.execute(
        """SELECT pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true)
             LIMIT %s""",
        (
            "statement_timeout", "60000",
            "lock_timeout", "5000",
            "idle_in_transaction_session_timeout", "60000",
            "search_path", "pg_catalog,public",
            1,
        ),
    )


def _read_assertions(cur, company_id, subjects):
    hashes = sorted(
        subject["confirmationSubjectSha256"] for subject in subjects
    )
    limit = 2 * len(hashes) + 1
    cur.execute(
        """SELECT id,confirmation_version,event_kind,company_id,
                  company_supplier_link_id,supplier_id,
                  material_identity_sha256,confirmation_subject_sha256,
                  actor_membership_id,actor_user_id,actor_role,source_kind,
                  revokes_assertion_id
             FROM public.supplier_material_capability_assertions
            WHERE company_id=%s
              AND confirmation_subject_sha256=ANY(%s::varchar[])
            ORDER BY confirmation_subject_sha256,id
            LIMIT %s""",
        (company_id, hashes, limit),
    )
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return None if len(rows) >= limit else rows


def _evidence(row):
    return {
        "assertionId": row["id"],
        "eventKind": row["event_kind"],
        "actorMembershipId": row["actor_membership_id"],
        "actorUserId": row["actor_user_id"],
        "actorRole": row["actor_role"],
        "sourceKind": row["source_kind"],
        "revokesAssertionId": row["revokes_assertion_id"],
    }


def _validated_proof_subjects(source, subjects, rows):
    expected = {
        subject["confirmationSubjectSha256"]: subject
        for subject in subjects
    }
    grouped = {subject_sha256: [] for subject_sha256 in expected}
    seen_ids = set()
    for row in rows:
        if type(row) is not dict or set(row) != _ASSERTION_FIELDS:
            raise _EvidenceInvalid()
        row_id = row.get("id")
        subject_sha256 = row.get("confirmation_subject_sha256")
        subject = expected.get(subject_sha256)
        revoke_id = row.get("revokes_assertion_id")
        if (
            not _positive_int(row_id)
            or row_id in seen_ids
            or type(row.get("confirmation_version")) is not int
            or row.get("confirmation_version") != 1
            or row.get("event_kind") not in {"confirmed", "revoked"}
            or type(row.get("event_kind")) is not str
            or not _positive_int(row.get("company_id"))
            or row.get("company_id") != source["companyId"]
            or subject is None
            or row.get("company_supplier_link_id") != subject[
                "companySupplierLinkId"
            ]
            or not _positive_int(row.get("company_supplier_link_id"))
            or row.get("supplier_id") != subject["supplierId"]
            or not _positive_int(row.get("supplier_id"))
            or row.get("material_identity_sha256") != source[
                "materialIdentitySha256"
            ]
            or not _sha256(row.get("material_identity_sha256"))
            or not _sha256(subject_sha256)
            or not _positive_int(row.get("actor_membership_id"))
            or not _positive_int(row.get("actor_user_id"))
            or type(row.get("actor_role")) is not str
            or row.get("actor_role") != "директор"
            or type(row.get("source_kind")) is not str
            or row.get("source_kind") != "director_manual"
            or (
                row.get("event_kind") == "confirmed"
                and revoke_id is not None
            )
            or (
                row.get("event_kind") == "revoked"
                and not _positive_int(revoke_id)
            )
        ):
            raise _EvidenceInvalid()
        seen_ids.add(row_id)
        grouped[subject_sha256].append(row)
        if len(grouped[subject_sha256]) > 2:
            raise _EvidenceInvalid()

    proof_subjects = []
    for subject in subjects:
        subject_sha256 = subject["confirmationSubjectSha256"]
        group = grouped[subject_sha256]
        confirmed = [row for row in group if row["event_kind"] == "confirmed"]
        revoked = [row for row in group if row["event_kind"] == "revoked"]
        if not group:
            proof_state = "missing"
            evidence = []
        elif len(confirmed) == 1 and not revoked:
            proof_state = "confirmed"
            evidence = [_evidence(confirmed[0])]
        elif (
            len(confirmed) == 1
            and len(revoked) == 1
            and revoked[0]["revokes_assertion_id"] == confirmed[0]["id"]
        ):
            proof_state = "revoked"
            evidence = [_evidence(confirmed[0]), _evidence(revoked[0])]
        else:
            raise _EvidenceInvalid()
        proof_subjects.append({
            "companySupplierLinkId": subject["companySupplierLinkId"],
            "supplierId": subject["supplierId"],
            "materialIdentitySha256": source["materialIdentitySha256"],
            "confirmationSubjectSha256": subject_sha256,
            "proofState": proof_state,
            "evidence": evidence,
        })
    return proof_subjects


def _state_for_subjects(subjects):
    confirmed = sum(
        subject["proofState"] == "confirmed" for subject in subjects
    )
    if confirmed == len(subjects):
        return "proof_complete", []
    if confirmed:
        return "proof_partial", [_PROOF_PARTIAL]
    return "confirmation_required", [_CONFIRMATION_REQUIRED]


def _collect_snapshot(cur, prepared):
    content = collect_prepared_supply_rfq_content(cur, prepared)
    eligibility = collect_prepared_supply_supplier_eligibility(
        cur, prepared, content,
    )
    try:
        confirmation = _build_material_capability_confirmation_snapshot(
            content, eligibility,
        )
        source, subjects = _validated_confirmation(confirmation)
    except (MaterialCapabilityConfirmationError, _EvidenceInvalid):
        state = "incomplete" if (
            (type(content) is dict and content.get("state") == "incomplete")
            or (
                type(eligibility) is dict
                and eligibility.get("state") == "incomplete"
            )
        ) else "needs_review"
        blocker = (
            _DEPENDENCY_INCOMPLETE if state == "incomplete"
            else _DEPENDENCY_INVALID
        )
        return (
            _result(
                source=_dependency_source(prepared, content, eligibility),
                confirmation_sha256=None,
                confirmation_subject_count=0,
                state=state,
                blockers=[blocker],
            ),
            content,
            eligibility,
            None,
        )

    if not subjects:
        return (
            _result(
                source=source,
                confirmation_sha256=confirmation["confirmationSha256"],
                confirmation_subject_count=0,
                state="no_candidates",
                blockers=[_NO_CANDIDATES],
            ),
            content,
            eligibility,
            confirmation,
        )

    try:
        schema = (
            material_capability_schema_probe
            .collect_material_capability_schema_readiness(cur)
        )
    except Exception:
        schema = None
    if (
        type(schema) is not dict
        or schema.get("contractVersion") != CONTRACT_VERSION
        or schema.get("complete") is not True
        or schema.get("blockers") != []
    ):
        return (
            _result(
                source=source,
                confirmation_sha256=confirmation["confirmationSha256"],
                confirmation_subject_count=len(subjects),
                state="incomplete",
                blockers=[_SCHEMA_NOT_READY],
            ),
            content,
            eligibility,
            confirmation,
        )

    rows = _read_assertions(cur, source["companyId"], subjects)
    if rows is None:
        result = _result(
            source=source,
            confirmation_sha256=confirmation["confirmationSha256"],
            confirmation_subject_count=len(subjects),
            state="incomplete",
            blockers=[_SCAN_INCOMPLETE],
        )
    else:
        try:
            proof_subjects = _validated_proof_subjects(
                source, subjects, rows,
            )
            state, blockers = _state_for_subjects(proof_subjects)
            result = _result(
                source=source,
                confirmation_sha256=confirmation["confirmationSha256"],
                confirmation_subject_count=len(subjects),
                state=state,
                blockers=blockers,
                proof_subjects=proof_subjects,
            )
        except _EvidenceInvalid:
            result = _result(
                source=source,
                confirmation_sha256=confirmation["confirmationSha256"],
                confirmation_subject_count=len(subjects),
                state="needs_review",
                blockers=[_EVIDENCE_INVALID],
            )
    return result, content, eligibility, confirmation


def _completed_confirmation(content, eligibility):
    completed_content = copy.deepcopy(content)
    completed_eligibility = copy.deepcopy(eligibility)
    completed_content["readOnlyTransaction"] = True
    completed_content["rolledBack"] = True
    completed_eligibility["readOnlyTransaction"] = True
    completed_eligibility["rolledBack"] = True
    return build_material_capability_confirmation_readiness(
        completed_content, completed_eligibility,
    )


def run_supplier_material_capability_proof_preview(
    get_db, combined_report, selected,
):
    """Collect one authoritative proof preview and always roll back."""

    try:
        prepared = prepare_supply_rfq_content(combined_report, selected)
    except Exception:
        raise SupplierMaterialCapabilityProofError(_INPUT_INVALID) from None

    connection = None
    cur = None
    collected = None
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
        _configure_transaction(cur)
        collected = _collect_snapshot(cur, prepared)
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
        raise SupplierMaterialCapabilityProofError(
            _ROLLBACK_FAILED
        ) from None
    if primary_error is not None:
        raise SupplierMaterialCapabilityProofError(_READ_FAILED) from None
    if cleanup_error is not None:
        raise SupplierMaterialCapabilityProofError(_CLEANUP_FAILED) from None

    try:
        result, content, eligibility, snapshot_confirmation = collected
        if snapshot_confirmation is not None:
            completed_confirmation = _completed_confirmation(
                content, eligibility,
            )
            if completed_confirmation != snapshot_confirmation:
                raise _EvidenceInvalid()
        result["readOnlyTransaction"] = True
        result["rolledBack"] = True
        result["proofSha256"] = calculate_proof_sha256(result)
        return result
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except Exception:
        raise SupplierMaterialCapabilityProofError(_READ_FAILED) from None


__all__ = [
    "PROOF_VERSION",
    "SupplierMaterialCapabilityProofError",
    "calculate_proof_sha256",
    "run_supplier_material_capability_proof_preview",
]
