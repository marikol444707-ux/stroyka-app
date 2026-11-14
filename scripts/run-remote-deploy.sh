#!/bin/bash
# SSH to the server and run scripts/auto-deploy-remote.sh there.
# The normal mode records the result for later health/rollback steps and does
# not fail the Actions step by itself. --apply-only returns the remote status.
set -euo pipefail

apply_only=0
target="${TARGET_SHA:-}"
if [[ "${1:-}" == "--apply-only" ]]; then
  apply_only=1
  target="${2:-}"
elif [[ -n "${1:-}" ]]; then
  target="$1"
fi

if [[ ! "$target" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ОШИБКА: не передан полный SHA коммита." >&2
  exit 1
fi

for name in SSH_KEY SSH_KNOWN_HOSTS SSH_PORT SSH_USER SSH_HOST; do
  if [[ -z "${!name:-}" ]]; then
    echo "ОШИБКА: SSH не подготовлен (${name})." >&2
    exit 1
  fi
done
if [[ ! -f "$SSH_KEY" || ! -f "$SSH_KNOWN_HOSTS" ]]; then
  echo "ОШИБКА: файлы SSH не найдены." >&2
  exit 1
fi
if [[ ! "$SSH_PORT" =~ ^[0-9]{1,5}$ ]]; then
  echo "ОШИБКА: порт SSH некорректен." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
remote="$script_dir/auto-deploy-remote.sh"
output="$(mktemp)"
trap 'rm -f "$output"' EXIT

set +e
set +o pipefail
if [[ "$apply_only" -eq 1 ]]; then
  ssh \
    -i "$SSH_KEY" \
    -p "$SSH_PORT" \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$SSH_KNOWN_HOSTS" \
    -o GlobalKnownHostsFile=/dev/null \
    -o ConnectTimeout=20 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=40 \
    -o LogLevel=ERROR \
    -- \
    "${SSH_USER}@${SSH_HOST}" \
    bash -s -- --apply-only "$target" < "$remote" | tee "$output"
else
  ssh \
    -i "$SSH_KEY" \
    -p "$SSH_PORT" \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$SSH_KNOWN_HOSTS" \
    -o GlobalKnownHostsFile=/dev/null \
    -o ConnectTimeout=20 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=40 \
    -o LogLevel=ERROR \
    -- \
    "${SSH_USER}@${SSH_HOST}" \
    bash -s -- "$target" < "$remote" | tee "$output"
fi
status=${PIPESTATUS[0]}
set -o pipefail
set -e

if [[ "$apply_only" -eq 1 ]]; then
  exit "$status"
fi

if [[ -z "${GITHUB_OUTPUT:-}" ]]; then
  echo "ОШИБКА: GITHUB_OUTPUT не задан." >&2
  exit 1
fi

rollback="$(grep -E '^STROYKA_ROLLBACK_SHA=[0-9a-f]{40}$' "$output" | head -n 1 | cut -d= -f2- || true)"
recorded="$status"
if [[ "$status" -eq 0 ]] && grep -qx 'STROYKA_SKIP=newer' "$output"; then
  recorded="skipped"
fi
{
  printf 'deploy_status=%s\n' "$recorded"
  printf 'rollback_sha=%s\n' "$rollback"
} >> "$GITHUB_OUTPUT"

if [[ "$recorded" == "skipped" ]]; then
  echo "Выкладка пропущена: на сервере уже более новый коммит."
elif [[ "$status" -ne 0 ]]; then
  echo "Выкладка на сервере завершилась с ошибкой. Если коммит уже сменился, скрипт пытался вернуть предыдущий." >&2
else
  echo "Команды на сервере выполнены. Дальше проверка здоровья сайта."
fi
exit 0
