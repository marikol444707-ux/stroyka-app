#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
MIN_ESTIMATES = int(os.getenv("SMOKE_ESTIMATES_MIN", "1"))
MIN_SECTIONS = int(os.getenv("SMOKE_ESTIMATE_MIN_SECTIONS", "1"))
MIN_ITEMS = int(os.getenv("SMOKE_ESTIMATE_MIN_ITEMS", "1"))
MIN_WORKS = int(os.getenv("SMOKE_ESTIMATE_MIN_WORKS", "1"))
MIN_TOTAL = float(os.getenv("SMOKE_ESTIMATE_MIN_TOTAL", "1"))
MAX_FULL_SECONDS = float(os.getenv("SMOKE_ESTIMATE_MAX_FULL_SECONDS", "25"))
MAX_QUANTITY = float(os.getenv("SMOKE_ESTIMATE_MAX_QUANTITY", "1000000"))


def _to_float(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("\xa0", "").replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text or 0)
    except Exception:
        return 0.0


def _json_request(method, path, token=None, payload=None, expected=200, timeout=80):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    elapsed = time.monotonic() - started
    if status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    return (json.loads(text) if text else {}), elapsed


def _totp_code(secret):
    secret = re.sub(r"\s+", "", secret or "").upper()
    if not secret:
        return ""
    secret += "=" * (-len(secret) % 8)
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time()) // 30
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
    return str(code).zfill(6)


def login():
    email = os.getenv("SMOKE_EMAIL", "")
    password = os.getenv("SMOKE_PASSWORD", "")
    if not email or not password:
        return "", "SMOKE_EMAIL/SMOKE_PASSWORD не заданы"

    body, _ = _json_request("POST", "/login", payload={"email": email, "password": password})
    token = body.get("authToken") or body.get("token")
    if token:
        return token, ""

    if body.get("twoFactorSetupRequired"):
        return "", "login требует первичную настройку 2FA"

    if body.get("twoFactorRequired") and body.get("challengeToken"):
        code = os.getenv("SMOKE_2FA_CODE", "")
        if not code and os.getenv("SMOKE_TOTP_SECRET"):
            code = _totp_code(os.getenv("SMOKE_TOTP_SECRET", ""))
        if not code:
            return "", "login требует 2FA; задайте SMOKE_2FA_CODE или SMOKE_TOTP_SECRET"
        verify_body, _ = _json_request(
            "POST",
            "/login/2fa/verify",
            payload={"challengeToken": body.get("challengeToken"), "code": code},
        )
        token = verify_body.get("authToken") or verify_body.get("token")
        if token:
            return token, ""
        return "", "2FA пройдена неуспешно: authToken не получен"

    return "", body.get("detail") or "authToken не получен"


def _rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "estimates", "data", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _sections(data):
    sections = data.get("sections") if isinstance(data, dict) else []
    return sections if isinstance(sections, list) else []


def _items(sections):
    out = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_name = section.get("name") or "Без раздела"
        for item in section.get("items") or []:
            if isinstance(item, dict):
                out.append((section_name, item))
    return out


def _item_type(section_name, item):
    raw = str(item.get("itemType") or item.get("type") or "").strip().lower()
    if raw:
        return raw
    text = (section_name + " " + str(item.get("name") or "")).lower()
    if any(word in text for word in ("материал", "ресурс", "оборудован", "издели")):
        return "material"
    return "work"


def _item_total(item):
    if item.get("isImported"):
        for field in ("totalWork", "workTotal", "workSum", "totalMaterial", "materialTotal", "materialSum"):
            value = _to_float(item.get(field))
            if value:
                return value
        for field in ("lineTotal", "currentTotal", "total", "amount", "sum", "totalSum", "estimatedCost"):
            value = _to_float(item.get(field))
            if value:
                return value
    qty = _to_float(item.get("quantity"))
    return qty * (_to_float(item.get("priceWork")) + _to_float(item.get("priceMaterial")))


def _summary_total(row):
    for field in ("summaryTotal", "total", "amount", "sum", "totalSum", "estimatedCost"):
        value = _to_float(row.get(field))
        if value:
            return value
    return 0.0


def _select_estimate(rows):
    requested_id = os.getenv("SMOKE_ESTIMATE_ID", "").strip()
    requested_name = os.getenv("SMOKE_ESTIMATE_NAME", "").strip().lower()
    if requested_id:
        for row in rows:
            if str(row.get("id")) == requested_id:
                return row
    if requested_name:
        for row in rows:
            if requested_name in str(row.get("name") or "").lower():
                return row
    active = [r for r in rows if str(r.get("status") or "").lower() in ("активная", "active")]
    candidates = active or rows
    return max(candidates, key=_summary_total)


def main():
    token, skip_reason = login()
    if not token:
        print(json.dumps({"ok": True, "skipped": True, "reason": skip_reason}, ensure_ascii=False, indent=2))
        return

    failures = []
    warnings = []

    summary_body, summary_elapsed = _json_request("GET", "/estimates?summary=true", token=token)
    estimate_rows = _rows(summary_body)
    active_count = sum(1 for row in estimate_rows if str(row.get("status") or "").lower() in ("активная", "active"))

    if len(estimate_rows) < MIN_ESTIMATES:
        failures.append(f"список смет пустой или меньше лимита: {len(estimate_rows)} < {MIN_ESTIMATES}")
    if estimate_rows and active_count == 0:
        warnings.append("активных смет не найдено")

    selected = _select_estimate(estimate_rows) if estimate_rows else {}
    selected_id = selected.get("id")
    if not selected_id:
        failures.append("не удалось выбрать смету для детальной проверки")
        selected_id = 0

    full_body = {}
    full_elapsed = 0.0
    sections = []
    items = []
    works = 0
    materials = 0
    computed_total = 0.0
    huge_quantity = []

    if selected_id:
        full_body, full_elapsed = _json_request("GET", f"/estimates/{selected_id}", token=token, timeout=max(80, int(MAX_FULL_SECONDS) + 10))
        sections = _sections(full_body)
        items = _items(sections)
        for section_name, item in items:
            item_type = _item_type(section_name, item)
            if item_type in ("material", "equipment", "transport"):
                materials += 1
            elif item_type not in ("adjustment", "note"):
                works += 1
            qty = _to_float(item.get("quantity"))
            if abs(qty) > MAX_QUANTITY:
                huge_quantity.append({
                    "section": section_name,
                    "name": item.get("name") or item.get("description") or "Без названия",
                    "quantity": qty,
                    "unit": item.get("unit") or "",
                })
            computed_total += _item_total(item)

        if full_elapsed > MAX_FULL_SECONDS:
            failures.append(f"детальная загрузка сметы слишком долгая: {full_elapsed:.2f}s > {MAX_FULL_SECONDS:.2f}s")
        if len(sections) < MIN_SECTIONS:
            failures.append(f"в смете мало разделов: {len(sections)} < {MIN_SECTIONS}")
        if len(items) < MIN_ITEMS:
            failures.append(f"в смете мало строк: {len(items)} < {MIN_ITEMS}")
        if works < MIN_WORKS:
            failures.append(f"работ меньше лимита: {works} < {MIN_WORKS}")
        if _summary_total(full_body) < MIN_TOTAL and computed_total < MIN_TOTAL:
            failures.append("сумма сметы нулевая или не рассчиталась")
        if huge_quantity:
            failures.append(f"найдены подозрительно большие количества: {len(huge_quantity)}")

        full_total = _summary_total(full_body)
        if full_total and computed_total and abs(full_total - computed_total) > max(10, full_total * 0.02):
            warnings.append(f"итог API отличается от пересчета строк: api={full_total:.2f}, rows={computed_total:.2f}")

    result = {
        "ok": not failures,
        "checked": [
            "login",
            "GET /estimates?summary=true",
            "GET /estimates/{id}",
            "estimate sections and items",
            "work/material counters",
            "non-zero totals",
            "large-estimate load time",
            "huge quantity guard",
        ],
        "summary": {
            "count": len(estimate_rows),
            "active": active_count,
            "elapsedSec": round(summary_elapsed, 3),
        },
        "selectedEstimate": {
            "id": selected_id,
            "name": selected.get("name") or full_body.get("name") or "",
            "projectName": selected.get("projectName") or full_body.get("projectName") or "",
            "status": selected.get("status") or full_body.get("status") or "",
            "summaryTotal": round(_summary_total(selected), 2),
            "fullTotal": round(_summary_total(full_body), 2),
            "computedTotal": round(computed_total, 2),
            "sections": len(sections),
            "items": len(items),
            "works": works,
            "materials": materials,
            "fullLoadSec": round(full_elapsed, 3),
        },
        "hugeQuantityExamples": huge_quantity[:5],
        "warnings": warnings,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except Exception as exc:
        print("FAIL smoke:estimates-prod:", exc, file=sys.stderr)
        raise SystemExit(1)
