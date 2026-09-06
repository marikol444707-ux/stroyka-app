#!/usr/bin/env bash
# Backup and rehearse only. Never deploy or migrate the live database here.
set -Eeuo pipefail
umask 077
test "$EUID" -eq 0
cd /var/www/stroyka-app
exec 8>/var/lock/stroyka-deploy.lock
flock -n 8

BEFORE="20cf455afd2690d99b560cf02257faf0a82744fc"
TARGET="4b935a5163ac602eee590adec02defba4222ef27"
BACKUP=""
CODE=""
CLONE=""
failed() {
  local status="$?"
  echo "SUPPLY_REHEARSAL_FAILED BACKUP=$BACKUP CODE=$CODE DATABASE=$CLONE" >&2
  echo "No production migration or application restart was attempted." >&2
  exit "$status"
}
trap failed ERR

test "$(git rev-parse HEAD)" = "$BEFORE"
test "$(git branch --show-current)" = main
git diff --quiet
git diff --cached --quiet
git cat-file -e "$TARGET^{commit}"
git merge-base --is-ancestor "$BEFORE" "$TARGET"
test "$(git diff --name-only "$BEFORE" "$TARGET" -- migrations)" = \
  "migrations/versions/0007_warehouse_invoice_vat_labels.py"
git diff --quiet "$BEFORE" "$TARGET" -- requirements.txt package.json package-lock.json deploy.sh
systemctl is-active --quiet stroyka
systemctl is-active --quiet nginx
test -s build/asset-manifest.json
test -f backend/.env

# No inherited PGHOST, PGSERVICE, credentials or database name may redirect tools.
pg() {
  timeout 300 runuser -u postgres -- env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
    PGHOST=/var/run/postgresql PGPORT=5432 PGUSER=postgres \
    PGCONNECT_TIMEOUT=5 PGPASSFILE=/dev/null "$@"
}
live_revision() {
  pg psql -X -v ON_ERROR_STOP=1 -At -d stroyka \
    -c 'SELECT version_num FROM public.alembic_version'
}
check_health() {
  python3 - "$BEFORE" <<'HEALTH'
import json, sys, urllib.request
for base in ('http://127.0.0.1:8001', 'https://stroyka26.pro'):
    with urllib.request.urlopen(base + '/health', timeout=15) as response:
        status = json.load(response)
    if (status.get('ok') is not True or status.get('db', {}).get('ok') is not True
            or status.get('version') != sys.argv[1][:12]):
        raise SystemExit('STOP: production health/version mismatch')
print('PRODUCTION_HEALTH_OK')
HEALTH
}
test "$(live_revision)" = "0006_user_company_staff_links"
test "$(pg psql -X -v ON_ERROR_STOP=1 -At -d stroyka -c \
  "SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='warehouse_invoices' AND column_name='vat'")" = text
check_health
pg python3 -c 'import alembic, psycopg2, sqlalchemy'

BACKUP="$(mktemp -d /root/stroyka-supply-rehearsal-XXXXXXXX)"
CODE="$(mktemp -d /var/tmp/stroyka-supply-rehearsal-code-XXXXXXXX)"
CLONE="stroyka_supply_rehearsal_$(date -u +%Y%m%d%H%M%S)_$$"
[[ "$CLONE" =~ ^stroyka_supply_rehearsal_[0-9]+_[0-9]+$ ]]
printf '%s\n' "$BEFORE" > "$BACKUP/commit-before.txt"
printf '%s\n' "$TARGET" > "$BACKUP/candidate.txt"
printf '%s\n' "$CODE" > "$BACKUP/code-path.txt"
printf '%s\n' "$CLONE" > "$BACKUP/clone.txt"
git status --short > "$BACKUP/git-status-before.txt"
git archive --format=tar --output="$BACKUP/code-before.tar" "$BEFORE"
cp -a build "$BACKUP/frontend-before"
cp -a backend/.env "$BACKUP/backend.env.before"
echo "Creating PostgreSQL backup..."
pg pg_dump --format=custom --lock-wait-timeout=5s --dbname=stroyka > "$BACKUP/database.dump"
test -s "$BACKUP/database.dump"
sha256sum "$BACKUP/database.dump" > "$BACKUP/database.sha256"
# Root opens the private file; postgres reads stdin, not an inaccessible /root path.
pg pg_restore --list < "$BACKUP/database.dump" > "$BACKUP/database.list"
test -s "$BACKUP/database.list"

git archive "$TARGET" | tar -x -C "$CODE"
test ! -e "$CODE/backend/.env"
test ! -e "$CODE/.env"
chown -R postgres:postgres "$CODE"
pg createdb --template=template0 --owner=postgres "$CLONE"
pg psql -X -v ON_ERROR_STOP=1 -d postgres -v clone="$CLONE" <<'SQL'
REVOKE CONNECT ON DATABASE :"clone" FROM PUBLIC;
SQL
pg pg_restore --exit-on-error --single-transaction --no-owner --no-privileges \
  --dbname="$CLONE" < "$BACKUP/database.dump"

(
  cd "$CODE"
  timeout 180 runuser -u postgres -- env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 DB_HOST=/var/run/postgresql DB_PORT=5432 \
    DB_NAME="$CLONE" DB_USER=postgres DB_PASSWORD= \
    PGPASSFILE=/dev/null PGCONNECT_TIMEOUT=5 \
    PGOPTIONS='-c lock_timeout=5000 -c statement_timeout=60000' \
    python3 - "$CLONE" <<'REHEARSAL_PY'
import hashlib
import json
import re
import subprocess
import sys


def validate_database_name(name):
    if not isinstance(name, str) or len(name) > 63 or not re.fullmatch(r'stroyka_supply_rehearsal_[0-9]{14}_[0-9]+', name):
        raise RuntimeError('STOP: invalid disposable database name')


def main():
    expected = sys.argv[1]
    validate_database_name(expected)
    from backend.db import DB_CONFIG
    import psycopg2

    required = dict(dbname=expected, user='postgres', password='',
                    host='/var/run/postgresql', port='5432')
    if DB_CONFIG != required:
        raise RuntimeError('STOP: unexpected database configuration')

    def snapshot():
        conn = psycopg2.connect(**required, connect_timeout=5)
        try:
            conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
            with conn.cursor() as cur:
                cur.execute('SELECT current_database(), current_user, inet_server_addr(), current_setting(\'port\')')
                if cur.fetchone() != (expected, 'postgres', None, '5432'):
                    raise RuntimeError('STOP: connected to unexpected database/server')
                cur.execute("SET LOCAL TIME ZONE 'UTC'; SET LOCAL DateStyle='ISO, YMD'; SET LOCAL extra_float_digits=3")
                cur.execute('SELECT version_num FROM public.alembic_version')
                revisions = cur.fetchall()
                cur.execute("""SELECT data_type, column_default, is_nullable,
                    character_maximum_length, collation_schema, collation_name
                    FROM information_schema.columns WHERE table_schema='public'
                    AND table_name='warehouse_invoices' AND column_name='vat'""")
                metadata = cur.fetchone()
                cur.execute('SELECT count(*) FROM public.warehouse_invoices')
                count = cur.fetchone()[0]
                digest = hashlib.sha256()

                class Sink:
                    def write(self, data):
                        digest.update(data.encode('utf-8') if isinstance(data, str) else data)

                cur.copy_expert('COPY (SELECT to_jsonb(w)::text FROM public.warehouse_invoices w ORDER BY id) TO STDOUT', Sink())
                return revisions, (metadata, count, digest.hexdigest())
        finally:
            conn.rollback()
            conn.close()

    revisions, before = snapshot()
    if revisions != [('0006_user_company_staff_links',)]:
        raise RuntimeError('STOP: clone revision must be exactly 0006')
    if before[0] is None or before[0][:4] != ('text', "'Без НДС'::text", 'YES', None):
        raise RuntimeError('STOP: clone does not match the reviewed TEXT VAT schema')
    cli = [sys.executable, '-m', 'alembic']
    heads = subprocess.check_output(cli + ['heads'], text=True).strip()
    if heads != '0007_warehouse_vat_labels (head)':
        raise RuntimeError('STOP: unexpected migration head')
    subprocess.run(cli + ['upgrade', '0007_warehouse_vat_labels'], check=True, timeout=90)
    revisions, after = snapshot()
    if revisions != [('0007_warehouse_vat_labels',)] or before != after:
        raise RuntimeError('STOP: migration changed invoice data/schema or revision is incorrect')
    print(json.dumps(dict(migration='0007_warehouse_vat_labels', warehouseRows=after[1],
                         rowsSha256=after[2], warehouseDataUnchanged=True, vatSchemaUnchanged=True)))


if __name__ == '__main__':
    main()
REHEARSAL_PY
) 2>&1 | tee "$BACKUP/rehearsal.log"

test "$(git rev-parse HEAD)" = "$BEFORE"
git diff --quiet
git diff --cached --quiet
test "$(live_revision)" = "0006_user_company_staff_links"
systemctl is-active --quiet stroyka
systemctl is-active --quiet nginx
check_health
trap - ERR
echo "SUPPLY_REHEARSAL_OK BACKUP=$BACKUP CODE=$CODE DATABASE=$CLONE CANDIDATE=$TARGET"
echo "Production was not deployed. Backup and restricted-access clone are retained on this server."
