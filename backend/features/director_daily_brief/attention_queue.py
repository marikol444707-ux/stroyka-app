"""Bounded read-only attention queue projected from a validated daily brief."""

from collections.abc import Mapping
from types import MappingProxyType


MAX_ATTENTION_QUEUE_ITEMS = 12
_ATTENTION_SEVERITIES = frozenset({"critical", "warning"})
_PRIORITY_ORDER = {"critical": 0, "warning": 1}
_ACTION_POLICY = MappingProxyType({
    "project.deadline_overdue": (
        "Просрочен срок объекта",
        "Проверить срок и ответственного по объекту",
        "projects",
    ),
    "task.deadline_overdue": (
        "Просрочена задача",
        "Проверить срок и ответственного по задаче",
        "assignments",
    ),
    "warehouse.below_minimum": (
        "Остаток ниже минимума",
        "Проверить остаток и потребность склада",
        "warehouse",
    ),
    "supply.open_shortage_claim": (
        "Открыта заявка с дефицитом",
        "Проверить заявку и доступный остаток",
        "supply",
    ),
    "estimate.unconfirmed": (
        "Смета не подтверждена",
        "Проверить смету перед использованием",
        "estimates",
    ),
    "supply.requests_pending": (
        "Заявки снабжения ожидают решения",
        "Проверить статус заявок снабжения",
        "supply",
    ),
    "task.unassigned": (
        "Задача без ответственного",
        "Назначить ответственного после проверки задачи",
        "assignments",
    ),
})
_FALLBACK_POLICY = (
    "Требуется проверка",
    "Проверить исходный пункт ежедневной сводки",
    "dailyBrief",
)


class AttentionQueueError(ValueError):
    pass


def _bounded_text(value, field, limit, *, required=True):
    if not isinstance(value, str):
        raise AttentionQueueError(f"{field} must be text")
    normalized = value.strip()
    if required and not normalized:
        raise AttentionQueueError(f"{field} is required")
    if len(normalized) > limit:
        raise AttentionQueueError(f"{field} is too long")
    return normalized


def build_attention_queue(brief):
    """Build a deterministic queue without exposing executable input fields."""
    if not isinstance(brief, Mapping):
        raise AttentionQueueError("brief must be an object")
    sections = brief.get("sections")
    if not isinstance(sections, list):
        raise AttentionQueueError("brief.sections must be a list")
    summary = brief.get("summary")
    if not isinstance(summary, Mapping):
        raise AttentionQueueError("brief.summary must be an object")
    attention_count = 0
    for severity in ("critical", "warning"):
        value = summary.get(severity)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AttentionQueueError(f"brief.summary.{severity} is invalid")
        attention_count += value

    candidates = []
    source_truncated = False
    for section_index, section in enumerate(sections):
        field = f"sections[{section_index}]"
        if not isinstance(section, Mapping):
            raise AttentionQueueError(f"{field} must be an object")
        key = _bounded_text(section.get("key"), f"{field}.key", 80)
        title = _bounded_text(section.get("title"), f"{field}.title", 200)
        status = section.get("status")
        if status not in {"clear", "attention", "info"}:
            raise AttentionQueueError(f"{field}.status is invalid")
        truncated = section.get("truncated")
        if not isinstance(truncated, bool):
            raise AttentionQueueError(f"{field}.truncated must be boolean")
        items = section.get("items")
        if not isinstance(items, list):
            raise AttentionQueueError(f"{field}.items must be a list")
        count = section.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < len(items):
            raise AttentionQueueError(f"{field}.count is invalid")

        for item_index, item in enumerate(items):
            item_field = f"{field}.items[{item_index}]"
            if not isinstance(item, Mapping):
                raise AttentionQueueError(f"{item_field} must be an object")
            severity = item.get("severity")
            if severity not in {"critical", "warning", "info"}:
                raise AttentionQueueError(f"{item_field}.severity is invalid")
            code = _bounded_text(item.get("code"), f"{item_field}.code", 120)
            subject = _bounded_text(
                item.get("subject"), f"{item_field}.subject", 240
            )
            if severity not in _ATTENTION_SEVERITIES:
                continue

            project = "Вся компания"
            if "project" in item:
                project = (
                    _bounded_text(
                        item.get("project"),
                        f"{item_field}.project",
                        200,
                        required=False,
                    )
                    or "Вся компания"
                )
            reason, next_action, destination = _ACTION_POLICY.get(
                code, _FALLBACK_POLICY
            )
            candidates.append({
                "id": f"{key}:{code}:{item_index}",
                "priority": severity,
                "category": title,
                "reason": reason,
                "subject": subject,
                "project": project,
                "owner": "Не назначен" if code == "task.unassigned" else "Не указан",
                "nextAction": next_action,
                "destination": destination,
                "sourceCode": code,
                "_sourceOrder": (section_index, item_index),
            })
        source_truncated = source_truncated or (
            status == "attention" and (truncated or count > len(items))
        )

    candidates.sort(
        key=lambda item: (_PRIORITY_ORDER[item["priority"]], item["_sourceOrder"])
    )
    if attention_count < len(candidates):
        raise AttentionQueueError("brief summary is inconsistent with attention items")
    public_items = []
    for item in candidates[:MAX_ATTENTION_QUEUE_ITEMS]:
        public_items.append({
            key: value
            for key, value in item.items()
            if key != "_sourceOrder"
        })
    return {
        "readOnly": True,
        "count": attention_count,
        "truncated": source_truncated or attention_count > len(public_items),
        "items": public_items,
    }
