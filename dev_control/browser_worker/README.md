# Jev Browser Worker

Отдельный Python 3.12 worker для браузерного QA. В production backend он не устанавливается.

## Как работает

Work Control отправляет защищённую HTTP-задачу -> worker ставит её в очередь ->
Chrome + Jev выполняют сценарий -> deterministic verifier проверяет итог ->
Work Control забирает результат и evidence.

## Безопасность

- `QA_BASE_URL` обязателен: worker отказывается открывать другой origin/path.
- Граница QA проверяется снова после каждого браузерного действия.
- `QA_ENVIRONMENT` должен быть только `qa`, `test` или `staging`.
- `DEV_CONTROL_API_TOKEN` обязателен для `/jobs`.
- `TIMEWEB_AI_API_KEY` хранится только в runtime secrets.
- В `TYPESAFE_API_KEY` кладётся не секрет, а безопасный sentinel.
- Jev `DONE` не считается успехом без детерминированных assertions.
- Production deploy и migrations worker не выполняет.
- Очередь ограничена одним одновременно выполняемым browser job.
- `BU_CDP_URL` принимается только как `http://127.0.0.1:9222`; внешний CDP запрещён.
- WebSocket/WebTransport/WebRTC блокируются до resume не только в page/iframe, но и в worker/shared-worker/service-worker targets.

## Timeweb App Platform

При создании приложения из репозитория выбрать:

    branch: dev-control/jev-browser-worker   (пока только тестовый этап)
    project directory: dev_control
    Dockerfile: dev_control/Dockerfile
    health path: /health

После принятия PR ветка будет заменена на стабильную ветку Dev Control.

Обязательные переменные:

    TIMEWEB_AI_API_KEY=<secret>
    DEV_CONTROL_API_TOKEN=<отдельный случайный secret>
    QA_ENVIRONMENT=staging
    QA_BASE_URL=https://<отдельный QA URL>
    QA_ALLOWED_ORIGIN=https://<тот же точный QA origin>

Опционально:

    JEV_SYSTEMONE_URL=https://api.timeweb.ai/v1/systemone
    JEV_MODEL=jev-latest
    QA_EVIDENCE_DIR=/tmp/stroyka-qa-evidence
    TIMEWEB_TEXT_MODEL=<явно выбранная Timeweb chat-модель>

`TIMEWEB_TEXT_MODEL` намеренно не угадывается. Без неё задача, требующая TYPE_TEXT,
должна завершиться ошибкой, а не уйти к неизвестному провайдеру.

## API

Проверка живости:

    GET /health

Создание задачи (Bearer token обязателен):

    POST /jobs

Проверка результата:

    GET /jobs/{job_id}

## Первый реальный сценарий

Только в отдельной QA/test среде с тестовыми данными:

    склад -> запросить перемещение больше остатка -> сервер отклоняет -> М-11 не открывается

## Безопасный первый запуск без Stroyka

Чтобы сначала проверить только цепочку App Platform -> Chrome -> Jev -> Timeweb,
не давая worker доступ к Stroyka, используется внутренняя self-test страница:

    QA_BASE_URL=http://127.0.0.1:8080
    QA_SELFTEST_ON_START=1

После старта worker один раз открывает /selftest-page, нажимает безопасную кнопку
и должен получить JEV_BROWSER_OK. Результат виден в /health как
startup_selftest=passed или failed.

Для реального QA Stroyka QA_SELFTEST_ON_START выключается, а QA_BASE_URL
заменяется на отдельный staging/QA URL.

## Лимиты

- App Platform: держать ровно 1 replica без autoscaling, пока очередь хранится в памяти.
- QA_MAX_PENDING_JOBS по умолчанию 2, допустимый диапазон 1..10.
- Одна браузерная проверка выполняется одновременно.
- max_seconds одной задачи ограничен API значением 180 секунд.

## Дополнительные гарантии после security review

- Известные production-хосты Stroyka (`stroyka26.pro`, `stroyka.pro`) запрещены независимо от `QA_ENVIRONMENT`.
- Любой browser job обязан иметь хотя бы один детерминированный assertion.
- CDP Fetch перехватывает запросы Chrome до отправки: чужой origin и document вне QA path блокируются до загрузки.
- URL с `..`, `%2e%2e` и повторным percent-encoding отклоняются до запуска Jev.
- Каждый job выполняется в отдельном subprocess; по `max_seconds` процесс принудительно завершается.
- `/health` возвращает HTTP 503, пока конфигурация или startup self-test не готовы.
- Evidence доступно Work Control через защищённые `/jobs/{job_id}/evidence/{filename}`.
- Evidence удаляется по TTL; активные jobs очистка не трогает.
- Timeweb text helper настраивается атомарно и не смешивает ключи разных провайдеров.

Для удалённого QA QA_ALLOWED_ORIGIN обязателен и должен точно совпадать с
origin QA_BASE_URL (scheme + host + port). Известные production-домены/IP
блокируются дополнительно. Для локального startup self-test allowlist не нужен.

## Важно для Timeweb App Platform

- Автоматический deploy/build from latest commit должен быть ВЫКЛЮЧЕН.
- Развёртывание worker выполняется только вручную с заранее проверенного commit SHA.
- Production deploy и production migrations этим worker не выполняются.

## Авторизация QA

Пароли, 2FA-коды и session tokens нельзя помещать в goal или assertions.
Для защищённых сценариев worker принимает заранее созданную тестовую session cookie
только через runtime secrets:

    QA_SESSION_COOKIE_NAME=<имя cookie>
    QA_SESSION_COOKIE_VALUE=<секрет>

Cookie внедряется локально в новый изолированный BrowserContext до открытия страницы,
только для HTTPS QA origin, с HttpOnly/Secure, и не передаётся Jev/Timeweb.
Worker не выполняет model-side login: логин/пароль/2FA нельзя передавать в goal/assertions;
для авторизованного QA используется только заранее созданная тестовая session cookie.
Для startup self-test эти переменные не нужны.

`startup-selftest` зарезервирован в журнале jobs и не удаляется обычным eviction,
чтобы результат первоначальной проверки контура оставался видимым.
