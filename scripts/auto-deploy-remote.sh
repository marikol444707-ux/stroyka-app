#!/bin/bash
# Runs on the server. Checks out one exact commit and runs the existing deploy.sh.
# deploy.sh itself does `git pull --ff-only`, which can move past the approved
# commit. A temporary git wrapper keeps that pull from changing HEAD.
set -euo pipefail

apply_only=0
if [[ "${1:-}" == "--apply-only" ]]; then
  apply_only=1
  shift
fi

target_sha="${1:-}"
app_root="${STROYKA_APP_ROOT:-/var/www/stroyka-app}"
deploy_script="${STROYKA_DEPLOY_SCRIPT:-$app_root/deploy.sh}"

if [[ ! "$target_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ОШИБКА: нужен полный SHA коммита из 40 шестнадцатеричных символов." >&2
  exit 2
fi
if [[ ! -d "$app_root" ]]; then
  echo "ОШИБКА: нет каталога приложения." >&2
  exit 2
fi
if [[ ! -f "$deploy_script" ]]; then
  echo "ОШИБКА: не найден deploy.sh." >&2
  exit 2
fi

cd "$app_root"
rollback_sha="$(git rev-parse HEAD)"
if [[ ! "$rollback_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ОШИБКА: текущий коммит сервера не похож на SHA." >&2
  exit 2
fi

printf 'STROYKA_ROLLBACK_SHA=%s\n' "$rollback_sha"
echo "Точка отката: $rollback_sha"
echo "Целевой коммит: $target_sha"

switched=0

# A newer commit already running on the server must not be replaced by an older
# successful CI run that finished later. Rollback uses --apply-only and skips this.
if [[ "$apply_only" -eq 0 ]]; then
  if git fetch origin main \
    && git cat-file -e "${target_sha}^{commit}" \
    && git merge-base --is-ancestor "$target_sha" HEAD \
    && [[ "$(git rev-parse HEAD)" != "$target_sha" ]]; then
    echo "STROYKA_SKIP=newer"
    echo "На сервере уже более новый коммит. Этот коммит не выкладываю, чтобы не откатить сайт."
    exit 0
  fi
fi

pin_and_deploy() {
  local sha="$1"
  local wrap real now status
  echo "Скачиваю коммит $sha"
  # Failures here must return. Inside a function, set -e can abort the whole
  # shell before the rollback trap sees the error.
  if ! git fetch origin main; then
    echo "ОШИБКА: не удалось скачать ветку main." >&2
    return 1
  fi
  if ! git cat-file -e "${sha}^{commit}"; then
    if ! git fetch origin "$sha"; then
      echo "ОШИБКА: коммит $sha не скачался с origin." >&2
      return 1
    fi
  fi
  if ! git cat-file -e "${sha}^{commit}"; then
    echo "ОШИБКА: коммита $sha нет на сервере." >&2
    return 1
  fi
  if git symbolic-ref -q HEAD >/dev/null; then
    if ! git reset --hard "$sha"; then
      echo "ОШИБКА: не удалось переключить ветку на $sha." >&2
      return 1
    fi
  elif ! git checkout -B main "$sha"; then
    echo "ОШИБКА: не удалось переключить ветку на $sha." >&2
    return 1
  fi
  switched=1
  now="$(git rev-parse HEAD)" || return 1
  if [[ "$now" != "$sha" ]]; then
    echo "ОШИБКА: после переключения HEAD=$now, а нужен $sha." >&2
    return 1
  fi

  wrap="$(mktemp -d)" || return 1
  real="$(command -v git)" || return 1
  cat > "$wrap/git" << 'EOF'
#!/bin/bash
set -euo pipefail
if [[ "${1:-}" == "pull" ]]; then
  current="$("$STROYKA_REAL_GIT" rev-parse HEAD)"
  if [[ "$current" != "$STROYKA_PINNED_SHA" ]]; then
    echo "ОШИБКА: HEAD $current не равен закреплённому коммиту $STROYKA_PINNED_SHA. git pull остановлен." >&2
    exit 1
  fi
  echo "git pull пропущен: остаёмся на коммите $STROYKA_PINNED_SHA"
  exit 0
fi
exec "$STROYKA_REAL_GIT" "$@"
EOF
  chmod 700 "$wrap/git"

  set +e
  STROYKA_REAL_GIT="$real" STROYKA_PINNED_SHA="$sha" PATH="$wrap:$PATH" bash "$deploy_script"
  status=$?
  set -e
  rm -rf "$wrap"
  if [[ "$status" -ne 0 ]]; then
    echo "ОШИБКА: deploy.sh завершился с кодом $status для коммита $sha." >&2
    return "$status"
  fi
  now="$(git rev-parse HEAD)" || return 1
  if [[ "$now" != "$sha" ]]; then
    echo "ОШИБКА: deploy.sh сдвинул HEAD на $now, ожидался $sha." >&2
    return 1
  fi
  echo "deploy.sh завершён на коммите $sha"
  return 0
}

rollback() {
  trap - ERR
  if [[ "$switched" -eq 0 ]]; then
    echo "ОШИБКА до смены коммита. Сервер остался на $rollback_sha." >&2
    exit 1
  fi
  echo "ОШИБКА выкладки. Возвращаю сервер на $rollback_sha и снова запускаю deploy.sh." >&2
  if pin_and_deploy "$rollback_sha"; then
    echo "Откат выполнен: $rollback_sha." >&2
  else
    echo "ОШИБКА: откат на $rollback_sha не удался. Сервер нужно проверить вручную." >&2
  fi
  exit 1
}

if [[ "$apply_only" -eq 1 ]]; then
  pin_and_deploy "$target_sha"
  echo "Коммит $target_sha применён."
  exit 0
fi

trap rollback ERR
pin_and_deploy "$target_sha"
trap - ERR
echo "Сервер на коммите $target_sha"
