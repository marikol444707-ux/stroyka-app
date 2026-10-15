# Срез 2е3: отзыв заявок без ответа при ошибочном подключении

15.10.2026. Продолжение 2е2 в том же изолированном worktree. Разрешена только
локальная разработка/синтетические испытания; production/push/отправки запрещены.

Цель: исправить связь, по которой отправлены RFQ, но поставщик ещё не ответил.
Новый отдельный путь rfq-correction-plans не меняет смысл старого unused-only API.
Backend/UI флаги PARTICIPANT_RFQ_CORRECTIONS_ENABLED и
REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED по умолчанию выключены.

План показывает компанию, кабинет и точные ID отзываемых заявок/получателей/
ожидаемых ответов, число отменяемых уведомлений. Используются существующие
immutable correction plans, 15-minute TTL, actor/owner epochs, юридическое
доказательство, версии связей, digest и атомарный audit. Новой миграции нет.
Разные типы плана нельзя подтверждать через другой endpoint.

Допустимы только явные адресаты target→target с текущим владельцем, без общей
группы других карточек, с подтверждённой компанией/исходной заявкой и пустыми
ожидающими ответами. Legacy selected_suppliers без авторитетного recipient,
ответ/цены/файл/выбранное КП, счета/поставки/договоры/назначения, общая адресация
этой заявки другой карточке того же кабинета, неизвестная принадлежность и
неопределённая/выполняющаяся отправка блокируют команду. Не более 50 заявок.

Подтверждение повторно проверяет весь план и атомарно:
- скрывает только точных получателей (visible_to_supplier=false, статус отозван);
- помечает только пустые ожидаемые ответы отозванными, не удаляет их;
- отменяет только ещё queued MAX/email, сохраняя завершённую историю доставки;
- отключает только созданную ошибочную связь, пишет результат и аудит.
Исходные заявки, selected_suppliers, цены/оплаты/party snapshots, другие
поставщики этой заявки и другие покупатели не переписываются. Обычная политика
recipient блокирует следующий read/respond и legacy fallback. Уже доставленное
письмо, скачивание или просмотр отменить нельзя — явно сообщить до подтверждения.

SHARE ROW EXCLUSIVE для изменяемых реестров предотвращает upgrade-deadlock двух
confirm; прочие predicate SHARE locks и ограничения 2е2 сохраняются. До production
нужен company writer protocol/нагрузочная приёмка. Внешний SMTP/MAX in-flight
не считается отменяемым: отказ и новый разбор после определённого результата.

Реализация: correction_rfqs.py — proof/apply/replay; correction_inventory.py и
corrections.py — расширение существующего механизма; SupplierConnectionCorrection
и модальное окно — точные последствия и подтверждение; профильные PG/UI tests,
mandatory CI, план/ADR/review. Стиль — существующие SQL placeholders/typed models,
без новых зависимостей и общего endpoint для произвольных таблиц.

Проверки: python3 scripts/run_supplier_catalog_postgres_tests.py
backend.features.participant_support.test_rfq_corrections_postgres.SupplierRfqCorrectionsPostgresTests
и существующая группа SupplierCorrectionsPostgresTests; CI=true npm test --
--watchAll=false --runInBand; npm run build с нужными UI-флагами; Chromium через
loopback/Unix-only disposable PG. Обязательны tenant/role/ABA, stale plan, повтор,
rollback audit, два concurrent confirm и ответ/worker между plan/confirm,
сохранность чужих поставщиков/покупателей, недоступность старой открытой формы,
точные ID/честные предупреждения/смена компании/телефон.

Исправление связи с полученным КП, счётом или историческим merge остаётся отдельным
блоком. Этот срез не обещает общий отзыв всех документов кабинета.
