import datetime as dt


SUBSCRIPTION_EXPIRY_WARNING_DAYS = 7
SUBSCRIPTION_READ_ONLY_STATUSES = frozenset({
    "soft_frozen",
    "overdue",
    "trial_expired",
    "payment_expired",
})


def _billing_result(status, label, level, **extra):
    return {
        "status": status,
        "label": label,
        "level": level,
        "readOnly": status in SUBSCRIPTION_READ_ONLY_STATUSES,
        **extra,
    }


def iso_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _date_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def billing_state(company, *, today=None):
    """Return the canonical, read-only subscription state for one company."""
    company = company or {}
    today = today or dt.date.today()
    if company.get("suspended_at"):
        return _billing_result("soft_frozen", "Мягко заморожена", "danger")
    payment_status = company.get("payment_status") or "active"
    if payment_status == "overdue":
        return _billing_result("overdue", "Просрочка", "danger")

    plan = str(company.get("plan") or "demo").strip()
    if plan == "demo":
        trial_until = _date_value(company.get("trial_until"))
        if trial_until is None:
            return _billing_result("trial_unknown", "Демо без даты", "warning")
        days_left = (trial_until - today).days
        if days_left < 0:
            return _billing_result("trial_expired", "Демо истекло", "danger", daysLeft=days_left)
        if days_left <= SUBSCRIPTION_EXPIRY_WARNING_DAYS:
            return _billing_result("trial_expiring", "Демо скоро закончится", "warning", daysLeft=days_left)
        return _billing_result("trial_active", "Демо активно", "info", daysLeft=days_left)

    plan_expires_at = _date_value(company.get("plan_expires_at"))
    if plan_expires_at is not None:
        days_left = (plan_expires_at - today).days
        if days_left < 0:
            return _billing_result("payment_expired", "Оплата истекла", "danger", daysLeft=days_left)
        if days_left <= SUBSCRIPTION_EXPIRY_WARNING_DAYS:
            return _billing_result("payment_expiring", "Оплата скоро закончится", "warning", daysLeft=days_left)
    return _billing_result("active", "Активна", "success")
