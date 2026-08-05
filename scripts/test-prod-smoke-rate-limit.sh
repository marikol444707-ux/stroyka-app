#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
definitions="$(sed '/^echo "Smoke-check:/,$d' "$ROOT/scripts/prod-smoke-check.sh")"
definitions_file="$(mktemp)"
trap 'rm -f "$definitions_file"' EXIT
printf '%s\n' "$definitions" > "$definitions_file"
source "$definitions_file"

FAKE_CODE=""
FAKE_BODY=""

curl() {
  local body_file=""
  while (($#)); do
    if [[ "$1" == "-o" ]]; then
      body_file="$2"
      shift 2
    else
      shift
    fi
  done
  printf '%s' "$FAKE_BODY" > "$body_file"
  printf '%s' "$FAKE_CODE"
}

failures=()
FAKE_CODE="429"
FAKE_BODY='<html><body>rate limited</body></html>'
check_post_not_spa_fallback "rate limited post" "https://example.test/route" "422 429" >/dev/null
[[ ${#failures[@]} -eq 0 ]]

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

echo "prod smoke rate-limit checks OK"
