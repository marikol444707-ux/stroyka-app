"""Human names for website ad codes. Edit this mapping in one place."""

AD_SOURCES = {
    "netip": "Нетипичный Ставрополь",
    "bloknot": "Блокнот",
    "s1777": "s1777",
    "minvody": "minvody",
    "ptgorsk": "ptgorsk",
    "novoalex": "novoalex",
    "barahkmv": "barahkmv",
    "izhs": "izhs",
    "ipoteka": "ipoteka",
    "pyatigorsk_rab": "pyatigorsk_rab",
}

UTM_COLUMN_LIMIT = 120


def ad_source_label(code) -> str:
    raw = str(code or "").strip()
    if not raw:
        return ""
    return AD_SOURCES.get(raw.lower(), raw[:UTM_COLUMN_LIMIT])


def utm_field(utm: dict, key: str):
    if not isinstance(utm, dict):
        return None
    value = str(utm.get(key) or "").strip()
    if not value:
        return None
    return value[:UTM_COLUMN_LIMIT]


def utm_columns(data: dict):
    utm = data.get("utm") if isinstance(data, dict) and isinstance(data.get("utm"), dict) else {}
    return (
        utm_field(utm, "utm_source"),
        utm_field(utm, "utm_medium"),
        utm_field(utm, "utm_campaign"),
    )


def website_lead_source(raw_source, utm_source, *, partner=False) -> str:
    base = "Сайт: партнерская заявка" if partner else "Сайт"
    supplied = str(raw_source or "").strip()
    if supplied.startswith("Сайт"):
        base = supplied.split(" / ", 1)[0].strip() or base
    label = ad_source_label(utm_source)
    if not label:
        return (supplied or base)[:255]
    return f"{base} / {label}"[:255]
