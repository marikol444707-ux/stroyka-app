#!/bin/bash
set -euo pipefail

service_environment="${1-}"
http_enabled=""
company_ids=""

for entry in $service_environment; do
  entry="${entry#\"}"
  entry="${entry%\"}"
  case "$entry" in
    ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=*)
      http_enabled="${entry#ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=}"
      ;;
    ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=*)
      company_ids="${entry#ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=}"
      ;;
  esac
done

if [ "$http_enabled" != "true" ]; then
  exit 0
fi

if ! [[ "$company_ids" =~ ^[1-9][0-9]*(,[1-9][0-9]*){0,99}$ ]]; then
  echo "Некорректный ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS: frontend A10 не собран" >&2
  exit 2
fi

seen=","
IFS=',' read -r -a parsed_company_ids <<< "$company_ids"
for company_id in "${parsed_company_ids[@]}"; do
  if [ "${#company_id}" -gt 16 ] ||
     { [ "${#company_id}" -eq 16 ] && [[ "$company_id" > "9007199254740991" ]]; }; then
    echo "ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS выходит за безопасный диапазон" >&2
    exit 2
  fi
  case "$seen" in
    *",$company_id,"*)
      echo "ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS содержит повтор" >&2
      exit 2
      ;;
  esac
  seen="${seen}${company_id},"
done

printf '%s\n' \
  'REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED=true' \
  "REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS=$company_ids"
