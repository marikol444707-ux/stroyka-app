#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$APP_DIR/backend/.env}"
UPLOADS_DIR="${UPLOADS_DIR:-uploads}"
LEGACY_UPLOADS_DIR="${LEGACY_UPLOADS_DIR:-backend/uploads}"
REQUIRE_S3="${REQUIRE_S3:-0}"

failures=0

note() {
  printf '%s\n' "$*"
}

fail() {
  note "FAIL $*"
  failures=$((failures + 1))
}

get_env_value() {
  local name="$1"
  local value="${!name:-}"
  local line
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
    return
  fi
  if [[ -f "$ENV_FILE" ]]; then
    line="$(grep -E "^${name}=" "$ENV_FILE" 2>/dev/null | tail -n 1 || true)"
    if [[ -n "$line" ]]; then
      value="${line#*=}"
      value="${value%\"}"
      value="${value#\"}"
      value="${value%\'}"
      value="${value#\'}"
    fi
  fi
  printf '%s\n' "$value"
}

dir_stats_text() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    printf '%s\n' "missing"
    return
  fi
  local files bytes
  files="$(find "$path" -type f 2>/dev/null | wc -l | tr -d ' ')"
  bytes="$(du -sh "$path" 2>/dev/null | awk '{print $1}')"
  printf '%s\n' "${files} files, ${bytes:-0}"
}

note "S3 uploads readiness check"
note "APP_DIR=$APP_DIR"
note "ENV_FILE=$ENV_FILE"

storage_backend="$(get_env_value STORAGE_BACKEND)"
storage_backend="${storage_backend:-local}"
s3_endpoint="$(get_env_value S3_ENDPOINT_URL)"
if [[ -z "$s3_endpoint" ]]; then
  s3_endpoint="$(get_env_value S3_ENDPOINT)"
fi
s3_bucket="$(get_env_value S3_BUCKET)"
s3_region="$(get_env_value S3_REGION)"
s3_region="${s3_region:-ru-central1}"
s3_access_key="$(get_env_value S3_ACCESS_KEY_ID)"
if [[ -z "$s3_access_key" ]]; then
  s3_access_key="$(get_env_value AWS_ACCESS_KEY_ID)"
fi
s3_secret_key="$(get_env_value S3_SECRET_ACCESS_KEY)"
if [[ -z "$s3_secret_key" ]]; then
  s3_secret_key="$(get_env_value AWS_SECRET_ACCESS_KEY)"
fi
s3_prefix="$(get_env_value S3_PREFIX)"
s3_prefix="${s3_prefix:-uploads}"

note "storage backend: $storage_backend"
note "s3 region: $s3_region"
note "s3 prefix: $s3_prefix"

uploads_path="$APP_DIR/$UPLOADS_DIR"
legacy_uploads_path="$APP_DIR/$LEGACY_UPLOADS_DIR"
note "uploads current: $uploads_path -> $(dir_stats_text "$uploads_path")"
if [[ "$LEGACY_UPLOADS_DIR" != "$UPLOADS_DIR" ]]; then
  if [[ -L "$legacy_uploads_path" ]]; then
    note "legacy uploads path: symlink -> $(readlink "$legacy_uploads_path")"
  elif [[ -d "$legacy_uploads_path" ]]; then
    note "legacy uploads path: directory -> $(dir_stats_text "$legacy_uploads_path")"
  else
    note "legacy uploads path: missing"
  fi
fi

missing=()
[[ -z "$s3_endpoint" ]] && missing+=("S3_ENDPOINT_URL")
[[ -z "$s3_bucket" ]] && missing+=("S3_BUCKET")
[[ -z "$s3_access_key" ]] && missing+=("S3_ACCESS_KEY_ID")
[[ -z "$s3_secret_key" ]] && missing+=("S3_SECRET_ACCESS_KEY")

if [[ "$storage_backend" == "s3" || "$REQUIRE_S3" == "1" ]]; then
  if [[ "${#missing[@]}" -gt 0 ]]; then
    fail "S3 is not ready, missing: ${missing[*]}"
  else
    note "OK S3 config is complete enough for uploads"
  fi
else
  note "INFO S3 is optional now. Set REQUIRE_S3=1 when preparing the real migration."
fi

if [[ "$storage_backend" == "s3" && "${#missing[@]}" -gt 0 ]]; then
  note "INFO STORAGE_BACKEND=s3 is set, but uploads will still fall back to local until all S3 variables are configured."
fi

if [[ "$failures" -gt 0 ]]; then
  note "S3 uploads readiness failed: $failures issue(s)"
  exit 1
fi

note "S3 uploads readiness OK"
