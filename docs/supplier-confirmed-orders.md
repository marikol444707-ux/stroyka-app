# P7 — подтверждённые заказы поставщика

Заказ — проекция выбранного КП (Утверждено), а не новая запись. Самостоятельная
загрузка requests/offers/deliveries/invoices с проверкой сессии, ошибки скрывают
старые данные. Полученные сервером права сохраняются. Каждая связь проверяет
offerId/requestId/companyId/supplierId; неоднозначные строки не закрывают заказ.

По каждой позиции: заказано, отгружено, принято, осталось отгрузить, в пути,
осталось принять. Разные материалы/единицы/пакеты не суммируются. Принято меньше
заказанного → заказ не завершён, даже если запись поставки уже «Принято».
Приёмка с проблемой требует проверки. Несопоставимые позиции показываются как
требующие сверки, а не как нулевой остаток. Документы только связанные с данным КП.

Переход к действующим формам через исходную заявку. Повторная отгрузка после
приёмки сейчас запрещена сервером; для допоставки требуется отдельная заявка/КП.
P7 этот процесс не меняет. Счета и оплаты не изменяются.

Проверки: многострочные заказы, единицы/пакеты, частичная приёмка, чужие связи,
ошибки/загрузка, отозванные предложения, документы, мобильный браузер; выпуск
без миграции и без изменения backend.

## Validation and review

Full frontend: 191 suites / 1181 tests PASS. Additional projection/UI tests:
6 PASS, including malformed historic items. Final production build passed, including refresh button styling. No backend or
migration changes; production verification uses existing read-only smoke.

Browser on isolated PostgreSQL: selected quote, ordered2/shipped2/received1,
partial receipt with remaining1. Existing request navigation and reload work.
Injected invoices HTTP503 hides old orders; retry restores the order.
Desktop1440/mobile320 screenshots inspected; document width320, no overflow.
Baseline supplier company-material-aliases403 and facade preload warning remain;
the injected503 is expected. No new JavaScript execution errors.

Review: all four reads must succeed before publishing the snapshot; actor change
and errors clear data. Documents are linked by identity, never supplier names.
Unknown/cancelled shipment states, excess quantities and unmatched lines require
reconciliation. No request or financial records are created or modified.

Browser with another supplier: zero orders, no access to the tested order.
