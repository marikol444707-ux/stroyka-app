import copy
import inspect
import json
import unittest

from backend.features.supply_recommendation_preview import (
    material_capability_source_resolver as resolver,
)
from backend.features.estimate_revision_impact.contract import (
    EVENT_TYPE,
    MAX_CANONICAL_SOURCE_BYTES,
    REPORT_VERSION,
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.combined_contract import (
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.job_contract import (
    JOB_TYPE,
    build_estimate_revision_impact_job_plan,
)
from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    MAX_REQUEST_ITEMS,
)
from backend.features.supply_recommendation_preview.rfq_content import (
    MAX_REQUEST_JSON_BYTES,
)
from backend.features.supply_recommendation_preview.test_rfq_content import (
    request_item,
    target_sections,
    valid_report,
)


INPUT_INVALID = "supply_supplier_material_source_input_invalid"
NOT_FOUND = "supply_supplier_material_source_not_found"
SOURCE_INVALID = "supply_supplier_material_source_invalid"


class FakeCursor:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, tuple(params or ())))
        if not self.responses:
            raise AssertionError("resolver executed an unbounded extra query")
        self.current = self.responses.pop(0)

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        raise AssertionError("resolver must retain the LIMIT 2 ambiguity sentinel")


def _encoded(value):
    return json.dumps(value, ensure_ascii=False)


def request_row(*, items=None, **overrides):
    encoded = _encoded([request_item()] if items is None else items)
    row = {
        "request_id": 21,
        "request_company_id": 4,
        "request_project": "Private project",
        "request_work_package": "Основная",
        "request_status": "Утверждена",
        "project_id": 17,
        "project_company_id": 4,
        "project_name": "Private project",
        "items_json": encoded,
        "items_bytes": len(encoded.encode("utf-8")),
        "private_detail": "must-not-leak",
    }
    row.update(overrides)
    return row


def target_row(**overrides):
    encoded = _encoded(target_sections())
    row = {
        "reconciliation_id": 91,
        "reconciliation_status": "Черновик",
        "reconciliation_smeta_type": "Заказчик",
        "reconciliation_work_package": "Основная",
        "base_estimate_id": 51,
        "base_company_id": 4,
        "base_project_id": 17,
        "base_smeta_type": "Заказчик",
        "base_work_package": "Основная",
        "target_estimate_id": 52,
        "target_company_id": 4,
        "target_project_id": 17,
        "target_version": "v2.0",
        "target_sections_json": encoded,
        "target_sections_bytes": len(encoded.encode("utf-8")),
        "target_status": "Активная",
        "target_is_template": False,
        "target_smeta_type": "Заказчик",
        "target_work_package": "Основная",
        "private_detail": "must-not-leak",
    }
    row.update(overrides)
    return row


def exact_source():
    return build_estimate_revision_source(
        company_id=4,
        project_id=17,
        estimate_id=52,
        version="v2.0",
        sections=target_sections(),
    )


def source_payload():
    source = exact_source()
    return {
        "schemaVersion": REPORT_VERSION,
        "eventType": EVENT_TYPE,
        "companyId": source.company_id,
        "projectId": source.project_id,
        "estimateId": source.estimate_id,
        "sourceRevision": source.source_revision,
    }


def rehash(report):
    report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report


def job_row(**overrides):
    plan = build_estimate_revision_impact_job_plan(exact_source())
    row = {
        "id": 301,
        "owner_scope": "company",
        "company_id": 4,
        "project_id": 17,
        "project_scope_id": 17,
        "requested_by_user_id": None,
        "requested_by_role": "system",
        "job_type": JOB_TYPE,
        "idempotency_key": plan.idempotency_key,
        "correlation_id": plan.correlation_id,
        "payload_json": source_payload(),
        "result_json": valid_report(),
        "payload_bytes": 1024,
        "result_bytes": 4096,
        "status": "succeeded",
        "private_detail": "must-not-leak",
    }
    row.update(overrides)
    return row


def resolve(cursor, *, company_id=4, request_id=21, item_index=0):
    return resolver.resolve_material_capability_source(
        cursor,
        company_id=company_id,
        request_id=request_id,
        request_item_index=item_index,
    )


def assert_code(test_case, cursor, code, **selectors):
    with test_case.assertRaises(
        resolver.MaterialCapabilitySourceResolverError
    ) as raised:
        resolve(cursor, **selectors)
    test_case.assertEqual(raised.exception.code, code)
    test_case.assertEqual(str(raised.exception), code)


class MaterialCapabilitySourceResolverTests(unittest.TestCase):
    def test_public_api_accepts_only_server_owned_company_request_item_selectors(self):
        signature = inspect.signature(
            resolver.resolve_material_capability_source
        )
        self.assertEqual(list(signature.parameters), [
            "cur", "company_id", "request_id", "request_item_index",
        ])
        for name in ("company_id", "request_id", "request_item_index"):
            self.assertEqual(
                signature.parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )
        self.assertEqual(resolver.__all__, [
            "MaterialCapabilitySourceResolverError",
            "resolve_material_capability_source",
        ])

    def test_resolves_one_exact_server_report_with_three_bounded_keyed_reads(self):
        report = valid_report()
        cursor = FakeCursor((
            [request_row()],
            [target_row()],
            [job_row(result_json=report)],
        ))

        result = resolve(cursor)

        self.assertEqual(set(result), {"combinedReport", "selected"})
        self.assertEqual(result["combinedReport"], report)
        self.assertEqual(result["selected"], {
            "requestId": 21,
            "requestItemIndex": 0,
        })
        self.assertEqual(len(cursor.calls), 3)
        self.assertEqual(cursor.responses, [])

        request_sql, request_params = cursor.calls[0]
        target_sql, target_params = cursor.calls[1]
        job_sql, job_params = cursor.calls[2]
        lowered = [sql.lower() for sql, _params in cursor.calls]
        self.assertTrue(all(sql.startswith("select ") for sql in lowered))
        self.assertTrue(all("select *" not in sql for sql in lowered))
        self.assertTrue(all(" where " in sql for sql in lowered))
        self.assertTrue(all(" limit %s" in sql for sql in lowered))
        self.assertTrue(all(params[-1] == 2 for _sql, params in cursor.calls))

        self.assertIn("from public.supply_requests", request_sql.lower())
        self.assertIn("public.projects", request_sql.lower())
        self.assertIn("octet_length", request_sql.lower())
        self.assertIn(21, request_params)
        self.assertIn(4, request_params)
        self.assertIn(MAX_REQUEST_JSON_BYTES, request_params)

        self.assertIn(
            "from public.estimate_reconciliations",
            target_sql.lower(),
        )
        self.assertIn("public.estimates", target_sql.lower())
        self.assertIn("base_estimate_id", target_sql.lower())
        self.assertIn("octet_length", target_sql.lower())
        self.assertIn(51, target_params)
        self.assertIn(4, target_params)
        self.assertIn(17, target_params)
        self.assertIn(MAX_CANONICAL_SOURCE_BYTES, target_params)

        plan = build_estimate_revision_impact_job_plan(exact_source())
        self.assertIn("from public.agent_jobs", job_sql.lower())
        self.assertNotIn(" where id=%s", job_sql.lower())
        self.assertIn("company_id=%s", job_sql.lower())
        self.assertIn("project_scope_id=%s", job_sql.lower())
        self.assertIn("job_type=%s", job_sql.lower())
        self.assertIn("idempotency_key=%s", job_sql.lower())
        self.assertGreaterEqual(job_sql.lower().count("octet_length"), 4)
        self.assertIn("case", job_sql.lower())
        self.assertEqual(job_params, (
            resolver.MAX_JOB_PAYLOAD_BYTES,
            resolver.MAX_JOB_RESULT_BYTES,
            4, 17, JOB_TYPE, plan.idempotency_key, 2,
        ))
        serialized_sql = " ".join(lowered)
        self.assertNotIn("private project", serialized_sql)
        self.assertNotIn("must-not-leak", serialized_sql)

    def test_oversized_job_payload_or_result_fails_closed_before_decoding(self):
        cases = (
            job_row(
                payload_json=None,
                payload_bytes=resolver.MAX_JOB_PAYLOAD_BYTES + 1,
            ),
            job_row(
                result_json=None,
                result_bytes=resolver.MAX_JOB_RESULT_BYTES + 1,
            ),
            job_row(payload_bytes=None),
            job_row(result_bytes=True),
        )
        for row in cases:
            with self.subTest(row=row):
                cursor = FakeCursor((
                    [request_row()],
                    [target_row()],
                    [row],
                ))
                assert_code(self, cursor, SOURCE_INVALID)

    def test_rejects_non_exact_selectors_before_any_database_read(self):
        invalid_cases = (
            {"company_id": True},
            {"company_id": 0},
            {"company_id": "4"},
            {"request_id": False},
            {"request_id": -1},
            {"request_id": "21"},
            {"item_index": True},
            {"item_index": -1},
            {"item_index": "0"},
        )
        for selectors in invalid_cases:
            with self.subTest(selectors=selectors):
                cursor = FakeCursor()
                assert_code(
                    self, cursor, INPUT_INVALID, **selectors,
                )
                self.assertEqual(cursor.calls, [])

    def test_missing_and_foreign_request_are_one_non_disclosing_not_found(self):
        cursors = (
            FakeCursor(([],)),
            FakeCursor(([request_row(
                request_company_id=8,
                project_company_id=8,
                private_detail="foreign-company-secret",
            )],)),
        )
        for cursor in cursors:
            with self.subTest(responses=cursor.responses):
                assert_code(self, cursor, NOT_FOUND)
                self.assertEqual(len(cursor.calls), 1)

    def test_rejects_ambiguous_oversized_or_non_v2_request_item_lineage(self):
        two_sources = request_item()
        two_sources["estimateLineage"]["sources"].append(copy.deepcopy(
            two_sources["estimateLineage"]["sources"][0]
        ))
        wrong_company = request_item()
        wrong_company["estimateLineage"]["companyId"] = 8
        wrong_project = request_item()
        wrong_project["estimateLineage"]["projectId"] = 18
        wrong_package = request_item()
        wrong_package["estimateLineage"]["workPackage"] = "Другой"
        wrong_package["workPackage"] = "Другой"
        v1 = request_item()
        v1["estimateLineage"]["version"] = 1
        unvalidated = request_item()
        unvalidated["estimateLineage"]["validated"] = False
        bad_coordinate = request_item()
        bad_coordinate["estimateLineage"]["sources"][0][
            "sectionIndex"
        ] = -1
        cases = (
            [request_row(), request_row()],
            [request_row(items=[v1])],
            [request_row(items=[unvalidated])],
            [request_row(items=[wrong_company])],
            [request_row(items=[wrong_project])],
            [request_row(items=[wrong_package])],
            [request_row(items=[two_sources])],
            [request_row(items=[bad_coordinate])],
            [request_row(items=["not-an-item"])],
            [request_row(items=[])],
            [request_row(
                items_json=None,
                items_bytes=MAX_REQUEST_JSON_BYTES + 1,
            )],
            [request_row(items=[request_item()] * (MAX_REQUEST_ITEMS + 1))],
        )
        for rows in cases:
            with self.subTest(rows=len(rows)):
                cursor = FakeCursor((rows,))
                assert_code(self, cursor, SOURCE_INVALID)
                self.assertEqual(len(cursor.calls), 1)

        out_of_range = FakeCursor(([request_row()],))
        assert_code(self, out_of_range, SOURCE_INVALID, item_index=1)
        self.assertEqual(len(out_of_range.calls), 1)

    def test_rejects_non_current_ambiguous_or_cross_owner_target_reconciliation(self):
        invalid_rows = (
            [target_row(), target_row(reconciliation_id=92)],
            [target_row(base_estimate_id=50)],
            [target_row(base_company_id=8)],
            [target_row(base_project_id=18)],
            [target_row(target_company_id=8)],
            [target_row(target_project_id=18)],
            [target_row(target_status="Черновик")],
            [target_row(target_is_template=True)],
            [target_row(target_smeta_type="Исполнитель")],
            [target_row(target_work_package="Другой")],
            [target_row(reconciliation_work_package="Другой")],
            [target_row(reconciliation_smeta_type="Исполнитель")],
            [target_row(reconciliation_status="unknown")],
            [target_row(target_sections_json=None,
                        target_sections_bytes=MAX_CANONICAL_SOURCE_BYTES + 1)],
            [target_row(target_version="")],
            [target_row(target_sections_json="not-json")],
        )
        for rows in invalid_rows:
            with self.subTest(row=rows[0]):
                cursor = FakeCursor(([request_row()], rows))
                assert_code(self, cursor, SOURCE_INVALID)
                self.assertEqual(len(cursor.calls), 2)

        missing = FakeCursor(([request_row()], []))
        assert_code(self, missing, NOT_FOUND)
        self.assertEqual(len(missing.calls), 2)

    def test_requires_one_exact_system_owned_succeeded_job(self):
        invalid_jobs = (
            [job_row(), job_row(id=302)],
            [job_row(owner_scope="user")],
            [job_row(company_id=8)],
            [job_row(project_id=18)],
            [job_row(project_scope_id=18)],
            [job_row(requested_by_user_id=9)],
            [job_row(requested_by_role="директор")],
            [job_row(job_type="director.daily_brief")],
            [job_row(idempotency_key="revision-impact:" + "0" * 32)],
            [job_row(correlation_id="revision-impact:" + "0" * 32)],
            [job_row(status="queued")],
            [job_row(status="running")],
            [job_row(status="failed")],
            [job_row(status="cancelled")],
        )
        for rows in invalid_jobs:
            with self.subTest(row=rows[0]):
                cursor = FakeCursor((
                    [request_row()], [target_row()], rows,
                ))
                assert_code(self, cursor, SOURCE_INVALID)
                self.assertEqual(len(cursor.calls), 3)

        missing = FakeCursor((
            [request_row()], [target_row()], [],
        ))
        assert_code(self, missing, NOT_FOUND)
        self.assertEqual(len(missing.calls), 3)

    def test_strictly_revalidates_private_job_payload_and_combined_result(self):
        payload_extra = {**source_payload(), "jobId": 301}
        payload_drift = {
            **source_payload(),
            "sourceRevision": "sha256:" + "0" * 64,
        }
        result_hash_drift = {
            **valid_report(),
            "evidenceSha256": "0" * 64,
        }
        result_extra = {**valid_report(), "private": "must-not-leak"}
        result_source_drift = copy.deepcopy(valid_report())
        result_source_drift["source"]["companyId"] = 8
        result_source_drift = rehash(result_source_drift)
        result_reconciliation_drift = copy.deepcopy(valid_report())
        result_reconciliation_drift["source"]["reconciliationId"] = 92
        result_reconciliation_drift = rehash(result_reconciliation_drift)
        result_base_drift = copy.deepcopy(valid_report())
        result_base_drift["source"]["baseEstimateId"] = 50
        result_base_drift = rehash(result_base_drift)
        result_status_drift = copy.deepcopy(valid_report())
        result_status_drift["source"]["reconciliationStatus"] = "Утверждена"
        result_status_drift = rehash(result_status_drift)
        result_request_drift = copy.deepcopy(valid_report())
        result_request_drift["domains"]["supply"]["openSupply"][0][
            "requestId"
        ] = 22
        result_request_drift = rehash(result_request_drift)
        result_item_drift = copy.deepcopy(valid_report())
        result_item_drift["domains"]["supply"]["openSupply"][0][
            "requestItemIndex"
        ] = 1
        result_item_drift = rehash(result_item_drift)
        result_lineage_drift = copy.deepcopy(valid_report())
        result_lineage_drift["domains"]["supply"]["openSupply"][0][
            "sourceEstimateId"
        ] = 50
        result_lineage_drift = rehash(result_lineage_drift)
        invalid_jobs = (
            job_row(payload_json=payload_extra),
            job_row(payload_json=payload_drift),
            job_row(payload_json={}),
            job_row(result_json=result_hash_drift),
            job_row(result_json=result_extra),
            job_row(result_json=result_source_drift),
            job_row(result_json=result_reconciliation_drift),
            job_row(result_json=result_base_drift),
            job_row(result_json=result_status_drift),
            job_row(result_json=result_request_drift),
            job_row(result_json=result_item_drift),
            job_row(result_json=result_lineage_drift),
            job_row(result_json={}),
        )
        for row in invalid_jobs:
            with self.subTest(row=row):
                cursor = FakeCursor((
                    [request_row()], [target_row()], [row],
                ))
                assert_code(self, cursor, SOURCE_INVALID)
                self.assertEqual(len(cursor.calls), 3)


if __name__ == "__main__":
    unittest.main()
