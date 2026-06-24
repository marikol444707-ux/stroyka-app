#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-stroyka}"
DRY_RUN="${DRY_RUN:-1}"
CONFIRM="${CONFIRM:-}"
RESET_UPLOADS="${RESET_UPLOADS:-0}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/stroyka}"
UPLOADS_DIR="${UPLOADS_DIR:-backend/uploads}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_FILE="$SCRIPT_DIR/live-work-reset.sql"

if [[ "$DRY_RUN" != "1" && "$CONFIRM" != "LIVE_WORK_RESET" ]]; then
  echo "ERROR: set CONFIRM=LIVE_WORK_RESET and DRY_RUN=0 to run destructive cleanup." >&2
  exit 1
fi

run_postgres() {
  local -a cmd=("$@")
  if [[ "$(id -u)" == "0" ]]; then
    su - postgres -c "$(printf '%q ' "${cmd[@]}")"
  else
    "${cmd[@]}"
  fi
}

echo "DB_NAME=$DB_NAME"
echo "DRY_RUN=$DRY_RUN"
echo "RESET_UPLOADS=$RESET_UPLOADS"

if [[ "$DRY_RUN" != "1" ]]; then
  mkdir -p "$BACKUP_DIR"
  backup_file="$BACKUP_DIR/stroyka_live_work_reset_$(date +%Y%m%d_%H%M%S).sql.gz"
  echo "Creating database backup: $backup_file"
  run_postgres pg_dump "$DB_NAME" | gzip > "$backup_file"
  echo "Database backup done: $(du -h "$backup_file" | cut -f1)"
fi

dry_run_bool=false
if [[ "$DRY_RUN" == "1" ]]; then
  dry_run_bool=true
fi

confirmed=false
if [[ "$CONFIRM" == "LIVE_WORK_RESET" ]]; then
  confirmed=true
fi

run_postgres psql \
  -v ON_ERROR_STOP=1 \
  -v "dry_run=$dry_run_bool" \
  -v "confirmed=$confirmed" \
  -v "reset_uploads=$RESET_UPLOADS" \
  -d "$DB_NAME" \
  -f "$SQL_FILE"

if [[ "$DRY_RUN" != "1" && "$RESET_UPLOADS" == "1" ]]; then
  uploads_path="$APP_DIR/$UPLOADS_DIR"
  if [[ -d "$uploads_path" ]]; then
    upload_backup_dir="$BACKUP_DIR/uploads_live_work_reset_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$upload_backup_dir"
    echo "Moving uploads to backup: $upload_backup_dir"
    find "$uploads_path" -mindepth 1 -maxdepth 1 -exec mv {} "$upload_backup_dir"/ \;
    echo "Uploads moved. Restore source: $upload_backup_dir"
  else
    echo "Uploads directory not found, skipped: $uploads_path"
  fi
fi
