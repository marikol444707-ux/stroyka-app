#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stroyka26.pro}"
BASE_URL="${BASE_URL%/}"
FAILURES=()

check_json() {
  local name="$1"
  local path="$2"
  local predicate="$3"
  local body
  body="$(curl -skS "$BASE_URL$path" || true)"
  if printf '%s' "$body" | python3 -c "$predicate" >/dev/null 2>&1; then
    echo "OK   $name $path"
    return 0
  fi
  echo "FAIL $name $path"
  if printf '%s' "$body" | head -c 120 | grep -qiE '<!doctype|<html'; then
    echo "INFO $path returned HTML, nginx is falling back to SPA index.html"
  else
    echo "INFO $path body: $(printf '%s' "$body" | head -c 180)"
  fi
  FAILURES+=("$name")
}

check_not_spa() {
  local name="$1"
  local path="$2"
  local expected_codes="$3"
  local body
  local code
  body="$(mktemp)"
  code="$(curl -skS -o "$body" -w '%{http_code}' "$BASE_URL$path" || true)"
  if [[ " $expected_codes " == *" $code "* ]] && ! head -c 200 "$body" | grep -qiE '<!doctype|<html'; then
    echo "OK   $name $path $code"
    rm -f "$body"
    return 0
  fi
  echo "FAIL $name $path got=$code expected=$expected_codes"
  if head -c 200 "$body" | grep -qiE '<!doctype|<html'; then
    echo "INFO $path returned HTML, nginx is falling back to SPA index.html"
  else
    echo "INFO $path body: $(head -c 180 "$body")"
  fi
  rm -f "$body"
  FAILURES+=("$name")
}

echo "Public API proxy check: $BASE_URL"
check_json "site pricing" "/site/pricing" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data.get("rules"), list) else 1)'
check_json "site projects" "/site/projects" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)'
check_not_spa "site leads route" "/site/leads" "405"
check_not_spa "site price rules route" "/site-price-rules" "401 403"
check_not_spa "estimate reconciliations route" "/estimate-reconciliations" "401 403"
check_not_spa "estimate reconciliation items route" "/estimate-reconciliation-items/1" "401 403 405"

if (( ${#FAILURES[@]} > 0 )); then
  echo "Public API proxy check failed:"
  printf ' - %s\n' "${FAILURES[@]}"
  exit 1
fi

echo "Public API proxy check OK"
