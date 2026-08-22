"""Pure A12.1 contract for one audit-only human-approved action.

This module has no database, HTTP, runtime registration, model, or business
writer dependency. Its hashes identify validated proposal/event data; they do
not authorize a write or prove current database state.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType


CONTRACT_VERSION = 1
CONTENT_VERSION = 1
PROPOSAL_TTL_SECONDS = 15 * 60
ACTION_KIND = "warehouse_anomaly_review_acknowledged"
INVALID = "human_approved_action_contract_invalid"
EVENT_KINDS = (
    "applied",
    "apply_failed",
    "approved",
    "proposed",
    "rejected",
)

_SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "jobId",
    "subjectKind",
    "subjectId",
    "anomalyCode",
    "contentVersion",
    "contentSha256",
})
_ACTOR_FIELDS = frozenset({"userId", "membershipId", "companyId"})
_DECISION_FIELDS = frozenset({
    "proposalId",
    "proposalSha256",
    "decision",
})
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$"
)
_ANOMALY_SUBJECTS = MappingProxyType({
    "warehouse_invoice_delivery_mismatch": "warehouseInvoice",
    "warehouse_invoice_items_invalid": "warehouseInvoice",
    "warehouse_invoice_project_mismatch": "warehouseInvoice",
    "warehouse_invoice_request_mismatch": "warehouseInvoice",
    "warehouse_invoice_supplier_invoice_mismatch": "warehouseInvoice",
    "warehouse_lot_movement_missing": "warehouseMovement",
    "warehouse_lot_movement_parent_mismatch": "lotMovement",
    "warehouse_lot_movement_source_mismatch": "lotMovement",
    "warehouse_movement_invoice_mismatch": "warehouseMovement",
    "warehouse_movement_line_invalid": "warehouseMovement",
    "warehouse_movement_lot_missing": "warehouseMovement",
    "warehouse_movement_package_mismatch": "warehouseMovement",
    "warehouse_receipt_invoice_mismatch": "warehouseHistory",
    "warehouse_receipt_line_invalid": "warehouseHistory",
    "warehouse_receipt_lot_invoice_mismatch": "receiptLot",
    "warehouse_receipt_lot_line_invalid": "receiptLot",
    "warehouse_receipt_lot_project_mismatch": "receiptLot",
    "warehouse_receipt_package_mismatch": "warehouseHistory",
})


class HumanApprovedActionContractError(ValueError):
    """One fixed non-leaking contract failure."""

    def __init__(self):
        self.code = INVALID
        super().__init__(self.code)


@dataclass(frozen=True)
class ActionPolicy:
    __slots__ = (
        "action_kind",
        "effect_kind",
        "subject_kinds",
        "separate_approver_required",
    )

    action_kind: str
    effect_kind: str
    subject_kinds: tuple
    separate_approver_required: bool


ACTION_POLICIES = MappingProxyType({
    ACTION_KIND: ActionPolicy(
        action_kind=ACTION_KIND,
        effect_kind="audit_only",
        subject_kinds=tuple(sorted(set(_ANOMALY_SUBJECTS.values()))),
        separate_approver_required=False,
    ),
})


@dataclass(frozen=True)
class HumanActionProposal:
    __slots__ = (
        "contract_version",
        "action_kind",
        "company_id",
        "project_id",
        "source_job_id",
        "subject_kind",
        "subject_id",
        "anomaly_code",
        "source_content_version",
        "source_content_sha256",
        "proposer_user_id",
        "proposer_membership_id",
        "created_at",
        "expires_at",
        "idempotency_key",
        "proposal_sha256",
    )

    contract_version: int
    action_kind: str
    company_id: int
    project_id: int
    source_job_id: int
    subject_kind: str
    subject_id: int
    anomaly_code: str
    source_content_version: int
    source_content_sha256: str
    proposer_user_id: int
    proposer_membership_id: int
    created_at: str
    expires_at: str
    idempotency_key: str
    proposal_sha256: str


@dataclass(frozen=True)
class HumanActionEvent:
    __slots__ = (
        "contract_version",
        "event_kind",
        "proposal_id",
        "proposal_sha256",
        "action_kind",
        "company_id",
        "project_id",
        "subject_kind",
        "subject_id",
        "proposer_user_id",
        "proposer_membership_id",
        "actor_user_id",
        "actor_membership_id",
        "proposal_created_at",
        "proposal_expires_at",
        "occurred_at",
        "event_sha256",
    )

    contract_version: int
    event_kind: str
    proposal_id: int
    proposal_sha256: str
    action_kind: str
    company_id: int
    project_id: int
    subject_kind: str
    subject_id: int
    proposer_user_id: int
    proposer_membership_id: int
    actor_user_id: int
    actor_membership_id: int
    proposal_created_at: str
    proposal_expires_at: str
    occurred_at: str
    event_sha256: str


def _fail():
    raise HumanApprovedActionContractError() from None


def _positive_int(value):
    if type(value) is not int or value <= 0:
        _fail()
    return value


def _sha256(value):
    if type(value) is not str or _HASH_RE.fullmatch(value) is None:
        _fail()
    return value


def _exact_dict(value, fields):
    if type(value) is not dict or set(value) != fields:
        _fail()
    return value


def _canonical_sha256(value):
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_datetime(value):
    if type(value) is not datetime:
        _fail()
    failed = False
    offset = None
    rendered = None
    try:
        offset = value.utcoffset()
        rendered = value.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    except (KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError):
        raise
    except Exception:
        failed = True
    if failed or offset != timedelta(0) or type(rendered) is not str:
        _fail()
    return rendered


def _parsed_timestamp(value):
    if type(value) is not str or _TIMESTAMP_RE.fullmatch(value) is None:
        _fail()
    failed = False
    parsed = None
    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        failed = True
    if failed or type(parsed) is not datetime:
        _fail()
    return parsed


def _validated_source(value):
    source = _exact_dict(value, _SOURCE_FIELDS)
    company_id = _positive_int(source.get("companyId"))
    project_id = _positive_int(source.get("projectId"))
    source_job_id = _positive_int(source.get("jobId"))
    subject_id = _positive_int(source.get("subjectId"))
    subject_kind = source.get("subjectKind")
    anomaly_code = source.get("anomalyCode")
    if (
        type(subject_kind) is not str
        or type(anomaly_code) is not str
        or _ANOMALY_SUBJECTS.get(anomaly_code) != subject_kind
        or type(source.get("contentVersion")) is not int
        or source["contentVersion"] != CONTENT_VERSION
    ):
        _fail()
    return {
        "company_id": company_id,
        "project_id": project_id,
        "source_job_id": source_job_id,
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "anomaly_code": anomaly_code,
        "source_content_version": CONTENT_VERSION,
        "source_content_sha256": _sha256(source.get("contentSha256")),
    }


def _validated_actor(value, company_id):
    actor = _exact_dict(value, _ACTOR_FIELDS)
    if _positive_int(actor.get("companyId")) != company_id:
        _fail()
    return {
        "user_id": _positive_int(actor.get("userId")),
        "membership_id": _positive_int(actor.get("membershipId")),
    }


def _proposal_identity(values):
    return {
        "contractVersion": values["contract_version"],
        "actionKind": values["action_kind"],
        "companyId": values["company_id"],
        "projectId": values["project_id"],
        "sourceJobId": values["source_job_id"],
        "subjectKind": values["subject_kind"],
        "subjectId": values["subject_id"],
        "anomalyCode": values["anomaly_code"],
        "sourceContentVersion": values["source_content_version"],
        "sourceContentSha256": values["source_content_sha256"],
        "proposerUserId": values["proposer_user_id"],
        "proposerMembershipId": values["proposer_membership_id"],
        "createdAt": values["created_at"],
        "expiresAt": values["expires_at"],
    }


def _expected_proposal(values):
    identity = _proposal_identity(values)
    idempotency_key = "human-action:v1:" + _canonical_sha256(identity)
    proposal_sha256 = _canonical_sha256({
        **identity,
        "idempotencyKey": idempotency_key,
    })
    return idempotency_key, proposal_sha256


def build_review_acknowledgement_proposal(source, proposer, *, created_at):
    """Build one immutable proposal from an already server-validated preview."""

    source = _validated_source(source)
    actor = _validated_actor(proposer, source["company_id"])
    created_at_value = _canonical_datetime(created_at)
    expiry_failed = False
    expires_at = None
    try:
        expires_at = created_at + timedelta(seconds=PROPOSAL_TTL_SECONDS)
    except (KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError):
        raise
    except Exception:
        expiry_failed = True
    if expiry_failed or type(expires_at) is not datetime:
        _fail()
    expires_at_value = _canonical_datetime(expires_at)
    values = {
        "contract_version": CONTRACT_VERSION,
        "action_kind": ACTION_KIND,
        **source,
        "proposer_user_id": actor["user_id"],
        "proposer_membership_id": actor["membership_id"],
        "created_at": created_at_value,
        "expires_at": expires_at_value,
    }
    idempotency_key, proposal_sha256 = _expected_proposal(values)
    return HumanActionProposal(
        **values,
        idempotency_key=idempotency_key,
        proposal_sha256=proposal_sha256,
    )


def validate_human_action_proposal(value):
    if type(value) is not HumanActionProposal:
        _fail()
    scalar_ints = (
        value.company_id,
        value.project_id,
        value.source_job_id,
        value.subject_id,
        value.source_content_version,
        value.proposer_user_id,
        value.proposer_membership_id,
    )
    if (
        type(value.contract_version) is not int
        or value.contract_version != CONTRACT_VERSION
        or type(value.action_kind) is not str
        or value.action_kind != ACTION_KIND
        or any(type(item) is not int or item <= 0 for item in scalar_ints)
        or value.source_content_version != CONTENT_VERSION
        or type(value.subject_kind) is not str
        or type(value.anomaly_code) is not str
        or _ANOMALY_SUBJECTS.get(value.anomaly_code) != value.subject_kind
        or type(value.idempotency_key) is not str
    ):
        _fail()
    _sha256(value.source_content_sha256)
    _sha256(value.proposal_sha256)
    created_at = _parsed_timestamp(value.created_at)
    expires_at = _parsed_timestamp(value.expires_at)
    if expires_at - created_at != timedelta(seconds=PROPOSAL_TTL_SECONDS):
        _fail()
    values = {
        field: getattr(value, field)
        for field in (
            "contract_version",
            "action_kind",
            "company_id",
            "project_id",
            "source_job_id",
            "subject_kind",
            "subject_id",
            "anomaly_code",
            "source_content_version",
            "source_content_sha256",
            "proposer_user_id",
            "proposer_membership_id",
            "created_at",
            "expires_at",
        )
    }
    expected_idempotency_key, expected_proposal_sha256 = _expected_proposal(
        values
    )
    if (
        value.idempotency_key != expected_idempotency_key
        or value.proposal_sha256 != expected_proposal_sha256
    ):
        _fail()
    return value


def normalize_human_action_decision(value):
    decision = _exact_dict(value, _DECISION_FIELDS)
    decision_value = decision.get("decision")
    if (
        type(decision_value) is not str
        or decision_value not in {"approve", "reject"}
    ):
        _fail()
    return {
        "proposalId": _positive_int(decision.get("proposalId")),
        "proposalSha256": _sha256(decision.get("proposalSha256")),
        "decision": decision_value,
    }


def _event_identity(values):
    return {
        "contractVersion": values["contract_version"],
        "eventKind": values["event_kind"],
        "proposalId": values["proposal_id"],
        "proposalSha256": values["proposal_sha256"],
        "actionKind": values["action_kind"],
        "companyId": values["company_id"],
        "projectId": values["project_id"],
        "subjectKind": values["subject_kind"],
        "subjectId": values["subject_id"],
        "proposerUserId": values["proposer_user_id"],
        "proposerMembershipId": values["proposer_membership_id"],
        "actorUserId": values["actor_user_id"],
        "actorMembershipId": values["actor_membership_id"],
        "proposalCreatedAt": values["proposal_created_at"],
        "proposalExpiresAt": values["proposal_expires_at"],
        "occurredAt": values["occurred_at"],
    }


def build_human_action_event(
    proposal,
    *,
    proposal_id,
    event_kind,
    actor,
    occurred_at,
):
    proposal = validate_human_action_proposal(proposal)
    proposal_id = _positive_int(proposal_id)
    actor = _validated_actor(actor, proposal.company_id)
    if type(event_kind) is not str or event_kind not in EVENT_KINDS:
        _fail()
    occurred_at_value = _canonical_datetime(occurred_at)
    occurred = _parsed_timestamp(occurred_at_value)
    created = _parsed_timestamp(proposal.created_at)
    expires = _parsed_timestamp(proposal.expires_at)
    if event_kind == "proposed":
        if (
            occurred != created
            or actor["user_id"] != proposal.proposer_user_id
            or actor["membership_id"] != proposal.proposer_membership_id
        ):
            _fail()
    elif occurred < created or occurred >= expires:
        _fail()
    values = {
        "contract_version": CONTRACT_VERSION,
        "event_kind": event_kind,
        "proposal_id": proposal_id,
        "proposal_sha256": proposal.proposal_sha256,
        "action_kind": proposal.action_kind,
        "company_id": proposal.company_id,
        "project_id": proposal.project_id,
        "subject_kind": proposal.subject_kind,
        "subject_id": proposal.subject_id,
        "proposer_user_id": proposal.proposer_user_id,
        "proposer_membership_id": proposal.proposer_membership_id,
        "actor_user_id": actor["user_id"],
        "actor_membership_id": actor["membership_id"],
        "proposal_created_at": proposal.created_at,
        "proposal_expires_at": proposal.expires_at,
        "occurred_at": occurred_at_value,
    }
    return HumanActionEvent(
        **values,
        event_sha256=_canonical_sha256(_event_identity(values)),
    )


def validate_human_action_event(value):
    if type(value) is not HumanActionEvent:
        _fail()
    integer_fields = (
        value.proposal_id,
        value.company_id,
        value.project_id,
        value.subject_id,
        value.proposer_user_id,
        value.proposer_membership_id,
        value.actor_user_id,
        value.actor_membership_id,
    )
    if (
        type(value.contract_version) is not int
        or value.contract_version != CONTRACT_VERSION
        or type(value.event_kind) is not str
        or value.event_kind not in EVENT_KINDS
        or type(value.action_kind) is not str
        or value.action_kind != ACTION_KIND
        or any(type(item) is not int or item <= 0 for item in integer_fields)
        or type(value.subject_kind) is not str
        or value.subject_kind not in ACTION_POLICIES[ACTION_KIND].subject_kinds
    ):
        _fail()
    _sha256(value.proposal_sha256)
    _sha256(value.event_sha256)
    created = _parsed_timestamp(value.proposal_created_at)
    expires = _parsed_timestamp(value.proposal_expires_at)
    occurred = _parsed_timestamp(value.occurred_at)
    if expires - created != timedelta(seconds=PROPOSAL_TTL_SECONDS):
        _fail()
    if value.event_kind == "proposed":
        if (
            occurred != created
            or value.actor_user_id != value.proposer_user_id
            or value.actor_membership_id != value.proposer_membership_id
        ):
            _fail()
    elif occurred < created or occurred >= expires:
        _fail()
    values = {
        field: getattr(value, field)
        for field in (
            "contract_version",
            "event_kind",
            "proposal_id",
            "proposal_sha256",
            "action_kind",
            "company_id",
            "project_id",
            "subject_kind",
            "subject_id",
            "proposer_user_id",
            "proposer_membership_id",
            "actor_user_id",
            "actor_membership_id",
            "proposal_created_at",
            "proposal_expires_at",
            "occurred_at",
        )
    }
    if value.event_sha256 != _canonical_sha256(_event_identity(values)):
        _fail()
    return value


__all__ = []
