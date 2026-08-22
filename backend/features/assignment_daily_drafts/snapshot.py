"""One bounded read-only snapshot for assignment and confirmed daily work."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import psycopg2.extras

from backend.features.brigade_lineage.canonical import (
    parse_sections,
    sections_sha256,
)

from .assignment_projection import (
    MAX_ASSIGNMENT_DRAFT_ROWS,
    AssignmentDraft,
    AssignmentDraftScope,
    AssignmentDraftSummary,
    build_assignment_draft,
)
from .projection import (
    MAX_DAILY_WORK_ROWS,
    AssignmentDailyDraftScope,
    DailyWorkDraft,
    DailyWorkDraftSummary,
    _positive_int,
    build_daily_work_draft,
)


MAX_SNAPSHOT_JSON_BYTES = 4 * 1024 * 1024
MAX_SNAPSHOT_QUERY_JSON_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_TEXT_QUERY_BYTES = 1024 * 1024

_CONTROL_FLOW = (KeyboardInterrupt, SystemExit, GeneratorExit)
_INPUT_INVALID = "assignment_daily_snapshot_input_invalid"
_CONTRACT_INVALID = "assignment_daily_snapshot_contract_invalid"
_READ_FAILED = "assignment_daily_snapshot_read_failed"
_ROLLBACK_FAILED = "assignment_daily_snapshot_rollback_failed"
_CLEANUP_FAILED = "assignment_daily_snapshot_cleanup_failed"
_SOURCE_NOT_FOUND = "assignment_snapshot_source_not_found"
_SOURCE_AMBIGUOUS = "assignment_snapshot_source_ambiguous"
_PAYLOAD_TOO_LARGE = "assignment_snapshot_payload_too_large"
_PROJECT_AMBIGUOUS = "assignment_snapshot_project_ambiguous"
_VERSION_STALE = "assignment_snapshot_version_stale"
_SOURCE_INVALID = "assignment_snapshot_source_invalid"
_LINEAGE_INVALID = "assignment_snapshot_lineage_invalid"
_ASSIGNMENT_SCAN_LIMIT = "assignment_draft_scan_limit_exceeded"
_DAILY_SCAN_LIMIT = "daily_work_scan_limit_exceeded"


class AssignmentDailySnapshotError(ValueError):
    """Fixed private error for malformed input, metadata or DB lifecycle."""


def _fail(code):
    raise AssignmentDailySnapshotError(code) from None


@dataclass(frozen=True)
class AssignmentDailySnapshotRequest:
    company_id: int
    project_id: int
    date: str
    estimate_id: int
    estimate_version_id: int
    work_package: str

    def __post_init__(self):
        try:
            daily_scope = AssignmentDailyDraftScope(
                self.company_id,
                self.project_id,
                self.date,
            )
            assignment_scope = AssignmentDraftScope(
                self.company_id,
                self.project_id,
                self.estimate_id,
                self.estimate_version_id,
                self.work_package,
            )
        except (TypeError, ValueError):
            _fail(_INPUT_INVALID)
        if (
            daily_scope.company_id != assignment_scope.company_id
            or daily_scope.project_id != assignment_scope.project_id
        ):
            _fail(_INPUT_INVALID)


@dataclass(frozen=True)
class AssignmentDailySnapshot:
    request: AssignmentDailySnapshotRequest
    state: str
    assignment_draft: AssignmentDraft
    daily_work_draft: DailyWorkDraft
    review_codes: tuple


def _assignment_scope(request):
    return AssignmentDraftScope(
        request.company_id,
        request.project_id,
        request.estimate_id,
        request.estimate_version_id,
        request.work_package,
    )


def _daily_scope(request):
    return AssignmentDailyDraftScope(
        request.company_id,
        request.project_id,
        request.date,
    )


def _empty_assignment(request, state="clear", reviews=()):
    return AssignmentDraft(
        scope=_assignment_scope(request),
        state=state,
        items=(),
        summary=AssignmentDraftSummary(0, 0, 0),
        review_codes=tuple(reviews),
    )


def _empty_daily(request, state="clear", reviews=()):
    return DailyWorkDraft(
        scope=_daily_scope(request),
        state=state,
        items=(),
        summary=DailyWorkDraftSummary(0, 0, 0),
        review_codes=tuple(reviews),
    )


def _snapshot(request, assignment, daily, extra_reviews=()):
    reviews = tuple(dict.fromkeys(
        tuple(extra_reviews)
        + tuple(assignment.review_codes)
        + tuple(daily.review_codes)
    ))
    if reviews or "review_required" in (assignment.state, daily.state):
        state = "review_required"
    elif "ready" in (assignment.state, daily.state):
        state = "ready"
    else:
        state = "clear"
    return AssignmentDailySnapshot(
        request=request,
        state=state,
        assignment_draft=assignment,
        daily_work_draft=daily,
        review_codes=reviews,
    )


def _review_snapshot(request, code, *, assignment_code=None, daily_code=None):
    assignment = _empty_assignment(
        request,
        "review_required" if assignment_code else "clear",
        (assignment_code,) if assignment_code else (),
    )
    daily = _empty_daily(
        request,
        "review_required" if daily_code else "clear",
        (daily_code,) if daily_code else (),
    )
    return _snapshot(request, assignment, daily, (code,))


def _exact_int(value, *, minimum=0):
    return value if type(value) is int and value >= minimum else None


def _exact_bool(value):
    return value if type(value) is bool else None


def _utf8_bytes(value):
    if value is None:
        return 0
    if type(value) is not str:
        _fail(_CONTRACT_INVALID)
    try:
        return len(value.encode("utf-8"))
    except UnicodeError:
        _fail(_CONTRACT_INVALID)


def _rows(cur):
    rows = cur.fetchall() or []
    if type(rows) not in (list, tuple):
        _fail(_CONTRACT_INVALID)
    detached = []
    for row in rows:
        if not isinstance(row, Mapping):
            _fail(_CONTRACT_INVALID)
        detached.append(dict(row))
    return detached


def _validate_gate_rows(
    rows,
    *,
    variable_fields,
    field_caps,
    total_field,
    total_cap,
    row_limit,
):
    if len(rows) > row_limit + 1:
        _fail(_CONTRACT_INVALID)
    if not rows:
        return "empty"
    expected_count = rows[0].get("row_count")
    expected_total = rows[0].get(total_field)
    if (
        _exact_int(expected_count, minimum=0) is None
        or _exact_int(expected_total, minimum=0) is None
        or expected_count != len(rows)
    ):
        _fail(_CONTRACT_INVALID)
    cardinality = expected_count > row_limit
    field_sum = 0
    field_overflow = False
    first_cardinality = None
    first_payload = None
    for row in rows:
        card_flag = _exact_bool(row.get("cardinality_limit_exceeded"))
        payload_flag = _exact_bool(row.get("payload_limit_exceeded"))
        if card_flag is None or payload_flag is None:
            _fail(_CONTRACT_INVALID)
        if first_cardinality is None:
            first_cardinality = card_flag
            first_payload = payload_flag
        if (
            row.get("row_count") != expected_count
            or row.get(total_field) != expected_total
            or card_flag != first_cardinality
            or payload_flag != first_payload
        ):
            _fail(_CONTRACT_INVALID)
        for field in variable_fields:
            count_name = "field_" + field + "_bytes"
            field_bytes = row.get(count_name)
            if _exact_int(field_bytes, minimum=0) is None:
                _fail(_CONTRACT_INVALID)
            field_sum += field_bytes
            if field_bytes > field_caps[field]:
                field_overflow = True
        denied = card_flag or payload_flag
        for field in variable_fields:
            if denied:
                if row.get(field) is not None:
                    _fail(_CONTRACT_INVALID)
            elif _utf8_bytes(
                str(row.get(field)) if field.endswith("quantity")
                and row.get(field) is not None else row.get(field)
            ) != row["field_" + field + "_bytes"]:
                _fail(_CONTRACT_INVALID)
    if field_sum != expected_total:
        _fail(_CONTRACT_INVALID)
    if first_cardinality is not cardinality:
        _fail(_CONTRACT_INVALID)
    overflow = field_overflow or expected_total > total_cap
    if first_payload is not (not cardinality and overflow):
        _fail(_CONTRACT_INVALID)
    if cardinality:
        return "cardinality"
    if first_payload:
        return "overflow"
    return "accepted"


def _load_context(cur, request):
    cur.execute(
        """SELECT bounded.estimate_id,bounded.company_id,bounded.project_id,
                  bounded.project_name,bounded.project_name_count,
                  bounded.estimate_version_id,bounded.estimate_status,
                  bounded.is_template,bounded.work_package,
                  bounded.active_sections_json,bounded.version_sections_json,
                  bounded.field_active_sections_json_bytes,
                  bounded.field_version_sections_json_bytes,
                  bounded.query_json_bytes,bounded.row_count,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT e.id AS estimate_id,e.company_id,e.project_id,
                        p.name AS project_name,
                        (SELECT COUNT(*) FROM public.projects sibling
                          WHERE sibling.company_id=e.company_id
                            AND sibling.name=p.name) AS project_name_count,
                        ev.id AS estimate_version_id,e.status AS estimate_status,
                        e.is_template,
                        COALESCE(NULLIF(e.work_package,''),'Основная')
                            AS work_package,
                        e.sections_json::text AS emitted_active_sections_json,
                        ev.sections_json::text AS emitted_version_sections_json
                   FROM public.estimates e
                   JOIN public.projects p
                     ON p.id=e.project_id AND p.company_id=e.company_id
                   JOIN public.estimate_versions ev
                     ON ev.estimate_id=e.id AND ev.id=%s
                  WHERE e.company_id=%s AND e.project_id=%s AND e.id=%s
                    AND e.status='Активная'
                    AND COALESCE(e.is_template,FALSE)=FALSE
                    AND COALESCE(NULLIF(e.work_package,''),'Основная')=%s
                  ORDER BY e.id,ev.id LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                          emitted_active_sections_json,'UTF8')),0)::bigint
                            AS field_active_sections_json_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_version_sections_json,'UTF8')),0)::bigint
                            AS field_version_sections_json_bytes,
                        COUNT(*) OVER ()::bigint AS row_count
                   FROM limited
               ), totaled AS MATERIALIZED (
                 SELECT sized.*,
                        SUM(field_active_sections_json_bytes
                            + field_version_sections_json_bytes)
                          OVER ()::bigint AS query_json_bytes
                   FROM sized
               ), decided AS MATERIALIZED (
                 SELECT totaled.*,
                        (field_active_sections_json_bytes <= %s
                         AND field_version_sections_json_bytes <= %s
                         AND query_json_bytes <= %s) AS bytes_allowed
                   FROM totaled
               )
               SELECT estimate_id,company_id,project_id,project_name,
                      project_name_count,estimate_version_id,estimate_status,
                      is_template,work_package,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_active_sections_json END
                          AS active_sections_json,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_version_sections_json END
                          AS version_sections_json,
                      field_active_sections_json_bytes,
                      field_version_sections_json_bytes,query_json_bytes,
                      row_count,row_count > %s AS cardinality_limit_exceeded,
                      row_count <= %s AND NOT bytes_allowed
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.estimate_id,bounded.estimate_version_id""",
        (
            request.estimate_version_id,
            request.company_id,
            request.project_id,
            request.estimate_id,
            request.work_package,
            2,
            MAX_SNAPSHOT_JSON_BYTES,
            MAX_SNAPSHOT_JSON_BYTES,
            MAX_SNAPSHOT_QUERY_JSON_BYTES,
            1, 1, 1, 1,
        ),
    )
    rows = _rows(cur)
    state = _validate_gate_rows(
        rows,
        variable_fields=("active_sections_json", "version_sections_json"),
        field_caps={
            "active_sections_json": MAX_SNAPSHOT_JSON_BYTES,
            "version_sections_json": MAX_SNAPSHOT_JSON_BYTES,
        },
        total_field="query_json_bytes",
        total_cap=MAX_SNAPSHOT_QUERY_JSON_BYTES,
        row_limit=1,
    )
    return state, rows


def _load_assignments(cur, request):
    cur.execute(
        """SELECT bounded.company_id,bounded.project_id,bounded.estimate_id,
                  bounded.estimate_version_id,bounded.work_package,
                  bounded.source_type,bounded.section_index,bounded.item_index,
                  bounded.item_key,bounded.assigned_quantity,
                  bounded.field_item_key_bytes,
                  bounded.field_assigned_quantity_bytes,
                  bounded.query_text_bytes,bounded.row_count,
                  bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH grouped AS MATERIALIZED (
                 SELECT bc.company_id,bc.project_id,ev.estimate_id,
                        bci.source_estimate_version_id AS estimate_version_id,
                        COALESCE(NULLIF(bci.work_package,''),'Основная')
                          AS work_package,
                        bci.source_type,
                        bci.source_section_index AS section_index,
                        bci.source_item_index AS item_index,
                        bci.source_item_key AS emitted_item_key,
                        SUM(bci.quantity::numeric) AS emitted_assigned_quantity
                   FROM public.brigade_contract_items bci
                   JOIN public.brigade_contracts bc ON bc.id=bci.contract_id
                   JOIN public.estimate_versions ev
                     ON ev.id=bci.source_estimate_version_id
                  WHERE bc.company_id=%s AND bc.project_id=%s
                    AND ev.estimate_id=%s
                    AND bci.source_estimate_version_id=%s
                    AND bci.source_type='estimate'
                    AND COALESCE(NULLIF(bc.work_package,''),'Основная')=%s
                    AND COALESCE(NULLIF(bci.work_package,''),'Основная')=%s
                    AND COALESCE(bc.status,'') NOT IN
                        ('Аннулирован','Удалён','Удален')
                    AND COALESCE(bci.status,'') NOT IN
                        ('Аннулирован','Удалён','Удален')
                  GROUP BY bc.company_id,bc.project_id,ev.estimate_id,
                           bci.source_estimate_version_id,
                           COALESCE(NULLIF(bci.work_package,''),'Основная'),
                           bci.source_type,bci.source_section_index,
                           bci.source_item_index,bci.source_item_key
               ), limited AS MATERIALIZED (
                 SELECT * FROM grouped
                  ORDER BY section_index,item_index,emitted_item_key LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                          emitted_item_key,'UTF8')),0)::bigint
                            AS field_item_key_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_assigned_quantity::text,'UTF8')),0)::bigint
                            AS field_assigned_quantity_bytes,
                        COUNT(*) OVER ()::bigint AS row_count
                   FROM limited
               ), totaled AS MATERIALIZED (
                 SELECT sized.*,
                        SUM(field_item_key_bytes
                            + field_assigned_quantity_bytes)
                          OVER ()::bigint AS query_text_bytes
                   FROM sized
               ), decided AS MATERIALIZED (
                 SELECT totaled.*,
                        (field_item_key_bytes <= %s
                         AND field_assigned_quantity_bytes <= %s
                         AND query_text_bytes <= %s) AS bytes_allowed
                   FROM totaled
               )
               SELECT company_id,project_id,estimate_id,estimate_version_id,
                      work_package,source_type,section_index,item_index,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_item_key END AS item_key,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_assigned_quantity END
                          AS assigned_quantity,
                      field_item_key_bytes,field_assigned_quantity_bytes,
                      query_text_bytes,row_count,
                      row_count > %s AS cardinality_limit_exceeded,
                      row_count <= %s AND NOT bytes_allowed
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded
            ORDER BY bounded.section_index,bounded.item_index,bounded.item_key""",
        (
            request.company_id,
            request.project_id,
            request.estimate_id,
            request.estimate_version_id,
            request.work_package,
            request.work_package,
            MAX_ASSIGNMENT_DRAFT_ROWS + 1,
            512,
            64,
            MAX_SNAPSHOT_TEXT_QUERY_BYTES,
            MAX_ASSIGNMENT_DRAFT_ROWS,
            MAX_ASSIGNMENT_DRAFT_ROWS,
            MAX_ASSIGNMENT_DRAFT_ROWS,
            MAX_ASSIGNMENT_DRAFT_ROWS,
        ),
    )
    rows = _rows(cur)
    state = _validate_gate_rows(
        rows,
        variable_fields=("item_key", "assigned_quantity"),
        field_caps={"item_key": 512, "assigned_quantity": 64},
        total_field="query_text_bytes",
        total_cap=MAX_SNAPSHOT_TEXT_QUERY_BYTES,
        row_limit=MAX_ASSIGNMENT_DRAFT_ROWS,
    )
    return state, rows


def _load_daily(cur, request):
    cur.execute(
        """SELECT bounded.id,bounded.company_id,bounded.project_id,
                  bounded.date,bounded.status,bounded.description,bounded.unit,
                  bounded.quantity,bounded.master_id,bounded.master_name,
                  bounded.work_package,bounded.field_description_bytes,
                  bounded.field_unit_bytes,bounded.field_quantity_bytes,
                  bounded.field_master_name_bytes,
                  bounded.field_work_package_bytes,bounded.query_text_bytes,
                  bounded.row_count,bounded.cardinality_limit_exceeded,
                  bounded.payload_limit_exceeded
             FROM (
               WITH limited AS MATERIALIZED (
                 SELECT wj.id,wj.company_id,p.id AS project_id,wj.date,wj.status,
                        wj.description AS emitted_description,
                        wj.unit AS emitted_unit,
                        wj.quantity::numeric AS emitted_quantity,
                        wj.master_id,wj.master_name AS emitted_master_name,
                        COALESCE(NULLIF(wj.work_package,''),'Основная')
                          AS emitted_work_package
                   FROM public.work_journal wj
                   JOIN public.projects p
                     ON p.id=%s AND p.company_id=%s AND p.name=wj.project
                  WHERE wj.company_id=%s AND wj.date=%s
                    AND wj.status='Подтверждено'
                  ORDER BY wj.id LIMIT %s
               ), sized AS MATERIALIZED (
                 SELECT limited.*,
                        COALESCE(octet_length(convert_to(
                          emitted_description,'UTF8')),0)::bigint
                            AS field_description_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_unit,'UTF8')),0)::bigint AS field_unit_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_quantity::text,'UTF8')),0)::bigint
                            AS field_quantity_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_master_name,'UTF8')),0)::bigint
                            AS field_master_name_bytes,
                        COALESCE(octet_length(convert_to(
                          emitted_work_package,'UTF8')),0)::bigint
                            AS field_work_package_bytes,
                        COUNT(*) OVER ()::bigint AS row_count
                   FROM limited
               ), totaled AS MATERIALIZED (
                 SELECT sized.*,
                        SUM(field_description_bytes+field_unit_bytes
                            +field_quantity_bytes+field_master_name_bytes
                            +field_work_package_bytes)
                          OVER ()::bigint AS query_text_bytes
                   FROM sized
               ), decided AS MATERIALIZED (
                 SELECT totaled.*,
                        (field_description_bytes <= %s
                         AND field_unit_bytes <= %s
                         AND field_quantity_bytes <= %s
                         AND field_master_name_bytes <= %s
                         AND field_work_package_bytes <= %s
                         AND query_text_bytes <= %s) AS bytes_allowed
                   FROM totaled
               )
               SELECT id,company_id,project_id,date,status,master_id,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_description END AS description,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_unit END AS unit,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_quantity END AS quantity,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_master_name END AS master_name,
                      CASE WHEN row_count <= %s AND bytes_allowed
                           THEN emitted_work_package END AS work_package,
                      field_description_bytes,field_unit_bytes,
                      field_quantity_bytes,field_master_name_bytes,
                      field_work_package_bytes,query_text_bytes,row_count,
                      row_count > %s AS cardinality_limit_exceeded,
                      row_count <= %s AND NOT bytes_allowed
                          AS payload_limit_exceeded
                 FROM decided
             ) AS bounded ORDER BY bounded.id""",
        (
            request.project_id,
            request.company_id,
            request.company_id,
            request.date,
            MAX_DAILY_WORK_ROWS + 1,
            4096, 128, 64, 512, 1024,
            MAX_SNAPSHOT_TEXT_QUERY_BYTES,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
            MAX_DAILY_WORK_ROWS,
        ),
    )
    rows = _rows(cur)
    state = _validate_gate_rows(
        rows,
        variable_fields=(
            "description", "unit", "quantity", "master_name", "work_package",
        ),
        field_caps={
            "description": 4096,
            "unit": 128,
            "quantity": 64,
            "master_name": 512,
            "work_package": 1024,
        },
        total_field="query_text_bytes",
        total_cap=MAX_SNAPSHOT_TEXT_QUERY_BYTES,
        row_limit=MAX_DAILY_WORK_ROWS,
    )
    return state, rows


def _context_matches(request, row):
    return (
        _positive_int(row.get("estimate_id")) == request.estimate_id
        and _positive_int(row.get("company_id")) == request.company_id
        and _positive_int(row.get("project_id")) == request.project_id
        and _positive_int(row.get("estimate_version_id"))
        == request.estimate_version_id
        and row.get("estimate_status") == "Активная"
        and row.get("is_template") is False
        and row.get("work_package") == request.work_package
        and type(row.get("project_name")) is str
        and bool(row.get("project_name").strip())
    )


def _item_key(estimate_id, section_index, item_index, item):
    keys = []
    for field in ("estimateItemKey", "estimate_item_key"):
        value = item.get(field)
        if value in (None, ""):
            continue
        if type(value) is not str or value != value.strip() or not value:
            return None
        if value not in keys:
            keys.append(value)
    if len(keys) > 1:
        return None
    return keys[0] if keys else f"{estimate_id}:{section_index}:{item_index}"


def _source_decimal(value):
    if type(value) not in (int, float, str, Decimal) or type(value) is bool:
        return None
    if type(value) is str and len(value) > 128:
        return None
    if type(value) is int and value.bit_length() > 512:
        return None
    if type(value) is Decimal:
        _sign, digits, exponent = value.as_tuple()
        if len(digits) > 128 or exponent > 128 or exponent < -128:
            return None
    try:
        number = Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return number if number.is_finite() else None


def _assignment_source_rows(request, sections, assignments):
    indexed = {}
    for row in assignments:
        if (
            _positive_int(row.get("company_id")) != request.company_id
            or _positive_int(row.get("project_id")) != request.project_id
            or _positive_int(row.get("estimate_id")) != request.estimate_id
            or _positive_int(row.get("estimate_version_id"))
            != request.estimate_version_id
            or row.get("work_package") != request.work_package
            or row.get("source_type") != "estimate"
            or _exact_int(row.get("section_index"), minimum=0) is None
            or _exact_int(row.get("item_index"), minimum=0) is None
            or type(row.get("item_key")) is not str
        ):
            return None
        key = (
            row["section_index"], row["item_index"], row["item_key"],
        )
        if key in indexed:
            return None
        indexed[key] = row["assigned_quantity"]

    source_rows = []
    seen = set()
    try:
        for section_index, section in enumerate(sections):
            if type(section) is not dict or type(section.get("items")) is not list:
                return None
            section_name = section.get("name") or section.get("title") or ""
            for item_index, item in enumerate(section["items"]):
                if len(source_rows) > MAX_ASSIGNMENT_DRAFT_ROWS:
                    return source_rows
                if type(item) is not dict:
                    return None
                item_key = _item_key(
                    request.estimate_id,
                    section_index,
                    item_index,
                    item,
                )
                if item_key is None:
                    return None
                key = (section_index, item_index, item_key)
                seen.add(key)
                quantity = _source_decimal(item.get("quantity"))
                source_rows.append({
                    "company_id": request.company_id,
                    "project_id": request.project_id,
                    "estimate_id": request.estimate_id,
                    "estimate_version_id": request.estimate_version_id,
                    "estimate_status": "Активная",
                    "is_template": False,
                    "work_package": request.work_package,
                    "source_type": "estimate",
                    "lineage_count": 1,
                    "section_index": section_index,
                    "item_index": item_index,
                    "item_key": item_key,
                    "section_name": section_name,
                    "item_name": item.get("name") or item.get("description") or "",
                    "unit": item.get("unit") or "",
                    "quantity": quantity,
                    "assigned_quantity": indexed.get(key, Decimal(0)),
                    "itemType": item.get("itemType"),
                    "type": item.get("type"),
                    "kind": item.get("kind"),
                    "priceWork": item.get("priceWork"),
                    "priceMaterial": item.get("priceMaterial"),
                })
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if set(indexed) - seen:
        return None
    return source_rows


def collect_assignment_daily_snapshot(cur, request):
    """Collect and detach both drafts; caller owns the read-only transaction."""

    if type(request) is not AssignmentDailySnapshotRequest:
        _fail(_INPUT_INVALID)
    if not callable(getattr(cur, "execute", None)) or not callable(
        getattr(cur, "fetchall", None)
    ):
        _fail(_INPUT_INVALID)

    context_state, context_rows = _load_context(cur, request)
    if context_state == "empty":
        return _review_snapshot(request, _SOURCE_NOT_FOUND)
    if context_state == "cardinality":
        return _review_snapshot(request, _SOURCE_AMBIGUOUS)
    if context_state == "overflow":
        return _review_snapshot(request, _PAYLOAD_TOO_LARGE)
    context = context_rows[0]
    if not _context_matches(request, context):
        return _review_snapshot(request, _SOURCE_INVALID)
    if _exact_int(context.get("project_name_count"), minimum=0) != 1:
        return _review_snapshot(request, _PROJECT_AMBIGUOUS)

    try:
        active_sections = parse_sections(context["active_sections_json"])
        version_sections = parse_sections(context["version_sections_json"])
        if sections_sha256(active_sections) != sections_sha256(version_sections):
            return _review_snapshot(request, _VERSION_STALE)
    except (
        TypeError, ValueError, json.JSONDecodeError, RecursionError,
        UnicodeError, OverflowError,
    ):
        return _review_snapshot(request, _SOURCE_INVALID)

    assignment_state, assignment_rows = _load_assignments(cur, request)
    if assignment_state == "cardinality":
        return _review_snapshot(
            request,
            _ASSIGNMENT_SCAN_LIMIT,
            assignment_code=_ASSIGNMENT_SCAN_LIMIT,
        )
    if assignment_state == "overflow":
        return _review_snapshot(
            request,
            _SOURCE_INVALID,
            assignment_code="assignment_source_invalid",
        )
    source_rows = _assignment_source_rows(
        request,
        version_sections,
        assignment_rows,
    )
    if source_rows is None:
        return _review_snapshot(request, _LINEAGE_INVALID)
    assignment = build_assignment_draft(_assignment_scope(request), source_rows)

    daily_state, daily_rows = _load_daily(cur, request)
    if daily_state == "cardinality":
        return _snapshot(
            request,
            assignment,
            _empty_daily(
                request,
                "review_required",
                (_DAILY_SCAN_LIMIT,),
            ),
        )
    if daily_state == "overflow":
        return _snapshot(
            request,
            assignment,
            _empty_daily(
                request,
                "review_required",
                ("daily_work_source_invalid",),
            ),
        )
    daily = build_daily_work_draft(_daily_scope(request), daily_rows)
    return _snapshot(request, assignment, daily)


def _configure_transaction(cur):
    cur.execute(
        """SELECT pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true),
                  pg_catalog.set_config(%s, %s, true)""",
        (
            "statement_timeout", "30000",
            "lock_timeout", "1000",
            "idle_in_transaction_session_timeout", "30000",
            "search_path", "pg_catalog,public",
        ),
    )


def run_assignment_daily_snapshot(get_db, request):
    """Run one repeatable read-only snapshot and always roll it back."""

    if not callable(get_db) or type(request) is not AssignmentDailySnapshotRequest:
        _fail(_INPUT_INVALID)
    connection = None
    cur = None
    result = None
    primary_error = None
    rollback_error = None
    cleanup_error = None
    first_control = None

    try:
        connection = get_db()
        connection.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        cur = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _configure_transaction(cur)
        result = collect_assignment_daily_snapshot(cur, request)
    except BaseException as exc:
        primary_error = exc
        if isinstance(exc, _CONTROL_FLOW):
            first_control = exc

    if connection is not None:
        try:
            connection.rollback()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            else:
                rollback_error = exc
    if cur is not None:
        try:
            cur.close()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            elif cleanup_error is None:
                cleanup_error = exc
    if connection is not None:
        try:
            connection.close()
        except BaseException as exc:
            if isinstance(exc, _CONTROL_FLOW):
                if first_control is None:
                    first_control = exc
            elif cleanup_error is None:
                cleanup_error = exc

    if first_control is not None:
        raise first_control
    if rollback_error is not None:
        _fail(_ROLLBACK_FAILED)
    if primary_error is not None:
        if (
            isinstance(primary_error, AssignmentDailySnapshotError)
            and primary_error.args == (_INPUT_INVALID,)
        ):
            _fail(_INPUT_INVALID)
        _fail(_READ_FAILED)
    if cleanup_error is not None:
        _fail(_CLEANUP_FAILED)
    if type(result) is not AssignmentDailySnapshot:
        _fail(_CONTRACT_INVALID)
    return result


__all__ = []
