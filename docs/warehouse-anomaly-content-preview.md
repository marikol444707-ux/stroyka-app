# Spec: A9.2 — текущая read-only проверка одной складской аномалии

## Статус

Спецификация и PLAN/TASKS утверждены человеком 2026-08-14. TDD-инкременты
A9.2a–A9.2e завершены локально и независимо проверены. Финальные уникальные
прогоны: combined A9.1+A9.2 `67/67`, A7 `117/117` с 11 ожидаемыми skip и full
backend `1953/1953` с 56 ожидаемыми skip; compile/diff/static gates зелёные,
три свежих ревью не нашли оставшихся Critical/Required замечаний. API, UI,
feature flag, database schema и production runtime по этой спецификации не
создавались. Утверждённый private file split и exact producer bounds/reason
surface ниже не меняют A7/A9.1 public contracts.

## Objective

A9.2 должен принять одну выбранную A9.1 аномалию из доверенного server-owned
A7 report, заново собрать текущий relevant supply+warehouse A7 snapshot в
одной PostgreSQL `REPEATABLE READ` read-only транзакции и после фактического
rollback показать
человеку короткое фиксированное объяснение только в том случае, если тот же
exact candidate всё ещё присутствует в полностью валидном A9.1 результате.

Пользователь результата — будущий авторизованный сотрудник выбранной компании,
которому нужно понять, какую связь первичных складских фактов проверить вручную.
A9.2 не отвечает на вопросы «какой остаток правильный?» и «какую корректировку
применить?», не читает inventory discrepancy как authoritative evidence и не
готовит stock movement.

Успех означает:

- tenant/source-inconsistent stored evidence нельзя превратить в content
  preview; provenance остаётся обязательной caller/runtime precondition;
- current source/supply/warehouse evidence перечитано существующим bounded A7
  collectors, а не ослабленным subject-only SQL;
- business text появляется только после успешного rollback и exact current
  candidate match;
- результат всегда preview-only и не содержит пути к apply.

## Предположения и архитектурные решения

1. A9.2 остаётся внутренним незарегистрированным server-side модулем. Первый
   срез не добавляет auth adapter, route, handler, job, CLI или UI.
2. `evidenceSha256` — контроль целостности, не provenance и не авторизация.
   Входной A7 report допустим только как in-process result или server-owned
   succeeded A7 artifact, уже полученный доверенным вызывающим кодом. Client
   report JSON запрещён. Будущий runtime обязан сначала аутентифицировать
   cookie-session, разрешить exact selected company/project и самостоятельно
   загрузить artifact; это отдельная спецификация. Сам внутренний A9.2 interface
   не может криптографически доказать происхождение переданного Python mapping.
   Поэтому A9.2 отклоняет malformed, hash-mismatched и report-internal
   inconsistent mappings, но не обещает распознать заново корректно
   канонизированный и перехэшированный чужой mapping. Его происхождение и
   авторизованная tenant-привязка остаются обязательной precondition caller и
   будущего runtime adapter.
3. Вызывающий код передаёт только strict A7 combined report и selection
   `{subjectKind, subjectId, anomalyCode}`. `recommendationCode`, company,
   project, source revision и evidence hash из selection не принимаются — они
   повторно выводятся из validated A9.1 readiness.
4. До открытия connection A9.2 проверяет размер и строгую форму доверенного
   report, запускает A9.1 и требует ровно один selected candidate. Invalid или
   уже blocked stored report отклоняется фиксированным exception code.
5. Внутри единственной transaction A9.2 использует существующий
   `collect_supply_warehouse_impact_audit(cur, source)`. Это намеренно сильнее
   отдельной выборки warehouse subject и уже проверяет current exact estimate,
   reconciliation, supply и warehouse lineage с существующими caps, но не
   перечитывает unrelated assignment/material/economics domains.
6. После rollback pure `build_combined_report()` создаёт truthful пятидоменный
   envelope из current source и current `supplyWarehouseImpact`; assignment,
   material и economics явно остаются `not_collected`/incomplete, а не берутся
   из stored report. Envelope получает truthful transaction metadata и только
   затем передаётся в `build_warehouse_anomaly_readiness()`.
7. Preparation сохраняет exact stored source tuple: `companyId`, `projectId`,
   `estimateId`, `sourceRevision`, `reconciliationId`, `baseEstimateId` и
   `reconciliationStatus`. Current collected report обязан иметь тот же tuple.
   Одного совпадения candidate недостаточно: reconciliation ID/status могут
   измениться, сохранив тот же warehouse review ID/code.
8. Если current collector честно возвращает `sourceReady=false` или
   `readyForDomainScan=false`, content отсутствует и state=`blocked` с fixed
   `warehouse_anomaly_current_source_not_ready`; публичный revalidated relevant
   hash равен `null`. Это ожидаемый outcome, например при
   `source_revision_mismatch`, а не
   повод подделывать current combined report.
9. Если source-ready current A9.1 blocked/incomplete, content отсутствует и
   state=`blocked`. Если source-ready tuple изменился, snapshot стал `clear`
   либо exact candidate исчез/изменился, state=`stale`. Только exact source и
   ровно один exact current candidate дают state=`preview_ready`.
10. A9.2 вычисляет отдельный canonical relevant-evidence SHA-256 над exact
   seven-field source и полными normalized `domains.supply` +
   `domains.warehouse`. Stored и current relevant hashes обязаны совпасть.
   Любое изменение normalized supply/warehouse contract, включая
   новый/исчезнувший candidate, закрывает preview как `stale`.
   Assignment/material/economics не входят в этот hash и не создают unrelated
   cross-domain churn.
   Это равенство normalized A7 contract, не побайтовое доказательство всех raw
   DB values: данные, которые A7 projection намеренно не сохраняет, hash не
   связывает. Поэтому A9.2 не выводит quantities и не утверждает raw-fact
   equality.
11. Content — только фиксированные allowlisted русские строки из кода плюс
   положительный subject ID. Имена проекта, материала, поставщика, пользователя,
   notes, цены, количества, контакты, raw JSON/SQL и model prose запрещены.
12. A9.2 не меняет A7/A9.1 public contracts. Если implementation потребует
    ослабить их validation или проставить `rolledBack=true` до реального
    rollback, нужно остановиться и пересогласовать спецификацию.
13. Без subject-specific SQL A9.2 — gate актуальности и локализации, а не
    remediation dossier. Он сообщает fixed reason/action и subject ID, но не
    показывает expected/actual parent IDs и не говорит, что именно переписать.
    Это осмысленно только как будущая ссылка на уже авторизованный просмотр
    первичного объекта; добавлять для «удобства» names/quantities нельзя.

## Tech Stack

- Python stdlib для validation, canonical JSON и SHA-256.
- Существующий `psycopg2`/`RealDictCursor` только в transaction runner.
- PostgreSQL read-only `REPEATABLE READ`.
- Существующие A7 `collect_supply_warehouse_impact_audit()`,
  `build_combined_report()` и A9.1 `build_warehouse_anomaly_readiness()` без
  нового data-access слоя.
- `unittest`; новые зависимости запрещены.

## Commands

RED/GREEN focused suite:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a9-content-pycache \
python3 -m unittest \
  backend.features.warehouse_recommendation_preview.test_content_contract \
  backend.features.warehouse_recommendation_preview.test_content_preview
```

Related A9 regression:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a9-content-pycache \
python3 -m unittest \
  backend.features.warehouse_recommendation_preview.test_readiness \
  backend.features.warehouse_recommendation_preview.test_content_contract \
  backend.features.warehouse_recommendation_preview.test_content_preview
```

A7 contract regression:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a9-content-pycache \
python3 -m unittest discover \
  -s backend/features/estimate_revision_impact -p 'test_*.py'
```

Full backend and static verification:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a9-content-pycache \
python3 -m unittest discover -s backend -p 'test_*.py'

PYTHONPYCACHEPREFIX=/private/tmp/a9-content-pycache \
python3 -m py_compile \
  backend/features/warehouse_recommendation_preview/content_contract.py \
  backend/features/warehouse_recommendation_preview/content_preview.py \
  backend/features/warehouse_recommendation_preview/test_content_contract.py \
  backend/features/warehouse_recommendation_preview/test_content_preview.py

git diff --check
```

No frontend build, browser or production smoke belongs to this unregistered
server-only slice. A disposable PostgreSQL proof is required only if fake-cursor
tests cannot prove rollback/error precedence and read-only transaction settings.

## Project Structure

```text
backend/features/warehouse_recommendation_preview/
  readiness.py              # существующий pure A9.1 contract; не ослаблять
  content_contract.py       # private pure prepare/raw/current/content contract
  content_preview.py        # единственный exported module: transaction runner
  test_readiness.py         # существующая A9.1 regression suite
  test_content_contract.py  # pure contract and producer-shape tests
  test_content_preview.py   # transaction/error-precedence/static tests

backend/features/estimate_revision_impact/
  supply_warehouse_audit.py # существующий caller-owned relevant collector
  combined_contract.py      # pure truthful five-domain envelope/hash builder
  contract.py               # exact EstimateRevisionSource contract

docs/
  warehouse-anomaly-recommendation-preview.md # утверждённая A9.1 граница
  warehouse-anomaly-content-preview.md        # эта A9.2 спецификация
```

A9.2 не должен добавлять файлы в `routes.py`, `backend/main.py`, frontend,
agent jobs, migrations, model/provider, notifications или warehouse writers.
Существующий package `__init__.py` и его A9.1 `__all__` остаются byte-unchanged:
A9.2 импортируется только из `content_preview.py`, пока отдельное package-level
API не будет явно согласовано.

## Internal Interface Contract

### Preparation

Единственный exported A9.2 interface живёт в модуле `content_preview.py`:

```python
def run_warehouse_anomaly_content_preview(get_db, combined_report, selected):
    """Collect once, roll back unconditionally, then finalize fixed content."""
```

Внутренние seams не входят в `__all__`:

```python
def _prepare_warehouse_anomaly_content(combined_report, selected):
    """Return one private frozen prepared value after strict preflight."""

def _collect_current_warehouse_anomaly_evidence(cur, prepared):
    """Return evidence only; never content or transaction-completion flags."""
```

Prepared value — private `@dataclass(frozen=True)` (или эквивалентный exact
immutable type), а не caller-forgeable dict. Collector требует именно этот type
и никогда не возвращает human-readable content, `readOnlyTransaction` или
`rolledBack`. Отдельный public caller-cursor seam потребует новой спецификации.

`selected` обязан иметь точный набор полей:

```json
{
  "subjectKind": "warehouseInvoice",
  "subjectId": 123,
  "anomalyCode": "warehouse_invoice_project_mismatch"
}
```

- `subjectKind` и `anomalyCode` должны соответствовать A9.1 allowlist;
- `subjectId` — положительный `int`, `bool` запрещён;
- extra/missing keys, strings вместо ID и caller-supplied recommendation code
  отклоняются до `get_db()`;
- canonical stored report не больше `4 MiB`; overflow, recursion, NaN или
  non-JSON value дают fixed input error до connection.

Preparation возвращает immutable/deep-copied plan с exact A7
`EstimateRevisionSource`, всеми семью stored source fields, original evidence
SHA, stored relevant evidence SHA и полным derived A9.1 candidate. Он не
сохраняет raw report и не содержит business text.

### Transaction and current revalidation

Runner обязан:

1. проверить callable dependencies и выполнить preparation до connection;
2. открыть ровно одну connection и вызвать
   `set_session(readonly=True, autocommit=False,
   isolation_level="REPEATABLE READ")`;
3. выставить transaction-local `statement_timeout=60000`,
   `lock_timeout=5000`, `idle_in_transaction_session_timeout=60000` и
   `search_path=pg_catalog,public` через parameterized
   `pg_catalog.set_config(..., true)`;
4. вызвать `collect_supply_warehouse_impact_audit(cur, source)` ровно один раз;
   require exact wrapper keys
   `{reportVersion,ok,dryRun,writesAttempted,schemaReady,missingColumns,
   scanComplete,sourceReady,readyForDomainScan,source,summary,issueCount,
   reasonCounts,issues,issuesTruncated,readyForSupplyWarehouseProjection,
   supplyWarehouseImpact}`, `reportVersion=1`, `ok=true`, `dryRun=true`,
   `writesAttempted=0`, strict boolean flags, bounded list/mapping fields and
   mapping `source`/`supplyWarehouseImpact`;
5. до любого business-result проверить cross-field coherence exact A7 wrapper:
   - outer `missingColumns` является sorted unique subset из 17 exact baseline
     `REQUIRED_COLUMNS` table/column pairs либо exact singleton
     `schema_scan_limit_exceeded`; произвольный `table.column` запрещён;
   - outer `summary` всегда имеет ровно `{estimateRows,reconciliationRows}` с
     non-negative exact-int значениями `estimateRows <= 2` и
     `reconciliationRows <= 101`; `issueCount == sum(reasonCounts.values())`,
     `len(issues) == min(issueCount, 100)` и
     `issuesTruncated == (issueCount > 100)` до более строгих ready/non-ready
     правил ниже;
   - четыре core source field (`companyId`, `projectId`, `estimateId`,
     `sourceRevision`) byte/value-equal запрошенному `EstimateRevisionSource`;
     их drift невозможен для корректного collector и означает
     `warehouse_anomaly_content_current_report_invalid`, а не business `stale`;
   - `sourceReady == readyForDomainScan`; ready source требует
     `schemaReady=true`, `scanComplete=true`, пустые `missingColumns`,
     `issueCount=0`, пустые `reasonCounts`/`issues`,
     `issuesTruncated=false`, exact seven-field source и exact baseline summary
     keys `{estimateRows,reconciliationRows}` со значениями `1,1`;
   - non-ready source требует `readyForDomainScan=false`, только exact
     four-field source без reconciliation fields, корректный существующий A7
     baseline issue и exact canonical `supplyWarehouseImpact` state
     `not_collected` с `complete=false`; outer baseline в этом случае имеет
     exact summary keys с bounded non-negative exact-int counts,
     `issueCount=1`, one-entry exact known baseline `reasonCounts`, ровно один
     issue с exact keys `{reasonCode,companyId,projectId,estimateId}` и requested
     core IDs, `issuesTruncated=false`;
   - outer `missingColumns` повторно удовлетворяет exact 17-pair-or-sentinel
     правилу выше, `schemaReady == (missingColumns == [])`; outer
     summary/reason/issue mappings не принимают extra keys, unknown reason или
     bool-as-int;
   - `readyForSupplyWarehouseProjection` exact-equal
     `supplyWarehouseImpact.complete`; source-ready projection не может иметь
     state=`not_collected`; до permissive `build_combined_report()` raw
     projection обязан пройти отдельную exact validation, описанную ниже;
   любая contradiction даёт current-report exception без partial result;
6. не требовать raw `readyForSupplyWarehouseProjection=true`: allowlisted
   warehouse review намеренно делает общий projection non-complete, и решение
   о допустимости принадлежит A9.1 после split supply/warehouse domains;
7. всегда выполнить rollback; commit запрещён;
8. закрыть cursor и connection;
9. после успешного rollback вернуть fixed blocked result, если current source
   не ready; только для source-ready wrapper потребовать exact current source и
   mapping `supplyWarehouseImpact`, вызвать `build_combined_report()` с ними и
   пустыми остальными projections, добавить runner metadata, выполнить A9.1,
   exact seven-field source comparison и exact candidate match;
10. не выдавать result при rollback failure; control-flow exceptions
   `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` не маскировать;
11. использовать приоритет ошибок: control flow → rollback failed → read failed
   → cleanup failed → current report invalid.

Control-flow priority относится ко всем фазам, включая `get_db`, session/cursor,
collector, rollback, cursor close и connection close. Runner сохраняет первый
`KeyboardInterrupt`/`SystemExit`/`GeneratorExit`, best-effort выполняет ещё не
выполненные rollback/cleanup шаги ровно один раз и затем re-raise исходный
control-flow exception без fixed-code wrapping.

Business-result precedence после успешного rollback строго фиксирован:

1. current source not ready → `blocked/current_source_not_ready`;
2. source-ready drift только трёх reconciliation fields (`reconciliationId`,
   `baseEstimateId`, `reconciliationStatus`) → `stale/source_drift`; drift
   любого из четырёх requested core fields уже отклонён как malformed current
   report;
3. current A9.1 blocked → `blocked/current_snapshot_blocked`;
4. exact selected candidate отсутствует/изменён → `stale/candidate_stale`;
5. selected candidate сохранился, но relevant hash изменился →
   `stale/relevant_evidence_drift`;
6. иначе → `preview_ready`.

SQL разрешён только внутри уже reviewed A7 collectors и для transaction-local
settings. A9.2 не добавляет собственный warehouse subject `SELECT`, DDL, DML,
`FOR UPDATE`, advisory lock или вызов write-capable HTTP handler.

Raw `supplyWarehouseImpact` нельзя считать валидным только потому, что
`build_combined_report()` смог его нормализовать. Нормализатор намеренно
отбрасывает extra fields и пересчитывает часть state/count/truncation данных,
поэтому перед ним A9.2 требует exact producer contract:

- точный набор верхнеуровневых полей
  `{state,schemaReady,missingColumns,scanComplete,complete,summary,openSupply,
  protectedEvidence,factsTruncated,reasonCounts,needsReview,
  needsReviewTruncated}` без extras;
- exact boolean types; `state` только `complete`, `incomplete`,
  `review_required` или `not_collected`; `missingColumns` — sorted unique
  список, который является subset из 59 exact
  `SUPPLY_WAREHOUSE_REQUIRED_COLUMNS` table/column pairs либо exact singleton
  `schema_scan_limit_exceeded`; произвольные `table.column` strings запрещены,
  и `schemaReady == (missingColumns == [])`;
- `summary` имеет ровно 14 producer fields: `supplyRequestRows`, `supplyItems`,
  `openSupplyItems`, `protectedSupplyItems`, `closedSupplyRequests`,
  `deliveries`, `allocations`, `supplierInvoices`, `warehouseInvoices`,
  `warehouseHistoryRows`, `receiptLots`, `warehouseMovements`, `lotMovements`,
  `needsReview`; каждое значение — bounded non-negative exact `int`, не `bool`.
  Producer-derived bounds в v1: `supplyRequestRows <= 100`,
  `supplyItems <= 100 * supplyRequestRows <= 10000`,
  `openSupplyItems <= supplyItems`,
  `protectedSupplyItems <= supplyItems`,
  `openSupplyItems + protectedSupplyItems <= supplyItems`,
  `closedSupplyRequests <= supplyRequestRows`; каждый из восьми downstream
  counts от `deliveries` до `lotMovements` не больше 100; `needsReview` не
  больше 10800. Эти bounds выводятся из 100 requests, 100 items на request и
  восьми downstream scans по 100 rows, а не принимаются из caller metadata.
  Они относятся к exact audit collector path; прямой вызов pure projection
  builder с произвольно большими списками не является допустимым A9.2 input;
- `protectedEvidence` имеет ровно девять producer ID lists:
  `closedSupplyRequestIds`, `deliveryIds`, `allocationIds`,
  `supplierInvoiceIds`, `warehouseInvoiceIds`, `warehouseHistoryIds`,
  `receiptLotIds`, `warehouseMovementIds`, `lotMovementIds`; каждая — sorted
  unique positive-int list не длиннее 100;
- каждый `openSupply` item имеет ровно
  `{requestId,requestItemIndex,sourceEstimateId,sourceSectionIndex,
  sourceItemIndex,state}`, положительные IDs, non-negative indices,
  `requestItemIndex < 100`, `state=open_balance`, exact
  `sourceEstimateId=source.baseEstimateId`; список
  bounded 100, lexicographically sorted по
  `(requestId,requestItemIndex,sourceSectionIndex,sourceItemIndex)` и без
  duplicate item tuples; дополнительно producer запрещает повтор source
  coordinate `(requestId,sourceSectionIndex,sourceItemIndex)` даже при разных
  `requestItemIndex`;
- каждый raw review имеет ровно `{sourceKind,sourceId,reasonCode}`; kind/code и
  nullable/positive non-bool ID обязаны соответствовать exact существующей A7
  supply/warehouse reason-to-shape allowlist из 71 текущего producer code
  (65 явных audit/projection call-site codes плюс шесть уникальных
  dependency-derived `supply_` codes текущего `resolve_snapshot_item()`),
  замороженной целиком в A9.2 v1 без prefix/wildcard matching и покрытой
  producer-shape tests для каждого текущего code. Unknown codes,
  dropped/missing keys и caller-invented shape invalid; `reasonCounts` содержит
  только те же known codes с positive exact-int counts;
- `summary.needsReview == sum(reasonCounts.values())`;
  `needsReviewTruncated == (summary.needsReview > 100)`, длина emitted reviews
  равна `min(summary.needsReview, 100)`; без truncation их exact histogram
  равен `reasonCounts`, при truncation каждый visible count не превышает total;
- для каждой producer pair длина emitted list exact-equal `min(count, 100)`:
  `openSupplyItems/openSupply`,
  `closedSupplyRequests/closedSupplyRequestIds`,
  `deliveries/deliveryIds`, `allocations/allocationIds`,
  `supplierInvoices/supplierInvoiceIds`,
  `warehouseInvoices/warehouseInvoiceIds`,
  `warehouseHistoryRows/warehouseHistoryIds`, `receiptLots/receiptLotIds`,
  `warehouseMovements/warehouseMovementIds` и
  `lotMovements/lotMovementIds`; `factsTruncated` exact-equal наличию хотя бы
  одного соответствующего count больше 100. Нельзя принять, например,
  `deliveries=101` с одним `deliveryId` как нормальную truncation;
- `complete` exact-equal conjunction
  `schemaReady && scanComplete && !factsTruncated && needsReview == 0`;
  `state=complete` iff `complete=true`; `state=incomplete` для schema/scan/fact
  incompleteness; `state=review_required` только для complete scan с reviews;
  `state=not_collected` допускается только как exact all-zero/empty canonical
  projection при non-ready source.

После этой raw validation нормализованный combined report также обязан пройти
strict A9.1 validation. Mutation любого ignored extra field, raw
state/complete, summary count, review/evidence shape или truncation relation
даёт `warehouse_anomaly_content_current_report_invalid`, даже если permissive
normalization могла бы восстановить совпадающий A9.1 view.

Cardinality bounded, но aggregate memory и wall-clock пока bounded недостаточно
жёстко для runtime:

- source-ready worst case существующего relevant collector — не более 14 A7
  `SELECT`, плюс один transaction-setting `SELECT`;
- per-row caps допускают до 100 request `items_json` по 1 MiB и до 100 invoice
  `items` по 1 MiB, плюс estimate snapshot до 4 MiB: inherited aggregate ceiling
  превышает примерно 204 MiB до Python/JSON overhead;
- каждый statement ограничен 60 секундами, но это per-statement timeout;
- последовательный worst case поэтому допускает примерно 14 минут до общего
  timeout, не считая pool acquisition;
- получение connection через `get_db()` и общий wall-clock этого
  незарегистрированного internal runner отдельным deadline пока не ограничены.

До любого runtime route A7/read path обязан получить query-level aggregate-byte
limit, а adapter — отдельные pool-acquisition и overall request deadlines (и
при необходимости меньший statement timeout). Текущий A9.2 не должен изображать
tight memory/latency SLO, которого нет.

### Output

Успешный `preview_ready` result имеет точную форму:

```json
{
  "warehouseAnomalyContentVersion": 1,
  "ok": true,
  "dryRun": true,
  "writesAttempted": 0,
  "previewOnly": true,
  "stockMovementAllowed": false,
  "inventoryAdjustmentAllowed": false,
  "applyAllowed": false,
  "state": "preview_ready",
  "source": {
    "companyId": 4,
    "projectId": 9,
    "estimateId": 80,
    "baseEstimateId": 30,
    "reconciliationId": 4,
    "reconciliationStatus": "Черновик",
    "sourceRevision": "sha256:<64 lowercase hex>",
    "revalidatedRelevantEvidenceSha256": "<64 lowercase hex>"
  },
  "candidate": {
    "subjectKind": "warehouseInvoice",
    "subjectId": 123,
    "anomalyCode": "warehouse_invoice_project_mismatch",
    "recommendationCode": "review_warehouse_invoice_lineage"
  },
  "content": {
    "title": "Проверить связь складской накладной",
    "finding": "Проект складской накладной не совпадает с текущей точной цепочкой источника.",
    "nextSafeAction": "Сверьте первичный документ и его точные связи. Не меняйте остаток автоматически."
  },
  "blockers": [],
  "contentSha256": "<64 lowercase hex>",
  "readOnlyTransaction": true,
  "rolledBack": true
}
```

Для `blocked` и `stale`:

- `content=null`, `contentSha256=null`;
- `candidate` остаётся только validated original candidate;
- `blockers=[]` только для `preview_ready`; для `blocked`/`stale` он содержит
  ровно один first-precedence A9.2 fixed code;
- business text и raw underlying report отсутствуют;
- `source` всегда содержит stored/selected seven-field source tuple. Current
  mismatched source values не выдаются; их отличие представлено только fixed
  drift code.
- `revalidatedRelevantEvidenceSha256` — единственный публичный evidence hash.
  Он равен совпавшему stored/current relevant hash только в `preview_ready` и
  равен `null` во всех `blocked`/`stale` results. Отдельные stored/current hashes
  остаются internal и не образуют current-state oracle. Malformed current
  wrapper/report не превращается в blocked result: result отсутствует и
  выбрасывается fixed exception.

Allowed result states и blockers:

| State | Условие | Blocker |
|---|---|---|
| `preview_ready` | exact current candidate найден один раз | нет |
| `blocked` | current A7 source не ready для domain scan | `warehouse_anomaly_current_source_not_ready` |
| `stale` | source-ready reconciliation ID/base/status отличаются при неизменных requested core fields | `warehouse_anomaly_source_drift` |
| `blocked` | current A9.1 strict result не допускает candidates | `warehouse_anomaly_current_snapshot_blocked` |
| `stale` | current A9.1 `clear` или candidate отсутствует/изменён | `warehouse_anomaly_candidate_stale` |
| `stale` | candidate сохранился, но stored/current relevant evidence hashes отличаются | `warehouse_anomaly_relevant_evidence_drift` |

Invalid stored report/selection/current report, read, rollback или cleanup — это
fixed-code `WarehouseAnomalyContentError`, а не частичный result:

- `warehouse_anomaly_content_input_invalid`;
- `warehouse_anomaly_content_selection_invalid`;
- `warehouse_anomaly_content_stored_readiness_blocked`;
- `warehouse_anomaly_content_current_report_invalid`;
- `warehouse_anomaly_content_contract_invalid`;
- `warehouse_anomaly_content_read_failed`;
- `warehouse_anomaly_content_rollback_failed`;
- `warehouse_anomaly_content_cleanup_failed`.

### Fixed human-readable allowlist

`finding` выводится только из exact anomaly code:

| Anomaly code | Fixed finding |
|---|---|
| `warehouse_invoice_request_mismatch` | Связь складской накладной с заявкой не совпадает с текущей точной цепочкой источника. |
| `warehouse_invoice_project_mismatch` | Проект складской накладной не совпадает с текущей точной цепочкой источника. |
| `warehouse_invoice_delivery_mismatch` | Связь складской накладной с поставкой не совпадает с текущей точной цепочкой источника. |
| `warehouse_invoice_supplier_invoice_mismatch` | Связь складской накладной с документом поставщика не совпадает с текущей точной цепочкой источника. |
| `warehouse_invoice_items_invalid` | Состав строк складской накладной не подтверждён текущим точным snapshot. |
| `warehouse_receipt_invoice_mismatch` | Приход склада не связан с ожидаемой накладной в текущем точном snapshot. |
| `warehouse_receipt_line_invalid` | Строка-источник складского прихода отсутствует или невалидна в текущем точном snapshot. |
| `warehouse_receipt_package_mismatch` | Пакет работ складского прихода не совпадает с текущей точной цепочкой источника. |
| `warehouse_receipt_lot_invoice_mismatch` | Партия прихода не связана с ожидаемой накладной в текущем точном snapshot. |
| `warehouse_receipt_lot_line_invalid` | Строка-источник партии прихода отсутствует или невалидна в текущем точном snapshot. |
| `warehouse_receipt_lot_project_mismatch` | Проект партии прихода не совпадает с текущей точной цепочкой источника. |
| `warehouse_movement_invoice_mismatch` | Движение склада не связано с ожидаемой накладной в текущем точном snapshot. |
| `warehouse_movement_line_invalid` | Строка-источник движения склада отсутствует или невалидна в текущем точном snapshot. |
| `warehouse_movement_package_mismatch` | Пакет работ движения склада не совпадает с текущей точной цепочкой источника. |
| `warehouse_movement_lot_missing` | Для движения склада не найдена ожидаемая связь с партией прихода. |
| `warehouse_lot_movement_missing` | Для связи партии не найдено ожидаемое складское движение. |
| `warehouse_lot_movement_parent_mismatch` | Родительская связь события партии не совпадает с текущим точным snapshot. |
| `warehouse_lot_movement_source_mismatch` | Источник события партии не совпадает с текущим точным snapshot. |

`title` и `nextSafeAction` выводятся только из seven existing A9.1
`recommendationCode` values:

| Recommendation code | Title | Next safe action |
|---|---|---|
| `review_warehouse_invoice_lineage` | Проверить связь складской накладной | Сверьте первичный документ и его точные связи. Не меняйте остаток автоматически. |
| `review_warehouse_invoice_items` | Проверить состав складской накладной | Сверьте строки первичного документа с источником. Не исправляйте количество автоматически. |
| `review_warehouse_receipt_lineage` | Проверить связь складского прихода | Сверьте приход с накладной, строкой и пакетом работ. Не создавайте корректирующее движение автоматически. |
| `review_receipt_lot_lineage` | Проверить связь партии прихода | Сверьте партию с накладной, строкой и проектом. Не меняйте доступное количество автоматически. |
| `review_warehouse_movement_lineage` | Проверить источник движения склада | Сверьте движение с накладной, строкой и пакетом работ. Не отменяйте и не повторяйте движение автоматически. |
| `review_warehouse_movement_traceability` | Проверить трассируемость движения склада | Сверьте движение и событие партии по первичным ID. Не восстанавливайте связь автоматически. |
| `review_lot_movement_lineage` | Проверить событие партии | Сверьте родительское движение и источник события партии. Не перепривязывайте событие автоматически. |

Любая отсутствующая mapping entry, невозможная output shape или canonical-hash
failure даёт `warehouse_anomaly_content_contract_invalid` без fallback text.
`contentSha256` — canonical SHA-256 над version, всем публичным `source`
(включая единственный revalidated relevant evidence hash), exact candidate и
fixed content; runner metadata в preimage не входит.

Relevant evidence hash имеет отдельную versioned preimage:

```json
{
  "warehouseAnomalyRelevantEvidenceVersion": 1,
  "source": {
    "companyId": 4,
    "projectId": 9,
    "estimateId": 80,
    "sourceRevision": "sha256:<64 lowercase hex>",
    "reconciliationId": 4,
    "baseEstimateId": 30,
    "reconciliationStatus": "Черновик"
  },
  "supply": "<entire strict normalized domains.supply mapping>",
  "warehouse": "<entire strict normalized domains.warehouse mapping>"
}
```

Canonical JSON использует UTF-8, sorted keys, compact separators и
`allow_nan=false`. Hash не является MAC/provenance. Stored hash считается только
после strict A9.1 validation; current — только из rebuilt relevant envelope.

## Code Style

- `content_preview.__all__` содержит ровно
  `{WAREHOUSE_ANOMALY_CONTENT_VERSION, WarehouseAnomalyContentError,
  run_warehouse_anomaly_content_preview}`; package-level `__init__.py` не
  меняется. Единственный public seam имеет verb-first имя; private helpers
  начинаются с `_` и не считаются стабильным composition API.
- Strict shape checks используют exact field sets и `type(value) is int`, чтобы
  `bool` не принимался как ID.
- Business uncertainty возвращается fixed state/blocker; malformed contract и
  infrastructure failure — fixed exception code.
- Input и dependency results deep-copy; caller mapping не мутируется.
- Private mappings immutable (`MappingProxyType`/tuples), сортировка canonical.

Пример ожидаемого fail-closed orchestration style:

```python
prepared = _prepare_warehouse_anomaly_content(combined_report, selected)
collected = _collect_current_warehouse_anomaly_evidence(cur, prepared)
# rollback happens before current readiness/content finalization
report = build_combined_report(
    collected["source"],
    assignment=None,
    material=None,
    supply_warehouse=collected["supplyWarehouseImpact"],
    economics=None,
)
current = build_warehouse_anomaly_readiness(completed_report(report))
candidate = exact_current_candidate(current, prepared.candidate)
return fixed_content_result(prepared, current, candidate)
```

`completed_report()` не вызывается и не делает report публичным до успешного
rollback. Реализация не должна буквально скрывать transaction lifecycle в
непроверяемой helper abstraction.

## Testing Strategy

### Contract RED/GREEN

- missing module/function first produces the expected RED import failure;
- all 18 exact A9.1 anomaly codes produce only their fixed finding and the
  seven exact recommendation/title/action mappings;
- selection rejects extra/missing fields, bool/zero/negative/string IDs,
  unknown/incompatible kind/code and caller-supplied recommendation;
- stored report malformed/blocked/oversized/hash-mismatched или
  report-internal inconsistent fails before `get_db()`; отдельно проверяется,
  что корректно перехэшированный mapping не считается доказанным provenance;
- input mappings remain byte-for-byte/deep equal after success and failure.

### Current revalidation

- exact current report and candidate → `preview_ready`;
- current `clear` или removed candidate → `stale`;
- source revision/baseline больше не ready → `blocked` с
  `warehouse_anomaly_current_source_not_ready` и null public revalidated hash;
- изменение любого из трёх reconciliation fields source-ready snapshot
  (`reconciliationId`, `baseEstimateId`, `reconciliationStatus`) → `stale` с
  `warehouse_anomaly_source_drift` даже при прежнем candidate;
- injected mismatch любого из четырёх requested core source fields, incoherent
  source/scan/schema flags, issue histogram/count или projection-ready flag →
  `warehouse_anomaly_content_current_report_invalid`, а не business result;
- raw projection mutation table покрывает extra field, state/complete drift,
  каждый summary/evidence count relation, malformed/unknown review shape,
  reason histogram, list ordering/duplicate/bounds и truncation coherence;
- current schema/scan/truncation/supply/duplicate/unknown blocker → `blocked`
  with no partial content;
- любой новый/исчезнувший relevant fact/review/candidate или другое изменение
  normalized supply/warehouse domain даёт relevant-evidence drift и no content;
- изменение unrelated assignment/material/economics domain не влияет на
  relevant evidence hash;
- source/reconciliation/revision/owner drift and invalid current A7 contract
  never emit content.

### Transaction and dependency boundary

- one connection, one caller-owned current relevant A7 collection, exact read-only
  `REPEATABLE READ`, safe local settings, zero commit, unconditional rollback;
- source-ready fake-cursor path не превышает 15 разрешённых SQL statements и
  не вызывает unrelated A7 collectors;
- rollback executes on success, normal exception and control-flow exception;
- rollback/read/cleanup precedence matches the fixed contract;
- content finalizer is not called before rollback succeeds;
- AST/static test rejects DB/network/filesystem writers, warehouse/inventory
  writer imports, routes, jobs, provider/model, notifications and outbox;
- `content_contract.py` exact import allowlist permits only stdlib, pure A7
  `estimate_revision_impact.contract`, combined-contract helpers and A9.1
  readiness; `content_preview.py` отдельно допускает `psycopg2`, relevant A7
  collector и private pure A9.2 contract;
  relative imports и любой package-level export regression проверяются явно;
- fake collector proves `writesAttempted=0`; related A7/A9 and full backend
  suites remain green.

## Boundaries

- **Always:** use a trusted server-owned A7 report; validate before connection;
  rebuild current relevant A7 evidence; require exact stored/current relevant
  hash and candidate match; rollback before content; fixed text only; bounded
  reads; zero writes; preserve A9.1.
- **Ask first:** move from approved PLAN/TASKS to IMPLEMENT; change any
  anomaly/recommendation/text mapping without bumping the relevant/content
  contract version; add/change A7 or A9.1 interfaces; add
  subject-specific SQL; expose API/CLI/job/UI; add auth/selected-company runtime;
  define whether project-mismatch subject IDs require company-wide warehouse
  authority or exact-project visibility; add business text; contact production;
  commit, push or deploy.
- **Never:** accept client report/source/evidence/recommendation; detailed
  all-companies mode; use name/fuzzy/implicit alias matching; emit raw report,
  SQL, notes, contacts, price or quantity; call provider/model; calculate or
  execute correction, movement, inventory adjustment, task, notification,
  outbox or any write-capable warehouse handler.

## Success Criteria

- Exact trusted stored source/relevant evidence/candidate plus exact current
  source/relevant evidence/candidate yields one stable `preview_ready` object
  whose fixed text and canonical hash are deterministic.
- Любой malformed, hash-mismatched или report-internal inconsistent stored/current
  mapping, report-internal owner/source mismatch,
  source-not-ready/drift, truncation, blocker,
  disappeared/changed candidate, rollback failure or unexpected dependency
  yields no human-readable content.
- Корректно заново канонизированный и перехэшированный mapping не объявляется
  обнаруженным «tamper»: его server-owned provenance и tenant authorization
  остаются обязанностью trusted caller/future runtime adapter.
- Current content is finalized only after one successful unconditional rollback;
  every path attempts zero business/schema/job/audit writes and no external call.
- Output contains only allowlisted IDs, hashes, codes, booleans and fixed text;
  it never claims the warehouse is clean or recommends a correction quantity.
- Focused A9.2, existing A9.1, full A7 and full backend suites pass; compilation,
  static forbidden-dependency scan and `git diff --check` pass.
- No runtime/API/UI/flag/schema/production behavior changes in A9.2.
- Runtime/API remains forbidden until inherited A7 reads have an aggregate-byte
  limit and the adapter has connection-acquisition plus overall deadlines.
- Before any future API, explicitly authorize the visibility of same-company
  candidate IDs in every ready/blocked/stale projection, особенно
  `*_project_mismatch`; exact company auth alone is not silently treated as
  exact project authorization.

## Open Questions

Нет незакрытых технических вопросов внутри этой узкой границы. Человеческое
подтверждение требуется для самого fail-closed решения: любое изменение
normalized current supply/warehouse evidence требует заново получить A9.1
selection; unrelated assignment/material/economics drift не блокирует A9.2.
