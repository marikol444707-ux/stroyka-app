#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stroyka26.pro}"
BASE_URL="${BASE_URL%/}"
SMOKE_RETRIES="${SMOKE_RETRIES:-20}"
SMOKE_DELAY="${SMOKE_DELAY:-1}"
SMOKE_STARTED_TS="${SMOKE_STARTED_TS:-$(date -u +%s)}"
FRONTEND_ASSET_RETRIES="${FRONTEND_ASSET_RETRIES:-3}"
FRONTEND_ASSET_FAILURE_LIMIT="${FRONTEND_ASSET_FAILURE_LIMIT:-5}"
FRONTEND_MANIFEST_MAX_BYTES="${FRONTEND_MANIFEST_MAX_BYTES:-1048576}"

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

check_frontend_asset() {
  local name="$1"
  local url="$2"
  local expected_kind="$3"
  local body_file
  local code=""
  local content_type=""
  local response_metadata
  local transfer_ok=0
  local attempt
  body_file="$(mktemp)"

  for attempt in $(seq 1 "$FRONTEND_ASSET_RETRIES"); do
    : > "$body_file"
    if response_metadata="$(
      curl -skS --connect-timeout 5 --max-time 20 \
        -o "$body_file" -w '%{http_code} %{content_type}' "$url"
    )"; then
      transfer_ok=1
    else
      transfer_ok=0
    fi
    code="${response_metadata%% *}"
    content_type=""
    if [[ "$response_metadata" == *" "* ]]; then
      content_type="${response_metadata#* }"
    fi
    content_type="$(printf '%s' "$content_type" | tr '[:upper:]' '[:lower:]')"
    if [[ "$transfer_ok" == "1" && "$code" == "200" && -s "$body_file" ]] \
      && ! head -c 512 "$body_file" | grep -qiE '<!doctype|<html' \
      && { [[ "$expected_kind" == "js" && "$content_type" =~ ^(application|text)/(javascript|x-javascript)([[:space:]]*\;.*)?$ ]] \
        || [[ "$expected_kind" == "css" && "$content_type" =~ ^text/css([[:space:]]*\;.*)?$ ]]; }; then
      echo "OK   $name $code"
      rm -f "$body_file"
      return 0
    fi
    if [[ "$attempt" != "$FRONTEND_ASSET_RETRIES" ]]; then
      sleep "$SMOKE_DELAY"
    fi
  done

  echo "FAIL $name got=$code content-type=$content_type expected=200 valid $expected_kind asset"
  failures+=("$name got=$code or invalid $expected_kind asset")
  rm -f "$body_file"
  return 1
}

check_frontend_assets() {
  local base_url="${1%/}"
  local manifest_file
  local paths_file
  local code=""
  local transfer_ok=0
  local attempt
  local asset_kind
  local asset_path
  local asset_failures=0
  manifest_file="$(mktemp)"
  paths_file="$(mktemp)"

  for attempt in $(seq 1 "$SMOKE_RETRIES"); do
    : > "$manifest_file"
    if code="$(curl -skS --connect-timeout 5 --max-time 20 \
      --max-filesize "$FRONTEND_MANIFEST_MAX_BYTES" \
      -o "$manifest_file" -w '%{http_code}' "$base_url/asset-manifest.json")"; then
      transfer_ok=1
    else
      transfer_ok=0
    fi
    if [[ "$transfer_ok" == "1" && "$code" == "200" ]] \
      && [[ "$(wc -c < "$manifest_file")" -le "$FRONTEND_MANIFEST_MAX_BYTES" ]] \
      && python3 - "$manifest_file" > "$paths_file" <<'PY'
import json
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    files = manifest.get("files") if type(manifest) is dict else None
    if type(files) is not dict:
        raise ValueError("files")
    if len(files) > 256:
        raise ValueError("too many frontend manifest entries")

    def checked_asset_path(value, suffix, label):
        if type(value) is not str or not value.endswith(suffix):
            raise ValueError(label)
        if not re.fullmatch(r"/static/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+", value):
            raise ValueError(label)
        if any(part in ("", ".", "..") for part in value.split("/")[1:]):
            raise ValueError(label)
        return value

    def asset_kind(value):
        if type(value) is not str:
            return None
        if value.endswith(".js"):
            return "js"
        if value.endswith(".css"):
            return "css"
        return None

    main_js = checked_asset_path(files.get("main.js"), ".js", "main.js")
    main_css = checked_asset_path(files.get("main.css"), ".css", "main.css")
    assets = {main_js: "js", main_css: "css"}
    for key, value in files.items():
        key_kind = asset_kind(key)
        value_kind = asset_kind(value)
        if key_kind is None and value_kind is None:
            continue
        if key_kind is None or value_kind != key_kind:
            raise ValueError(key)
        assets[checked_asset_path(value, f".{key_kind}", key)] = key_kind

    ordered = [(main_js, "js"), (main_css, "css")]
    ordered.extend(sorted(
        (path, kind)
        for path, kind in assets.items()
        if path not in (main_js, main_css)
    ))
    for path, kind in ordered:
        print(f"{kind}\t{path}")
except (OSError, UnicodeError, ValueError, json.JSONDecodeError, TypeError):
    raise SystemExit(1)
PY
    then
      echo "OK   frontend asset manifest 200"
      while IFS=$'\t' read -r asset_kind asset_path; do
        [[ -n "$asset_kind" && -n "$asset_path" ]] || continue
        if ! check_frontend_asset "frontend asset $asset_path" "$base_url$asset_path" "$asset_kind"; then
          ((asset_failures += 1))
          if ((asset_failures >= FRONTEND_ASSET_FAILURE_LIMIT)); then
            echo "FAIL frontend asset check stopped after $asset_failures failures"
            break
          fi
        fi
      done < "$paths_file"
      rm -f "$manifest_file" "$paths_file"
      return 0
    fi
    if [[ "$attempt" != "$SMOKE_RETRIES" ]]; then
      sleep "$SMOKE_DELAY"
    fi
  done

  echo "FAIL frontend asset manifest got=$code expected=200 with valid JavaScript/CSS assets"
  failures+=("frontend asset manifest got=$code or invalid payload")
  rm -f "$manifest_file" "$paths_file"
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
  if [[ "$code" == "429" || " $expected_codes " == *" $code "* ]]; then
    if [[ "$code" == "429" ]] || ! head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
      echo "OK   $name $code"
      rm -f "$body_file"
      return 0
    fi
  fi
  echo "FAIL $name got=$code expected=$expected_codes"
  if head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
    failures+=("$name returned SPA index.html")
  else
    failures+=("$name got=$code expected=$expected_codes")
  fi
  rm -f "$body_file"
}

check_post_not_spa_fallback() {
  local name="$1"
  local url="$2"
  local expected_codes="$3"
  local body_file
  local code
  body_file="$(mktemp)"
  code="$(curl -skS -X POST -o "$body_file" -w '%{http_code}' "$url" || true)"
  if [[ "$code" == "429" || " $expected_codes " == *" $code "* ]]; then
    if [[ "$code" == "429" ]] || ! head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
      echo "OK   $name $code"
      rm -f "$body_file"
      return 0
    fi
  fi
  echo "FAIL $name got=$code expected=$expected_codes"
  if head -c 200 "$body_file" | grep -qiE '<!doctype|<html'; then
    failures+=("$name returned HTML instead of backend JSON")
  else
    failures+=("$name got=$code expected=$expected_codes")
  fi
  rm -f "$body_file"
}

describe_auth_failure() {
  local code="$1"
  local body="$2"
  local detail
  detail="$(printf '%s' "$body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("detail", ""))' 2>/dev/null || true)"
  if [[ -n "$detail" ]]; then
    echo "HTTP $code: $detail"
  elif [[ "$code" == "429" || "$code" == "503" ]]; then
    echo "HTTP $code: временный лимит Nginx/CDN"
  elif [[ -z "$body" || "$code" == "000" ]]; then
    echo "HTTP $code: пустой или недоступный ответ"
  elif printf '%s' "$body" | head -c 200 | grep -qiE '<!doctype|<html'; then
    echo "HTTP $code: Nginx/CDN вернул HTML вместо JSON"
  else
    echo "HTTP $code: неожиданный ответ без описания ошибки"
  fi
}

public_smoke_checks_enabled() {
  [[ "${SMOKE_PROTECTED_ONLY:-0}" != "1" ]]
}

echo "Smoke-check: $BASE_URL"

check_code "frontend /" "$BASE_URL/"
check_code "frontend /app" "$BASE_URL/app"
check_code "frontend /max-app" "$BASE_URL/max-app"
check_frontend_assets "$BASE_URL"

check_health "$BASE_URL/health"
health_version="$(printf '%s' "$health_body" | json_field version 2>/dev/null || true)"
if [[ -n "$health_version" ]]; then
  echo "INFO version=$health_version"
fi

if public_smoke_checks_enabled; then
  check_json_predicate "site pricing" "$BASE_URL/site/pricing" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data.get("rules"), list) else 1)'
  check_json_predicate "site projects" "$BASE_URL/site/projects" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)'
  check_json_predicate "site publications" "$BASE_URL/site/publications?limit=1" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)'
  check_not_spa_fallback "site leads route" "$BASE_URL/site/leads" "405 429"
  check_post_not_spa_fallback "site lead files route" "$BASE_URL/site/lead-files" "422 429"
  check_not_spa_fallback "site price rules route" "$BASE_URL/site-price-rules" "401 403 429"
  check_not_spa_fallback "tenant files route" "$BASE_URL/tenant-files/1" "401 403"
  check_not_spa_fallback "tenant file content route" "$BASE_URL/tenant-files/1/content" "401 403"
  check_not_spa_fallback "company messages route" "$BASE_URL/messages" "401 403"
  check_not_spa_fallback "estimate versions route" "$BASE_URL/estimates/1/versions" "401 403"
  check_not_spa_fallback "estimate version detail route" "$BASE_URL/estimate-version/1" "401 403"
  check_not_spa_fallback "estimate chat history route" "$BASE_URL/estimates/1/chat-history" "401 403"
  check_not_spa_fallback "estimate chat post route" "$BASE_URL/estimate-chat" "405"
  check_not_spa_fallback "estimate transfer plan route" "$BASE_URL/estimate-row-transfer-plans/1" "401 403"
  check_post_not_spa_fallback "estimate transfer plan post route" "$BASE_URL/estimate-row-transfer-plans" "401 403 422"
  check_post_not_spa_fallback "estimate transfer approval route" "$BASE_URL/estimate-row-transfer-plans/1/approval" "401 403 422"
  check_post_not_spa_fallback "estimate assignment apply route" "$BASE_URL/estimate-row-transfer-plans/1/assignment-apply" "401 403 422"
  check_post_not_spa_fallback "estimate supply apply route" "$BASE_URL/estimate-row-transfer-plans/1/supply-apply" "401 403 422"
  check_not_spa_fallback "estimate budget adjustment preview route" "$BASE_URL/estimate-reconciliations/1/budget-adjustment-preview" "401 403"
  check_post_not_spa_fallback "estimate budget adjustment approval route" "$BASE_URL/estimate-reconciliations/1/budget-adjustment-approval" "401 403 422"
  check_not_spa_fallback "project budget adjustment history route" "$BASE_URL/projects/1/budget-adjustments" "401 403"
  check_not_spa_fallback "project AI summary route" "$BASE_URL/project-ai-summary/smoke" "401 403"
  check_not_spa_fallback "project AI summary post route" "$BASE_URL/project-ai-summary" "405"
  check_not_spa_fallback "AI findings route" "$BASE_URL/ai-findings" "401 403"
  check_not_spa_fallback "agent jobs route" "$BASE_URL/agent-jobs" "401 403"
  check_not_spa_fallback "director daily brief latest route" "$BASE_URL/agent-jobs/director-daily-brief/latest" "401 403"
  check_not_spa_fallback "agent job detail route" "$BASE_URL/agent-jobs/1" "401 403"
  check_post_not_spa_fallback "agent job cancel route" "$BASE_URL/agent-jobs/1/cancel" "401 403"
  check_not_spa_fallback "AI tasks route" "$BASE_URL/ai-tasks" "401 403"
  check_not_spa_fallback "assignments route" "$BASE_URL/assignments" "401 403"
  check_not_spa_fallback "AI task reports route" "$BASE_URL/ai-tasks/1/reports" "401 403"
  check_not_spa_fallback "project events route" "$BASE_URL/project-events?project_name=smoke" "401 403"
  check_not_spa_fallback "material packaging rules route" "$BASE_URL/material-packaging-rules" "401 403"
  check_post_not_spa_fallback "material packaging correction preview route" "$BASE_URL/material-packaging-corrections/preview" "401 403 422 429"
  check_not_spa_fallback "material packaging reviews route" "$BASE_URL/material-packaging-reviews" "401 403"
  check_not_spa_fallback "material capability proof route" "$BASE_URL/supply-requests/2147483647/items/0/material-capability-proof" "404 422"
  check_not_spa_fallback "material capability confirmation route" "$BASE_URL/supply-requests/2147483647/items/0/material-capability-confirmations" "404 405"
  check_not_spa_fallback "material capability revocation route" "$BASE_URL/supplier-material-capability-confirmations/2147483647/revocations" "404 405"
  check_not_spa_fallback "AI control single run route" "$BASE_URL/ai-control/run" "405"
  check_not_spa_fallback "AI findings generate route" "$BASE_URL/ai-findings/generate" "405"
  check_not_spa_fallback "AI control run-all route" "$BASE_URL/ai-control/run-all" "405"
  check_not_spa_fallback "messenger channels route" "$BASE_URL/messenger-channels" "401 403"
  check_not_spa_fallback "messenger accounts route" "$BASE_URL/messenger-accounts" "401 403"
  check_post_not_spa_fallback "messenger channels post route" "$BASE_URL/messenger-channels" "401 403 422"
  check_post_not_spa_fallback "messenger accounts post route" "$BASE_URL/messenger-accounts" "401 403 422"
  check_not_spa_fallback "messenger outbox route" "$BASE_URL/messenger-outbox" "401 403"
  check_not_spa_fallback "MAX outbox worker route" "$BASE_URL/max/outbox" "401 403"
  check_post_not_spa_fallback "MAX outbox dispatch route" "$BASE_URL/max/outbox/dispatch?dry_run=true" "401 403"
  check_not_spa_fallback "marketing publications route" "$BASE_URL/marketing-publications" "401 403"
  check_post_not_spa_fallback "marketing publications post route" "$BASE_URL/marketing-publications" "401 403 422"
  check_post_not_spa_fallback "client errors route" "$BASE_URL/client-errors" "200 422 429"
else
  echo "INFO protected-only smoke: unauthenticated API route checks skipped"
fi

if [[ -n "${SMOKE_EMAIL:-}" && -n "${SMOKE_PASSWORD:-}" ]]; then
  login_payload="$(python3 -c 'import json,os; print(json.dumps({"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]}, ensure_ascii=False))')"
  login_response_file="$(mktemp)"
  login_code="$(curl -skS -X POST -o "$login_response_file" -w '%{http_code}' "$BASE_URL/login" -H 'Content-Type: application/json' -d "$login_payload" || true)"
  login_body="$(cat "$login_response_file")"
  rm -f "$login_response_file"
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
        verify_response_file="$(mktemp)"
        verify_code="$(curl -skS -X POST -o "$verify_response_file" -w '%{http_code}' "$BASE_URL/login/2fa/verify" -H 'Content-Type: application/json' -d "$verify_payload" || true)"
        verify_body="$(cat "$verify_response_file")"
        rm -f "$verify_response_file"
        token="$(printf '%s' "$verify_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("authToken",""))' 2>/dev/null || true)"
        if [[ -z "$token" ]]; then
          echo "FAIL login 2FA: $(describe_auth_failure "$verify_code" "$verify_body")"
          failures+=("login 2FA")
        fi
      else
        echo "SKIP protected checks: login requires 2FA; set SMOKE_2FA_CODE or SMOKE_TOTP_SECRET"
      fi
    elif [[ -n "$two_factor_setup_required" ]]; then
      echo "SKIP protected checks: login requires initial 2FA setup"
    else
      echo "FAIL login: $(describe_auth_failure "$login_code" "$login_body")"
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
      "/estimates?summary=true"
      "/materials"
      "/messages"
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
      "/ai-findings"
      "/agent-jobs"
      "/ai-tasks"
      "/assignments"
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

    estimates_body="$(curl -skS "$BASE_URL/estimates?summary=true" -H "Authorization: Bearer $token" || true)"
    versioned_estimate_id="$(printf '%s' "$estimates_body" | python3 -c '
import json
import sys

try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for row in rows if isinstance(rows, list) else []:
    if int(row.get("versionCount") or 0) > 0 and int(row.get("id") or 0) > 0:
        print(int(row["id"]))
        break
' 2>/dev/null || true)"
    if [[ -n "$versioned_estimate_id" ]]; then
      estimate_versions_file="$(mktemp)"
      estimate_versions_code="$(curl -skS -o "$estimate_versions_file" -w '%{http_code}' "$BASE_URL/estimates/$versioned_estimate_id/versions" -H "Authorization: Bearer $token" || true)"
      if [[ "$estimate_versions_code" == "200" ]] && python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); sys.exit(0 if isinstance(data,list) and data else 1)' "$estimate_versions_file" >/dev/null 2>&1; then
        echo "OK   /estimates/$versioned_estimate_id/versions 200"
        estimate_version_id="$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); print(int(data[0].get("id") or 0))' "$estimate_versions_file" 2>/dev/null || true)"
      else
        echo "FAIL /estimates/$versioned_estimate_id/versions got=$estimate_versions_code expected=200 non-empty JSON list"
        failures+=("/estimates/$versioned_estimate_id/versions got=$estimate_versions_code")
        estimate_version_id=""
      fi
      rm -f "$estimate_versions_file"

      if [[ -n "$estimate_version_id" && "$estimate_version_id" != "0" ]]; then
        estimate_version_detail_file="$(mktemp)"
        estimate_version_detail_code="$(curl -skS -o "$estimate_version_detail_file" -w '%{http_code}' "$BASE_URL/estimate-version/$estimate_version_id" -H "Authorization: Bearer $token" || true)"
        if [[ "$estimate_version_detail_code" == "200" ]] && python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); sys.exit(0 if int(data.get("id") or 0)==int(sys.argv[2]) and int(data.get("estimateId") or 0)==int(sys.argv[3]) else 1)' "$estimate_version_detail_file" "$estimate_version_id" "$versioned_estimate_id" >/dev/null 2>&1; then
          echo "OK   /estimate-version/$estimate_version_id 200"
        else
          echo "FAIL /estimate-version/$estimate_version_id got=$estimate_version_detail_code expected=200 matching parent"
          failures+=("/estimate-version/$estimate_version_id got=$estimate_version_detail_code")
        fi
        rm -f "$estimate_version_detail_file"
      fi

      estimate_chat_history_file="$(mktemp)"
      estimate_chat_history_code="$(curl -skS -o "$estimate_chat_history_file" -w '%{http_code}' "$BASE_URL/estimates/$versioned_estimate_id/chat-history" -H "Authorization: Bearer $token" || true)"
      if [[ "$estimate_chat_history_code" == "200" ]] && python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); sys.exit(0 if isinstance(data,list) else 1)' "$estimate_chat_history_file" >/dev/null 2>&1; then
        echo "OK   /estimates/$versioned_estimate_id/chat-history 200"
      else
        echo "FAIL /estimates/$versioned_estimate_id/chat-history got=$estimate_chat_history_code expected=200 JSON list"
        failures+=("/estimates/$versioned_estimate_id/chat-history got=$estimate_chat_history_code")
      fi
      rm -f "$estimate_chat_history_file"
    else
      echo "SKIP estimate version detail checks: no visible estimate with saved versions"
    fi

    company_messages_all_code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL/messages" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' || true)"
    if [[ "$company_messages_all_code" == "400" || "$company_messages_all_code" == "403" ]]; then
      echo "OK   /messages all-companies blocked $company_messages_all_code"
    else
      echo "FAIL /messages all-companies got=$company_messages_all_code expected=400/403"
      failures+=("/messages all-companies got=$company_messages_all_code expected=400/403")
    fi

    agent_jobs_all_code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL/agent-jobs" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' || true)"
    if [[ "$agent_jobs_all_code" == "400" || "$agent_jobs_all_code" == "403" || "$agent_jobs_all_code" == "409" ]]; then
      echo "OK   /agent-jobs all-companies blocked $agent_jobs_all_code"
    else
      echo "FAIL /agent-jobs all-companies got=$agent_jobs_all_code expected=400/403/409"
      failures+=("/agent-jobs all-companies got=$agent_jobs_all_code expected=400/403/409")
    fi

    director_daily_brief_all_code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL/agent-jobs/director-daily-brief/latest" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' || true)"
    if [[ "$director_daily_brief_all_code" == "400" || "$director_daily_brief_all_code" == "403" || "$director_daily_brief_all_code" == "409" ]]; then
      echo "OK   director daily brief all-companies blocked $director_daily_brief_all_code"
    else
      echo "FAIL director daily brief all-companies got=$director_daily_brief_all_code expected=400/403/409"
      failures+=("director daily brief all-companies got=$director_daily_brief_all_code expected=400/403/409")
    fi

    agent_jobs_foreign_code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL/agent-jobs" -H "Authorization: Bearer $token" -H 'X-Company-Id: 2147483647' || true)"
    if [[ "$agent_jobs_foreign_code" == "400" || "$agent_jobs_foreign_code" == "403" || "$agent_jobs_foreign_code" == "404" || "$agent_jobs_foreign_code" == "409" ]]; then
      echo "OK   /agent-jobs foreign company blocked $agent_jobs_foreign_code"
    else
      echo "FAIL /agent-jobs foreign company got=$agent_jobs_foreign_code expected=400/403/404/409"
      failures+=("/agent-jobs foreign company got=$agent_jobs_foreign_code expected=400/403/404/409")
    fi

    agent_job_cancel_all_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/agent-jobs/2147483647/cancel" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' -H 'Content-Type: application/json' -d '{"reasonCode":"user_request"}' || true)"
    if [[ "$agent_job_cancel_all_code" == "400" || "$agent_job_cancel_all_code" == "403" || "$agent_job_cancel_all_code" == "409" ]]; then
      echo "OK   agent job cancel all-companies blocked $agent_job_cancel_all_code"
    else
      echo "FAIL agent job cancel all-companies got=$agent_job_cancel_all_code expected=400/403/409"
      failures+=("agent job cancel all-companies got=$agent_job_cancel_all_code expected=400/403/409")
    fi

    agent_job_cancel_foreign_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/agent-jobs/2147483647/cancel" -H "Authorization: Bearer $token" -H 'X-Company-Id: 2147483647' -H 'Content-Type: application/json' -d '{"reasonCode":"user_request"}' || true)"
    if [[ "$agent_job_cancel_foreign_code" == "400" || "$agent_job_cancel_foreign_code" == "403" || "$agent_job_cancel_foreign_code" == "404" || "$agent_job_cancel_foreign_code" == "409" ]]; then
      echo "OK   agent job cancel foreign company blocked $agent_job_cancel_foreign_code"
    else
      echo "FAIL agent job cancel foreign company got=$agent_job_cancel_foreign_code expected=400/403/404/409"
      failures+=("agent job cancel foreign company got=$agent_job_cancel_foreign_code expected=400/403/404/409")
    fi

    agent_job_cancel_missing_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/agent-jobs/2147483647/cancel" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d '{"reasonCode":"user_request"}' || true)"
    if [[ "$agent_job_cancel_missing_code" == "404" ]]; then
      echo "OK   agent job cancel missing $agent_job_cancel_missing_code"
    else
      echo "FAIL agent job cancel missing got=$agent_job_cancel_missing_code expected=404"
      failures+=("agent job cancel missing got=$agent_job_cancel_missing_code expected=404")
    fi

    agent_jobs_file="$(mktemp)"
    agent_jobs_code="$(curl -skS -o "$agent_jobs_file" -w '%{http_code}' "$BASE_URL/agent-jobs" -H "Authorization: Bearer $token" || true)"
    if [[ "$agent_jobs_code" == "200" ]] && python3 - "$agent_jobs_file" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
items = data.get("items") if isinstance(data, dict) else None
forbidden = {
    "payload", "payloadJson", "payload_json", "result", "resultJson",
    "result_json", "lockedBy", "locked_by", "leaseToken", "lease_token",
    "idempotencyKey", "idempotency_key",
}
ok = isinstance(items, list) and all(
    isinstance(item, dict) and not (forbidden & set(item)) for item in items
)
raise SystemExit(0 if ok else 1)
PY
    then
      echo "OK   /agent-jobs public field policy 200"
    else
      echo "FAIL /agent-jobs public field policy got=$agent_jobs_code"
      failures+=("/agent-jobs public field policy")
    fi
    rm -f "$agent_jobs_file"

    director_daily_brief_file="$(mktemp)"
    director_daily_brief_code="$(curl -skS -o "$director_daily_brief_file" -w '%{http_code}' "$BASE_URL/agent-jobs/director-daily-brief/latest" -H "Authorization: Bearer $token" || true)"
    if [[ "$director_daily_brief_code" == "200" ]] && python3 - "$director_daily_brief_file" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
forbidden = {
    "payload", "payloadJson", "payload_json", "result", "resultJson",
    "result_json", "lockedBy", "locked_by", "leaseToken", "lease_token",
    "idempotencyKey", "idempotency_key", "correlationId", "correlation_id",
}

def has_forbidden(value):
    if isinstance(value, dict):
        return bool(forbidden & set(value)) or any(has_forbidden(item) for item in value.values())
    if isinstance(value, list):
        return any(has_forbidden(item) for item in value)
    return False

ok = isinstance(data, dict) and not has_forbidden(data)
if ok and data.get("available") is True:
    brief = data.get("brief")
    ok = (
        isinstance(data.get("jobId"), int)
        and isinstance(brief, dict)
        and brief.get("schemaVersion") == 1
        and brief.get("mode") == "deterministic_read_only"
        and isinstance(brief.get("summary"), dict)
        and isinstance(brief.get("sections"), list)
    )
elif ok:
    ok = data == {"available": False}
raise SystemExit(0 if ok else 1)
PY
    then
      echo "OK   /agent-jobs/director-daily-brief/latest public field policy 200"
    else
      echo "FAIL /agent-jobs/director-daily-brief/latest public field policy got=$director_daily_brief_code"
      failures+=("/agent-jobs/director-daily-brief/latest public field policy")
    fi
    rm -f "$director_daily_brief_file"

    estimate_chat_all_write_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/estimate-chat" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' -H 'Content-Type: application/json' -d '{"estimateId":2147483647,"message":"scope-smoke"}' || true)"
    if [[ "$estimate_chat_all_write_code" == "400" || "$estimate_chat_all_write_code" == "403" || "$estimate_chat_all_write_code" == "409" ]]; then
      echo "OK   /estimate-chat all-companies blocked $estimate_chat_all_write_code"
    else
      echo "FAIL /estimate-chat all-companies got=$estimate_chat_all_write_code expected=400/403/409"
      failures+=("/estimate-chat all-companies got=$estimate_chat_all_write_code expected=400/403/409")
    fi

    estimate_chat_all_delete_code="$(curl -skS -o /dev/null -w '%{http_code}' -X DELETE "$BASE_URL/estimates/2147483647/chat-history" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' || true)"
    if [[ "$estimate_chat_all_delete_code" == "400" || "$estimate_chat_all_delete_code" == "403" || "$estimate_chat_all_delete_code" == "409" ]]; then
      echo "OK   /estimate chat clear all-companies blocked $estimate_chat_all_delete_code"
    else
      echo "FAIL /estimate chat clear all-companies got=$estimate_chat_all_delete_code expected=400/403/409"
      failures+=("/estimate chat clear all-companies got=$estimate_chat_all_delete_code expected=400/403/409")
    fi

    ai_summary_all_read_code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL/project-ai-summary/scope-smoke" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' || true)"
    if [[ "$ai_summary_all_read_code" == "400" || "$ai_summary_all_read_code" == "403" || "$ai_summary_all_read_code" == "409" ]]; then
      echo "OK   /project-ai-summary all-companies read blocked $ai_summary_all_read_code"
    else
      echo "FAIL /project-ai-summary all-companies read got=$ai_summary_all_read_code expected=400/403/409"
      failures+=("/project-ai-summary all-companies read got=$ai_summary_all_read_code expected=400/403/409")
    fi

    ai_summary_all_write_code="$(curl -skS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/project-ai-summary" -H "Authorization: Bearer $token" -H 'X-Company-Mode: all_companies' -H 'Content-Type: application/json' -d '{"projectName":"scope-smoke","payloadHash":"scope-smoke","summary":"scope-smoke"}' || true)"
    if [[ "$ai_summary_all_write_code" == "400" || "$ai_summary_all_write_code" == "403" || "$ai_summary_all_write_code" == "409" ]]; then
      echo "OK   /project-ai-summary all-companies write blocked $ai_summary_all_write_code"
    else
      echo "FAIL /project-ai-summary all-companies write got=$ai_summary_all_write_code expected=400/403/409"
      failures+=("/project-ai-summary all-companies write got=$ai_summary_all_write_code expected=400/403/409")
    fi

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
