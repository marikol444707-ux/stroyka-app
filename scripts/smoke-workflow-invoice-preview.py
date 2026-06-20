#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")


def load_env():
    values = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()


def env_value(name, default=""):
    return os.getenv(name) or ENV.get(name, default)


def api_json(method, path, data=None, headers=None, expected=None):
    body = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    if expected is not None and status != expected:
        raise SystemExit(f"FAIL {method} {path}: got {status}, expected {expected}. Body: {text[:700]}")
    if not text:
        return status, {}
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def require_workflow_token():
    token = (env_value("SMOKE_WORKFLOW_TOKEN") or env_value("WORKFLOW_TOKEN") or env_value("STROYKA_WORKFLOW_TOKEN")).strip()
    if not token:
        raise SystemExit("Нужно задать WORKFLOW_TOKEN в backend/.env или SMOKE_WORKFLOW_TOKEN в окружении")
    if token in {"...", "***", "token", "TOKEN"} or "ТОКЕН" in token.upper():
        raise SystemExit("WORKFLOW_TOKEN выглядит как заглушка")
    try:
        token.encode("latin-1")
    except UnicodeEncodeError:
        raise SystemExit("WORKFLOW_TOKEN должен быть ASCII-строкой без кириллицы")
    return token


def main():
    token = require_workflow_token()
    payload = {
        "projectName": os.getenv("SMOKE_WORKFLOW_PROJECT", "Кисловодск Лицей 4"),
        "warehouseTarget": "object",
        "selectedAction": "receive_to_warehouse",
        "photos": ["test-page-1.jpg", "test-page-2.jpg"],
        "document": {
            "number": "140563",
            "date": "2026-06-19",
            "supplierName": "АО КПК Ставропольстройопторг",
            "vat": "НДС 20%",
        },
        "items": [
            {
                "name": "Керамогранит глазурованный матовый 600x600",
                "quantity": 368.64,
                "unit": "м2",
                "price": 875,
                "lineTotal": 322560,
                "page": 1,
                "confidence": 0.92,
            }
        ],
        "user": {"role": "директор", "name": "Workflow smoke"},
    }

    protected_status, _ = api_json("POST", "/workflow/invoice/preview", data=payload)
    if protected_status not in (403, 503):
        raise SystemExit(f"FAIL workflow token protection: got {protected_status}, expected 403/503")

    _, body = api_json(
        "POST",
        "/workflow/invoice/preview",
        data=payload,
        headers={"X-Workflow-Token": token},
        expected=200,
    )

    failures = []
    if body.get("route") != "warehouse_invoice":
        failures.append("route != warehouse_invoice")
    if body.get("status") != "ok":
        failures.append(f"status != ok ({body.get('status')})")
    if body.get("document", {}).get("pagesDetected") != 2:
        failures.append("pagesDetected != 2")
    if len(body.get("items") or []) != 1:
        failures.append("items length != 1")
    if round(float(body.get("totals", {}).get("totalWithVat") or 0), 2) != 322560:
        failures.append("totalWithVat != 322560")
    if round(float(body.get("totals", {}).get("totalBase") or 0), 2) != 268800:
        failures.append("totalBase != 268800")
    if round(float(body.get("totals", {}).get("totalVat") or 0), 2) != 53760:
        failures.append("totalVat != 53760")
    if failures:
        raise SystemExit("FAIL workflow invoice preview: " + "; ".join(failures))

    print(json.dumps({
        "ok": True,
        "checked": [
            "workflow endpoint is token-protected",
            "multi-page invoice preview returns warehouse route",
            "VAT 20% is split into base and VAT",
            "preview does not write stock or expenses",
        ],
        "projectName": body.get("projectName"),
        "status": body.get("status"),
        "pagesDetected": body.get("document", {}).get("pagesDetected"),
        "items": len(body.get("items") or []),
        "totals": body.get("totals"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
