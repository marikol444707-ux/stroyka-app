#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://stroyka26.pro}"
BASE_URL="${BASE_URL%/}"

if [[ -z "${SMOKE_EMAIL:-}" || -z "${SMOKE_PASSWORD:-}" ]]; then
  echo "Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD"
  exit 1
fi

login_payload="$(python3 -c 'import json,os; print(json.dumps({"email": os.environ["SMOKE_EMAIL"], "password": os.environ["SMOKE_PASSWORD"]}, ensure_ascii=False))')"
login_body="$(curl -skS -X POST "$BASE_URL/login" -H 'Content-Type: application/json' -d "$login_payload" || true)"
token="$(printf '%s' "$login_body" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("authToken",""))' 2>/dev/null || true)"

if [[ -z "$token" ]]; then
  echo "FAIL login"
  exit 1
fi

echo "OK   login"

paths=(
  "/projects"
  "/users"
  "/staff"
  "/estimates"
  "/materials"
  "/warehouse-main"
  "/warehouse-invoices"
  "/supply-requests"
  "/project-payments"
  "/expense-reports"
  "/company-documents"
  "/hidden-works-acts"
  "/material-inspection"
  "/cable-journal"
  "/ai-tasks"
  "/system-status"
)

failed=0
for path in "${paths[@]}"; do
  code="$(curl -skS -o /dev/null -w '%{http_code}' "$BASE_URL$path" -H "Authorization: Bearer $token" || true)"
  if [[ "$code" == "200" ]]; then
    echo "OK   $path $code"
  else
    echo "FAIL $path got=$code expected=200"
    failed=1
  fi
done

if [[ "$failed" == "1" ]]; then
  exit 1
fi

echo "Role smoke OK"
