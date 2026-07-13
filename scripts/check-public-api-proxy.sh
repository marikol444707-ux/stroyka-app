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
  if [[ " $expected_codes " == *" $code "* ]]; then
    if [[ "$code" == "429" ]] || ! head -c 200 "$body" | grep -qiE '<!doctype|<html'; then
      echo "OK   $name $path $code"
      rm -f "$body"
      return 0
    fi
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

check_post_not_spa() {
  local name="$1"
  local path="$2"
  local expected_codes="$3"
  local body
  local code
  body="$(mktemp)"
  code="$(curl -skS -X POST -o "$body" -w '%{http_code}' "$BASE_URL$path" || true)"
  if [[ " $expected_codes " == *" $code "* ]] && ! head -c 200 "$body" | grep -qiE '<!doctype|<html'; then
    echo "OK   $name $path $code"
    rm -f "$body"
    return 0
  fi
  echo "FAIL $name $path got=$code expected=$expected_codes"
  if head -c 200 "$body" | grep -qiE '<!doctype|<html'; then
    echo "INFO $path returned HTML instead of backend JSON"
  else
    echo "INFO $path body: $(head -c 180 "$body")"
  fi
  rm -f "$body"
  FAILURES+=("$name")
}

echo "Public API proxy check: $BASE_URL"
check_json "site pricing" "/site/pricing" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data.get("rules"), list) else 1)'
check_json "site projects" "/site/projects" 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)'
check_not_spa "site leads route" "/site/leads" "405 429"
check_post_not_spa "site lead files route" "/site/lead-files" "422 429"
check_not_spa "site price rules route" "/site-price-rules" "401 403"
check_not_spa "estimate reconciliations route" "/estimate-reconciliations" "401 403"
check_not_spa "estimate reconciliation items route" "/estimate-reconciliation-items/1" "401 403 405"
check_not_spa "tenant files route" "/tenant-files/1" "401 403"
check_not_spa "tenant file content route" "/tenant-files/1/content" "401 403"
check_not_spa "company messages route" "/messages" "401 403"
check_not_spa "project AI summary route" "/project-ai-summary/smoke" "401 403"
check_not_spa "project AI summary post route" "/project-ai-summary" "405"
check_not_spa "AI tasks route" "/ai-tasks" "401 403"
check_not_spa "assignments route" "/assignments" "401 403"
check_not_spa "AI task reports route" "/ai-tasks/1/reports" "401 403"
check_not_spa "AI control single run route" "/ai-control/run" "405"
check_not_spa "AI findings generate route" "/ai-findings/generate" "405"
check_not_spa "AI control run-all route" "/ai-control/run-all" "405"
check_not_spa "messenger channels route" "/messenger-channels" "401 403"
check_post_not_spa "messenger channels post route" "/messenger-channels" "401 403 422"

if (( ${#FAILURES[@]} > 0 )); then
  echo "Public API proxy check failed:"
  printf ' - %s\n' "${FAILURES[@]}"
  exit 1
fi

echo "Public API proxy check OK"
