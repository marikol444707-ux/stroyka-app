# Spec: A9.3 — безопасная подготовка warehouse anomaly preview к runtime

## Статус

Утверждена человеком 2026-08-15 после plain-language clarification; approved
design body был независимо проверен на exact SHA-256
`ca88b5458d7c4194512ab3ecb1ec8ef55e879a192054b5e7331c3445e9a83449`.
Локально завершён A9.3a через PLAN/TASKS и TDD. Exact evidence записан в
`tasks/todo.md`: изолированный PostgreSQL proof прошёл `28/28`, full backend —
`2015/2015`, три fresh review не нашли Critical или Required замечаний. A9.3b
отдельно разрешён человеком 2026-08-15 и локально завершён через PLAN/TDD,
включая b4 isolated-PostgreSQL proof `29/29`, A7 `179/179` и full backend
`2087/2087`. Exact evidence записан в `tasks/todo.md`. A9.3c отдельно разрешён
человеком 2026-08-21 и локально завершён через четыре DB-free TDD checkpoint:
focused `20/20`, preview package `159/159`, A7 `179/179`, full backend
`2107/2107`, три final review axes без Critical/Required. A9.3d отдельно
разрешён человеком 2026-08-21 и локально завершён через четыре TDD-checkpoint:
isolated PostgreSQL `33/33`, focused runtime `115/115`, preview package
`182/182`, A7 `179/179`, full backend `2130/2130` и три final review axes без
Critical/Required. A9.3e отдельно разрешён человеком 2026-08-21 и локально
завершён через четыре TDD-checkpoint: focused runtime `125/125`, preview
package `192/192`, A7 `179/179`, full backend `2140/2140`; финальная проверка
не нашла Critical или Required замечаний. HTTP route, UI, feature flag, commit,
push, production contact и deployment по-прежнему не разрешены.

A9.1 и A9.2 остаются локальными и незарегистрированными. A9.3 закрывает
известные resource, provenance и authorization gaps небольшими проверяемыми
срезами, но сам по себе не публикует feature пользователям.

## Objective

A9.3 должен сделать существующий A9.2 preview пригодным для последующего
защищённого runtime adapter:

1. ограничить объём всех variable-width данных до передачи через libpq;
2. ограничить ожидание capacity/connection и длительность каждого SQL;
3. зафиксировать cookie/2FA/company-wide authorization и disclosure policy;
4. разрешать только exact succeeded system-owned A7 artifact из `agent_jobs`;
5. собрать auth, artifact и current A7 revalidation в одной read-only
   `REPEATABLE READ` transaction, не выдавая content до rollback/cleanup.

Первый полезный результат A9.3 — доказуемо bounded и всё ещё unregistered
server-side runtime. HTTP и UI являются отдельным последующим решением.

## Не входит в A9.3

- stock movement, inventory adjustment, correction quantity или apply;
- model/provider, recommendation generation, ranking или free-form text;
- client-supplied A7 report, evidence hash, source или recommendation code;
- `all_companies`, legacy/default company fallback или project-name access;
- project-scoped roles, пока нет independent subject-level owner resolver для
  каждого из 18 anomaly kinds;
- public GET route, URL с subject/job ID, cache/ETag, notification/outbox;
- persistent read-audit row; это отдельная write-policy decision;
- hard killable wall-clock guarantee. Текущий sync psycopg2 stack может дать
  только cooperative deadline плюс libpq/server timeouts;
- commit, push, production contact, deployment или server configuration.

## Зафиксированные предположения и безопасные defaults

1. Version-1 actor — только exact active membership role `директор`.
   `зам_директора` и остальные роли добавляются только отдельным approval.
2. Все 18 subject IDs считаются company-wide sensitive. Lineage anomaly может
   означать, что именно связь, доказывающая project ownership, сломана;
   поэтому нельзя ограничить риск только кодами `*_project_mismatch`.
3. Future transport — cookie session only. Bearer/mixed credentials запрещены;
   expensive preview требует POST + CSRF, но route не входит в этот spec.
4. Client передаёт только untrusted exact-positive claims: `companyId` header
   context, `projectId`, `jobId` и selection triple
   `{subjectKind, subjectId, anomalyCode}`. Report/source/hash/text не
   принимаются. Authoritative actor/company/project/source выводятся только из
   live DB membership/project row и server-owned job payload; claims обязаны
   exactly совпасть, но сами ничего не авторизуют.
5. Artifact — ровно одна immutable succeeded system-owned
   `estimate.revision_impact` job row. Поиск `latest` запрещён.
6. Существующие A7/A9.1/A9.2 reason/version surfaces не расширяются. Resource
   overflow использует уже существующие fail-closed reason codes.
7. Conservative byte defaults:
   - `MAX_JSON_QUERY_BYTES = 4_194_304` aggregate UTF-8 bytes для каждого из
     request-items и warehouse-invoice-items query;
   - существующие target/base estimate snapshots остаются максимум 4 MiB
     каждый;
   - `MAX_TEXT_FIELD_BYTES = 1_024` UTF-8 bytes для любого другого выбранного
     variable-width DB field;
   - `MAX_TEXT_QUERY_AGGREGATE_BYTES = 1_048_576` для суммы таких fields в
     каждом payload-bearing query;
   - `MAX_NUMERIC_FIELD_BYTES = 64` для SQL text representation выбранных
     `received_quantity` и `allocation_quantity`; эти bytes входят в тот же
     query/cumulative budget;
   - `MAX_COLLECTOR_VARIABLE_BYTES = 17_825_792` (17 MiB) для всего relevant
     collector pass, включая JSON и non-JSON text;
   - system-owned job `payload_json` и `result_json` после canonical
     reserialization остаются максимум 65,536 UTF-8 bytes каждый, как в
     существующем agent-job serializer; SQL transport additionally rejects
     `jsonb::text` больше 131,072 bytes, учитывая whitespace canonicalization
     PostgreSQL без ослабления logical 64 KiB contract.
8. При текущих row caps и independent cumulative gate это ограничивает
   variable-width result payload одного полного A7 relevant pass максимумом
   17,825,792 bytes до driver/Python object overhead. Четыре JSON/snapshot
   categories имеют собственные 4 MiB caps, каждый text-bearing query — 1 MiB,
   но их совместный accepted payload всё равно не может превысить 17 MiB.
   Поэтому cumulative cap не является суммой/redundant alias per-query caps:
   после четырёх полностью заполненных JSON categories на все остальные fields
   остаётся только 1 MiB.
   Это не обещание точного RSS; fixed-width IDs/booleans и Python containers
   ограничены отдельно существующими row/node caps.
   Whole unregistered runtime additionally reads at most 2×128 KiB guarded job
   JSON transport plus schema-bounded job-plan `VARCHAR` fields; live auth
   projects only fixed-width IDs/booleans. Это finite small addition, но всё
   равно не RSS claim.
9. Conservative time/capacity defaults:
   - per-process capacity `1`, ожидание slot не более `1s`;
   - libpq `connect_timeout=5s`;
   - PostgreSQL `statement_timeout=5s`, `lock_timeout=1s`,
     `idle_in_transaction_session_timeout=10s`;
   - cooperative operation budget `30s`: начинается после получения slot и до
     `connect()`, включает connect/auth/artifact/collection/finalization;
     начатый перед границей SQL может дать не более одного дополнительного
     server statement timeout; runner также проверяет clock после каждой
     bounded pure phase, перед finalization и перед return, а cleanup остаётся
     best-effort. Уже начатая pure phase и established libpq/network wait не
     имеют доказанной wall-clock границы, поэтому весь runtime не называется
     hard deadline.
10. Runtime остаётся незарегистрированным даже после всех A9.3 slices. Route
    требует отдельного HTTP/ops spec с cross-process rate/concurrency limit.

Эти limits разрешено только повысить после отдельного evidence-backed review.

## Threat model (STRIDE)

| Threat | Abuse case | Обязательный control |
|---|---|---|
| Spoofing | Поддельные company/project/job selectors, bearer downgrade, revoked session | Cookie-only authentication; live session, 2FA, membership, company/account и project проверяются в DB |
| Tampering | Client присылает report/hash/recommendation либо выбирает foreign job | Client supplies selectors only; exact system-owned artifact и current A7 contracts валидируются server-side |
| Repudiation | Дорогой read нельзя связать с actor | Structured redacted operational metric допустим позже; persistent audit write требует отдельного approval |
| Information disclosure | Foreign job/candidate oracle, broken-lineage subject ID, evidence hashes | Authorize before artifact lookup; director-only; uniform not-found; minimal public projection; hashes наружу не выходят |
| Denial of service | Unbounded TEXT, 204+ MiB JSON, 14×60s SQL, direct connect storm | SQL projection gates, field/aggregate byte caps, 5s statements, bounded connect, semaphore, later route limit |
| Elevation of privilege | Global role или project name ошибочно дают warehouse visibility | Только live company membership role; exact project ID; никаких project-scoped actors |

Trust boundary: unkeyed SHA-256 доказывает canonical integrity, но не
provenance/auth. Provenance создаётся только exact server-owned job lookup после
live DB authorization.

## Tech Stack

- Python stdlib (`hashlib/json`, `threading`, `time`, `typing.NamedTuple`) для pure
  contracts, capacity и cooperative deadline;
- существующий `psycopg2`/`RealDictCursor`, без нового ORM/async driver;
- PostgreSQL read-only `REPEATABLE READ`, parameterized SQL и transaction-local
  settings;
- существующие A7 `collect_supply_warehouse_impact_audit()`, A9.1 readiness и
  A9.2 pure content contract;
- `unittest`; disposable PostgreSQL только для approved A7 resource gates,
  explicit transaction lifecycle и runtime-access auth/artifact SQL proofs.

Новая внешняя dependency не допускается.

## Project Structure

Предлагаемый split; точные имена можно изменить только без расширения
dependency/public surface:

```text
backend/features/estimate_revision_impact/
  baseline.py                       # bounded target/reconciliation queries
  supply_warehouse_audit.py         # bounded relevant A7 queries
  resource_limits.py                # private constants + exact mutable budget
  test_resource_limits.py           # fake-cursor + disposable-PG proofs

backend/features/warehouse_recommendation_preview/
  readiness.py                      # existing A9.1; public contract unchanged
  content_contract.py               # existing A9.2 pure strict contract
  content_preview.py                # existing A9.2 internal runner
  runtime_budget.py                 # capacity/connect/cooperative budget only
  runtime_contract.py               # pure auth/selectors/public projection
  runtime_access.py                 # caller-cursor live auth + artifact reads
  runtime_preview.py                # one unregistered same-snapshot runner
  test_runtime_budget.py
  test_runtime_contract.py
  test_runtime_access.py
  test_runtime_preview.py

docs/
  warehouse-anomaly-runtime-readiness.md
```

`routes.py`, `backend/main.py`, package `__init__.py`, frontend, nginx,
systemd, schema/migrations, writers and agent worker registration не меняются.

## A9.3a — bounded A7 data substrate

### Exact variable-width inventory

До передачи через libpq должны быть ограничены все следующие значения:

| Query | Variable-width columns |
|---|---|
| target estimate | `version`, `sections_json`, `status`, `smeta_type`, `work_package` |
| reconciliation | reconciliation/base/next `status`, `smeta_type`, `work_package` |
| source context | project `name`, base `work_package`, base `sections_json` |
| supply requests | `project`, `work_package`, `status`, `items_json` |
| deliveries | `project`, `work_package`, `material_name`, `unit`, text representation `received_quantity` |
| allocations | text representation `allocation_quantity` |
| warehouse invoices | `project`, `items` |
| warehouse history | `work_package` |
| warehouse movements | `work_package` |

Catalog identifiers from the fixed schema probes are bounded PostgreSQL names;
integer/boolean IDs and counters stay under existing fixed-width types. Decimal
quantities не считаются fixed metadata: их SQL text representation имеет exact
64-byte field gate и входит в aggregate/cumulative accounting.

### SQL projection contract

Каждый payload-bearing query сначала выбирает existing ordered `LIMIT` set,
считает byte lengths на стороне PostgreSQL и только затем проецирует values.
Принципиальная форма:

```sql
SELECT bounded.id,bounded.items_json,
       bounded.cardinality_limit_exceeded,
       bounded.payload_limit_exceeded,
       bounded.field_json_bytes,bounded.query_json_bytes,
       bounded.query_variable_bytes
  FROM (
    WITH limited AS MATERIALIZED (
        SELECT id,items_json AS raw_items_json,
               COALESCE(items_json,'') AS emitted_items_json
          FROM public.supply_requests
         WHERE company_id=%s AND project=%s
         ORDER BY id
         LIMIT %s
    ), sized AS MATERIALIZED (
        SELECT limited.*,
               octet_length(convert_to(emitted_items_json,'UTF8'))
                   AS item_bytes,
               MAX(octet_length(convert_to(
                   emitted_items_json,'UTF8'
               ))) OVER () AS max_item_bytes,
               SUM(octet_length(convert_to(
                   emitted_items_json,'UTF8'
               ))) OVER () AS total_bytes,
               COUNT(*) OVER () AS row_count
          FROM limited
    ), gated AS MATERIALIZED (
        SELECT sized.*,
               (max_item_bytes<=%s AND total_bytes<=%s AND total_bytes<=%s)
                   AS bytes_allowed,
               (row_count<=%s AND max_item_bytes<=%s
                AND total_bytes<=%s AND total_bytes<=%s) AS payload_allowed
          FROM sized
    )
    SELECT gated.id,
           CASE WHEN gated.payload_allowed THEN gated.raw_items_json
                ELSE NULL END AS items_json,
           (gated.row_count>%s) AS cardinality_limit_exceeded,
           (gated.row_count<=%s AND NOT gated.bytes_allowed)
               AS payload_limit_exceeded,
           gated.item_bytes AS field_json_bytes,
           gated.total_bytes AS query_json_bytes,
           gated.total_bytes AS query_variable_bytes
      FROM gated
  ) AS bounded
 ORDER BY bounded.id
```

Production SQL сохраняет все существующие predicates/order/columns. Пример
показывает только safety shape. Window aggregate вычисляется только после
отдельного materialized ordered-LIMIT CTE; один и тот же MVCC statement snapshot
связывает carried raw value, его exact emitted expression, byte metadata и final
CASE без повторного join. Schema probe не доказывает PK/unique constraints,
поэтому ID-only limited set с последующим rejoin запрещён. Top-level query
остаётся reviewed `SELECT` с explicit outer columns/order, чтобы не расширять
существующий read-only/static contract.

Обязательные свойства:

- bytes считаются через
  `octet_length(convert_to(<exact emitted text expression>,'UTF8'))`, не Python
  `len` и не implicit database encoding;
- cap inclusive: ровно limit проходит, `limit+1` fail closed;
- ordered cardinality sentinel проверяется первым; при `limit+1` все raw
  variable fields CASE-null и через libpq проходят только small metadata/flags;
- только действительно emitted SQL `NULL` считается нулём; отдельный overflow
  flag не даёт принять CASE-nulled oversized value как обычный database NULL;
- размер считается по exact emitted SQL expression после всех
  `COALESCE/NULLIF` fallbacks. Поэтому raw NULL, превращённый в `Основная` или
  `Черновик`, потребляет UTF-8 bytes fallback; ноль допустим только для
  действительно emitted SQL NULL;
- original oversized value не входит в result tuple и не пересекает libpq;
- `MAX/BOOL_AND` формирует один query-wide allow decision: если хотя бы одна
  limited row превышает field cap, CASE-null применён ко всем variable fields
  всех строк; mixed small+oversized query не пропускает small raw payload;
- JSON сохраняет существующий 1 MiB per-row cap плюс новый 4 MiB aggregate cap;
- non-JSON text имеет 1 KiB per-field и 1 MiB per-query aggregate caps; при
  overflow возвращаются только IDs/fixed metadata/flag;
- selected NUMERIC values проецируются только через `CASE` после проверки
  `octet_length(convert_to(value::text,'UTF8'))<=64`; raw arbitrary-precision
  value не выходит;
- remaining cumulative collector budget передаётся parameterized в каждый
  payload-bearing query; один private budget object проходит через baseline,
  context и все loaders, а payload проецируется только если весь query
  помещается и в fixed query caps, и в remaining 17 MiB budget;
- query возвращает bounded exact `query_json_bytes`, `query_text_bytes` и
  `query_variable_bytes`; Python требует non-bool non-negative integers,
  одинаковые aggregate values на всех строках, exact arithmetic и затем один
  раз списывает bytes из private accumulator. Per-row `field_*_bytes` отдельно
  сверяются с соответствующим CASE/flag. Metadata удаляется до передачи rows в
  A7 projection и никогда не входит в public report/hash;
- collection прекращается до JSON parse, sorting downstream IDs или следующих
  dependent queries, когда это возможно;
- query count не увеличивается.

Public A7 signatures остаются byte-for-byte compatible. Новый private core
принимает `_VariableByteBudget` с `remaining_bytes` и exact `consume(count)`:
standalone `collect_baseline_audit()` создаёт свой budget, а
`collect_supply_warehouse_impact_audit()` создаёт один shared budget и вызывает
private baseline core + все relevant loaders с ним. Budget/report metadata не
передаются в public A7 contract. Любая попытка изменить public function
signature или report fields требует reopening spec.

### Existing fail-closed mapping

Новых A7 reason codes нет:

| Overflow location | Existing outcome |
|---|---|
| target estimate source payload | `impact_estimate_snapshot_too_large` |
| reconciliation status/smeta/package field | соответствующий existing `impact_reconciliation_*_invalid/not_customer/package_mismatch/next_not_active` |
| reconciliation aggregate/row-set limit | `impact_reconciliation_scan_limit_exceeded` только с уже допустимой producer summary shape |
| source context | `supply_warehouse_scan_limit_exceeded` |
| requests text/JSON aggregate | `supply_request_scan_limit_exceeded` |
| deliveries, включая `received_quantity` | `supply_warehouse_scan_limit_exceeded` |
| allocations, включая `allocation_quantity` | `supply_warehouse_scan_limit_exceeded` |
| invoices/history/movements text/JSON aggregate | `supply_warehouse_scan_limit_exceeded` |

При одновременных дефектах порядок фиксирован: cardinality sentinel, затем
проверяемые без raw payload ID/owner invariants, затем exact overflow-location
mapping из таблицы, и только для принятого payload — прежние semantic checks.
Query-wide CASE намеренно скрывает остальные variable values, поэтому runtime
не пытается угадывать их старый multi-defect порядок по `NULL`. Например,
oversized reconciliation status остаётся `impact_reconciliation_status_invalid`
даже при `next_is_template=true`: скрытые smeta/package values могли содержать
более ранний дефект, а добавлять новые semantic sentinels в этот hardening slice
не разрешено.

Если exact producer shape нельзя сохранить без лжи в count/summary, задача
останавливается: новый reason/version нельзя добавлять под видом hardening.

### A9.3a acceptance

- каждый перечисленный field покрыт SQL-side cap и overflow branch;
- 100 individually sub-limit JSON rows с aggregate `limit+1` не передают raw
  payload в Python и возвращают existing incomplete blocker;
- huge `TEXT` при малом row count также не пересекает driver;
- boundary `limit`, `limit+1`, multibyte UTF-8 и `NULL` проверены;
- selected NUMERIC text boundary 64/65 bytes проверена отдельно для delivery и
  allocation и даёт exact existing systemic blocker;
- overflow short-circuits later dependent reads;
- A7/A9.1/A9.2 producer-parity suites остаются зелёными без reason/version drift;
- disposable PostgreSQL proof обязателен, потому что fake cursor не доказывает
  `convert_to(...,'UTF8')`, window aggregate и query-wide CASE projection
  behavior.

## A9.3b — capacity, connection и cooperative deadline

Нельзя оборачивать текущий blocking `get_db()` в abandoned thread timeout.
Нужен отдельный A9-only connection factory, который вызывает libpq сразу с
`connect_timeout=5`; глобальный `backend.db.get_db()` и остальной runtime не
меняются.

Предлагаемый private interface:

```python
class WarehouseAnomalyRuntimeBudget(NamedTuple):
    deadline_monotonic: float
    statement_timeout_ms: int

def acquire_warehouse_anomaly_runtime_slot(
    clock=time.monotonic, *, wait_seconds=1.0
):
    """Return one private lease that owns this clock and immutable budget."""

def open_warehouse_anomaly_read_connection(
    db_config, lease, *, connect=psycopg2.connect
):
    """Accept only that genuine lease; never mutate global DB_CONFIG."""
```

Rules:

- one `threading.BoundedSemaphore(1)` per backend process;
- slot acquired before `connect()` and held through rollback/close/finalize;
- the one-use lease owns the exact injected monotonic clock and immutable
  budget; later phases accept that lease rather than a caller-forgeable bare
  budget, and only the connector is injectable at the connection seam;
- the successful connection factory binds the exact returned connection
  identity to that genuine lease. The transaction seam accepts that exact pair
  once, never a swapped connection/lease pair, and clears the binding only
  after connection cleanup;
- operation deadline создаётся сразу после slot acquisition; slot wait имеет
  отдельный 1s cap;
- monotonic guard выполняется как соседняя cooperative проверка до blocking
  `connect()` и сразу после его возврата/ошибки. Если budget уже истёк в момент
  pre-check, libpq не вызывается. Между Python pre-check и входом в libpq
  остаётся неизбежное scheduler/bytecode окно: это не атомарная и не hard-wall
  граница. Поэтому post-connect expiry обязательно закрывает и отбрасывает
  поздно возвращённый connection, освобождает lease и не начинает BEGIN;
- a failed connect always releases the lease;
- dedicated libpq connection получает protective startup `options` с 5s
  statement timeout, остальными fixed timeouts и `client_encoding=UTF8` до
  первого SQL. Settings query затем подтверждает exact client encoding и
  повторно фиксирует transaction-local limits/search path;
- connection начинает в autocommit mode только для одного guarded exact
  `BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`; это отдельный
  первый server statement. Нельзя полагаться на неявный psycopg2 `BEGIN`,
  который мог бы выполниться внутри первого `execute` без отдельной clock
  boundary. После explicit `BEGIN` разрешены только reviewed SELECTs, а
  cleanup делает ровно одну best-effort rollback attempt iff explicit BEGIN
  was attempted (the flag is set before driver `execute`); post-connect expiry
  closes the connection without cursor/BEGIN/rollback. Disposable-PG test
  доказывает возврат backend transaction status в idle;
- connection/session/cursor/rollback/close follow A9.2 control-flow precedence;
- transaction uses `statement_timeout=5s`, `lock_timeout=1s`,
  `idle_in_transaction_session_timeout=10s`, fixed search path;
- private cursor guard exposes only `execute`, `fetchall` and cleanup `close`,
  checks the same monotonic deadline immediately before every `execute`
  (включая explicit `BEGIN` и все 14 internal A7 SELECTs) и после каждого
  `execute/fetchall`; no new statement starts after budget exhaustion;
- runner-level guard дополнительно проверяет deadline после live-auth
  validation, artifact validation/preparation и raw-current validation; после
  rollback и обоих close перед finalizer; после finalizer/public-result
  validation перед return. Expired result/content отбрасывается, fixed deadline
  error не включает private values; started pure phase остаётся cooperative;
- every returned collection remains row/byte bounded, so post-SQL CPU loops
  cannot grow with untrusted database cardinality;
- result distinguishes fixed `busy`, `deadline`, `read`, `rollback`, `cleanup`
  classes without dependency text.

Это cooperative overall deadline: один already-running psycopg2 call может
закончиться только по server/libpq timeout и дать до 5s overshoot, а Python
rollback/close нельзя безопасно kill. Route/ops documentation не должно
называть его hard wall-clock SLO.

После slot acquisition до cleanup выполняется максимум 18 server statements:
один explicit `BEGIN` и 17 SELECTs. При работающей доставке server timeout
`min(18 * 5s, 30s + 5s) = 35s` ограничивает только cumulative active
server-SQL exposure/SQL completion window. Это не upper bound всего
pre-cleanup elapsed time: уже начатая bounded pure phase, established
libpq/network wait и best-effort rollback/close не имеют отдельного killable
wall timeout. Bounded connect входит в тот же 30s cooperative budget, имеет
libpq `connect_timeout=5s` и проверяется clock до/после вызова; формула не
является HTTP response SLO.

Statement 19 is rejected before the driver call with the fixed private
`warehouse_anomaly_runtime_contract_invalid` code and then follows the normal
rollback/close cleanup path. This ceiling is enforced by the closed reviewed
call graph; a SQL prefix check is not treated as a parser or sandbox because a
`SELECT`/`WITH` form can still invoke writing or advisory operations.

During A9.3b the callback-owned transaction primitive remains private,
unexported, unregistered and has zero production call sites. A9.3b proves the
exact BEGIN/settings statements, guarded primitive and absence of raw-cursor
delegation. The full SELECT-only 18-statement production call-graph inventory
is closed only in A9.3e when the sole composition callback exists; A9.3b does
not make the false claim that a generic callback or SQL-prefix check is a
writer sandbox.

### A9.3b acceptance

- fake clock and connection tests cover slot wait, expiry at the cooperative
  pre-check and after connect, connect timeout, budget exhaustion immediately around
  every SQL/`fetchall` and release on every failure/control path;
- no thread/executor timeout and no orphan query/connection;
- static test proves global `DB_CONFIG/get_db()` unchanged;
- current internal A9.2 path remains unregistered;
- exact server-statement count/exposure is documented without claiming an
  exact pre-cleanup wall time from a cooperative or HTTP timeout.

## A9.3c — pure authorization and disclosure policy

Этот slice не открывает DB и не регистрирует route. Он фиксирует small immutable
selectors/auth/public projection contract.

Authentication envelope имеет ровно два поля:

```json
{
  "authenticationKind": "cookie_session",
  "sessionHash": "<64 lowercase hex>"
}
```

Extra/missing keys, subclasses, non-string kind/hash, uppercase/non-hex или
другая длина rejected до DB. Единственный допустимый producer этого envelope —
существующий DB-free `build_cookie_session_authentication()` с forbidden
Authorization и future POST `require_csrf=true`; runtime не принимает raw
cookie/session token/hash непосредственно от client/caller.

Future request shape:

```json
{
  "projectId": 9,
  "jobId": 123,
  "selected": {
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "anomalyCode": "warehouse_invoice_project_mismatch"
  }
}
```

Company берётся только из exact `X-Company-Mode=company` + positive
`X-Company-Id`. Body extra/missing fields, bool-as-int, names, source, hash,
report, recommendation или content запрещены.

Exact request/selection types и allowlisted kind/code compatibility проверяются
до slot/connection. Совпадение с artifact candidate проверяется только после
live authorization; well-formed, но absent/foreign selection становится тем же
opaque resource-not-found, а не candidate oracle.

Live DB auth policy для будущего runner:

- authentication kind exactly `cookie_session`; Authorization header absent;
- session hash valid, unrevoked, unexpired, `two_factor_passed=true`;
- user active и `two_factor_enabled=true`;
- exact active `user_company_roles` membership for selected company with
  `role='директор'`;
- company and platform account active;
- membership/company `platform_account_id` совпадают exactly и account status
  равен `active`; legacy NULL binding fail closed;
- exact project row belongs to selected company;
- auth SELECT использует actor `MATERIALIZED` CTE с `LIMIT 2`, считает exact
  actor rows и всегда возвращает одну small result row. Только когда
  `actor_count=1`, отдельный `EXISTS`/LEFT-joined flag проверяет exact project
  ID+company; project row не является INNER JOIN условием actor CTE;
- validator сначала требует `actor_count=1`: zero/two actor rows дают
  authentication-required. Только затем false `project_exists` даёт opaque
  resource-not-found. Поэтому invalid session/member не схлопывается с
  absent/foreign project, хотя всё остаётся одним parameterized SELECT;
- ambiguous membership fail closed, а legacy NULL account binding не
  нормализуется;
- no platform/account overview role, no global `users.role`, no project-name
  membership fallback.

Любой live cookie/session/2FA/user/membership/role/company/account failure имеет
один internal `warehouse_anomaly_runtime_authentication_required`; роль и
существование membership не раскрываются. Exact authorized actor получает один
и тот же resource-not-found для absent/foreign project, job или candidate.

Public projection removes both evidence/content hashes, seven-field source
internals, reconciliation IDs/status and raw blocker details. It may contain
only safety flags, state, original fixed candidate, fixed content or one
allowlisted public state code. Current/mismatched source values never выходят.

Exact detached shape:

```json
{
  "warehouseAnomalyRuntimeVersion": 1,
  "ok": true,
  "dryRun": true,
  "writesAttempted": 0,
  "previewOnly": true,
  "stockMovementAllowed": false,
  "inventoryAdjustmentAllowed": false,
  "applyAllowed": false,
  "state": "preview_ready",
  "candidate": {
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "anomalyCode": "warehouse_invoice_project_mismatch",
    "recommendationCode": "review_warehouse_invoice_lineage"
  },
  "content": {
    "title": "Проверить связь складской накладной",
    "finding": "Проект складской накладной не совпадает с текущей точной цепочкой источника.",
    "nextSafeAction": "Сверьте первичный документ и его точные связи. Не меняйте остаток автоматически."
  },
  "blockers": [],
  "readOnlyTransaction": true,
  "rolledBack": true
}
```

Для `blocked`/`stale` `content=null`; blockers содержит ровно
`warehouse_anomaly_preview_blocked` либо `warehouse_anomaly_preview_stale`.
Internal A9.2 blocker/evidence/content hashes, source, job/project IDs и current
values не копируются. `preview_ready` имеет `blockers=[]`.

All 18 candidates share the same policy. A future project-scoped version needs
an independent exact owner query for every subjectKind/code and must fail closed
on missing/ambiguous owner; redaction after running is insufficient.

## A9.3d — exact server-owned artifact resolver

Resolver принимает validated untrusted `companyId/projectId/jobId` claims,
работает на том же caller-owned read-only cursor и выполняет один parameterized
query. Контракт намеренно разделён на opaque lookup и post-read validation.

Opaque `WHERE` predicates:

- exact `agent_jobs.id`, `company_id`, `project_id`;
- `owner_scope='company'`;
- `job_type='estimate.revision_impact'`;
- `status='succeeded'`;
- `requested_by_user_id IS NULL` и `requested_by_role='system'`;
- `LIMIT 2`, хотя `id` unique, чтобы validator не зависел от schema assumption.

Missing/foreign/wrong-type/wrong-status/human-owned row поэтому даёт один
`resource_not_found`. Остальные lifecycle/integrity predicates нельзя помещать
в `WHERE`, иначе corrupted exact artifact будет замаскирован под 404.

SELECT возвращает все bounded plan/terminal fields плюс:

- `payload_json` и `result_json` только через
  `CASE WHEN octet_length(convert_to(value::text,'UTF8'))<=131_072 THEN value
  ELSE NULL END`;
- отдельные small `payload_limit_exceeded`/`result_limit_exceeded` flags;
- raw oversized JSON никогда не пересекает libpq, но exact row остаётся видимой
  и классифицируется `artifact_invalid`;
- post-read exact checks требуют `project_scope_id=project_id`, `priority=4`,
  `max_attempts=3`, `1<=attempts<=max_attempts`, `completed_at IS NOT NULL`,
  `started_at IS NOT NULL`, projected `last_error_empty IS TRUE`, projected
  terminal-null flags for
  `locked_at/locked_by/lease_token/lease_expires_at/heartbeat_at` и повторно
  сверяют все lookup identities;
- unbounded `last_error` и lease/lock text не выбираются raw: SQL возвращает
  только small exact booleans для empty/NULL terminal predicates, а validator
  проверяет flags post-read;
- existing safe serializer/validator повторно требует canonical JSON
  `<=65_536`, exact field/type contract и не доверяет CASE flags без проверки.

После чтения resolver обязан:

1. восстановить source только через `source_from_job_payload()`;
2. перестроить exact job plan и сверить весь plan: owner/project, job type,
   idempotency, correlation, requested owner, priority и max attempts;
3. проверить result через `validate_estimate_revision_impact_result()`;
4. проверить report source against job payload/row;
5. отдать detached mapping только внутреннему A9.2 preparation.

Нельзя использовать public `agent_jobs` query service: он намеренно не выдаёт
`result_json`. Нельзя искать latest, принимать result от клиента или возвращать
private artifact наружу.

После успешной auth missing/foreign/wrong-type/wrong-status job имеют один
oracle-resistant `not_found` outcome. Exact найденный, но corrupted internal
artifact даёт fixed server contract failure, не content и не 404 disguise.

## A9.3e — unregistered same-snapshot runtime composition

Один private runner выполняет в одной connection/transaction:

```text
capacity lease
  -> bounded connect
  -> read-only REPEATABLE READ + fixed settings
  -> live cookie/session/2FA/company/director/project auth
  -> exact succeeded system-owned job artifact
  -> strict stored A9.2 preparation
  -> current bounded A7 relevant collection
  -> exact raw/current validation
  -> unconditional rollback
  -> cursor.close + connection.close
  -> pure A9.2 finalization
  -> minimal detached public projection
  -> release capacity lease
```

Auth, artifact и current facts никогда не смешиваются из разных connections.
Существующий `run_warehouse_anomaly_content_preview()` не вызывается как nested
transaction. A9.2 private helpers также не превращаются случайно в public API:
нужен явно утверждённый private composition module и static import gate.

Content/final projection не выполняются до успешных rollback и обоих close.
Контроль ошибок сохраняет A9.2 precedence; control-flow re-raised by identity
после best-effort cleanup. Zero `commit`, DDL/DML, `FOR UPDATE`, advisory locks,
session last-seen write, audit write, cache или side effect.

Private fixed error surface:

- `warehouse_anomaly_runtime_input_invalid`;
- `warehouse_anomaly_runtime_busy`;
- `warehouse_anomaly_runtime_deadline_exceeded`;
- `warehouse_anomaly_runtime_authentication_required`;
- `warehouse_anomaly_runtime_resource_not_found`;
- `warehouse_anomaly_runtime_artifact_invalid`;
- `warehouse_anomaly_runtime_read_failed`;
- `warehouse_anomaly_runtime_rollback_failed`;
- `warehouse_anomaly_runtime_cleanup_failed`;
- `warehouse_anomaly_runtime_contract_invalid`.

Dependency text/cause не выходит. Priority: first named control-flow identity →
rollback failure → ordinary primary read/dependency или pre-cleanup deadline →
cleanup failure → deadline, впервые замеченный post-cleanup/post-finalizer →
artifact/auth/resource business outcome. Pre-connection input/busy errors не
открывают DB; deadline after acquisition still attempts rollback/cleanup.

Maximum SQL surface после composition:

- 1 explicit guarded `BEGIN ... REPEATABLE READ READ ONLY`;
- 1 transaction-settings SELECT;
- 1 live auth/project SELECT;
- 1 exact artifact SELECT;
- максимум 14 existing A7 relevant SELECTs;
- итого 18 server statements: exact constant BEGIN + максимум 17
  parameterized SELECTs; collector exactly once.

## Future HTTP/ops gate — явно вне A9.3

Только после локального закрытия A9.3 отдельная спецификация может предложить:

- POST-only route с CSRF; candidate/job IDs не в URL;
- feature flag default-off и company allowlist;
- `Cache-Control: no-store`, no ETag;
- dedicated nginx `limit_req`/`limit_conn` zone и backend capacity metrics;
- uniform public 401/403/404/409/429/503 mapping without private codes;
- explicit user flow для выбора exact succeeded job/candidate;
- browser/tenant/role/rate/load tests и production rollout/rollback plan.

До этого ни route, ни UI не регистрируются.

## Testing Strategy

### TDD order

Для каждого slice сначала observed RED, затем минимальный GREEN, related/full
regression и fresh-context correctness/security review.

1. A9.3a: query/byte boundary tests + disposable PostgreSQL proof.
2. A9.3b: fake clock/semaphore/connect/lifecycle matrix + тот же disposable
   PostgreSQL proof для guarded explicit BEGIN, single rollback и backend idle.
3. A9.3c: pure selector/auth/disclosure truth table.
4. A9.3d: exact job row/size/provenance/oracle matrix + тот же disposable
   PostgreSQL proof для actor/project CTE и artifact CASE/sentinel projection.
5. A9.3e: one-snapshot lifecycle, collision/control-flow and SQL-count tests.

### Required adversarial cases

- 100 rows individually below 1 MiB but aggregate `4 MiB + 1`;
- mixed small+one oversized row делает query-wide decision false и CASE-null
  для всех raw variable fields, включая small row;
- `row_limit+1` одновременно с byte overflow даёт cardinality blocker, null raw
  payload и не запускает downstream query;
- 1 KiB and 1 KiB+1 UTF-8 text, including multibyte values;
- SQL NULL/empty inputs, которые exact emitted expression превращает в
  `Основная`/`Черновик`, учитывают bytes fallback; emitted NULL остаётся zero;
- startup и settings подтверждают `client_encoding=UTF8`, а byte metadata
  совпадает с exact UTF-8 result bytes;
- selected delivery/allocation NUMERIC text проходит на 64 bytes и fail-closed
  на 65 bytes;
- 1 MiB and 1 MiB+1 aggregate non-JSON text plus 17 MiB and 17 MiB+1
  cumulative collector payload. При текущих cap 100 rows × 1 KiB per field
  1 MiB text-query boundary недостижим в production query (maximum меньше);
  его inclusive arithmetic проверяется pure helper test, а real SQL доказывает
  более строгие field/current-query maxima. Row/field caps не ослабляются ради
  искусственного end-to-end case;
- DB field changed to huge TEXT after query planning;
- oversized payload produces only small sentinel and no downstream query;
- capacity exhaustion, connect hang bounded by libpq, statement timeout,
  monotonic deadline expiration and every rollback/close collision;
- explicit guarded BEGIN является первым server statement; test запрещает
  implicit-BEGIN path, фиксирует 18-command ceiling и проверяет deadline сразу
  до/после каждого execute/fetch, после pure validation, перед finalizer и
  перед return;
- bearer/mixed auth, stale/revoked/non-2FA session, inactive user/member/company,
  deputy/project role, all-companies, foreign project;
- missing/foreign/wrong-status/human-owned/latest job attempts;
- oversized/corrupted/rehashed job result and selection mismatch;
- huge `agent_jobs.last_error` никогда не выбирается raw: наружу из SQL идёт
  только boolean terminal sentinel, exact row становится artifact-invalid;
- actor/session failure и valid actor+foreign project различаются внутренне
  одним actor-CTE SELECT, но не создают external project/membership oracle;
- all 18 candidate kinds under the same director-only disclosure policy;
- finalizer cannot see content before rollback/cleanup and cannot return hashes
  in public projection;
- input/result detachment and zero caller mutation.

### Commands после approval/implementation

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a93-pycache \
python3 -m unittest \
  backend.features.estimate_revision_impact.test_resource_limits

PYTHONPYCACHEPREFIX=/private/tmp/a93-pycache \
python3 -m unittest \
  backend.features.warehouse_recommendation_preview.test_runtime_budget \
  backend.features.warehouse_recommendation_preview.test_runtime_contract \
  backend.features.warehouse_recommendation_preview.test_runtime_access \
  backend.features.warehouse_recommendation_preview.test_runtime_preview

PYTHONPYCACHEPREFIX=/private/tmp/a93-pycache \
python3 -m unittest discover \
  -s backend/features/estimate_revision_impact -p 'test_*.py'

PYTHONPYCACHEPREFIX=/private/tmp/a93-pycache \
python3 -m unittest discover -s backend -p 'test_*.py'

git diff --check
```

Disposable PostgreSQL command/fixture определяется в A9.3a PLAN после approval;
тот же isolated fixture повторно используется в A9.3b для BEGIN/rollback/idle
и в A9.3d для auth/artifact SQL. Production DB для этих proofs запрещена.

## Success Criteria

A9.3 считается локально завершённым только когда:

- весь перечисленный variable-width SQL result surface имеет pre-libpq cap;
- доказан максимум 17,825,792 variable-width bytes для одного relevant pass,
  без ложного заявления о Python RSS;
- connect/slot/statement/cooperative deadline gates проходят failure matrix;
- exact cookie/2FA/director/company/project policy зафиксирована и протестирована;
- exact succeeded system job — единственный artifact source;
- auth, artifact и current evidence находятся в одной transaction snapshot;
- content/public result возникает только после rollback и cleanup;
- A7/A9.1/A9.2/full-backend regressions и static write/import gates зелёные;
- три свежих reviews не имеют Critical/Required;
- route/UI/package export/runtime registration/production остаются неизменными.

Даже после этого A9.3 status — `runtime substrate ready, HTTP not approved`.

## Boundaries

### Always

- fail closed, exact types/sets, fixed error codes, parameterized SQL;
- selected company/project and artifact source derived server-side;
- unconditional rollback and no content before cleanup;
- TDD plus fresh adversarial review at every checkpoint;
- preserve existing A7/A9.1/A9.2 public contracts unless spec is reopened.

### Ask first

- change byte/time/capacity limits;
- add/change A7 reason/version/interface;
- allow `зам_директора` or any project-scoped/warehouse role;
- expose any subject ID/hash/source field in HTTP;
- add persistent audit, cache, route, feature flag, nginx/systemd config or UI;
- use disposable PostgreSQL unless covered by the exact approval bundle below;
- commit, push, production contact or deployment.

### Never

- client report/source/hash/recommendation/content;
- `all_companies`, legacy company fallback or name-only project auth;
- latest-job lookup, foreign artifact oracle or raw job result response;
- inventory/warehouse writer, runtime/production DDL, commit, model/provider,
  notification/outbox. Единственное исключение — fixture-only CREATE/DROP в
  explicitly approved isolated local disposable PostgreSQL с unique test
  database/schema и обязательным teardown;
- abandoned timeout thread or claim of hard deadline from cooperative controls.

## Human approval requested

Предлагается утвердить одним решением следующие safe defaults:

1. A9.3 выполняется slices a→e без HTTP/UI/runtime registration.
2. Byte limits: 4 MiB aggregate JSON query, 1 KiB other text field, 64 bytes
   на selected NUMERIC text, 1 MiB aggregate text query, 17 MiB cumulative
   collector, 128 KiB guarded DB transport и 64 KiB canonical job
   payload/result.
3. Capacity/time: 1 in-flight per process, 1s slot wait, 5s connect, 5s SQL,
   30s cooperative detection budget с максимум одним 5s server-SQL overshoot
   при исправной timeout delivery; уже начатая pure phase, established
   libpq/network wait и cleanup не получают ложного exact wall-clock claim.
4. Future v1 authorization: cookie+2FA, exact company/project, только
   `директор`; все project-scoped roles запрещены.
5. Exact succeeded system-owned job ID only; no latest lookup.
6. No public hashes, no persistent read-audit, no route until a separate
   HTTP/ops spec is approved.
7. Approval включает только local disposable PostgreSQL proofs для A9.3a,
   A9.3b guarded BEGIN/rollback/idle и A9.3d SQL: unique test database/schema,
   fixture-only CREATE/DROP, no production host/data, explicit teardown. Любая
   установка, network access или нестандартный внешний DB всё равно требует
   отдельного разрешения.

Любое изменение первых шести contract defaults или седьмого test-authorization
пункта должно быть названо до PLAN/TASKS/implementation.
