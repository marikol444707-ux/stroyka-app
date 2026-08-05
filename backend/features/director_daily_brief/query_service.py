"""Company-scoped read model for the latest completed director brief."""

import math
from collections.abc import Mapping
from datetime import date

from .service import MAX_SECTION_ITEMS, SECTION_ORDER


class DirectorDailyBriefQueryError(ValueError):
    pass


_JOB_TYPE = "director.daily_brief"
_SUMMARY_KEYS = ("total", "critical", "warning", "info")
_SOURCE_KEYS = (
    "projects",
    "warehouse",
    "supply",
    "estimates",
    "finances",
    "staff",
    "ai_tasks",
)
_SECTION_STATUSES = frozenset({"clear", "attention", "info"})
_SEVERITIES = frozenset({"critical", "warning", "info"})
_ITEM_TEXT_LIMITS = {
    "code": 120,
    "subject": 240,
    "project": 200,
    "status": 80,
    "dueDate": 40,
    "metricUnit": 32,
}


def _positive_int(value, field):
    if isinstance(value, bool):
        raise DirectorDailyBriefQueryError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefQueryError(
            f"{field} must be a positive integer"
        ) from exc
    if normalized <= 0:
        raise DirectorDailyBriefQueryError(f"{field} must be a positive integer")
    return normalized


def _nonnegative_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DirectorDailyBriefQueryError(
            f"stored daily brief {field} must be a non-negative integer"
        )
    return value


def _bounded_text(value, field, limit, *, required=False):
    if not isinstance(value, str):
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} must be text")
    if required and not value.strip():
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} is required")
    if len(value) > limit:
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} is too long")
    return value


def _finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} must be numeric")
    if not math.isfinite(float(value)):
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} must be finite")
    return value


def _brief_date(value):
    text = _bounded_text(value, "briefDate", 10, required=True)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise DirectorDailyBriefQueryError(
            "stored daily brief briefDate must be an ISO date"
        ) from exc
    if parsed.isoformat() != text:
        raise DirectorDailyBriefQueryError(
            "stored daily brief briefDate must be an ISO date"
        )
    return text


def _public_item(value, section_index, item_index):
    field = f"sections[{section_index}].items[{item_index}]"
    if not isinstance(value, Mapping):
        raise DirectorDailyBriefQueryError(f"stored daily brief {field} must be an object")
    severity = value.get("severity")
    if severity not in _SEVERITIES:
        raise DirectorDailyBriefQueryError(f"stored daily brief {field}.severity is invalid")
    item = {
        "code": _bounded_text(value.get("code"), f"{field}.code", 120, required=True),
        "severity": severity,
        "subject": _bounded_text(
            value.get("subject"), f"{field}.subject", 240, required=True
        ),
    }
    for key in ("project", "status", "dueDate", "metricUnit"):
        if key in value:
            item[key] = _bounded_text(
                value[key], f"{field}.{key}", _ITEM_TEXT_LIMITS[key]
            )
    for key in ("metricValue", "previousValue", "currentValue"):
        if key in value:
            item[key] = _finite_number(value[key], f"{field}.{key}")
    return item


def public_director_daily_brief(value):
    """Validate schema v1 and return an allowlisted copy for the leadership UI."""
    if not isinstance(value, Mapping):
        raise DirectorDailyBriefQueryError("stored daily brief result must be an object")
    if value.get("schemaVersion") != 1:
        raise DirectorDailyBriefQueryError("stored daily brief schemaVersion is unsupported")
    if value.get("mode") != "deterministic_read_only":
        raise DirectorDailyBriefQueryError("stored daily brief mode is invalid")

    raw_summary = value.get("summary")
    if not isinstance(raw_summary, Mapping):
        raise DirectorDailyBriefQueryError("stored daily brief summary must be an object")
    summary = {
        key: _nonnegative_int(raw_summary.get(key), f"summary.{key}")
        for key in _SUMMARY_KEYS
    }
    if summary["total"] != sum(summary[key] for key in _SUMMARY_KEYS[1:]):
        raise DirectorDailyBriefQueryError("stored daily brief summary totals are inconsistent")

    raw_sections = value.get("sections")
    if not isinstance(raw_sections, list) or len(raw_sections) != len(SECTION_ORDER):
        raise DirectorDailyBriefQueryError("stored daily brief sections are incomplete")
    sections = []
    for section_index, ((expected_key, expected_title), raw_section) in enumerate(
        zip(SECTION_ORDER, raw_sections)
    ):
        field = f"sections[{section_index}]"
        if not isinstance(raw_section, Mapping):
            raise DirectorDailyBriefQueryError(f"stored daily brief {field} must be an object")
        if raw_section.get("key") != expected_key or raw_section.get("title") != expected_title:
            raise DirectorDailyBriefQueryError(f"stored daily brief {field} identity is invalid")
        status = raw_section.get("status")
        if status not in _SECTION_STATUSES:
            raise DirectorDailyBriefQueryError(f"stored daily brief {field}.status is invalid")
        raw_items = raw_section.get("items")
        if not isinstance(raw_items, list) or len(raw_items) > MAX_SECTION_ITEMS:
            raise DirectorDailyBriefQueryError(f"stored daily brief {field}.items is invalid")
        count = _nonnegative_int(raw_section.get("count"), f"{field}.count")
        if count < len(raw_items):
            raise DirectorDailyBriefQueryError(f"stored daily brief {field}.count is inconsistent")
        truncated = raw_section.get("truncated")
        if not isinstance(truncated, bool):
            raise DirectorDailyBriefQueryError(f"stored daily brief {field}.truncated is invalid")
        sections.append({
            "key": expected_key,
            "title": expected_title,
            "status": status,
            "count": count,
            "truncated": truncated,
            "items": [
                _public_item(item, section_index, item_index)
                for item_index, item in enumerate(raw_items)
            ],
        })

    raw_sources = value.get("sourceCounts")
    if not isinstance(raw_sources, Mapping):
        raise DirectorDailyBriefQueryError("stored daily brief sourceCounts must be an object")
    source_counts = {
        key: _nonnegative_int(raw_sources.get(key), f"sourceCounts.{key}")
        for key in _SOURCE_KEYS
    }
    return {
        "schemaVersion": 1,
        "briefDate": _brief_date(value.get("briefDate")),
        "mode": "deterministic_read_only",
        "summary": summary,
        "sections": sections,
        "sourceCounts": source_counts,
    }


def _time(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def get_latest_director_daily_brief(cur, *, company_id):
    company_id = _positive_int(company_id, "company_id")
    cur.execute(
        """SELECT id,completed_at,result_json
             FROM agent_jobs
            WHERE company_id=%s
              AND project_id IS NULL
              AND job_type=%s
              AND status='succeeded'
              AND completed_at IS NOT NULL
              AND result_json IS NOT NULL
            ORDER BY completed_at DESC,id DESC
            LIMIT 1""",
        (company_id, _JOB_TYPE),
    )
    row = cur.fetchone()
    if not row:
        return {"available": False}
    return {
        "available": True,
        "jobId": _positive_int(row.get("id"), "job_id"),
        "completedAt": _time(row.get("completed_at")),
        "brief": public_director_daily_brief(row.get("result_json")),
    }
