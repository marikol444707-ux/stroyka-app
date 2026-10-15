# Jev QA — архитектура, отчёты и пакет приёмки
Дата: 2026-10-13. **Проект, не подтверждённый на VPS.** Зависимости: Draft PR #327 (QA worker), Draft PR #361 (GitHub bridge), Issues #311/#344/#345/#346.

## Целевой контур
GitHub Issue (allowlisted command + author + issue floor) → GitHub bridge (durable claim, single-run, scoped PAT) → HMAC-authenticated loopback watcher API → isolated QA worker → Chrome BrowserContext (HttpOnly QA cookie, exact HTTPS origin, separate Chrome UID, sandbox) → independent verifier → private evidence store → redacted GitHub summary + authenticated viewer.

**Границы:** production/real tenants запрещены; никакого shell, произвольного URL, токенов в Issue, auto-merge, миграций, деплоя или включения timer без release gate. Одна задача — один ограниченный запуск. Fail-closed при неизвестной роли, окружении, company, авторизации или результате.

## Состав модулей
1. **Command registry** — versioned allowlisted scenarios; для v1 только `JEV_QA_SMOKE_V1`. В будущем отдельные сценарии и права на каждый тип, без передачи произвольного промпта.
2. **Scheduler/bridge** — GitHub polling, ограниченный token, автор/Issue-порог, idempotency key, SQLite transaction/lock, claim-before-execute, retries только для доставки отчёта. Нужна проверка дублирующегося GitHub-комментария после потерянного acknowledgement.
3. **Execution** — отдельный worker/Chrome UID, CDP network guard, один QA BrowserContext на job, HMAC API, запрет внешних origin, timeout/cancel, строго read-only default.
4. **Auth/tenant** — серверная проверка cookie/session/membership; UI bootstrap только из проверенного ответа; no localStorage auth token; expired/foreign/401/403 fail closed. GET read-only должен подтверждаться реальной DB policy, не только методом HTTP.
5. **Verifier** — независимые UI/API/DB assertions. Результат `PASS`, `FAIL`, `BLOCKED` или `NOT_TESTED`. Без before/after DB evidence нельзя утверждать «0 writes».
6. **Evidence** — приватный per-job storage, TTL/size quota, redaction, SHA-256 manifest, immutable job/commit linkage, права на просмотр. Raw screenshots/DOM/password/cookie запрещены в GitHub. Потеря кадров отмечается `SCREENSHOTS_NOT_AVAILABLE`, а не скрывается.
7. **Reporting** — Issue получает безопасные коды ошибок, русские объяснения, job ID, verified scenario/commit, counts, evidence status. Подробные скрины доступны только через авторизованный Jev Live/viewer или защищённый экспорт с TTL; никаких публичных bearer URL.
8. **Release** — pin commit/image digest, security review, SBOM, QA-only install/rollback, выключенный timer, smoke с реальным QA-аккаунтом, независимая приёмка, отдельное решение владельца.

## Стандарт отчёта владельцу
Заголовок: дата, Issue, job ID, SHA/image, QA origin alias, роль/компания (только тестовые идентификаторы), сценарий и verdict.
Для каждого шага: действие → ожидаемый результат → фактический UI/API/DB результат → независимое доказательство → screenshot reference/hash, если доступен.
Для каждой ошибки: стабильный код, критичность, русское описание, шаг воспроизведения, компонент, ожидаемое/фактическое поведение, evidence, Issue/PR и статус исправления.
В конце: passed/failed/blocked/not_tested, 0 unauthorized writes только при доказанной проверке, tenant isolation, состояние screenshot evidence, ограничения, rollback.
**Никаких выдуманных скриншотов, ложного PASS и утечки секретов.**

## Первые 10 QA E2E сценариев
1. Авторизация в чистом BrowserContext, серверно подтверждённая company.
2. Отказ при expired/revoked cookie и 401/403.
3. Отказ при foreign company/inactive membership.
4. Открытие панели и навигация «Проекты».
5. Чтение списка проектов и карточки объекта.
6. Открытие «Склад» и чтение остатков.
7. Запрет POST/presence в read-only smoke.
8. Отрицательный тест перемещения > остатка — **только в отдельном разрешённом write-QA контуре** с независимыми DB invariants.
9. Документы и формы: навигация/просмотр без записи.
10. Timeout/alert/worker restart, отсутствие unsafe retry.

Для release gate: >=8/10 самостоятельных E2E с реальными evidence, 0 unauthorized writes, 0 tenant escapes, все security P1/P2 устранены и проверены независимо. CI не равен QA E2E.

## Критические сбои
- GitHub 401/403/429/timeout: bounded retry/backoff; неизвестный статус = BLOCKED.
- Crash после claim: не повторять browser action; записать interrupted.
- Комментарий GitHub принят, локальный ack потерян: искать idempotent marker перед повторным POST.
- Параллельные dispatchers: single leader + lock/unique task ID.
- Worker timeout: cancel, verify cancellation, no silent retry.
- Browser CDP/dialog crash: stop/recover only with safe read actions.
- Wrong origin, TLS downgrade, cookie expiry, role/tenant mismatch: deny.
- DB writes via GET/dependency/presence: fail read-only; отдельная проверка БД.
- Chrome sandbox/UID/proc failure: NO-GO.
- Screenshot missing, redaction failed, expired TTL: explicitly NOT_AVAILABLE; raw data never upload.
- Wrong pinned SHA or stale image: NOT_TESTED.

## Будущее развитие (после QA v1)
**Стройка:** регрессионный обход проектов, склада, поставщиков, субподрядчиков, актов, смет, документов, ролей и мультиорганизаций; сравнение релизов и поиск аномалий.
**Документы:** OCR/сопоставление смет, счетов, КС-2/КС-3, спецификаций, расхождений — сначала read-only, с цитатами и provenance.
**Операционный помощник:** заявки поставщикам, контроль сроков и материалов, уведомления, автоматические черновики — каждое действие через отдельные approval gates.
**Поиск коммерческих заявок:** отдельный сервис, источники/правила/права и безопасность; не смешивать с Jev QA и не включать в этот релиз.
**Оркестрация:** registry инструментов, versioned policy, tenant-scoped permissions, job queue, rate limits, observability, human approvals и cost budget. Никакого универсального SSH/SQL/browser admin access модели.

## До однократной установки на VPS
Закрыть #345 (полная read-only гарантия + реальные DB invariants), #346 (cookie identity + frontend), #344 (sandbox/UID/proc), review threads, независимые E2E. Затем зафиксировать SHA, QA image, подготовить rollback, проверить секреты и права, отдельным решением разрешить QA-only install. Bridge timer **не включать автоматически**.
