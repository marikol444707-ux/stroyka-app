#!/bin/bash
set -euo pipefail

service_environment="${1-}"
backend_env_path="${2-}"
http_enabled=""
company_ids=""
http_was_set=false
company_ids_was_set=false

for entry in $service_environment; do
  entry="${entry#\"}"
  entry="${entry%\"}"
  case "$entry" in
    ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=*)
      http_enabled="${entry#ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=}"
      http_was_set=true
      ;;
    ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=*)
      company_ids="${entry#ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=}"
      company_ids_was_set=true
      ;;
  esac
done

if [ -n "$backend_env_path" ] && [ -f "$backend_env_path" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    case "$line" in
      ""|\#*)
        continue
        ;;
      *=*)
        ;;
      *)
        continue
        ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value#\"}"
    value="${value%\"}"
    value="${value#\'}"
    value="${value%\'}"

    case "$key" in
      ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED)
        if [ "$http_was_set" = false ]; then
          http_enabled="$value"
          http_was_set=true
        fi
        ;;
      ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS)
        if [ "$company_ids_was_set" = false ]; then
          company_ids="$value"
          company_ids_was_set=true
        fi
        ;;
    esac
  done < "$backend_env_path"
fi

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
