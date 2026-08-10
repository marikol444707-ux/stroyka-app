"""Pure A8.4a readiness for exact supplier-material confirmations.

The hashes built here identify confirmation subjects.  They are not
authorization, proof of current database state, or proof of supplier
capability.  A later trusted collector must establish those properties.
"""

import hashlib
import json
import re

CONFIRMATION_VERSION = 1
_RFQ_CONTENT_VERSION = 1
_ELIGIBILITY_VERSION = 1
_MAX_CANDIDATES = 100
_MAX_MATERIAL_TEXT_LENGTH = 200
_MAX_UNIT_TEXT_LENGTH = 50
_RFQ_CONTENT_ELIGIBLE_STATUSES = {"Утверждена", "КП запрошены"}
_SOURCE_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_QUANTITY_RE = re.compile(r"^(0|[1-9][0-9]{0,13})\.([0-9]{6})$")
MATERIAL_IDENTITY_DOMAIN = (
    "stroyka.supply.material_capability_confirmation.material_identity"
)
CONFIRMATION_SUBJECT_DOMAIN = (
    "stroyka.supply.material_capability_confirmation.subject"
)
CONFIRMATION_READINESS_DOMAIN = (
    "stroyka.supply.material_capability_confirmation.readiness"
)
SUBJECT_KIND = "supplier_material_capability_confirmation"
INVALID_INPUT = "material_capability_confirmation_input_invalid"

_RFQ_FIELDS = {
    "contentVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "candidate", "readyForRfqDraft", "blockers", "request",
    "balance", "rfqDraft", "requestItemSha256", "contentSha256",
    "readOnlyTransaction", "rolledBack",
}
_RFQ_SOURCE_FIELDS = {
    "companyId", "projectId", "estimateId", "sourceRevision",
    "reconciliationId", "baseEstimateId", "impactEvidenceSha256",
}
_CANDIDATE_FIELDS = {
    "requestId", "requestItemIndex", "base", "target", "matchKind",
    "aliasIds", "changeKinds",
}
_COORDINATE_FIELDS = {"estimateId", "sectionIndex", "itemIndex"}
_REQUEST_FIELDS = {"requestId", "requestItemIndex", "status"}
_BALANCE_FIELDS = {
    "requestedQuantity", "receivedQuantity", "allocatedQuantity",
    "openQuantity", "unit",
}
_DRAFT_FIELDS = {"status", "sendAllowed", "supplierIds", "items"}
_ITEM_FIELDS = {"materialName", "quantity", "unit", "lineage"}
_LINEAGE_FIELDS = {"requestId", "requestItemIndex", "base", "target"}
_ELIGIBILITY_FIELDS = {
    "eligibilityVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "candidateKind", "readyForHumanSupplierReview",
    "materialEligibilityProven", "rankingApplied", "candidateCount",
    "candidateSupplierLinks", "supplierIds", "selectionAllowed",
    "sendAllowed", "blockers", "eligibilitySha256",
    "readOnlyTransaction", "rolledBack",
}
_ELIGIBILITY_SOURCE_FIELDS = {
    "companyId", "requestId", "requestItemIndex", "requestItemSha256",
    "rfqContentSha256",
}
_ELIGIBILITY_CANDIDATE_FIELDS = {
    "companySupplierLinkId", "supplierId", "evidence",
}
_CANDIDATE_EVIDENCE = [
    "company_link_exact",
    "supplier_card_active",
    "supplier_portal_user_direct_active",
]
_MATCH_KINDS = {"stable_item_key", "confirmed_alias"}
_CHANGE_KINDS = {
    "quantity_changed", "identity_changed", "alias_identity_changed",
}
_NO_CANDIDATE_BLOCKERS = ["supply_supplier_no_active_company_links"]


class MaterialCapabilityConfirmationError(ValueError):
    """Fixed error code safe to expose without input or business text."""

    def __init__(self, code=INVALID_INPUT):
        self.code = str(code)
        super().__init__(self.code)


def _fail():
    raise MaterialCapabilityConfirmationError()


def _mapping(value, fields):
    if (
        type(value) is not dict
        or len(value) != len(fields)
        or set(value) != fields
    ):
        _fail()
    return value


def _positive_int(value):
    if type(value) is int and value > 0:
        return value
    _fail()


def _non_negative_int(value):
    if type(value) is int and value >= 0:
        return value
    _fail()


def _zero(value):
    if type(value) is not int or value != 0:
        _fail()


def _sha256(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail()
    return value


def _json_sha256(value, *, ensure_ascii):
    try:
        payload = json.dumps(
            value,
            ensure_ascii=ensure_ascii,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError, ValueError, RecursionError, UnicodeError, OverflowError,
    ) as exc:
        raise MaterialCapabilityConfirmationError() from exc
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value):
    return _json_sha256(value, ensure_ascii=True)


# Keep these deployed A8.2/A8.3 preimages local.  Importing their collectors
# would load database and runtime modules into this intentionally pure seam.
def _calculate_content_sha256(result):
    return _json_sha256({
        "contentVersion": result.get("contentVersion"),
        "source": result.get("source"),
        "candidate": result.get("candidate"),
        "request": result.get("request"),
        "balance": result.get("balance"),
        "rfqDraft": result.get("rfqDraft"),
        "requestItemSha256": result.get("requestItemSha256"),
    }, ensure_ascii=False)


def _calculate_eligibility_sha256(result):
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


def _coordinate(value):
    value = _mapping(value, _COORDINATE_FIELDS)
    return {
        "estimateId": _positive_int(value.get("estimateId")),
        "sectionIndex": _non_negative_int(value.get("sectionIndex")),
        "itemIndex": _non_negative_int(value.get("itemIndex")),
    }


def _rfq_source(value):
    value = _mapping(value, _RFQ_SOURCE_FIELDS)
    source = {
        "companyId": _positive_int(value.get("companyId")),
        "projectId": _positive_int(value.get("projectId")),
        "estimateId": _positive_int(value.get("estimateId")),
        "sourceRevision": value.get("sourceRevision"),
        "reconciliationId": _positive_int(value.get("reconciliationId")),
        "baseEstimateId": _positive_int(value.get("baseEstimateId")),
        "impactEvidenceSha256": _sha256(
            value.get("impactEvidenceSha256")
        ),
    }
    if (
        source["baseEstimateId"] == source["estimateId"]
        or type(source["sourceRevision"]) is not str
        or len(source["sourceRevision"]) != 71
        or not _SOURCE_REVISION_RE.fullmatch(source["sourceRevision"])
    ):
        _fail()
    return source


def _candidate(value, source):
    value = _mapping(value, _CANDIDATE_FIELDS)
    base = _coordinate(value.get("base"))
    target = _coordinate(value.get("target"))
    alias_ids = value.get("aliasIds")
    change_kinds = value.get("changeKinds")
    match_kind = value.get("matchKind")
    if (
        type(alias_ids) is not list
        or len(alias_ids) > _MAX_CANDIDATES
        or any(
            type(item) is not int or item <= 0
            for item in alias_ids
        )
        or alias_ids != sorted(set(alias_ids))
        or type(change_kinds) is not list
        or not change_kinds
        or len(change_kinds) > len(_CHANGE_KINDS)
        or any(
            type(kind) is not str or len(kind) > 32
            for kind in change_kinds
        )
        or change_kinds != sorted(set(change_kinds))
        or any(kind not in _CHANGE_KINDS for kind in change_kinds)
        or type(match_kind) is not str
        or len(match_kind) > 32
        or match_kind not in _MATCH_KINDS
        or (match_kind == "confirmed_alias" and not alias_ids)
        or (
            match_kind == "confirmed_alias"
            and "identity_changed" in change_kinds
        )
        or (
            match_kind == "stable_item_key"
            and "alias_identity_changed" in change_kinds
        )
        or (
            match_kind == "stable_item_key"
            and "identity_changed" in change_kinds
        )
        or base["estimateId"] != source["baseEstimateId"]
        or target["estimateId"] != source["estimateId"]
    ):
        _fail()
    return {
        "requestId": _positive_int(value.get("requestId")),
        "requestItemIndex": _non_negative_int(value.get("requestItemIndex")),
        "base": base,
        "target": target,
        "matchKind": match_kind,
        "aliasIds": list(alias_ids),
        "changeKinds": list(change_kinds),
    }


def _bounded_exact_text(value, maximum):
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or value.strip() != value
        or any(ord(character) < 32 for character in value)
    ):
        _fail()
    return value


def _quantity(value, *, positive=False):
    if type(value) is not str or len(value) > 21:
        _fail()
    matched = _QUANTITY_RE.fullmatch(value)
    if matched is None:
        _fail()
    scaled = int(matched.group(1)) * 1_000_000 + int(matched.group(2))
    if positive and scaled <= 0:
        _fail()
    return scaled


def _validated_rfq(content, *, transaction_complete):
    content = _mapping(content, _RFQ_FIELDS)
    _zero(content.get("writesAttempted"))
    if (
        type(content.get("contentVersion")) is not int
        or content.get("contentVersion") != _RFQ_CONTENT_VERSION
        or content.get("ok") is not True
        or content.get("dryRun") is not True
        or type(content.get("state")) is not str
        or content.get("state") != "draft_ready"
        or content.get("readyForRfqDraft") is not True
        or type(content.get("blockers")) is not list
        or content.get("blockers") != []
        or content.get("readOnlyTransaction") is not transaction_complete
        or content.get("rolledBack") is not transaction_complete
    ):
        _fail()

    source = _rfq_source(content.get("source"))
    candidate = _candidate(content.get("candidate"), source)
    request = _mapping(content.get("request"), _REQUEST_FIELDS)
    request_id = _positive_int(request.get("requestId"))
    request_item_index = _non_negative_int(request.get("requestItemIndex"))
    request_status = request.get("status")
    if (
        request_id != candidate["requestId"]
        or request_item_index != candidate["requestItemIndex"]
        or type(request_status) is not str
        or len(request_status) > 32
        or request_status not in _RFQ_CONTENT_ELIGIBLE_STATUSES
    ):
        _fail()

    balance = _mapping(content.get("balance"), _BALANCE_FIELDS)
    requested = _quantity(balance.get("requestedQuantity"), positive=True)
    received = _quantity(balance.get("receivedQuantity"))
    allocated = _quantity(balance.get("allocatedQuantity"))
    remaining = _quantity(balance.get("openQuantity"), positive=True)
    unit = _bounded_exact_text(balance.get("unit"), _MAX_UNIT_TEXT_LENGTH)
    if requested - received - allocated != remaining:
        _fail()

    draft = _mapping(content.get("rfqDraft"), _DRAFT_FIELDS)
    items = draft.get("items")
    if (
        type(draft.get("status")) is not str
        or draft.get("status") != "human_supplier_selection_required"
        or draft.get("sendAllowed") is not False
        or type(draft.get("supplierIds")) is not list
        or draft.get("supplierIds") != []
        or type(items) is not list
        or len(items) != 1
    ):
        _fail()
    item = _mapping(items[0], _ITEM_FIELDS)
    material_name = _bounded_exact_text(
        item.get("materialName"), _MAX_MATERIAL_TEXT_LENGTH
    )
    item_unit = _bounded_exact_text(item.get("unit"), _MAX_UNIT_TEXT_LENGTH)
    if (
        item_unit != unit
        or item.get("quantity") != balance.get("openQuantity")
    ):
        _fail()
    _quantity(item.get("quantity"), positive=True)

    lineage = _mapping(item.get("lineage"), _LINEAGE_FIELDS)
    if (
        _positive_int(lineage.get("requestId")) != candidate["requestId"]
        or _non_negative_int(lineage.get("requestItemIndex"))
        != candidate["requestItemIndex"]
        or _coordinate(lineage.get("base")) != candidate["base"]
        or _coordinate(lineage.get("target")) != candidate["target"]
    ):
        _fail()

    request_item_sha256 = _sha256(content.get("requestItemSha256"))
    content_sha256 = _sha256(content.get("contentSha256"))
    if _calculate_content_sha256(content) != content_sha256:
        _fail()
    return {
        "source": source,
        "candidate": candidate,
        "materialName": material_name,
        "unit": unit,
        "requestItemSha256": request_item_sha256,
        "contentSha256": content_sha256,
    }


def _validated_eligibility(
    eligibility, rfq, *, transaction_complete,
):
    eligibility = _mapping(eligibility, _ELIGIBILITY_FIELDS)
    _zero(eligibility.get("writesAttempted"))
    if (
        type(eligibility.get("eligibilityVersion")) is not int
        or eligibility.get("eligibilityVersion") != _ELIGIBILITY_VERSION
        or eligibility.get("ok") is not True
        or eligibility.get("dryRun") is not True
        or type(eligibility.get("candidateKind")) is not str
        or eligibility.get("candidateKind") != "company_link_account_ready"
        or eligibility.get("materialEligibilityProven") is not False
        or eligibility.get("rankingApplied") is not False
        or type(eligibility.get("supplierIds")) is not list
        or eligibility.get("supplierIds") != []
        or eligibility.get("selectionAllowed") is not False
        or eligibility.get("sendAllowed") is not False
        or eligibility.get("readOnlyTransaction") is not transaction_complete
        or eligibility.get("rolledBack") is not transaction_complete
    ):
        _fail()

    raw_source = _mapping(
        eligibility.get("source"), _ELIGIBILITY_SOURCE_FIELDS
    )
    source = {
        "companyId": _positive_int(raw_source.get("companyId")),
        "requestId": _positive_int(raw_source.get("requestId")),
        "requestItemIndex": _non_negative_int(
            raw_source.get("requestItemIndex")
        ),
        "requestItemSha256": _sha256(
            raw_source.get("requestItemSha256")
        ),
        "rfqContentSha256": _sha256(
            raw_source.get("rfqContentSha256")
        ),
    }
    expected_source = {
        "companyId": rfq["source"]["companyId"],
        "requestId": rfq["candidate"]["requestId"],
        "requestItemIndex": rfq["candidate"]["requestItemIndex"],
        "requestItemSha256": rfq["requestItemSha256"],
        "rfqContentSha256": rfq["contentSha256"],
    }
    if source != expected_source:
        _fail()

    candidates = eligibility.get("candidateSupplierLinks")
    count = eligibility.get("candidateCount")
    if (
        type(candidates) is not list
        or len(candidates) > _MAX_CANDIDATES
        or type(count) is not int
        or count != len(candidates)
    ):
        _fail()

    state = eligibility.get("state")
    blockers = eligibility.get("blockers")
    if type(state) is not str or len(state) > 32 or type(blockers) is not list:
        _fail()
    if state == "no_candidates":
        if (
            eligibility.get("readyForHumanSupplierReview") is not False
            or candidates
            or any(type(code) is not str for code in blockers)
            or blockers != _NO_CANDIDATE_BLOCKERS
        ):
            _fail()
    elif state == "review_ready":
        if (
            eligibility.get("readyForHumanSupplierReview") is not True
            or not candidates
            or blockers != []
        ):
            _fail()
    else:
        _fail()

    validated_candidates = []
    seen_links = set()
    seen_suppliers = set()
    for raw_candidate in candidates:
        raw_candidate = _mapping(
            raw_candidate, _ELIGIBILITY_CANDIDATE_FIELDS
        )
        link_id = _positive_int(raw_candidate.get("companySupplierLinkId"))
        supplier_id = _positive_int(raw_candidate.get("supplierId"))
        evidence = raw_candidate.get("evidence")
        if (
            type(evidence) is not list
            or any(type(code) is not str for code in evidence)
            or evidence != _CANDIDATE_EVIDENCE
            or link_id in seen_links
            or supplier_id in seen_suppliers
        ):
            _fail()
        seen_links.add(link_id)
        seen_suppliers.add(supplier_id)
        validated_candidates.append({
            "companySupplierLinkId": link_id,
            "supplierId": supplier_id,
        })
    if validated_candidates != sorted(
        validated_candidates,
        key=lambda item: (
            item["supplierId"], item["companySupplierLinkId"]
        ),
    ):
        _fail()

    eligibility_sha256 = _sha256(eligibility.get("eligibilitySha256"))
    if _calculate_eligibility_sha256(eligibility) != eligibility_sha256:
        _fail()
    return state, validated_candidates, eligibility_sha256


def _material_identity_sha256(rfq):
    source = rfq["source"]
    candidate = rfq["candidate"]
    return _canonical_sha256({
        "domain": MATERIAL_IDENTITY_DOMAIN,
        "version": CONFIRMATION_VERSION,
        "companyId": source["companyId"],
        "projectId": source["projectId"],
        "sourceRevision": source["sourceRevision"],
        "requestId": candidate["requestId"],
        "requestItemIndex": candidate["requestItemIndex"],
        "target": candidate["target"],
        "materialName": rfq["materialName"],
        "unit": rfq["unit"],
    })


def _confirmation_sha256(result):
    return _canonical_sha256({
        "domain": CONFIRMATION_READINESS_DOMAIN,
        "version": result["confirmationVersion"],
        "ok": result["ok"],
        "dryRun": result["dryRun"],
        "writesAttempted": result["writesAttempted"],
        "state": result["state"],
        "source": result["source"],
        "subjectKind": result["subjectKind"],
        "readyForMaterialCapabilityConfirmation": result[
            "readyForMaterialCapabilityConfirmation"
        ],
        "confirmationSubjectCount": result["confirmationSubjectCount"],
        "confirmationSubjects": result["confirmationSubjects"],
        "materialEligibilityProven": result["materialEligibilityProven"],
        "rankingApplied": result["rankingApplied"],
        "supplierIds": result["supplierIds"],
        "selectionAllowed": result["selectionAllowed"],
        "sendAllowed": result["sendAllowed"],
        "blockers": result["blockers"],
    })


def _build_material_capability_confirmation_readiness(
    rfq_content_result, supplier_eligibility_result, *,
    transaction_complete=True,
):
    """Build inert confirmation subjects from exact A8.2/A8.3 results."""

    try:
        rfq = _validated_rfq(
            rfq_content_result,
            transaction_complete=transaction_complete,
        )
        state, candidates, eligibility_sha256 = _validated_eligibility(
            supplier_eligibility_result,
            rfq,
            transaction_complete=transaction_complete,
        )
        material_identity_sha256 = _material_identity_sha256(rfq)
        source = {
            "companyId": rfq["source"]["companyId"],
            "requestId": rfq["candidate"]["requestId"],
            "requestItemIndex": rfq["candidate"]["requestItemIndex"],
            "requestItemSha256": rfq["requestItemSha256"],
            "rfqContentSha256": rfq["contentSha256"],
            "supplierEligibilitySha256": eligibility_sha256,
            "materialIdentitySha256": material_identity_sha256,
        }
        subjects = []
        for candidate in candidates:
            subject = {
                "companySupplierLinkId": candidate[
                    "companySupplierLinkId"
                ],
                "supplierId": candidate["supplierId"],
                "confirmationSubjectSha256": None,
            }
            subject["confirmationSubjectSha256"] = _canonical_sha256({
                "domain": CONFIRMATION_SUBJECT_DOMAIN,
                "version": CONFIRMATION_VERSION,
                "source": source,
                "subjectKind": SUBJECT_KIND,
                "companySupplierLinkId": subject[
                    "companySupplierLinkId"
                ],
                "supplierId": subject["supplierId"],
            })
            subjects.append(subject)

        ready = state == "review_ready"
        result = {
            "confirmationVersion": CONFIRMATION_VERSION,
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "state": "confirmation_ready" if ready else "no_candidates",
            "source": source,
            "subjectKind": SUBJECT_KIND,
            "readyForMaterialCapabilityConfirmation": ready,
            "confirmationSubjectCount": len(subjects),
            "confirmationSubjects": subjects,
            "materialEligibilityProven": False,
            "rankingApplied": False,
            "supplierIds": [],
            "selectionAllowed": False,
            "sendAllowed": False,
            "blockers": [] if ready else list(_NO_CANDIDATE_BLOCKERS),
            "confirmationSha256": None,
        }
        result["confirmationSha256"] = _confirmation_sha256(result)
        return result
    except MaterialCapabilityConfirmationError:
        raise
    except Exception as exc:
        raise MaterialCapabilityConfirmationError() from exc


def _build_material_capability_confirmation_snapshot(
    rfq_content_result, supplier_eligibility_result,
):
    """Build subjects only from dependencies still inside one snapshot."""

    try:
        return _build_material_capability_confirmation_readiness(
            rfq_content_result,
            supplier_eligibility_result,
            transaction_complete=False,
        )
    except Exception:
        pass
    raise MaterialCapabilityConfirmationError()


def build_material_capability_confirmation_readiness(
    rfq_content_result, supplier_eligibility_result,
):
    """Normalize every malformed dependency to one fixed public error."""

    try:
        return _build_material_capability_confirmation_readiness(
            rfq_content_result, supplier_eligibility_result
        )
    except Exception:
        pass
    raise MaterialCapabilityConfirmationError()


__all__ = [
    "CONFIRMATION_VERSION",
    "MaterialCapabilityConfirmationError",
    "build_material_capability_confirmation_readiness",
]
