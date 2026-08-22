import dataclasses
import unittest
from datetime import datetime, timedelta, timezone, tzinfo
from types import MappingProxyType

from backend.features.human_approved_actions.contract import (
    ACTION_KIND,
    ACTION_POLICIES,
    CONTRACT_VERSION,
    PROPOSAL_TTL_SECONDS,
    HumanApprovedActionContractError,
    HumanActionEvent,
    HumanActionProposal,
    build_human_action_event,
    build_review_acknowledgement_proposal,
    normalize_human_action_decision,
    validate_human_action_event,
    validate_human_action_proposal,
)


CREATED_AT = datetime(2026, 8, 22, 9, 10, 11, 123456, tzinfo=timezone.utc)
SOURCE = {
    "companyId": 4,
    "projectId": 17,
    "jobId": 29,
    "subjectKind": "warehouseInvoice",
    "subjectId": 61,
    "anomalyCode": "warehouse_invoice_project_mismatch",
    "contentVersion": 1,
    "contentSha256": "a" * 64,
}
PROPOSER = {"userId": 41, "membershipId": 71, "companyId": 4}


def proposal(**changes):
    values = dict(SOURCE)
    values.update(changes.pop("source", {}))
    actor = dict(PROPOSER)
    actor.update(changes.pop("proposer", {}))
    created_at = changes.pop("created_at", CREATED_AT)
    if changes:
        raise AssertionError(changes)
    return build_review_acknowledgement_proposal(
        values,
        actor,
        created_at=created_at,
    )


class HumanApprovedActionContractTests(unittest.TestCase):
    def assert_fixed_error(self, operation):
        with self.assertRaises(HumanApprovedActionContractError) as raised:
            operation()
        self.assertEqual(
            raised.exception.args,
            ("human_approved_action_contract_invalid",),
        )
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertNotIn("PRIVATE", repr(raised.exception))

    def test_registry_is_immutable_and_contains_only_the_audit_only_pilot(self):
        self.assertIsInstance(ACTION_POLICIES, MappingProxyType)
        self.assertEqual(set(ACTION_POLICIES), {ACTION_KIND})
        policy = ACTION_POLICIES[ACTION_KIND]
        self.assertEqual(policy.action_kind, ACTION_KIND)
        self.assertEqual(policy.effect_kind, "audit_only")
        self.assertFalse(policy.separate_approver_required)
        self.assertEqual(
            policy.subject_kinds,
            (
                "lotMovement",
                "receiptLot",
                "warehouseHistory",
                "warehouseInvoice",
                "warehouseMovement",
            ),
        )
        with self.assertRaises(TypeError):
            ACTION_POLICIES["arbitrary_sql"] = policy
        with self.assertRaises(dataclasses.FrozenInstanceError):
            policy.effect_kind = "business_write"

    def test_builds_one_deterministic_immutable_bounded_proposal(self):
        first = proposal()
        second = proposal()

        self.assertIsInstance(first, HumanActionProposal)
        self.assertEqual(first, second)
        self.assertEqual(first.contract_version, CONTRACT_VERSION)
        self.assertEqual(first.action_kind, ACTION_KIND)
        self.assertEqual(first.company_id, 4)
        self.assertEqual(first.project_id, 17)
        self.assertEqual(first.source_job_id, 29)
        self.assertEqual(first.subject_kind, "warehouseInvoice")
        self.assertEqual(first.subject_id, 61)
        self.assertEqual(
            first.anomaly_code,
            "warehouse_invoice_project_mismatch",
        )
        self.assertEqual(first.source_content_version, 1)
        self.assertEqual(first.source_content_sha256, "a" * 64)
        self.assertEqual(first.proposer_user_id, 41)
        self.assertEqual(first.proposer_membership_id, 71)
        self.assertEqual(first.created_at, "2026-08-22T09:10:11.123456Z")
        self.assertEqual(first.expires_at, "2026-08-22T09:25:11.123456Z")
        self.assertRegex(first.idempotency_key, r"^human-action:v1:[0-9a-f]{64}$")
        self.assertRegex(first.proposal_sha256, r"^[0-9a-f]{64}$")
        self.assertIs(validate_human_action_proposal(first), first)
        self.assertFalse(hasattr(first, "__dict__"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.company_id = 999
        with self.assertRaises((AttributeError, TypeError)):
            object.__setattr__(first, "payload", {"PRIVATE": True})

    def test_proposal_hash_binds_every_authoritative_field(self):
        baseline = proposal()
        variants = (
            proposal(source={"companyId": 5}, proposer={"companyId": 5}),
            proposal(source={"projectId": 18}),
            proposal(source={"jobId": 30}),
            proposal(source={"subjectId": 62}),
            proposal(source={
                "anomalyCode": "warehouse_invoice_items_invalid",
            }),
            proposal(source={"contentSha256": "b" * 64}),
            proposal(proposer={"userId": 42}),
            proposal(created_at=CREATED_AT + timedelta(microseconds=1)),
        )
        self.assertEqual(
            len({baseline.proposal_sha256, *(item.proposal_sha256 for item in variants)}),
            len(variants) + 1,
        )

    def test_source_actor_and_clock_inputs_are_exact_and_fail_closed(self):
        class ExplodingTimezone(tzinfo):
            def utcoffset(self, _value):
                raise RuntimeError("PRIVATE_TIMEZONE")

        invalid_sources = (
            None,
            [],
            {},
            {**SOURCE, "extra": "PRIVATE"},
            {key: value for key, value in SOURCE.items() if key != "subjectId"},
            {**SOURCE, "companyId": True},
            {**SOURCE, "projectId": 0},
            {**SOURCE, "jobId": 0},
            {**SOURCE, "subjectId": -1},
            {**SOURCE, "subjectKind": "warehouseInvoice "},
            {**SOURCE, "contentVersion": 2},
            {**SOURCE, "contentSha256": "A" * 64},
            {**SOURCE, "contentSha256": "PRIVATE"},
            {**SOURCE, "anomalyCode": "warehouse_invoice_owner_mismatch"},
            {**SOURCE, "anomalyCode": "warehouse_movement_line_invalid"},
        )
        for value in invalid_sources:
            with self.subTest(source=value):
                self.assert_fixed_error(lambda value=value: (
                    build_review_acknowledgement_proposal(
                        value, PROPOSER, created_at=CREATED_AT,
                    )
                ))

        invalid_actors = (
            None,
            [],
            {},
            {**PROPOSER, "extra": "PRIVATE"},
            {**PROPOSER, "userId": True},
            {**PROPOSER, "membershipId": 0},
            {**PROPOSER, "companyId": 999},
        )
        for value in invalid_actors:
            with self.subTest(actor=value):
                self.assert_fixed_error(lambda value=value: (
                    build_review_acknowledgement_proposal(
                        SOURCE, value, created_at=CREATED_AT,
                    )
                ))

        invalid_clocks = (
            None,
            "2026-08-22T09:10:11Z",
            datetime(2026, 8, 22, 9, 10, 11),
            datetime(2026, 8, 22, 9, 10, 11, tzinfo=timezone(timedelta(hours=3))),
            datetime.max.replace(tzinfo=timezone.utc),
            datetime(2026, 8, 22, tzinfo=ExplodingTimezone()),
        )
        for value in invalid_clocks:
            with self.subTest(created_at=value):
                self.assert_fixed_error(lambda value=value: (
                    build_review_acknowledgement_proposal(
                        SOURCE, PROPOSER, created_at=value,
                    )
                ))

    def test_forged_or_subclassed_proposals_are_revalidated(self):
        valid = proposal()
        fields = {
            field.name: getattr(valid, field.name)
            for field in dataclasses.fields(valid)
        }
        for name, value in (
            ("contract_version", True),
            ("action_kind", "arbitrary_sql"),
            ("action_kind", type("Text", (str,), {})(ACTION_KIND)),
            ("company_id", 999),
            ("anomaly_code", []),
            ("created_at", "9999-99-99T99:99:99.999999Z"),
            ("expires_at", valid.created_at),
            ("idempotency_key", "human-action:v1:" + "0" * 64),
            ("proposal_sha256", "0" * 64),
        ):
            with self.subTest(field=name):
                forged = HumanActionProposal(**{**fields, name: value})
                self.assert_fixed_error(
                    lambda forged=forged: validate_human_action_proposal(forged)
                )

        class ProposalSubclass(HumanActionProposal):
            pass

        subclassed = ProposalSubclass(**fields)
        self.assert_fixed_error(
            lambda: validate_human_action_proposal(subclassed)
        )

    def test_decision_payload_is_exact_detached_and_contains_no_write_values(self):
        payload = {
            "proposalId": 501,
            "proposalSha256": "b" * 64,
            "decision": "approve",
        }
        normalized = normalize_human_action_decision(payload)
        payload["decision"] = "reject"
        self.assertEqual(normalized, {
            "proposalId": 501,
            "proposalSha256": "b" * 64,
            "decision": "approve",
        })
        for value in (
            None,
            {},
            {**normalized, "quantity": "1.000000"},
            {**normalized, "proposalId": True},
            {**normalized, "proposalSha256": "B" * 64},
            {**normalized, "decision": "apply"},
            {**normalized, "decision": []},
            {
                **normalized,
                "decision": type("Text", (str,), {})("approve"),
            },
        ):
            with self.subTest(value=value):
                self.assert_fixed_error(
                    lambda value=value: normalize_human_action_decision(value)
                )

    def test_events_are_immutable_hash_bound_and_expire_fail_closed(self):
        current = proposal()
        proposed = build_human_action_event(
            current,
            proposal_id=501,
            event_kind="proposed",
            actor=PROPOSER,
            occurred_at=CREATED_AT,
        )
        approved = build_human_action_event(
            current,
            proposal_id=501,
            event_kind="approved",
            actor=PROPOSER,
            occurred_at=CREATED_AT + timedelta(minutes=1),
        )
        self.assertIsInstance(proposed, HumanActionEvent)
        self.assertFalse(hasattr(proposed, "__dict__"))
        self.assertIs(validate_human_action_event(proposed), proposed)
        self.assertIs(validate_human_action_event(approved), approved)
        self.assertNotEqual(proposed.event_sha256, approved.event_sha256)
        self.assertEqual(approved.proposal_sha256, current.proposal_sha256)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            approved.event_kind = "applied"

        for event_kind in ("proposed", "approved", "rejected", "applied", "apply_failed"):
            with self.subTest(event_kind=event_kind):
                event = build_human_action_event(
                    current,
                    proposal_id=501,
                    event_kind=event_kind,
                    actor=PROPOSER,
                    occurred_at=(
                        CREATED_AT if event_kind == "proposed"
                        else CREATED_AT + timedelta(minutes=1)
                    ),
                )
                self.assertEqual(event.event_kind, event_kind)

        invalid = (
            dict(event_kind="unknown", occurred_at=CREATED_AT),
            dict(event_kind="proposed", occurred_at=CREATED_AT + timedelta(seconds=1)),
            dict(event_kind="approved", occurred_at=CREATED_AT - timedelta(seconds=1)),
            dict(event_kind="approved", occurred_at=CREATED_AT + timedelta(seconds=PROPOSAL_TTL_SECONDS)),
            dict(event_kind="approved", occurred_at=CREATED_AT + timedelta(seconds=PROPOSAL_TTL_SECONDS + 1)),
        )
        for case in invalid:
            with self.subTest(case=case):
                self.assert_fixed_error(lambda case=case: build_human_action_event(
                    current,
                    proposal_id=501,
                    actor=PROPOSER,
                    **case,
                ))

    def test_event_revalidation_rejects_forged_hash_and_raw_payload(self):
        event = build_human_action_event(
            proposal(),
            proposal_id=501,
            event_kind="approved",
            actor=PROPOSER,
            occurred_at=CREATED_AT + timedelta(seconds=1),
        )
        fields = {
            field.name: getattr(event, field.name)
            for field in dataclasses.fields(event)
        }
        forged = HumanActionEvent(**{**fields, "event_sha256": "0" * 64})
        self.assert_fixed_error(lambda: validate_human_action_event(forged))
        subclassed_subject = HumanActionEvent(**{
            **fields,
            "subject_kind": type("Text", (str,), {})(fields["subject_kind"]),
        })
        self.assert_fixed_error(
            lambda: validate_human_action_event(subclassed_subject)
        )
        self.assertNotIn("payload", fields)
        self.assertNotIn("sql", fields)
        self.assertNotIn("notes", fields)


if __name__ == "__main__":
    unittest.main()
