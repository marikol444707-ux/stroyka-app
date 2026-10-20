#!/usr/bin/env bash
# Manual, pinned release install. Does not merge supplier records.
# Usage: bash install-participant-duplicate-merge.sh BEFORE_FULL_SHA TARGET_FULL_SHA
set -Eeuo pipefail
[[ $# = 2 && "$1" =~ ^[0-9a-f]{40}$ && "$2" =~ ^[0-9a-f]{40}$ ]] || { echo 'Нужны две полные версии: текущая и устанавливаемая'; exit 2; }
[[ "$(id -u)" = 0 ]] || { echo 'Запустите из серверного терминала root'; exit 2; }
umask 077
cd /var/www/stroyka-app
TARGET="$2"
BEFORE="$1"
DROPIN='/etc/systemd/system/stroyka.service.d/99-participant-history-merge.conf'
exec 8>/var/lock/stroyka-deploy.lock
flock -n 8 || { echo "Уже выполняется другой деплой"; exit 1; }
[[ "$(git branch --show-current)" = main ]]
[[ "$(git rev-parse HEAD)" = "$BEFORE" ]]
git diff --quiet HEAD --
[[ ! -e "$DROPIN" && ! -L "$DROPIN" ]]
git fetch origin main
[[ "$(git rev-parse FETCH_HEAD)" = "$TARGET" ]]
git merge-base --is-ancestor "$BEFORE" "$TARGET"
git diff --quiet "$BEFORE" "$TARGET" -- deploy.sh migrations requirements.txt package.json package-lock.json
export RELEASE_BACKUP="$(mktemp -d /root/stroyka-participant-merge-XXXXXXXX)"
export RELEASE_TARGET="$TARGET"
export RELEASE_BEFORE="$BEFORE"
printf '%s\n' "$BEFORE" > "$RELEASE_BACKUP/commit-before.txt"
# The current checkout may predate this helper. Read it from the pinned target.
git show "$TARGET:scripts/participant_merge_release.py" > "$RELEASE_BACKUP/participant_merge_release.py"
python3 - <<'PY'
import json,os,shutil,subprocess,urllib.request
from pathlib import Path
import sys
sys.path.insert(0,os.environ['RELEASE_BACKUP'])
from participant_merge_release import manifest_paths, regular_asset
from backend.db import get_db
pid=subprocess.check_output(['systemctl','show','stroyka','-p','MainPID','--value'],text=True).strip()
runtime=dict(item.split('=',1) for item in Path('/proc',pid,'environ').read_text().split('\0') if '=' in item)
assert runtime.get('PARTICIPANT_SUPPORT_ENABLED')=='1', 'Сначала должен быть включён основной раздел'
assert runtime.get('PARTICIPANT_CONNECTIONS_ENABLED')=='1', 'Подключение поставщиков должно быть уже включено'
for source in (os.environ,runtime):
    assert not any(key.startswith('PARTICIPANT_') and key.endswith('_ENABLED') and key not in ('PARTICIPANT_SUPPORT_ENABLED','PARTICIPANT_CONNECTIONS_ENABLED') and value=='1' for key,value in source.items()), 'Перед этим этапом остальные режимы участников должны быть выключены'
with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=10) as response:
    health=json.load(response)
assert health.get('ok') and health.get('db',{}).get('ok') and health.get('version')==os.environ['RELEASE_BEFORE'][:12]
conn=get_db()
try:
    conn.autocommit=False; conn.set_session(readonly=True)
    with conn.cursor() as cur:
        cur.execute('SELECT version_num FROM alembic_version')
        assert cur.fetchall()==[('0100_packaging_history_guard',)]
    conn.rollback()
finally: conn.close()
root=Path('build'); dest=Path(os.environ['RELEASE_BACKUP'])/'frontend-before'
manifest=json.loads((root/'asset-manifest.json').read_text())
files=manifest_paths(manifest)
for folder,dirs,names in os.walk(root):
    if Path(folder)==root: dirs[:]=[name for name in dirs if name!='static']
    files.update(Path(folder,name).relative_to(root) for name in names)
for rel in files:
    assert not rel.is_absolute() and '..' not in rel.parts
    source=regular_asset(root,rel)
    target=dest/rel; target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
print('Резерв текущего интерфейса:',dest)
PY
# Preserve the publisher before changing checkout; never depend on a deleted stage.
cp scripts/publish-frontend.sh "$RELEASE_BACKUP/publish-before.sh"
UNIT_CREATED=0
DEPLOY_STARTED=0
rollback() {
  local status=$?
  trap - ERR
  set +e
  local recovery_failed=0
  if [[ "$UNIT_CREATED" = 1 ]]; then
    rm -- "$DROPIN" || recovery_failed=1
    systemctl daemon-reload || recovery_failed=1
  fi
  if [[ "$DEPLOY_STARTED" = 0 ]]; then
    # No target runtime has been started: restoring BEFORE cannot undo new access guards.
    # --keep refuses conflicting local edits, unlike --hard. Never erase unknown files.
    git reset --keep "$BEFORE" || recovery_failed=1
    if [[ "$(git rev-parse HEAD)" != "$BEFORE" ]]; then recovery_failed=1; fi
    if [[ "$recovery_failed" = 0 ]]; then
      bash "$RELEASE_BACKUP/publish-before.sh" "$RELEASE_BACKUP/frontend-before" build || recovery_failed=1
    fi
    if [[ "$recovery_failed" = 0 ]]; then
      printf '%s\n' 'rollback-before-runtime-complete' > "$RELEASE_BACKUP/recovery-status.txt"
    else
      printf '%s\n' 'manual-recovery-required: pre-runtime checkout/frontend restoration incomplete' > "$RELEASE_BACKUP/recovery-status.txt"
    fi
  else
    # New access history could already exist. An older backend can reopen revoked access.
    # Keep the target checkout and turn off the new mutation mode, never roll back blindly.
    if [[ "$recovery_failed" = 0 && "$(git rev-parse HEAD)" = "$TARGET" ]]; then
      systemctl restart stroyka || recovery_failed=1
      systemctl is-active --quiet stroyka || recovery_failed=1
    else
      recovery_failed=1
    fi
    printf '%s\n' 'manual-recovery-required: target code retained; verify runtime and frontend before recovery' > "$RELEASE_BACKUP/recovery-status.txt"
    recovery_failed=1
  fi
  if [[ "$recovery_failed" != 0 ]]; then
    echo "АВТОМАТИЧЕСКИЙ ОТКАТ НЕ ПОДТВЕРЖДЁН. Требуется проверка runtime, прав доступа и интерфейса."
  fi
  echo "Включение остановлено. Резерв сохранён: $RELEASE_BACKUP."
  exit "$status"
}
trap rollback ERR
git merge --ff-only "$TARGET"
python3 - <<'PY'
import os
from pathlib import Path
script=Path('deploy.sh').read_text()
for line in ('git reset --hard HEAD\n','git pull --ff-only\n'):
    assert script.count(line)==1
    script=script.replace(line,'')
(Path(os.environ['RELEASE_BACKUP'])/'deploy-reviewed.sh').write_text(script)
PY
mkdir -p /etc/systemd/system/stroyka.service.d
UNIT_CREATED=1
printf '%s\n' '[Service]' 'Environment=PARTICIPANT_HISTORY_MERGE_ENABLED=1' > "$DROPIN"
systemctl daemon-reload
export DEPLOY_LOCK_FILE="$RELEASE_BACKUP/deploy-inner.lock"
export SMOKE_BUSINESS_READ_ONLY=1
DEPLOY_STARTED=1
bash "$RELEASE_BACKUP/deploy-reviewed.sh"
python3 - <<'PY'
import json,os,subprocess,urllib.request
from html.parser import HTMLParser
import sys
sys.path.insert(0,os.environ['RELEASE_BACKUP'])
from participant_merge_release import verify_assets, write_pending
from pathlib import Path
from backend.db import get_db
head=os.environ['RELEASE_TARGET']; base='https://stroyka26.pro'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
pid=subprocess.check_output(['systemctl','show','stroyka','-p','MainPID','--value'],text=True).strip()
runtime=dict(item.split('=',1) for item in Path('/proc',pid,'environ').read_text().split('\0') if '=' in item)
assert runtime.get('PARTICIPANT_SUPPORT_ENABLED')=='1', 'Настройка сервиса переопределена другим файлом'
assert runtime.get('PARTICIPANT_CONNECTIONS_ENABLED')=='1', 'Настройка подключения переопределена другим файлом'
assert runtime.get('PARTICIPANT_HISTORY_MERGE_ENABLED')=='1', 'Объединение не включено в сервисе'
assert not any(key.startswith('PARTICIPANT_') and key.endswith('_ENABLED') and key not in ('PARTICIPANT_SUPPORT_ENABLED','PARTICIPANT_CONNECTIONS_ENABLED','PARTICIPANT_HISTORY_MERGE_ENABLED') and value=='1' for key,value in runtime.items())
def fetch(url):
    request=urllib.request.Request(url,headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=30) as response: return response.read()
for host in ('http://127.0.0.1:8001',base):
    health=json.loads(fetch(host+'/health'))
    assert health.get('ok') and health.get('db',{}).get('ok') and health.get('version')==head[:12]
conn=get_db()
try:
    conn.autocommit=False; conn.set_session(readonly=True)
    with conn.cursor() as cur:
        cur.execute('SELECT version_num FROM alembic_version')
        assert cur.fetchall()==[('0100_packaging_history_guard',)]
    conn.rollback()
finally: conn.close()
manifest=json.loads(Path('build/asset-manifest.json').read_text())
assert json.loads(fetch(base+'/asset-manifest.json'))==manifest
asset_count=verify_assets(Path('build'),manifest,fetch,base)
published=fetch(base+'/app').decode()
assert published==Path('build/index.html').read_text()
class Modes(HTMLParser):
    def __init__(self):
        super().__init__();self.values={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);name=attrs.get('name','')
        if tag=='meta' and name.startswith('stroyka-participant-'):
            assert name not in self.values
            self.values[name]=attrs.get('content')
modes=Modes();modes.feed(published)
assert len(modes.values)==12
wanted={'stroyka-participant-support','stroyka-participant-connections','stroyka-participant-history-merge'}
assert all(modes.values.get(name)=='1' for name in wanted)
assert all(value==('1' if name in wanted else '0') for name,value in modes.values.items())
backup=Path(os.environ['RELEASE_BACKUP'])
write_pending(backup,head,asset_count)
print('УСТАНОВЛЕНО, НО НЕ ПРИНЯТО В БРАУЗЕРЕ. Версия:',head[:12])
print('Карточки поставщиков пока не объединены: выполните проверку в кабинете администратора.')
print('РЕЗЕРВ:',backup)
PY
trap - ERR
