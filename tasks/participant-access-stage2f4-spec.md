# Срез 2е4: полученное КП до оформления заказа/счёта

15.10.2026. Продолжение 2е3; локальная разработка, синтетические HTTP/PG/browser
испытания и коммиты. Production, реальные отправки, push и выдача прав запрещены.

Цель: закрыть ошибочную связь с полученными, ещё не утверждёнными КП. После
плана/причины/явного подтверждения received КП отклоняется, пустые ожидаемые
ответы отзываются, получатели скрываются, очереди отменяются и связь отключается.
Цены, позиции, комментарии, party snapshots, responded_at, PDF/файловые ссылки,
прежние события и исходные документы сохраняются. Другие покупатели/поставщики
не меняются. Уже доставленные сообщения и скачивания не отзываются.

Отдельный путь quote-correction-plans с mode=reject_received_quotes; старые
unused/RFQ endpoints сохраняют смысл. Новые default-off флаги:
PARTICIPANT_QUOTE_CORRECTIONS_ENABLED / REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED.
Переиспользовать схему 0099, immutable plan, TTL, epochs/версии, свежую авторизацию,
повторный digest/блокировки, атомарный result/audit и события КП. Миграции нет.

До confirm показать точные заявки и КП, status before/after и сохранность цен/файла.
Result включает rejectedQuoteCount, проверяемый UI против плана. Типы планов и
пути не взаимозаменяемы. При потере ответа повторить тот же план/основание.

Границы: только явный current owner target→target recipient, подтверждённый buyer,
human-approved request; received status Получено и pending без draft ответа.
Выбранное/утверждённое КП, awarded позиции, счета (включая другого покупателя),
поставки/договоры/назначения, неизвестные дочерние FK, shared group/legacy,
in-flight уведомление и предыдущие business events блокируют операцию.
PDF полученного КП должен иметь активный зарегистрированный original выбранной
компании; отсутствие/чужой файл — отказ, не удаление или подмена ссылки.
Physical storage/CDN readiness остаётся отдельно.

Реализация: расширить существующий RFQ proof/apply/replay точным received mode,
вынести проверку received КП/оригинала в correction_quotes.py. Общая транзакция
использует явный mode вместо множества bool-параметров. UI — один и тот же путь
подготовки, конкретный список последствий и подтверждение отклонения.
Backend feature files/тесты рядом; frontend platform-admin; CI группа и ADR/план.
Стиль существующего кода: typed DTO, SQL parameters/Identifier, bounded SELECT,
без новых зависимостей, сумм из LLM или произвольного mutation API.

Приёмка: новые failing regression tests → реализация → PostgreSQL/HTTP:
полученное КП и PDF видны до/недоступны после; prices/JSON/PDF/party snapshots
и paid source invoice неизменны; buyer сохраняет архив, stale supplier response/
buyer select запрещены; concurrent select/response, drift, idempotency/rollback,
tenant/role/owner epochs, parent financial mismatch и полнота схемы.
Не более 50 заявок и прежние пределы архивов. Блокировки default-off и требуют
company writer protocol/нагрузочной приёмки до production, как в 2е2–2е3.

Команды: python3 scripts/run_supplier_catalog_postgres_tests.py
backend.features.participant_support.test_quote_corrections_postgres.SupplierQuoteCorrectionsPostgresTests
и прежние corrections/RFQ/preview/connections/security группы. CI=true npm test --
--watchAll=false --runInBand; npm run build с флагами; Chromium loopback + Unix-only
disposable PG. Общий backend/remote CI — отдельно, пропуски честно указать.

Связь с уже утверждённым заказом, счётом/поставкой/договором и исторический merge
этим шагом не исправляются; это отдельные сценарии сохранения финансовой основы.
