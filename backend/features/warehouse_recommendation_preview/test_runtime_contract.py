import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from backend.features.warehouse_recommendation_preview import runtime_contract
from backend.features.warehouse_recommendation_preview import content_contract


_parse_runtime_claims = (
    runtime_contract._parse_warehouse_anomaly_runtime_claims
)
_authorize_runtime_claims = (
    runtime_contract._authorize_warehouse_anomaly_runtime_claims
)
_public_runtime_projection = (
    runtime_contract._public_warehouse_anomaly_runtime_projection
)

_SESSION_HASH = "a" * 64
_AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": _SESSION_HASH,
}
_SELECTION_RULES = {
    "warehouse_invoice_request_mismatch": "warehouseInvoice",
    "warehouse_invoice_project_mismatch": "warehouseInvoice",
    "warehouse_invoice_delivery_mismatch": "warehouseInvoice",
    "warehouse_invoice_supplier_invoice_mismatch": "warehouseInvoice",
    "warehouse_invoice_items_invalid": "warehouseInvoice",
    "warehouse_receipt_invoice_mismatch": "warehouseHistory",
    "warehouse_receipt_line_invalid": "warehouseHistory",
    "warehouse_receipt_package_mismatch": "warehouseHistory",
    "warehouse_receipt_lot_invoice_mismatch": "receiptLot",
    "warehouse_receipt_lot_line_invalid": "receiptLot",
    "warehouse_receipt_lot_project_mismatch": "receiptLot",
    "warehouse_movement_invoice_mismatch": "warehouseMovement",
    "warehouse_movement_line_invalid": "warehouseMovement",
    "warehouse_movement_package_mismatch": "warehouseMovement",
    "warehouse_movement_lot_missing": "warehouseMovement",
    "warehouse_lot_movement_missing": "warehouseMovement",
    "warehouse_lot_movement_parent_mismatch": "lotMovement",
    "warehouse_lot_movement_source_mismatch": "lotMovement",
}


class _TextSubclass(str):
    pass


class _IntSubclass(int):
    pass


def _body(anomaly_code="warehouse_invoice_project_mismatch"):
    return {
        "projectId": 9,
        "jobId": 123,
        "selected": {
            "subjectKind": _SELECTION_RULES[anomaly_code],
            "subjectId": 456,
            "anomalyCode": anomaly_code,
        },
    }


def _stored_source():
    return {
        "companyId": 4,
        "projectId": 9,
        "estimateId": 51,
        "sourceRevision": "sha256:" + "d" * 64,
        "reconciliationId": 61,
        "baseEstimateId": 50,
        "reconciliationStatus": "Утверждена",
    }


def _candidate(anomaly_code):
    return {
        "subjectKind": _SELECTION_RULES[anomaly_code],
        "subjectId": 456,
        "anomalyCode": anomaly_code,
        "recommendationCode": (
            content_contract._ANOMALY_RECOMMENDATION_RULES[anomaly_code]
        ),
    }


def _content_result(anomaly_code, state="preview_ready"):
    keyword = {
        "preview_ready": {"relevant_sha256": "b" * 64},
        "blocked": {"blocker": "warehouse_anomaly_current_snapshot_blocked"},
        "stale": {"blocker": "warehouse_anomaly_candidate_stale"},
    }[state]
    return content_contract._content_result(
        _stored_source(), _candidate(anomaly_code), state=state, **keyword,
    )


class WarehouseAnomalyRuntimeClaimsTests(unittest.TestCase):
    def _parse(
        self,
        authentication=_AUTHENTICATION,
        *,
        company_mode="company",
        company_id="4",
        body=None,
    ):
        return _parse_runtime_claims(
            authentication,
            company_mode=company_mode,
            company_id=company_id,
            body=_body() if body is None else body,
        )

    def _assert_input_invalid(self, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(
            getattr(error, "code", None),
            "warehouse_anomaly_runtime_input_invalid",
        )
        self.assertEqual(
            error.args, ("warehouse_anomaly_runtime_input_invalid",),
        )
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_private_parser_has_one_exact_keyword_only_boundary(self):
        parameters = inspect.signature(_parse_runtime_claims).parameters
        self.assertEqual(
            list(parameters),
            ["authentication", "company_mode", "company_id", "body"],
        )
        self.assertEqual(
            parameters["authentication"].kind,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for name in ("company_mode", "company_id", "body"):
            self.assertEqual(
                parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )
            self.assertIs(
                parameters[name].default, inspect.Parameter.empty,
            )

    def test_returns_detached_immutable_claims_without_raw_credentials(self):
        authentication = dict(_AUTHENTICATION)
        body = _body()

        claims = self._parse(authentication, body=body)

        self.assertEqual(claims.session_hash, _SESSION_HASH)
        self.assertEqual(claims.company_id, 4)
        self.assertEqual(claims.project_id, 9)
        self.assertEqual(claims.job_id, 123)
        self.assertEqual(claims.selection.subject_kind, "warehouseInvoice")
        self.assertEqual(claims.selection.subject_id, 456)
        self.assertEqual(
            claims.selection.anomaly_code,
            "warehouse_invoice_project_mismatch",
        )
        with self.assertRaises(AttributeError):
            claims.company_id = 5
        with self.assertRaises(AttributeError):
            claims.selection.subject_id = 999

        authentication["sessionHash"] = "b" * 64
        body["projectId"] = 99
        body["selected"]["subjectId"] = 999
        self.assertEqual(claims.session_hash, _SESSION_HASH)
        self.assertEqual(claims.project_id, 9)
        self.assertEqual(claims.selection.subject_id, 456)
        rendered = repr(claims)
        for forbidden in (
            "authenticationKind", "cookie_session", "projectId", "jobId",
            "selected", "recommendation", "report", "content", "source",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_all_18_exact_kind_and_anomaly_pairs_are_accepted(self):
        for anomaly_code, subject_kind in _SELECTION_RULES.items():
            with self.subTest(anomaly_code=anomaly_code):
                claims = self._parse(body=_body(anomaly_code))
                self.assertEqual(
                    (
                        claims.selection.subject_kind,
                        claims.selection.anomaly_code,
                    ),
                    (subject_kind, anomaly_code),
                )
        self.assertEqual(len(_SELECTION_RULES), 18)

    def test_authentication_requires_the_exact_cookie_session_envelope(self):
        invalid = (
            None,
            {},
            {"authenticationKind": "cookie_session"},
            {**_AUTHENTICATION, "extra": 1},
            {**_AUTHENTICATION, "authenticationKind": "bearer"},
            {**_AUTHENTICATION, "authenticationKind": _TextSubclass(
                "cookie_session"
            )},
            {**_AUTHENTICATION, "sessionHash": "A" * 64},
            {**_AUTHENTICATION, "sessionHash": "a" * 63},
            {**_AUTHENTICATION, "sessionHash": "g" * 64},
            {**_AUTHENTICATION, "sessionHash": _TextSubclass("a" * 64)},
        )
        for value in invalid:
            with self.subTest(value=repr(value)):
                self._assert_input_invalid(
                    lambda value=value: self._parse(value),
                    secrets=("bearer", "A" * 64, "g" * 64),
                )

    def test_company_must_be_exact_company_mode_and_canonical_positive_header(self):
        invalid = (
            (None, "4"),
            ("all_companies", None),
            ("all_companies", "4"),
            (_TextSubclass("company"), "4"),
            ("company", None),
            ("company", 4),
            ("company", _TextSubclass("4")),
            ("company", ""),
            ("company", "0"),
            ("company", "04"),
            ("company", "+4"),
            ("company", " 4"),
            ("company", "4 "),
            ("company", "9223372036854775808"),
        )
        for company_mode, company_id in invalid:
            with self.subTest(
                company_mode=repr(company_mode), company_id=repr(company_id),
            ):
                self._assert_input_invalid(
                    lambda: self._parse(
                        company_mode=company_mode, company_id=company_id,
                    ),
                )

        claims = self._parse(company_id="9223372036854775807")
        self.assertEqual(claims.company_id, 9223372036854775807)

    def test_body_and_selection_reject_extra_missing_or_wrong_exact_types(self):
        invalid_bodies = []
        for field in ("projectId", "jobId", "selected"):
            value = _body()
            value.pop(field)
            invalid_bodies.append(value)
        invalid_bodies.append({**_body(), "companyId": 4})
        invalid_bodies.append({**_body(), "content": {}})
        for field in ("projectId", "jobId"):
            for invalid in (
                None, True, 0, -1, 1.0, "1", _IntSubclass(1),
                9223372036854775808,
            ):
                value = _body()
                value[field] = invalid
                invalid_bodies.append(value)
        for field in ("subjectKind", "subjectId", "anomalyCode"):
            value = _body()
            value["selected"].pop(field)
            invalid_bodies.append(value)
        value = _body()
        value["selected"]["recommendationCode"] = "private"
        invalid_bodies.append(value)
        value = _body()
        value["selected"]["hash"] = "a" * 64
        invalid_bodies.append(value)
        for field in ("subjectKind", "anomalyCode"):
            value = _body()
            value["selected"][field] = _TextSubclass(
                value["selected"][field]
            )
            invalid_bodies.append(value)
        for invalid in (
            None, True, 0, -1, 1.0, "1", _IntSubclass(1),
            9223372036854775808,
        ):
            value = _body()
            value["selected"]["subjectId"] = invalid
            invalid_bodies.append(value)

        for body in invalid_bodies:
            with self.subTest(body=repr(body)):
                self._assert_input_invalid(lambda body=body: self._parse(
                    body=body,
                ))

    def test_kind_and_anomaly_compatibility_is_fail_closed(self):
        invalid = (
            ("warehouseHistory", "warehouse_invoice_project_mismatch"),
            ("warehouseInvoice", "warehouse_receipt_line_invalid"),
            ("warehouseInvoice", "unknown_anomaly"),
            ("unknownSubject", "warehouse_invoice_project_mismatch"),
        )
        for subject_kind, anomaly_code in invalid:
            body = _body()
            body["selected"] = {
                "subjectKind": subject_kind,
                "subjectId": 456,
                "anomalyCode": anomaly_code,
            }
            with self.subTest(
                subject_kind=subject_kind, anomaly_code=anomaly_code,
            ):
                self._assert_input_invalid(lambda: self._parse(body=body))

    def test_module_is_private_and_has_no_io_or_runtime_registration(self):
        self.assertEqual(runtime_contract.__all__, [])
        source = inspect.getsource(runtime_contract)
        for forbidden in (
            "psycopg2", "backend.db", "get_db", "cursor(", "execute(",
            "requests", "httpx", "logging", "print(", "FastAPI", "APIRouter",
            "agent_jobs", "commit(", "rollback(",
        ):
            self.assertNotIn(forbidden, source)


class WarehouseAnomalyRuntimeAuthorizationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.claims = _parse_runtime_claims(
            _AUTHENTICATION,
            company_mode="company",
            company_id="4",
            body=_body(),
        )

    def _assert_fixed_error(self, code, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(getattr(error, "code", None), code)
        self.assertEqual(error.args, (code,))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_exact_single_actor_and_project_returns_the_same_immutable_claims(self):
        outcome = {"actor_count": 1, "project_exists": True}

        result = _authorize_runtime_claims(self.claims, outcome)

        self.assertIs(result, self.claims)
        self.assertEqual(outcome, {
            "actor_count": 1,
            "project_exists": True,
        })

    def test_actor_failure_precedes_project_existence_without_role_oracle(self):
        for actor_count in (0, 2):
            for project_exists in (False, True):
                with self.subTest(
                    actor_count=actor_count,
                    project_exists=project_exists,
                ):
                    self._assert_fixed_error(
                        "warehouse_anomaly_runtime_authentication_required",
                        lambda: _authorize_runtime_claims(
                            self.claims,
                            {
                                "actor_count": actor_count,
                                "project_exists": project_exists,
                            },
                        ),
                        secrets=(_SESSION_HASH,),
                    )

    def test_only_valid_actor_with_absent_project_is_opaque_not_found(self):
        self._assert_fixed_error(
            "warehouse_anomaly_runtime_resource_not_found",
            lambda: _authorize_runtime_claims(
                self.claims,
                {"actor_count": 1, "project_exists": False},
            ),
            secrets=(_SESSION_HASH,),
        )

    def test_malformed_auth_query_metadata_is_contract_invalid_before_outcome(self):
        invalid = (
            None,
            {},
            {"actor_count": 1},
            {"project_exists": True},
            {"actor_count": 1, "project_exists": True, "actor_id": 7},
            {"actor_count": True, "project_exists": True},
            {"actor_count": _IntSubclass(1), "project_exists": True},
            {"actor_count": -1, "project_exists": True},
            {"actor_count": 3, "project_exists": True},
            {"actor_count": 1.0, "project_exists": True},
            {"actor_count": "1", "project_exists": True},
            {"actor_count": 1, "project_exists": 1},
            {"actor_count": 1, "project_exists": None},
        )
        for outcome in invalid:
            with self.subTest(outcome=repr(outcome)):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_contract_invalid",
                    lambda outcome=outcome: _authorize_runtime_claims(
                        self.claims, outcome,
                    ),
                    secrets=(_SESSION_HASH,),
                )

    def test_non_claims_input_is_contract_invalid_without_consuming_an_outcome(self):
        class Outcome(dict):
            reads = 0

            def get(self, key, default=None):
                self.reads += 1
                return super().get(key, default)

        outcome = Outcome(actor_count=1, project_exists=True)
        self._assert_fixed_error(
            "warehouse_anomaly_runtime_contract_invalid",
            lambda: _authorize_runtime_claims(object(), outcome),
        )
        self.assertEqual(outcome.reads, 0)


class WarehouseAnomalyRuntimeDisclosurePolicyTests(unittest.TestCase):
    def _assert_contract_invalid(self, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(
            getattr(error, "code", None),
            "warehouse_anomaly_runtime_contract_invalid",
        )
        self.assertEqual(
            error.args, ("warehouse_anomaly_runtime_contract_invalid",),
        )
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_all_18_ready_candidates_share_one_minimal_public_policy(self):
        for anomaly_code in _SELECTION_RULES:
            with self.subTest(anomaly_code=anomaly_code):
                internal = _content_result(anomaly_code)
                result = _public_runtime_projection(internal)

                self.assertIs(type(result), dict)
                self.assertEqual(set(result), {
                    "warehouseAnomalyRuntimeVersion",
                    "ok",
                    "dryRun",
                    "writesAttempted",
                    "previewOnly",
                    "stockMovementAllowed",
                    "inventoryAdjustmentAllowed",
                    "applyAllowed",
                    "state",
                    "candidate",
                    "content",
                    "blockers",
                    "readOnlyTransaction",
                    "rolledBack",
                })
                self.assertEqual(result, {
                    "warehouseAnomalyRuntimeVersion": 1,
                    "ok": True,
                    "dryRun": True,
                    "writesAttempted": 0,
                    "previewOnly": True,
                    "stockMovementAllowed": False,
                    "inventoryAdjustmentAllowed": False,
                    "applyAllowed": False,
                    "state": "preview_ready",
                    "candidate": _candidate(anomaly_code),
                    "content": content_contract._fixed_content(
                        _candidate(anomaly_code)
                    ),
                    "blockers": [],
                    "readOnlyTransaction": True,
                    "rolledBack": True,
                })
                self.assertIs(type(result["candidate"]), dict)
                self.assertIs(type(result["content"]), dict)
                self.assertIs(type(result["blockers"]), list)

    def test_blocked_and_stale_replace_private_details_with_one_public_code(self):
        cases = (
            (
                "blocked",
                "warehouse_anomaly_preview_blocked",
                "warehouse_anomaly_current_snapshot_blocked",
            ),
            (
                "stale",
                "warehouse_anomaly_preview_stale",
                "warehouse_anomaly_candidate_stale",
            ),
        )
        for state, public_blocker, private_blocker in cases:
            with self.subTest(state=state):
                internal = _content_result(
                    "warehouse_invoice_project_mismatch", state,
                )
                self.assertEqual(internal["blockers"], [private_blocker])

                result = _public_runtime_projection(internal)

                self.assertEqual(result["state"], state)
                self.assertIsNone(result["content"])
                self.assertEqual(result["blockers"], [public_blocker])
                self.assertNotIn(private_blocker, json.dumps(
                    result, ensure_ascii=False, sort_keys=True,
                ))

    def test_projection_is_detached_and_never_mutates_the_internal_result(self):
        internal = _content_result("warehouse_invoice_project_mismatch")
        before = copy.deepcopy(internal)

        result = _public_runtime_projection(internal)

        self.assertEqual(internal, before)
        self.assertIsNot(result["candidate"], internal["candidate"])
        self.assertIsNot(result["content"], internal["content"])
        self.assertIsNot(result["blockers"], internal["blockers"])
        internal["candidate"]["subjectId"] = 999
        internal["content"]["title"] = "PRIVATE TITLE"
        internal["blockers"].append("PRIVATE BLOCKER")
        self.assertEqual(result["candidate"]["subjectId"], 456)
        self.assertNotEqual(result["content"]["title"], "PRIVATE TITLE")
        self.assertEqual(result["blockers"], [])

    def test_projection_recursively_excludes_every_private_source_and_hash(self):
        internal = _content_result("warehouse_invoice_project_mismatch")
        private_source_revision = internal["source"]["sourceRevision"]
        private_status = internal["source"]["reconciliationStatus"]
        private_content_hash = internal["contentSha256"]

        result = _public_runtime_projection(internal)
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)

        for forbidden_key in (
            "source", "companyId", "projectId", "jobId", "estimateId",
            "reconciliationId", "baseEstimateId", "reconciliationStatus",
            "sourceRevision", "contentSha256", "evidenceSha256",
            "revalidatedRelevantEvidenceSha256",
        ):
            self.assertNotIn('"' + forbidden_key + '"', serialized)
        for forbidden_value in (
            private_source_revision, private_status, private_content_hash,
        ):
            self.assertNotIn(forbidden_value, serialized)

    def test_malformed_internal_result_fails_closed_without_private_detail(self):
        valid = _content_result("warehouse_invoice_project_mismatch")
        invalid = []
        for field in tuple(valid):
            value = copy.deepcopy(valid)
            value.pop(field)
            invalid.append(value)
        invalid.append({**copy.deepcopy(valid), "jobId": 123})
        for field, replacement in (
            ("warehouseAnomalyContentVersion", 2),
            ("ok", 1),
            ("dryRun", False),
            ("writesAttempted", True),
            ("previewOnly", False),
            ("stockMovementAllowed", True),
            ("inventoryAdjustmentAllowed", True),
            ("applyAllowed", True),
            ("state", "ready"),
            ("readOnlyTransaction", False),
            ("rolledBack", False),
            ("source", []),
            ("candidate", []),
            ("content", []),
            ("blockers", ()),
            ("contentSha256", "PRIVATE-HASH"),
        ):
            value = copy.deepcopy(valid)
            value[field] = replacement
            invalid.append(value)

        value = copy.deepcopy(valid)
        value["candidate"]["subjectKind"] = "warehouseHistory"
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["candidate"]["recommendationCode"] = "private_code"
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["content"]["title"] = "PRIVATE TITLE"
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["source"]["sourceRevision"] = "sha256:" + "G" * 64
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["source"]["reconciliationStatus"] = "PRIVATE-STATUS"
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["source"]["baseEstimateId"] = value["source"]["estimateId"]
        invalid.append(value)
        value = copy.deepcopy(valid)
        value["contentSha256"] = "c" * 64
        invalid.append(value)
        value = _content_result(
            "warehouse_invoice_project_mismatch", "blocked",
        )
        value["blockers"] = ["PRIVATE-BLOCKER"]
        invalid.append(value)

        for value in invalid:
            with self.subTest(value=repr(value)[:200]):
                self._assert_contract_invalid(
                    lambda value=value: _public_runtime_projection(value),
                    secrets=(
                        "PRIVATE-HASH", "private_code", "PRIVATE TITLE",
                        "PRIVATE-SOURCE-MARKER",
                    ),
                )

    def test_private_module_imports_and_only_approved_access_callsite_are_frozen(self):
        tree = ast.parse(inspect.getsource(runtime_contract))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertEqual(imports, [
            "types",
            "typing",
            "backend.features.warehouse_recommendation_preview",
        ])

        package_root = Path(runtime_contract.__file__).resolve().parent
        backend_root = package_root.parents[1]
        callsites = []
        for path in backend_root.rglob("*.py"):
            if path == Path(runtime_contract.__file__).resolve():
                continue
            if path.name.startswith("test_"):
                continue
            source = path.read_text(encoding="utf-8")
            parsed = ast.parse(source)
            imports_runtime_contract = any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name.endswith(
                            "warehouse_recommendation_preview.runtime_contract"
                        )
                        for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and (
                        (node.module or "").endswith(
                            "warehouse_recommendation_preview.runtime_contract"
                        )
                        or (
                            (node.module or "").endswith(
                                "warehouse_recommendation_preview"
                            )
                            and any(
                                alias.name == "runtime_contract"
                                for alias in node.names
                            )
                        )
                    )
                )
                for node in ast.walk(parsed)
            )
            if imports_runtime_contract:
                callsites.append(str(path.relative_to(backend_root)))
        self.assertEqual(callsites, [
            "main.py",
            "features/warehouse_recommendation_preview/runtime_access.py",
            "features/warehouse_recommendation_preview/runtime_preview.py",
            "features/human_approved_actions/action_kernel.py",
        ])

    def test_existing_private_and_public_surfaces_remain_byte_identical(self):
        package_root = Path(runtime_contract.__file__).resolve().parent
        backend_root = package_root.parents[1]
        expected = {
            package_root / "__init__.py": (
                "d30babfeb425141af2fbf645be82eef358b6dea7d213b6d6b23cef3e7c551fea"
            ),
            package_root / "content_preview.py": (
                "6bf1b385b833bd2f02b16e066fbb41a7ea6aa9566cb4ce4c6eeff8d5dea9da64"
            ),
            package_root / "content_contract.py": (
                "ebfd82c1ed2c1a7216b06636785585c6c02856d2b1df185e5c7210ca90aac10a"
            ),
            package_root / "runtime_budget.py": (
                "72542dbdcb2487f1da98a177337e7becac22fd918703adac17b39ec60ec89717"
            ),
            backend_root / "db.py": (
                "7e53bc3f1bed6481c9579dc241768b948fc22b37ec5d0809505022e62e2d750f"
            ),
            backend_root / "main.py": (
                "9456a455b4aa51bbfed8dcf48c3ebf821bb239781aaa3abf4c4ffa5e8b6246f5"
            ),
        }
        actual = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in expected
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
