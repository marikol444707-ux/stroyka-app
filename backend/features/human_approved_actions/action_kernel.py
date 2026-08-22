"""Private audit-only proposal, decision and history kernel.

The module owns no route, feature flag or database configuration and accepts
only a caller-supplied connection factory.
"""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from backend.features.human_approved_actions.contract import (
    ACTION_KIND,
    HumanApprovedActionContractError,
    HumanActionEvent,
    HumanActionProposal,
    build_human_action_event,
    build_review_acknowledgement_proposal,
    normalize_human_action_decision,
    validate_human_action_event,
    validate_human_action_proposal,
)
from backend.features.warehouse_recommendation_preview import (
    runtime_access as _runtime_access,
)
from backend.features.warehouse_recommendation_preview import (
    runtime_contract as _runtime_contract,
)
from backend.features.warehouse_recommendation_preview.content_contract import (
    WarehouseAnomalyContentError,
    _finalize_warehouse_anomaly_content,
    _prepare_warehouse_anomaly_content,
    _validated_warehouse_anomaly_content_result,
)
from backend.features.warehouse_recommendation_preview.content_preview import (
    _collect_current_warehouse_anomaly_evidence,
)


RECEIPT_VERSION = 1

_INPUT_INVALID = "human_action_kernel_input_invalid"
_AUTHENTICATION_REQUIRED = "human_action_kernel_authentication_required"
_SOURCE_STALE = "human_action_kernel_source_stale"
_PROPOSAL_EXPIRED = "human_action_kernel_proposal_expired"
_PROPOSAL_CONFLICT = "human_action_kernel_proposal_conflict"
_PROPOSAL_NOT_FOUND = "human_action_kernel_proposal_not_found"
_LEDGER_INVALID = "human_action_kernel_ledger_invalid"
_WRITE_CONFLICT = "human_action_kernel_write_conflict"
_WRITE_FAILED = "human_action_kernel_write_failed"
_READ_FAILED = "human_action_kernel_read_failed"
_COMMIT_UNKNOWN = "human_action_kernel_commit_outcome_unknown"
_ROLLBACK_FAILED = "human_action_kernel_rollback_failed"
_CLEANUP_FAILED = "human_action_kernel_cleanup_failed"
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_ACTOR_FIELDS = frozenset({
    "actor_user_id",
    "actor_membership_id",
    "actor_company_id",
    "project_exists",
})


class HumanActionKernelError(ValueError):
    """One fixed non-leaking A12.3 failure."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _raise_fixed(code):
    error = HumanActionKernelError(code)
    try:
        raise error from None
    except HumanActionKernelError as raised:
        raised.__context__ = None
        raise


def _lowercase_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _positive_int(value):
    return type(value) is int and value > 0


def _database_row(value):
    if type(value) not in (dict, psycopg2.extras.RealDictRow):
        return None
    try:
        return dict(value)
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        return None


def _configure_transaction(cur):
    cur.execute(
        """SELECT pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true),
                  pg_catalog.set_config(%s,%s,true)""",
        (
            "statement_timeout", "60000",
            "lock_timeout", "5000",
            "idle_in_transaction_session_timeout", "60000",
            "search_path", "pg_catalog,public",
        ),
    )


def _authenticate_scope(
    cur, session_hash, company_id, project_id, *, lock=True,
):
    sql = """SELECT actor_user.id AS actor_user_id,
                  membership.id AS actor_membership_id,
                  company.id AS actor_company_id,
                  TRUE AS project_exists
             FROM public.user_sessions session
             JOIN public.users actor_user
               ON actor_user.id=session.user_id
             JOIN public.user_company_roles membership
               ON membership.user_id=actor_user.id
             JOIN public.companies company
               ON company.id=membership.company_id
             JOIN public.platform_accounts platform_account
               ON platform_account.id=company.platform_account_id
             JOIN public.projects project
               ON project.id=%s AND project.company_id=company.id
            WHERE session.session_hash=%s
              AND membership.company_id=%s
              AND session.revoked_at IS NULL
              AND session.expires_at>clock_timestamp()
              AND session.two_factor_passed IS TRUE
              AND actor_user.active IS TRUE
              AND actor_user.two_factor_enabled IS TRUE
              AND membership.role='директор'
              AND membership.active IS TRUE
              AND company.active IS TRUE
              AND membership.platform_account_id=company.platform_account_id
              AND platform_account.active IS TRUE
              AND platform_account.status='active'
            ORDER BY membership.id
            LIMIT %s"""
    if lock:
        sql += (
            " FOR SHARE OF session,actor_user,membership,company,"
            " platform_account,project"
        )
    cur.execute(
        sql,
        (project_id, session_hash, company_id, 2),
    )
    rows = cur.fetchall()
    actor = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if actor is None:
        _raise_fixed(_AUTHENTICATION_REQUIRED)
    if (
        set(actor) != _ACTOR_FIELDS
        or not _positive_int(actor.get("actor_user_id"))
        or not _positive_int(actor.get("actor_membership_id"))
        or actor.get("actor_company_id") != company_id
        or actor.get("project_exists") is not True
    ):
        _raise_fixed(_AUTHENTICATION_REQUIRED)
    return dict(actor)


def _authenticate_company(cur, authentication, company_id):
    cur.execute(
        """SELECT actor_user.id AS actor_user_id,
                  membership.id AS actor_membership_id,
                  company.id AS actor_company_id,
                  TRUE AS project_exists
             FROM public.user_sessions session
             JOIN public.users actor_user
               ON actor_user.id=session.user_id
             JOIN public.user_company_roles membership
               ON membership.user_id=actor_user.id
             JOIN public.companies company
               ON company.id=membership.company_id
             JOIN public.platform_accounts platform_account
               ON platform_account.id=company.platform_account_id
            WHERE session.session_hash=%s
              AND membership.company_id=%s
              AND session.revoked_at IS NULL
              AND session.expires_at>clock_timestamp()
              AND session.two_factor_passed IS TRUE
              AND actor_user.active IS TRUE
              AND actor_user.two_factor_enabled IS TRUE
              AND membership.role='директор'
              AND membership.active IS TRUE
              AND company.active IS TRUE
              AND membership.platform_account_id=company.platform_account_id
              AND platform_account.active IS TRUE
              AND platform_account.status='active'
            ORDER BY membership.id
            LIMIT %s
            FOR SHARE OF session,actor_user,membership,company,
                         platform_account""",
        (authentication["sessionHash"], company_id, 2),
    )
    rows = cur.fetchall()
    actor = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if actor is None:
        _raise_fixed(_AUTHENTICATION_REQUIRED)
    if (
        set(actor) != _ACTOR_FIELDS
        or not _positive_int(actor.get("actor_user_id"))
        or not _positive_int(actor.get("actor_membership_id"))
        or actor.get("actor_company_id") != company_id
        or actor.get("project_exists") is not True
    ):
        _raise_fixed(_AUTHENTICATION_REQUIRED)
    return dict(actor)


class _DetachedDatabaseCursor:
    __slots__ = ("_cur",)

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        return self._cur.execute(sql, params)

    def fetchall(self):
        rows = self._cur.fetchall()
        if type(rows) is not list:
            return rows
        return [
            detached if (detached := _database_row(row)) is not None else row
            for row in rows
        ]


def _rebuild_current_preview(cur, claims):
    detached_cur = _DetachedDatabaseCursor(cur)
    artifact = _runtime_access._resolve_warehouse_anomaly_runtime_artifact(
        detached_cur, claims,
    )
    prepared = _prepare_warehouse_anomaly_content(
        artifact["combinedReport"], artifact["selected"],
    )
    current = _collect_current_warehouse_anomaly_evidence(
        detached_cur, prepared,
    )
    result = _finalize_warehouse_anomaly_content(prepared, current)
    return _validated_warehouse_anomaly_content_result(result, prepared)


def _proposal_source(preview, claims):
    try:
        if (
            type(preview) is not dict
            or preview.get("warehouseAnomalyContentVersion") != 1
            or preview.get("state") != "preview_ready"
            or type(preview.get("source")) is not dict
            or preview["source"].get("companyId") != claims.company_id
            or preview["source"].get("projectId") != claims.project_id
            or type(preview.get("candidate")) is not dict
            or preview["candidate"].get("subjectKind")
            != claims.selection.subject_kind
            or preview["candidate"].get("subjectId")
            != claims.selection.subject_id
            or preview["candidate"].get("anomalyCode")
            != claims.selection.anomaly_code
            or not _lowercase_sha256(preview.get("contentSha256"))
        ):
            _raise_fixed(_SOURCE_STALE)
        return {
            "companyId": claims.company_id,
            "projectId": claims.project_id,
            "jobId": claims.job_id,
            "subjectKind": claims.selection.subject_kind,
            "subjectId": claims.selection.subject_id,
            "anomalyCode": claims.selection.anomaly_code,
            "contentVersion": preview["warehouseAnomalyContentVersion"],
            "contentSha256": preview["contentSha256"],
        }
    except HumanActionKernelError:
        raise
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_SOURCE_STALE)


def _database_now(cur):
    cur.execute("SELECT clock_timestamp() AS occurred_at")
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if row is None:
        _raise_fixed(_LEDGER_INVALID)
    value = row.get("occurred_at")
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        _raise_fixed(_LEDGER_INVALID)
    return value.astimezone(timezone.utc)


def _timestamp(value):
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        _raise_fixed(_LEDGER_INVALID)
    return value.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _insert_proposal(cur, proposal):
    cur.execute(
        """INSERT INTO public.human_action_proposals
             (contract_version,action_kind,effect_kind,company_id,project_id,
              source_job_id,subject_kind,subject_id,anomaly_code,
              source_content_version,source_content_sha256,proposer_user_id,
              proposer_membership_id,created_at,expires_at,idempotency_key,
              proposal_sha256)
           VALUES (%s,%s,'audit_only',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s)
           ON CONFLICT (company_id,idempotency_key) DO NOTHING
           RETURNING id""",
        (
            proposal.contract_version,
            proposal.action_kind,
            proposal.company_id,
            proposal.project_id,
            proposal.source_job_id,
            proposal.subject_kind,
            proposal.subject_id,
            proposal.anomaly_code,
            proposal.source_content_version,
            proposal.source_content_sha256,
            proposal.proposer_user_id,
            proposal.proposer_membership_id,
            proposal.created_at,
            proposal.expires_at,
            proposal.idempotency_key,
            proposal.proposal_sha256,
        ),
    )
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if (
        row is None
        or not _positive_int(row.get("id"))
    ):
        _raise_fixed(_WRITE_FAILED)
    return row["id"]


def _insert_event(cur, event):
    cur.execute(
        """INSERT INTO public.human_action_events
             (contract_version,event_kind,proposal_id,proposal_sha256,
              action_kind,company_id,project_id,subject_kind,subject_id,
              proposer_user_id,proposer_membership_id,actor_user_id,
              actor_membership_id,proposal_created_at,proposal_expires_at,
              occurred_at,event_sha256)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (
            event.contract_version,
            event.event_kind,
            event.proposal_id,
            event.proposal_sha256,
            event.action_kind,
            event.company_id,
            event.project_id,
            event.subject_kind,
            event.subject_id,
            event.proposer_user_id,
            event.proposer_membership_id,
            event.actor_user_id,
            event.actor_membership_id,
            event.proposal_created_at,
            event.proposal_expires_at,
            event.occurred_at,
            event.event_sha256,
        ),
    )
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if (
        row is None
        or not _positive_int(row.get("id"))
    ):
        _raise_fixed(_WRITE_FAILED)
    return row["id"]


def _proposal_receipt(proposal, proposal_id, actor, *, idempotent=False):
    return {
        "humanActionReceiptVersion": RECEIPT_VERSION,
        "state": "proposed",
        "actionKind": ACTION_KIND,
        "proposalId": proposal_id,
        "proposalSha256": proposal.proposal_sha256,
        "companyId": proposal.company_id,
        "projectId": proposal.project_id,
        "sourceJobId": proposal.source_job_id,
        "subjectKind": proposal.subject_kind,
        "subjectId": proposal.subject_id,
        "actorUserId": actor["actor_user_id"],
        "actorMembershipId": actor["actor_membership_id"],
        "expiresAt": proposal.expires_at,
        "writesAttempted": 0 if idempotent else 2,
        "committed": True,
        "idempotent": idempotent,
    }


def _lock_proposal_identity(cur, source, actor):
    identity = ":".join((
        ACTION_KIND,
        str(source["companyId"]),
        str(source["projectId"]),
        str(source["jobId"]),
        source["subjectKind"],
        str(source["subjectId"]),
        source["anomalyCode"],
        source["contentSha256"],
        str(actor["actor_user_id"]),
        str(actor["actor_membership_id"]),
    ))
    cur.execute(
        "SELECT pg_catalog.pg_advisory_xact_lock("
        "pg_catalog.hashtextextended(%s,0))",
        (identity,),
    )


def _read_active_proposal(cur, source, actor):
    cur.execute(
        """SELECT proposal.id,proposal.contract_version,
                  proposal.action_kind,proposal.effect_kind,
                  proposal.company_id,proposal.project_id,
                  proposal.source_job_id,proposal.subject_kind,
                  proposal.subject_id,proposal.anomaly_code,
                  proposal.source_content_version,
                  proposal.source_content_sha256,
                  proposal.proposer_user_id,
                  proposal.proposer_membership_id,
                  proposal.created_at,proposal.expires_at,
                  proposal.idempotency_key,proposal.proposal_sha256
             FROM public.human_action_proposals proposal
            WHERE proposal.action_kind=%s
              AND proposal.effect_kind='audit_only'
              AND proposal.company_id=%s
              AND proposal.project_id=%s
              AND proposal.source_job_id=%s
              AND proposal.subject_kind=%s
              AND proposal.subject_id=%s
              AND proposal.anomaly_code=%s
              AND proposal.source_content_version=%s
              AND proposal.source_content_sha256=%s
              AND proposal.proposer_user_id=%s
              AND proposal.proposer_membership_id=%s
              AND proposal.expires_at>clock_timestamp()
              AND NOT EXISTS (
                  SELECT 1
                    FROM public.human_action_events terminal
                   WHERE terminal.proposal_id=proposal.id
                     AND terminal.event_kind IN ('approved','rejected')
              )
            ORDER BY proposal.id
            LIMIT %s
            FOR UPDATE OF proposal""",
        (
            ACTION_KIND,
            source["companyId"],
            source["projectId"],
            source["jobId"],
            source["subjectKind"],
            source["subjectId"],
            source["anomalyCode"],
            source["contentVersion"],
            source["contentSha256"],
            actor["actor_user_id"],
            actor["actor_membership_id"],
            2,
        ),
    )
    rows = cur.fetchall()
    if type(rows) is not list or len(rows) > 1:
        _raise_fixed(_LEDGER_INVALID)
    if not rows:
        return None
    proposal_id, proposal = _decode_proposal_row(rows[0])
    events = _read_events_for_id(cur, proposal, proposal_id)
    if len(events) != 1 or events[0][1].event_kind != "proposed":
        _raise_fixed(_LEDGER_INVALID)
    return proposal_id, proposal


_PROPOSAL_ROW_FIELDS = frozenset({
    "id", "contract_version", "action_kind", "effect_kind",
    "company_id", "project_id", "source_job_id", "subject_kind",
    "subject_id", "anomaly_code", "source_content_version",
    "source_content_sha256", "proposer_user_id",
    "proposer_membership_id", "created_at", "expires_at",
    "idempotency_key", "proposal_sha256",
})


def _decode_proposal_row(row):
    row = _database_row(row)
    if row is None or set(row) != _PROPOSAL_ROW_FIELDS:
        _raise_fixed(_LEDGER_INVALID)
    if not _positive_int(row.get("id")) or row.get("effect_kind") != "audit_only":
        _raise_fixed(_LEDGER_INVALID)
    try:
        proposal = HumanActionProposal(
            contract_version=row["contract_version"],
            action_kind=row["action_kind"],
            company_id=row["company_id"],
            project_id=row["project_id"],
            source_job_id=row["source_job_id"],
            subject_kind=row["subject_kind"],
            subject_id=row["subject_id"],
            anomaly_code=row["anomaly_code"],
            source_content_version=row["source_content_version"],
            source_content_sha256=row["source_content_sha256"],
            proposer_user_id=row["proposer_user_id"],
            proposer_membership_id=row["proposer_membership_id"],
            created_at=_timestamp(row["created_at"]),
            expires_at=_timestamp(row["expires_at"]),
            idempotency_key=row["idempotency_key"],
            proposal_sha256=row["proposal_sha256"],
        )
        return row["id"], validate_human_action_proposal(proposal)
    except HumanActionKernelError:
        raise
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_LEDGER_INVALID)


def _read_proposal(cur, decision, company_id):
    cur.execute(
        """SELECT proposal.id,proposal.contract_version,
                  proposal.action_kind,proposal.effect_kind,
                  proposal.company_id,proposal.project_id,
                  proposal.source_job_id,proposal.subject_kind,
                  proposal.subject_id,proposal.anomaly_code,
                  proposal.source_content_version,
                  proposal.source_content_sha256,
                  proposal.proposer_user_id,
                  proposal.proposer_membership_id,
                  proposal.created_at,proposal.expires_at,
                  proposal.idempotency_key,proposal.proposal_sha256
             FROM public.human_action_proposals proposal
             JOIN public.projects project
               ON project.id=proposal.project_id
              AND project.company_id=proposal.company_id
            WHERE proposal.id=%s
              AND proposal.proposal_sha256=%s
              AND proposal.company_id=%s
            ORDER BY proposal.id
            LIMIT %s
            FOR UPDATE OF proposal""",
        (
            decision["proposalId"], decision["proposalSha256"],
            company_id, 2,
        ),
    )
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if row is None:
        _raise_fixed(_PROPOSAL_NOT_FOUND)
    if (
        row.get("id") != decision["proposalId"]
        or row.get("proposal_sha256") != decision["proposalSha256"]
    ):
        _raise_fixed(_LEDGER_INVALID)
    _proposal_id, proposal = _decode_proposal_row(row)
    return proposal


def _claims_for_proposal(authentication, proposal):
    try:
        return _runtime_contract._parse_warehouse_anomaly_runtime_claims(
            authentication,
            company_mode="company",
            company_id=str(proposal.company_id),
            body={
                "projectId": proposal.project_id,
                "jobId": proposal.source_job_id,
                "selected": {
                    "subjectKind": proposal.subject_kind,
                    "subjectId": proposal.subject_id,
                    "anomalyCode": proposal.anomaly_code,
                },
            },
        )
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_INPUT_INVALID)


def _read_events_for_id(cur, proposal, proposal_id):
    cur.execute(
        """SELECT id,contract_version,event_kind,proposal_id,
                  proposal_sha256,action_kind,company_id,project_id,
                  subject_kind,subject_id,proposer_user_id,
                  proposer_membership_id,actor_user_id,actor_membership_id,
                  proposal_created_at,proposal_expires_at,occurred_at,
                  event_sha256
             FROM public.human_action_events
            WHERE proposal_id=%s
            ORDER BY id
            LIMIT %s
            FOR SHARE""",
        (proposal_id, 4),
    )
    rows = cur.fetchall()
    if type(rows) is not list or not 1 <= len(rows) <= 3:
        _raise_fixed(_LEDGER_INVALID)
    decoded = []
    expected = {
        "id", "contract_version", "event_kind", "proposal_id",
        "proposal_sha256", "action_kind", "company_id", "project_id",
        "subject_kind", "subject_id", "proposer_user_id",
        "proposer_membership_id", "actor_user_id", "actor_membership_id",
        "proposal_created_at", "proposal_expires_at", "occurred_at",
        "event_sha256",
    }
    for raw_row in rows:
        row = _database_row(raw_row)
        if row is None or set(row) != expected:
            _raise_fixed(_LEDGER_INVALID)
        try:
            event = HumanActionEvent(
                contract_version=row["contract_version"],
                event_kind=row["event_kind"],
                proposal_id=row["proposal_id"],
                proposal_sha256=row["proposal_sha256"],
                action_kind=row["action_kind"],
                company_id=row["company_id"],
                project_id=row["project_id"],
                subject_kind=row["subject_kind"],
                subject_id=row["subject_id"],
                proposer_user_id=row["proposer_user_id"],
                proposer_membership_id=row["proposer_membership_id"],
                actor_user_id=row["actor_user_id"],
                actor_membership_id=row["actor_membership_id"],
                proposal_created_at=_timestamp(row["proposal_created_at"]),
                proposal_expires_at=_timestamp(row["proposal_expires_at"]),
                occurred_at=_timestamp(row["occurred_at"]),
                event_sha256=row["event_sha256"],
            )
            validate_human_action_event(event)
        except HumanActionKernelError:
            raise
        except _CONTROL_FLOW:
            raise
        except MemoryError:
            raise
        except BaseException:
            _raise_fixed(_LEDGER_INVALID)
        if event.proposal_id != proposal_id or event.proposal_sha256 != (
            proposal.proposal_sha256
        ):
            _raise_fixed(_LEDGER_INVALID)
        decoded.append((row["id"], event))
    kinds = [event.event_kind for _event_id, event in decoded]
    if kinds.count("proposed") != 1 or len(kinds) != len(set(kinds)):
        _raise_fixed(_LEDGER_INVALID)
    return decoded


def _read_audit_receipt(cur, proposal_id):
    cur.execute(
        """SELECT id
             FROM public.audit_log
            WHERE action='warehouse_anomaly_review_acknowledged'
              AND entity_type='human_action_proposal'
              AND entity_id=%s
            ORDER BY id
            LIMIT %s
            FOR SHARE""",
        (proposal_id, 2),
    )
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if (
        row is None
        or set(row) != {"id"}
        or not _positive_int(row.get("id"))
    ):
        _raise_fixed(_LEDGER_INVALID)
    return row["id"]


def _insert_audit_receipt(cur, proposal, proposal_id, actor):
    cur.execute(
        """INSERT INTO public.audit_log
             (user_id,user_name,user_role,action,entity_type,entity_id,
              description,owner_scope,company_id,project_id)
           VALUES (%s,'authenticated_user','директор',
                   'warehouse_anomaly_review_acknowledged',
                   'human_action_proposal',%s,
                   'warehouse anomaly review acknowledged',
                   'company',%s,%s)
           RETURNING id""",
        (
            actor["actor_user_id"], proposal_id,
            proposal.company_id, proposal.project_id,
        ),
    )
    rows = cur.fetchall()
    row = _database_row(rows[0]) if type(rows) is list and len(rows) == 1 else None
    if (
        row is None
        or set(row) != {"id"}
        or not _positive_int(row.get("id"))
    ):
        _raise_fixed(_WRITE_FAILED)
    return row["id"]


def _decision_receipt(
    proposal,
    proposal_id,
    actor,
    *,
    state,
    event_id,
    audit_event_id,
    writes_attempted,
    idempotent,
):
    return {
        "humanActionReceiptVersion": RECEIPT_VERSION,
        "state": state,
        "actionKind": ACTION_KIND,
        "proposalId": proposal_id,
        "proposalSha256": proposal.proposal_sha256,
        "companyId": proposal.company_id,
        "projectId": proposal.project_id,
        "sourceJobId": proposal.source_job_id,
        "subjectKind": proposal.subject_kind,
        "subjectId": proposal.subject_id,
        "actorUserId": actor["actor_user_id"],
        "actorMembershipId": actor["actor_membership_id"],
        "eventId": event_id,
        "auditEventId": audit_event_id,
        "writesAttempted": writes_attempted,
        "committed": True,
        "idempotent": idempotent,
    }


def _is_write_conflict(error):
    return getattr(error, "pgcode", None) in {
        "23505", "40001", "40P01", "55P03", "57014",
    }


def _run_write(get_db, operation):
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_errors = []
    commit_attempted = False
    committed = False
    try:
        connection = get_db()
        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure_transaction(cur)
        result = operation(cur)
        commit_attempted = True
        connection.commit()
        committed = True
    except BaseException as error:
        primary_error = error

    if connection is not None and not committed:
        try:
            connection.rollback()
        except BaseException as error:
            rollback_error = error
    if cur is not None:
        try:
            cur.close()
        except BaseException as error:
            cleanup_errors.append(error)
    if connection is not None:
        try:
            connection.close()
        except BaseException as error:
            cleanup_errors.append(error)

    for error in (primary_error, rollback_error, *cleanup_errors):
        if isinstance(error, _CONTROL_FLOW) or isinstance(error, MemoryError):
            raise error
    if commit_attempted and not committed:
        if _is_write_conflict(primary_error):
            _raise_fixed(_WRITE_CONFLICT)
        _raise_fixed(_COMMIT_UNKNOWN)
    if rollback_error is not None:
        _raise_fixed(_ROLLBACK_FAILED)
    if primary_error is not None:
        if isinstance(primary_error, HumanActionKernelError):
            _raise_fixed(primary_error.code)
        if _is_write_conflict(primary_error):
            _raise_fixed(_WRITE_CONFLICT)
        _raise_fixed(_WRITE_FAILED)
    if cleanup_errors:
        _raise_fixed(_CLEANUP_FAILED)
    return result


def _run_read(get_db, operation):
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_errors = []
    try:
        connection = get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure_transaction(cur)
        result = operation(cur)
    except BaseException as error:
        primary_error = error

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as error:
            rollback_error = error
    if cur is not None:
        try:
            cur.close()
        except BaseException as error:
            cleanup_errors.append(error)
    if connection is not None:
        try:
            connection.close()
        except BaseException as error:
            cleanup_errors.append(error)

    for error in (primary_error, rollback_error, *cleanup_errors):
        if isinstance(error, _CONTROL_FLOW) or isinstance(error, MemoryError):
            raise error
    if rollback_error is not None:
        _raise_fixed(_ROLLBACK_FAILED)
    if primary_error is not None:
        if isinstance(primary_error, HumanActionKernelError):
            _raise_fixed(primary_error.code)
        _raise_fixed(_READ_FAILED)
    if cleanup_errors:
        _raise_fixed(_CLEANUP_FAILED)
    return result


def create_review_acknowledgement_proposal(
    get_db,
    authentication,
    *,
    company_mode,
    company_id,
    body,
):
    """Create one current audit-only proposal and its proposed event."""

    if not callable(get_db):
        _raise_fixed(_INPUT_INVALID)
    try:
        claims = _runtime_contract._parse_warehouse_anomaly_runtime_claims(
            authentication,
            company_mode=company_mode,
            company_id=company_id,
            body=body,
        )
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_INPUT_INVALID)

    def operation(cur):
        actor = _authenticate_scope(
            cur,
            claims.session_hash,
            claims.company_id,
            claims.project_id,
        )
        preview = _rebuild_current_preview(cur, claims)
        source = _proposal_source(preview, claims)
        _lock_proposal_identity(cur, source, actor)
        active = _read_active_proposal(cur, source, actor)
        if active is not None:
            proposal_id, proposal = active
            return _proposal_receipt(
                proposal, proposal_id, actor, idempotent=True,
            )
        occurred_at = _database_now(cur)
        proposer = {
            "userId": actor["actor_user_id"],
            "membershipId": actor["actor_membership_id"],
            "companyId": actor["actor_company_id"],
        }
        try:
            proposal = build_review_acknowledgement_proposal(
                source, proposer, created_at=occurred_at,
            )
            proposal_id = _insert_proposal(cur, proposal)
            event = build_human_action_event(
                proposal,
                proposal_id=proposal_id,
                event_kind="proposed",
                actor=proposer,
                occurred_at=occurred_at,
            )
            _insert_event(cur, event)
        except _CONTROL_FLOW:
            raise
        except MemoryError:
            raise
        except HumanActionKernelError:
            raise
        except HumanApprovedActionContractError:
            _raise_fixed(_LEDGER_INVALID)
        return _proposal_receipt(proposal, proposal_id, actor)

    return _run_write(get_db, operation)


def _valid_authentication(value):
    return (
        type(value) is dict
        and set(value) == {"authenticationKind", "sessionHash"}
        and value.get("authenticationKind") == "cookie_session"
        and _lowercase_sha256(value.get("sessionHash"))
    )


def _selected_company_id(company_mode, company_id):
    if (
        type(company_mode) is not str
        or company_mode != "company"
        or type(company_id) is not str
        or not company_id
        or len(company_id) > 19
        or company_id[0] not in "123456789"
        or not company_id.isascii()
        or not company_id.isdecimal()
    ):
        return None
    parsed = int(company_id)
    return parsed if parsed <= 9223372036854775807 else None


def _event_actor(event):
    return {
        "actor_user_id": event.actor_user_id,
        "actor_membership_id": event.actor_membership_id,
        "actor_company_id": event.company_id,
        "project_exists": True,
    }


def decide_review_acknowledgement(
    get_db,
    authentication,
    decision,
    *,
    company_mode,
    company_id,
):
    """Reject or approve-and-apply one exact current audit-only proposal."""

    selected_company_id = _selected_company_id(company_mode, company_id)
    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or selected_company_id is None
    ):
        _raise_fixed(_INPUT_INVALID)
    try:
        decision = normalize_human_action_decision(decision)
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_INPUT_INVALID)

    def operation(cur):
        actor = _authenticate_company(
            cur, authentication, selected_company_id,
        )
        proposal = _read_proposal(cur, decision, selected_company_id)
        claims = _claims_for_proposal(authentication, proposal)
        events = _read_events_for_id(cur, proposal, decision["proposalId"])
        by_kind = {
            event.event_kind: (event_id, event)
            for event_id, event in events
        }
        approved = by_kind.get("approved")
        rejected = by_kind.get("rejected")
        applied = by_kind.get("applied")

        if decision["decision"] == "approve" and applied is not None:
            if approved is None or rejected is not None:
                _raise_fixed(_LEDGER_INVALID)
            audit_id = _read_audit_receipt(cur, decision["proposalId"])
            return _decision_receipt(
                proposal,
                decision["proposalId"],
                _event_actor(applied[1]),
                state="applied",
                event_id=applied[0],
                audit_event_id=audit_id,
                writes_attempted=0,
                idempotent=True,
            )
        if decision["decision"] == "reject" and rejected is not None:
            if approved is not None or applied is not None:
                _raise_fixed(_LEDGER_INVALID)
            return _decision_receipt(
                proposal,
                decision["proposalId"],
                _event_actor(rejected[1]),
                state="rejected",
                event_id=rejected[0],
                audit_event_id=None,
                writes_attempted=0,
                idempotent=True,
            )
        if approved is not None or rejected is not None or applied is not None:
            _raise_fixed(_PROPOSAL_CONFLICT)

        occurred_at = _database_now(cur)
        expires_at = datetime.strptime(
            proposal.expires_at, "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        if occurred_at >= expires_at:
            _raise_fixed(_PROPOSAL_EXPIRED)
        actor_contract = {
            "userId": actor["actor_user_id"],
            "membershipId": actor["actor_membership_id"],
            "companyId": actor["actor_company_id"],
        }

        if decision["decision"] == "reject":
            event = build_human_action_event(
                proposal,
                proposal_id=decision["proposalId"],
                event_kind="rejected",
                actor=actor_contract,
                occurred_at=occurred_at,
            )
            event_id = _insert_event(cur, event)
            return _decision_receipt(
                proposal,
                decision["proposalId"],
                actor,
                state="rejected",
                event_id=event_id,
                audit_event_id=None,
                writes_attempted=1,
                idempotent=False,
            )

        preview = _rebuild_current_preview(cur, claims)
        source = _proposal_source(preview, claims)
        if (
            source["contentVersion"] != proposal.source_content_version
            or source["contentSha256"] != proposal.source_content_sha256
        ):
            _raise_fixed(_SOURCE_STALE)
        approved_event = build_human_action_event(
            proposal,
            proposal_id=decision["proposalId"],
            event_kind="approved",
            actor=actor_contract,
            occurred_at=occurred_at,
        )
        _insert_event(cur, approved_event)
        applied_event = build_human_action_event(
            proposal,
            proposal_id=decision["proposalId"],
            event_kind="applied",
            actor=actor_contract,
            occurred_at=occurred_at,
        )
        applied_event_id = _insert_event(cur, applied_event)
        audit_event_id = _insert_audit_receipt(
            cur, proposal, decision["proposalId"], actor,
        )
        return _decision_receipt(
            proposal,
            decision["proposalId"],
            actor,
            state="applied",
            event_id=applied_event_id,
            audit_event_id=audit_event_id,
            writes_attempted=3,
            idempotent=False,
        )

    return _run_write(get_db, operation)


_HISTORY_ROW_FIELDS = frozenset({
    "event_id", "contract_version", "event_kind", "proposal_id",
    "proposal_sha256", "action_kind", "company_id", "project_id",
    "source_job_id", "subject_kind", "subject_id", "proposer_user_id",
    "proposer_membership_id", "actor_user_id", "actor_membership_id",
    "proposal_created_at", "proposal_expires_at", "occurred_at",
    "event_sha256",
})


def _history_item(row, company_id, project_id):
    row = _database_row(row)
    if row is None or set(row) != _HISTORY_ROW_FIELDS:
        _raise_fixed(_LEDGER_INVALID)
    if (
        not _positive_int(row.get("event_id"))
        or not _positive_int(row.get("source_job_id"))
        or row.get("company_id") != company_id
        or row.get("project_id") != project_id
    ):
        _raise_fixed(_LEDGER_INVALID)
    try:
        event = HumanActionEvent(
            contract_version=row["contract_version"],
            event_kind=row["event_kind"],
            proposal_id=row["proposal_id"],
            proposal_sha256=row["proposal_sha256"],
            action_kind=row["action_kind"],
            company_id=row["company_id"],
            project_id=row["project_id"],
            subject_kind=row["subject_kind"],
            subject_id=row["subject_id"],
            proposer_user_id=row["proposer_user_id"],
            proposer_membership_id=row["proposer_membership_id"],
            actor_user_id=row["actor_user_id"],
            actor_membership_id=row["actor_membership_id"],
            proposal_created_at=_timestamp(row["proposal_created_at"]),
            proposal_expires_at=_timestamp(row["proposal_expires_at"]),
            occurred_at=_timestamp(row["occurred_at"]),
            event_sha256=row["event_sha256"],
        )
        validate_human_action_event(event)
    except HumanActionKernelError:
        raise
    except _CONTROL_FLOW:
        raise
    except MemoryError:
        raise
    except BaseException:
        _raise_fixed(_LEDGER_INVALID)
    return {
        "eventId": row["event_id"],
        "eventKind": event.event_kind,
        "proposalId": event.proposal_id,
        "proposalSha256": event.proposal_sha256,
        "actionKind": event.action_kind,
        "sourceJobId": row["source_job_id"],
        "subjectKind": event.subject_kind,
        "subjectId": event.subject_id,
        "actorUserId": event.actor_user_id,
        "actorMembershipId": event.actor_membership_id,
        "occurredAt": event.occurred_at,
        "eventSha256": event.event_sha256,
    }


def list_review_acknowledgement_history(
    get_db,
    authentication,
    *,
    company_mode,
    company_id,
    project_id,
    before_event_id,
    limit,
):
    """Read one bounded newest-first page of immutable action events."""

    selected_company_id = _selected_company_id(company_mode, company_id)
    if (
        not callable(get_db)
        or not _valid_authentication(authentication)
        or selected_company_id is None
        or not _positive_int(project_id)
        or (
            before_event_id is not None
            and not _positive_int(before_event_id)
        )
        or type(limit) is not int
        or not 1 <= limit <= 100
    ):
        _raise_fixed(_INPUT_INVALID)

    def operation(cur):
        _authenticate_scope(
            cur,
            authentication["sessionHash"],
            selected_company_id,
            project_id,
            lock=False,
        )
        base_sql = """SELECT event.id AS event_id,
                  event.contract_version,event.event_kind,event.proposal_id,
                  event.proposal_sha256,event.action_kind,event.company_id,
                  event.project_id,proposal.source_job_id,event.subject_kind,
                  event.subject_id,event.proposer_user_id,
                  event.proposer_membership_id,event.actor_user_id,
                  event.actor_membership_id,event.proposal_created_at,
                  event.proposal_expires_at,event.occurred_at,
                  event.event_sha256
             FROM public.human_action_events event
             JOIN public.human_action_proposals proposal
               ON proposal.id=event.proposal_id
              AND proposal.proposal_sha256=event.proposal_sha256
              AND proposal.company_id=event.company_id
              AND proposal.project_id=event.project_id
            WHERE event.action_kind='warehouse_anomaly_review_acknowledged'
              AND event.company_id=%s
              AND event.project_id=%s"""
        if before_event_id is None:
            sql = base_sql + " ORDER BY event.id DESC LIMIT %s"
            params = (selected_company_id, project_id, limit + 1)
        else:
            sql = base_sql + (
                " AND event.id<%s ORDER BY event.id DESC LIMIT %s"
            )
            params = (
                selected_company_id, project_id, before_event_id, limit + 1,
            )
        cur.execute(sql, params)
        rows = cur.fetchall()
        if type(rows) is not list or len(rows) > limit + 1:
            _raise_fixed(_LEDGER_INVALID)
        page_rows = rows[:limit]
        items = [
            _history_item(row, selected_company_id, project_id)
            for row in page_rows
        ]
        if any(
            items[index]["eventId"] <= items[index + 1]["eventId"]
            for index in range(len(items) - 1)
        ):
            _raise_fixed(_LEDGER_INVALID)
        next_before_id = (
            items[-1]["eventId"] if len(rows) > limit and items else None
        )
        return {
            "humanActionHistoryVersion": 1,
            "companyId": selected_company_id,
            "projectId": project_id,
            "items": items,
            "nextBeforeId": next_before_id,
        }

    return _run_read(get_db, operation)


__all__ = []
