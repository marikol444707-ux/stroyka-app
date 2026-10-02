# Jev Browser Worker

Отдельный Python 3.12 worker для браузерного QA. В production backend он не устанавливается.

## Безопасность

- `QA_BASE_URL` обязателен: worker отказывается открывать другой origin/path.
- `TIMEWEB_AI_API_KEY` хранится только в runtime secrets.
- Jev-запросы к hard-coded TypeSafe SystemOne перенаправляются только на Timeweb.
- В `TYPESAFE_API_KEY` кладётся не секрет, а безопасный sentinel.
- Jev `DONE` не считается успехом без детерминированных assertions.
- Скриншоты и `result.json` сохраняются отдельно как evidence.
- Production deploy и migrations worker не выполняет.

## Сборка

Из корня репозитория:

    docker build -f dev_control/browser_worker/Dockerfile -t stroyka-jev-worker .

## Обязательные переменные

    TIMEWEB_AI_API_KEY=<secret>
    QA_BASE_URL=https://qa.example.test

Опционально:

    JEV_SYSTEMONE_URL=https://api.timeweb.ai/v1/systemone
    JEV_MODEL=jev-latest
    QA_EVIDENCE_DIR=/evidence
    TIMEWEB_TEXT_MODEL=<явно выбранная Timeweb chat-модель>

`TIMEWEB_TEXT_MODEL` намеренно не угадывается. Если задача требует TYPE_TEXT,
а модель не настроена, worker должен упасть, а не выбрать неизвестный провайдер.

## Первый smoke test

Сначала используем read-only QA URL. Реальный складской сценарий добавляется
только после появления отдельной QA/test среды и тестовых данных.

Целевой сценарий:

    склад -> отклонённое перемещение -> М-11 не должен открыться
