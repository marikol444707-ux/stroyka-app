# Штатный QA-режим: реализован локально, НЕ исполнен

В unified_release добавлен отдельный qa-install. По умолчанию он только проверяет
структуру manifest и печатает план, не создаёт driver и не обращается к серверу.
Реальное исполнение требует отдельного выбора execute, терминала и ввода точной
фразы с именем QA-базы/контейнера/целевым SHA. Подтверждение истекает через 5 минут;
после него preflight повторяется. Это не разрешение запуска в текущей задаче.
Production install/apply и его безусловный hold сохранены без изменения AST.

Manifest принимает только: qa_only=true, database=stroyka_qa,
container=stroyka-qa-db, candidate_root=/opt/stroyka-jev-qa-7e89d73,
frontend_root=/var/lib/docker/volumes/stroyka-qa-frontend-work/_data,
source_sha и target_sha (полные), discard_test_data=true,
other_writers_accounted_for=true. Дополнительные поля/другие цели отклоняются.
Нет флага production, force, skip или stamp. Старые учебные записи не требуют backup.

## Реальные функции

- LocalDriver.preflight: QA-host, точные images/mounts/workdirs, clean candidate,
  локальное наличие target и ancestry012c9984; совпадение reviewed SQL, зависимости
  установленного venv, точная DB mapping, Caddy routing и read-only DB предусловия.
  Не делает fetch/install packages. Секреты подключения читаются локально из
  выбранных Docker Env-ключей, остаются в памяти, raw stderr не выводится.
- stop: оба backend, frontend writer и gateway; DB-контейнер не останавливается.
- switch: обычный git checkout --detach точного target без force/reset/clean.
  Первый checkout не меняется. Непереносимые bind/git layouts дают ошибку, не обход.
- reset_schema: один child-процесс известного host venv, проверка current_database,
  отсутствие дополнительных схем/extensions/чужих соединений, очистка только public
  существующей stroyka_qa и base schema в одной транзакции. Нет DROP DATABASE,
  новых БД/контейнеров, изменения ролей или очистки Docker volume.
- migrate: полный Alembic upgrade до0109, затем проверка version table. main не
  импортируется. Частичная/неопределённая ошибка останавливает работу без retry.
- frontend: git archive только frontend sources/lock/scripts в новый временный
  каталог СУЩЕСТВУЮЩЕГО общего тома; npm ci/build внутри СУЩЕСТВУЮЩЕГО frontend
  контейнера; links/traversal/.env отвергаются. Затем frontend writer остановлен,
  build заменяется с сохранением предыдущей сборки. Config/source-root не стираются.
- start_and_check: candidate start и health с точным SHA/DB ok; защищённая копия
  двух исходных Caddyfile, узкое изменение root на /srv/app/build и backend upstream
  на candidate с портом из фактической mapping8002; запуск static/gateway и caddy
  validate. Неизвестные/неоднозначные формы конфигурации дают отказ, не guessed rewrite.
- execute: fail-stop на каждом этапе, старается остановить QA writers после ошибки;
  не обещает rollback, не удаляет промежуточные материалы и не начинает аудит.

## Проверки и пределы

Финальный набор64passed/0failed/0skipped, только unit/mock/text. Проверены default
dry-run, QA scope, отсутствие/истечение confirmation, повторная preflight, сбой
каждой стадии, маршрутизация и сохранение соседнего config, SQLpayload только
через mock, старые guards/SQL/inventory. Production install AST не изменился.
Реальная схема, npm build, Caddy и контейнеры не запускались в разработке.

Не заявляется готовый релиз. До реального применения нужно предъявить точные
manifest/версию/операцию удаления пользователю для действийного подтверждения.
Target должен быть доставлен в checkout отдельно: исполнитель не публикует и
не скачивает код. При не-git bind layout preflight остановится; это не основание
копировать поверх неизвестных файлов. Venv уже установлен, повторная установка
не нужна. npm ci использует существующую frontend runtime-конфигурацию; его
доступность и воспроизводимость сборки относятся к непройденной приёмке.

Оставшиеся runtime-проверки:
1. Реальные target/code/layout/permissions, DBauth/bridge и exclusive writers.
2. Очистка public+bootstrap, полный граф, constraints и последующий startup DDL.
3. npm build/публикация и фактическое обслуживание новой сборки через QA gateway.
4. Health/version после старта и обычная отдельно согласованная бизнес-приёмка.
5. Поведение при реальном сбое: остановка writers и ручное решение; старые учебные
   записи не сохраняются, автоматического отката нет.

Есть реальные ограничения: frontend HTTP/browser-приёмка не реализована как
доказанный PASS; успешный caddy validate и файлы не заменяют браузер. Инициализация
может создавать legacy default accounts и repairs — это пока непроверенный runtime.
Глобальный security/role/full-remainder аудит не включён и не обходится.
Ничего на сервере не выполнено, новых контейнеров нет, push/merge отсутствуют.

## Local maintenance exclusion revision (2026-11-02; NOT deployed)

The manifest now requires `maintenance_database: "postgres"` instead of the
unprovable `other_writers_accounted_for` flag. Old manifests fail validation.
Dry-run remains pure plan rendering; it does not validate actual DB permissions.
Actual invocation requires a fresh interactive phrase explicitly naming the
connection gate, termination of other stroyka_qa sessions, and replacement SHA.
No permission to perform these actions is implied by publishing or planning.

Before stopping containers or changing checkout, a private durable intent journal
records the manifest, observed container running states and topology/config hashes.
The DB phase uses two connections to the same verified QA PostgreSQL address,
port and system identifier: an existing postgres database for control, and one
stroyka_qa worker for schema, Alembic and final revision verification. Nothing
creates postgres or grants privileges. Current implementation conservatively
requires existing superuser privileges; absent privileges fail before gate change.
Production installer hold is unchanged.

The control connection serializes instances of this tool, records original access
state/OID/identity/PID, closes new QA connections and waits for other QA client
sessions to terminate. Prepared transactions, subscriptions and unexpected workers
are rejected. This is not protection against another administrator actively
changing the gate or the cluster. No other database's sessions are terminated.
Reset plus migrations use one READ COMMITTED transaction and the same connection;
ordinary Alembic invocation retains its original connection creation path.

Confirmed rollback/success restores the original open state. A pre-existing closed
DB is rejected, never automatically reopened. Lost commit/rollback outcome leaves
access closed and records recovery_required; no automatic retry/reset. Restore
failure propagates. No old backend is automatically started on an unknown schema.
SIGTERM/KeyboardInterrupt get ordinary cleanup; SIGKILL, power loss, or loss of
both connections cannot be repaired by finally. Journals under the private
/opt/stroyka-qa-maintenance-* directory must be retained. Recovery after an abrupt
crash is deliberately not an automatic CLI: reconcile the recorded cluster/OID,
transaction outcome and worker lifetime before separately approving restoration.

Local mock/static tests do not prove PostgreSQL DDL/migration compatibility,
termination races, privileges, recovery or frontend/browser acceptance. None of
those runtime checks were executed during implementation. No new container, DB,
role, permanent credentials, server service or production change is introduced.
