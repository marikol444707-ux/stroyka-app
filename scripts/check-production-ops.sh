#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/stroyka}"
UPLOADS_DIR="${UPLOADS_DIR:-uploads}"
LEGACY_UPLOADS_DIR="${LEGACY_UPLOADS_DIR:-backend/uploads}"
STRICT="${STRICT:-0}"

failures=0

note() {
  printf '%s\n' "$*"
}

warn() {
  note "WARN $*"
  if [[ "$STRICT" == "1" ]]; then
    failures=$((failures + 1))
  fi
}

fail() {
  note "FAIL $*"
  failures=$((failures + 1))
}

has_text() {
  local pattern="$1"
  local path="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -q "$pattern" "$path"
  else
    grep -Eq "$pattern" "$path"
  fi
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

note "Production ops check"
note "APP_DIR=$APP_DIR"
note "BACKUP_DIR=$BACKUP_DIR"
note "UPLOADS_DIR=$UPLOADS_DIR"
note "LEGACY_UPLOADS_DIR=$LEGACY_UPLOADS_DIR"

if [[ -d "$BACKUP_DIR" ]]; then
  latest_backup="$(find "$BACKUP_DIR" -maxdepth 1 -type f 2>/dev/null | sort | tail -1 || true)"
  if [[ -n "$latest_backup" ]]; then
    note "OK backup latest: $(basename "$latest_backup") ($(du -h "$latest_backup" | awk '{print $1}'))"
  else
    warn "backup directory exists, but no backup files found"
  fi
else
  warn "backup directory not found: $BACKUP_DIR"
fi

uploads_path="$APP_DIR/$UPLOADS_DIR"
legacy_uploads_path="$APP_DIR/$LEGACY_UPLOADS_DIR"
if [[ -d "$uploads_path" ]]; then
  note "OK uploads current: $uploads_path -> $(dir_stats_text "$uploads_path")"
else
  note "INFO uploads current directory not found: $uploads_path"
fi
if [[ "$LEGACY_UPLOADS_DIR" != "$UPLOADS_DIR" && -d "$legacy_uploads_path" ]]; then
  legacy_files="$(find "$legacy_uploads_path" -type f 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "${legacy_files:-0}" != "0" ]]; then
    warn "legacy uploads directory has files: $legacy_uploads_path ($(dir_stats_text "$legacy_uploads_path"))"
  fi
fi

if [[ -f "$APP_DIR/ops-nginx-stroyka-public-api.conf" ]]; then
  if has_text "limit_req" "$APP_DIR/ops-nginx-stroyka-public-api.conf"; then
    note "OK nginx public API snippet has limit_req"
  else
    fail "ops-nginx-stroyka-public-api.conf has no limit_req"
  fi
else
  fail "missing ops-nginx-stroyka-public-api.conf"
fi

if [[ -f "$APP_DIR/docs/ddos-and-ai-indexing.md" ]]; then
  if has_text "limit_req_zone" "$APP_DIR/docs/ddos-and-ai-indexing.md" && has_text "client_max_body_size" "$APP_DIR/docs/ddos-and-ai-indexing.md"; then
    note "OK DDoS/nginx doc includes rate zones and upload limit"
  else
    fail "docs/ddos-and-ai-indexing.md misses rate limit or upload limit guidance"
  fi
else
  fail "missing docs/ddos-and-ai-indexing.md"
fi

if [[ "$failures" -gt 0 ]]; then
  note "Production ops check failed: $failures issue(s)"
  exit 1
fi

note "Production ops check OK"
