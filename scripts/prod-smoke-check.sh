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

totp_code_from_secret() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64
import hashlib
import hmac
import re
import sys
import time

secret = re.sub(r"\s+", "", sys.argv[1] or "").upper()
if not secret:
    raise SystemExit(1)
secret += "=" * (-len(secret) % 8)
key = base64.b32decode(secret, casefold=True)
counter = int(time.time()) // 30
digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
offset = digest[-1] & 0x0F
code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000
print(str(code).zfill(6))
PY
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

check_not_spa_fallback() {
  local name="$1"
  local url="$2"
  local expected_codes="$3"
  local body_file
  local code
  body_file="$(mktemp)"
  code="$(curl -skS -o "$body_file" -w '%{http_code}' "$url" || true)"
  if [[ " $expected_codes " == *" $code "* ]] && ! head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
    echo "OK   $name $code"
    rm -f "$body_file"
    return 0
  fi
  echo "FAIL $name got=$code expected=$expected_codes"
  if head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
    failures+=("$name returned SPA index.html")
  else
    failures+=("$name got=$code expected=$expected_codes")
  fi
  rm -f "$body_file"
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
check_not_spa_fallback "site leads route" "$BASE_URL/site/leads" "405"
check_not_spa_fallback "site price rules route" "$BASE_URL/site-price-rules" "401 403"

if [[ -n "${SMOKE_EMAIL:-}" && -n "${SMOKE_PASSWORD:-}" ]]; then
  login_payload="$(python3 -c 'import json,os; print(json.dumps({"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]}, ensure_ascii=False))')"
  login_body="$(curl -skS -X POST "$BASE_URL/login" -H 'Content-Type: application/json' -d "$login_payload" || true)"
  token="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("authToken",""))' 2>/dev/null || true)"
  if [[ -z "$token" ]]; then
    two_factor_required="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print("1" if data.get("twoFactorRequired") else "")' 2>/dev/null || true)"
    two_factor_setup_required="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print("1" if data.get("twoFactorSetupRequired") else "")' 2>/dev/null || true)"
    challenge_token="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("challengeToken",""))' 2>/dev/null || true)"
    if [[ -n "$two_factor_required" && -n "$challenge_token" ]]; then
      two_factor_code="${SMOKE_2FA_CODE:-}"
      if [[ -z "$two_factor_code" && -n "${SMOKE_TOTP_SECRET:-}" ]]; then
        two_factor_code="$(totp_code_from_secret "$SMOKE_TOTP_SECRET" 2>/dev/null || true)"
      fi
      if [[ -n "$two_factor_code" ]]; then
        verify_payload="$(CHALLENGE_TOKEN="$challenge_token" TWO_FACTOR_CODE="$two_factor_code" python3 -c 'import json,os; print(json.dumps({"challengeToken": os.environ["CHALLENGE_TOKEN"], "code": os.environ["TWO_FACTOR_CODE"]}, ensure_ascii=False))')"
        verify_body="$(curl -skS -X POST "$BASE_URL/login/2fa/verify" -H 'Content-Type: application/json' -d "$verify_payload" || true)"
        token="$(printf '%s' "$verify_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("authToken",""))' 2>/dev/null || true)"
        if [[ -z "$token" ]]; then
          echo "FAIL login 2FA"
          failures+=("login 2FA")
        fi
      else
        echo "SKIP protected checks: login requires 2FA; set SMOKE_2FA_CODE or SMOKE_TOTP_SECRET"
      fi
    elif [[ -n "$two_factor_setup_required" ]]; then
      echo "SKIP protected checks: login requires initial 2FA setup"
    else
      login_detail="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("detail",""))' 2>/dev/null || true)"
      echo "FAIL login${login_detail:+: $login_detail}"
      failures+=("login")
    fi
  fi
  if [[ -n "$token" ]]; then
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
