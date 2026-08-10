import copy
import hashlib
import json
import subprocess
import sys
import traceback
import unittest
from collections.abc import Mapping
from decimal import localcontext
from pathlib import Path

from backend.features.supply_recommendation_preview import (
    material_capability_confirmation,
    rfq_content,
    supplier_eligibility,
)


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
EVIDENCE = [
    "company_link_exact",
    "supplier_card_active",
    "supplier_portal_user_direct_active",
]


class OversizedMapping(Mapping):
    def __init__(self):
        self.iterated = False

    def __len__(self):
        return 10_000

    def __iter__(self):
        self.iterated = True
        return iter(())

    def __getitem__(self, key):
        raise KeyError(key)


class OversizedList(list):
    def __init__(self, values):
        super().__init__(values)
        self.iterated = False

    def __iter__(self):
        self.iterated = True
        return super().__iter__()


class OversizedText(str):
    def __new__(cls):
        value = super().__new__(cls, "x" * 201)
        value.stripped = False
        return value

    def strip(self, *args, **kwargs):
        self.stripped = True
        return super().strip(*args, **kwargs)


class LeakyMapping(Mapping):
    def __len__(self):
        return 16

    def __iter__(self):
        raise RuntimeError("PRIVATE_MATERIAL_A500C")

    def __getitem__(self, key):
        raise KeyError(key)


class AlwaysEqualList(list):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


class AlwaysEqualText(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


class Poison(dict):
    def get(self, key, default=None):
        if key == "writesAttempted":
            raise material_capability_confirmation.MaterialCapabilityConfirmationError(
                "attacker_controlled"
            )
        return super().get(key, default)


class OversizedEnum(str):
    def __new__(cls):
        value = super().__new__(cls, "x" * 1_000_000)
        value.hashed = False
        return value

    def __hash__(self):
        self.hashed = True
        return super().__hash__()


def _canonical_sha256(value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _candidate_supplier_links(count):
    return [
        {
            "companySupplierLinkId": 61 + index,
            "supplierId": 71 + index,
            "evidence": list(EVIDENCE),
        }
        for index in range(count)
    ]


def _valid_dependencies(candidate_count=2):
    content = {
        "contentVersion": rfq_content.RFQ_CONTENT_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": "draft_ready",
        "source": {
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "sourceRevision": "sha256:" + "1" * 64,
            "reconciliationId": 91,
            "baseEstimateId": 51,
            "impactEvidenceSha256": "2" * 64,
        },
        "candidate": {
            "requestId": 21,
            "requestItemIndex": 0,
            "base": {
                "estimateId": 51,
                "sectionIndex": 0,
                "itemIndex": 0,
            },
            "target": {
                "estimateId": 52,
                "sectionIndex": 0,
                "itemIndex": 0,
            },
            "matchKind": "stable_item_key",
            "aliasIds": [],
            "changeKinds": ["quantity_changed"],
        },
        "readyForRfqDraft": True,
        "blockers": [],
        "request": {
            "requestId": 21,
            "requestItemIndex": 0,
            "status": "Утверждена",
        },
        "balance": {
            "requestedQuantity": "10.000000",
            "receivedQuantity": "3.000000",
            "allocatedQuantity": "2.000000",
            "openQuantity": "5.000000",
            "unit": "т",
        },
        "rfqDraft": {
            "status": "human_supplier_selection_required",
            "sendAllowed": False,
            "supplierIds": [],
            "items": [{
                "materialName": "Арматура A500C Ø12",
                "quantity": "5.000000",
                "unit": "т",
                "lineage": {
                    "requestId": 21,
                    "requestItemIndex": 0,
                    "base": {
                        "estimateId": 51,
                        "sectionIndex": 0,
                        "itemIndex": 0,
                    },
                    "target": {
                        "estimateId": 52,
                        "sectionIndex": 0,
                        "itemIndex": 0,
                    },
                },
            }],
        },
        "requestItemSha256": "3" * 64,
        "contentSha256": None,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }
    content["contentSha256"] = rfq_content.calculate_content_sha256(
        content
    )

    eligibility = {
        "eligibilityVersion": supplier_eligibility.ELIGIBILITY_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "state": "review_ready",
        "source": {
            "companyId": content["source"]["companyId"],
            "requestId": content["candidate"]["requestId"],
            "requestItemIndex": content["candidate"]["requestItemIndex"],
            "requestItemSha256": content["requestItemSha256"],
            "rfqContentSha256": content["contentSha256"],
        },
        "candidateKind": "company_link_account_ready",
        "readyForHumanSupplierReview": True,
        "materialEligibilityProven": False,
        "rankingApplied": False,
        "candidateCount": candidate_count,
        "candidateSupplierLinks": _candidate_supplier_links(
            candidate_count
        ),
        "supplierIds": [],
        "selectionAllowed": False,
        "sendAllowed": False,
        "blockers": [],
        "eligibilitySha256": None,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }
    eligibility["eligibilitySha256"] = (
        supplier_eligibility.calculate_eligibility_sha256(eligibility)
    )
    return content, eligibility


def _valid_no_candidates_dependencies():
    content, eligibility = _valid_dependencies(candidate_count=0)
    eligibility["state"] = "no_candidates"
    eligibility["readyForHumanSupplierReview"] = False
    eligibility["blockers"] = [
        "supply_supplier_no_active_company_links",
    ]
    eligibility["eligibilitySha256"] = (
        supplier_eligibility.calculate_eligibility_sha256(eligibility)
    )
    return content, eligibility


def _refresh_bindings(content, eligibility):
    content["contentSha256"] = rfq_content.calculate_content_sha256(
        content
    )
    eligibility["source"]["companyId"] = content["source"]["companyId"]
    eligibility["source"]["requestId"] = content["candidate"]["requestId"]
    eligibility["source"]["requestItemIndex"] = content["candidate"][
        "requestItemIndex"
    ]
    eligibility["source"]["requestItemSha256"] = content[
        "requestItemSha256"
    ]
    eligibility["source"]["rfqContentSha256"] = content["contentSha256"]
    eligibility["candidateCount"] = len(
        eligibility["candidateSupplierLinks"]
    )
    eligibility["eligibilitySha256"] = (
        supplier_eligibility.calculate_eligibility_sha256(eligibility)
    )


def _expected_material_identity_sha256(content):
    item = content["rfqDraft"]["items"][0]
    return _canonical_sha256({
        "domain": MATERIAL_IDENTITY_DOMAIN,
        "version": 1,
        "companyId": content["source"]["companyId"],
        "projectId": content["source"]["projectId"],
        "sourceRevision": content["source"]["sourceRevision"],
        "requestId": content["candidate"]["requestId"],
        "requestItemIndex": content["candidate"]["requestItemIndex"],
        "target": content["candidate"]["target"],
        "materialName": item["materialName"],
        "unit": item["unit"],
    })


def _expected_source(content, eligibility):
    return {
        "companyId": content["source"]["companyId"],
        "requestId": content["candidate"]["requestId"],
        "requestItemIndex": content["candidate"]["requestItemIndex"],
        "requestItemSha256": content["requestItemSha256"],
        "rfqContentSha256": content["contentSha256"],
        "supplierEligibilitySha256": eligibility["eligibilitySha256"],
        "materialIdentitySha256": _expected_material_identity_sha256(
            content
        ),
    }


def _expected_subject(source, candidate):
    subject = {
        "companySupplierLinkId": candidate["companySupplierLinkId"],
        "supplierId": candidate["supplierId"],
        "confirmationSubjectSha256": None,
    }
    subject["confirmationSubjectSha256"] = _canonical_sha256({
        "domain": CONFIRMATION_SUBJECT_DOMAIN,
        "version": 1,
        "source": source,
        "subjectKind": SUBJECT_KIND,
        "companySupplierLinkId": subject["companySupplierLinkId"],
        "supplierId": subject["supplierId"],
    })
    return subject


def _expected_confirmation_sha256(result):
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
        "materialEligibilityProven": result[
            "materialEligibilityProven"
        ],
        "rankingApplied": result["rankingApplied"],
        "supplierIds": result["supplierIds"],
        "selectionAllowed": result["selectionAllowed"],
        "sendAllowed": result["sendAllowed"],
        "blockers": result["blockers"],
    })


class MaterialCapabilityConfirmationReadinessTests(unittest.TestCase):
    def assert_invalid(self, content, eligibility):
        with self.assertRaises(
            material_capability_confirmation.MaterialCapabilityConfirmationError
        ) as error:
            (
                material_capability_confirmation
                .build_material_capability_confirmation_readiness(
                    content, eligibility
                )
            )
        self.assertEqual(error.exception.code, INVALID_INPUT)

    def test_snapshot_builder_requires_open_transaction_metadata_only(self):
        content, eligibility = _valid_dependencies()
        content["readOnlyTransaction"] = False
        content["rolledBack"] = False
        eligibility["readOnlyTransaction"] = False
        eligibility["rolledBack"] = False

        snapshot = (
            material_capability_confirmation
            ._build_material_capability_confirmation_snapshot(
                content, eligibility,
            )
        )
        self.assertEqual(snapshot["state"], "confirmation_ready")
        with self.assertRaises(
            material_capability_confirmation.MaterialCapabilityConfirmationError
        ):
            (
                material_capability_confirmation
                .build_material_capability_confirmation_readiness(
                    content, eligibility,
                )
            )

        content["readOnlyTransaction"] = True
        content["rolledBack"] = True
        eligibility["readOnlyTransaction"] = True
        eligibility["rolledBack"] = True
        with self.assertRaises(
            material_capability_confirmation.MaterialCapabilityConfirmationError
        ):
            (
                material_capability_confirmation
                ._build_material_capability_confirmation_snapshot(
                    content, eligibility,
                )
            )

    def test_builds_deterministic_id_hash_only_confirmation_subjects(self):
        content, eligibility = _valid_dependencies()

        first = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                copy.deepcopy(content), copy.deepcopy(eligibility)
            )
        )
        second = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                copy.deepcopy(content), copy.deepcopy(eligibility)
            )
        )

        self.assertEqual(first, second)
        self.assertEqual(set(first), {
            "confirmationVersion",
            "ok",
            "dryRun",
            "writesAttempted",
            "state",
            "source",
            "subjectKind",
            "readyForMaterialCapabilityConfirmation",
            "confirmationSubjectCount",
            "confirmationSubjects",
            "materialEligibilityProven",
            "rankingApplied",
            "supplierIds",
            "selectionAllowed",
            "sendAllowed",
            "blockers",
            "confirmationSha256",
        })
        self.assertEqual(first["confirmationVersion"], 1)
        self.assertTrue(first["ok"])
        self.assertTrue(first["dryRun"])
        self.assertEqual(first["writesAttempted"], 0)
        self.assertEqual(first["state"], "confirmation_ready")
        self.assertTrue(first["readyForMaterialCapabilityConfirmation"])
        self.assertEqual(first["source"], _expected_source(
            content, eligibility
        ))
        self.assertEqual(first["subjectKind"], SUBJECT_KIND)
        expected_subjects = [
            _expected_subject(first["source"], candidate)
            for candidate in eligibility["candidateSupplierLinks"]
        ]
        self.assertEqual(first["confirmationSubjects"], expected_subjects)
        self.assertEqual(first["confirmationSubjectCount"], 2)
        for subject in first["confirmationSubjects"]:
            self.assertEqual(set(subject), {
                "companySupplierLinkId",
                "supplierId",
                "confirmationSubjectSha256",
            })
            self.assertRegex(
                subject["confirmationSubjectSha256"], r"^[0-9a-f]{64}$"
            )
        self.assertFalse(first["materialEligibilityProven"])
        self.assertFalse(first["rankingApplied"])
        self.assertEqual(first["supplierIds"], [])
        self.assertFalse(first["selectionAllowed"])
        self.assertFalse(first["sendAllowed"])
        self.assertEqual(first["blockers"], [])
        self.assertEqual(
            first["confirmationSha256"],
            _expected_confirmation_sha256(first),
        )
        for field, value in (
            ("ok", False), ("dryRun", False), ("writesAttempted", 1),
        ):
            with self.subTest(hash_metadata=field):
                changed = copy.deepcopy(first)
                changed[field] = value
                self.assertNotEqual(
                    material_capability_confirmation._confirmation_sha256(
                        changed
                    ),
                    first["confirmationSha256"],
                )

        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "Арматура", "A500C", "Ø12", '"unit"', '"quantity"',
            "sourceRevision", "impactEvidenceSha256", "evidence",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_material_identity_excludes_quantity_but_subject_binds_content(self):
        first_content, first_eligibility = _valid_dependencies()
        changed_content = copy.deepcopy(first_content)
        changed_eligibility = copy.deepcopy(first_eligibility)
        changed_content["balance"].update({
            "requestedQuantity": "11.000000",
            "openQuantity": "6.000000",
        })
        changed_content["rfqDraft"]["items"][0]["quantity"] = "6.000000"
        _refresh_bindings(changed_content, changed_eligibility)

        first = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                first_content, first_eligibility
            )
        )
        changed = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                changed_content, changed_eligibility
            )
        )

        self.assertEqual(
            first["source"]["materialIdentitySha256"],
            changed["source"]["materialIdentitySha256"],
        )
        self.assertNotEqual(
            first["source"]["rfqContentSha256"],
            changed["source"]["rfqContentSha256"],
        )
        self.assertNotEqual(
            first["confirmationSubjects"][0]["confirmationSubjectSha256"],
            changed["confirmationSubjects"][0]["confirmationSubjectSha256"],
        )

    def test_strict_allowlists_reject_unknown_fields_at_every_boundary(self):
        cases = (
            ("rfq", lambda content, _eligibility: content.update({
                "privateField": "must-not-pass",
            })),
            ("rfq_source", lambda content, _eligibility: content[
                "source"
            ].update({"privateField": "must-not-pass"})),
            ("rfq_candidate", lambda content, _eligibility: content[
                "candidate"
            ].update({"privateField": "must-not-pass"})),
            ("rfq_target", lambda content, _eligibility: content[
                "candidate"
            ]["target"].update({"privateField": "must-not-pass"})),
            ("rfq_request", lambda content, _eligibility: content[
                "request"
            ].update({"privateField": "must-not-pass"})),
            ("rfq_balance", lambda content, _eligibility: content[
                "balance"
            ].update({"privateField": "must-not-pass"})),
            ("rfq_draft", lambda content, _eligibility: content[
                "rfqDraft"
            ].update({"privateField": "must-not-pass"})),
            ("rfq_item", lambda content, _eligibility: content[
                "rfqDraft"
            ]["items"][0].update({"privateField": "must-not-pass"})),
            ("rfq_lineage", lambda content, _eligibility: content[
                "rfqDraft"
            ]["items"][0]["lineage"].update({
                "privateField": "must-not-pass",
            })),
            ("eligibility", lambda _content, eligibility: eligibility.update({
                "privateField": "must-not-pass",
            })),
            ("eligibility_source", lambda _content, eligibility: eligibility[
                "source"
            ].update({"privateField": "must-not-pass"})),
            ("eligibility_candidate", lambda _content, eligibility:
                eligibility["candidateSupplierLinks"][0].update({
                    "privateField": "must-not-pass",
                })),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                content, eligibility = _valid_dependencies()
                mutate(content, eligibility)
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

    def test_rejects_non_current_tampered_or_cross_bound_dependencies(self):
        cases = (
            ("content_hash", lambda content, _eligibility:
                content.update({"contentSha256": "a" * 64})),
            ("eligibility_hash", lambda _content, eligibility:
                eligibility.update({"eligibilitySha256": "b" * 64})),
            ("company", lambda _content, eligibility: eligibility[
                "source"
            ].update({"companyId": 404})),
            ("request", lambda _content, eligibility: eligibility[
                "source"
            ].update({"requestId": 404})),
            ("item", lambda _content, eligibility: eligibility[
                "source"
            ].update({"requestItemIndex": 9})),
            ("request_item_hash", lambda _content, eligibility: eligibility[
                "source"
            ].update({"requestItemSha256": "c" * 64})),
            ("rfq_hash", lambda _content, eligibility: eligibility[
                "source"
            ].update({"rfqContentSha256": "d" * 64})),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                content, eligibility = _valid_dependencies()
                mutate(content, eligibility)
                if name not in {"content_hash", "eligibility_hash"}:
                    eligibility["eligibilitySha256"] = (
                        supplier_eligibility.calculate_eligibility_sha256(
                            eligibility
                        )
                    )
                self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        content["request"]["requestId"] = 22
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        content["rfqDraft"]["items"][0]["lineage"]["target"][
            "itemIndex"
        ] = 1
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

        bool_alias_cases = (
            ("companyId", "source", "companyId", 1, True),
            ("requestId", "candidate", "requestId", 1, True),
            ("requestItemIndex", "candidate", "requestItemIndex", 0, False),
        )
        for eligibility_field, content_parent, content_field, value, alias in (
            bool_alias_cases
        ):
            with self.subTest(bool_alias=eligibility_field):
                content, eligibility = _valid_dependencies()
                content[content_parent][content_field] = value
                if content_parent == "candidate":
                    content["request"][content_field] = value
                    content["rfqDraft"]["items"][0]["lineage"][
                        content_field
                    ] = value
                _refresh_bindings(content, eligibility)
                eligibility["source"][eligibility_field] = alias
                eligibility["eligibilitySha256"] = (
                    supplier_eligibility.calculate_eligibility_sha256(
                        eligibility
                    )
                )
                self.assert_invalid(content, eligibility)

    def test_rejects_non_ready_metadata_and_contaminated_action_flags(self):
        cases = (
            ("rfq_version_float", lambda content, _eligibility:
                content.update({"contentVersion": 1.0})),
            ("eligibility_version_float", lambda _content, eligibility:
                eligibility.update({"eligibilityVersion": 1.0})),
            ("rfq_state", lambda content, _eligibility:
                content.update({"state": "no_action"})),
            ("rfq_ready", lambda content, _eligibility:
                content.update({"readyForRfqDraft": False})),
            ("rfq_send", lambda content, _eligibility: content[
                "rfqDraft"
            ].update({"sendAllowed": True})),
            ("rfq_suppliers", lambda content, _eligibility: content[
                "rfqDraft"
            ].update({"supplierIds": [71]})),
            ("eligibility_state", lambda _content, eligibility:
                eligibility.update({"state": "no_candidates"})),
            ("eligibility_ready", lambda _content, eligibility:
                eligibility.update({"readyForHumanSupplierReview": False})),
            ("proof", lambda _content, eligibility: eligibility.update({
                "materialEligibilityProven": True,
            })),
            ("ranking", lambda _content, eligibility: eligibility.update({
                "rankingApplied": True,
            })),
            ("selection", lambda _content, eligibility: eligibility.update({
                "selectionAllowed": True,
            })),
            ("send", lambda _content, eligibility: eligibility.update({
                "sendAllowed": True,
            })),
            ("selected_suppliers", lambda _content, eligibility:
                eligibility.update({"supplierIds": [71]})),
            ("writes", lambda _content, eligibility: eligibility.update({
                "writesAttempted": 1,
            })),
            ("rfq_not_read_only", lambda content, _eligibility:
                content.update({"readOnlyTransaction": False})),
            ("rfq_not_rolled_back", lambda content, _eligibility:
                content.update({"rolledBack": False})),
            ("eligibility_not_read_only", lambda _content, eligibility:
                eligibility.update({"readOnlyTransaction": False})),
            ("eligibility_not_rolled_back", lambda _content, eligibility:
                eligibility.update({"rolledBack": False})),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                content, eligibility = _valid_dependencies()
                mutate(content, eligibility)
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

    def test_rejects_impossible_lineage_and_context_rounded_balance(self):
        content, eligibility = _valid_dependencies()
        content["candidate"]["changeKinds"] = ["identity_changed"]
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        content["balance"].update({
            "requestedQuantity": "12345678901234.000000",
            "receivedQuantity": "1.000000",
            "allocatedQuantity": "0.000000",
            "openQuantity": "12346000000000.000000",
        })
        content["rfqDraft"]["items"][0]["quantity"] = (
            content["balance"]["openQuantity"]
        )
        _refresh_bindings(content, eligibility)
        with localcontext() as context:
            context.prec = 5
            self.assert_invalid(content, eligibility)

    def test_enforces_candidate_raw_bound_positive_ids_and_uniqueness(self):
        content, eligibility = _valid_dependencies(candidate_count=100)
        result = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                content, eligibility
            )
        )
        self.assertEqual(result["confirmationSubjectCount"], 100)

        content, eligibility = _valid_dependencies(candidate_count=101)
        self.assert_invalid(content, eligibility)

        for field in ("companySupplierLinkId", "supplierId"):
            for value in (0, -1, True, "71"):
                with self.subTest(field=field, value=value):
                    content, eligibility = _valid_dependencies()
                    eligibility["candidateSupplierLinks"][0][field] = value
                    _refresh_bindings(content, eligibility)
                    self.assert_invalid(content, eligibility)

        duplicate_cases = (
            {
                "companySupplierLinkId": 61,
                "supplierId": 71,
                "evidence": list(EVIDENCE),
            },
            {
                "companySupplierLinkId": 63,
                "supplierId": 71,
                "evidence": list(EVIDENCE),
            },
            {
                "companySupplierLinkId": 61,
                "supplierId": 73,
                "evidence": list(EVIDENCE),
            },
        )
        for duplicate in duplicate_cases:
            with self.subTest(duplicate=duplicate):
                content, eligibility = _valid_dependencies()
                eligibility["candidateSupplierLinks"].append(duplicate)
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        eligibility["candidateCount"] = 1
        eligibility["eligibilitySha256"] = (
            supplier_eligibility.calculate_eligibility_sha256(eligibility)
        )
        self.assert_invalid(content, eligibility)

    def test_valid_no_candidates_remains_unproven_and_non_actionable(self):
        content, eligibility = _valid_no_candidates_dependencies()

        result = (
            material_capability_confirmation
            .build_material_capability_confirmation_readiness(
                content, eligibility
            )
        )

        self.assertEqual(result["state"], "no_candidates")
        self.assertFalse(result["readyForMaterialCapabilityConfirmation"])
        self.assertEqual(result["confirmationSubjectCount"], 0)
        self.assertEqual(result["confirmationSubjects"], [])
        self.assertFalse(result["materialEligibilityProven"])
        self.assertFalse(result["rankingApplied"])
        self.assertEqual(result["supplierIds"], [])
        self.assertFalse(result["selectionAllowed"])
        self.assertFalse(result["sendAllowed"])
        self.assertEqual(result["blockers"], [
            "supply_supplier_no_active_company_links",
        ])
        self.assertEqual(
            result["confirmationSha256"],
            _expected_confirmation_sha256(result),
        )

    def test_rejects_empty_ready_candidates_or_missing_exact_evidence(self):
        content, eligibility = _valid_dependencies(candidate_count=0)
        self.assert_invalid(content, eligibility)

        evidence_cases = (
            [],
            EVIDENCE[:-1],
            list(reversed(EVIDENCE)),
            EVIDENCE + ["material_capability_proven"],
        )
        for evidence in evidence_cases:
            with self.subTest(evidence=evidence):
                content, eligibility = _valid_dependencies()
                eligibility["candidateSupplierLinks"][0]["evidence"] = list(
                    evidence
                )
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        eligibility["candidateSupplierLinks"][0]["evidence"] = (
            AlwaysEqualList(["material_capability_proven"])
        )
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

        list_subclass_cases = (
            ("rfq_blockers", lambda content, _eligibility:
                content.update({
                    "blockers": AlwaysEqualList(["poison"]),
                })),
            ("rfq_supplier_ids", lambda content, _eligibility:
                content["rfqDraft"].update({
                    "supplierIds": AlwaysEqualList([71]),
                })),
            ("eligibility_supplier_ids", lambda _content, eligibility:
                eligibility.update({
                    "supplierIds": AlwaysEqualList([71]),
                })),
            ("eligibility_blockers", lambda _content, eligibility:
                eligibility.update({
                    "blockers": AlwaysEqualList(["poison"]),
                })),
        )
        for name, mutate in list_subclass_cases:
            with self.subTest(list_subclass=name):
                content, eligibility = _valid_dependencies()
                mutate(content, eligibility)
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

        content, eligibility = _valid_dependencies()
        eligibility["candidateSupplierLinks"][0]["evidence"] = [
            AlwaysEqualText("poison-1"),
            AlwaysEqualText("poison-2"),
            AlwaysEqualText("poison-3"),
        ]
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

        content, eligibility = _valid_no_candidates_dependencies()
        eligibility["blockers"] = [AlwaysEqualText("poison")]
        _refresh_bindings(content, eligibility)
        self.assert_invalid(content, eligibility)

    def test_rejects_raw_oversize_before_mapping_or_change_kind_scan(self):
        oversized_mapping = OversizedMapping()
        content, eligibility = _valid_dependencies()
        self.assert_invalid(oversized_mapping, eligibility)
        self.assertFalse(oversized_mapping.iterated)

        content, eligibility = _valid_dependencies()
        oversized_change_kinds = OversizedList([
            "quantity_changed",
            "identity_changed",
            "alias_identity_changed",
            "quantity_changed",
        ])
        content["candidate"]["changeKinds"] = oversized_change_kinds
        self.assert_invalid(content, eligibility)
        self.assertFalse(oversized_change_kinds.iterated)

        content, eligibility = _valid_dependencies()
        oversized_text = OversizedText()
        content["rfqDraft"]["items"][0]["materialName"] = oversized_text
        self.assert_invalid(content, eligibility)
        self.assertFalse(oversized_text.stripped)

        enum_cases = (
            ("match_kind", lambda content, value:
                content["candidate"].update({"matchKind": value})),
            ("change_kind", lambda content, value:
                content["candidate"].update({"changeKinds": [value]})),
            ("request_status", lambda content, value:
                content["request"].update({"status": value})),
        )
        for name, mutate in enum_cases:
            with self.subTest(oversized_enum=name):
                content, eligibility = _valid_dependencies()
                oversized_enum = OversizedEnum()
                mutate(content, oversized_enum)
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)
                self.assertFalse(oversized_enum.hashed)

        for field, value in (("materialName", ""), ("unit", "")):
            with self.subTest(field=field):
                content, eligibility = _valid_dependencies()
                content["rfqDraft"]["items"][0][field] = value
                _refresh_bindings(content, eligibility)
                self.assert_invalid(content, eligibility)

    def test_import_is_pure_and_does_not_load_runtime_or_db_modules(self):
        script = """
import atexit
import sys

registered = []
original_register = atexit.register

def capture(function, *args, **kwargs):
    registered.append(function)
    return function

atexit.register = capture
import backend.features.supply_recommendation_preview.material_capability_confirmation
atexit.register = original_register

for forbidden in ("backend.main", "fastapi", "psycopg2"):
    if forbidden in sys.modules:
        raise SystemExit("forbidden import: " + forbidden)
if registered:
    raise SystemExit("import registered an exit callback")
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(Path(__file__).resolve().parents[3]),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fixed_error_does_not_chain_or_render_private_input_text(self):
        with self.assertRaises(
            material_capability_confirmation.MaterialCapabilityConfirmationError
        ) as error:
            (
                material_capability_confirmation
                .build_material_capability_confirmation_readiness(
                    LeakyMapping(), {}
                )
            )
        rendered = "".join(traceback.format_exception(
            type(error.exception), error.exception,
            error.exception.__traceback__,
        ))
        self.assertIsNone(error.exception.__cause__)
        self.assertNotIn("PRIVATE_MATERIAL_A500C", rendered)

        content, eligibility = _valid_dependencies()
        with self.assertRaises(
            material_capability_confirmation.MaterialCapabilityConfirmationError
        ) as poisoned:
            (
                material_capability_confirmation
                .build_material_capability_confirmation_readiness(
                    Poison(content), eligibility
                )
            )
        self.assertEqual(poisoned.exception.code, INVALID_INPUT)


if __name__ == "__main__":
    unittest.main()
