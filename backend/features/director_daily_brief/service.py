"""Pure deterministic aggregation for a single-company director brief."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date

from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS
from backend.features.director_agent.result_policy import (
    DirectorAgentResultPolicyError,
    sanitize_director_agent_tool_result,
)


class DirectorDailyBriefError(ValueError):
    pass


SECTION_ORDER = (
    ("overdue", "Просрочки"),
    ("shortages", "Дефициты"),
    ("documents", "Неподтверждённые документы"),
    ("estimateDeviations", "Отклонения смет"),
    ("payments", "Платежи"),
    ("tasks", "Задачи"),
)
MAX_SECTION_ITEMS = 20
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_TERMINAL_PROJECT_STATUSES = {
    "архив",
    "архивный",
    "выполнен",
    "выполнено",
    "завершен",
    "завершён",
    "завершено",
    "закрыт",
    "закрыто",
}
_UNCONFIRMED_ESTIMATE_STATUSES = {
    "",
    "черновик",
    "на проверке",
}
_TERMINAL_SUPPLY_STATUSES = {
    "отклонена",
    "отменена",
    "отменена с откатом",
    "поставлено",
}


def _iso_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _required_brief_date(value):
    parsed = _iso_date(value)
    if parsed is None:
        raise DirectorDailyBriefError("brief_date must be an ISO date")
    return parsed


def _normalize_status(value):
    return str(value or "").strip().casefold()


def _round_number(value):
    return round(float(value or 0), 3)


def _item(code, severity, subject, **fields):
    item = {
        "code": code,
        "severity": severity,
        "subject": str(subject or "")[:500],
    }
    allowed = {
        "project",
        "status",
        "dueDate",
        "metricValue",
        "metricUnit",
        "previousValue",
        "currentValue",
    }
    for key, value in fields.items():
        if key in allowed and value not in (None, ""):
            item[key] = value
    return item


def _project_overdue(projects, brief_date):
    items = []
    for project in projects:
        deadline = _iso_date(project["deadline"])
        if (
            deadline is None
            or deadline >= brief_date
            or _normalize_status(project["status"]) in _TERMINAL_PROJECT_STATUSES
        ):
            continue
        items.append(_item(
            "project.deadline_overdue",
            "critical",
            project["name"],
            project=project["name"],
            status=project["status"],
            dueDate=deadline.isoformat(),
            metricValue=(brief_date - deadline).days,
            metricUnit="days",
        ))
    return items


def _task_overdue(tasks, brief_date):
    items = []
    for task in tasks:
        due_date = _iso_date(task["dueDate"])
        if due_date is None or due_date >= brief_date:
            continue
        items.append(_item(
            "task.deadline_overdue",
            "critical",
            task["title"],
            project=task["project"],
            status=task["status"],
            dueDate=due_date.isoformat(),
            metricValue=(brief_date - due_date).days,
            metricUnit="days",
        ))
    return items


def _shortages(warehouse, supply):
    items = []
    for material in warehouse["mainWarehouse"]:
        shortage = _round_number(material["minQty"] - material["qty"])
        if material["minQty"] <= 0 or shortage <= 0:
            continue
        items.append(_item(
            "warehouse.below_minimum",
            "warning",
            material["name"],
            metricValue=shortage,
            metricUnit=material["unit"],
            previousValue=_round_number(material["qty"]),
            currentValue=_round_number(material["minQty"]),
        ))
    for claim in supply["openClaims"]:
        if claim["shortage"] <= 0:
            continue
        items.append(_item(
            "supply.open_shortage_claim",
            "critical",
            claim["material"],
            project=claim["project"],
            status=claim["status"],
            metricValue=_round_number(claim["shortage"]),
        ))
    return items


def _documents(estimates, supply):
    items = []
    for estimate in estimates:
        if _normalize_status(estimate["status"]) not in _UNCONFIRMED_ESTIMATE_STATUSES:
            continue
        items.append(_item(
            "estimate.unconfirmed",
            "warning",
            estimate["name"],
            project=estimate["project"],
            status=estimate["status"] or "Без статуса",
            currentValue=_round_number(estimate["total"]),
            metricUnit="RUB",
        ))
    for status, count in supply["requestStatusCounts"].items():
        if count <= 0 or _normalize_status(status) in _TERMINAL_SUPPLY_STATUSES:
            continue
        items.append(_item(
            "supply.requests_pending",
            "warning",
            status or "Без статуса",
            status=status or "Без статуса",
            metricValue=count,
            metricUnit="requests",
        ))
    return items


def _estimate_deviations(estimates):
    grouped = defaultdict(list)
    for estimate in estimates:
        key = (estimate["project"], estimate["type"], estimate["package"])
        grouped[key].append(estimate)
    items = []
    for group in grouped.values():
        if len(group) < 2:
            continue
        current, previous = group[0], group[1]
        delta = round(current["total"] - previous["total"], 2)
        if abs(delta) < 0.01:
            continue
        items.append(_item(
            "estimate.total_changed",
            "warning",
            current["name"],
            project=current["project"],
            status=current["status"],
            metricValue=delta,
            metricUnit="RUB",
            previousValue=round(previous["total"], 2),
            currentValue=round(current["total"], 2),
        ))
    return items


def _payments(finances):
    total_budget = round(sum(row["budget"] for row in finances), 2)
    total_payments = round(sum(row["paymentsNet"] for row in finances), 2)
    items = [_item(
        "finance.overview",
        "info",
        "Все объекты",
        metricValue=round(total_payments - total_budget, 2),
        metricUnit="RUB",
        previousValue=total_budget,
        currentValue=total_payments,
    )]
    for row in finances:
        if row["paymentsNet"] < 0:
            items.append(_item(
                "finance.negative_payments",
                "critical",
                row["project"],
                project=row["project"],
                status=row["status"],
                metricValue=round(row["paymentsNet"], 2),
                metricUnit="RUB",
            ))
        elif row["budget"] > 0 and row["paymentsNet"] > row["budget"]:
            items.append(_item(
                "finance.over_budget",
                "warning",
                row["project"],
                project=row["project"],
                status=row["status"],
                metricValue=round(row["paymentsNet"] - row["budget"], 2),
                metricUnit="RUB",
                previousValue=round(row["budget"], 2),
                currentValue=round(row["paymentsNet"], 2),
            ))
    return items


def _tasks(ai_tasks):
    items = []
    for status, count in ai_tasks["openStatusCounts"].items():
        if count <= 0:
            continue
        items.append(_item(
            "task.open_status",
            "info",
            status or "Без статуса",
            status=status or "Без статуса",
            metricValue=count,
            metricUnit="tasks",
        ))
    for task in ai_tasks["tasks"]:
        if task["assignedTo"].strip():
            continue
        items.append(_item(
            "task.unassigned",
            "warning",
            task["title"],
            project=task["project"],
            status=task["status"],
            dueDate=task["dueDate"],
        ))
    return items


def _item_sort_key(item):
    return (
        _SEVERITY_ORDER[item["severity"]],
        item["code"],
        item.get("project", ""),
        item["subject"],
        item.get("dueDate", ""),
    )


def _section(key, title, items):
    ordered = sorted(items, key=_item_sort_key)
    severities = {item["severity"] for item in ordered}
    status = (
        "attention"
        if severities.intersection({"critical", "warning"})
        else "info"
        if ordered
        else "clear"
    )
    return {
        "key": key,
        "title": title,
        "status": status,
        "count": len(ordered),
        "truncated": len(ordered) > MAX_SECTION_ITEMS,
        "items": ordered[:MAX_SECTION_ITEMS],
    }


def _source_counts(facts):
    return {
        "projects": len(facts["projects"]),
        "warehouse": len(facts["warehouse"]["mainWarehouse"]) + len(facts["warehouse"]["objectMaterials"]),
        "supply": len(facts["supply"]["recentRequests"]) + len(facts["supply"]["recentDeliveries"]) + len(facts["supply"]["openClaims"]),
        "estimates": len(facts["estimates"]),
        "finances": len(facts["finances"]),
        "staff": len(facts["staff"]["staff"]),
        "ai_tasks": len(facts["ai_tasks"]["tasks"]),
    }


def build_director_daily_brief(*, brief_date, tool_results):
    """Build a bounded brief from all seven allowlisted read-tool results."""
    parsed_date = _required_brief_date(brief_date)
    if not isinstance(tool_results, Mapping):
        raise DirectorDailyBriefError("tool_results must be an object")
    if set(tool_results) != set(DIRECTOR_AGENT_READ_TOOLS):
        raise DirectorDailyBriefError("tool_results must contain exactly the allowed tools")
    try:
        facts = {
            tool_name: sanitize_director_agent_tool_result(
                tool_name,
                tool_results[tool_name],
            )
            for tool_name in DIRECTOR_AGENT_READ_TOOLS
        }
    except DirectorAgentResultPolicyError as exc:
        raise DirectorDailyBriefError(str(exc)) from exc

    findings = {
        "overdue": _project_overdue(facts["projects"], parsed_date)
        + _task_overdue(facts["ai_tasks"]["tasks"], parsed_date),
        "shortages": _shortages(facts["warehouse"], facts["supply"]),
        "documents": _documents(facts["estimates"], facts["supply"]),
        "estimateDeviations": _estimate_deviations(facts["estimates"]),
        "payments": _payments(facts["finances"]),
        "tasks": _tasks(facts["ai_tasks"]),
    }
    sections = [
        _section(key, title, findings[key])
        for key, title in SECTION_ORDER
    ]
    severity_counts = {"critical": 0, "warning": 0, "info": 0}
    for section in sections:
        for item in findings[section["key"]]:
            severity_counts[item["severity"]] += 1
    return {
        "schemaVersion": 1,
        "briefDate": parsed_date.isoformat(),
        "mode": "deterministic_read_only",
        "summary": {
            "total": sum(severity_counts.values()),
            **severity_counts,
        },
        "sections": sections,
        "sourceCounts": _source_counts(facts),
    }
