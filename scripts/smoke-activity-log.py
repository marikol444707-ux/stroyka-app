#!/usr/bin/env python3
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")


def api_json(method, path, token=None, data=None, expected=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def query(path, params):
    return path + "?" + urllib.parse.urlencode(params)


def login(email, password):
    _, body = api_json("POST", "/login", data={"email": email, "password": password}, expected=200)
    token = body.get("authToken")
    if not token:
        raise RuntimeError("authToken не получен")
    return token


def require_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Нужно задать {name}")
    return value


def parse_created_at(row):
    raw = str(row.get("createdAt") or "")
    if not raw:
        return dt.datetime.min
    raw = raw.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(raw).replace(tzinfo=None)
    except ValueError:
        return dt.datetime.min


def assert_true(condition, message):
    if not condition:
        raise RuntimeError(message)


def all_match(rows, key, expected):
    expected = str(expected).lower()
    return all(expected in str(row.get(key) or "").lower() for row in rows)


def main():
    email = require_env("SMOKE_EMAIL")
    password = require_env("SMOKE_PASSWORD")
    token = login(email, password)

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
    marker = f"CODEX QA audit smoke {stamp}"
    project_name = os.getenv("SMOKE_AUDIT_PROJECT", "Кисловодск Лицей 4")
    action = "codex_smoke_activity"
    entity_type = "qa_activity_log"
    entity_id = int(stamp[-8:])

    _, created = api_json(
        "POST",
        "/audit-log",
        token=token,
        expected=200,
        data={
            "action": action,
            "entityType": entity_type,
            "entityId": entity_id,
            "description": marker,
            "projectName": project_name,
        },
    )
    audit_id = created.get("id")
    assert_true(audit_id, "audit-log запись не создана")

    today = dt.datetime.now(dt.UTC).date().isoformat()
    checks = []

    _, rows = api_json(
        "GET",
        query("/audit-log", {"limit": 20, "search": marker}),
        token=token,
        expected=200,
    )
    assert_true(isinstance(rows, list), "search вернул не список")
    assert_true(any(row.get("id") == audit_id for row in rows), "созданная запись не найдена по search")
    checks.append("search finds created audit row")

    _, action_rows = api_json(
        "GET",
        query("/audit-log", {"limit": 20, "action": action}),
        token=token,
        expected=200,
    )
    assert_true(any(row.get("id") == audit_id for row in action_rows), "созданная запись не найдена по action")
    assert_true(all_match(action_rows, "action", action), "фильтр action вернул чужие действия")
    checks.append("action filter")

    _, entity_rows = api_json(
        "GET",
        query("/audit-log", {"limit": 20, "entity_type": entity_type}),
        token=token,
        expected=200,
    )
    assert_true(any(row.get("id") == audit_id for row in entity_rows), "созданная запись не найдена по entity_type")
    assert_true(all_match(entity_rows, "entityType", entity_type), "фильтр entity_type вернул чужие сущности")
    checks.append("entity type filter")

    _, project_rows = api_json(
        "GET",
        query("/audit-log", {"limit": 20, "project_name": project_name, "search": marker}),
        token=token,
        expected=200,
    )
    assert_true(any(row.get("id") == audit_id for row in project_rows), "созданная запись не найдена по объекту")
    assert_true(all_match(project_rows, "projectName", project_name), "фильтр project_name вернул чужие объекты")
    checks.append("project filter")

    _, date_rows = api_json(
        "GET",
        query("/audit-log", {"limit": 20, "date_from": today, "search": marker}),
        token=token,
        expected=200,
    )
    assert_true(any(row.get("id") == audit_id for row in date_rows), "созданная запись не найдена по date_from")
    checks.append("date filter")

    _, latest_rows = api_json(
        "GET",
        query("/audit-log", {"limit": 50}),
        token=token,
        expected=200,
    )
    assert_true(isinstance(latest_rows, list), "последние записи вернули не список")
    parsed = [parse_created_at(row) for row in latest_rows]
    assert_true(parsed == sorted(parsed, reverse=True), "сортировка audit_log не DESC по времени")
    checks.append("createdAt descending order")

    print(json.dumps({
        "ok": True,
        "auditId": audit_id,
        "marker": marker,
        "projectName": project_name,
        "checked": checks,
        "note": "smoke оставляет одну audit_log запись как след проверки",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
