import inspect
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.features.supply_recommendation_preview.runtime_routes as runtime_routes
from backend.auth import CookieSessionAuthenticationError
from backend.features.supply_recommendation_preview.material_capability_proof import (
    SupplierMaterialCapabilityProofError,
)
from backend.features.supply_recommendation_preview.material_capability_source_resolver import (
    MaterialCapabilitySourceResolverError,
)
from backend.features.supply_recommendation_preview.material_capability_writer import (
    MaterialCapabilityWriterError,
)


REGISTER = runtime_routes.register_material_capability_runtime_module
SELECTOR_INVALID = "supply_supplier_material_route_selector_invalid"
CONFIRMATION_PAYLOAD_INVALID = (
    "supply_supplier_material_confirmation_payload_invalid"
)
REVOCATION_PAYLOAD_INVALID = "supply_supplier_material_revocation_payload_invalid"
RUNTIME_FAILED = "supply_supplier_material_runtime_failed"
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
SELECTION = {"requestId": 21, "requestItemIndex": 0}
REPORT = {"privateReport": "must-not-cross-the-HTTP-boundary"}
PROOF = {
    "proofVersion": 1,
    "ok": True,
    "state": "confirmation_required",
    "source": {"companyId": 4, **SELECTION},
    "proofSubjects": [],
    "materialEligibilityProven": False,
    "selectionAllowed": False,
    "sendAllowed": False,
    "blockers": [],
}
PUBLIC_PROOF = {
    "publicProofVersion": 1,
    "state": "confirmation_required",
    "requestId": 21,
    "requestItemIndex": 0,
    "subjectCount": 0,
    "subjects": [],
    "materialEligibilityProven": False,
    "selectionAllowed": False,
    "sendAllowed": False,
    "blockers": [],
}


def confirmation_receipt(idempotent=False):
    return {
        "writeVersion": 1,
        "ok": True,
        "eventKind": "confirmed",
        "state": "already_confirmed" if idempotent else "confirmed",
        "companyId": 4,
        "companySupplierLinkId": 31,
        "supplierId": 41,
        "materialIdentitySha256": "c" * 64,
        "confirmationSubjectSha256": "b" * 64,
        "assertionId": 501,
        "revokesAssertionId": None,
        "actorUserId": 11,
        "actorMembershipId": 12,
        "writesAttempted": 0 if idempotent else 1,
        "committed": not idempotent,
    }


def revocation_receipt(idempotent=False):
    return {
        "writeVersion": 1,
        "ok": True,
        "eventKind": "revoked",
        "state": "already_revoked" if idempotent else "revoked",
        "companyId": 4,
        "companySupplierLinkId": 31,
        "supplierId": 41,
        "materialIdentitySha256": "c" * 64,
        "confirmationSubjectSha256": "b" * 64,
        "assertionId": 502,
        "revokesAssertionId": 501,
        "actorUserId": 11,
        "actorMembershipId": 12,
        "writesAttempted": 0 if idempotent else 1,
        "committed": not idempotent,
    }


def public_receipt(receipt):
    return {
        "writeVersion": receipt["writeVersion"],
        "eventKind": receipt["eventKind"],
        "state": receipt["state"],
        "companySupplierLinkId": receipt["companySupplierLinkId"],
        "supplierId": receipt["supplierId"],
        "confirmationSubjectSha256": receipt[
            "confirmationSubjectSha256"
        ],
        "assertionId": receipt["assertionId"],
        "revokesAssertionId": receipt["revokesAssertionId"],
        "writesAttempted": receipt["writesAttempted"],
        "committed": receipt["committed"],
    }


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path, **_kwargs):
        return self._decorator("GET", path)

    def post(self, path, **_kwargs):
        return self._decorator("POST", path)

    def _decorator(self, method, path):
        def decorate(func):
            self.routes[(method, path)] = func
            return func

        return decorate


class RouteHarness:
    def __init__(
        self,
        *,
        authentication_error=None,
        read_error=None,
        confirmation_error=None,
        revocation_error=None,
        confirmation_result=None,
        revocation_result=None,
        proof_result=None,
    ):
        self.db_calls = 0
        self.authentication_calls = []
        self.runtime_read_calls = []
        self.confirmation_calls = []
        self.revocation_calls = []
        self.forbidden_calls = []
        self.authentication_error = authentication_error
        self.read_error = read_error
        self.confirmation_error = confirmation_error
        self.revocation_error = revocation_error
        self.confirmation_result = (
            confirmation_result or confirmation_receipt()
        )
        self.revocation_result = revocation_result or revocation_receipt()
        self.proof_result = proof_result or PROOF
        self.get_db_dependency = self.get_db
        self.app = FastAPI()
        REGISTER(self.app, {
            "enabled": True,
            "get_db": self.get_db_dependency,
            "build_cookie_session_authentication": self.authenticate,
            "run_material_capability_runtime_read": self.run_runtime_read,
            "run_material_capability_confirmation_write": self.confirm,
            "run_material_capability_revocation_write": self.revoke,
            "insert_audit_event": self.forbidden("audit"),
            "call_model": self.forbidden("model"),
            "rank_suppliers": self.forbidden("rank"),
            "select_supplier": self.forbidden("select"),
            "send_rfq": self.forbidden("send"),
        })
        self.client = TestClient(self.app)

    def forbidden(self, name):
        def fail(*_args, **_kwargs):
            self.forbidden_calls.append(name)
            raise AssertionError(f"forbidden route side effect: {name}")

        return fail

    def get_db(self):
        self.db_calls += 1
        return object()

    def authenticate(
        self,
        request,
        authorization=None,
        csrf_token=None,
        *,
        require_csrf=True,
    ):
        self.authentication_calls.append((
            request.method,
            request.url.path,
            authorization,
            csrf_token,
            require_csrf,
        ))
        if self.authentication_error:
            raise self.authentication_error
        return dict(AUTHENTICATION)

    def run_runtime_read(self, *args):
        self.runtime_read_calls.append(args)
        if self.read_error:
            raise self.read_error
        return {
            "proof": dict(self.proof_result),
            "combinedReport": REPORT,
            "selected": dict(SELECTION),
        }

    def confirm(self, *args):
        self.confirmation_calls.append(args)
        if self.confirmation_error:
            raise self.confirmation_error
        return dict(self.confirmation_result)

    def revoke(self, *args):
        self.revocation_calls.append(args)
        if self.revocation_error:
            raise self.revocation_error
        return dict(self.revocation_result)

    @staticmethod
    def headers(csrf=False):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }
        if csrf:
            headers["X-CSRF-Token"] = "csrf-value"
        return headers

    @staticmethod
    def confirmation_body():
        return {
            "companySupplierLinkId": 31,
            "supplierId": 41,
            "confirmationSubjectSha256": "b" * 64,
        }


class MaterialCapabilityRuntimeRouteContractTests(unittest.TestCase):
    def test_feature_flag_off_registers_nothing_and_reads_no_other_dep(self):
        app = FakeApp()

        REGISTER(app, {"enabled": False})

        self.assertEqual(app.routes, {})

    def test_enabled_registers_only_the_three_approved_routes(self):
        app = FakeApp()
        no_call = lambda *_args, **_kwargs: None
        REGISTER(app, {
            "enabled": True,
            "get_db": no_call,
            "build_cookie_session_authentication": no_call,
            "run_material_capability_runtime_read": no_call,
            "run_material_capability_confirmation_write": no_call,
            "run_material_capability_revocation_write": no_call,
        })

        self.assertEqual(set(app.routes), {
            ("GET", "/supply-requests/{request_id}/items/"
                    "{request_item_index}/material-capability-proof"),
            ("POST", "/supply-requests/{request_id}/items/"
                     "{request_item_index}/material-capability-confirmations"),
            ("POST", "/supplier-material-capability-confirmations/"
                     "{confirmation_assertion_id}/revocations"),
        })

    def test_cookie_dependency_and_exact_private_writer_arguments(self):
        harness = RouteHarness()

        proof = harness.client.get(
            "/supply-requests/21/items/0/material-capability-proof",
            headers=harness.headers(),
        )
        confirmed = harness.client.post(
            "/supply-requests/21/items/0/material-capability-confirmations",
            headers=harness.headers(csrf=True),
            json=harness.confirmation_body(),
        )
        revoked = harness.client.post(
            "/supplier-material-capability-confirmations/501/revocations",
            headers=harness.headers(csrf=True),
            json={},
        )

        self.assertEqual(
            (proof.status_code, proof.json()), (200, PUBLIC_PROOF),
        )
        self.assertNotIn("privateReport", proof.text)
        self.assertEqual(
            (confirmed.status_code, confirmed.json()),
            (201, public_receipt(confirmation_receipt())),
        )
        self.assertEqual(
            (revoked.status_code, revoked.json()),
            (201, public_receipt(revocation_receipt())),
        )
        self.assertEqual(
            [call[-1] for call in harness.authentication_calls],
            [False, True, True],
        )
        self.assertEqual(
            [call[3] for call in harness.authentication_calls],
            [None, "csrf-value", "csrf-value"],
        )
        self.assertEqual(harness.runtime_read_calls, [
            (
                harness.get_db_dependency,
                AUTHENTICATION,
                {"companyId": 4, **SELECTION},
            ),
            (
                harness.get_db_dependency,
                AUTHENTICATION,
                {"companyId": 4, **SELECTION},
            ),
        ])
        self.assertEqual(harness.confirmation_calls, [(
            harness.get_db_dependency,
            REPORT,
            SELECTION,
            AUTHENTICATION,
            {"companyId": 4, **harness.confirmation_body()},
        )])
        self.assertEqual(harness.revocation_calls, [(
            harness.get_db_dependency,
            AUTHENTICATION,
            {"companyId": 4, "confirmationAssertionId": 501},
        )])
        self.assertEqual(harness.forbidden_calls, [])

    def test_new_rows_are_201_and_idempotent_receipts_are_200(self):
        cases = (
            ("confirmation", confirmation_receipt(False), 201),
            ("confirmation", confirmation_receipt(True), 200),
            ("revocation", revocation_receipt(False), 201),
            ("revocation", revocation_receipt(True), 200),
        )
        for operation, receipt, status in cases:
            with self.subTest(operation=operation, state=receipt["state"]):
                harness = RouteHarness(
                    confirmation_result=receipt,
                    revocation_result=receipt,
                )
                if operation == "confirmation":
                    response = harness.client.post(
                        "/supply-requests/21/items/0/"
                        "material-capability-confirmations",
                        headers=harness.headers(csrf=True),
                        json=harness.confirmation_body(),
                    )
                else:
                    response = harness.client.post(
                        "/supplier-material-capability-confirmations/501/"
                        "revocations",
                        headers=harness.headers(csrf=True),
                    )
                self.assertEqual((response.status_code, response.json()), (
                    status, public_receipt(receipt),
                ))

    def test_http_projection_never_exposes_actor_or_evidence_payload(self):
        proof = dict(PROOF)
        proof["state"] = "proof_complete"
        proof["proofSubjects"] = [{
            "companySupplierLinkId": 31,
            "supplierId": 41,
            "materialIdentitySha256": "c" * 64,
            "confirmationSubjectSha256": "b" * 64,
            "proofState": "confirmed",
            "evidence": [{
                "assertionId": 501,
                "eventKind": "confirmed",
                "actorMembershipId": 12,
                "actorUserId": 11,
                "actorRole": "директор",
                "sourceKind": "director_manual",
                "revokesAssertionId": None,
            }],
        }]
        proof["materialEligibilityProven"] = True
        harness = RouteHarness(proof_result=proof)

        read = harness.client.get(
            "/supply-requests/21/items/0/material-capability-proof",
            headers=harness.headers(),
        )
        written = harness.client.post(
            "/supply-requests/21/items/0/"
            "material-capability-confirmations",
            headers=harness.headers(csrf=True),
            json=harness.confirmation_body(),
        )

        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json()["subjects"], [{
            "companySupplierLinkId": 31,
            "supplierId": 41,
            "confirmationSubjectSha256": "b" * 64,
            "proofState": "confirmed",
            "confirmationAssertionId": 501,
            "revocationAssertionId": None,
        }])
        self.assertEqual(written.status_code, 201)
        for response in (read, written):
            self.assertNotIn("actorUserId", response.text)
            self.assertNotIn("actorMembershipId", response.text)
            self.assertNotIn("actorRole", response.text)
            self.assertNotIn("sourceKind", response.text)
            self.assertNotIn("evidence", response.text)

    def test_invalid_selector_or_confirmation_body_fails_before_db(self):
        selector_cases = (
            ("/supply-requests/0/items/0/material-capability-proof", {}),
            ("/supply-requests/x/items/0/material-capability-proof", {}),
            ("/supply-requests/21/items/-1/material-capability-proof", {}),
            ("/supply-requests/21/items/0/material-capability-proof", {
                "X-Company-Mode": "all_companies",
            }),
            ("/supply-requests/21/items/0/material-capability-proof", {
                "X-Company-Mode": "company", "X-Company-Id": "04",
            }),
        )
        for path, header_override in selector_cases:
            with self.subTest(path=path, headers=header_override):
                harness = RouteHarness()
                headers = harness.headers()
                headers.update(header_override)
                if header_override.get("X-Company-Mode") == "all_companies":
                    headers.pop("X-Company-Id", None)
                response = harness.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {"detail": SELECTOR_INVALID})
                self.assertEqual(harness.db_calls, 0)
                self.assertEqual(harness.runtime_read_calls, [])

        invalid_bodies = (
            None,
            {},
            {**RouteHarness.confirmation_body(), "companyId": 4},
            {**RouteHarness.confirmation_body(), "proof": PROOF},
            {**RouteHarness.confirmation_body(), "supplierId": True},
            {**RouteHarness.confirmation_body(),
             "confirmationSubjectSha256": "B" * 64},
        )
        for body in invalid_bodies:
            with self.subTest(body=body):
                harness = RouteHarness()
                kwargs = {"headers": harness.headers(csrf=True)}
                if body is not None:
                    kwargs["json"] = body
                response = harness.client.post(
                    "/supply-requests/21/items/0/"
                    "material-capability-confirmations",
                    **kwargs,
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {
                    "detail": CONFIRMATION_PAYLOAD_INVALID,
                })
                self.assertEqual(harness.db_calls, 0)
                self.assertEqual(harness.runtime_read_calls, [])
                self.assertEqual(harness.confirmation_calls, [])

    def test_revocation_body_is_absent_or_exact_empty_object_only(self):
        for invalid in ("null", "[]", '{"companyId":4}'):
            with self.subTest(body=invalid):
                harness = RouteHarness()
                headers = harness.headers(csrf=True)
                headers["Content-Type"] = "application/json"
                response = harness.client.post(
                    "/supplier-material-capability-confirmations/501/"
                    "revocations",
                    headers=headers,
                    content=invalid,
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {
                    "detail": REVOCATION_PAYLOAD_INVALID,
                })
                self.assertEqual(harness.revocation_calls, [])

        for body in (None, {}):
            harness = RouteHarness()
            kwargs = {"headers": harness.headers(csrf=True)}
            if body is not None:
                kwargs["json"] = body
            response = harness.client.post(
                "/supplier-material-capability-confirmations/501/revocations",
                **kwargs,
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(len(harness.revocation_calls), 1)

    def test_auth_and_runtime_read_errors_have_fixed_statuses(self):
        cases = (
            ({"authentication_error": CookieSessionAuthenticationError(
                "cookie_session_authentication_required")}, 401,
             "cookie_session_authentication_required"),
            ({"authentication_error": CookieSessionAuthenticationError(
                "cookie_session_csrf_invalid")}, 403,
             "cookie_session_csrf_invalid"),
            ({"read_error": MaterialCapabilitySourceResolverError(
                "supply_supplier_material_source_input_invalid")}, 422,
             "supply_supplier_material_source_input_invalid"),
            ({"read_error": MaterialCapabilitySourceResolverError(
                "supply_supplier_material_source_not_found")}, 404,
             "supply_supplier_material_source_not_found"),
            ({"read_error": MaterialCapabilitySourceResolverError(
                "supply_supplier_material_source_invalid")}, 409,
             "supply_supplier_material_source_invalid"),
            ({"read_error": SupplierMaterialCapabilityProofError(
                "supply_supplier_material_schema_not_ready")}, 503,
             "supply_supplier_material_schema_not_ready"),
            ({"read_error": SupplierMaterialCapabilityProofError(
                "supply_supplier_material_proof_read_failed")}, 500,
             RUNTIME_FAILED),
        )
        for options, status, code in cases:
            with self.subTest(code=code):
                harness = RouteHarness(**options)
                method = "post" if "authentication_error" in options and (
                    options["authentication_error"].code.endswith("csrf_invalid")
                ) else "get"
                if method == "post":
                    response = harness.client.post(
                        "/supply-requests/21/items/0/"
                        "material-capability-confirmations",
                        headers=harness.headers(csrf=True),
                        json=harness.confirmation_body(),
                    )
                else:
                    response = harness.client.get(
                        "/supply-requests/21/items/0/"
                        "material-capability-proof",
                        headers=harness.headers(),
                    )
                self.assertEqual((response.status_code, response.json()), (
                    status, {"detail": code},
                ))
                if "authentication_error" in options:
                    self.assertEqual(harness.db_calls, 0)

    def test_incomplete_completed_proof_is_a_fixed_service_unavailable(self):
        blocker_codes = (
            "supply_supplier_material_schema_not_ready",
            "supply_supplier_material_evidence_scan_incomplete",
            "supply_supplier_material_dependency_incomplete",
        )
        for code in blocker_codes:
            with self.subTest(code=code):
                proof = dict(PROOF)
                proof.update({"state": "incomplete", "blockers": [code]})
                harness = RouteHarness(proof_result=proof)
                response = harness.client.get(
                    "/supply-requests/21/items/0/material-capability-proof",
                    headers=harness.headers(),
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": code})

    def test_mutations_require_cookie_csrf_before_buffering_invalid_body(self):
        error = CookieSessionAuthenticationError(
            "cookie_session_csrf_invalid"
        )
        cases = (
            (
                "/supply-requests/21/items/0/"
                "material-capability-confirmations",
                {},
            ),
            (
                "/supplier-material-capability-confirmations/501/"
                "revocations",
                {"companyId": 4},
            ),
        )
        for path, body in cases:
            with self.subTest(path=path):
                harness = RouteHarness(authentication_error=error)
                response = harness.client.post(
                    path,
                    headers=harness.headers(),
                    json=body,
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {
                    "detail": "cookie_session_csrf_invalid",
                })
                self.assertEqual(len(harness.authentication_calls), 1)
                self.assertEqual(harness.runtime_read_calls, [])

    def test_writer_errors_use_the_fixed_public_status_table(self):
        cases = (
            ("supply_supplier_material_writer_input_invalid", 422),
            ("supply_supplier_material_writer_authentication_required", 403),
            ("supply_supplier_material_writer_target_invalid", 404),
            ("supply_supplier_material_writer_subject_stale", 409),
            ("supply_supplier_material_writer_subject_terminal", 409),
            ("supply_supplier_material_writer_tenant_mismatch", 409),
            ("supply_supplier_material_writer_evidence_invalid", 409),
            ("supply_supplier_material_writer_write_conflict", 409),
            ("supply_supplier_material_writer_schema_not_ready", 503),
            ("supply_supplier_material_writer_commit_outcome_unknown", 503),
            ("supply_supplier_material_writer_write_failed", 500),
            ("supply_supplier_material_writer_rollback_failed", 500),
            ("supply_supplier_material_writer_cleanup_failed", 500),
        )
        for writer_code, status in cases:
            with self.subTest(code=writer_code):
                harness = RouteHarness(
                    confirmation_error=MaterialCapabilityWriterError(
                        writer_code
                    )
                )
                response = harness.client.post(
                    "/supply-requests/21/items/0/"
                    "material-capability-confirmations",
                    headers=harness.headers(csrf=True),
                    json=harness.confirmation_body(),
                )
                code = writer_code if status != 500 else RUNTIME_FAILED
                self.assertEqual((response.status_code, response.json()), (
                    status, {"detail": code},
                ))
                self.assertEqual(harness.forbidden_calls, [])

    def test_runtime_has_no_main_model_send_selection_or_audit_seam(self):
        source = inspect.getsource(runtime_routes).lower()
        for forbidden in (
            "backend.main",
            "resolve_material_capability_source",
            "run_supplier_material_capability_proof_preview",
            "insert_audit_event",
            "call_model",
            "call_ai",
            "rank_suppliers",
            "select_supplier",
            "send_rfq",
            "openai",
            "yandex",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
