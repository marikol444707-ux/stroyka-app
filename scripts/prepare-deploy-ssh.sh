#!/bin/bash
# Write the deploy key to a 600 file. Never print the key or the known_hosts value.
set -euo pipefail

if [[ -z "${GITHUB_ENV:-}" || -z "${RUNNER_TEMP:-}" ]]; then
  echo "ОШИБКА: подготовка SSH запускается только внутри GitHub Actions." >&2
  exit 1
fi

missing=0
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_SSH_KEY DEPLOY_PORT; do
  if [[ -z "${!name:-}" ]]; then
    echo "ОШИБКА: не задан секрет ${name}." >&2
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

if [[ ! "$DEPLOY_HOST" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ОШИБКА: DEPLOY_HOST должен быть именем сервера или IPv4, без пробелов." >&2
  exit 1
fi
if [[ ! "$DEPLOY_USER" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ОШИБКА: DEPLOY_USER должен содержать только буквы, цифры, точку, _ и -." >&2
  exit 1
fi
if [[ ! "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] || [[ "$DEPLOY_PORT" -lt 1 || "$DEPLOY_PORT" -gt 65535 ]]; then
  echo "ОШИБКА: DEPLOY_PORT должен быть числом от 1 до 65535." >&2
  exit 1
fi

install -d -m 700 "$RUNNER_TEMP/stroyka-ssh"
key="$RUNNER_TEMP/stroyka-ssh/id"
known="$RUNNER_TEMP/stroyka-ssh/known_hosts"
umask 077
printf '%s\n' "$DEPLOY_SSH_KEY" > "$key"
chmod 600 "$key"
if ! grep -q "PRIVATE KEY" "$key"; then
  rm -f "$key"
  echo "ОШИБКА: DEPLOY_SSH_KEY не похож на приватный ключ. Вставьте весь ключ, включая строки BEGIN и END." >&2
  exit 1
fi

if [[ -n "${DEPLOY_KNOWN_HOSTS:-}" ]]; then
  printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$known"
  echo "Ключ сервера взят из секрета DEPLOY_KNOWN_HOSTS."
else
  echo "Секрет DEPLOY_KNOWN_HOSTS не задан. Ключ сервера будет получен через ssh-keyscan."
  echo "Так проще, но при подмене сети можно довериться чужому серверу. Лучше задать DEPLOY_KNOWN_HOSTS."
  if ! ssh-keyscan -p "$DEPLOY_PORT" -T 10 -H "$DEPLOY_HOST" > "$known" 2>"$RUNNER_TEMP/stroyka-ssh/keyscan.err"; then
    rm -f "$known" "$RUNNER_TEMP/stroyka-ssh/keyscan.err"
    echo "ОШИБКА: не удалось получить ключ сервера через ssh-keyscan." >&2
    exit 1
  fi
  rm -f "$RUNNER_TEMP/stroyka-ssh/keyscan.err"
fi
chmod 600 "$known"
if [[ ! -s "$known" ]]; then
  rm -f "$known"
  echo "ОШИБКА: файл ключа сервера пустой." >&2
  exit 1
fi

{
  printf 'SSH_KEY=%s\n' "$key"
  printf 'SSH_KNOWN_HOSTS=%s\n' "$known"
  printf 'SSH_PORT=%s\n' "$DEPLOY_PORT"
  printf 'SSH_USER=%s\n' "$DEPLOY_USER"
  printf 'SSH_HOST=%s\n' "$DEPLOY_HOST"
} >> "$GITHUB_ENV"
