#!/bin/bash
set -euo pipefail

APP_ROOT="${STROYKA_APP_ROOT:-/var/www/stroyka-app}"
DEPLOY_LOCK_FILE="${DEPLOY_LOCK_FILE:-/var/lock/stroyka-deploy.lock}"

exec 9>"$DEPLOY_LOCK_FILE"
if ! flock -n 9; then
  echo "Другой деплой уже выполняется. Повторите позже." >&2
  exit 1
fi

cd "$APP_ROOT"
git reset --hard HEAD
git pull --ff-only
echo "HEAD: $(git rev-parse --short HEAD)"
PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py
npm ci

FRONTEND_BUILD_DIR="$(mktemp -d "$APP_ROOT/.frontend-build.XXXXXX")"
cleanup_frontend_build() {
  rm -rf -- "$FRONTEND_BUILD_DIR"
}
trap cleanup_frontend_build EXIT

BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build
systemctl restart stroyka
systemctl is-active --quiet stroyka
bash scripts/publish-frontend.sh "$FRONTEND_BUILD_DIR" "$APP_ROOT/build"
bash scripts/prod-smoke-check.sh
echo "Деплой завершён!"
