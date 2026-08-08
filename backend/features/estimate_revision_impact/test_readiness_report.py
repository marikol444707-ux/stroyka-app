import json
import subprocess
import sys
import unittest
from pathlib import Path

from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
)
from backend.features.estimate_revision_impact.readiness_report import (
    collect_exact_job_ledger,
    run_readiness_report,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    source,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
    material_projection,
)


def ready_inventory():
    return {
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "writerInventoryReady": True,
        "runtimeInventoryReady": True,
        "a7DmlStatements": 0,
        "operationalMutationCalls": 3,
        "expectedOperationalMutationCalls": 3,
        "handlerRegistrations": 1,
        "postCommitHandoffs": 3,
        "requiredIntegrationChecks": 5,
        "missingIntegrationChecks": [],
        "violationCount": 0,
        "violations": [],
        "violationsTruncated": False,
    }


def ready_agent_schema():
    return {
        "ok": True,
        "dryRun": True,
        "table": "agent_jobs",
        "writesAttempted": 0,
        "tableExists": True,
        "missingColumns": [],
        "missingIndexes": [],
        "missingConstraints": [],
        "summary": {
            "total": 0,
            "invalidOwner": 0,
            "invalidStatus": 0,
            "invalidLeaseState": 0,
        },
        "readyForWorker": True,
    }


def exact_job_row(**changes):
    plan = build_estimate_revision_impact_job_plan(source())
    row = {
        "id": 81,
        "owner_scope": "company",
        "company_id": plan.company_id,
        "project_id": plan.project_id,
        "project_scope_id": plan.project_id,
        "requested_by_user_id": None,
        "requested_by_role": plan.requested_by_role,
        "job_type": plan.job_type,
        "idempotency_key": plan.idempotency_key,
        "correlation_id": plan.correlation_id,
        "payload_json": dict(plan.payload),
        "result_json": {},
        "status": "queued",
        "priority": plan.priority,
        "attempts": 0,
        "max_attempts": plan.max_attempts,
        "locked_at": None,
        "locked_by": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
    row.update(changes)
    return row


class ExactJobLedgerTests(unittest.TestCase):
    def test_absent_queued_and_valid_succeeded_states_are_ready(self):
        absent = collect_exact_job_ledger(FakeCursor(((),)), source())
        self.assertTrue(absent["ledgerReady"])
        self.assertEqual(absent["state"], "absent")
        self.assertEqual(absent["jobIds"], [])

        queued = collect_exact_job_ledger(
            FakeCursor(((exact_job_row(),),)), source(),
        )
        self.assertTrue(queued["ledgerReady"])
        self.assertEqual(queued["state"], "queued")
        self.assertEqual(queued["jobIds"], [81])

        result = {
            **combined(),
            "readOnlyTransaction": True,
            "rolledBack": True,
        }
        succeeded = collect_exact_job_ledger(
            FakeCursor(((exact_job_row(
                status="succeeded",
                attempts=1,
                result_json=result,
            ),),)),
            source(),
        )
        self.assertTrue(succeeded["ledgerReady"], succeeded)
        self.assertEqual(succeeded["state"], "succeeded")

    def test_duplicate_foreign_payload_lease_or_result_drift_fails_closed(self):
        cases = (
            (exact_job_row(), exact_job_row(id=82)),
            (exact_job_row(company_id=5),),
            (exact_job_row(payload_json={}),),
            (exact_job_row(locked_by="worker"),),
            (exact_job_row(status="failed", attempts=1),),
            (exact_job_row(
                status="succeeded",
                attempts=1,
                result_json={"ok": True},
            ),),
        )
        for rows in cases:
            with self.subTest(rows=rows):
                report = collect_exact_job_ledger(
                    FakeCursor((rows,)), source(),
                )
                self.assertFalse(report["ledgerReady"])
                self.assertGreater(report["issueCount"], 0)
                serialized = json.dumps(report)
                self.assertNotIn(source().source_revision, serialized)
                self.assertNotIn("schemaVersion", serialized)


class EstimateRevisionImpactReadinessTests(unittest.TestCase):
    def test_incomplete_non_actionable_evidence_is_safe_for_shadow_canary(self):
        impact = combined(material=material_projection(
            state="review_required",
            complete=False,
            reasonCounts={"material_lineage_missing": 1},
            needsReview=[{"reasonCode": "material_lineage_missing"}],
        ))
        cursor = FakeCursor(((),))
        connection = FakeConnection(cursor)

        report = run_readiness_report(
            lambda: connection,
            source(),
            collect_combined=lambda cur, exact: impact,
            build_agent_schema=lambda cur: ready_agent_schema(),
            audit_inventory=lambda: ready_inventory(),
        )

        self.assertTrue(report["ok"])
        self.assertTrue(report["readyForCanary"], report)
        self.assertFalse(report["combinedAudit"]["complete"])
        self.assertFalse(report["combinedAudit"]["actionable"])
        self.assertEqual(report["ledgerAudit"]["state"], "absent")
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_inventory_schema_ledger_or_combined_drift_blocks_canary(self):
        cases = (
            {
                "inventory": {**ready_inventory(), "runtimeInventoryReady": False},
            },
            {
                "schema": {**ready_agent_schema(), "readyForWorker": False},
            },
            {
                "rows": (exact_job_row(status="failed", attempts=1),),
            },
            {
                "impact": {**combined(), "evidenceSha256": "0" * 64},
            },
        )
        for changes in cases:
            with self.subTest(changes=changes):
                connection = FakeConnection(FakeCursor((changes.get("rows", ()),)))
                report = run_readiness_report(
                    lambda: connection,
                    source(),
                    collect_combined=lambda *_args, value=changes.get(
                        "impact", combined()
                    ): value,
                    build_agent_schema=lambda _cur, value=changes.get(
                        "schema", ready_agent_schema()
                    ): value,
                    audit_inventory=lambda value=changes.get(
                        "inventory", ready_inventory()
                    ): value,
                )
                self.assertFalse(report["readyForCanary"])
                self.assertTrue(report["rolledBack"])

    def test_runner_rolls_back_and_closes_when_collection_raises(self):
        connection = FakeConnection(FakeCursor(()))
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            run_readiness_report(
                lambda: connection,
                source(),
                collect_combined=lambda *_args: (_ for _ in ()).throw(
                    RuntimeError("unavailable")
                ),
                build_agent_schema=lambda _cur: ready_agent_schema(),
                audit_inventory=lambda: ready_inventory(),
            )
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_module_help_and_package_script_are_available(self):
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.features.estimate_revision_impact.readiness_report",
                "--help",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for option in (
            "--company-id",
            "--project-id",
            "--estimate-id",
            "--source-revision",
        ):
            self.assertIn(option, completed.stdout)
        scripts = json.loads((root / "package.json").read_text())["scripts"]
        self.assertEqual(
            scripts["audit:estimate-revision-impact-readiness"],
            "python3 -m backend.features.estimate_revision_impact.readiness_report",
        )


if __name__ == "__main__":
    unittest.main()
