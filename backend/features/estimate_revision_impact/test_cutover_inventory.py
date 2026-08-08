import unittest

from backend.features.estimate_revision_impact.cutover_inventory import (
    audit_cutover_inventory,
)


REQUIRED_CHECKS = (
    "test_same_name_readiness_rolls_back_and_preserves_business_tables",
    "test_repeat_and_concurrent_enqueue_create_one_exact_job",
    "test_exact_runner_completes_only_selected_tenant_job",
    "test_failure_rolls_back_queue_and_preserves_business_tables",
    "test_final_readiness_is_read_only_and_exact",
)


def integration_source(*names):
    return "\n".join(f"def {name}(): pass" for name in names)


def reviewed_sources():
    return {
        "backend/features/estimate_revision_impact/handler.py": """
            from .combined_report import run_combined_impact_audit

            def build_estimate_revision_impact_handler(
                run_report=run_combined_impact_audit,
            ):
                run_report_dependency = run_report
                def handle(context):
                    source = source_from_job_payload(context.payload)
                    return run_report_dependency(context, source)
                return handle
        """,
        "backend/features/estimate_revision_impact/producer.py": """
            def prepare_estimate_revision_impact_job(cur, source, enqueue_job):
                return enqueue_job(cur, source=source)
        """,
        "backend/features/estimate_revision_impact/handoff.py": """
            FEATURE_FLAG = "ESTIMATE_REVISION_IMPACT_APPLY"
            COMPANY_ALLOWLIST = "ESTIMATE_REVISION_IMPACT_COMPANY_IDS"

            def handoff_estimate_revision_impact_transition(prepare_job, enqueue_job):
                def tracked_enqueue(*args, **kwargs):
                    return enqueue_job(*args, **kwargs)
                return prepare_job(apply=True)
        """,
        "backend/features/agent_jobs/handler_registry.py": """
            def build_default_handler_registry():
                return ((
                    "estimate.revision_impact",
                    handle_estimate_revision_impact,
                ),)
        """,
        "backend/features/agent_jobs/runner.py": """
            class AgentJobRunner:
                def run_once(self, cur, result):
                    return complete_agent_job(cur, result=result)
        """,
        "backend/main.py": """
            def create_estimate(conn):
                conn.commit()
                handoff_estimate_revision_impact_transition()

            def update_estimate(conn):
                conn.commit()
                handoff_estimate_revision_impact_transition()

            def update_estimate_status(conn):
                conn.commit()
                handoff_estimate_revision_impact_transition()
        """,
    }


class EstimateRevisionImpactCutoverInventoryTests(unittest.TestCase):
    def test_repository_inventory_is_exact_and_has_all_postgres_proofs(self):
        report = audit_cutover_inventory()

        self.assertTrue(report["ok"], report["violations"])
        self.assertEqual(report["a7DmlStatements"], 0)
        self.assertEqual(report["operationalMutationCalls"], 3)
        self.assertEqual(report["handlerRegistrations"], 1)
        self.assertEqual(report["postCommitHandoffs"], 3)
        self.assertEqual(report["missingIntegrationChecks"], [])

    def test_exact_reviewed_execution_surface_is_ready(self):
        report = audit_cutover_inventory(
            source_files=reviewed_sources(),
            integration_test_source=integration_source(*REQUIRED_CHECKS),
            enforce_complete_inventory=True,
        )

        self.assertTrue(report["ok"], report["violations"])
        self.assertTrue(report["writerInventoryReady"])
        self.assertTrue(report["runtimeInventoryReady"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["a7DmlStatements"], 0)
        self.assertEqual(report["operationalMutationCalls"], 3)
        self.assertEqual(report["handlerRegistrations"], 1)
        self.assertEqual(report["postCommitHandoffs"], 3)
        self.assertEqual(report["requiredIntegrationChecks"], 5)
        self.assertEqual(report["missingIntegrationChecks"], [])
        self.assertEqual(report["violations"], [])

    def test_business_dml_fails_closed(self):
        sources = reviewed_sources()
        sources[
            "backend/features/estimate_revision_impact/handler.py"
        ] += """
            def unsafe(cur):
                cur.execute("UPDATE projects SET budget=0 WHERE id=1")
        """

        report = audit_cutover_inventory(
            source_files=sources,
            integration_test_source=integration_source(*REQUIRED_CHECKS),
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["writerInventoryReady"])
        self.assertIn(
            "a7_business_dml_forbidden",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_model_notification_or_http_route_dependency_fails_closed(self):
        cases = {
            "model": "from openai import OpenAI",
            "notification": "from backend.features.messenger.service import send_message",
            "route": "@app.post('/estimate-revision-impact/apply')\ndef apply(): pass",
        }
        for label, unsafe_source in cases.items():
            with self.subTest(label=label):
                sources = reviewed_sources()
                sources[
                    "backend/features/estimate_revision_impact/unsafe.py"
                ] = unsafe_source
                report = audit_cutover_inventory(
                    source_files=sources,
                    integration_test_source=integration_source(*REQUIRED_CHECKS),
                    enforce_complete_inventory=True,
                )
                self.assertFalse(report["runtimeInventoryReady"])

    def test_unreviewed_external_business_writer_import_fails_closed(self):
        sources = reviewed_sources()
        sources["backend/features/estimate_revision_impact/unsafe.py"] = """
            from backend.features.project_budget_adjustments.approval import (
                approve_budget_adjustment,
            )
        """

        report = audit_cutover_inventory(
            source_files=sources,
            integration_test_source=integration_source(*REQUIRED_CHECKS),
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["runtimeInventoryReady"])
        self.assertIn(
            "a7_external_import_not_allowlisted",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_automatic_apply_route_outside_a7_package_fails_closed(self):
        sources = reviewed_sources()
        sources["backend/features/unsafe/routes.py"] = """
            @router.post("/estimate-revision-impact/apply")
            def apply_revision_impact():
                pass
        """

        report = audit_cutover_inventory(
            source_files=sources,
            integration_test_source=integration_source(*REQUIRED_CHECKS),
            enforce_complete_inventory=True,
        )

        self.assertFalse(report["runtimeInventoryReady"])
        self.assertIn(
            "automatic_a7_apply_route",
            {item["reasonCode"] for item in report["violations"]},
        )

    def test_missing_registration_post_commit_order_or_postgres_proof_blocks(self):
        cases = []

        missing_registration = reviewed_sources()
        missing_registration[
            "backend/features/agent_jobs/handler_registry.py"
        ] = "def build_default_handler_registry(): return ()"
        cases.append((missing_registration, REQUIRED_CHECKS))

        before_commit = reviewed_sources()
        before_commit["backend/main.py"] = before_commit[
            "backend/main.py"
        ].replace(
            "conn.commit()\n                handoff_estimate_revision_impact_transition()",
            "handoff_estimate_revision_impact_transition()\n                conn.commit()",
            1,
        )
        cases.append((before_commit, REQUIRED_CHECKS))
        cases.append((reviewed_sources(), REQUIRED_CHECKS[:-1]))

        for sources, checks in cases:
            with self.subTest(checks=checks):
                report = audit_cutover_inventory(
                    source_files=sources,
                    integration_test_source=integration_source(*checks),
                    enforce_complete_inventory=True,
                )
                self.assertFalse(report["ok"])
                self.assertGreater(report["violationCount"], 0)


if __name__ == "__main__":
    unittest.main()
