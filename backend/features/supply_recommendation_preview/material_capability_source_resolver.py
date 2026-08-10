"""Bounded server-owned A7 source resolution for one supply request item."""

import copy
import json
from collections.abc import Mapping

from backend.features.estimate_revision_impact.baseline import (
    KNOWN_RECONCILIATION_STATUSES,
)
from backend.features.estimate_revision_impact.contract import (
    MAX_CANONICAL_SOURCE_BYTES,
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.handler import (
    validate_estimate_revision_impact_result,
)
from backend.features.estimate_revision_impact.job_contract import (
    JOB_TYPE,
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)
from backend.features.estimate_revision_impact.supply_warehouse_projection import (
    MAX_REQUEST_ITEMS,
)
from backend.features.supply_recommendation_preview.rfq_content import (
    MAX_REQUEST_JSON_BYTES,
    prepare_supply_rfq_content,
)


_INPUT_INVALID = "supply_supplier_material_source_input_invalid"
_NOT_FOUND = "supply_supplier_material_source_not_found"
_SOURCE_INVALID = "supply_supplier_material_source_invalid"
_ERROR_CODES = frozenset({_INPUT_INVALID, _NOT_FOUND, _SOURCE_INVALID})
_MAX_PROJECT_TEXT = 1000
_MAX_PACKAGE_TEXT = 100
_MAX_MATERIAL_TEXT = 1000
_MAX_UNIT_TEXT = 100


class MaterialCapabilitySourceResolverError(ValueError):
    """Fixed resolver error that never includes tenant business content."""

    def __init__(self, code):
        code = code if code in _ERROR_CODES else _SOURCE_INVALID
        self.code = code
        super().__init__(code)


def _fail(code):
    raise MaterialCapabilitySourceResolverError(code)


def _positive_int(value):
    return type(value) is int and value > 0


def _non_negative_int(value):
    return type(value) is int and value >= 0


def _text(value, limit):
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > limit
    ):
        return None
    return value


def _package(value):
    value = "Основная" if value in (None, "") else value
    return _text(value, _MAX_PACKAGE_TEXT)


def _decoded_object(value):
    if type(value) is dict:
        return copy.deepcopy(value)
    if type(value) is str:
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            return None
        return decoded if type(decoded) is dict else None
    return None


def _decoded_list(value):
    if type(value) is list:
        return copy.deepcopy(value)
    if type(value) is str:
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            return None
        return decoded if type(decoded) is list else None
    return None


def _rows(cur):
    try:
        return [dict(row or {}) for row in (cur.fetchall() or [])]
    except Exception:
        _fail(_SOURCE_INVALID)


def _load_request(cur, company_id, request_id):
    cur.execute(
        """SELECT request.id AS request_id,
                  request.company_id AS request_company_id,
                  request.project AS request_project,
                  COALESCE(NULLIF(request.work_package,''),'Основная')
                      AS request_work_package,
                  COALESCE(request.status,'') AS request_status,
                  project.id AS project_id,
                  project.company_id AS project_company_id,
                  project.name AS project_name,
                  CASE
                    WHEN octet_length(COALESCE(request.items_json,'')) <= %s
                    THEN request.items_json
                    ELSE NULL
                  END AS items_json,
                  octet_length(COALESCE(request.items_json,'')) AS items_bytes
             FROM public.supply_requests request
             JOIN public.projects project
               ON project.company_id=request.company_id
              AND project.name=request.project
            WHERE request.id=%s AND request.company_id=%s
            ORDER BY project.id
            LIMIT %s""",
        (MAX_REQUEST_JSON_BYTES, request_id, company_id, 2),
    )
    return _rows(cur)


def _request_lineage(rows, company_id, request_id, request_item_index):
    if not rows:
        _fail(_NOT_FOUND)
    if len(rows) != 1:
        _fail(_SOURCE_INVALID)
    row = rows[0]
    if (
        not _positive_int(row.get("request_id"))
        or row.get("request_id") != request_id
        or row.get("request_company_id") != company_id
        or row.get("project_company_id") != company_id
    ):
        _fail(_NOT_FOUND)
    project_id = row.get("project_id")
    project_name = _text(row.get("project_name"), _MAX_PROJECT_TEXT)
    request_project = _text(row.get("request_project"), _MAX_PROJECT_TEXT)
    work_package = _package(row.get("request_work_package"))
    size = row.get("items_bytes")
    if (
        not _positive_int(project_id)
        or project_name is None
        or request_project != project_name
        or work_package is None
        or type(size) is not int
        or size < 0
        or size > MAX_REQUEST_JSON_BYTES
        or row.get("items_json") is None
    ):
        _fail(_SOURCE_INVALID)
    items = _decoded_list(row.get("items_json"))
    if (
        items is None
        or len(items) > MAX_REQUEST_ITEMS
        or request_item_index >= len(items)
        or type(items[request_item_index]) is not dict
    ):
        _fail(_SOURCE_INVALID)
    item = items[request_item_index]
    lineage = item.get("estimateLineage")
    if type(lineage) is not dict:
        _fail(_SOURCE_INVALID)
    sources = lineage.get("sources")
    item_package = _package(item.get("workPackage"))
    if (
        item.get("sourceType") != "estimate_material_control"
        or item_package != work_package
        or type(lineage.get("version")) is not int
        or lineage.get("version") != 2
        or lineage.get("validated") is not True
        or lineage.get("companyId") != company_id
        or lineage.get("projectId") != project_id
        or lineage.get("projectName") != project_name
        or _package(lineage.get("workPackage")) != work_package
        or type(sources) is not list
        or len(sources) != 1
        or type(sources[0]) is not dict
    ):
        _fail(_SOURCE_INVALID)
    source = sources[0]
    material_name = _text(
        item.get("materialName") or item.get("name"), _MAX_MATERIAL_TEXT,
    )
    unit = _text(item.get("unit"), _MAX_UNIT_TEXT)
    if (
        source.get("validated") is not True
        or not _positive_int(source.get("estimateId"))
        or not _non_negative_int(source.get("sectionIndex"))
        or not _non_negative_int(source.get("itemIndex"))
        or material_name is None
        or unit is None
        or _text(source.get("materialName"), _MAX_MATERIAL_TEXT)
        != material_name
        or _text(source.get("unit"), _MAX_UNIT_TEXT) != unit
    ):
        _fail(_SOURCE_INVALID)
    return {
        "projectId": project_id,
        "workPackage": work_package,
        "baseEstimateId": source["estimateId"],
        "sourceSectionIndex": source["sectionIndex"],
        "sourceItemIndex": source["itemIndex"],
    }


def _load_target(cur, company_id, lineage):
    cur.execute(
        """SELECT reconciliation.id AS reconciliation_id,
                  reconciliation.status AS reconciliation_status,
                  COALESCE(reconciliation.smeta_type,'Заказчик')
                      AS reconciliation_smeta_type,
                  COALESCE(NULLIF(reconciliation.work_package,''),'Основная')
                      AS reconciliation_work_package,
                  base.id AS base_estimate_id,
                  base.company_id AS base_company_id,
                  base.project_id AS base_project_id,
                  COALESCE(base.smeta_type,'Заказчик') AS base_smeta_type,
                  COALESCE(NULLIF(base.work_package,''),'Основная')
                      AS base_work_package,
                  target.id AS target_estimate_id,
                  target.company_id AS target_company_id,
                  target.project_id AS target_project_id,
                  target.version AS target_version,
                  CASE
                    WHEN octet_length(COALESCE(target.sections_json::text,''))
                         <= %s
                    THEN target.sections_json
                    ELSE NULL
                  END AS target_sections_json,
                  octet_length(COALESCE(target.sections_json::text,''))
                      AS target_sections_bytes,
                  COALESCE(target.status,'Черновик') AS target_status,
                  COALESCE(target.is_template,FALSE) AS target_is_template,
                  COALESCE(target.smeta_type,'Заказчик') AS target_smeta_type,
                  COALESCE(NULLIF(target.work_package,''),'Основная')
                      AS target_work_package
             FROM public.estimate_reconciliations reconciliation
             JOIN public.estimates base
               ON base.id=reconciliation.base_estimate_id
             JOIN public.estimates target
               ON target.id=reconciliation.next_estimate_id
            WHERE reconciliation.base_estimate_id=%s
              AND base.company_id=%s AND base.project_id=%s
              AND target.company_id=%s AND target.project_id=%s
            ORDER BY reconciliation.id DESC
            LIMIT %s""",
        (
            MAX_CANONICAL_SOURCE_BYTES,
            lineage["baseEstimateId"],
            company_id,
            lineage["projectId"],
            company_id,
            lineage["projectId"],
            2,
        ),
    )
    return _rows(cur)


def _target_source(rows, company_id, lineage):
    if not rows:
        _fail(_NOT_FOUND)
    if len(rows) != 1:
        _fail(_SOURCE_INVALID)
    row = rows[0]
    target_id = row.get("target_estimate_id")
    sections_size = row.get("target_sections_bytes")
    packages = {
        _package(row.get("reconciliation_work_package")),
        _package(row.get("base_work_package")),
        _package(row.get("target_work_package")),
        lineage["workPackage"],
    }
    if (
        not _positive_int(row.get("reconciliation_id"))
        or row.get("reconciliation_status")
        not in KNOWN_RECONCILIATION_STATUSES
        or row.get("reconciliation_smeta_type") != "Заказчик"
        or row.get("base_estimate_id") != lineage["baseEstimateId"]
        or row.get("base_company_id") != company_id
        or row.get("base_project_id") != lineage["projectId"]
        or row.get("base_smeta_type") != "Заказчик"
        or not _positive_int(target_id)
        or target_id == lineage["baseEstimateId"]
        or row.get("target_company_id") != company_id
        or row.get("target_project_id") != lineage["projectId"]
        or row.get("target_status") != "Активная"
        or row.get("target_is_template") is not False
        or row.get("target_smeta_type") != "Заказчик"
        or None in packages
        or len(packages) != 1
        or type(sections_size) is not int
        or sections_size < 0
        or sections_size > MAX_CANONICAL_SOURCE_BYTES
        or row.get("target_sections_json") is None
    ):
        _fail(_SOURCE_INVALID)
    sections = _decoded_list(row.get("target_sections_json"))
    if sections is None:
        _fail(_SOURCE_INVALID)
    try:
        source = build_estimate_revision_source(
            company_id=company_id,
            project_id=lineage["projectId"],
            estimate_id=target_id,
            version=row.get("target_version"),
            sections=sections,
        )
        return source, {
            "reconciliationId": row["reconciliation_id"],
            "baseEstimateId": row["base_estimate_id"],
            "reconciliationStatus": row["reconciliation_status"],
        }
    except Exception:
        _fail(_SOURCE_INVALID)


def _load_job(cur, source):
    plan = build_estimate_revision_impact_job_plan(source)
    cur.execute(
        """SELECT id,owner_scope,company_id,project_id,project_scope_id,
                  requested_by_user_id,requested_by_role,job_type,
                  idempotency_key,correlation_id,payload_json,result_json,status
             FROM public.agent_jobs
            WHERE company_id=%s AND project_scope_id=%s
              AND job_type=%s AND idempotency_key=%s
            ORDER BY id
            LIMIT %s""",
        (
            plan.company_id,
            plan.project_id,
            plan.job_type,
            plan.idempotency_key,
            2,
        ),
    )
    return plan, _rows(cur)


def _validated_report(plan, source, source_details, lineage, selected, rows):
    if not rows:
        _fail(_NOT_FOUND)
    if len(rows) != 1:
        _fail(_SOURCE_INVALID)
    row = rows[0]
    if (
        not _positive_int(row.get("id"))
        or row.get("owner_scope") != "company"
        or row.get("company_id") != plan.company_id
        or row.get("project_id") != plan.project_id
        or row.get("project_scope_id") != plan.project_id
        or row.get("requested_by_user_id") is not None
        or row.get("requested_by_role") != plan.requested_by_role
        or row.get("job_type") != JOB_TYPE
        or row.get("idempotency_key") != plan.idempotency_key
        or row.get("correlation_id") != plan.correlation_id
        or row.get("status") != "succeeded"
    ):
        _fail(_SOURCE_INVALID)
    payload = _decoded_object(row.get("payload_json"))
    report = _decoded_object(row.get("result_json"))
    if payload is None or report is None:
        _fail(_SOURCE_INVALID)
    try:
        payload_source = source_from_job_payload(payload)
        if payload_source != source or payload != dict(plan.payload):
            _fail(_SOURCE_INVALID)
        validated = validate_estimate_revision_impact_result(report, source)
        report_source = validated.get("source")
        if (
            not isinstance(report_source, Mapping)
            or any(
                report_source.get(field) != expected
                for field, expected in source_details.items()
            )
        ):
            _fail(_SOURCE_INVALID)
        prepared = prepare_supply_rfq_content(validated, selected)
        candidate = prepared.get("candidate")
        if (
            not isinstance(candidate, Mapping)
            or candidate.get("requestId") != selected["requestId"]
            or candidate.get("requestItemIndex")
            != selected["requestItemIndex"]
            or candidate.get("base") != {
                "estimateId": lineage["baseEstimateId"],
                "sectionIndex": lineage["sourceSectionIndex"],
                "itemIndex": lineage["sourceItemIndex"],
            }
            or candidate.get("target", {}).get("estimateId")
            != source.estimate_id
        ):
            _fail(_SOURCE_INVALID)
        return validated
    except MaterialCapabilitySourceResolverError:
        raise
    except Exception:
        _fail(_SOURCE_INVALID)


def resolve_material_capability_source(
    cur,
    *,
    company_id,
    request_id,
    request_item_index,
):
    """Return one strict stored A7 report and exact supply selection."""

    if (
        not _positive_int(company_id)
        or not _positive_int(request_id)
        or not _non_negative_int(request_item_index)
    ):
        _fail(_INPUT_INVALID)
    try:
        lineage = _request_lineage(
            _load_request(cur, company_id, request_id),
            company_id,
            request_id,
            request_item_index,
        )
        source, source_details = _target_source(
            _load_target(cur, company_id, lineage), company_id, lineage,
        )
        plan, jobs = _load_job(cur, source)
        selected = {
            "requestId": request_id,
            "requestItemIndex": request_item_index,
        }
        report = _validated_report(
            plan, source, source_details, lineage, selected, jobs,
        )
        return {
            "combinedReport": copy.deepcopy(report),
            "selected": selected,
        }
    except MaterialCapabilitySourceResolverError:
        raise
    except (KeyboardInterrupt, SystemExit, GeneratorExit):
        raise
    except Exception:
        _fail(_SOURCE_INVALID)


__all__ = [
    "MaterialCapabilitySourceResolverError",
    "resolve_material_capability_source",
]
