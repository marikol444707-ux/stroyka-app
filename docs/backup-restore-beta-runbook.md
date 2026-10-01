# Beta: Резервная копия и восстановление — безопасный dry-run план

Статус: Beta runbook для операторов/инженеров. НЕ выполнять восстановление в production. Не менять production данные.

Источник истины: текущий GitHub `main`. Этот файл агрегирует существующие runbook'ы и добавляет минимальные dry-run проверки.

1) Что сохраняется (backup evidence)
- Снимок провайдера (cloud snapshot) для VM/FS/DB как обычно.
- Полный, restorable, custom-format `pg_dump` для основной базы данных (pg_dump -Fc).
- Записать размер байт, SHA-256 и вывод `pg_restore --list` для дампа в защищённую evidence-директорию вне репозитория (директория с правами `0700`).
- ID-only подсчёты (row counts) и байто-стабильные checksum'ы для защищённых таблиц, перечисленных в соответствующем runbook (напр., A12 ledger: `human_action_proposals`, `human_action_events`, scoped `audit_log`).
- Бэкап активных nginx/systemd конфигов и `nginx -t` вывод.
- Не включать: учётные данные, cookies, session хэши, приватные/полные бизнес-тексты или raw job/preview JSON.

Ссылки: `docs/human-approved-actions-migration-runbook.md` (секция Backup and before-state).

2) Как проверить backup (dry-run verification)
- Проверка целостности: вычислить SHA-256 файла дампа и сравнить с записью.
- Проверка `pg_restore --list` на успешный вывод и наличие ожидаемых объектов — сохранить вывод.
- Попробовать `pg_restore --list` в изолированной disposable Postgres (не production) и убедиться, что список корректно парсится.
- Проверить что `pg_dump` файл открывается и имеет не нулевой размер.
- Проверить провайдерский snapshot доступен и recent timestamp записан.
- Повторить protected-table row-count/checksum и подтвердить совпадение с pre-backup evidence.

3) Как безопасно восстановить в отдельный dev/test контур (dry-run restore)
- Никогда не использовать production credentials или target для restore.
- Создать isolated/dev DB instance (disposable), либо использовать проектный disposable Postgres указанной команды.
- Перенести дамп и провайдерский snapshot туда (если требуется файловая/asset часть).
- Выполнить `pg_restore --verbose --clean --if-exists -d <dev-db> <dumpfile>` и фиксировать вывод и ошибки.
- После восстановления выполнить набор sanity checks: доступность схем, ожидаемые таблицы, контрольные row-count/checksums для ключевых таблиц.
- Выполнить приложение на dev контуре и запустить smoke тесты (локальные focused tests) для проверки совместимости миграций/каталога.

4) Как откатить приложение (app rollback) — операторный план
- Если проблема на уровне кода/деплоя: rollback приложения на предыдущий ревизит (через стандартный провайдерный/CI механизм). Перед откатом убедиться, что:
  - Backup evidence сделан и проверен (п.1 и п.2).
  - Откат не предполагает автоматического восстановления БД в production.
- При флаговом откате (feature flag): сначала удалить/выключить backend-флаг(и), рестартнуть сервисы, проверить loopback/public health, затем откат frontend если нужно.
- Если инцидент связан с миграцией схемы и требует DB-level recovery — это инцидентный процесс: НЕ выполнять автоматический rollback; инициировать восстановление из бэкапа только после утверждённого инцидентного плана и соответствующей авторизации.

Ссылки: `docs/human-approved-actions-canary.md` (Rollback секция) и `docs/human-approved-actions-migration-runbook.md`.

5) Запрещённые автоматически действия
- Нельзя автоматически восстанавливать production базу без ручного утверждения и инцидентного runbook'а.
- Нельзя автоматически выполнять destructive DDL/DELETE/TRUNCATE operations в production как часть отката.
- Нельзя сохранять/логи приватные данные (credentials, session tokens, raw job JSON) в evidence.
- Нельзя применять `COALESCE(company_id,1)` или другие fallback ownerships при восстановлении данных — сохраняется строгая tenant isolation.

6) Минимальные dry-run проверки, которые надо выполнять сейчас (чеклист)
- [ ] Выполнить `pg_dump -Fc` на disposable DB и записать SHA-256 + `pg_restore --list` (dry-run locally).
- [ ] Восстановить дамп в disposable Postgres и выполнить `pg_restore --list` там.
- [ ] Сравнить row-counts/checksums для ключевых защищённых таблиц с preback evidence.
- [ ] Проверить `nginx -t` и сохранить конфиг snapshot.
- [ ] Выполнить focused backend smoke tests на restored dev instance (narrowest relevant tests).

7) Где смотреть / кто одобряет
- Текущие подробные процедуры по миграциям и canary приведены в `docs/human-approved-actions-migration-runbook.md` и `docs/human-approved-actions-canary.md`.
- Для production-restore требуется отдельная явная approval запись с перечислением commit, operator, exact database, maintenance window и планом восстановления.

8) Следующие шаги (рекомендации)
- Провести dry-run по чеклисту на выделенной disposable среде и задокументировать результаты в evidence-директории с правами `0700`.
- При успехе пометить этот файл как проверенный и включить ссылку на evidence.

