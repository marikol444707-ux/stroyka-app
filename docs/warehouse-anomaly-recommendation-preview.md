# A9.1: Preview складских аномалий с точной связью источника

## Статус

Спецификация подтверждена, а pure A9.1 contract реализован и локально
проверен 2026-08-14. Он не зарегистрирован как API, handler, job или runtime,
не добавляет UI/feature flag и не выкладывался в production. A9.2 collector,
human-readable preview и любые apply-действия остаются отдельными срезами.

## Цель

Первый срез A9 должен превратить складские review-строки, зафиксированные в
одном строгом A7 combined report, в небольшой детерминированный список
рекомендаций для ручной проверки. Результат остаётся ID/code-only preview и никогда не
создаёт складское движение, корректировку остатка, инвентаризацию, задачу,
уведомление или модельный запрос.

A9.1 отвечает только на вопрос: «какие адресные A7 warehouse review-строки
присутствуют в этом exact estimate-revision snapshot и какая фиксированная
проверка им соответствует?». Он не доказывает отсутствие иных строк или
аномалий, не отвечает на вопрос «какой сейчас правильный остаток?» и не
рассчитывает количество для исправления.

## Архитектурные решения и предположения

1. Источник A9.1 — один уже построенный A7 combined report v1 с точными
   `companyId`, `projectId`, `estimateId`, `baseEstimateId`,
   `reconciliationId`, `sourceRevision`, `evidenceSha256`,
   `readOnlyTransaction=true`, `rolledBack=true` и `writesAttempted=0`.
2. Кандидаты берутся только из `domains.warehouse.needsReview`. A9.1 не
   перечитывает БД и не принимает отдельный список замечаний от вызывающего
   кода.
3. `domains.supply` обязан быть полностью готов: складская цепочка зависит от
   точных заявок, поставок и входящих документов. Любое supply-замечание,
   неполный scan или truncation блокирует весь результат без частичного списка.
4. Складской домен может быть `complete` без видимых review-строк или
   `review_required` с адресными замечаниями. Отсутствие замечаний означает
   `clear` в границах этого A7 snapshot, а не глобальную чистоту склада.
5. Аномалия становится кандидатом только при известной allowlisted причине и
   положительном `sourceId`. Redacted owner mismatch, invalid identity,
   неизвестная причина, системный `supply_warehouse_*` blocker или
   неоднозначность блокируют весь preview.
6. `subjectKind` выводится из точного allowlisted mapping `reasonCode`, а не из
   пользовательского текста. Если A7 сохранил `sourceKind`, он обязан
   согласоваться с выведенным типом.
7. Этот срез покрывает только structural/lineage anomalies внутри точного A7
   estimate-revision snapshot. Глобальная сверка текущих остатков, low-stock,
   расхождения инвентаризации и aggregate-versus-lot reconciliation отложены.
8. Клиентские `inventory_items.difference` нельзя считать авторитетным фактом:
   значение приходит от клиента, строки могут повторно добавляться, а явной
   семантики завершённой/последней инвентаризации нет. Будущий collector обязан
   перечитать exact owner, пересчитать `actual - expected`, определить
   уникальность и полноту snapshot и только затем передать нормализованные
   факты в отдельный контракт.
9. A9.1 — чистый stdlib-only модуль. Никакой route/job/UI/runtime registration,
   feature flag, SQL, connection factory, DDL/DML, `FOR UPDATE`, commit,
   provider/model, outbox или network dependency.
10. `evidenceSha256` доказывает каноническую целостность, но не является
    авторизацией или MAC. A9.1 остаётся незарегистрированным; любой будущий
    runtime обязан сам найти server-owned succeeded A7 job/report и заново
    проверить exact selected company/project access. Детальный all-companies
    mode и report JSON от клиента запрещены.

## Входной контракт

Функция `build_warehouse_anomaly_readiness(combined_report)` принимает только
полный A7 combined report. Валидатор обязан:

- потребовать точный набор top-level полей и точный `domainOrder` из пяти A7
  доменов;
- потребовать `ok=true`, `dryRun=true`, `writesAttempted=0`,
  `readOnlyTransaction=true` и `rolledBack=true`;
- строго проверить source IDs, reconciliation state и canonical
  `sha256:<64 lowercase hex>` revision;
- пересчитать A7 `evidenceSha256` и сравнить его с report;
- строго проверить shape, типы, limits и count equality у supply/warehouse
  domains, summaries, protected evidence, `reasonCounts` и `needsReview`;
- запретить extra fields в проверяемых структурах, bool-as-int, отрицательные
  IDs/counts, несортированные или повторяющиеся evidence IDs;
- ограничить каждый список существующим A7 `PREVIEW_LIMIT=100`;
- не возвращать exception text или business content при ошибке.

Поля других трёх доменов остаются частью A7 evidence hash, но их готовность не
гейтит этот warehouse-only срез.

Есть одно точное исключение из обычного равенства warehouse
`reasonCounts == needsReview`: A7 combined contract дублирует один системный
`supply_warehouse_*` count в supply и warehouse, но сохраняет его единственную
review-строку только в supply. Допустимы ровно четыре текущих кода:

```text
supply_warehouse_impact_schema_not_ready
supply_warehouse_project_identity_invalid
supply_warehouse_scan_limit_exceeded
supply_warehouse_source_snapshot_invalid
```

Такой gap принимается только когда один код имеет count `1` в обоих доменах,
а supply содержит одну exact review-строку с `sourceKind=supplyWarehouse` и
`sourceId=null`. После валидации результат становится `blocked` с
`warehouse_anomaly_systemic_source_incomplete`. Любой другой count/review gap,
повтор или shape — contract error `warehouse_anomaly_relevant_domain_invalid`.

## Allowlist адресных аномалий

Первый срез принимает только причины, уже создаваемые A7 warehouse projection:

| Семейство | Допустимые адресные причины | `subjectKind` | `recommendationCode` |
| --- | --- | --- | --- |
| Накладная | request/project/delivery/supplier-invoice mismatch | `warehouseInvoice` | `review_warehouse_invoice_lineage` |
| Накладная | items invalid | `warehouseInvoice` | `review_warehouse_invoice_items` |
| Приход | invoice/line/package mismatch | `warehouseHistory` | `review_warehouse_receipt_lineage` |
| Партия | invoice/line/project mismatch | `receiptLot` | `review_receipt_lot_lineage` |
| Перемещение | invoice/line/package mismatch | `warehouseMovement` | `review_warehouse_movement_lineage` |
| Перемещение | receipt lot missing / lot movement missing | `warehouseMovement` | `review_warehouse_movement_traceability` |
| Проводка партии | parent/source mismatch | `lotMovement` | `review_lot_movement_lineage` |

Точный immutable mapping v1 содержит только следующие пары:

```text
warehouse_invoice_request_mismatch          -> review_warehouse_invoice_lineage
warehouse_invoice_project_mismatch          -> review_warehouse_invoice_lineage
warehouse_invoice_delivery_mismatch         -> review_warehouse_invoice_lineage
warehouse_invoice_supplier_invoice_mismatch -> review_warehouse_invoice_lineage
warehouse_invoice_items_invalid             -> review_warehouse_invoice_items
warehouse_receipt_invoice_mismatch          -> review_warehouse_receipt_lineage
warehouse_receipt_line_invalid              -> review_warehouse_receipt_lineage
warehouse_receipt_package_mismatch           -> review_warehouse_receipt_lineage
warehouse_receipt_lot_invoice_mismatch      -> review_receipt_lot_lineage
warehouse_receipt_lot_line_invalid          -> review_receipt_lot_lineage
warehouse_receipt_lot_project_mismatch      -> review_receipt_lot_lineage
warehouse_movement_invoice_mismatch         -> review_warehouse_movement_lineage
warehouse_movement_line_invalid             -> review_warehouse_movement_lineage
warehouse_movement_package_mismatch          -> review_warehouse_movement_lineage
warehouse_movement_lot_missing              -> review_warehouse_movement_traceability
warehouse_lot_movement_missing              -> review_warehouse_movement_traceability
warehouse_lot_movement_parent_mismatch      -> review_lot_movement_lineage
warehouse_lot_movement_source_mismatch      -> review_lot_movement_lineage
```

`subjectKind` также выводится этим exact mapping. Shape входной review-строки
зависит от семейства и не допускает свободной вариативности:

- invoice-коды обязаны содержать `sourceKind=warehouseInvoice`;
- receipt и receipt-lot коды не должны содержать `sourceKind` — A7 combined
  sanitizer отбрасывает underscored raw kinds;
- movement invoice/line/package mismatch также не содержит `sourceKind`;
- movement lot/link missing обязан содержать
  `sourceKind=warehouseMovement`;
- lot-movement parent/source mismatch обязан содержать
  `sourceKind=lotMovement`.

`subjectKind=warehouseHistory` и `subjectKind=receiptLot` выводятся только в
результате; caller-invented одноимённый `sourceKind` во входе запрещён.

Prefix-only acceptance запрещён. Точные текущие non-candidate причины и их
результат:

```text
warehouse_invoice_identity_invalid           -> warehouse_anomaly_subject_invalid
warehouse_invoice_owner_mismatch              -> warehouse_anomaly_subject_invalid
warehouse_receipt_identity_invalid           -> warehouse_anomaly_subject_invalid
warehouse_receipt_owner_mismatch              -> warehouse_anomaly_subject_invalid
warehouse_receipt_lot_identity_invalid       -> warehouse_anomaly_subject_invalid
warehouse_receipt_lot_owner_mismatch          -> warehouse_anomaly_subject_invalid
warehouse_movement_identity_invalid          -> warehouse_anomaly_subject_invalid
warehouse_movement_owner_mismatch             -> warehouse_anomaly_subject_invalid
warehouse_lot_movement_identity_invalid      -> warehouse_anomaly_subject_invalid
warehouse_lot_movement_owner_mismatch         -> warehouse_anomaly_subject_invalid
warehouse_invoice_items_limit_exceeded       -> warehouse_anomaly_source_items_limit_exceeded
```

Для этих строк действуют те же exact family `sourceKind` rules, что выше;
каждая строка обязана содержать `sourceId`, но owner mismatch обязан иметь
redacted `sourceId=null`. Четыре exact systemic кода имеют отдельную форму и
blocker, описанные во входном контракте. Любой иной well-formed код получает
`warehouse_anomaly_reason_unsupported`; invented suffix не принимается как
известный класс. Строка candidate-кода без положительного `sourceId`,
source-kind mismatch или дубликат
`(subjectKind, subjectId, anomalyCode)` получает соответствующий blocker.

Они возвращают фиксированный blocker и пустой список кандидатов. Частичный
preview при наличии blocker запрещён.

## Выходной контракт

```json
{
  "warehouseAnomalyReadinessVersion": 1,
  "ok": true,
  "dryRun": true,
  "writesAttempted": 0,
  "previewOnly": true,
  "stockMovementAllowed": false,
  "inventoryAdjustmentAllowed": false,
  "applyAllowed": false,
  "state": "ready",
  "source": {
    "companyId": 1,
    "projectId": 2,
    "estimateId": 3,
    "sourceRevision": "sha256:...",
    "reconciliationId": 4,
    "baseEstimateId": 5,
    "impactEvidenceSha256": "..."
  },
  "classificationComplete": true,
  "readyForRecommendationPreview": true,
  "candidateCount": 1,
  "candidates": [
    {
      "subjectKind": "warehouseMovement",
      "subjectId": 6,
      "anomalyCode": "warehouse_movement_lot_missing",
      "recommendationCode": "review_warehouse_movement_traceability"
    }
  ],
  "blockers": []
}
```

Допустимые состояния:

- `ready`: classification complete, есть хотя бы один candidate;
- `clear`: classification complete, в этом A7 snapshot нет адресных warehouse
  review-строк для текущего allowlist;
- `blocked`: classification incomplete/unsafe, candidates всегда пусты.

`readyForRecommendationPreview=true` только в `ready`.
`classificationComplete=true` в `ready` и `clear`. Кандидаты сортируются по
`subjectKind`, `subjectId`, `anomalyCode`; blockers сортируются и
дедуплицируются. Выход не содержит material/project/supplier names, unit,
quantity, price, notes, actor/session data или свободный текст.

Точные state invariants:

- `ready`: `classificationComplete=true`,
  `readyForRecommendationPreview=true`, `candidateCount > 0`;
- `clear`: `classificationComplete=true`,
  `readyForRecommendationPreview=false`, `candidateCount=0`;
- `blocked`: `classificationComplete=false`,
  `readyForRecommendationPreview=false`, `candidateCount=0`, `candidates=[]`.

`classificationComplete` означает только, что все безопасно видимые A7
warehouse review rows классифицированы. Оно не доказывает актуальный остаток,
полноту downstream invoice-line causality или готовность stock correction.

## Фиксированные ошибки контракта и blockers

Ошибки строгой валидации выбрасываются как fixed-code exception:

- `warehouse_anomaly_report_invalid`;
- `warehouse_anomaly_source_invalid`;
- `warehouse_anomaly_evidence_invalid`;
- `warehouse_anomaly_relevant_domain_invalid`;
- `warehouse_anomaly_candidate_limit_exceeded`.

После успешной валидации безопасные ограничения возвращаются в `blockers`:

- `warehouse_anomaly_supply_not_ready`;
- `warehouse_anomaly_schema_not_ready`;
- `warehouse_anomaly_scan_incomplete`;
- `warehouse_anomaly_facts_truncated`;
- `warehouse_anomaly_reviews_truncated`;
- `warehouse_anomaly_systemic_source_incomplete`;
- `warehouse_anomaly_source_items_limit_exceeded`;
- `warehouse_anomaly_reason_unsupported`;
- `warehouse_anomaly_subject_invalid`;
- `warehouse_anomaly_duplicate_candidate`.

Безопасно классифицированные, но заблокированные warehouse facts возвращают
обычный `blocked` result. В обоих случаях exception/business text наружу не
попадает.

## Технологии и структура

Только Python standard library и существующие pure A7 contract helpers:

```text
backend/features/warehouse_recommendation_preview/
  __init__.py
  readiness.py
  test_readiness.py
```

Публичный API пакета ограничен version constant, fixed-code exception и
`build_warehouse_anomaly_readiness`. SQL/service/route файлы в A9.1 не нужны.

## Стиль кода

Следовать строгому стилю A8.1, включая точные field sets:

```python
def _strict_mapping(value, fields, code):
    if not isinstance(value, Mapping) or set(value) != set(fields):
        _fail(code)
    return value
```

Allowlist причин — immutable mapping literal. Никаких fallback по имени,
substring/prefix acceptance, caller-supplied recommendation text или
неограниченных comprehensions над входом. Функция не мутирует вход.

## Стратегия тестирования

Разработка начинается с RED import test, затем покрывает:

1. один точный кандидат каждого allowlisted семейства;
2. детерминированный порядок, повторный вызов и неизменность входа;
3. валидный warehouse domain без адресных review-строк -> `clear` без blocker;
4. owner mismatch и redacted/null `sourceId` -> `blocked`, без утечки ID;
5. identity invalid, items overflow, systemic supply/warehouse reason,
   неизвестный reason/source kind -> `blocked`;
6. supply domain review/incomplete/truncated -> `blocked`;
7. schema/scan/facts/reviews truncation -> `blocked`;
8. duplicate tuple, два разных anomaly codes одного subject, invalid ID,
   extra/missing field и `>100` candidates; только exact duplicate блокирует;
9. ordinary reason/summary/review/protected-evidence count mismatch и точный
   допустимый cross-domain systemic gap;
10. source, report shape и evidence hash tamper;
11. unrelated assignments/materials/economics readiness не гейтит результат,
    но полный report shape и evidence hash остаются валидными;
12. статический scan запрещает SQL, DB factories, route/job/runtime/model,
    network и warehouse/inventory writer imports.
13. missing camel-case `sourceKind` и injected `sourceKind` для underscored
    families fail closed по exact generated shape.

Проверки после GREEN:

```bash
python3 -m unittest backend.features.warehouse_recommendation_preview.test_readiness
python3 -m unittest discover -s backend/features/estimate_revision_impact -p 'test_*.py'
python3 -m unittest discover -s backend -p 'test_*.py'
python3 -m py_compile backend/features/warehouse_recommendation_preview/*.py
git diff --check
```

Frontend test/build, PostgreSQL, browser и production smoke для A9.1 не
применимы: срез не добавляет frontend, collector, route, handler, job, schema,
flag или deploy behavior.

## Границы

### Всегда

- один точный A7 source и его canonical evidence hash;
- только ID/code output, fixed bounds и fail-closed whole-result behavior;
- `previewOnly=true`, все apply/movement/adjustment флаги false;
- ноль чтений/записей БД и внешних вызовов.

### Спросить отдельно

- A9.2 read-only collector или выбранный-candidate content preview;
- API, роль, selected-company UI, browser flow или feature flag;
- новая authoritative inventory snapshot semantics;
- production deployment или user-visible enablement.

### Никогда в A9.1

- рассчитывать или предлагать correction/movement quantity;
- менять `materials`, `warehouse_main`, lots, movements, history, inventory;
- связывать строки по material/project name, fuzzy match или implicit alias;
- считать aggregate stock равным сумме receipt lots без полноты всех writers;
- создавать task, notification, outbox, report, model prompt или audit row;
- вызывать существующий write-capable `GET /warehouse-invoices` handler.

## Зависимости

- A7 combined report v1 и его canonical evidence hash уже реализованы и
  остаются единственным входным форматом A9.1.
- A8.1 служит стилевым образцом строгого pure readiness contract, но A9.1 не
  вызывает supply recommendation code и не расширяет его публичный API.
- Незавершённый A8.4c2d и отложенное устранение production secret-at-rest
  инцидента не входят в эту локальную спецификацию и по-прежнему блокируют
  отдельную UI/production выкладку.

## Последующие срезы

- A9.2 может в одной bounded read-only `REPEATABLE READ` транзакции заново
  разрешить current exact source, перестроить relevant supply+warehouse
  projection и A9.1 readiness, сопоставить выбранный candidate с текущим
  результатом и только затем построить human-readable content preview. Любой
  disappeared/newly blocked/truncated/drifted evidence отклоняется; транзакция
  всегда rollback и без apply.
- Отдельный inventory slice сначала должен определить finalized snapshot,
  пересчитывать арифметику на сервере, устранять duplicate rows, строго
  проверять owner/project/package и маркировать incomplete sources.
- UI позже размещается в read-only складском контроле, но только после exact
  `companyContext` plumbing. Он fail-closed при loading/all-companies/неточной
  effective selected-company role, загружается только по явному клику,
  key/abort/ignore stale response при смене company/project и не использует
  текущие client reconciliation/inventory arrays как authority. Состояния
  `idle/loading/clear/ready/blocked/error` и весь текст фиксированы; raw HTML
  через печатный `PreviewModal` и кнопки перемещения/корректировки запрещены.
- Любой будущий apply относится минимум к A12 и требует нового server preview,
  human approval, audit, idempotency, concurrency и rollback contract.

## Критерии успеха

- Один валидный A7 report даёт тот же bounded ID/code-only результат при каждом
  запуске и не меняет вход.
- Любая неопределённость, truncation, tamper или drift, представленные и
  проверяемые во входном A7 report, не допускают список кандидатов.
- Snapshot без адресных allowlisted A7 review-строк честно возвращает `clear`,
  не утверждая, что склад или текущая БД свободны от других аномалий.
- В production/runtime ничего не меняется.

## Открытые вопросы

Открытых вопросов для этой узкой спецификации нет. Главная граница уже выбрана:
зафиксированные A7 lineage review-строки входят в A9.1; глобальные остатки и
инвентаризационные расхождения требуют отдельного доказанного collector.
