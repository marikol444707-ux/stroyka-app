# Срез 2е6: закрытие доступа к оформленной цепочке без изменения документов

15.10.2026. Backend-коммит `fec30b06`; UI/приёмка — следующий локальный коммит.
[Спецификация](participant-access-stage2f6-spec.md), [план](participant-access-plan.md),
[ADR0008](../docs/decisions/0008-organization-participant-support.md).

## Что работает

Администратор → организация → поставщик → проверка ошибочного подключения.
Отдельная операция проверяет возможность закрыть доступ к КП, связанным счетам,
поставкам и накладным. В плане показаны точные IDs/счётчики, сохранение статусов,
оплат, склада и originals, отменяемые уведомления. Список документов свёрнут
для телефона. Нужны причина и явное подтверждение «Закрыть доступ и отключить связь».

Закрываются адресаты и одна связь покупателя. КП остаётся утверждённым, счёт
сохраняет прежний статус/paid amount, документы/поставки/приёмки/склад/история
не меняются. Полученное КП и pending ответы в этом режиме также сохраняют
статусы. Это отзыв доступа, не отмена заказа, оплаты или документов. Архив
покупателя и другие покупатели/поставщики остаются доступными по прежним правилам.
Менеджерские назначения не переписываются и не обходят закрытого recipient.

Поставщик получает отказ на старые respond/create-invoice/ship/upload/history
формы и оригиналы; соответствующие списки больше не возвращают документы.
Оригиналы у покупателя остаются, включая один файл нескольких документов
закрываемой цепочки. Отдельный счёт без КП, договор, претензия, group/shared/
неизвестная цепочка и in-flight уведомление требуют отдельного разбора.

## Реализация / review

- `correction_issued.py`: bounded financial history, точные прямые/обратные
  родители, служебные shipment batches/supply history, существующие назначения,
  originals registry и SELECT-only ClosedRecipients. Через живые политики
  сравниваются before/after для документов и файлов. Raw rows/суммы/URL в DTO
  и saved plan не входят — только IDs/counts/digests и минимальные assignment keys.
  Списки originals/назначений упорядочены детерминированно для разных workers.
- `correction_rfqs.py` / `corrections.py`: mode-specific proof, exact allowed
  descendants, сохранение статусов, новая команда, event/audit/result, TTL/epochs/
  digest/locks/atomicity/replay. Старые endpoints/сохранённые планы совместимы;
  mode проверяется и при operationId replay, и при confirm. Миграций нет.
- Новый always-on read guard `supplier_history_visibility_filter` и применение
  в `supply_history/routes.py`: связанные записи следуют точной live цепочке.
  До исправления ручное скрытие recipient оставляло такую историю видимой по
  supplier_id — это воспроизведено failing HTTP тестом. Unlinked legacy другого
  покупателя сохраняется по собственному основанию; неизвестная компания не
  выдаётся, при team mode standalone history доступна только leader.
- UI: отдельный issued flag/path, полная проверка списка КП/документов и result
  counts, свёрнутый перечень и подтверждение сохранения. При неопределённом
  результате повторяется тот же plan/reason. Scope/pending/keyboard safeguards
  переиспользованы. Старые режимы автоматически не приобретают финансовый отзыв.
- Проверены корректность/сохранность, границы типов/API, tenant/role/owner,
  retries/concurrency, читаемость и bounded запросы. Общие политики используются
  повторно; новые универсальные grants/deny-флаги не вводятся. Данные production
  и обычный процесс работы с договорами не менялись. Код в изолированном worktree.

Флаги `PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED` /
`REACT_APP_PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED` — default-off. Нужны
существующие support/connections/correction схемы/флаги. RFQ/quote флаги отдельно
не обязательны. Supplier-history read fix от нового mutation флага не зависит.

## Проверки

- 19 новых HTTP/PostgreSQL сценариев PASS. Реальные respond/select/create-invoice,
  shipment, receive, частичная отметка оплаты и project-payment в синтетической БД;
  реальный upload/download и сравнение точных байтов original. Снимки всех строк
  КП/счетов/поставок/накладных/склада/платежей/файлов/истории/пакетов до и после
  совпадают; прежние offer events сохраняются. Новые events/audit — отдельно.
- Проверены queued/in-flight, drift оплаты/файла, незакоммиченный writer, rollback
  audit, concurrent confirm/one event, role/company/default-off, owner ABA,
  несовместимые endpoint/operationId/reason, immutable expired copy, unknown FK,
  contract original, foreign/shared/deleted file, group/batch/receipt mismatch,
  reverse invoice/receipt, manager per-customer/per-offer и другие покупатели.
  Empty/pending/received работают без отдельных quote/RFQ флагов. Последние
  deterministic ordering изменения проверены двумя профильными PG сценариями.
- 84 прежних профильных PG сценария PASS: 14 quote, 14 RFQ, 13 unused, 8 preview,
  9 financial review, 9 support security, 17 capabilities. Ещё 11: 3 multicompany
  и 8 supplier team. Всего **114 различных PG сценариев**, без skips.
  Support security отказал 565 business operations до handler. Общий backend и
  remote CI не запускались; новый класс добавлен в mandatory CI.
- 13 unit tests supplier policy/supply-history routes PASS; py_compile и
  git diff --check PASS. Начальные новые endpoint/UI тесты были red; history
  regression отдельно показал реальную утечку после скрытия recipient.
  Невалидные ранние fixtures упёрлись в postpayment/estimate/contract FK guards:
  исправлены тестовые данные/план ресурса, рабочие guards не ослаблялись.
  Один запуск указал ошибочное имя multicompany class; исправленный запуск PASS.
- Frontend: 306 suites / **1901 tests PASS**. После сворачивания перечня и
  уточнения UI-теста — 3 профильных suites / 39 tests PASS. Финальная production
  сборка с issued UI flag PASS; прежние Browserslist/Node/bundle warnings остаются.
- Chromium: реальные компоненты/HTTP/отдельный Unix-only PG. Проверены план
  1 КП/1 счёт/1 поставка/1 накладная/1 original → причина/checkbox → keyboard
  Tab/Shift+Tab/Enter → итог → неактивная связь. 320/390/768/1440 без горизонтального
  переполнения, снимки телефона/desktop просмотрены. Отдельный счёт без КП дал
  ожидаемый 409 и не показал confirm. Смена компании закрыла старое окно.
  Консоль — React dev info и ожидаемый 409, без JavaScript exception.
  Это component+HTTP проверка, не новый полный App login/cookie test.
- После браузера сравнены business snapshots: неизменны. Серверы/браузер
  остановлены, private context, отдельная БД и временные uploads удалены.
  В synthetic receipt fixtures остаются предупреждения AI-задачи без владельца;
  старый multicompany fixture также сообщает неполную audit-error schema. Их
  операции/ассерты PASS; это не объявляется общей приёмкой AI/audit подсистем.

Origin/main после fetch — `d788bce9`, ветка включает его. Чужая основная рабочая
копия сохранена. Push, реальные аккаунты/приглашения/сообщения, production
платежи/склад, миграции и включение на сервере не выполнялись.

## Ограничения / точка продолжения

Дальше — standalone счета без КП и договоры/претензии, shared originals,
непроверенная/исторически объединённая история. Нужен отдельный сценарий отзыва
их собственного основания доступа; сейчас операция отказывает, сохраняя данные.
Повторная выдача прав новому участнику не выполняется этой командой.

Новый режим отзывает адресацию существующей точной цепочки, не создаёт глобальный
запрет кабинета и не отменяет последующие явно разрешённые бизнес-действия.
Уже доставленные/скачанные копии не отзываются; physical storage/CDN readiness
здесь не доказана. До production остаются company writer protocol вместо
глобальных SHARE/SRE locks, нагрузка/большие архивы (50 запросов/2000 строк/
100 originals), storage/CDN и отдельная интеграционная приёмка выпуска.

PR title: **Закрывать ошибочный доступ поставщика без отмены оформленных документов**.

PR description: Администратор может закрыть точную адресную цепочку КП, счетов,
поставок и приёмок. Документы, статусы, frozen parties, оплаты, склад и назначения
сохраняются. Живые policies проверяются в SELECT-only проекции; старые supplier
формы/файлы и supply-history больше не обходят отзыв. Самостоятельные основания
доступа блокируют команду и требуют отдельного разбора. Флаги и ограничения выше.
