# Локальная интеграция: согласованный граф, выпуск ещё не принят

Ветка integration/server-audit-20261101 сохраняет историю server
57023611c6090c1bdf63a107a28eefadd1afb492 и audit
 a398d3874208038dd7dec3b2d9cf56ab66aa9487 через merge-коммит
c3cc1743f6c4dbd07af3bac244358a82440b37b6. Старые ветки не менялись.

## Новое основание и минимальное изменение

Пользователь сообщил результат разрешённого read-only чтения:
0104_jev_search_run_history. Это БД из текущего backend/.env; если файл менялся
после запуска, тождество с подключением процесса ещё не доказано. Номер revision
не доказывает наличие всех таблиц, constraints или качество старых данных.

У 0103_room_owner_identity изменён только down_revision:
0102_platform_company_features → 0104_jev_search_run_history.
Серверные revision-файлы сохранены побайтно. SQL-тела, revision IDs и downgrade
всех семи аудиторских миграций сохранены; нет повторного применения одинаковых
job_candidates/platform_company_features, stamp, backfill или снятия guards.
Это локальная адаптация опубликованной, но не установленной на указанном
сервере аудиторской цепочки. Исходная аудиторская ветка остаётся неизменной.

После 0100_packaging_history_guard:
0101_manual_brigade_origins → 0102_job_candidates →
0103_platform_company_features → 0104_jev_search_run_history →
0103_room_owner_identity → 0104_legacy_project_owners →
0105_settlement_cash_guard → 0106_document_version_owner →
0107_room_work_owner → 0108_project_create_requests →
0109_legacy_payment_requests.

Номера в начале ID — подписи, порядок задаёт down_revision. Единственная
вершина: 0109_legacy_payment_requests. От исходной 0104 — ровно семь новых
миграций. До изменения отсутствовал parent 0102_platform_company_features
и были две конечные вершины; теперь статически нет dangling parent и циклов.

## Зависимости и предел совместимости

Составной уникальный индекс projects(id,company_id) создаёт 0023; ledger и
supplier_payment_operation_guard — 0045, supplier_settlement_cash — 0055,
корректировку даты — 0072. Эти revisions находятся до серверной 0104 по графу.
Legacy-таблицы rooms/room_works/document_versions и другие должны реально
существовать; отметка revision не заменяет проверку структуры и владельцев.
Owner/FK/CHECK ограничения могут отклонить частичные или противоречивые старые
связи. Данные не исправлялись и по именам не привязывались.

Поддерживаемая цель этого пакета: продолжение подтверждённой серверной линии
0104_jev_search_run_history. НЕ применять автоматически к базе старой audit-only
линии 0101_job_candidates/0102_platform_company_features или уже прошедшей её
0103–0109: совпадающий поздний ID не доказывает одинаковую историю. Такой базе
нужны отдельная инвентаризация и переход. Не переименовывать применённые IDs
и не подменять историю через stamp. Чистый bootstrap и обновление с более
ранних точек не объявлены принятыми.

## Derived tests, fixtures и установщик

Строгий graph expectation в test_release_upgrade_postgres.py теперь включает
серверную цепочку и её продолжение. Сам PG test module НЕ запускался.
Partial fixture WORK_OWNER_MIGRATIONS использует неизменённые имена файлов и
SQL-тела; он не изображает полноценный Alembic upgrade и не изменялся.
Новый source-only набор подтверждает исключение ровно для одного parent,
сохранение SQL/серверных файлов, полный граф, точный pending path и ancestry.

Release tooling теперь знает точный source 0104 и target 0109, полный pending
path, отсутствие старых audit-only IDs, missing parents/циклов/дублей. Manifest
и package validation используют тот же source/target. Исторический partial PG
fixture по-прежнему обновляется лишь до SOURCE_REVISION (0104), не притворяется
приёмкой 0109; теперь явно ожидает blocked от нового readiness checker.

Это подготовка tooling, НЕ разрешение выполнения: apply останавливается самым
первым guard до чтения credentials/DB/staging; git delivery helper останавливается
до fetch/mktemp и не использует старые pinned SHA. Нет флага обхода. Checker
сохраняет старые schema/owner/trigger/read-only проверки, допускает только source
0104 при preflight и target0109 при postcheck, но всегда добавляет блокер
INTEGRATION_RELEASE_ACCEPTANCE_REQUIRED; для target также
TARGET_SCHEMA_AND_DATA_ACCEPTANCE_REQUIRED. Новая схема/данные/backup restore
ещё не приняты, поэтому status ready не выдаётся даже при подходящем revision.
Проверки новых constraints/данных и механизм доказанной приёмки предстоит довести
после разрешённых проверок; их наличие не имитируется булевым разрешением.

Существующие backup, expected SHA, clean checkout, branch-main, ownership,
service/health, checksum, rollback-material и browser=false guards сохранены.
Неподтверждённое имя серверной ветки также остаётся возможным блокером: main не
предполагается автоматически. Установщик/pack/check/db-check не запускались.
Его реальные действия после допуска: чтение service config, read-only schema
query, backup БД/frontend, fetch локального bundle, build, остановка служб,
fast-forward, upgrade, import main (startup DDL), restart, публикация и HTTP
проверки. Поэтому это не диагностическая команда. pg_restore --list не является
доказательством восстановления. Остановка всех writers, согласованность backup
файлов/БД и доказанный rollback должны входить в последующую приёмку.

## Проверки: новый проход и прежние результаты раздельно

Новый проход: python3 -m unittest scripts.test_server_audit_integration_static:
9 passed, 0 failed, 0 skipped; git diff --check clean. Чтение/AST/Git, без
импорта приложения, SQL, DB или HTTP. Полный граф до/после сохранён в evidence.
Проверки доказывают структуру/сохранение кода, не SQL runtime/concurrency.

Предыдущий c3cc1743: frontend 320 suites / 2052 passed, backend mock/unit
84 passed, source-only 6 passed, frontend build success. Эти результаты не
прибавляются к новым девяти. Frontend/бизнес-код в новом проходе не менялся;
повторные frontend/build не требовались. Первый старый запуск системным Python
дал 36 pass/21 error (включая failed imports) из-за отсутствия зависимостей;
финальные 84 выполнены в существующем .venv. Ни один внешний AI не вызывался.

Статические доказательства c3cc: 192 независимых файла совпадают с родителями;
6 серверных и 19 аудиторских main definitions сохранены. JEV AST равен серверу
плюс семь явных transaction assignments. Preview AST и защищаемые соседние
файлы совпадают с обоими родителями; три hashes согласованы после review.
FH04/R1–R3, legacy gates, owners, contractor/team/OCR/JEV не изменялись в новом
проходе. Статические preservation checks повторены в текущих девяти тестах.

## Дубли веток и оставшиеся условия допуска

Предыдущая инвентаризация: 192 remote branches, 192 разных HEAD; 61 вершина
доступна локально (60 в серверной истории, одна в audit), 131 patch-unverified.
main и codex/jev-platform-feature-next имеют одинаковое дерево при разных
commits. Ничего не удалено; этот проход инвентаризацию не расширял.

До выпуска: подтвердить актуальность DB mapping/отметки, фактическую схему и
старые owners, резервную копию с проверенным восстановлением; провести отдельно
разрешённую реальную upgrade/FH04/0109/rollback и browser-приёмку, адаптировать
release tooling, получить CI точного итогового SHA и отдельное решение о выпуске.
Старые клиенты не становятся атомарными; журналы повторов нельзя терять при
откате. Git checkout не откатывает БД. Нельзя восстановлением старой копии
молча потерять новые учётные операции.

NOT RUN: миграции, SQL/БД/HTTP/browser/mobile/внешние сервисы и ранее запрещённый
security/full-remainder аудит. Нового стенда нет, запрет не обходился.
Нет push, PR mutation, main merge, deploy, production changes или новых
credentials. Новых временных БД/контейнеров/сборок нет; отчёты/patch сохранены.

## Дополнение: локальная проверка release tooling

Финальный выбранный набор: 28 passed, 0 failed, 0 skipped. Включает 10 новых
policy mock/AST тестов, 9 source/graph проверок и 9 существующих unit-тестов
парсера synthetic config/backup/manifest/early-stop. Fake cursors записывают
строки, но не исполняют SQL. Guard apply проверен извлечением первого AST узла,
install() не вызывался. Полный transport/pack test намеренно не включён и не
считается PASS; его synthetic graph expectation обновлено. PG fixture только
отредактирован, не запущен. Предварительные 19 результатов не суммируются с 28.
Frontend и бизнес-код не менялись, повторные frontend/build не запускались.

Снятие release stop — отдельная будущая правка после доказанной приёмки,
не runtime-флаг и не приглашение обойти прежний запрет. Нет публикации, сервера,
новых БД/стендов или доступа. Старые ветки/инвентаризация сохранены.
