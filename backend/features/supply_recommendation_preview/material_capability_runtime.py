"""Cookie-session-only, same-snapshot material capability proof runtime."""

import copy

import psycopg2.extras

from . import material_capability_proof
from . import material_capability_source_resolver
from . import rfq_content


_INPUT_INVALID = "supply_supplier_material_runtime_input_invalid"
_AUTHENTICATION_REQUIRED = (
    "supply_supplier_material_runtime_authentication_required"
)
_READ_FAILED = "supply_supplier_material_runtime_read_failed"
_ROLLBACK_FAILED = "supply_supplier_material_runtime_rollback_failed"
_CLEANUP_FAILED = "supply_supplier_material_runtime_cleanup_failed"
_RUNTIME_CODES = frozenset({
    _INPUT_INVALID,
    _AUTHENTICATION_REQUIRED,
    _READ_FAILED,
    _ROLLBACK_FAILED,
    _CLEANUP_FAILED,
})
_AUTHENTICATION_FIELDS = {"authenticationKind", "sessionHash"}
_ACTOR_FIELDS = {
    "actor_user_id", "actor_membership_id", "actor_company_id",
}
_SELECTOR_FIELDS = {"companyId", "requestId", "requestItemIndex"}
_PROOF_FIELDS = {
    "proofVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "subjectKind", "confirmationSha256",
    "confirmationSubjectCount", "proofSubjectCount", "provenSubjectCount",
    "proofSubjects", "materialEligibilityProven", "rankingApplied",
    "supplierIds", "selectionAllowed", "sendAllowed", "blockers",
    "proofSha256", "readOnlyTransaction", "rolledBack",
}
_PROOF_SOURCE_FIELDS = {
    "companyId", "requestId", "requestItemIndex", "requestItemSha256",
    "rfqContentSha256", "supplierEligibilitySha256",
    "materialIdentitySha256",
}
_SOURCE_ERROR_CODES = frozenset({
    "supply_supplier_material_source_input_invalid",
    "supply_supplier_material_source_not_found",
    "supply_supplier_material_source_invalid",
})
_PROOF_ERROR_CODES = frozenset({
    "supply_supplier_material_proof_input_invalid",
    "supply_supplier_material_proof_read_failed",
    "supply_supplier_material_proof_rollback_failed",
    "supply_supplier_material_proof_cleanup_failed",
    "supply_supplier_material_schema_not_ready",
    "supply_supplier_material_evidence_invalid",
    "supply_supplier_material_evidence_scan_incomplete",
    "supply_supplier_material_dependency_invalid",
    "supply_supplier_material_dependency_incomplete",
    "supply_supplier_no_active_company_links",
})
_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)


class MaterialCapabilityRuntimeError(ValueError):
    """Fixed runtime failure without session, database or business detail."""

    def __init__(self, code):
        code = code if code in _RUNTIME_CODES else _READ_FAILED
        self.code = code
        super().__init__(code)


class _AuthenticationFailure(Exception):
    pass


def _positive_int(value):
    return type(value) is int and value > 0


def _non_negative_int(value):
    return type(value) is int and value >= 0


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
        raise MaterialCapabilityRuntimeError(_INPUT_INVALID)
    return value["sessionHash"]


def _validated_selectors(value):
    if (
        type(value) is not dict
        or set(value) != _SELECTOR_FIELDS
        or not _positive_int(value.get("companyId"))
        or not _positive_int(value.get("requestId"))
        or not _non_negative_int(value.get("requestItemIndex"))
    ):
        raise MaterialCapabilityRuntimeError(_INPUT_INVALID)
    return dict(value)


def _configure_transaction(cur):
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
            LIMIT %s""",
        (session_hash, company_id, 2),
    )
    try:
        rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    except Exception:
        rows = []
    if len(rows) != 1:
        raise _AuthenticationFailure()
    actor = rows[0]
    if (
        set(actor) != _ACTOR_FIELDS
        or not _positive_int(actor.get("actor_user_id"))
        or not _positive_int(actor.get("actor_membership_id"))
        or not _positive_int(actor.get("actor_company_id"))
        or actor.get("actor_company_id") != company_id
    ):
        raise _AuthenticationFailure()


def _validated_resolved(value, selectors):
    if type(value) is not dict or set(value) != {"combinedReport", "selected"}:
        raise ValueError("runtime source invalid")
    selected = value.get("selected")
    if (
        type(selected) is not dict
        or selected != {
            "requestId": selectors["requestId"],
            "requestItemIndex": selectors["requestItemIndex"],
        }
        or type(value.get("combinedReport")) is not dict
    ):
        raise ValueError("runtime source invalid")
    return {
        "combinedReport": copy.deepcopy(value["combinedReport"]),
        "selected": dict(selected),
    }


def _completed_proof(value, selectors):
    if type(value) is not dict or set(value) != _PROOF_FIELDS:
        raise ValueError("runtime proof invalid")
    source = value.get("source")
    if (
        value.get("ok") is not True
        or value.get("dryRun") is not True
        or type(value.get("writesAttempted")) is not int
        or value.get("writesAttempted") != 0
        or value.get("readOnlyTransaction") is not False
        or value.get("rolledBack") is not False
        or not _sha256(value.get("proofSha256"))
        or value.get("proofSha256")
        != material_capability_proof.calculate_proof_sha256(value)
        or type(source) is not dict
        or set(source) != _PROOF_SOURCE_FIELDS
        or source.get("companyId") != selectors["companyId"]
        or source.get("requestId") != selectors["requestId"]
        or source.get("requestItemIndex") != selectors["requestItemIndex"]
    ):
        raise ValueError("runtime proof invalid")
    result = copy.deepcopy(value)
    result["readOnlyTransaction"] = True
    result["rolledBack"] = True
    result["proofSha256"] = (
        material_capability_proof.calculate_proof_sha256(result)
    )
    return result


def _run_material_capability_runtime_read(
    get_db, authentication, selectors,
):
    if not callable(get_db):
        raise MaterialCapabilityRuntimeError(_INPUT_INVALID)
    selectors = _validated_selectors(selectors)
    session_hash = _validated_authentication(authentication)

    connection = None
    cur = None
    resolved = None
    raw_proof = None
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
        _authenticate(cur, session_hash, selectors["companyId"])
        resolved = _validated_resolved(
            material_capability_source_resolver
            .resolve_material_capability_source(
                cur,
                company_id=selectors["companyId"],
                request_id=selectors["requestId"],
                request_item_index=selectors["requestItemIndex"],
            ),
            selectors,
        )
        prepared = rfq_content.prepare_supply_rfq_content(
            resolved["combinedReport"], resolved["selected"],
        )
        raw_proof = (
            material_capability_proof
            .collect_prepared_supplier_material_capability_proof(
                cur, prepared,
            )
        )
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
    if connection is not None and hasattr(connection, "close"):
        try:
            connection.close()
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc

    if isinstance(primary_error, _CONTROL_FLOW):
        raise primary_error
    if rollback_error is not None:
        raise MaterialCapabilityRuntimeError(_ROLLBACK_FAILED) from None
    if isinstance(primary_error, _AuthenticationFailure):
        raise MaterialCapabilityRuntimeError(
            _AUTHENTICATION_REQUIRED
        ) from None
    if isinstance(
        primary_error,
        material_capability_source_resolver
        .MaterialCapabilitySourceResolverError,
    ) and primary_error.code in _SOURCE_ERROR_CODES:
        raise primary_error
    if isinstance(
        primary_error,
        material_capability_proof.SupplierMaterialCapabilityProofError,
    ) and primary_error.code in _PROOF_ERROR_CODES:
        raise primary_error
    if primary_error is not None:
        raise MaterialCapabilityRuntimeError(_READ_FAILED) from None
    if cleanup_error is not None:
        raise MaterialCapabilityRuntimeError(_CLEANUP_FAILED) from None
    try:
        proof = _completed_proof(raw_proof, selectors)
        return {
            "proof": proof,
            "combinedReport": copy.deepcopy(resolved["combinedReport"]),
            "selected": dict(resolved["selected"]),
        }
    except Exception:
        raise MaterialCapabilityRuntimeError(_READ_FAILED) from None


def run_material_capability_runtime_read(
    get_db, authentication, selectors,
):
    """Return proof plus private server source for an immediate writer call."""

    return _run_material_capability_runtime_read(
        get_db, authentication, selectors,
    )


def run_material_capability_proof_read(
    get_db,
    authentication,
    *,
    company_id,
    request_id,
    request_item_index,
):
    """Return only the public proof from one authoritative read snapshot."""

    bundle = _run_material_capability_runtime_read(
        get_db,
        authentication,
        {
            "companyId": company_id,
            "requestId": request_id,
            "requestItemIndex": request_item_index,
        },
    )
    return bundle["proof"]


__all__ = [
    "MaterialCapabilityRuntimeError",
    "run_material_capability_proof_read",
    "run_material_capability_runtime_read",
]
