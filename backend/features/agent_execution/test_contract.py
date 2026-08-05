import json
import unittest

from backend.features.agent_execution.contract import (
    AgentExecutionContractError,
    get_execution_contract,
    prepare_agent_execution,
    sanitize_director_agent_tool_result,
)
from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS
from backend.features.director_agent.read_tools import DIRECTOR_AGENT_TOOLS


class AgentExecutionContractTests(unittest.TestCase):
    def test_tool_policy_matches_live_director_agent_registry(self):
        self.assertEqual(tuple(DIRECTOR_AGENT_TOOLS), DIRECTOR_AGENT_READ_TOOLS)
        self.assertTrue(all(
            callable(DIRECTOR_AGENT_TOOLS[tool_name]["fn"])
            and DIRECTOR_AGENT_TOOLS[tool_name]["desc"]
            for tool_name in DIRECTOR_AGENT_READ_TOOLS
        ))
        with self.assertRaises(TypeError):
            DIRECTOR_AGENT_TOOLS["projects"]["fn"] = lambda *_: []

    def test_daily_brief_contract_is_read_only_and_bounded(self):
        contract = get_execution_contract("director.daily_brief")

        self.assertEqual(contract.allowed_tools, DIRECTOR_AGENT_READ_TOOLS)
        self.assertTrue(contract.read_only)
        self.assertEqual(contract.database_access, "none")
        self.assertLessEqual(contract.timeout_seconds, 45)
        self.assertLessEqual(contract.max_model_calls, 2)
        self.assertLessEqual(contract.max_tool_calls, len(DIRECTOR_AGENT_READ_TOOLS))
        self.assertLessEqual(contract.max_input_bytes, 32 * 1024)
        self.assertLessEqual(contract.max_output_tokens, 1600)
        self.assertEqual(contract.cost_currency, "RUB")
        self.assertGreater(contract.max_cost_minor_units, 0)
        self.assertLessEqual(contract.max_cost_minor_units, 500)

    def test_unknown_job_type_fails_closed(self):
        with self.assertRaises(AgentExecutionContractError):
            get_execution_contract("director.unknown")

    def test_requested_tools_must_be_an_explicit_allowlisted_subset(self):
        prepared = prepare_agent_execution(
            job_type="director.daily_brief",
            owner_company_id=7,
            requested_tools=["projects", "supply", "projects"],
            model_payload={"briefDate": "2026-08-05", "facts": {}},
        )

        self.assertEqual(prepared.owner_company_id, 7)
        self.assertEqual(prepared.requested_tools, ("projects", "supply"))

        for requested_tools in (None, ["sql"], ["warehouse", "write_payment"]):
            with self.subTest(requested_tools=requested_tools):
                with self.assertRaises(AgentExecutionContractError):
                    prepare_agent_execution(
                        job_type="director.daily_brief",
                        owner_company_id=7,
                        requested_tools=requested_tools,
                        model_payload={"briefDate": "2026-08-05", "facts": {}},
                    )

    def test_model_payload_rejects_unknown_or_sensitive_fields(self):
        invalid_payloads = (
            {"briefDate": "2026-08-05", "facts": {}, "rawDatabaseRows": []},
            {"briefDate": "2026-08-05", "facts": {"authToken": "secret"}},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(AgentExecutionContractError):
                    prepare_agent_execution(
                        job_type="director.daily_brief",
                        owner_company_id=7,
                        requested_tools=["projects"],
                        model_payload=payload,
                    )

    def test_model_payload_requires_typed_minimal_fields(self):
        invalid_payloads = (
            {"facts": {}},
            {"briefDate": "05.08.2026", "facts": {}},
            {"briefDate": "2026-08-05", "facts": []},
            {"briefDate": "2026-08-05", "facts": {}, "sections": ["sql"]},
            {"briefDate": "2026-08-05", "facts": {}, "sections": ["supply"]},
            {"briefDate": "2026-08-05", "facts": {"supply": {}}},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(AgentExecutionContractError):
                    prepare_agent_execution(
                        job_type="director.daily_brief",
                        owner_company_id=7,
                        requested_tools=["projects"],
                        model_payload=payload,
                    )

    def test_execution_requires_one_server_owned_company(self):
        for company_id in (None, 0, -1, [7], "all_companies"):
            with self.subTest(company_id=company_id):
                with self.assertRaises(AgentExecutionContractError):
                    prepare_agent_execution(
                        job_type="director.daily_brief",
                        owner_company_id=company_id,
                        requested_tools=[],
                        model_payload={"briefDate": "2026-08-05", "facts": {}},
                    )

    def test_model_payload_rejects_database_context_and_secret_like_values(self):
        invalid_facts = (
            {"projects": {"rawDatabaseRows": []}},
            {"projects": {"credentials": {"value": "not-for-model"}}},
            {"projects": [{"name": "Bearer private-token"}]},
            {"projects": [{"name": "Incomplete"}]},
            {"supply": {"requestStatusCounts": {}}},
        )

        for facts in invalid_facts:
            with self.subTest(facts=facts):
                with self.assertRaises(AgentExecutionContractError):
                    prepare_agent_execution(
                        job_type="director.daily_brief",
                        owner_company_id=7,
                        requested_tools=list(facts),
                        model_payload={"briefDate": "2026-08-05", "facts": facts},
                    )

    def test_model_payload_is_canonical_and_size_limited(self):
        prepared = prepare_agent_execution(
            job_type="director.daily_brief",
            owner_company_id=7,
            requested_tools=["projects"],
            model_payload={
                "sections": ["projects"],
                "briefDate": "2026-08-05",
                "facts": {"projects": [{
                    "name": "Demo",
                    "status": "В работе",
                    "budget": 1000,
                    "progress": 25,
                    "deadline": "2026-12-31",
                }]},
            },
        )

        payload = json.loads(prepared.model_payload_json)
        self.assertEqual(payload["briefDate"], "2026-08-05")
        self.assertEqual(payload["sections"], ["projects"])
        self.assertEqual(payload["facts"]["projects"][0]["name"], "Demo")
        self.assertNotIn("client", payload["facts"]["projects"][0])

        with self.assertRaises(AgentExecutionContractError):
            prepare_agent_execution(
                job_type="director.daily_brief",
                owner_company_id=7,
                requested_tools=["projects"],
                model_payload={
                    "briefDate": "2026-08-05",
                    "facts": {"projects": [{
                        "name": "x" * (33 * 1024),
                        "status": "В работе",
                        "budget": 1000,
                        "progress": 25,
                        "deadline": "2026-12-31",
                    }]},
                },
            )

    def test_finance_result_removes_company_id_and_unknown_database_fields(self):
        sanitized = sanitize_director_agent_tool_result(
            "finances",
            [{
                "companyId": 7,
                "project": "School",
                "status": "В работе",
                "budget": 1000,
                "paymentsNet": 250,
                "manualExpenses": None,
                "manualExpensesScoped": False,
                "rawDatabaseRows": [{"secretValue": "must-not-pass"}],
            }],
        )

        self.assertEqual(sanitized, [{
            "project": "School",
            "status": "В работе",
            "budget": 1000.0,
            "paymentsNet": 250.0,
            "manualExpenses": None,
            "manualExpensesScoped": False,
        }])

    def test_prepared_execution_does_not_accept_runtime_limit_overrides(self):
        with self.assertRaises(TypeError):
            prepare_agent_execution(
                job_type="director.daily_brief",
                owner_company_id=7,
                requested_tools=[],
                model_payload={},
                timeout_seconds=3600,
            )


if __name__ == "__main__":
    unittest.main()
