#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")
PROJECT_NAME = os.getenv("SMOKE_PROJECT_NAME", "Кисловодск Лицей 4")
MIN_ACTIVE_ESTIMATES = int(os.getenv("SMOKE_NORMS_MIN_ACTIVE_ESTIMATES", "1"))
MIN_WORKS = int(os.getenv("SMOKE_NORMS_MIN_WORKS", "1"))
MIN_MATERIALS = int(os.getenv("SMOKE_NORMS_MIN_MATERIALS", "1"))
MIN_SUGGESTIONS = int(os.getenv("SMOKE_NORMS_MIN_SUGGESTIONS", "1"))


def _json_request(method, path, token=None, payload=None, expected=200):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=80) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if status != expected:
        raise RuntimeError(f"{method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    return json.loads(text) if text else {}


def login():
    email = os.getenv("SMOKE_EMAIL", "")
    password = os.getenv("SMOKE_PASSWORD", "")
    if not email or not password:
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD")
    body = _json_request("POST", "/login", payload={"email": email, "password": password})
    token = body.get("authToken") or body.get("token")
    if not token:
        raise SystemExit("Login ok, но authToken не получен")
    return token


def _int_metric(data, diagnostics, *names):
    for name in names:
        value = data.get(name)
        if value is None:
            value = diagnostics.get(name)
        try:
            return int(float(value or 0))
        except Exception:
            continue
    return 0


def main():
    token = login()
    payload = {
        "projectName": PROJECT_NAME,
        "dryRun": True,
        "useAi": False,
    }
    body = _json_request(
        "POST",
        "/material-norm-suggestions/generate",
        token=token,
        payload=payload,
        expected=200,
    )

    diagnostics = body.get("diagnostics") or {}
    failures = []
    warnings = []

    if not body.get("ok"):
        failures.append("endpoint вернул ok=false")
    if not body.get("dryRun"):
        failures.append("endpoint не подтвердил dryRun=true")
    if body.get("aiUsed"):
        failures.append("dry-run неожиданно использовал внешний AI")
    if int(body.get("created") or 0) != 0 or int(body.get("updated") or 0) != 0:
        failures.append("dry-run записал изменения в БД")

    active_estimates = _int_metric(body, diagnostics, "activeCustomerEstimates")
    estimate_works = _int_metric(body, diagnostics, "estimateWorks")
    estimate_materials = _int_metric(body, diagnostics, "estimateMaterials")
    suggestions = _int_metric(body, diagnostics, "total", "suggestions")
    covered = _int_metric(body, diagnostics, "estimateMaterialsCoveredByNorm")

    if active_estimates < MIN_ACTIVE_ESTIMATES:
        failures.append(f"активных смет меньше лимита: {active_estimates} < {MIN_ACTIVE_ESTIMATES}")
    if estimate_works < MIN_WORKS:
        failures.append(f"работ в сметах меньше лимита: {estimate_works} < {MIN_WORKS}")
    if estimate_materials < MIN_MATERIALS:
        failures.append(f"материалов в сметах меньше лимита: {estimate_materials} < {MIN_MATERIALS}")
    if suggestions < MIN_SUGGESTIONS:
        failures.append(f"предложений норм меньше лимита: {suggestions} < {MIN_SUGGESTIONS}")
    if estimate_materials and covered == 0:
        warnings.append("материалы есть, но покрытие нормами равно 0")

    result = {
        "ok": not failures,
        "projectName": PROJECT_NAME,
        "checked": [
            "login",
            "material norm suggestions dry-run",
            "no database writes",
            "no external AI in dry-run",
            "active estimates/work/material counters",
        ],
        "metrics": {
            "activeCustomerEstimates": active_estimates,
            "estimateWorks": estimate_works,
            "estimateMaterials": estimate_materials,
            "estimateMaterialsCoveredByNorm": covered,
            "suggestions": suggestions,
        },
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
        print("FAIL smoke:norms-dry-run:", exc, file=sys.stderr)
        raise SystemExit(1)
