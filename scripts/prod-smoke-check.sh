#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stroyka26.pro}"
BASE_URL="${BASE_URL%/}"
SMOKE_RETRIES="${SMOKE_RETRIES:-20}"
SMOKE_DELAY="${SMOKE_DELAY:-1}"
SMOKE_STARTED_TS="${SMOKE_STARTED_TS:-$(date -u +%s)}"

failures=()
health_body=""

check_code() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"
  local code
  local attempt
  for attempt in $(seq 1 "$SMOKE_RETRIES"); do
    code="$(curl -skS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" == "$expected" ]]; then
      echo "OK   $name $code"
      return 0
    fi
    if [[ "$attempt" != "$SMOKE_RETRIES" ]]; then
      sleep "$SMOKE_DELAY"
    fi
  done
  echo "FAIL $name got=$code expected=$expected"
  failures+=("$name got=$code expected=$expected")
}

json_field() {
  local field="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get(sys.argv[1], ""))' "$field"
}

check_health() {
  local url="$1"
  local attempt
  for attempt in $(seq 1 "$SMOKE_RETRIES"); do
    health_body="$(curl -skS "$url" || true)"
    if printf '%s' "$health_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("ok") is True else 1)' >/dev/null 2>&1; then
      echo "OK   health"
      return 0
    fi
    if [[ "$attempt" != "$SMOKE_RETRIES" ]]; then
      sleep "$SMOKE_DELAY"
    fi
  done
  echo "FAIL health"
  failures+=("health")
}

check_json_predicate() {
  local name="$1"
  local url="$2"
  local predicate="$3"
  local body
  local attempt
  for attempt in $(seq 1 "$SMOKE_RETRIES"); do
    body="$(curl -skS "$url" || true)"
    if printf '%s' "$body" | python3 -c "$predicate" >/dev/null 2>&1; then
      echo "OK   $name"
      return 0
    fi
    if [[ "$attempt" != "$SMOKE_RETRIES" ]]; then
      sleep "$SMOKE_DELAY"
    fi
  done
  echo "FAIL $name"
  failures+=("$name")
}

echo "Smoke-check: $BASE_URL"

check_code "frontend /" "$BASE_URL/"

check_health "$BASE_URL/health"
health_version="$(printf '%s' "$health_body" | json_field version 2>/dev/null || true)"
if [[ -n "$health_version" ]]; then
  echo "INFO version=$health_version"
fi

check_json_predicate "site pricing" "$BASE_URL/site/pricing" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data.get("rules"), list) else 1)'
check_json_predicate "site projects" "$BASE_URL/site/projects" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)'

if [[ -n "${SMOKE_EMAIL:-}" && -n "${SMOKE_PASSWORD:-}" ]]; then
  login_payload="$(python3 -c 'import json,os; print(json.dumps({"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]}, ensure_ascii=False))')"
  login_body="$(curl -skS -X POST "$BASE_URL/login" -H 'Content-Type: application/json' -d "$login_payload" || true)"
  token="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("authToken",""))' 2>/dev/null || true)"
  if [[ -z "$token" ]]; then
    echo "FAIL login"
    failures+=("login")
  else
    echo "OK   login"
    protected_paths=(
      "/system-status"
      "/projects"
      "/users"
      "/estimates"
      "/materials"
      "/supply-requests"
      "/supply-history"
      "/own-expenses"
      "/work-journal"
      "/hidden-works-acts"
      "/interim-acts"
      "/project-payments"
      "/unexpected-works"
      "/supervisor-acts"
      "/expenses"
      "/ai-tasks"
    )
    for path in "${protected_paths[@]}"; do
      code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL$path" -H "Authorization: Bearer $token" || true)"
      if [[ "$code" == "200" ]]; then
        echo "OK   $path $code"
      else
        echo "FAIL $path got=$code expected=200"
        failures+=("$path got=$code expected=200")
      fi
    done

    telegram_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/telegram/own-expenses" -H 'Content-Type: application/json' -d '{"telegramId":"smoke","description":"smoke","amount":1}' || true)"
    if [[ "$telegram_code" == "403" || "$telegram_code" == "503" ]]; then
      echo "OK   /telegram/own-expenses protected $telegram_code"
    else
      echo "FAIL /telegram/own-expenses unprotected got=$telegram_code expected=403/503"
      failures+=("/telegram/own-expenses unprotected got=$telegram_code")
    fi

    if [[ -n "${SMOKE_TELEGRAM_BOT_TOKEN:-}" ]]; then
      telegram_valid_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/telegram/own-expenses" -H 'Content-Type: application/json' -H "X-Telegram-Bot-Token: $SMOKE_TELEGRAM_BOT_TOKEN" -d '{"telegramId":"__smoke_missing_employee__","description":"smoke","amount":1}' || true)"
      if [[ "$telegram_valid_code" == "404" ]]; then
        echo "OK   /telegram/own-expenses route $telegram_valid_code"
      else
        echo "FAIL /telegram/own-expenses route got=$telegram_valid_code expected=404"
        failures+=("/telegram/own-expenses route got=$telegram_valid_code expected=404")
      fi
    fi

    status_body="$(curl -skS "$BASE_URL/system-status?api_errors_since=$SMOKE_STARTED_TS" -H "Authorization: Bearer $token" || true)"
    api_errors="$(printf '%s' "$status_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(len(data.get("apiErrors", [])))' 2>/dev/null || true)"
    if [[ -n "$api_errors" ]]; then
      echo "INFO apiErrorsShown=$api_errors"
      api_errors_window="$(printf '%s' "$status_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("apiErrorsWindow", ""))' 2>/dev/null || true)"
      if [[ -n "$api_errors_window" ]]; then
        echo "INFO apiErrorsWindow=$api_errors_window"
      fi
      if [[ "$api_errors" != "0" ]]; then
        printf '%s' "$status_body" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
for e in (data.get("apiErrors") or [])[:5]:
    created = e.get("createdAt") or "?"
    method = e.get("method") or "?"
    path = e.get("path") or "?"
    code = e.get("statusCode") or 500
    err_type = e.get("errorType") or "?"
    msg = (e.get("message") or "").replace("\n", " ")
    if len(msg) > 140:
        msg = msg[:137] + "..."
    print(f"INFO apiError {created} {code} {method} {path} {err_type}: {msg}")
'
      fi
    fi
  fi
else
  echo "SKIP protected checks: set SMOKE_EMAIL and SMOKE_PASSWORD"
fi

if (( ${#failures[@]} > 0 )); then
  echo "Smoke-check failed:"
  printf ' - %s\n' "${failures[@]}"
  exit 1
fi

echo "Smoke-check OK"
