#!/bin/bash
set -euo pipefail

APP_ROOT="${STROYKA_APP_ROOT:-/var/www/stroyka-app}"
DEPLOY_LOCK_FILE="${DEPLOY_LOCK_FILE:-/var/lock/stroyka-deploy.lock}"
AGENT_JOB_WORKER_UNIT="stroyka-agent-job-worker.service"

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
(
  cd "$APP_ROOT/backend"
  PYTHONPATH=. PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache \
    python3 -c 'import features.estimate_row_transfer'
)
if ! python3 -c 'import alembic, psycopg2, sqlalchemy'; then
  echo "Не установлены Python-зависимости. Выполните: python3 -m pip install --break-system-packages -r requirements.txt" >&2
  exit 1
fi
npm ci

FRONTEND_BUILD_DIR="$(mktemp -d "$APP_ROOT/.frontend-build.XXXXXX")"
cleanup_frontend_build() {
  rm -rf -- "$FRONTEND_BUILD_DIR"
}
trap cleanup_frontend_build EXIT

STROYKA_SERVICE_ENVIRONMENT="$(
  systemctl show stroyka -p Environment --value --no-pager
)"
FRONTEND_BUILD_ENV_OUTPUT="$(
  bash scripts/resolve-frontend-build-env.sh "$STROYKA_SERVICE_ENVIRONMENT"
)"
FRONTEND_BUILD_ENV=()
while IFS= read -r build_variable; do
  if [ -n "$build_variable" ]; then
    FRONTEND_BUILD_ENV+=("$build_variable")
  fi
done <<< "$FRONTEND_BUILD_ENV_OUTPUT"
if [ "${#FRONTEND_BUILD_ENV[@]}" -gt 0 ]; then
  echo "Frontend A10 включён для backend allowlist."
fi
env "${FRONTEND_BUILD_ENV[@]}" BUILD_PATH="$FRONTEND_BUILD_DIR" npm run build
echo "Применение миграций базы данных..."
PGOPTIONS="-c lock_timeout=5000 -c statement_timeout=60000" \
  python3 -m alembic upgrade head
systemctl restart stroyka
systemctl is-active --quiet stroyka
if systemctl is-active --quiet "$AGENT_JOB_WORKER_UNIT"; then
  echo "Перезапуск фонового работника..."
  systemctl restart "$AGENT_JOB_WORKER_UNIT"
  systemctl is-active --quiet "$AGENT_JOB_WORKER_UNIT"
fi
bash scripts/publish-frontend.sh "$FRONTEND_BUILD_DIR" "$APP_ROOT/build"
bash scripts/prod-smoke-check.sh
echo "Деплой завершён!"
