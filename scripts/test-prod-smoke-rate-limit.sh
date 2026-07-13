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

echo "prod smoke rate-limit checks OK"
