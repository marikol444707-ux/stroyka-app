#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
definitions="$(sed '/^echo "Smoke-check:/,$d' "$ROOT/scripts/prod-smoke-check.sh")"
definitions_file="$(mktemp)"
curl_log="$(mktemp)"
trap 'rm -f "$definitions_file" "$curl_log"' EXIT
printf '%s\n' "$definitions" > "$definitions_file"
source "$definitions_file"
SMOKE_RETRIES=1
SMOKE_DELAY=0

FAKE_CODE=""
FAKE_BODY=""
FAKE_FRONTEND_ASSETS="0"
FAKE_MANIFEST_CODE="200"
FAKE_MANIFEST_CURL_STATUS="0"
FAKE_MANIFEST_BODY=""
FAKE_MAIN_JS_CODE="200"
FAKE_MAIN_JS_CURL_STATUS="0"
FAKE_MAIN_CSS_CODE="200"
FAKE_LAZY_JS_CODE="200"
FAKE_LAZY_CSS_CODE="200"
FAKE_MAIN_JS_BODY="javascript"
FAKE_MAIN_CSS_BODY="stylesheet"
FAKE_LAZY_JS_BODY="lazy javascript"
FAKE_LAZY_CSS_BODY="lazy stylesheet"
FAKE_MAIN_JS_CONTENT_TYPE="application/javascript"
FAKE_MAIN_CSS_CONTENT_TYPE="text/css"
FAKE_LAZY_JS_CONTENT_TYPE="application/javascript"
FAKE_LAZY_CSS_CONTENT_TYPE="text/css"
TEST_BASE_URL="https://example.test"
FRONTEND_ASSET_RETRIES=1
FRONTEND_ASSET_FAILURE_LIMIT=5

curl() {
  local body_file=""
  local write_out=""
  local url=""
  local response_code="$FAKE_CODE"
  local response_body="$FAKE_BODY"
  local response_content_type="application/json"
  local response_status="0"
  while (($#)); do
    case "$1" in
      -o|--output)
        body_file="$2"
        shift 2
        ;;
      -w|--write-out)
        write_out="$2"
        shift 2
        ;;
      -*)
        shift
        ;;
      *)
        url="$1"
        shift
        ;;
    esac
  done
  printf '%s\n' "$url" >> "$curl_log"
  if [[ "$FAKE_FRONTEND_ASSETS" == "1" ]]; then
    case "$url" in
      "$TEST_BASE_URL/asset-manifest.json")
        response_code="$FAKE_MANIFEST_CODE"
        response_body="$FAKE_MANIFEST_BODY"
        response_status="$FAKE_MANIFEST_CURL_STATUS"
        ;;
      "$TEST_BASE_URL/static/js/main.test.js")
        response_code="$FAKE_MAIN_JS_CODE"
        response_body="$FAKE_MAIN_JS_BODY"
        response_content_type="$FAKE_MAIN_JS_CONTENT_TYPE"
        response_status="$FAKE_MAIN_JS_CURL_STATUS"
        ;;
      "$TEST_BASE_URL/static/css/main.test.css")
        response_code="$FAKE_MAIN_CSS_CODE"
        response_body="$FAKE_MAIN_CSS_BODY"
        response_content_type="$FAKE_MAIN_CSS_CONTENT_TYPE"
        ;;
      "$TEST_BASE_URL/static/js/9085.test.chunk.js")
        response_code="$FAKE_LAZY_JS_CODE"
        response_body="$FAKE_LAZY_JS_BODY"
        response_content_type="$FAKE_LAZY_JS_CONTENT_TYPE"
        ;;
      "$TEST_BASE_URL/static/css/5000.test.chunk.css")
        response_code="$FAKE_LAZY_CSS_CODE"
        response_body="$FAKE_LAZY_CSS_BODY"
        response_content_type="$FAKE_LAZY_CSS_CONTENT_TYPE"
        ;;
      *)
        response_code="404"
        response_body="not found"
        ;;
    esac
  fi
  if [[ -n "$body_file" ]]; then
    if [[ "$body_file" != "/dev/null" ]]; then
      printf '%s' "$response_body" > "$body_file"
    fi
  else
    printf '%s' "$response_body"
  fi
  if [[ -n "$write_out" ]]; then
    printf '%s' "${write_out//\%\{http_code\}/$response_code}" \
      | sed "s|%{content_type}|$response_content_type|g"
  fi
  return "$response_status"
}

failures=()
FAKE_CODE="429"
FAKE_BODY='<html><body>rate limited</body></html>'
check_post_not_spa_fallback "rate limited post" "https://example.test/route" "422" >/dev/null
check_not_spa_fallback "rate limited get" "https://example.test/route" "401 403" >/dev/null
if [[ ${#failures[@]} -ne 0 ]]; then
  echo "HTTP 429 must be accepted without listing it for every route" >&2
  exit 1
fi

failures=()
FAKE_CODE="422"
FAKE_BODY='<html><body>wrong proxy</body></html>'
check_post_not_spa_fallback "HTML backend error" "https://example.test/route" "422 429" >/dev/null
[[ ${#failures[@]} -eq 1 ]]

failures=()
FAKE_CODE="422"
FAKE_BODY='{"detail":"validation error"}'
check_post_not_spa_fallback "JSON backend error" "https://example.test/route" "422 429" >/dev/null
[[ ${#failures[@]} -eq 0 ]]

summary="$(describe_auth_failure "503" '<html><body>rate limited</body></html>')"
[[ "$summary" == "HTTP 503: временный лимит Nginx/CDN" ]]

summary="$(describe_auth_failure "401" '{"detail":"Неверный email или пароль"}')"
[[ "$summary" == "HTTP 401: Неверный email или пароль" ]]

summary="$(describe_auth_failure "000" '')"
[[ "$summary" == "HTTP 000: пустой или недоступный ответ" ]]

unset SMOKE_PROTECTED_ONLY
public_smoke_checks_enabled
SMOKE_PROTECTED_ONLY=1
if public_smoke_checks_enabled; then
  echo "protected-only mode must skip unauthenticated route checks" >&2
  exit 1
fi

if ! declare -F check_frontend_assets >/dev/null; then
  echo "prod smoke must define check_frontend_assets" >&2
  exit 1
fi

FAKE_FRONTEND_ASSETS="1"
FAKE_MANIFEST_BODY='{"files":{"main.js":"/static/js/main.test.js","main.css":"/static/css/main.test.css","static/js/9085.test.chunk.js":"/static/js/9085.test.chunk.js","static/css/5000.test.chunk.css":"/static/css/5000.test.chunk.css"}}'
FAKE_MAIN_JS_CODE="200"
FAKE_MAIN_CSS_CODE="200"
failures=()
: > "$curl_log"
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -ne 0 ]]; then
  echo "HTTP 200 for manifest main.js and main.css must pass" >&2
  printf ' - %s\n' "${failures[@]}" >&2
  exit 1
fi
grep -Fxq "$TEST_BASE_URL/static/js/main.test.js" "$curl_log" || {
  echo "manifest main.js must be fetched" >&2
  exit 1
}
grep -Fxq "$TEST_BASE_URL/static/css/main.test.css" "$curl_log" || {
  echo "manifest main.css must be fetched" >&2
  exit 1
}
grep -Fxq "$TEST_BASE_URL/static/js/9085.test.chunk.js" "$curl_log" || {
  echo "every lazy JavaScript asset in the manifest must be fetched" >&2
  exit 1
}
grep -Fxq "$TEST_BASE_URL/static/css/5000.test.chunk.css" "$curl_log" || {
  echo "every lazy CSS asset in the manifest must be fetched" >&2
  exit 1
}

FAKE_LAZY_JS_CODE="403"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "HTTP 403 for a lazy manifest asset must add a smoke failure" >&2
  exit 1
fi
FAKE_LAZY_JS_CODE="200"

FAKE_LAZY_CSS_CODE="403"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "HTTP 403 for a lazy CSS manifest asset must add a smoke failure" >&2
  exit 1
fi
FAKE_LAZY_CSS_CODE="200"

FAKE_MAIN_JS_CODE="403"
FAKE_MAIN_CSS_CODE="200"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "HTTP 403 for a manifest asset must add a smoke failure" >&2
  exit 1
fi

FAKE_MAIN_JS_CODE="200"
FAKE_MAIN_JS_BODY='<!doctype html><html><body>SPA fallback</body></html>'
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "HTTP 200 SPA HTML for a manifest asset must add a smoke failure" >&2
  exit 1
fi
FAKE_MAIN_JS_BODY="javascript"

FAKE_MAIN_JS_CONTENT_TYPE="text/html"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "wrong MIME type for a non-HTML JS body must add a smoke failure" >&2
  exit 1
fi
FAKE_MAIN_JS_CONTENT_TYPE="application/javascript"

FAKE_MAIN_JS_CONTENT_TYPE="application/javascriptfoo"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "MIME type prefix spoof must add a smoke failure" >&2
  exit 1
fi
FAKE_MAIN_JS_CONTENT_TYPE="Application/JavaScript; charset=utf-8"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -ne 0 ]]; then
  echo "case-insensitive JavaScript MIME with parameters must pass" >&2
  exit 1
fi
FAKE_MAIN_JS_CONTENT_TYPE="application/javascript"

FAKE_MAIN_JS_BODY=""
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "empty HTTP 200 JS asset must add a smoke failure" >&2
  exit 1
fi
FAKE_MAIN_JS_BODY="javascript"

FAKE_MANIFEST_BODY='not-json'
FAKE_MANIFEST_CODE="200"
FAKE_MAIN_JS_CODE="200"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "invalid asset-manifest.json must add a smoke failure" >&2
  exit 1
fi

FAKE_MANIFEST_BODY='{"files":{"main.js":"https://outside.example/main.js","main.css":"/static/css/main.test.css"}}'
failures=()
: > "$curl_log"
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "cross-origin manifest asset must add a smoke failure" >&2
  exit 1
fi
if grep -Fq 'outside.example' "$curl_log"; then
  echo "cross-origin manifest asset must never be fetched" >&2
  exit 1
fi

FAKE_MANIFEST_BODY='{"files":{"main.js":"/static/js/main.test.js","main.css":"/static/css/main.test.css","static/js/9085.test.chunk.js":"/static/media/9085.txt"}}'
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "a JavaScript manifest key with a non-JavaScript value must fail" >&2
  exit 1
fi

FAKE_MANIFEST_BODY='{"files":{"main.js":"/static/js/main.test.js","main.css":"/static/css/main.test.css","static/js/9085.test.chunk.js":"/static/js/main.test.js"}}'
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -ne 0 ]]; then
  echo "duplicate manifest values with a matching asset kind must be fetched once and pass" >&2
  exit 1
fi

FAKE_MANIFEST_BODY="$(python3 - <<'PY'
import json
files = {
    "main.js": "/static/js/main.test.js",
    "main.css": "/static/css/main.test.css",
}
files.update({f"static/js/chunk-{index}.js": "/static/js/main.test.js" for index in range(255)})
print(json.dumps({"files": files}, separators=(",", ":")))
PY
)"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "more than 256 raw manifest entries must fail even when values are duplicated" >&2
  exit 1
fi

FAKE_MANIFEST_BODY='{"files":{"main.js":"/static/js/main.test.js","main.css":"/static/css/main.test.css"}}'
FRONTEND_MANIFEST_MAX_BYTES=16
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "an oversized frontend manifest must fail before asset fetching" >&2
  exit 1
fi
FRONTEND_MANIFEST_MAX_BYTES=1048576

FAKE_MAIN_JS_CURL_STATUS="28"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "a timed-out asset transfer must fail even after an HTTP 200 JavaScript prefix" >&2
  exit 1
fi
FAKE_MAIN_JS_CURL_STATUS="0"

FAKE_MANIFEST_CURL_STATUS="63"
failures=()
check_frontend_assets "$TEST_BASE_URL" >/dev/null
if [[ ${#failures[@]} -eq 0 ]]; then
  echo "a truncated manifest transfer must fail even when its prefix is valid JSON" >&2
  exit 1
fi
FAKE_MANIFEST_CURL_STATUS="0"

echo "prod smoke rate-limit checks OK"
