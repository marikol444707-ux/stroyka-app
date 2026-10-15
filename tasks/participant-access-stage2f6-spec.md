# Срез 2е6: закрытие ошибочного доступа к оформленной цепочке КП

15.10.2026. Локальная разработка/изолированные синтетические испытания, без
production, реальных отправок, изменения платежей/склада или публикации.

## Цель и точная граница

Выполненное ошибочное подключение можно исправить и после выбора КП, выставления
счёта, отгрузки/приёмки, если вся затронутая история имеет точную адресацию через
КП и recipient. Команда закрывает visible_to_supplier, отменяет только queued
уведомления, отключает точную company_supplier_link и пишет atomic audit/events.
**Ни одна строка КП, счёта, поставки, накладной, оплаты или склада не меняется**.
Статусы КП и recipient сохраняются; полученное КП не отклоняется, заказ не отменяется.
Покупатель сохраняет архив, поставщик теряет следующую адресную операцию/файл.
Остальные покупатели/поставщики/карточки кабинета сохраняют прежний доступ.

Первый financial revoke path не исправляет standalone счёт без КП, договоры,
претензии, непроверенные назначения, общий original с независимым доступом, group/legacy
адресацию, неизвестную/чужую цепочку, in-flight доставку, исторический merge.
Такие случаи блокируются, а не теряют документы/права молча. Нужен current owner,
неизменные epochs/versions/evidence, human-approved requests и согласованные
КП/recipient. Недостаток схемы не означает отсутствие документов.

## Контракт и реализация

Отдельный POST .../connection-requests/{id}/issued-access-plans и
.../issued-access-plans/{plan}/confirm. Mode revoke_issued_access; новые default-off
PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED /
REACT_APP_PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED. Прежние correction paths
не получают новых полномочий. Переиспользовать immutable планы 0099, 15 минут,
свежую авторизацию, digest/блокировки, идемпотентный result, audit/события.
В плане exact IDs сохраняемых КП/счетов/поставок/накладных и число originals;
нет сумм/реквизитов/URL. Result revokedRequestCount и preserved document counts.
UI проверяет точные последствия, показывает «Закрыть доступ и отключить связь»,
просит причину/явное подтверждение. Нет выдачи прав новому адресату.

Общий request proof дополнить точным issued mode. Финансовый proof и SELECT-only
проекция закрытых recipients — отдельный correction_issued.py. Переиспользовать
реальные supplier policies, чтобы проверить доступ до/после: нельзя закрыть только
каталог и назвать это отзывом документов. Originals должны быть зарегистрированы
в компании; независимый путь к тому же original блокирует операцию. Байты и
metadata не меняются. Public/CDN/уже скачанные копии не отзываются этой командой.

Проверенные назначения менеджеров по покупателю/КП сохраняются; они не дают
обойти закрытого recipient. Служебные пакеты отгрузки/история сохраняются с точной
цепочкой. Supply-history GET для связанных записей обязан применять ту же live
policy; прямой supplier_id не должен обходить отзыв. Независимая legacy-история
другого покупателя остаётся по собственному основанию, без выдачи общего tenant.

## Проверки и код

Сначала failing HTTP/PG/UI regression, затем реализация. Практически проверить
реальные respond/select/create-invoice/ship/read/upload/download где доступны,
сохранность JSON/frozen parties/paid amounts/истории/склада, запрет старых supplier
форм/файлов, доступ покупателя/другого покупателя. Default-off/roles/company/
owner ABA, цены/оплаты/получатели/схема/очереди после плана, concurrent writer,
audit rollback, одинаковый confirm, endpoint/mode mismatch, expire и shared files.
Новые backend feature/test рядом, UI platform-admin, CI класс, ADR/план/приёмка.
Нет миграций или зависимостей. Python 3.9 Optional, фиксированные SQL/Identifier,
bounded queries и прежние лимиты 50 заявок/2000 строк/100 originals компании.

Команды: python3 scripts/run_supplier_catalog_postgres_tests.py
backend.features.participant_support.test_issued_access_corrections_postgres.SupplierIssuedAccessCorrectionsPostgresTests
и прежние corrections/preview/quote/RFQ/security группы. CI=true npm test --
--watchAll=false --runInBand; npm run build с UI-флагами; Chromium component+HTTP
с loopback/Unix-only PostgreSQL. Production writer protocol/load/storage/CDN
readiness остаются отдельными блокерами, общий этап 2 этим не завершается.
