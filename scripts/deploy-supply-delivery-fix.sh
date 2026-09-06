#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /var/www/stroyka-app
exec 8>/var/lock/stroyka-deploy.lock
flock -n 8

TARGET="${SUPPLY_RELEASE_COMMIT:?Set SUPPLY_RELEASE_COMMIT to the reviewed full commit SHA}"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
BEFORE="$(git rev-parse HEAD)"
test "$(git branch --show-current)" = main
case "$BEFORE" in
  20cf455afd2690d99b560cf02257faf0a82744fc|a559ae9aaa3218e51cb31e997047d0d1e8718a13) ;;
  *) echo "STOP: unexpected current commit: $BEFORE"; exit 1 ;;
esac
git diff --quiet
git diff --cached --quiet
git fetch origin main
test "$(git rev-parse FETCH_HEAD)" = "$TARGET"
git merge-base --is-ancestor "$BEFORE" "$TARGET"
git diff --quiet "$BEFORE" "$TARGET" -- migrations requirements.txt package.json package-lock.json deploy.sh
systemctl is-active --quiet stroyka
systemctl is-active --quiet nginx
nginx -t
test -s build/asset-manifest.json
BACKUP="$(mktemp -d /root/stroyka-supply-fix-XXXXXXXX)"
printf '%s\n' "$BEFORE" > "$BACKUP/commit-before.txt"
python3 -m alembic current > "$BACKUP/alembic-before.txt"
grep -Fx '0006_user_company_staff_links (head)' "$BACKUP/alembic-before.txt"
cp -a build "$BACKUP/frontend-before"
WORKER_WAS_ACTIVE=0
if systemctl is-active --quiet stroyka-agent-job-worker.service; then WORKER_WAS_ACTIVE=1; fi
DEPLOY_PID=""
DEPLOY_FINISHED=0

stop_deploy() {
  # $! also covers a signal arriving between launching setsid and assigning DEPLOY_PID.
  local child_pid="${DEPLOY_PID:-${!:-}}"
  [ "$DEPLOY_FINISHED" = 0 ] && [ -n "$child_pid" ] || return 0
  if kill -0 -- "-$child_pid" 2>/dev/null; then
    kill -TERM -- "-$child_pid" 2>/dev/null || true
    for attempt in {1..10}; do
      kill -0 -- "-$child_pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 -- "-$child_pid" 2>/dev/null; then kill -KILL -- "-$child_pid" 2>/dev/null || true; fi
  else
    kill -TERM "$child_pid" 2>/dev/null || true
  fi
  wait "$child_pid" 2>/dev/null || true
}

check_health() {
  python3 - "$1" <<'PY'
import json, sys, time, urllib.request
for base in ('http://127.0.0.1:8001', 'https://stroyka26.pro'):
    for attempt in range(30):
        try:
            with urllib.request.urlopen(base + '/health', timeout=5) as response:
                result = json.load(response)
            assert result.get('ok') is True and result.get('db', {}).get('ok') is True
            assert result.get('version') == sys.argv[1][:12]
            print(json.dumps(result))
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
PY
}

rollback() {
  local status="${1:-$?}"
  trap - ERR HUP INT TERM
  set +e
  stop_deploy
  echo "DEPLOY FAILED; restoring application. BACKUP=$BACKUP"
  if git switch --detach "$BEFORE" &&
     bash scripts/publish-frontend.sh "$BACKUP/frontend-before" build &&
     systemctl restart stroyka; then
    local worker_ok=1
    if [ "$WORKER_WAS_ACTIVE" = 1 ]; then
      if ! systemctl restart stroyka-agent-job-worker.service ||
         ! systemctl is-active --quiet stroyka-agent-job-worker.service; then worker_ok=0; fi
    fi
    if check_health "$BEFORE" && [ "$worker_ok" = 1 ]; then
      echo "APPLICATION_ROLLED_BACK; checkout is detached. BACKUP=$BACKUP"
    else
      echo "ROLLBACK_HEALTH_FAILED; inspect service logs. BACKUP=$BACKUP"
    fi
  else
    echo "ROLLBACK_FAILED; do not repeat deployment. BACKUP=$BACKUP"
  fi
  exit "$status"
}

check_health "$BEFORE"
trap rollback ERR
trap 'rollback 129' HUP
trap 'rollback 130' INT
trap 'rollback 143' TERM
git merge --ff-only "$TARGET"
export STROYKA_APP_ROOT=/var/www/stroyka-app
export DEPLOY_LOCK_FILE="$BACKUP/deploy-inner.lock"
export SMOKE_BUSINESS_READ_ONLY=1
# Pin the code above, and omit destructive reset / unpinned pull from the existing deployment.
sed '/^git reset --hard HEAD$/d; /^git pull --ff-only$/d' deploy.sh > "$BACKUP/deploy-reviewed.sh"
setsid bash "$BACKUP/deploy-reviewed.sh" &
DEPLOY_PID=$!
wait "$DEPLOY_PID"
DEPLOY_FINISHED=1
test "$(git rev-parse HEAD)" = "$TARGET"
check_health "$TARGET"
python3 - <<'PY'
import json, urllib.request
with open('build/asset-manifest.json', encoding='utf-8') as source:
    expected = json.load(source)
request = urllib.request.Request('https://stroyka26.pro/asset-manifest.json', headers={'Cache-Control': 'no-cache'})
with urllib.request.urlopen(request, timeout=15) as response:
    assert json.load(response) == expected, 'Published frontend does not match local build'
PY
if [ "$WORKER_WAS_ACTIVE" = 1 ]; then systemctl is-active --quiet stroyka-agent-job-worker.service; fi
trap - ERR HUP INT TERM
echo "SUPPLY_FIX_DEPLOYED ${TARGET:0:12} BACKUP=$BACKUP"
