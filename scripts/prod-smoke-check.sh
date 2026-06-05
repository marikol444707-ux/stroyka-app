#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stroyka26.pro}"
BASE_URL="${BASE_URL%/}"

failures=()

check_code() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"
  local code
  code="$(curl -skS -o /dev/null -w '%{http_code}' "$url" || true)"
  if [[ "$code" == "$expected" ]]; then
    echo "OK   $name $code"
  else
    echo "FAIL $name got=$code expected=$expected"
    failures+=("$name got=$code expected=$expected")
  fi
}

json_field() {
  local field="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get(sys.argv[1], ""))' "$field"
}

check_json_ok() {
  local name="$1"
  local body="$2"
  if printf '%s' "$body" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("ok") is True else 1)' >/dev/null 2>&1; then
    echo "OK   $name"
  else
    echo "FAIL $name"
    failures+=("$name")
  fi
}

echo "Smoke-check: $BASE_URL"

check_code "frontend /" "$BASE_URL/"

health_body="$(curl -skS "$BASE_URL/health" || true)"
check_json_ok "health" "$health_body"
health_version="$(printf '%s' "$health_body" | json_field version 2>/dev/null || true)"
if [[ -n "$health_version" ]]; then
  echo "INFO version=$health_version"
fi

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
    status_body="$(curl -skS "$BASE_URL/system-status" -H "Authorization: Bearer $token" || true)"
    api_errors="$(printf '%s' "$status_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(len(data.get("apiErrors", [])))' 2>/dev/null || true)"
    if [[ -n "$api_errors" ]]; then
      echo "INFO apiErrorsShown=$api_errors"
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
