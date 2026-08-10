"""Local append-only writer for exact supplier-material capability evidence."""

import psycopg2
import psycopg2.extras

from . import material_capability_proof
from . import material_capability_schema_probe
from .material_capability_schema_contract import (
    ADVISORY_LOCK_ID,
    CONTRACT_VERSION,
)
from .rfq_content import prepare_supply_rfq_content


WRITE_VERSION = 1

_INPUT_INVALID = "supply_supplier_material_writer_input_invalid"
_AUTHENTICATION_REQUIRED = (
    "supply_supplier_material_writer_authentication_required"
)
_TENANT_MISMATCH = "supply_supplier_material_writer_tenant_mismatch"
_SCHEMA_NOT_READY = "supply_supplier_material_writer_schema_not_ready"
_SUBJECT_STALE = "supply_supplier_material_writer_subject_stale"
_SUBJECT_TERMINAL = "supply_supplier_material_writer_subject_terminal"
_EVIDENCE_INVALID = "supply_supplier_material_writer_evidence_invalid"
_TARGET_INVALID = "supply_supplier_material_writer_target_invalid"
_WRITE_CONFLICT = "supply_supplier_material_writer_write_conflict"
_WRITE_FAILED = "supply_supplier_material_writer_write_failed"
_COMMIT_UNKNOWN = "supply_supplier_material_writer_commit_outcome_unknown"
_ROLLBACK_FAILED = "supply_supplier_material_writer_rollback_failed"
_CLEANUP_FAILED = "supply_supplier_material_writer_cleanup_failed"
_PUBLIC_ERROR_CODES = {
    _INPUT_INVALID,
    _AUTHENTICATION_REQUIRED,
    _TENANT_MISMATCH,
    _SCHEMA_NOT_READY,
    _SUBJECT_STALE,
    _SUBJECT_TERMINAL,
    _EVIDENCE_INVALID,
    _TARGET_INVALID,
    _WRITE_CONFLICT,
    _WRITE_FAILED,
}

_AUTHENTICATION_FIELDS = {"authenticationKind", "sessionHash"}
_CONFIRM_COMMAND_FIELDS = {
    "companyId", "companySupplierLinkId", "supplierId",
    "confirmationSubjectSha256",
}
_REVOKE_COMMAND_FIELDS = {"companyId", "confirmationAssertionId"}
_ACTOR_FIELDS = {
    "actor_user_id", "actor_membership_id", "actor_company_id",
}
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)

_collect_proof = (
    material_capability_proof
    .collect_prepared_supplier_material_capability_proof
)


class MaterialCapabilityWriterError(ValueError):
    """Fixed public failure code without private database detail."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _positive_int(value):
    return type(value) is int and value > 0


def _sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validated_authentication(value):
    if (
        type(value) is not dict
        or set(value) != _AUTHENTICATION_FIELDS
        or type(value.get("authenticationKind")) is not str
        or value.get("authenticationKind") != "cookie_session"
        or not _sha256(value.get("sessionHash"))
    ):
        raise MaterialCapabilityWriterError(_INPUT_INVALID)
    return value["sessionHash"]


def _validated_confirmation_command(value):
    if (
        type(value) is not dict
        or set(value) != _CONFIRM_COMMAND_FIELDS
        or not _positive_int(value.get("companyId"))
        or not _positive_int(value.get("companySupplierLinkId"))
        or not _positive_int(value.get("supplierId"))
        or not _sha256(value.get("confirmationSubjectSha256"))
    ):
        raise MaterialCapabilityWriterError(_INPUT_INVALID)
    return dict(value)


def _validated_revocation_command(value):
    if (
        type(value) is not dict
        or set(value) != _REVOKE_COMMAND_FIELDS
        or not _positive_int(value.get("companyId"))
        or not _positive_int(value.get("confirmationAssertionId"))
    ):
        raise MaterialCapabilityWriterError(_INPUT_INVALID)
    return dict(value)


def _configure_transaction(cur):
    # SET does not establish a SERIALIZABLE snapshot.  Keep every SELECT and
    # data-changing statement after the explicit relation lock below.
    cur.execute("SET LOCAL statement_timeout='60s'")
    cur.execute("SET LOCAL lock_timeout='5s'")
    cur.execute("SET LOCAL idle_in_transaction_session_timeout='60s'")
    cur.execute("SET LOCAL search_path=pg_catalog,public")


def _authenticate(cur, session_hash, company_id):
    cur.execute(
        """SELECT actor_user.id AS actor_user_id,
                  membership.id AS actor_membership_id,
                  company.id AS actor_company_id
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
            FOR SHARE OF session,actor_user,membership,company,platform_account""",
        (session_hash, company_id, 2),
    )
    try:
        rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    except Exception:
        rows = []
    if len(rows) != 1:
        raise MaterialCapabilityWriterError(_AUTHENTICATION_REQUIRED)
    actor = rows[0]
    if (
        set(actor) != _ACTOR_FIELDS
        or not _positive_int(actor.get("actor_user_id"))
        or not _positive_int(actor.get("actor_membership_id"))
        or not _positive_int(actor.get("actor_company_id"))
        or actor.get("actor_company_id") != company_id
    ):
        raise MaterialCapabilityWriterError(_AUTHENTICATION_REQUIRED)
    return actor


def _lock_evidence_table(cur):
    # The b1 schema migration locks public.companies before its advisory lock.
    # Use the same gate first so a writer and that migration cannot invert the
    # target-table/advisory order and deadlock.
    cur.execute(
        "LOCK TABLE public.companies IN SHARE UPDATE EXCLUSIVE MODE"
    )
    try:
        cur.execute(
            "LOCK TABLE public.supplier_material_capability_assertions "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    except BaseException as exc:
        if getattr(exc, "pgcode", None) == "42P01":
            raise MaterialCapabilityWriterError(
                _SCHEMA_NOT_READY
            ) from None
        raise
    cur.execute(
        "SELECT pg_catalog.pg_advisory_xact_lock(%s)",
        (ADVISORY_LOCK_ID,),
    )


def _schema_ready(cur):
    try:
        readiness = (
            material_capability_schema_probe
            .collect_material_capability_schema_readiness(cur)
        )
    except Exception:
        readiness = None
    if (
        type(readiness) is not dict
        or set(readiness) != {"contractVersion", "complete", "blockers"}
        or type(readiness.get("contractVersion")) is not int
        or readiness.get("contractVersion") != CONTRACT_VERSION
        or readiness.get("complete") is not True
        or type(readiness.get("blockers")) is not list
        or readiness.get("blockers") != []
    ):
        raise MaterialCapabilityWriterError(_SCHEMA_NOT_READY)


def _collect_active_proof(cur, prepared, company_id):
    result = _collect_proof(cur, prepared)
    try:
        projection = (
            material_capability_proof
            .validate_supplier_material_capability_write_projection(
                result, company_id,
            )
        )
    except material_capability_proof.SupplierMaterialCapabilityProofError as exc:
        if exc.code == "supply_supplier_material_schema_not_ready":
            code = _SCHEMA_NOT_READY
        elif exc.code == "supply_supplier_no_active_company_links":
            code = _SUBJECT_STALE
        else:
            code = _EVIDENCE_INVALID
        raise MaterialCapabilityWriterError(code) from None
    return projection["source"], projection["proofSubjects"]


def _decode_assertion(raw, error_code):
    try:
        return (
            material_capability_proof
            .validate_supplier_material_capability_assertion(
                dict(raw or {})
            )
        )
    except Exception:
        raise MaterialCapabilityWriterError(error_code) from None


def _result(row, state, writes_attempted, committed):
    return {
        "writeVersion": WRITE_VERSION,
        "ok": True,
        "eventKind": row["event_kind"],
        "state": state,
        "companyId": row["company_id"],
        "companySupplierLinkId": row["company_supplier_link_id"],
        "supplierId": row["supplier_id"],
        "materialIdentitySha256": row["material_identity_sha256"],
        "confirmationSubjectSha256": row[
            "confirmation_subject_sha256"
        ],
        "assertionId": row["id"],
        "revokesAssertionId": row["revokes_assertion_id"],
        "actorUserId": row["actor_user_id"],
        "actorMembershipId": row["actor_membership_id"],
        "writesAttempted": writes_attempted,
        "committed": committed,
    }


def _idempotent_result(event_kind, state, source, subject, evidence):
    row = {
        "id": evidence["assertionId"],
        "event_kind": event_kind,
        "company_id": source["companyId"],
        "company_supplier_link_id": subject["companySupplierLinkId"],
        "supplier_id": subject["supplierId"],
        "material_identity_sha256": subject["materialIdentitySha256"],
        "confirmation_subject_sha256": subject[
            "confirmationSubjectSha256"
        ],
        "actor_user_id": evidence["actorUserId"],
        "actor_membership_id": evidence["actorMembershipId"],
        "revokes_assertion_id": evidence["revokesAssertionId"],
    }
    return _result(row, state, 0, False)


def _insert_assertion(cur, values):
    cur.execute(
        """INSERT INTO public.supplier_material_capability_assertions
                  (confirmation_version,event_kind,company_id,company_supplier_link_id,supplier_id,material_identity_sha256,confirmation_subject_sha256,actor_membership_id,actor_user_id,actor_role,source_kind,revokes_assertion_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id,confirmation_version,event_kind,company_id,
                  company_supplier_link_id,supplier_id,
                  material_identity_sha256,confirmation_subject_sha256,
                  actor_membership_id,actor_user_id,actor_role,source_kind,
                  revokes_assertion_id""",
        values,
    )
    raw = cur.fetchone()
    return _decode_assertion(raw or {}, _WRITE_FAILED)


def _same_actor(before, after):
    return (
        before["actor_user_id"] == after["actor_user_id"]
        and before["actor_membership_id"] == after["actor_membership_id"]
        and before["actor_company_id"] == after["actor_company_id"]
    )


def _is_write_conflict(exc):
    return (
        isinstance(exc, psycopg2.IntegrityError)
        or getattr(exc, "pgcode", None) in {
            "23505", "40001", "40P01", "55P03", "57014",
        }
    )


def _run_transaction(get_db, operation):
    connection = None
    cur = None
    outcome = None
    primary_error = None
    rollback_error = None
    cleanup_error = None
    rollback_required = False
    commit_uncertain = False
    try:
        connection = get_db()
        connection.set_session(
            readonly=False,
            autocommit=False,
            isolation_level="SERIALIZABLE",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure_transaction(cur)
        outcome, should_commit = operation(cur)
        if should_commit:
            try:
                connection.commit()
            except BaseException as exc:
                if _is_write_conflict(exc):
                    primary_error = MaterialCapabilityWriterError(
                        _WRITE_CONFLICT
                    )
                    rollback_required = True
                else:
                    commit_uncertain = True
                    primary_error = MaterialCapabilityWriterError(
                        _COMMIT_UNKNOWN
                    )
                    rollback_required = True
            else:
                rollback_required = False
        else:
            rollback_required = True
    except BaseException as exc:
        primary_error = exc
        rollback_required = connection is not None

    if connection is not None and rollback_required:
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

    if isinstance(primary_error, _CONTROL_FLOW):
        raise primary_error
    if commit_uncertain:
        raise MaterialCapabilityWriterError(_COMMIT_UNKNOWN) from None
    if rollback_error is not None:
        raise MaterialCapabilityWriterError(_ROLLBACK_FAILED) from None
    if primary_error is not None:
        if isinstance(primary_error, MaterialCapabilityWriterError):
            if primary_error.code in _PUBLIC_ERROR_CODES:
                raise primary_error
            raise MaterialCapabilityWriterError(_WRITE_FAILED) from None
        if _is_write_conflict(primary_error):
            raise MaterialCapabilityWriterError(_WRITE_CONFLICT) from None
        raise MaterialCapabilityWriterError(_WRITE_FAILED) from None
    if cleanup_error is not None:
        if isinstance(cleanup_error, _CONTROL_FLOW):
            raise cleanup_error
        raise MaterialCapabilityWriterError(_CLEANUP_FAILED) from None
    return outcome


def run_material_capability_confirmation_write(
    get_db, combined_report, selected, authentication, command,
):
    """Confirm one exact current proof subject in a serializable transaction."""

    if not callable(get_db):
        raise MaterialCapabilityWriterError(_INPUT_INVALID)
    session_hash = _validated_authentication(authentication)
    command = _validated_confirmation_command(command)
    try:
        prepared = prepare_supply_rfq_content(combined_report, selected)
        prepared_company_id = prepared["source"]["companyId"]
    except Exception:
        raise MaterialCapabilityWriterError(_INPUT_INVALID) from None
    if command["companyId"] != prepared_company_id:
        raise MaterialCapabilityWriterError(_TENANT_MISMATCH)

    def operation(cur):
        _lock_evidence_table(cur)
        actor = _authenticate(cur, session_hash, command["companyId"])
        source, subjects = _collect_active_proof(
            cur, prepared, command["companyId"]
        )
        matches = [
            subject for subject in subjects
            if subject["companySupplierLinkId"]
            == command["companySupplierLinkId"]
            and subject["supplierId"] == command["supplierId"]
            and subject["confirmationSubjectSha256"]
            == command["confirmationSubjectSha256"]
        ]
        if not matches:
            raise MaterialCapabilityWriterError(_SUBJECT_STALE)
        if len(matches) != 1:
            raise MaterialCapabilityWriterError(_EVIDENCE_INVALID)
        subject = matches[0]
        if subject["proofState"] == "revoked":
            raise MaterialCapabilityWriterError(_SUBJECT_TERMINAL)
        if subject["proofState"] == "confirmed":
            return _idempotent_result(
                "confirmed", "already_confirmed", source, subject,
                subject["evidence"][0],
            ), False

        actor_again = _authenticate(
            cur, session_hash, command["companyId"]
        )
        if not _same_actor(actor, actor_again):
            raise MaterialCapabilityWriterError(_AUTHENTICATION_REQUIRED)
        values = (
            WRITE_VERSION, "confirmed", source["companyId"],
            subject["companySupplierLinkId"], subject["supplierId"],
            subject["materialIdentitySha256"],
            subject["confirmationSubjectSha256"],
            actor["actor_membership_id"], actor["actor_user_id"],
            "директор", "director_manual", None,
        )
        inserted = _insert_assertion(cur, values)
        expected = {
            "event_kind": "confirmed",
            "company_id": source["companyId"],
            "company_supplier_link_id": subject["companySupplierLinkId"],
            "supplier_id": subject["supplierId"],
            "material_identity_sha256": subject[
                "materialIdentitySha256"
            ],
            "confirmation_subject_sha256": subject[
                "confirmationSubjectSha256"
            ],
            "actor_membership_id": actor["actor_membership_id"],
            "actor_user_id": actor["actor_user_id"],
            "actor_role": "директор",
            "source_kind": "director_manual",
            "revokes_assertion_id": None,
        }
        if any(inserted.get(key) != value for key, value in expected.items()):
            raise MaterialCapabilityWriterError(_WRITE_FAILED)
        return _result(inserted, "confirmed", 1, True), True

    return _run_transaction(get_db, operation)


def _read_target(cur, company_id, assertion_id):
    cur.execute(
        """SELECT id,confirmation_version,event_kind,company_id,
                  company_supplier_link_id,supplier_id,
                  material_identity_sha256,confirmation_subject_sha256,
                  actor_membership_id,actor_user_id,actor_role,source_kind,
                  revokes_assertion_id
             FROM public.supplier_material_capability_assertions
            WHERE company_id=%s AND id=%s
            ORDER BY id
            LIMIT %s
            FOR SHARE""",
        (company_id, assertion_id, 2),
    )
    try:
        rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    except Exception:
        raise MaterialCapabilityWriterError(_EVIDENCE_INVALID) from None
    if not rows:
        raise MaterialCapabilityWriterError(_TARGET_INVALID)
    if len(rows) != 1:
        raise MaterialCapabilityWriterError(_EVIDENCE_INVALID)
    if (
        rows[0].get("id") != assertion_id
        or rows[0].get("company_id") != company_id
        or rows[0].get("event_kind") != "confirmed"
    ):
        raise MaterialCapabilityWriterError(_TARGET_INVALID)
    return _decode_assertion(rows[0], _EVIDENCE_INVALID)


def _read_existing_revocation(cur, target):
    cur.execute(
        """SELECT id,confirmation_version,event_kind,company_id,
                  company_supplier_link_id,supplier_id,
                  material_identity_sha256,confirmation_subject_sha256,
                  actor_membership_id,actor_user_id,actor_role,source_kind,
                  revokes_assertion_id
             FROM public.supplier_material_capability_assertions
            WHERE company_id=%s
              AND revokes_assertion_id=%s
              AND event_kind='revoked'
            ORDER BY id
            LIMIT %s
            FOR SHARE""",
        (target["company_id"], target["id"], 2),
    )
    try:
        rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    except Exception:
        raise MaterialCapabilityWriterError(_EVIDENCE_INVALID) from None
    if len(rows) > 1:
        raise MaterialCapabilityWriterError(_EVIDENCE_INVALID)
    if not rows:
        return None
    revocation = _decode_assertion(rows[0], _EVIDENCE_INVALID)
    copied_fields = (
        "company_id", "company_supplier_link_id", "supplier_id",
        "material_identity_sha256", "confirmation_subject_sha256",
    )
    if (
        revocation["event_kind"] != "revoked"
        or revocation["revokes_assertion_id"] != target["id"]
        or any(revocation[field] != target[field] for field in copied_fields)
    ):
        raise MaterialCapabilityWriterError(_EVIDENCE_INVALID)
    return revocation


def run_material_capability_revocation_write(
    get_db, authentication, command,
):
    """Revoke one immutable confirmation in a serializable transaction."""

    if not callable(get_db):
        raise MaterialCapabilityWriterError(_INPUT_INVALID)
    session_hash = _validated_authentication(authentication)
    command = _validated_revocation_command(command)

    def operation(cur):
        _lock_evidence_table(cur)
        actor = _authenticate(cur, session_hash, command["companyId"])
        _schema_ready(cur)
        target = _read_target(
            cur, command["companyId"], command["confirmationAssertionId"]
        )
        existing = _read_existing_revocation(cur, target)
        if existing is not None:
            return _result(existing, "already_revoked", 0, False), False

        actor_again = _authenticate(
            cur, session_hash, command["companyId"]
        )
        if not _same_actor(actor, actor_again):
            raise MaterialCapabilityWriterError(_AUTHENTICATION_REQUIRED)
        values = (
            WRITE_VERSION, "revoked", target["company_id"],
            target["company_supplier_link_id"], target["supplier_id"],
            target["material_identity_sha256"],
            target["confirmation_subject_sha256"],
            actor["actor_membership_id"], actor["actor_user_id"],
            "директор", "director_manual", target["id"],
        )
        inserted = _insert_assertion(cur, values)
        copied_fields = (
            "company_id", "company_supplier_link_id", "supplier_id",
            "material_identity_sha256", "confirmation_subject_sha256",
        )
        if (
            inserted["event_kind"] != "revoked"
            or inserted["revokes_assertion_id"] != target["id"]
            or inserted["actor_membership_id"]
            != actor["actor_membership_id"]
            or inserted["actor_user_id"] != actor["actor_user_id"]
            or inserted["actor_role"] != "директор"
            or inserted["source_kind"] != "director_manual"
            or any(inserted[field] != target[field] for field in copied_fields)
        ):
            raise MaterialCapabilityWriterError(_WRITE_FAILED)
        return _result(inserted, "revoked", 1, True), True

    return _run_transaction(get_db, operation)


__all__ = [
    "WRITE_VERSION",
    "MaterialCapabilityWriterError",
    "run_material_capability_confirmation_write",
    "run_material_capability_revocation_write",
]
