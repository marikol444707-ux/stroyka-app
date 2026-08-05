import unittest

from backend.features.agent_jobs.handler_registry import (
    AgentJobContext,
    AgentJobHandlerRegistry,
    AgentJobHandlerRegistryError,
    build_default_handler_registry,
)


class AgentJobHandlerRegistryTests(unittest.TestCase):
    def test_registry_is_explicit_immutable_and_rejects_unknown_jobs(self):
        handler = lambda context: {"ok": True}
        registry = AgentJobHandlerRegistry((("director.daily_brief", handler),))

        self.assertEqual(registry.job_types, ("director.daily_brief",))
        self.assertIs(registry.get("director.daily_brief"), handler)
        self.assertIsNone(registry.get("director.unknown"))
        with self.assertRaises(TypeError):
            registry.handlers["director.unknown"] = handler

    def test_registry_rejects_duplicate_invalid_or_non_callable_handlers(self):
        handler = lambda context: {"ok": True}

        with self.assertRaises(AgentJobHandlerRegistryError):
            AgentJobHandlerRegistry((
                ("director.daily_brief", handler),
                ("director.daily_brief", handler),
            ))
        with self.assertRaises(AgentJobHandlerRegistryError):
            AgentJobHandlerRegistry((("Director Daily Brief", handler),))
        with self.assertRaises(AgentJobHandlerRegistryError):
            AgentJobHandlerRegistry((("director.daily_brief", object()),))

    def test_context_payload_is_deeply_immutable(self):
        context = AgentJobContext.from_claimed_row({
            "id": 41,
            "company_id": 7,
            "project_id": 12,
            "requested_by_user_id": 5,
            "requested_by_role": "director",
            "job_type": "director.daily_brief",
            "correlation_id": "corr-41",
            "payload_json": {"sections": ["projects"], "options": {"days": 7}},
            "attempts": 1,
            "max_attempts": 3,
        })

        self.assertEqual(context.owner_company_id, 7)
        self.assertEqual(context.payload["sections"], ("projects",))
        with self.assertRaises(TypeError):
            context.payload["new"] = True
        with self.assertRaises(TypeError):
            context.payload["options"]["days"] = 30
        self.assertNotIn("lease_token", context.__dataclass_fields__)

    def test_default_registry_only_exposes_the_non_business_probe(self):
        registry = build_default_handler_registry()
        context = AgentJobContext.from_claimed_row({
            "id": 41,
            "company_id": 7,
            "project_id": None,
            "requested_by_user_id": None,
            "requested_by_role": "system",
            "job_type": "system.worker_probe",
            "correlation_id": "corr-41",
            "payload_json": {},
            "attempts": 1,
            "max_attempts": 1,
        })

        self.assertEqual(registry.job_types, ("system.worker_probe",))
        self.assertEqual(
            registry.get("system.worker_probe")(context),
            {"ok": True, "workerReady": True},
        )
        self.assertIsNone(registry.get("director.daily_brief"))


if __name__ == "__main__":
    unittest.main()
