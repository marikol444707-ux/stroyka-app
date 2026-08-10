import copy
import inspect
import json
import subprocess
import sys
import unittest
from unittest import mock

from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
)
from backend.features.supply_recommendation_preview import (
    material_capability_confirmation,
    material_capability_proof,
    material_capability_schema_probe,
    rfq_content,
)
from backend.features.supply_recommendation_preview.test_material_capability_schema import (
    absent_catalog,
    exact_catalog,
)
from backend.features.supply_recommendation_preview.test_rfq_content import (
    baseline_report,
    current_supply_report,
    run_case as run_rfq_case,
    valid_report,
    valid_result_sets,
)
from backend.features.supply_recommendation_preview.test_supplier_eligibility import (
    direct_user_row,
    linked_supplier_row,
    run_case as run_eligibility_case,
    supplier_schema_rows,
    supporting_index_row,
)


TOP_LEVEL_FIELDS = {
    "proofVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "subjectKind", "confirmationSha256",
    "confirmationSubjectCount", "proofSubjectCount", "provenSubjectCount",
    "proofSubjects", "materialEligibilityProven", "rankingApplied",
    "supplierIds", "selectionAllowed", "sendAllowed", "blockers",
    "proofSha256", "readOnlyTransaction", "rolledBack",
}
PROOF_SUBJECT_FIELDS = {
    "companySupplierLinkId", "supplierId", "materialIdentitySha256",
    "confirmationSubjectSha256", "proofState", "evidence",
}
EVIDENCE_FIELDS = {
    "assertionId", "eventKind", "actorMembershipId", "actorUserId",
    "actorRole", "sourceKind", "revokesAssertionId",
}


def _supplier_sets(candidate_count):
    if candidate_count == 0:
        empty = linked_supplier_row(
            link_id=None,
            link_company_id=None,
            supplier_id=None,
            link_account_id=None,
            link_status=None,
            supplier_parent_id=None,
            supplier_status=None,
            supplier_user_link_id=None,
            supplier_user_id=None,
            supplier_user_role=None,
            supplier_user_active=None,
        )
        return (
            supplier_schema_rows(),
            (supporting_index_row(),),
            (empty,),
        )
    links = tuple(
        linked_supplier_row(
            link_id=61 + index,
            supplier_id=71 + index,
            supplier_parent_id=71 + index,
            supplier_user_link_id=81 + index,
            supplier_user_id=81 + index,
        )
        for index in range(candidate_count)
    )
    users = tuple(
        direct_user_row(
            supplier_id=71 + index,
            supplier_user_id=81 + index,
        )
        for index in range(candidate_count)
    )
    return (
        supplier_schema_rows(),
        (supporting_index_row(),),
        links,
        (supporting_index_row(),),
        users,
    )


def _expected_confirmation(candidate_count):
    report = valid_report()
    content, _, _ = run_rfq_case(report=copy.deepcopy(report))
    eligibility, _, _ = run_eligibility_case(
        report=copy.deepcopy(report),
        supplier_sets=_supplier_sets(candidate_count),
    )
    return (
        material_capability_confirmation
        .build_material_capability_confirmation_readiness(
            content, eligibility,
        )
    )


def _assertion(subject, assertion_id, **overrides):
    row = {
        "id": assertion_id,
        "confirmation_version": 1,
        "event_kind": "confirmed",
        "company_id": 4,
        "company_supplier_link_id": subject["companySupplierLinkId"],
        "supplier_id": subject["supplierId"],
        "material_identity_sha256": None,
        "confirmation_subject_sha256": subject[
            "confirmationSubjectSha256"
        ],
        "actor_membership_id": 501 + assertion_id,
        "actor_user_id": 601 + assertion_id,
        "actor_role": "директор",
        "source_kind": "director_manual",
        "revokes_assertion_id": None,
    }
    row.update(overrides)
    return row


def _confirmation_rows(readiness):
    material_hash = readiness["source"]["materialIdentitySha256"]
    return tuple(
        _assertion(subject, 101 + index, material_identity_sha256=material_hash)
        for index, subject in enumerate(readiness["confirmationSubjects"])
    )


class RollbackFails(FakeConnection):
    def rollback(self):
        self.rollbacks += 1
        raise RuntimeError("PRIVATE_ROLLBACK_DETAIL")


class CloseFailsCursor(FakeCursor):
    def close(self):
        self.closed = True
        raise RuntimeError("PRIVATE_CLEANUP_DETAIL")


def _run_case(*, candidate_count=2, assertion_rows=(), catalog=None,
              connection_class=FakeConnection, cursor_class=FakeCursor):
    report = valid_report()
    result_sets = (
        valid_result_sets()
        + _supplier_sets(candidate_count)
        + ((tuple(assertion_rows),) if candidate_count else ())
    )
    cursor = cursor_class(result_sets)
    connection = connection_class(cursor)
    current = current_supply_report(report)
    current.update(copy.deepcopy(baseline_report(report)))
    with mock.patch.object(
        rfq_content,
        "collect_supply_warehouse_impact_audit",
        return_value=current,
    ), mock.patch.object(
        material_capability_schema_probe,
        "collect_material_capability_schema_catalog",
        return_value=exact_catalog() if catalog is None else catalog,
    ):
        result = (
            material_capability_proof
            .run_supplier_material_capability_proof_preview(
                lambda: connection,
                report,
                {"requestId": 21, "requestItemIndex": 0},
            )
        )
    return result, connection, cursor


class SupplierMaterialCapabilityProofTests(unittest.TestCase):
    def test_all_exact_confirmations_are_complete_in_one_rolled_back_snapshot(self):
        readiness = _expected_confirmation(2)
        rows = tuple(reversed(_confirmation_rows(readiness)))

        result, connection, cursor = _run_case(assertion_rows=rows)

        self.assertEqual(set(result), TOP_LEVEL_FIELDS)
        self.assertEqual(result["proofVersion"], 1)
        self.assertEqual(result["state"], "proof_complete")
        self.assertEqual(result["confirmationSha256"], readiness[
            "confirmationSha256"
        ])
        self.assertEqual(result["confirmationSubjectCount"], 2)
        self.assertEqual(result["proofSubjectCount"], 2)
        self.assertEqual(result["provenSubjectCount"], 2)
        self.assertTrue(result["materialEligibilityProven"])
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["readOnlyTransaction"])
        self.assertTrue(result["rolledBack"])
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)
        timeout_sql, timeout_params = cursor.calls[0]
        self.assertIn("pg_catalog.set_config", timeout_sql)
        self.assertEqual(timeout_params, (
            "statement_timeout", "60000",
            "lock_timeout", "5000",
            "idle_in_transaction_session_timeout", "60000",
            "search_path", "pg_catalog,public",
            1,
        ))
        self.assertEqual(result["proofSha256"],
                         material_capability_proof.calculate_proof_sha256(
                             result
                         ))
        self.assertEqual(
            [subject["supplierId"] for subject in result["proofSubjects"]],
            [71, 72],
        )
        for subject in result["proofSubjects"]:
            self.assertEqual(set(subject), PROOF_SUBJECT_FIELDS)
            self.assertEqual(subject["proofState"], "confirmed")
            self.assertEqual(len(subject["evidence"]), 1)
            self.assertEqual(set(subject["evidence"][0]), EVIDENCE_FIELDS)
            self.assertIsNone(subject["evidence"][0]["revokesAssertionId"])

        assertion_sql, assertion_params = cursor.calls[-1]
        lowered = assertion_sql.lower()
        self.assertIn("from public.supplier_material_capability_assertions", lowered)
        self.assertIn("company_id=%s", lowered)
        self.assertIn(
            "confirmation_subject_sha256=any(%s::varchar[])", lowered,
        )
        self.assertIn("order by confirmation_subject_sha256,id", lowered)
        self.assertIn("limit %s", lowered)
        self.assertEqual(assertion_params[0], 4)
        self.assertEqual(assertion_params[-1], 5)
        self.assertEqual(set(assertion_params[1]), {
            subject["confirmationSubjectSha256"]
            for subject in readiness["confirmationSubjects"]
        })
        for sql, _params in cursor.calls:
            self.assertTrue(sql.upper().startswith("SELECT "))
        for fixed in ("rankingApplied", "selectionAllowed", "sendAllowed"):
            self.assertFalse(result[fixed])
        self.assertEqual(result["supplierIds"], [])
        self.assertEqual(result["writesAttempted"], 0)

    def test_missing_and_partial_evidence_never_promote_overall_proof(self):
        readiness = _expected_confirmation(2)
        confirmed = _confirmation_rows(readiness)[0]
        cases = (
            ((), "confirmation_required", 0,
             ["supply_supplier_material_confirmation_required"]),
            ((confirmed,), "proof_partial", 1,
             ["supply_supplier_material_proof_partial"]),
        )
        for rows, state, proven, blockers in cases:
            with self.subTest(state=state):
                result, _, _ = _run_case(assertion_rows=rows)
                self.assertEqual(result["state"], state)
                self.assertEqual(result["provenSubjectCount"], proven)
                self.assertFalse(result["materialEligibilityProven"])
                self.assertEqual(result["blockers"], blockers)
                self.assertEqual(
                    [subject["proofState"] for subject in result[
                        "proofSubjects"
                    ]],
                    ["confirmed", "missing"] if rows else [
                        "missing", "missing"
                    ],
                )

    def test_exact_revocation_is_terminal_and_keeps_both_id_only_events(self):
        readiness = _expected_confirmation(1)
        confirmed = _confirmation_rows(readiness)[0]
        revoked = _assertion(
            readiness["confirmationSubjects"][0],
            confirmed["id"] + 1,
            event_kind="revoked",
            material_identity_sha256=readiness["source"][
                "materialIdentitySha256"
            ],
            revokes_assertion_id=confirmed["id"],
        )

        result, _, _ = _run_case(
            candidate_count=1,
            assertion_rows=(revoked, confirmed),
        )

        self.assertEqual(result["state"], "confirmation_required")
        self.assertEqual(result["provenSubjectCount"], 0)
        self.assertFalse(result["materialEligibilityProven"])
        self.assertEqual(result["proofSubjects"][0]["proofState"], "revoked")
        evidence = result["proofSubjects"][0]["evidence"]
        self.assertEqual([row["eventKind"] for row in evidence], [
            "confirmed", "revoked",
        ])
        self.assertEqual(evidence[1]["revokesAssertionId"], confirmed["id"])

    def test_orphan_wrong_target_and_third_event_fail_closed(self):
        readiness = _expected_confirmation(1)
        subject = readiness["confirmationSubjects"][0]
        confirmed = _confirmation_rows(readiness)[0]
        revoked = _assertion(
            subject,
            confirmed["id"] + 1,
            event_kind="revoked",
            material_identity_sha256=readiness["source"][
                "materialIdentitySha256"
            ],
            revokes_assertion_id=confirmed["id"],
        )
        cases = (
            (revoked,),
            (confirmed, dict(
                revoked,
                revokes_assertion_id=confirmed["id"] + 999,
            )),
        )
        for rows in cases:
            with self.subTest(rows=rows):
                result, _, _ = _run_case(
                    candidate_count=1,
                    assertion_rows=rows,
                )
                self.assertEqual(result["state"], "needs_review")
                self.assertEqual(result["blockers"], [
                    "supply_supplier_material_evidence_invalid",
                ])
                self.assertEqual(result["proofSubjects"], [])
                self.assertFalse(result["materialEligibilityProven"])

        two_subjects = _expected_confirmation(2)
        first_subject = two_subjects["confirmationSubjects"][0]
        first_confirmed = _confirmation_rows(two_subjects)[0]
        first_revoked = _assertion(
            first_subject,
            first_confirmed["id"] + 1000,
            event_kind="revoked",
            material_identity_sha256=two_subjects["source"][
                "materialIdentitySha256"
            ],
            revokes_assertion_id=first_confirmed["id"],
        )
        result, _, _ = _run_case(
            candidate_count=2,
            assertion_rows=(
                first_confirmed,
                first_revoked,
                dict(first_revoked, id=first_revoked["id"] + 1),
            ),
        )
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["blockers"], [
            "supply_supplier_material_evidence_invalid",
        ])
        self.assertEqual(result["proofSubjects"], [])

    def test_malformed_mixed_scope_or_duplicate_evidence_fails_closed(self):
        readiness = _expected_confirmation(1)
        confirmed = _confirmation_rows(readiness)[0]
        cases = (
            (confirmed, dict(company_id=999)),
            (confirmed, dict(actor_role="заместитель директора")),
            (confirmed, dict(source_kind="model")),
            (confirmed, dict(material_identity_sha256="0" * 64)),
            (confirmed, dict(company_supplier_link_id=999)),
            (confirmed, dict(supplier_id=999)),
        )
        row_sets = [
            (dict(row, **changes),) for row, changes in cases
        ]
        row_sets.append((confirmed, dict(confirmed, id=confirmed["id"] + 1)))
        for rows in row_sets:
            with self.subTest(rows=rows):
                result, _, _ = _run_case(
                    candidate_count=1, assertion_rows=rows,
                )
                self.assertEqual(result["state"], "needs_review")
                self.assertEqual(result["blockers"], [
                    "supply_supplier_material_evidence_invalid",
                ])
                self.assertEqual(result["proofSubjectCount"], 0)
                self.assertEqual(result["provenSubjectCount"], 0)
                self.assertEqual(result["proofSubjects"], [])
                self.assertFalse(result["materialEligibilityProven"])

    def test_assertion_sentinel_overflow_is_incomplete_not_partial(self):
        readiness = _expected_confirmation(2)
        subject = readiness["confirmationSubjects"][0]
        rows = tuple(
            _assertion(
                subject,
                100 + index,
                material_identity_sha256=readiness["source"][
                    "materialIdentitySha256"
                ],
            )
            for index in range(5)
        )

        result, _, cursor = _run_case(assertion_rows=rows)

        self.assertEqual(cursor.calls[-1][1][-1], 5)
        self.assertEqual(result["state"], "incomplete")
        self.assertEqual(result["blockers"], [
            "supply_supplier_material_evidence_scan_incomplete",
        ])
        self.assertEqual(result["proofSubjects"], [])
        self.assertFalse(result["materialEligibilityProven"])

    def test_hundred_subject_bound_accepts_two_exact_events_each(self):
        readiness = _expected_confirmation(100)
        rows = []
        for confirmed in _confirmation_rows(readiness):
            subject = next(
                item for item in readiness["confirmationSubjects"]
                if item["confirmationSubjectSha256"]
                == confirmed["confirmation_subject_sha256"]
            )
            rows.extend((
                confirmed,
                _assertion(
                    subject,
                    confirmed["id"] + 1000,
                    event_kind="revoked",
                    material_identity_sha256=readiness["source"][
                        "materialIdentitySha256"
                    ],
                    revokes_assertion_id=confirmed["id"],
                ),
            ))

        result, _, cursor = _run_case(
            candidate_count=100,
            assertion_rows=tuple(reversed(rows)),
        )

        self.assertEqual(cursor.calls[-1][1][-1], 201)
        self.assertEqual(result["confirmationSubjectCount"], 100)
        self.assertEqual(result["proofSubjectCount"], 100)
        self.assertEqual(result["provenSubjectCount"], 0)
        self.assertEqual(result["state"], "confirmation_required")
        self.assertTrue(all(
            subject["proofState"] == "revoked"
            and len(subject["evidence"]) == 2
            for subject in result["proofSubjects"]
        ))

    def test_schema_drift_blocks_proof_and_no_candidates_stay_non_actionable(self):
        blocked, _, blocked_cursor = _run_case(catalog=absent_catalog())
        self.assertEqual(blocked["state"], "incomplete")
        self.assertEqual(blocked["blockers"], [
            "supply_supplier_material_schema_not_ready",
        ])
        self.assertEqual(blocked["proofSubjects"], [])
        self.assertFalse(blocked["materialEligibilityProven"])
        self.assertNotIn(
            "supplier_material_capability_assertions",
            " ".join(sql for sql, _params in blocked_cursor.calls).lower(),
        )

        empty, _, empty_cursor = _run_case(
            candidate_count=0,
            catalog=absent_catalog(),
        )
        self.assertEqual(empty["state"], "no_candidates")
        self.assertEqual(empty["confirmationSubjectCount"], 0)
        self.assertEqual(empty["proofSubjectCount"], 0)
        self.assertEqual(empty["provenSubjectCount"], 0)
        self.assertEqual(empty["proofSubjects"], [])
        self.assertEqual(empty["blockers"], [
            "supply_supplier_no_active_company_links",
        ])
        self.assertFalse(empty["materialEligibilityProven"])
        self.assertNotIn(
            "supplier_material_capability_assertions",
            " ".join(sql for sql, _params in empty_cursor.calls).lower(),
        )

    def test_input_read_rollback_and_cleanup_failures_use_fixed_codes(self):
        calls = []
        with self.assertRaises(
            material_capability_proof.SupplierMaterialCapabilityProofError
        ) as invalid:
            material_capability_proof.run_supplier_material_capability_proof_preview(
                lambda: calls.append("db"),
                valid_report(),
                {"requestId": 21, "requestItemIndex": True},
            )
        self.assertEqual(
            invalid.exception.code,
            "supply_supplier_material_proof_input_invalid",
        )
        self.assertEqual(calls, [])

        with self.assertRaises(
            material_capability_proof.SupplierMaterialCapabilityProofError
        ) as read_error:
            material_capability_proof.run_supplier_material_capability_proof_preview(
                lambda: (_ for _ in ()).throw(
                    RuntimeError("PRIVATE_READ_DETAIL")
                ),
                valid_report(),
                {"requestId": 21, "requestItemIndex": 0},
            )
        self.assertEqual(
            read_error.exception.code,
            "supply_supplier_material_proof_read_failed",
        )
        self.assertNotIn("PRIVATE", str(read_error.exception))

        def fail_to_open():
            raise RuntimeError("PRIVATE_DATABASE_DETAIL")

        with self.assertRaises(
            material_capability_proof.SupplierMaterialCapabilityProofError
        ) as read_error:
            material_capability_proof.run_supplier_material_capability_proof_preview(
                fail_to_open,
                valid_report(),
                {"requestId": 21, "requestItemIndex": 0},
            )
        self.assertEqual(
            read_error.exception.code,
            "supply_supplier_material_proof_read_failed",
        )
        self.assertNotIn("PRIVATE", str(read_error.exception))

        readiness = _expected_confirmation(1)
        rows = _confirmation_rows(readiness)
        for connection_class, cursor_class, code in (
            (RollbackFails, FakeCursor,
             "supply_supplier_material_proof_rollback_failed"),
            (FakeConnection, CloseFailsCursor,
             "supply_supplier_material_proof_cleanup_failed"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(
                    material_capability_proof
                    .SupplierMaterialCapabilityProofError
                ) as error:
                    _run_case(
                        candidate_count=1,
                        assertion_rows=rows,
                        connection_class=connection_class,
                        cursor_class=cursor_class,
                    )
                self.assertEqual(error.exception.code, code)
                self.assertNotIn("PRIVATE", str(error.exception))

    def test_post_rollback_confirmation_parity_is_mandatory(self):
        readiness = _expected_confirmation(1)
        completed = copy.deepcopy(readiness)
        completed["confirmationSha256"] = "0" * 64

        with mock.patch.object(
            material_capability_proof,
            "build_material_capability_confirmation_readiness",
            return_value=completed,
        ), self.assertRaises(
            material_capability_proof.SupplierMaterialCapabilityProofError
        ) as error:
            _run_case(
                candidate_count=1,
                assertion_rows=_confirmation_rows(readiness),
            )

        self.assertEqual(
            error.exception.code,
            "supply_supplier_material_proof_read_failed",
        )

    def test_public_contract_and_import_are_inert_and_model_free(self):
        signature = inspect.signature(
            material_capability_proof
            .run_supplier_material_capability_proof_preview
        )
        self.assertEqual(list(signature.parameters), [
            "get_db", "combined_report", "selected",
        ])
        self.assertEqual(material_capability_proof.__all__, [
            "PROOF_VERSION",
            "SupplierMaterialCapabilityProofError",
            "calculate_proof_sha256",
            "run_supplier_material_capability_proof_preview",
        ])
        source = inspect.getsource(material_capability_proof).lower()
        for forbidden in (
            "backend.main", "yandex", "openai", "gemini", "llm",
            "supplier_catalog", "supplier_offers", "messenger_outbox",
            "supply_request_recipients", "requests.", "httpx", "smtp",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn(".commit(", source)

        script = """
import atexit
import json
import sys
before = len(getattr(atexit, '_exithandlers', ()))
import backend.features.supply_recommendation_preview.material_capability_proof
print(json.dumps({
    'mainLoaded': 'backend.main' in sys.modules,
    'dbLoaded': 'backend.db' in sys.modules,
    'fastapiLoaded': 'fastapi' in sys.modules,
    'migrationLoaded': (
        'backend.features.supply_recommendation_preview.'
        'material_capability_schema' in sys.modules
    ),
    'forbiddenFeatureModules': sorted(
        name for name in sys.modules
        if name.startswith((
            'backend.features.estimate_row_transfer.routes',
            'backend.features.estimate_row_transfer.assignment_apply',
            'backend.features.estimate_row_transfer.supply_apply',
            'backend.features.project_budget_adjustments.preview_routes',
            'backend.features.project_budget_adjustments.runtime_routes',
        ))
    ),
    'handlersAdded': len(getattr(atexit, '_exithandlers', ())) - before,
}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            text=True,
            capture_output=True,
            check=True,
        )
        report = json.loads(completed.stdout)
        self.assertFalse(report["mainLoaded"])
        self.assertFalse(report["dbLoaded"])
        self.assertFalse(report["fastapiLoaded"])
        self.assertFalse(report["migrationLoaded"])
        self.assertEqual(report["forbiddenFeatureModules"], [])
        self.assertEqual(report["handlersAdded"], 0)


if __name__ == "__main__":
    unittest.main()
