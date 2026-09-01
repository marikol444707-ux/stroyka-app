import datetime as dt


SUBSCRIPTION_EXPIRY_WARNING_DAYS = 7


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
        return {"status": "soft_frozen", "label": "Мягко заморожена", "level": "danger"}
    payment_status = company.get("payment_status") or "active"
    if payment_status == "overdue":
        return {"status": "overdue", "label": "Просрочка", "level": "danger"}

    plan = str(company.get("plan") or "demo").strip()
    if plan == "demo":
        trial_until = _date_value(company.get("trial_until"))
        if trial_until is None:
            return {"status": "trial_unknown", "label": "Демо без даты", "level": "warning"}
        days_left = (trial_until - today).days
        if days_left < 0:
            return {"status": "trial_expired", "label": "Демо истекло", "level": "danger", "daysLeft": days_left}
        if days_left <= SUBSCRIPTION_EXPIRY_WARNING_DAYS:
            return {"status": "trial_expiring", "label": "Демо скоро закончится", "level": "warning", "daysLeft": days_left}
        return {"status": "trial_active", "label": "Демо активно", "level": "info", "daysLeft": days_left}

    plan_expires_at = _date_value(company.get("plan_expires_at"))
    if plan_expires_at is not None:
        days_left = (plan_expires_at - today).days
        if days_left < 0:
            return {"status": "payment_expired", "label": "Оплата истекла", "level": "danger", "daysLeft": days_left}
        if days_left <= SUBSCRIPTION_EXPIRY_WARNING_DAYS:
            return {"status": "payment_expiring", "label": "Оплата скоро закончится", "level": "warning", "daysLeft": days_left}
    return {"status": "active", "label": "Активна", "level": "success"}
