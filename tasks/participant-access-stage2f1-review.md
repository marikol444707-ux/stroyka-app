# Срез 2е1: проверка последствий подключения

Дата: 13.10.2026. Только локальная разработка в отдельном worktree.
Это завершённый read-only шаг; корректирующая команда ещё не реализована.

## Результат для пользователя

У выбранной организации: «Участники и доступ» → «Поставщики» → исходная
карточка → «Проверить кабинет» → выполненный запрос →
«Проверить ошибочное подключение». Открывается отдельное окно с компанией,
карточками, временем подключения, документами и текущим доступом поставщика.
Кнопка закрытия остаётся видимой при прокрутке; есть Escape, удержание/возврат
фокуса, блокировка прокрутки фона. В каждой странице не больше 5 записей.

Счета, накладные, КП, версии договоров и зарегистрированные основные файлы
считаются только в выбранной компании. Общий оригинал обеих карточек считается
один раз. Неизвестные даты и отсутствующие реестры отмечаются явно.
Не показываем суммы, банковские реквизиты, snapshots, contacts или original URLs.

## Сервер и границы

GET `/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/correction-preview`.
Допустимы только точные исходная карточка и accepted request в company/account;
связь target также должна существовать. Чтение доступно активному system_owner /
platform_admin, роль повторно проверяется в read-only snapshot. Роль поддержки
не получает новую capability или бизнес-права.

Флаги `PARTICIPANT_CORRECTION_PREVIEW_ENABLED` и
`REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED` выключены по умолчанию.
UI находится внутри прежнего connection UI и требует также его включения.
Новых миграций нет; нужны существующие supplier connections / archive registries.

Даты сравниваются в UTC; timestamp без timezone интерпретируется согласно
существующей UTC-конвенции приложения. NULL/строковые/отсутствующие creation
timestamps не выдаются за подтверждённое создание до исходной операции.
Creation time не отражает все позднейшие редактирования/назначения/просмотры.
Счета и КП используют текущие обычные supplier policies; файлы/накладные/договоры
помечаются «нужна проверка», без обещания наличия или доступности original.

Смена владельца/его epoch, изменение полномочий, объединённая карточка,
непривязанные документы и неподтверждённые file references требуют разбора.
Не возвращаем IDs/количество/содержимое документов других покупателей.
Сама каталожная связь не отзывает адресацию старых документов: это явно объяснено
на экране. `canApply=false`; нет POST/подтверждения/отзыва прав/универсального undo.
Этот ответ не является сохранённым, неизменяемым планом для будущей команды.

## Проверки

- Red: 5 PostgreSQL сценариев падают на отсутствующем endpoint; frontend падает
  на отсутствующем компоненте. Логи `/tmp/participant-correction-red.log` и
  `/tmp/participant-correction-ui-red.log`.
- 7 новых PostgreSQL сценариев: реальные authenticated HTTP, zero business/audit
  writes, другая компания/карточка/request, pending request, неизвестные даты,
  владельцы/epochs, missing registry, unassigned documents, paging, registered
  originals/dedup/contracts, forbidden mutation и read-only transaction guard.
- Регрессии: 11 connection, 7 history preview, 17 support capabilities —
  всего 42 разных PostgreSQL сценария, без skips, каждый класс в отдельной
  disposable socket-only базе. Исходящая сеть/SMTP/S3 запрещены fixture.
- Frontend: точный scope/поздний ответ, paging/category reset, failure/retry,
  feature flag и accepted-only entry point, неизвестные даты, modal focus/Escape.
- После окончательной UI правки: 305 frontend suites / 1878 тестов PASS;
  профильный прогон 3 suites / 21 тест PASS. Сборка Compiled successfully,
  без новых ESLint ошибок; прежние Browserslist/Node/bundle size предупреждения.
  Python compile и git diff --check PASS.
- Chromium: реальные OrganizationParticipants/SupplierConnectionRequests и
  новый компонент, реальный HTTP backend и disposable PG; synthetic bearer
  authentication передаёт loopback proxy. Это проверка UI/HTTP, не новый login E2E.
  Проверяем paging, category reset, смену компании и 320/390/768/1440 px.
  Скриншоты: `output/playwright/participant-support/correction-preview-390.png`
  и `correction-preview-1440.png` (игнорируемые локальные артефакты).
- Chromium нашёл потерю Escape после paging: сфокусированная кнопка исчезала
  на loading, событие уходило в body. Regression сначала FAIL; клавиатурный
  обработчик ограниченного открытого dialog перенесён на document. Повторный
  реальный сценарий paging → category → Escape/restore focus/scroll unlock PASS.
  Четыре ширины без горизонтального overflow; мобильный скриншот просмотрен;
  console содержит только React DevTools INFO, без ошибок JavaScript.

Логи: `/tmp/participant-correction-pg-final.log` (7 новых + 11 connections +
7 history), `/tmp/participant-correction-pg-accepted.log` (7 новых после contract
дополнений + 17 capabilities), `/tmp/participant-correction-pg-reviewed.log`
(7 новых после unassigned guard), `/tmp/participant-correction-focus-red.log`,
`/tmp/participant-correction-focus-green.log`,
`/tmp/participant-correction-ui-final-accepted.log`,
`/tmp/participant-correction-build-final-accepted.log`.
Повторные прогоны вызваны только изменениями кода/тестов и найденной browser ошибкой.
Браузер и оба тестовых сервера закрыты; disposable PG и приватный контекст удалены.

Review пяти осей: только чтение с актуальной ролью и точной компанией; текущая
видимость переиспользует обычные policies; originals не дублируются; страницы
ограничены, metadata snapshot не претендует на неизменяемый confirm plan;
даты/unknown schema не превращаются в ложную полноту истории. COUNT запросы
остаются под 15-секундным timeout, без новой гарантии для больших архивов.

Новый PG класс добавлен в mandatory CI. Удалённый CI, production, физическое
storage/CDN, полный backend regression и вся матрица этапа 4 здесь не проверялись.

## Следующая ограниченная операция

Сохранённый корректирующий план должен учесть не только создание записей,
но изменения документов/адресатов/назначений после подключения, версии и epochs.
Перед применением — проверка последствий и явное подтверждение; в транзакции —
повторная авторизация, проверка drift, идемпотентность и аудит. Сохранить IDs,
party/bank snapshots, подписи, платежи и факт прежнего просмотра.
Ошибочное историческое объединение разбирается отдельно, без общего отката.

## Подготовленное описание PR

Название: `feat: review supplier connection correction impact per company`.

Администратор может проверить документы и текущий доступ после конкретного
подключения поставщика, не изменяя связи или финансовую историю. Просмотр
ограничен выбранной организацией и открывается отдельным окном на телефоне.
Неизвестные даты/реестры и изменения владельца показаны как препятствия.
Отключение каталожной связи не представляется как полный отзыв адресного доступа.
Публикация и production enablement не выполнялись.
