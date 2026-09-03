import ast
import math
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

from backend.features.supply_kp_comparison.company_boundary import (
    BOUNDARY_INPUT_INVALID,
    BOUNDARY_VIOLATION,
    COMPANY_MODE,
    OWNER_SCOPE_COMPANY,
    READ_ONLY_MODE,
    SupplyCompanyBoundaryError,
    assert_company_chain,
    assert_resource_company,
    assert_resource_project,
    boundary_from_request_context,
    boundary_metadata_view,
    build_company_boundary,
    company_sql_predicate,
)


MODULE_PATH = Path(__file__).with_name("company_boundary.py")
RESOLVER_PATH = Path(__file__).with_name("source_resolver.py")


class SupplyCompanyBoundaryTests(unittest.TestCase):
    def assert_boundary_error(self, expected_code, operation):
        with self.assertRaises(SupplyCompanyBoundaryError) as caught:
            operation()
        self.assertEqual(caught.exception.code, expected_code)
        self.assertEqual(str(caught.exception), expected_code)

    def test_builds_deterministic_read_only_company_boundary(self):
        first = build_company_boundary(
            owner_scope="company",
            company_id=17,
            project_id=42,
            payload={
                "requestId": 91,
                "companyId": 17,
                "nested": {"project_id": 42},
            },
        )
        second = build_company_boundary(
            owner_scope="company",
            company_id=17,
            project_id=42,
            payload={
                "nested": {"project_id": 42},
                "companyId": 17,
                "requestId": 91,
            },
        )

        self.assertEqual(first, second)
        self.assertEqual(first.owner_scope, OWNER_SCOPE_COMPANY)
        self.assertEqual(first.company_mode, COMPANY_MODE)
        self.assertEqual(first.execution_mode, READ_ONLY_MODE)
        self.assertEqual(len(first.payload_sha256), 64)
        self.assertEqual(len(first.boundary_sha256), 64)
        self.assertEqual(first.writes_attempted, 0)
        self.assertEqual(first.model_calls, 0)

        result = first.to_dict()
        self.assertTrue(result["readOnly"])
        self.assertFalse(result["automaticApprovalAllowed"])
        self.assertEqual(result["companyId"], 17)
        self.assertEqual(result["projectId"], 42)
        self.assertNotIn("payload", result)

    def test_boundary_is_frozen_and_metadata_view_is_immutable(self):
        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
        )
        with self.assertRaises(FrozenInstanceError):
            boundary.company_id = 18

        view = boundary_metadata_view(boundary)
        self.assertIsInstance(view, MappingProxyType)
        with self.assertRaises(TypeError):
            view["companyId"] = 18

    def test_rejects_invalid_or_ambiguous_server_owned_ids(self):
        invalid_values = (None, True, False, 0, -1, "17", 17.0)
        for value in invalid_values:
            with self.subTest(company_id=value):
                self.assert_boundary_error(
                    BOUNDARY_INPUT_INVALID,
                    lambda value=value: build_company_boundary(
                        owner_scope="company",
                        company_id=value,
                    ),
                )

        for value in (True, 0, -1, "42", 42.0):
            with self.subTest(project_id=value):
                self.assert_boundary_error(
                    BOUNDARY_INPUT_INVALID,
                    lambda value=value: build_company_boundary(
                        owner_scope="company",
                        company_id=17,
                        project_id=value,
                    ),
                )

    def test_rejects_non_company_owner_or_all_companies_mode(self):
        for owner_scope in ("account", "platform", "all_companies", "", None):
            with self.subTest(owner_scope=owner_scope):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION,
                    lambda owner_scope=owner_scope: build_company_boundary(
                        owner_scope=owner_scope,
                        company_id=17,
                    ),
                )

        for company_mode in ("all_companies", "summary", "", None):
            with self.subTest(company_mode=company_mode):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION,
                    lambda company_mode=company_mode: build_company_boundary(
                        owner_scope="company",
                        company_id=17,
                        company_mode=company_mode,
                    ),
                )

    def test_request_context_requires_exactly_one_verified_company(self):
        boundary = boundary_from_request_context(
            {
                "mode": "company",
                "companyId": 17,
                "company_id": 17,
                "companyIds": [17],
            },
            project_id=42,
            payload={"company_id": 17, "projectId": 42},
        )
        self.assertEqual(boundary.company_id, 17)

        invalid_contexts = (
            {"mode": "all_companies", "companyId": 17},
            {"mode": "company"},
            {"mode": "company", "companyId": 17, "company_id": 18},
            {"mode": "company", "companyId": 17, "companyIds": [17, 18]},
            {"mode": "company", "companyId": 17, "companyIds": [18]},
        )
        for context in invalid_contexts:
            with self.subTest(context=context):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION,
                    lambda context=context: boundary_from_request_context(context),
                )

    def test_untrusted_payload_cannot_replace_company_at_any_depth(self):
        payloads = (
            {"companyId": 18},
            {"source": {"company_id": 18}},
            {"rows": [{"resourceCompanyId": 17}, {"resourceCompanyId": 18}]},
            {"tenant_company_id": 18},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION,
                    lambda payload=payload: build_company_boundary(
                        owner_scope="company",
                        company_id=17,
                        payload=payload,
                    ),
                )

    def test_untrusted_payload_cannot_widen_company_mode_or_owner_scope(self):
        payloads = (
            {"companyMode": "all_companies"},
            {"company_mode": "summary"},
            {"ownerScope": "account"},
            {"owner_scope": "platform"},
            {"nested": [{"owner_scope": "all_companies"}]},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION,
                    lambda payload=payload: build_company_boundary(
                        owner_scope="company",
                        company_id=17,
                        payload=payload,
                    ),
                )

    def test_untrusted_payload_cannot_create_or_replace_project_scope(self):
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: build_company_boundary(
                owner_scope="company",
                company_id=17,
                payload={"projectId": 42},
            ),
        )
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: build_company_boundary(
                owner_scope="company",
                company_id=17,
                project_id=42,
                payload={"project_id": 43},
            ),
        )

        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
            project_id=42,
            payload={
                "projectId": 42,
                "nested": {"project_scope_id": 42},
            },
        )
        self.assertEqual(boundary.project_id, 42)

    def test_rejects_oversized_unsupported_or_non_finite_payload(self):
        self.assert_boundary_error(
            BOUNDARY_INPUT_INVALID,
            lambda: build_company_boundary(
                owner_scope="company",
                company_id=17,
                payload={"value": "x" * (64 * 1024)},
            ),
        )
        self.assert_boundary_error(
            BOUNDARY_INPUT_INVALID,
            lambda: build_company_boundary(
                owner_scope="company",
                company_id=17,
                payload={"value": object()},
            ),
        )
        for value in (math.nan, math.inf, -math.inf):
            self.assert_boundary_error(
                BOUNDARY_INPUT_INVALID,
                lambda value=value: build_company_boundary(
                    owner_scope="company",
                    company_id=17,
                    payload={"value": value},
                ),
            )

    def test_resource_company_must_be_present_exact_and_consistent(self):
        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
        )
        self.assertEqual(
            assert_resource_company(boundary, {"company_id": 17}),
            17,
        )
        self.assertEqual(
            assert_resource_company(
                boundary,
                {"tenant": 17},
                company_keys=("tenant",),
            ),
            17,
        )

        invalid_rows = (
            {},
            {"company_id": None},
            {"company_id": 18},
            {"company_id": 17, "companyId": 18},
            {"company_id": "17"},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assert_boundary_error(
                    BOUNDARY_VIOLATION
                    if row != {"company_id": "17"}
                    else BOUNDARY_INPUT_INVALID,
                    lambda row=row: assert_resource_company(boundary, row),
                )

    def test_company_chain_fails_closed_on_one_foreign_row(self):
        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
        )
        self.assertEqual(
            assert_company_chain(
                boundary,
                {"company_id": 17},
                {"company_id": 17},
                {"company_id": 17},
            ),
            (17, 17, 17),
        )
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: assert_company_chain(
                boundary,
                {"company_id": 17},
                {"company_id": 18},
            ),
        )

    def test_project_scope_is_checked_only_against_server_scope(self):
        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
            project_id=42,
        )
        self.assertEqual(
            assert_resource_project(boundary, {"project_id": 42}),
            42,
        )
        self.assertIsNone(
            assert_resource_project(boundary, {}, required=False),
        )
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: assert_resource_project(
                boundary,
                {},
                required=True,
            ),
        )
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: assert_resource_project(
                boundary,
                {"project_id": 43},
            ),
        )

        company_only = build_company_boundary(
            owner_scope="company",
            company_id=17,
        )
        self.assert_boundary_error(
            BOUNDARY_VIOLATION,
            lambda: assert_resource_project(
                company_only,
                {"project_id": 42},
            ),
        )

    def test_sql_predicate_is_parameterized_and_identifier_is_allowlisted(self):
        boundary = build_company_boundary(
            owner_scope="company",
            company_id=17,
        )
        self.assertEqual(
            company_sql_predicate(boundary),
            ("company_id=%s", (17,)),
        )
        self.assertEqual(
            company_sql_predicate(boundary, "invoice.company_id"),
            ("invoice.company_id=%s", (17,)),
        )
        for column in (
            "company_id OR TRUE",
            "invoice.company_id;DELETE",
            "invoice..company_id",
            "",
        ):
            with self.subTest(column=column):
                self.assert_boundary_error(
                    BOUNDARY_INPUT_INVALID,
                    lambda column=column: company_sql_predicate(
                        boundary,
                        column,
                    ),
                )

    def test_error_codes_do_not_leak_tenant_values(self):
        try:
            boundary = build_company_boundary(
                owner_scope="company",
                company_id=170001,
            )
            assert_resource_company(
                boundary,
                {"company_id": 180002, "secret": "PRIVATE-INVOICE"},
            )
        except SupplyCompanyBoundaryError as error:
            rendered = str(error)
        else:
            self.fail("boundary mismatch must fail")

        self.assertEqual(rendered, BOUNDARY_VIOLATION)
        self.assertNotIn("170001", rendered)
        self.assertNotIn("180002", rendered)
        self.assertNotIn("PRIVATE-INVOICE", rendered)

    def test_module_remains_pure_and_has_no_write_or_model_surface(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(MODULE_PATH))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        self.assertTrue(
            imported_roots.isdisjoint(
                {
                    "psycopg2",
                    "sqlalchemy",
                    "requests",
                    "httpx",
                    "openai",
                    "backend",
                    "features",
                }
            )
        )
        upper = source.upper()
        for marker in (
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
            "ALTER TABLE",
            "DROP TABLE",
            "COMMIT",
            "ROLLBACK",
        ):
            self.assertNotIn(marker, upper)

    def test_live_source_resolver_invokes_the_company_boundary(self):
        source = RESOLVER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(RESOLVER_PATH))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        resolver = functions.get("resolve_supply_technical_source_rows")
        self.assertIsNotNone(resolver)
        rendered = ast.unparse(resolver)

        for required_call in (
            "build_company_boundary",
            "assert_company_chain",
            "assert_resource_company",
            "assert_resource_project",
        ):
            self.assertIn(required_call, rendered)

        self.assertLess(
            rendered.index("build_company_boundary"),
            rendered.index("compare_required_to_offer"),
        )
        self.assertIn(
            "company_keys=('company_id', 'offer_company_id')",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
