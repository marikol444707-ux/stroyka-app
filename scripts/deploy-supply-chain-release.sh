#!/usr/bin/env bash
# One reviewed release only. No historical requests or DB rollback are applied.
set -Eeuo pipefail
umask 077
test "$EUID" -eq 0
cd /var/www/stroyka-app
exec 8>/var/lock/stroyka-deploy.lock
flock -n 8

BEFORE="20cf455afd2690d99b560cf02257faf0a82744fc"
TARGET="65ce327917253d3c565d729dc288a0937f16ec29"
REHEARSED="4b935a5163ac602eee590adec02defba4222ef27"
CI_RUN_ID=34064031567
REHEARSAL="/root/stroyka-supply-rehearsal-0W76EnqI"
MIGRATION="migrations/versions/0007_warehouse_invoice_vat_labels.py"

test "$(git rev-parse HEAD)" = "$BEFORE"
test "$(git branch --show-current)" = main
git diff --quiet
git diff --cached --quiet
git fetch origin main
test "$(git rev-parse FETCH_HEAD)" = "$TARGET"
git cat-file -e "$TARGET^{commit}"
git merge-base --is-ancestor "$BEFORE" "$TARGET"
test "$(git diff --name-only "$BEFORE" "$TARGET" -- migrations)" = "$MIGRATION"
test "$(git rev-parse "$REHEARSED:$MIGRATION")" = "$(git rev-parse "$TARGET:$MIGRATION")"
git diff --quiet "$REHEARSED" "$TARGET" -- migrations
git diff --quiet "$BEFORE" "$TARGET" -- requirements.txt package.json package-lock.json deploy.sh alembic.ini
test "$(cat "$REHEARSAL/candidate.txt")" = "$REHEARSED"
sha256sum -c "$REHEARSAL/database.sha256"
python3 - "$CI_RUN_ID" "$TARGET" "$REHEARSAL" <<'PREFLIGHT_PY'
import json
from pathlib import Path
import sys
import urllib.request

run, target, evidence = sys.argv[1:]
request = urllib.request.Request(
    'https://api.github.com/repos/marikol444707-ux/stroyka-app/actions/runs/' + run,
    headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'stroyka-release-check'})
with urllib.request.urlopen(request, timeout=20) as response:
    ci = json.load(response)
if not (str(ci['id']) == run and ci['head_sha'] == target and ci['head_branch'] == 'main'
        and ci['event'] == 'push' and ci['path'] == '.github/workflows/ci.yml'
        and ci['repository']['full_name'] == 'marikol444707-ux/stroyka-app'
        and ci['status'] == 'completed' and ci['conclusion'] == 'success'):
    raise SystemExit('STOP: pinned release CI is not successful')
proofs = [json.loads(line) for line in (Path(evidence) / 'rehearsal.log').read_text().splitlines()
          if line.startswith('{')]
if len(proofs) != 1 or proofs[0] != {
        'migration': '0007_warehouse_vat_labels', 'warehouseRows': 53,
        'rowsSha256': '5a1478de6c19603b3611153e86bc9607e6a9a7e084d2b37ddb130f60f58802c6',
        'warehouseDataUnchanged': True, 'vatSchemaUnchanged': True}:
    raise SystemExit('STOP: reviewed rehearsal evidence does not match')
print('PINNED_CI_AND_REHEARSAL_OK')
PREFLIGHT_PY

systemctl is-active --quiet stroyka
systemctl is-active --quiet nginx
nginx -t
test -s build/asset-manifest.json
test -f backend/.env
BACKUP="$(mktemp -d /root/stroyka-supply-release-XXXXXXXX)"
printf '%s\n' "$BEFORE" > "$BACKUP/commit-before.txt"
printf '%s\n' "$TARGET" > "$BACKUP/target.txt"
WORKER_WAS_ACTIVE=0
if systemctl is-active --quiet stroyka-agent-job-worker.service; then WORKER_WAS_ACTIVE=1; fi

pg() {
  timeout 300 runuser -u postgres -- env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
    PGHOST=/var/run/postgresql PGPORT=5432 PGUSER=postgres \
    PGCONNECT_TIMEOUT=5 PGPASSFILE=/dev/null "$@"
}
check_schema() {
  test "$(pg psql -X -v ON_ERROR_STOP=1 -At -d stroyka \
    -c 'SELECT version_num FROM public.alembic_version')" = "$1"
  test "$(pg psql -X -v ON_ERROR_STOP=1 -At -d stroyka -c \
    "SELECT data_type || '|' || column_default || '|' || is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='warehouse_invoices' AND column_name='vat'")" = "text|'Без НДС'::text|YES"
}
check_health() {
  python3 - "$1" <<'HEALTH_PY'
import json, sys, time, urllib.request
for base in ('http://127.0.0.1:8001', 'https://stroyka26.pro'):
    for attempt in range(30):
        try:
            with urllib.request.urlopen(base + '/health', timeout=5) as response:
                result = json.load(response)
            if (result.get('ok') is not True or result.get('db', {}).get('ok') is not True
                    or result.get('version') != sys.argv[1][:12]):
                raise RuntimeError('health/version mismatch')
            print(json.dumps(result))
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
HEALTH_PY
}
check_schema 0006_user_company_staff_links
check_health "$BEFORE"

# Freeze the same DB_* configuration that Alembic consumes. Never print secrets.
PID="$(systemctl show stroyka -p MainPID --value)"
python3 - "$PID" "$BACKUP/migration-env.json" <<'DB_ENV_PY'
import json, os, sys
from pathlib import Path
import psycopg2
from backend.db import DB_CONFIG

if (DB_CONFIG['dbname'] != 'stroyka' or str(DB_CONFIG['port']) != '5432'
        or DB_CONFIG['host'] not in ('localhost', '127.0.0.1', '::1', '/var/run/postgresql')):
    raise SystemExit('STOP: application database is not the backed-up local database')
mapping = dict(DB_NAME='dbname', DB_USER='user', DB_PASSWORD='password', DB_HOST='host', DB_PORT='port')
frozen = {name: str(DB_CONFIG[key]) for name, key in mapping.items()}
process_env = dict(item.split(b'=', 1) for item in Path('/proc/' + sys.argv[1] + '/environ').read_bytes().split(b'\0') if b'=' in item)
if any(name.encode() in process_env and process_env[name.encode()].decode() != value for name, value in frozen.items()):
    raise SystemExit('STOP: service and migration database configuration differ')
for name in tuple(os.environ):
    if name.startswith('PG'):
        del os.environ[name]
os.environ.update(PGPASSFILE='/dev/null', PGCONNECT_TIMEOUT='5')
conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
try:
    conn.set_session(readonly=True)
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_setting('port'), inet_server_addr()::text")
        db, port, host = cur.fetchone()
        if db != 'stroyka' or port != '5432' or host not in (None, '127.0.0.1', '::1'):
            raise SystemExit('STOP: migration connection is not the reviewed local server')
finally:
    conn.rollback()
    conn.close()
Path(sys.argv[2]).write_text(json.dumps(frozen), encoding='utf-8')
print('MIGRATION_DATABASE_ENV_VERIFIED')
DB_ENV_PY

git archive --format=tar --output="$BACKUP/code-before.tar" "$BEFORE"
cp -a build "$BACKUP/frontend-before"
cp -a backend/.env "$BACKUP/backend.env.before"
git status --short > "$BACKUP/git-status-before.txt"
echo "Creating fresh PostgreSQL backup..."
pg pg_dump --format=custom --lock-wait-timeout=5s --dbname=stroyka > "$BACKUP/database.dump"
test -s "$BACKUP/database.dump"
sha256sum "$BACKUP/database.dump" > "$BACKUP/database.sha256"
pg pg_restore --list < "$BACKUP/database.dump" > "$BACKUP/database.list"
test -s "$BACKUP/database.list"

# Keep the existing build/env/publish/smoke workflow, but remove moving git
# operations and pin the one rehearsed migration. Exact matches fail closed.
python3 - "$BACKUP/deploy-reviewed.sh" <<'RENDER_PY'
from pathlib import Path
import sys
source = Path('deploy.sh').read_text(encoding='utf-8')
changes = {
    'git reset --hard HEAD\n': '',
    'git pull --ff-only\n': '',
    'python3 -m alembic upgrade head\n': 'python3 -m alembic -c "$APP_ROOT/alembic.ini" upgrade 0007_warehouse_vat_labels\n',
}
for old, new in changes.items():
    if source.count(old) != 1:
        raise SystemExit('STOP: deploy workflow differs from the reviewed version')
    source = source.replace(old, new)
Path(sys.argv[1]).write_text(source, encoding='utf-8')
RENDER_PY
bash -n "$BACKUP/deploy-reviewed.sh"
DEPLOY_PID=""
DEPLOY_FINISHED=0
stop_deploy() {
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
rollback() {
  local status="${1:-$?}"
  trap - ERR HUP INT TERM
  set +e
  stop_deploy
  echo "DEPLOY FAILED; restoring application only. BACKUP=$BACKUP"
  if git switch --detach "$BEFORE" &&
     bash scripts/publish-frontend.sh "$BACKUP/frontend-before" build &&
     systemctl restart stroyka; then
    local worker_ok=1
    if [ "$WORKER_WAS_ACTIVE" = 1 ]; then
      if ! systemctl restart stroyka-agent-job-worker.service ||
         ! systemctl is-active --quiet stroyka-agent-job-worker.service; then worker_ok=0; fi
    fi
    if check_health "$BEFORE" && [ "$worker_ok" = 1 ]; then
      echo "APPLICATION_ROLLED_BACK; checkout is detached. DB was not restored. BACKUP=$BACKUP"
    else
      echo "ROLLBACK_HEALTH_FAILED; inspect service logs. BACKUP=$BACKUP"
    fi
  else
    echo "ROLLBACK_FAILED; do not repeat deployment. BACKUP=$BACKUP"
  fi
  exit "$status"
}

# No rollback/restart for failed preflight or backup. Arm only before checkout.
trap rollback ERR
trap 'rollback 129' HUP
trap 'rollback 130' INT
trap 'rollback 143' TERM
git merge --ff-only "$TARGET"
export STROYKA_APP_ROOT=/var/www/stroyka-app
export DEPLOY_LOCK_FILE="$BACKUP/deploy-inner.lock"
export SMOKE_BUSINESS_READ_ONLY=1
setsid python3 - "$BACKUP/migration-env.json" "$BACKUP/deploy-reviewed.sh" <<'LAUNCH_PY' &
import json, os, sys
from pathlib import Path
environment = dict(os.environ)
for name in tuple(environment):
    if name.startswith('PG'):
        del environment[name]
environment.update(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
environment.update(PGPASSFILE='/dev/null', PGCONNECT_TIMEOUT='5')
environment['ALEMBIC_CONFIG'] = '/var/www/stroyka-app/alembic.ini'
os.execvpe('bash', ['bash', sys.argv[2]], environment)
LAUNCH_PY
DEPLOY_PID=$!
wait "$DEPLOY_PID"
DEPLOY_FINISHED=1
test "$(git rev-parse HEAD)" = "$TARGET"
check_schema 0007_warehouse_vat_labels
check_health "$TARGET"
python3 - <<'MANIFEST_PY'
import json, urllib.request
with open('build/asset-manifest.json', encoding='utf-8') as source:
    expected = json.load(source)
request = urllib.request.Request('https://stroyka26.pro/asset-manifest.json', headers={'Cache-Control': 'no-cache'})
with urllib.request.urlopen(request, timeout=15) as response:
    if json.load(response) != expected:
        raise SystemExit('STOP: published frontend differs from the release build')
MANIFEST_PY
if [ "$WORKER_WAS_ACTIVE" = 1 ]; then systemctl is-active --quiet stroyka-agent-job-worker.service; fi
systemctl is-active --quiet nginx
trap - ERR HUP INT TERM
echo "SUPPLY_CHAIN_DEPLOYED ${TARGET:0:12} BACKUP=$BACKUP"
echo "Next: verify one authorized real supplier request; no old requests were resent."
