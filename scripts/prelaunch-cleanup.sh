#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-stroyka}"
KEEP_EMAIL="${KEEP_EMAIL:-admin@stroyka.ru}"
DRY_RUN="${DRY_RUN:-1}"
CONFIRM="${CONFIRM:-}"
RESET_PRICELISTS="${RESET_PRICELISTS:-0}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/stroyka}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/prelaunch-cleanup.sql"

if [[ ! "$KEEP_EMAIL" =~ ^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+$ ]]; then
  echo "ERROR: KEEP_EMAIL looks unsafe: $KEEP_EMAIL" >&2
  exit 1
fi

if [[ "$DRY_RUN" != "1" && "$CONFIRM" != "CLEAN_STROYKA_PROD" ]]; then
  echo "ERROR: destructive cleanup requires CONFIRM=CLEAN_STROYKA_PROD" >&2
  echo "Run dry preview first:" >&2
  echo "  KEEP_EMAIL='$KEEP_EMAIL' DRY_RUN=1 $0" >&2
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
echo "KEEP_EMAIL=$KEEP_EMAIL"
echo "DRY_RUN=$DRY_RUN"
echo "RESET_PRICELISTS=$RESET_PRICELISTS"

if [[ "$DRY_RUN" != "1" ]]; then
  mkdir -p "$BACKUP_DIR"
  backup_file="$BACKUP_DIR/stroyka_prelaunch_$(date +%Y%m%d_%H%M%S).sql.gz"
  echo "Creating backup: $backup_file"
  run_postgres pg_dump "$DB_NAME" | gzip > "$backup_file"
  echo "Backup done: $(du -h "$backup_file" | cut -f1)"
fi

run_postgres psql \
  -v ON_ERROR_STOP=1 \
  -v "keep_email=$KEEP_EMAIL" \
  -v "dry_run=$DRY_RUN" \
  -v "reset_pricelists=$RESET_PRICELISTS" \
  -d "$DB_NAME" \
  -f "$SQL_FILE"
