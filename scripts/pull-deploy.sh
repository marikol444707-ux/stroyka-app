#!/bin/bash
# On the server: if origin/main moved and CI is green, run deploy.sh.
# A busy lock or an unchanged commit exits 0 with no output.
# GitHub is asked at most once. A token is optional and is never printed.
set -euo pipefail

APP_ROOT="${STROYKA_APP_ROOT:-/var/www/stroyka-app}"
DEPLOY_LOCK_FILE="${DEPLOY_LOCK_FILE:-/var/lock/stroyka-deploy.lock}"
STATE_DIR="${STROYKA_DEPLOY_STATE_DIR:-/var/lib/stroyka-deploy}"
TOKEN_FILE="${STROYKA_GITHUB_TOKEN_FILE:-/etc/stroyka/pull-deploy.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl_config_file=""
api_body_file=""
deploy_log=""
deploy_status=0
health_status=0

# The EXIT trap calls this on every path. One direct call keeps ShellCheck
# from treating the function as unused.
# shellcheck disable=SC2317,SC2329
cleanup() {
  if [[ -n "${curl_config_file}" ]]; then
    rm -f -- "$curl_config_file"
  fi
  if [[ -n "${api_body_file}" ]]; then
    rm -f -- "$api_body_file"
  fi
  if [[ -n "${deploy_log}" ]]; then
    rm -f -- "$deploy_log"
  fi
}
trap cleanup EXIT

export GIT_TERMINAL_PROMPT=0

record_failed() {
  local sha="$1"
  local tmp
  install -d -m 0700 "$STATE_DIR"
  tmp="$(mktemp "$STATE_DIR/failed-sha.XXXXXX")"
  printf '%s\n' "$sha" > "$tmp"
  chmod 600 "$tmp"
  mv -f -- "$tmp" "$STATE_DIR/failed-sha"
}

remembered_failure() {
  local file="$STATE_DIR/failed-sha"
  local value
  if [[ ! -f "$file" ]]; then
    printf ''
    return 0
  fi
  value="$(tr -d '[:space:]' < "$file")"
  if [[ "$value" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s' "$value"
  fi
}

prepare_github_auth() {
  local status
  local -a args
  curl_config_file="$(mktemp)"
  chmod 600 "$curl_config_file"
  args=(--curl-config "$curl_config_file")
  if [[ -z "${GITHUB_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
    args+=("$TOKEN_FILE")
  fi
  set +e
  status="$(python3 "$SCRIPT_DIR/pull-deploy-ci.py" "${args[@]}")"
  set -e
  case "$status" in
    ready)
      ;;
    absent|empty)
      rm -f -- "$curl_config_file"
      curl_config_file=""
      ;;
    open)
      rm -f -- "$curl_config_file"
      curl_config_file=""
      echo "Файл токена GitHub доступен не только владельцу. Работаю без токена."
      ;;
    owner)
      rm -f -- "$curl_config_file"
      curl_config_file=""
      echo "Файл токена GitHub принадлежит не тому пользователю. Работаю без токена."
      ;;
    *)
      rm -f -- "$curl_config_file"
      curl_config_file=""
      echo "Токен GitHub не использован: значение выглядит некорректно."
      ;;
  esac
  unset GITHUB_TOKEN || true
}

fetch_ci_payload() {
  local url="$1"
  local http_code=""
  local curl_status=0
  local -a curl_args
  api_body_file="$(mktemp)"
  curl_args=(
    -sS
    --max-time 20
    --retry 0
    -o "$api_body_file"
    -w "%{http_code}"
    -H "Accept: application/vnd.github+json"
    -H "X-GitHub-Api-Version: 2022-11-28"
    -H "User-Agent: stroyka-pull-deploy"
  )
  if [[ -n "$curl_config_file" ]]; then
    curl_args+=(--config "$curl_config_file")
  fi
  set +e
  http_code="$(curl "${curl_args[@]}" "$url")"
  curl_status=$?
  set -e
  if [[ -n "$curl_config_file" ]]; then
    rm -f -- "$curl_config_file"
    curl_config_file=""
  fi
  if [[ "$curl_status" -ne 0 || "$http_code" != "200" ]]; then
    echo "GitHub API недоступен (HTTP ${http_code:-нет}). Повторю в следующий запуск."
    return 1
  fi
  return 0
}

run_deploy() {
  local sha="$1"
  local mode="${2:-deploy}"
  if [[ -n "$deploy_log" ]]; then
    rm -f -- "$deploy_log"
  fi
  deploy_log="$(mktemp)"
  set +e
  set +o pipefail
  if [[ "$mode" == "apply-only" ]]; then
    STROYKA_EXTERNAL_LOCK=1 bash "$SCRIPT_DIR/auto-deploy-remote.sh" --apply-only "$sha" | tee "$deploy_log"
    deploy_status=${PIPESTATUS[0]}
  else
    STROYKA_EXTERNAL_LOCK=1 bash "$SCRIPT_DIR/auto-deploy-remote.sh" "$sha" | tee "$deploy_log"
    deploy_status=${PIPESTATUS[0]}
  fi
  set -o pipefail
  set -e
}

run_health() {
  local sha="$1"
  local attempts="${STROYKA_HEALTH_ATTEMPTS:-12}"
  local delay="${STROYKA_HEALTH_DELAY:-5}"
  set +e
  if [[ -n "${STROYKA_HEALTH_CHECK:-}" ]]; then
    "$STROYKA_HEALTH_CHECK" "$sha"
    health_status=$?
  else
    local -a health_args
    health_args=(--sha "$sha" --attempts "$attempts" --delay "$delay")
    if [[ -n "${STROYKA_HEALTH_URL:-}" ]]; then
      health_args+=(--url "$STROYKA_HEALTH_URL")
    fi
    python3 "$APP_ROOT/scripts/check-deploy-health.py" "${health_args[@]}"
    health_status=$?
  fi
  set -e
}

finish_rollback() {
  local failed_sha="$1"
  local rollback_sha="$2"
  local now=""
  echo "Проверяю откат на ${rollback_sha:0:12}."
  now="$(git rev-parse HEAD)"
  if [[ "$now" != "$rollback_sha" ]]; then
    run_deploy "$rollback_sha" apply-only
    if [[ "$deploy_status" -ne 0 ]]; then
      echo "Откат на ${rollback_sha:0:12} не удался. Нужна ручная проверка." >&2
    fi
  fi
  run_health "$rollback_sha"
  if [[ "$health_status" -ne 0 ]]; then
    echo "Сайт после отката не подтвердил ${rollback_sha:0:12}." >&2
  fi
  record_failed "$failed_sha"
  exit 1
}

if [[ ! -d "$APP_ROOT" ]]; then
  echo "Нет каталога приложения." >&2
  exit 1
fi
cd "$APP_ROOT"

if ! command -v flock >/dev/null 2>&1; then
  echo "На сервере нет команды flock." >&2
  exit 1
fi
if ! exec 9>"$DEPLOY_LOCK_FILE"; then
  echo "Не удалось открыть блокировку выкладки." >&2
  exit 1
fi
if ! flock -n 9; then
  exit 0
fi

if ! git fetch --quiet origin main; then
  echo "Не удалось скачать origin/main. Повторю в следующий запуск." >&2
  exit 1
fi

current=""
target=""
if ! current="$(git rev-parse HEAD)" || ! target="$(git rev-parse origin/main)"; then
  echo "Не удалось прочитать коммит." >&2
  exit 1
fi
current="${current//[[:space:]]/}"
target="${target//[[:space:]]/}"
current="${current,,}"
target="${target,,}"
if [[ ! "$current" =~ ^[0-9a-f]{40}$ || ! "$target" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Коммит выглядит некорректно." >&2
  exit 1
fi
if [[ "$current" == "$target" ]]; then
  exit 0
fi
if ! git merge-base --is-ancestor "$current" "$target"; then
  echo "origin/main ${target:0:12} не продолжает установленный ${current:0:12}. Сайт не меняю."
  exit 0
fi
if [[ "$(remembered_failure)" == "$target" ]]; then
  exit 0
fi

repo="${STROYKA_GITHUB_REPO:-}"
if [[ -z "$repo" ]]; then
  remote_url="$(git remote get-url origin)"
  if ! repo="$(python3 "$SCRIPT_DIR/pull-deploy-ci.py" --repo "$remote_url")"; then
    echo "Не удалось понять адрес origin. Нужен github.com/owner/repo." >&2
    exit 1
  fi
fi
if [[ ! "$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
  echo "Некорректное имя репозитория." >&2
  exit 1
fi

prepare_github_auth
ci_url="https://api.github.com/repos/${repo}/actions/workflows/ci.yml/runs?head_sha=${target}&per_page=10"
if ! fetch_ci_payload "$ci_url"; then
  exit 0
fi

ci_status=0
set +e
python3 "$SCRIPT_DIR/pull-deploy-ci.py" "$target" "$api_body_file"
ci_status=$?
set -e
case "$ci_status" in
  0)
    ;;
  10)
    exit 0
    ;;
  11)
    record_failed "$target"
    exit 0
    ;;
  *)
    exit 0
    ;;
esac

if [[ ! -f "$APP_ROOT/scripts/check-deploy-health.py" && -z "${STROYKA_HEALTH_CHECK:-}" ]]; then
  echo "Не найден скрипт проверки здоровья." >&2
  exit 1
fi

rollback_sha="$current"
echo "Выкладываю ${target:0:12} (сейчас ${rollback_sha:0:12})."
run_deploy "$target"
if [[ "$deploy_status" -eq 0 ]] && grep -qx 'STROYKA_SKIP=newer' "$deploy_log"; then
  echo "На сервере уже более новый коммит. ${target:0:12} не выкладываю."
  exit 0
fi
if [[ "$deploy_status" -ne 0 ]]; then
  echo "Выкладка ${target:0:12} не удалась." >&2
  finish_rollback "$target" "$rollback_sha"
fi

run_health "$target"
if [[ "$health_status" -ne 0 ]]; then
  echo "Сайт не подтвердил ${target:0:12}. Возвращаю ${rollback_sha:0:12}." >&2
  finish_rollback "$target" "$rollback_sha"
fi

echo "Выложено: $target"
cleanup
exit 0
